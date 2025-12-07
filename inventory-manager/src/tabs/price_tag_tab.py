# inventory-manager/src/tabs/price_tag_tab.py

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
        
        # Initialize session state with configuration values from files
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration values from files"""
        # Load page/layout configuration from app_config.json
        app_config_path = Path("app_config.json")
        if app_config_path.exists():
            try:
                with open(app_config_path, 'r') as f:
                    app_config = json.load(f)
                
                # Set page/layout config values in session state
                layout_keys = ['label_width_mm', 'label_height_mm', 'left_margin_mm', 
                             'gutter_spacing_mm', 'top_margin_mm', 'font_size']
                for key in layout_keys:
                    if key not in st.session_state:
                        st.session_state[key] = app_config.get(key, self._get_default_value(key))
            except Exception as e:
                st.error(f"Error loading app config: {e}")
                self._set_default_layout_values()
        else:
            self._set_default_layout_values()
        
        # Load price tag design configuration from print_config.json
        print_config_path = Path("src/print_config.json")
        if print_config_path.exists():
            try:
                with open(print_config_path, 'r') as f:
                    print_config = json.load(f)
                
                # Set design config values in session state
                design_keys = ['price_font_size', 'price_y_pos', 'text_font_size', 
                             'barcode_y_pos', 'barcode_height', 'print_borders']
                for key in design_keys:
                    if key not in st.session_state:
                        st.session_state[key] = print_config.get(key, self._get_default_value(key))
            except Exception as e:
                st.error(f"Error loading print config: {e}")
                self._set_default_design_values()
        else:
            self._set_default_design_values()
    
    def _get_default_value(self, key):
        """Get default value for a configuration key"""
        defaults = {
            # Page/Layout defaults
            'label_width_mm': 45.0,
            'label_height_mm': 16.8,
            'left_margin_mm': 6.5,
            'gutter_spacing_mm': 6.5,
            'top_margin_mm': 14.0,
            'font_size': 7,
            # Design defaults
            'price_font_size': 10,
            'price_y_pos': 12.0,
            'text_font_size': 6,
            'barcode_y_pos': 2.0,
            'barcode_height': 6.0,
            'print_borders': True
        }
        return defaults.get(key)
    
    def _set_default_layout_values(self):
        """Set default page/layout values in session state"""
        layout_defaults = {
            'label_width_mm': 45.0,
            'label_height_mm': 16.8,
            'left_margin_mm': 6.5,
            'gutter_spacing_mm': 6.5,
            'top_margin_mm': 14.0,
            'font_size': 7
        }
        for key, value in layout_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def _set_default_design_values(self):
        """Set default design values in session state"""
        design_defaults = {
            'price_font_size': 10,
            'price_y_pos': 12.0,
            'text_font_size': 6,
            'barcode_y_pos': 2.0,
            'barcode_height': 6.0,
            'print_borders': True
        }
        for key, value in design_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    def _save_page_layout_config(self, key, value):
        """Save a page/layout configuration value"""
        # Update session state
        st.session_state[key] = value
        
        # Save to app_config.json
        config_path = Path("app_config.json")
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # Update the specific key
            config[key] = value
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
        except Exception as e:
            st.error(f"❌ Error saving page layout: {e}")
    
    def _save_tag_design_config(self, key, value):
        """Save a price tag design configuration value"""
        # Update session state
        st.session_state[key] = value
        
        # Save to print_config.json
        config_path = Path("src/print_config.json")
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
            else:
                config = {}
            
            # Update the specific key
            config[key] = value
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
        except Exception as e:
            st.error(f"❌ Error saving tag design: {e}")
    
    def render(self):
        st.header("🏷️ Print Price Tags")
        
        # Show status message - check if it exists first
        if hasattr(st.session_state, 'print_status') and st.session_state.print_status:
            if hasattr(st.session_state, 'print_success') and st.session_state.print_success:
                st.success(st.session_state.print_message)
            else:
                st.error(st.session_state.print_message)
        
        # Check dependencies
        import barcode
        import reportlab
        st.success("✅ Printing dependencies available")
        
        # TWO SEPARATE CONFIGURATION SECTIONS
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📐 Page/Layout Configuration", expanded=True):
                self._render_page_layout_configuration()
        
        with col2:
            with st.expander("⚙️ Price Tag Design", expanded=True):
                self._render_price_tag_design_configuration()
        
        # Get records without barcodes - ORDERED BY ID (latest first)
        records = self.price_tag_handler.get_records_without_barcodes()
        
        # MANAGEMENT SECTION
        st.subheader("Manage Printed Tags")
        
        # Show printed count using API
        all_records = self.db_manager.get_all_records()
        printed_count = len(all_records[all_records['barcode'].notna() & (all_records['barcode'] != '')])
        total_count = len(all_records)
        st.metric("Printed", f"{printed_count}/{total_count}")
        
        # Add button to clear recent price tags (last 24 hours)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear Recent Price Tags (last 24 hours)", use_container_width=True, 
                       help="Remove barcodes from records created in the last 24 hours"):
                cleared_count = self.price_tag_handler.clear_recent_barcodes()
                if cleared_count > 0:
                    st.success(f"✅ Cleared {cleared_count} recent price tags!")
                    st.rerun()
                else:
                    st.info("No recent price tags to clear")
        
        if not records:
            st.info("All records have price tags printed.")
            return
        
        st.subheader(f"Records Needing Price Tags ({len(records)} found)")
        
        # Toggle Select All button - check if it exists first
        col1, col2 = st.columns(2)
        with col1:
            select_all = getattr(st.session_state, 'select_all', False)
            if select_all:
                if st.button("❌ Deselect All", use_container_width=True):
                    st.session_state.select_all = False
                    st.rerun()
            else:
                if st.button("✅ Select All", use_container_width=True):
                    st.session_state.select_all = True
                    st.rerun()
        
        # Print first X labels field - REMOVED MAX VALUE LIMIT
        with col2:
            print_first_x = getattr(st.session_state, 'print_first_x', 0)
            st.number_input("Print First X Labels", min_value=0, value=print_first_x, key="print_first_x")
        
        # Display records table - ordered by ID (latest first)
        display_data = []
        for i, record in enumerate(records):
            # If print_first_x is set and we're within the range, auto-select
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
            use_container_width=True,
            key="price_tag_editor"
        )
        
        selected_records = edited_df[edited_df['Select'] == True]
        
        if len(selected_records) > 0:
            st.subheader(f"Selected for Printing ({len(selected_records)} records)")
            st.dataframe(selected_records[['ID', 'Artist', 'Title', 'Genre', 'Price']], hide_index=True)
            
            if st.button("🖨️ Print Price Tags", type="primary", use_container_width=True):
                self._print_tags(selected_records['ID'].tolist())
    
    def _render_page_layout_configuration(self):
        """Render page/layout configuration settings with auto-save"""
        st.write("**Page Layout Settings**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Label Width - using unique widget key
            label_width_mm = st.number_input(
                "Label Width (mm)",
                min_value=10.0,
                max_value=100.0,
                value=st.session_state.label_width_mm,
                step=0.5,
                key="widget_label_width_mm",
                on_change=lambda: self._save_page_layout_config('label_width_mm', st.session_state.widget_label_width_mm)
            )
            
            # Label Height - using unique widget key
            label_height_mm = st.number_input(
                "Label Height (mm)",
                min_value=10.0,
                max_value=100.0,
                value=st.session_state.label_height_mm,
                step=0.5,
                key="widget_label_height_mm",
                on_change=lambda: self._save_page_layout_config('label_height_mm', st.session_state.widget_label_height_mm)
            )
            
            # Left Margin - using unique widget key
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
            # Gutter Spacing - using unique widget key
            gutter_spacing_mm = st.number_input(
                "Gutter Spacing (mm)",
                min_value=0.0,
                max_value=50.0,
                value=st.session_state.gutter_spacing_mm,
                step=0.5,
                key="widget_gutter_spacing_mm",
                on_change=lambda: self._save_page_layout_config('gutter_spacing_mm', st.session_state.widget_gutter_spacing_mm)
            )
            
            # Top Margin - using unique widget key
            top_margin_mm = st.number_input(
                "Top Margin (mm)",
                min_value=0.0,
                max_value=50.0,
                value=st.session_state.top_margin_mm,
                step=0.5,
                key="widget_top_margin_mm",
                on_change=lambda: self._save_page_layout_config('top_margin_mm', st.session_state.widget_top_margin_mm)
            )
            
            # Font Size - using unique widget key
            font_size = st.number_input(
                "Base Font Size",
                min_value=4,
                max_value=20,
                value=st.session_state.font_size,
                key="widget_font_size",
                on_change=lambda: self._save_page_layout_config('font_size', st.session_state.widget_font_size)
            )
    
    def _render_price_tag_design_configuration(self):
        """Render price tag design configuration settings with auto-save"""
        st.write("**Price Tag Design Settings**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Price Font Size - using unique widget key
            price_font_size = st.number_input(
                "Price Font Size",
                min_value=6,
                max_value=20,
                value=st.session_state.price_font_size,
                key="widget_price_font_size",
                on_change=lambda: self._save_tag_design_config('price_font_size', st.session_state.widget_price_font_size)
            )
            
            # Price Y Position - using unique widget key
            price_y_pos = st.number_input(
                "Price Y Position (mm)",
                min_value=0.0,
                max_value=20.0,
                value=st.session_state.price_y_pos,
                step=0.5,
                key="widget_price_y_pos",
                on_change=lambda: self._save_tag_design_config('price_y_pos', st.session_state.widget_price_y_pos)
            )
            
            # Text Font Size - using unique widget key
            text_font_size = st.number_input(
                "Text Font Size",
                min_value=4,
                max_value=12,
                value=st.session_state.text_font_size,
                key="widget_text_font_size",
                on_change=lambda: self._save_tag_design_config('text_font_size', st.session_state.widget_text_font_size)
            )
                
        with col2:
            # Barcode Y Position - using unique widget key
            barcode_y_pos = st.number_input(
                "Barcode Y Position (mm)",
                min_value=0.0,
                max_value=20.0,
                value=st.session_state.barcode_y_pos,
                step=0.5,
                key="widget_barcode_y_pos",
                on_change=lambda: self._save_tag_design_config('barcode_y_pos', st.session_state.widget_barcode_y_pos)
            )
            
            # Barcode Height - using unique widget key
            barcode_height = st.number_input(
                "Barcode Height (mm)",
                min_value=0.0,
                max_value=12.0,
                value=st.session_state.barcode_height,
                step=0.5,
                key="widget_barcode_height",
                on_change=lambda: self._save_tag_design_config('barcode_height', st.session_state.widget_barcode_height)
            )
            
            # Print Borders - using unique widget key
            print_borders = st.checkbox(
                "Print Borders Around Labels",
                value=st.session_state.print_borders,
                key="widget_print_borders",
                on_change=lambda: self._save_tag_design_config('print_borders', st.session_state.widget_print_borders)
            )
    
    def _print_tags(self, record_ids):
        """Print price tags with robust error handling and progress tracking"""
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
        
        # Step 1: Assign barcodes
        status_text.text("Step 1/3: Assigning barcodes...")
        print(f"🔴 DEBUG: Calling assign_barcodes with record_ids: {record_ids}")
        barcode_mapping = self.price_tag_handler.assign_barcodes(record_ids)
        print(f"🔴 DEBUG: assign_barcodes returned: {barcode_mapping}")
        progress_bar.progress(33)
        
        if not barcode_mapping:
            st.session_state.print_status = "error"
            st.session_state.print_message = "❌ Failed to assign barcodes"
            st.session_state.print_success = False
            progress_bar.empty()
            status_text.empty()
            st.rerun()
            return
        
        # Step 2: Get record data using API
        status_text.text("Step 2/3: Loading record data...")
        all_records = self.db_manager.get_all_records()
        print(f"🔴 DEBUG: all_records: {all_records}")
        records_to_print = all_records[all_records['id'].isin(record_ids)]
        print(f"🔴 DEBUG: records_to_print: {records_to_print}")
        progress_bar.progress(66)
        
        # Step 3: Generate PDF with timeout protection
        status_text.text("Step 3/3: Generating PDF...")
        result_queue = queue.Queue()
        
        # Capture all layout parameters BEFORE creating the thread
        layout_params = {
            'price_font_size': st.session_state.price_font_size,
            'price_y_pos': st.session_state.price_y_pos,
            'text_font_size': st.session_state.text_font_size,
            'barcode_y_pos': st.session_state.barcode_y_pos,
            'barcode_height': st.session_state.barcode_height,
            'print_borders': st.session_state.print_borders
        }
        
        # Capture page layout parameters
        page_layout_params = {
            'label_width_mm': st.session_state.label_width_mm,
            'label_height_mm': st.session_state.label_height_mm,
            'left_margin_mm': st.session_state.left_margin_mm,
            'gutter_spacing_mm': st.session_state.gutter_spacing_mm,
            'top_margin_mm': st.session_state.top_margin_mm,
            'font_size': st.session_state.font_size
        }
        
        def generate_pdf_thread():
            try:
                print(f"🔴 DEBUG: generate_pdf called with {len(records_to_print)} records and barcode_mapping: {barcode_mapping}")
                pdf_path = self.price_tag_handler.generate_pdf(records_to_print, barcode_mapping, layout_params, page_layout_params)
                result_queue.put(('success', pdf_path))
            except Exception as e:
                print(f"🔴 DEBUG: PDF generation error: {str(e)}")
                result_queue.put(('error', str(e)))
        
        # Start PDF generation in thread
        pdf_thread = threading.Thread(target=generate_pdf_thread)
        pdf_thread.daemon = True
        pdf_thread.start()
        
        # Wait for PDF generation with timeout
        pdf_thread.join(timeout=20)
        
        progress_bar.progress(100)
        
        if pdf_thread.is_alive():
            st.session_state.print_status = "error"
            st.session_state.print_message = "❌ PDF generation timed out after 20 seconds"
            st.session_state.print_success = False
        else:
            try:
                result_type, result_data = result_queue.get_nowait()
                
                if result_type == 'success' and result_data and os.path.exists(result_data):
                    with open(result_data, "rb") as f:
                        st.session_state.pdf_data = f.read()
                    st.session_state.pdf_filename = f"price_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    
                    os.unlink(result_data)
                    
                    st.session_state.print_status = "completed"
                    st.session_state.print_message = f"✅ Successfully generated price tags for {len(record_ids)} records"
                    st.session_state.print_success = True
                else:
                    st.session_state.print_status = "error"
                    st.session_state.print_message = f"❌ PDF generation failed: {result_data}"
                    st.session_state.print_success = False
            except queue.Empty:
                st.session_state.print_status = "error"
                st.session_state.print_message = "❌ PDF generation failed - no result returned"
                st.session_state.print_success = False
        
        progress_bar.empty()
        status_text.empty()
        
        if hasattr(st.session_state, 'print_success') and st.session_state.print_success and 'pdf_data' in st.session_state:
            st.download_button(
                label="📄 Download Price Tags PDF",
                data=st.session_state.pdf_data,
                file_name=st.session_state.pdf_filename,
                mime="application/pdf",
                use_container_width=True,
                key=f"download_pdf_{datetime.now().strftime('%H%M%S')}"
            )
        
        if hasattr(st.session_state, 'print_success') and not st.session_state.print_success:
            st.rerun()