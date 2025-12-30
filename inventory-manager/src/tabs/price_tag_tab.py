import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os
import time
import threading
import queue
import json
from pathlib import Path
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
import barcode
from barcode.writer import ImageWriter
import io

class PriceTagTab:
    def __init__(self):
        # Initialize config values - will throw errors if config file doesn't exist or values are missing
        self._validate_configuration()
        self.api_base_url = "https://arjanshaw.pythonanywhere.com"
    
    def _validate_configuration(self):
        """Validate that all required configuration values exist"""
        from config import AppConfig
        
        try:
            config = AppConfig()
            
            # Load all required config values
            required_keys = [
                'label_width_mm', 'label_height_mm', 'left_margin_mm',
                'gutter_spacing_mm', 'top_margin_mm', 'font_size',
                'price_font_size', 'price_y_pos', 'text_font_size',
                'barcode_y_pos', 'barcode_height', 'print_borders'
            ]
            
            for key in required_keys:
                st.session_state[key] = config.get(key)
                
        except Exception as e:
            st.error(f"Configuration error: {e}")
            st.stop()
    
    def _save_page_layout_config(self, key, value):
        """Save page layout configuration to config file"""
        from config import AppConfig
        
        try:
            config = AppConfig()
            current_config = config.get_all()
            current_config[key] = value
            config.update(current_config)
            st.session_state[key] = value
        except Exception as e:
            st.error(f"Error saving configuration: {e}")
    
    def _save_tag_design_config(self, key, value):
        """Save tag design configuration to config file"""
        # Both page layout and tag design are in the same config file now
        self._save_page_layout_config(key, value)
    
    def render(self):
        st.header("🏷️ Print Price Tags")
        
        # Check dependencies
        try:
            import barcode
            import reportlab
            st.success("✅ Printing dependencies available")
        except ImportError as e:
            st.error(f"Missing dependencies: {e}")
            return
        
        # Two columns for configuration
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📐 Page/Layout Configuration", expanded=True):
                self._render_page_layout_configuration()
        
        with col2:
            with st.expander("⚙️ Price Tag Design", expanded=True):
                self._render_price_tag_design_configuration()
        
        # Get all users for selection
        users = self._get_all_users()
        
        st.subheader("🔍 Select Records for Printing")
        
        # User selection combobox
        user_options = ["All Users"] + [f"{user.get('username', 'Unknown')} (ID: {user['id']})" for user in users]
        selected_user = st.selectbox(
            "Select User:",
            options=user_options,
            index=0,
            key="user_selection"
        )
        
        # Parse selected user ID
        selected_user_id = None
        if selected_user != "All Users":
            try:
                # Extract user ID from the selection string
                user_id_str = selected_user.split("(ID: ")[1].replace(")", "")
                selected_user_id = int(user_id_str)
            except:
                st.error("Invalid user selection")
                return
        
        # Get records for the selected user (or all records)
        records = self._get_records_for_user(selected_user_id)
        
        # Get all records for statistics
        all_records_response = requests.get(f"{self.api_base_url}/records?limit=1000")
        if all_records_response.status_code == 200:
            all_data = all_records_response.json()
            all_records = all_data.get('records', [])
            printed_count = len([r for r in all_records if r.get('barcode') and r['barcode'] not in [None, '', 'None']])
            total_count = len(all_records)
            
            # Filter selected user's printed count
            if selected_user_id:
                user_printed_count = len([r for r in all_records if r.get('barcode') and r['barcode'] not in [None, '', 'None'] and r.get('consignor_id') == selected_user_id])
                user_total_count = len([r for r in all_records if r.get('consignor_id') == selected_user_id])
            else:
                user_printed_count = printed_count
                user_total_count = total_count
            
            # Display statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Selected User Records", user_total_count)
            with col2:
                st.metric("Already Printed", f"{user_printed_count}/{user_total_count}")
            with col3:
                st.metric("Ready to Print", len(records))
        
        # Get last printed batch size from config
        last_batch_size = self._get_config_value('LAST_PRINT_BATCH_SIZE', '0')
        try:
            last_batch_size = int(last_batch_size)
        except:
            last_batch_size = 0
        
        # Management buttons
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Clear Recent Price Tags**")
            
            if last_batch_size > 0:
                st.info(f"Last printed batch: {last_batch_size} tags")
            
            clear_count = st.number_input(
                "Number of tags to clear:",
                min_value=0,
                max_value=1000,
                value=last_batch_size if last_batch_size > 0 else 10,
                step=1,
                key="clear_tag_count"
            )
            
            if st.button("🗑️ Clear Recent Tags", width='stretch', 
                       help=f"Remove barcodes from {clear_count} most recent printed records"):
                cleared_count = self._clear_recent_barcodes(clear_count)
                if cleared_count > 0:
                    st.success(f"✅ Cleared {cleared_count} recent price tags!")
                    st.rerun()
                else:
                    st.info("No recent price tags to clear")
        
        with col2:
            st.write("**Clear ALL Price Tags**")
            if st.button("🗑️ Clear ALL", width='stretch', 
                       help="Remove barcodes from ALL records (use with caution!)", type="secondary"):
                if st.checkbox("I understand this will remove ALL barcodes from ALL records"):
                    try:
                        # Get all records with barcodes
                        response = requests.get(f"{self.api_base_url}/records?limit=1000")
                        if response.status_code == 200:
                            data = response.json()
                            records_with_barcodes = [r for r in data.get('records', []) 
                                                    if r.get('barcode') and r['barcode'] not in [None, '', 'None']]
                            clear_count = len(records_with_barcodes)
                            
                            if st.button(f"CONFIRM: Clear ALL {clear_count} barcodes", type="primary"):
                                # Clear barcodes via API
                                for record in records_with_barcodes:
                                    requests.put(f"{self.api_base_url}/records/{record['id']}", 
                                                json={'barcode': None})
                                st.success(f"✅ Cleared ALL {clear_count} price tags!")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error clearing barcodes: {e}")
        
        if not records:
            st.info(f"No records found for {'selected user' if selected_user_id else 'any user'} that need price tags.")
            return
        
        st.subheader(f"📋 Records Ready for Printing ({len(records)} found)")
        
        # Selection controls
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("✅ Select All", width='stretch'):
                st.session_state.select_all = True
                st.rerun()
        with col2:
            if st.button("❌ Deselect All", width='stretch'):
                st.session_state.select_all = False
                st.rerun()
        with col3:
            st.number_input("Select First N", min_value=0, value=0, key="select_first_n")
        
        # Display records in a table with checkboxes
        display_data = []
        for i, record in enumerate(records):
            current_select_all = st.session_state.get('select_all', False)
            select_first_n = st.session_state.get('select_first_n', 0)
            auto_select = current_select_all or (select_first_n > 0 and i < select_first_n)
            
            display_data.append({
                'Select': auto_select,
                'ID': record['id'],
                'Artist': record['artist'],
                'Title': record['title'],
                'Genre': record.get('genre_name', 'Unknown'),
                'Price': f"${record.get('store_price', 0):.2f}",
                'Condition': record.get('condition', 'Unknown'),
                'Added Date': record.get('created_at', ''),
                'User': self._get_username_by_id(record.get('consignor_id'), users)
            })
        
        df = pd.DataFrame(display_data)
        edited_df = st.data_editor(
            df,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", default=False),
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "Artist": st.column_config.TextColumn("Artist", disabled=True),
                "Title": st.column_config.TextColumn("Title", disabled=True),
                "Genre": st.column_config.TextColumn("Genre", disabled=True),
                "Price": st.column_config.TextColumn("Price", disabled=True),
                "Condition": st.column_config.TextColumn("Condition", disabled=True),
                "Added Date": st.column_config.DatetimeColumn("Added Date", disabled=True),
                "User": st.column_config.TextColumn("User", disabled=True)
            },
            hide_index=True,
            width='stretch',
            height=400,
            key="price_tag_editor"
        )
        
        selected_records = edited_df[edited_df['Select'] == True]
        
        if len(selected_records) > 0:
            st.subheader(f"🖨️ Selected for Printing ({len(selected_records)} records)")
            
            # Show summary of selected records
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Items", len(selected_records))
            with col2:
                total_value = sum(float(r['Price'].replace('$', '')) for r in selected_records.to_dict('records'))
                st.metric("Total Value", f"${total_value:.2f}")
            with col3:
                if selected_user_id:
                    user_name = self._get_username_by_id(selected_user_id, users)
                    st.metric("User", user_name)
            
            # Print button
            if st.button("🖨️ PRINT PRICE TAGS", type="primary", use_container_width=True):
                self._print_tags(selected_records['ID'].tolist(), selected_user_id)
    
    def _render_page_layout_configuration(self):
        st.write("**Page Layout Settings**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            label_width_mm = st.number_input(
                "Label Width (mm)",
                min_value=10.0,
                max_value=100.0,
                value=st.session_state.label_width_mm,
                step=0.5,
                key="widget_label_width_mm",
                on_change=lambda: self._save_page_layout_config('label_width_mm', st.session_state.widget_label_width_mm)
            )
            
            label_height_mm = st.number_input(
                "Label Height (mm)",
                min_value=10.0,
                max_value=100.0,
                value=st.session_state.label_height_mm,
                step=0.5,
                key="widget_label_height_mm",
                on_change=lambda: self._save_page_layout_config('label_height_mm', st.session_state.widget_label_height_mm)
            )
            
            left_margin_mm = st.number_input(
                "Left Margin (mm)",
                min_value=0.0,
                max_value=50.0,
                value=st.session_state.left_margin_mm,
                step=0.5,
                key="widget_left_margin_mm",
                on_change=lambda: self._save_page_layout_config('left_margin_mm', st.session_state.widget_left_margin_mm)
            )
        
        with col2:
            gutter_spacing_mm = st.number_input(
                "Gutter Spacing (mm)",
                min_value=0.0,
                max_value=50.0,
                value=st.session_state.gutter_spacing_mm,
                step=0.5,
                key="widget_gutter_spacing_mm",
                on_change=lambda: self._save_page_layout_config('gutter_spacing_mm', st.session_state.widget_gutter_spacing_mm)
            )
            
            top_margin_mm = st.number_input(
                "Top Margin (mm)",
                min_value=0.0,
                max_value=50.0,
                value=st.session_state.top_margin_mm,
                step=0.5,
                key="widget_top_margin_mm",
                on_change=lambda: self._save_page_layout_config('top_margin_mm', st.session_state.widget_top_margin_mm)
            )
            
            font_size = st.number_input(
                "Base Font Size",
                min_value=4,
                max_value=20,
                value=st.session_state.font_size,
                key="widget_font_size",
                on_change=lambda: self._save_page_layout_config('font_size', st.session_state.widget_font_size)
            )
    
    def _render_price_tag_design_configuration(self):
        st.write("**Price Tag Design Settings**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            price_font_size = st.number_input(
                "Price Font Size",
                min_value=6,
                max_value=20,
                value=st.session_state.price_font_size,
                key="widget_price_font_size",
                on_change=lambda: self._save_tag_design_config('price_font_size', st.session_state.widget_price_font_size)
            )
            
            price_y_pos = st.number_input(
                "Price Y Position (mm)",
                min_value=0.0,
                max_value=20.0,
                value=st.session_state.price_y_pos,
                step=0.5,
                key="widget_price_y_pos",
                on_change=lambda: self._save_tag_design_config('price_y_pos', st.session_state.widget_price_y_pos)
            )
            
            text_font_size = st.number_input(
                "Text Font Size",
                min_value=4,
                max_value=12,
                value=st.session_state.text_font_size,
                key="widget_text_font_size",
                on_change=lambda: self._save_tag_design_config('text_font_size', st.session_state.widget_text_font_size)
            )
                
        with col2:
            barcode_y_pos = st.number_input(
                "Barcode Y Position (mm)",
                min_value=0.0,
                max_value=20.0,
                value=st.session_state.barcode_y_pos,
                step=0.5,
                key="widget_barcode_y_pos",
                on_change=lambda: self._save_tag_design_config('barcode_y_pos', st.session_state.widget_barcode_y_pos)
            )
            
            barcode_height = st.number_input(
                "Barcode Height (mm)",
                min_value=0.0,
                max_value=12.0,
                value=st.session_state.barcode_height,
                step=0.5,
                key="widget_barcode_height",
                on_change=lambda: self._save_tag_design_config('barcode_height', st.session_state.widget_barcode_height)
            )
            
            print_borders = st.checkbox(
                "Print Borders Around Labels",
                value=st.session_state.print_borders,
                key="widget_print_borders",
                on_change=lambda: self._save_tag_design_config('print_borders', st.session_state.widget_print_borders)
            )

    def _print_tags(self, record_ids, user_id=None):
        """Print price tags for selected records"""
        if not record_ids:
            st.error("❌ No records selected")
            return
        
        # Initialize session state for printing
        st.session_state.print_status = "processing"
        st.session_state.print_message = f"🔄 Starting price tag generation for {len(record_ids)} records..."
        st.session_state.print_success = False

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("Step 1/3: Assigning barcodes...")
        barcode_mapping = self._assign_barcodes(record_ids)
        progress_bar.progress(33)
        
        if not barcode_mapping:
            st.session_state.print_status = "error"
            st.session_state.print_message = "❌ Failed to assign barcodes"
            st.session_state.print_success = False
            progress_bar.empty()
            status_text.empty()
            return
        
        status_text.text("Step 2/3: Loading record data...")
        # Get records via API
        try:
            response = requests.post(f"{self.api_base_url}/records/by-ids",
                                   json={'record_ids': record_ids})
            if response.status_code == 200:
                data = response.json()
                records_to_print = data.get('records', [])
            else:
                st.error("Failed to get records")
                return
        except Exception as e:
            st.error(f"Error getting records: {e}")
            return
        
        progress_bar.progress(66)
        
        status_text.text("Step 3/3: Generating PDF...")
        result_queue = queue.Queue()
        
        layout_params = {
            'price_font_size': st.session_state.price_font_size,
            'price_y_pos': st.session_state.price_y_pos,
            'text_font_size': st.session_state.text_font_size,
            'barcode_y_pos': st.session_state.barcode_y_pos,
            'barcode_height': st.session_state.barcode_height,
            'print_borders': st.session_state.print_borders
        }
        
        page_layout_params = {
            'label_width_mm': st.session_state.label_width_mm,
            'label_height_mm': st.session_state.label_height_mm,
            'left_margin_mm': st.session_state.left_margin_mm,
            'gutter_spacing_mm': st.session_state.gutter_spacing_mm,
            'top_margin_mm': st.session_state.top_margin_mm,
            'font_size': st.session_state.font_size
        }
        
        def generate_pdf_thread():
            pdf_path = self._generate_pdf(records_to_print, barcode_mapping, layout_params, page_layout_params)
            result_queue.put(('success', pdf_path))
        
        pdf_thread = threading.Thread(target=generate_pdf_thread)
        pdf_thread.daemon = True
        pdf_thread.start()
        
        pdf_thread.join(timeout=30)
        
        progress_bar.progress(100)
        
        if pdf_thread.is_alive():
            st.session_state.print_status = "error"
            st.session_state.print_message = "❌ PDF generation timed out after 30 seconds"
            st.session_state.print_success = False
        else:
            try:
                result_type, result_data = result_queue.get_nowait()
                
                if result_type == 'success' and result_data and os.path.exists(result_data):
                    with open(result_data, "rb") as f:
                        st.session_state.pdf_data = f.read()
                    
                    # Create filename with user info
                    if user_id:
                        users = self._get_all_users()
                        user_name = self._get_username_by_id(user_id, users).replace(" ", "_")
                        filename = f"price_tags_{user_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    else:
                        filename = f"price_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    
                    st.session_state.pdf_filename = filename
                    
                    os.unlink(result_data)
                    
                    # Save the batch size to config for future clearing
                    batch_size = len(record_ids)
                    self._save_config_value('LAST_PRINT_BATCH_SIZE', str(batch_size))
                    
                    st.session_state.print_status = "completed"
                    st.session_state.print_message = f"✅ Successfully generated price tags for {batch_size} records"
                    st.session_state.print_success = True
                else:
                    st.session_state.print_status = "error"
                    st.session_state.print_message = f"❌ PDF generation failed"
                    st.session_state.print_success = False
            except queue.Empty:
                st.session_state.print_status = "error"
                st.session_state.print_message = "❌ PDF generation failed - no result returned"
                st.session_state.print_success = False
        
        progress_bar.empty()
        status_text.empty()
        
        # Display result
        if st.session_state.print_success:
            st.success(st.session_state.print_message)
            
            # Show download button
            st.download_button(
                label="📄 Download Price Tags PDF",
                data=st.session_state.pdf_data,
                file_name=st.session_state.pdf_filename,
                mime="application/pdf",
                use_container_width=True,
                key=f"download_pdf_{datetime.now().strftime('%H%M%S')}"
            )
        else:
            st.error(st.session_state.print_message)
            
            # Try to show any available PDF
            if hasattr(st.session_state, 'pdf_data') and st.session_state.pdf_data:
                st.download_button(
                    label="⚠️ Download Partial PDF",
                    data=st.session_state.pdf_data,
                    file_name=f"partial_{st.session_state.pdf_filename}",
                    mime="application/pdf",
                    use_container_width=True
                )
    
    # API Methods
    def _get_all_users(self):
        """Get all users via API"""
        try:
            response = requests.get(f"{self.api_base_url}/users")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('users', [])
            return []
        except Exception as e:
            st.error(f"Error getting users: {e}")
            return []
    
    def _get_records_for_user(self, user_id=None):
        """Get records without barcodes for a specific user (or all users)"""
        try:
            if user_id:
                # Get all records for this user, then filter those without barcodes
                response = requests.get(f"{self.api_base_url}/records/user/{user_id}")
            else:
                # Get all records without barcodes
                response = requests.get(f"{self.api_base_url}/records/no-barcodes")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    records = data.get('records', [])
                    
                    if user_id:
                        # Filter for records without barcodes
                        records = [r for r in records if not r.get('barcode') or r['barcode'] in [None, '', 'None']]
                    
                    return records
            return []
        except Exception as e:
            st.error(f"Error getting records: {e}")
            return []
    
    def _get_username_by_id(self, user_id, users_list):
        """Get username by user ID from users list"""
        if not user_id:
            return "Store Owned"
        
        for user in users_list:
            if user['id'] == user_id:
                return user.get('username', f"User {user_id}")
        
        return f"User {user_id}"
    
    def _assign_barcodes(self, record_ids):
        """Assign barcodes to records via API"""
        if not record_ids:
            return {}
        
        try:
            response = requests.post(
                f"{self.api_base_url}/barcodes/assign",
                json={'record_ids': record_ids}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('barcode_mapping', {})
            return {}
        except Exception as e:
            st.error(f"Error assigning barcodes: {e}")
            return {}
    
    def _clear_recent_barcodes(self, count):
        """
        Clear barcodes from the most recent X records that have barcodes
        """
        try:
            # Get all records
            response = requests.get(f"{self.api_base_url}/records?limit=1000")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    records = data.get('records', [])
                    
                    # Filter records with barcodes and sort by ID (most recent first)
                    records_with_barcodes = [
                        r for r in records 
                        if r.get('barcode') and r['barcode'] not in [None, '', 'None']
                    ]
                    records_with_barcodes.sort(key=lambda x: x.get('id', 0), reverse=True)
                    
                    # Clear barcodes for the most recent records
                    cleared_count = 0
                    for record in records_with_barcodes[:count]:
                        success = self._clear_barcode(record['id'])
                        if success:
                            cleared_count += 1
                    
                    return cleared_count
            return 0
        except Exception as e:
            st.error(f"Error clearing barcodes: {e}")
            return 0
    
    def _clear_barcode(self, record_id):
        """Clear barcode for a record via API"""
        try:
            response = requests.put(
                f"{self.api_base_url}/records/{record_id}",
                json={'barcode': None}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error clearing barcode: {e}")
            return False
    
    def _generate_barcode(self, barcode_number):
        """Generate barcode image"""
        if not barcode_number:
            return None
            
        try:
            barcode_class = barcode.get_barcode_class('code128')
            barcode_obj = barcode_class(str(barcode_number), writer=ImageWriter())
            
            buffer = io.BytesIO()
            barcode_obj.write(buffer, options={
                'module_height': 6.0,
                'font_size': 0,
                'quiet_zone': 1.0,
                'write_text': False
            })
            buffer.seek(0)
            
            return buffer
        except Exception as e:
            st.error(f"Error generating barcode: {e}")
            return None
    
    def _generate_pdf(self, records, barcode_mapping, layout_params, page_layout_params):
        """Generate PDF with price tags"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        output_path = temp_file.name
        temp_file.close()

        c = canvas.Canvas(output_path, pagesize=letter)
        
        # Layout parameters
        label_width = page_layout_params.get('label_width_mm', 45.0) * mm
        label_height = page_layout_params.get('label_height_mm', 16.8) * mm
        left_margin = page_layout_params.get('left_margin_mm', 6.5) * mm
        gutter_spacing = page_layout_params.get('gutter_spacing_mm', 6.5) * mm
        top_margin = page_layout_params.get('top_margin_mm', 14.0) * mm
        rows = 15
        columns = 4

        labels_per_page = rows * columns
        current_label = 0
        
        errors = []
        
        for idx, record in enumerate(records):
            if current_label % labels_per_page == 0 and current_label > 0:
                c.showPage()
            
            row = (current_label % labels_per_page) // columns
            col = (current_label % labels_per_page) % columns
            
            x = left_margin + col * (label_width + gutter_spacing)
            y = letter[1] - top_margin - (row + 1) * label_height
            
            barcode_number = barcode_mapping.get(str(record['id']))
            
            error = self._draw_tag(c, x, y, label_width, label_height, record, barcode_number, layout_params)
            if error:
                errors.append(f"Record ID {record['id']}: {error}")

            current_label += 1
        
        c.save()
        
        if errors:
            st.warning(f"Some text overflow errors detected (printed anyway):\n" + "\n".join(errors[:3]))
        
        return output_path
    
    def _draw_tag(self, c, x, y, label_width, label_height, record, barcode_number, params):
        """Draw a single price tag"""
        left_bound = x + 2 * mm
        right_bound = x + label_width - 2 * mm
        printable_width = label_width - 4 * mm

        if params.get('print_borders', True):
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.5)
            c.rect(x, y, label_width, label_height, stroke=1, fill=0)
        
        top_start = y + label_height - 2 * mm

        # Draw price
        price = record.get('store_price', 0.0)
        price_text = f"${price:.2f}"
        c.setFont("Helvetica-Bold", params['price_font_size'])
        price_width = c.stringWidth(price_text, "Helvetica-Bold", params['price_font_size'])
        
        if price_width > printable_width:
            return f"Price text too wide: '{price_text}'"
        
        price_x = left_bound + (printable_width - price_width) / 2
        price_y = top_start - (params['price_y_pos'] * mm)
        c.drawString(price_x, price_y, price_text)
        
        # Draw genre and artist
        genre = record.get('genre_name', 'Unknown')[:15]
        artist = record.get('artist', 'Unknown')[:20]
        
        genre_artist_text = f"{genre} | {artist}"
        
        MAX_LENGTH = 35
        SEPARATOR = ' | '
        
        if len(genre_artist_text) > MAX_LENGTH:
            max_artist_length = MAX_LENGTH - len(genre) - len(SEPARATOR)
            
            if max_artist_length > 0:
                if len(artist) > max_artist_length:
                    artist = artist[:max_artist_length-1] + '…'
                genre_artist_text = f"{genre}{SEPARATOR}{artist}"
            else:
                genre_artist_text = genre[:MAX_LENGTH-1] + '…'
        
        c.setFont("Helvetica", params['text_font_size'])
        genre_artist_width = c.stringWidth(genre_artist_text, "Helvetica", params['text_font_size'])
        
        if genre_artist_width > printable_width:
            return f"Genre/Artist text too wide: '{genre_artist_text}'"
        
        genre_artist_x = left_bound + (printable_width - genre_artist_width) / 2
        genre_artist_y = price_y - 4 * mm
        c.drawString(genre_artist_x, genre_artist_y, genre_artist_text)
        
        # Draw barcode
        if barcode_number:
            barcode_bytes = self._generate_barcode(barcode_number)
            if barcode_bytes:
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    temp_file.write(barcode_bytes.getvalue())
                    temp_path = temp_file.name
                
                barcode_height = params['barcode_height'] * mm
                barcode_width = 25 * mm
                
                if barcode_width > printable_width:
                    os.unlink(temp_path)
                    return f"Barcode too wide"
                
                barcode_x = left_bound + (printable_width - barcode_width) / 2
                barcode_y = y + (params['barcode_y_pos'] * mm)
                
                c.drawImage(temp_path, barcode_x, barcode_y, width=barcode_width, height=barcode_height)
                os.unlink(temp_path)
        
        return None
    
    def _get_config_value(self, config_key, default=None):
        """Get config value via API"""
        try:
            response = requests.get(f"{self.api_base_url}/config/{config_key}")
            if response.status_code == 200:
                data = response.json()
                return data.get('config_value', default)
            return default
        except Exception as e:
            st.error(f"Error getting config: {e}")
            return default
    
    def _save_config_value(self, config_key, config_value):
        """Save config value via API"""
        try:
            response = requests.put(
                f"{self.api_base_url}/config/{config_key}",
                json={'config_value': config_value}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error saving config: {e}")
            return False