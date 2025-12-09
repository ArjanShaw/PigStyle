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

class PriceTagTab:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        from handlers.price_tag_handler import PriceTagHandler
        self.price_tag_handler = PriceTagHandler(db_manager)
        
        # Initialize config values - will throw errors if config file doesn't exist or values are missing
        self._validate_configuration()
    
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
        
        if hasattr(st.session_state, 'print_status') and st.session_state.print_status:
            if hasattr(st.session_state, 'print_success') and st.session_state.print_success:
                st.success(st.session_state.print_message)
            else:
                st.error(st.session_state.print_message)
        
        import barcode
        import reportlab
        st.success("✅ Printing dependencies available")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📐 Page/Layout Configuration", expanded=True):
                self._render_page_layout_configuration()
        
        with col2:
            with st.expander("⚙️ Price Tag Design", expanded=True):
                self._render_price_tag_design_configuration()
        
        records = self.price_tag_handler.get_records_without_barcodes()
        
        st.subheader("Manage Printed Tags")
        
        all_records = self.db_manager.get_all_records()
        printed_count = len(all_records[all_records['barcode'].notna() & (all_records['barcode'] != '')])
        total_count = len(all_records)
        st.metric("Printed", f"{printed_count}/{total_count}")
        
        # Get last printed batch size from database config
        last_batch_size = st.session_state.db_manager.get_config_value('LAST_PRINT_BATCH_SIZE', '0')
        try:
            last_batch_size = int(last_batch_size)
        except:
            last_batch_size = 0
        
        col1, col2 = st.columns(2)
        with col1:
            # Clear barcodes section with last batch size
            st.write("**Clear Recent Price Tags**")
            
            # Show last batch size info
            if last_batch_size > 0:
                st.info(f"Last printed batch: {last_batch_size} tags")
            
            # Input for number of tags to clear with default from last batch
            clear_count = st.number_input(
                "Number of tags to clear:",
                min_value=0,
                max_value=1000,
                value=last_batch_size if last_batch_size > 0 else 10,
                step=1,
                key="clear_tag_count"
            )
            
            if st.button("🗑️ Clear Price Tags", width='stretch', 
                       help=f"Remove barcodes from {clear_count} most recent printed records"):
                cleared_count = self.price_tag_handler.clear_recent_barcodes(clear_count)
                if cleared_count > 0:
                    st.success(f"✅ Cleared {cleared_count} recent price tags!")
                    st.rerun()
                else:
                    st.info("No recent price tags to clear")
        
        with col2:
            # Other buttons remain
            if st.button("🗑️ Clear ALL Price Tags", width='stretch', 
                       help="Remove barcodes from ALL records (use with caution!)", type="secondary"):
                if st.checkbox("I understand this will remove ALL barcodes from ALL records"):
                    all_records = self.db_manager.get_all_records()
                    records_with_barcodes = all_records[
                        (all_records['barcode'].notna()) & 
                        (all_records['barcode'] != '') & 
                        (all_records['barcode'] != 'None')
                    ]
                    clear_count = len(records_with_barcodes)
                    
                    if st.button(f"CONFIRM: Clear ALL {clear_count} barcodes", type="primary"):
                        for _, record in records_with_barcodes.iterrows():
                            st.session_state.db_manager.update_record(record['id'], {'barcode': None})
                        st.success(f"✅ Cleared ALL {clear_count} price tags!")
                        st.rerun()
        
        if not records:
            st.info("All records have price tags printed.")
            return
        
        st.subheader(f"Records Needing Price Tags ({len(records)} found)")
        
        col1, col2 = st.columns(2)
        with col1:
            select_all = getattr(st.session_state, 'select_all', False)
            if select_all:
                if st.button("❌ Deselect All", width='stretch'):
                    st.session_state.select_all = False
                    st.rerun()
            else:
                if st.button("✅ Select All", width='stretch'):
                    st.session_state.select_all = True
                    st.rerun()
        
        with col2:
            print_first_x = getattr(st.session_state, 'print_first_x', 0)
            st.number_input("Print First X Labels", min_value=0, value=print_first_x, key="print_first_x")
        
        display_data = []
        for i, record in enumerate(records):
            current_select_all = getattr(st.session_state, 'select_all', False)
            current_print_first_x = getattr(st.session_state, 'print_first_x', 0)
            auto_select = current_select_all or (current_print_first_x > 0 and i < current_print_first_x)
            
            display_data.append({
                'Select': auto_select,
                'ID': record['id'],
                'Artist': record['artist'],
                'Title': record['title'],
                'Genre': record.get('genre_name', 'Unknown'),
                'Price': f"${record.get('store_price', 0):.2f}",
                'Added Date': record.get('created_at', '')
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
                "Added Date": st.column_config.DatetimeColumn("Added Date", disabled=True)
            },
            hide_index=True,
            width='stretch',
            key="price_tag_editor"
        )
        
        selected_records = edited_df[edited_df['Select'] == True]
        
        if len(selected_records) > 0:
            st.subheader(f"Selected for Printing ({len(selected_records)} records)")
            st.dataframe(selected_records[['ID', 'Artist', 'Title', 'Genre', 'Price']], hide_index=True)
            
            if st.button("🖨️ Print Price Tags", type="primary", width='stretch'):
                self._print_tags(selected_records['ID'].tolist())
    
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
    
    def _print_tags(self, record_ids):
        if not record_ids:
            st.session_state.print_status = "error"
            st.session_state.print_message = "❌ No records selected"
            st.session_state.print_success = False
            st.rerun()
            return
        
        st.session_state.print_status = "processing"
        st.session_state.print_message = f"🔄 Starting price tag generation for {len(record_ids)} records..."
        st.session_state.print_success = False

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("Step 1/3: Assigning barcodes...")
        barcode_mapping = self.price_tag_handler.assign_barcodes(record_ids)
        progress_bar.progress(33)
        
        if not barcode_mapping:
            st.session_state.print_status = "error"
            st.session_state.print_message = "❌ Failed to assign barcodes"
            st.session_state.print_success = False
            progress_bar.empty()
            status_text.empty()
            st.rerun()
            return
        
        status_text.text("Step 2/3: Loading record data...")
        all_records = self.db_manager.get_all_records()
        records_to_print = all_records[all_records['id'].isin(record_ids)]
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
            pdf_path = self.price_tag_handler.generate_pdf(records_to_print, barcode_mapping, layout_params, page_layout_params)
            result_queue.put(('success', pdf_path))
        
        pdf_thread = threading.Thread(target=generate_pdf_thread)
        pdf_thread.daemon = True
        pdf_thread.start()
        
        pdf_thread.join(timeout=20)
        
        progress_bar.progress(100)
        
        if pdf_thread.is_alive():
            st.session_state.print_status = "error"
            st.session_state.print_message = "❌ PDF generation timed out after 20 seconds"
            st.session_state.print_success = False
        else:
            result_type, result_data = result_queue.get_nowait()
            
            if result_type == 'success' and result_data and os.path.exists(result_data):
                with open(result_data, "rb") as f:
                    st.session_state.pdf_data = f.read()
                st.session_state.pdf_filename = f"price_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                
                os.unlink(result_data)
                
                # Save the batch size to config for future clearing
                batch_size = len(record_ids)
                st.session_state.db_manager.set_config_value('LAST_PRINT_BATCH_SIZE', str(batch_size))
                
                st.session_state.print_status = "completed"
                st.session_state.print_message = f"✅ Successfully generated price tags for {batch_size} records (batch size saved)"
                st.session_state.print_success = True
            else:
                st.session_state.print_status = "error"
                st.session_state.print_message = f"❌ PDF generation failed: {result_data}"
                st.session_state.print_success = False
        
        progress_bar.empty()
        status_text.empty()
        
        if hasattr(st.session_state, 'print_success') and st.session_state.print_success and 'pdf_data' in st.session_state:
            st.download_button(
                label="📄 Download Price Tags PDF",
                data=st.session_state.pdf_data,
                file_name=st.session_state.pdf_filename,
                mime="application/pdf",
                width='stretch',
                key=f"download_pdf_{datetime.now().strftime('%H%M%S')}"
            )
        
        if hasattr(st.session_state, 'print_success') and not st.session_state.print_success:
            st.rerun()