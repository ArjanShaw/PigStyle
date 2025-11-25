# inventory-manager/src/tabs/price_tag_tab.py

import streamlit as st
import pandas as pd
from datetime import datetime
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
        
        # Initialize session state
        self._initialize_session_state()
    
    def _get_config_path(self):
        """Get the unified configuration file path"""
        return Path(__file__).parent / "print_config.json"
    
    def _initialize_session_state(self):
        """Initialize session state with values from config file"""
        # Load saved layout configuration
        saved_config = self._load_layout_config()
        
        # Initialize ONLY layout configuration parameters from the config file
        layout_config_keys = [
            'price_font_size', 'price_y_pos', 'text_font_size', 'artist_y_pos', 'file_y_pos',
            'date_font_size', 'date_y_pos', 'barcode_y_pos', 'barcode_height', 'label_width_mm',
            'label_height_mm', 'left_margin_mm', 'gutter_spacing_mm', 'top_margin_mm', 'rows',
            'columns', 'print_borders'
        ]
        
        for key in layout_config_keys:
            if key not in st.session_state:
                if key not in saved_config:
                    raise Exception(f"Missing required configuration key: {key}")
                st.session_state[key] = saved_config[key]
        
        # UI state parameters will be created on-demand when users interact with the UI
        # No need to pre-initialize print_first_x, select_all, etc.
    
    def _load_layout_config(self):
        """Load layout configuration from file"""
        config_file = self._get_config_path()
        
        if not config_file.exists():
            raise Exception(f"Configuration file not found: {config_file}")
        
        try:
            with open(config_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    raise Exception("Configuration file is empty")
                saved_config = json.loads(content)
            return saved_config
        except (json.JSONDecodeError, Exception) as e:
            raise Exception(f"Error loading layout config: {e}")
    
    def _save_layout_config(self, config):
        """Save layout configuration to file"""
        try:
            config_file = self._get_config_path()
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            raise Exception(f"Error saving layout config: {e}")
    
    def _save_current_layout_config(self):
        """Save current layout configuration to file"""
        current_config = {
            # Label Layout Configuration
            'price_font_size': st.session_state.price_font_size,
            'price_y_pos': st.session_state.price_y_pos,
            'text_font_size': st.session_state.text_font_size,
            'artist_y_pos': st.session_state.artist_y_pos,
            'file_y_pos': st.session_state.file_y_pos,
            'date_font_size': st.session_state.date_font_size,
            'date_y_pos': st.session_state.date_y_pos,
            'barcode_y_pos': st.session_state.barcode_y_pos,
            'barcode_height': st.session_state.barcode_height,
            # Page Layout Configuration
            'label_width_mm': st.session_state.label_width_mm,
            'label_height_mm': st.session_state.label_height_mm,
            'left_margin_mm': st.session_state.left_margin_mm,
            'gutter_spacing_mm': st.session_state.gutter_spacing_mm,
            'top_margin_mm': st.session_state.top_margin_mm,
            'rows': st.session_state.rows,
            'columns': st.session_state.columns,
            # Border Configuration
            'print_borders': st.session_state.print_borders
        }
        self._save_layout_config(current_config)
    
    def render(self):
        st.header("🏷️ Print Price Tags")
        
        # Show status message - check if it exists first
        if hasattr(st.session_state, 'print_status') and st.session_state.print_status:
            if hasattr(st.session_state, 'print_success') and st.session_state.print_success:
                st.success(st.session_state.print_message)
            else:
                st.error(st.session_state.print_message)
        
        # Check dependencies
        try:
            import barcode
            import reportlab
            st.success("✅ Printing dependencies available")
        except ImportError as e:
            st.error(f"❌ Missing: {e}")
            st.info("Install: pip install python-barcode reportlab")
            return
        
        # Configuration Sections
        with st.expander("📐 Label Layout Configuration", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.number_input("Price Font Size", min_value=6, max_value=20, value=st.session_state.price_font_size, key="price_font_size")
                st.number_input("Price Y Position (mm)", min_value=0.0, max_value=20.0, value=st.session_state.price_y_pos, step=0.5, key="price_y_pos")
                st.number_input("Text Font Size", min_value=4, max_value=12, value=st.session_state.text_font_size, key="text_font_size")
                
            with col2:
                st.number_input("Artist Title Y Position (mm)", min_value=0.0, max_value=20.0, value=st.session_state.artist_y_pos, step=0.5, key="artist_y_pos")
                st.number_input("File Location Y Position (mm)", min_value=0.0, max_value=20.0, value=st.session_state.file_y_pos, step=0.5, key="file_y_pos")
                st.number_input("Date Font Size", min_value=4, max_value=12, value=st.session_state.date_font_size, key="date_font_size")
                
            with col3:
                st.number_input("Date Y Position (mm)", min_value=0.0, max_value=20.0, value=st.session_state.date_y_pos, step=0.5, key="date_y_pos")
                st.number_input("Barcode Y Position (mm)", min_value=0.0, max_value=20.0, value=st.session_state.barcode_y_pos, step=0.5, key="barcode_y_pos")
                st.number_input("Barcode Height (mm)", min_value=0.0, max_value=12.0, value=st.session_state.barcode_height, step=0.5, key="barcode_height")
            
            # Border Configuration
            st.checkbox("Print Borders Around Labels", value=st.session_state.print_borders, key="print_borders")
        
        with st.expander("📄 Page Layout Configuration", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.number_input("Label Width (mm)", min_value=10.0, max_value=100.0, value=st.session_state.label_width_mm, step=0.1, key="label_width_mm")
                st.number_input("Label Height (mm)", min_value=10.0, max_value=100.0, value=st.session_state.label_height_mm, step=0.1, key="label_height_mm")
                st.number_input("Left Margin (mm)", min_value=0.0, max_value=50.0, value=st.session_state.left_margin_mm, step=0.1, key="left_margin_mm")
                
            with col2:
                st.number_input("Gutter Spacing (mm)", min_value=0.0, max_value=50.0, value=st.session_state.gutter_spacing_mm, step=0.1, key="gutter_spacing_mm")
                st.number_input("Top Margin (mm)", min_value=0.0, max_value=50.0, value=st.session_state.top_margin_mm, step=0.1, key="top_margin_mm")
                st.number_input("Rows per Page", min_value=1, max_value=50, value=st.session_state.rows, key="rows")
                st.number_input("Columns per Page", min_value=1, max_value=10, value=st.session_state.columns, key="columns")
        
        # Save configuration button
        if st.button("💾 Save Layout Configuration", use_container_width=True):
            self._save_current_layout_config()
            st.success("✅ Layout configuration saved!")
        
        # Get records without barcodes
        records = self.price_tag_handler.get_records_without_barcodes()
        
        # MANAGEMENT SECTION
        st.subheader("Manage Printed Tags")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ CLEAR ALL BARCODES", type="secondary", use_container_width=True):
                self._clear_barcodes()
        
        with col2:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM records WHERE barcode IS NOT NULL AND barcode != ""')
            printed_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM records')
            total_count = cursor.fetchone()[0]
            conn.close()
            st.metric("Printed", f"{printed_count}/{total_count}")
        
        if not records:
            st.info("All records have price tags printed. Use the 'Clear All Barcodes' button above to reset them.")
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
        
        # Display records table
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
                'Price': f"${record.get('store_price', 0):.2f}" if record.get('store_price') else 'N/A',
                'File Location': record.get('file_at', ''),
            })
        
        df = pd.DataFrame(display_data)
        edited_df = st.data_editor(
            df,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", default=False),
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "Artist": st.column_config.TextColumn("Artist", disabled=True),
                "Title": st.column_config.TextColumn("Title", disabled=True),
                "Price": st.column_config.TextColumn("Price", disabled=True),
                "File Location": st.column_config.TextColumn("File Location", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="price_tag_editor"
        )
        
        selected_records = edited_df[edited_df['Select'] == True]
        
        if len(selected_records) > 0:
            st.subheader(f"Selected for Printing ({len(selected_records)} records)")
            st.dataframe(selected_records[['ID', 'Artist', 'Title', 'Price']], hide_index=True)
            
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("🖨️ Print Price Tags", type="primary", use_container_width=True):
                    self._print_tags(selected_records['ID'].tolist())
            with col2:
                if st.button("⚡ Quick Assign Barcodes Only", use_container_width=True):
                    self._quick_assign_barcodes(selected_records['ID'].tolist())
    
    def _print_tags(self, record_ids):
        """Print price tags with robust error handling and progress tracking"""
        if not record_ids:
            st.session_state.print_status = "error"
            st.session_state.print_message = "❌ No records selected"
            st.session_state.print_success = False
            st.rerun()
            return
        
        try:
            st.session_state.print_status = "processing"
            st.session_state.print_message = f"🔄 Starting price tag generation for {len(record_ids)} records..."
            st.session_state.print_success = False

            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 1: Assign barcodes
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
            
            # Step 2: Get record data
            status_text.text("Step 2/3: Loading record data...")
            conn = self.db_manager._get_connection()
            placeholders = ','.join(['?'] * len(record_ids))
            query = f'''
                SELECT r.*, g.genre_name as genre, c.name as consignor_name
                FROM records r
                LEFT JOIN genres g ON r.genre_id = g.id
                LEFT JOIN consignment_sessions cs ON r.consignment_session_id = cs.id
                LEFT JOIN consignors c ON cs.consignor_id = c.id
                WHERE r.id IN ({placeholders})
            '''
            df = pd.read_sql(query, conn, params=record_ids)
            conn.close()
            progress_bar.progress(66)
            
            # Step 3: Generate PDF with timeout protection
            status_text.text("Step 3/3: Generating PDF...")
            result_queue = queue.Queue()
            
            # Capture all layout parameters BEFORE creating the thread
            layout_params = {
                # Label Layout Configuration
                'price_font_size': st.session_state.price_font_size,
                'price_y_pos': st.session_state.price_y_pos,
                'text_font_size': st.session_state.text_font_size,
                'artist_y_pos': st.session_state.artist_y_pos,
                'file_y_pos': st.session_state.file_y_pos,
                'date_font_size': st.session_state.date_font_size,
                'date_y_pos': st.session_state.date_y_pos,
                'barcode_y_pos': st.session_state.barcode_y_pos,
                'barcode_height': st.session_state.barcode_height,
                # Page Layout Configuration
                'label_width_mm': st.session_state.label_width_mm,
                'label_height_mm': st.session_state.label_height_mm,
                'left_margin_mm': st.session_state.left_margin_mm,
                'gutter_spacing_mm': st.session_state.gutter_spacing_mm,
                'top_margin_mm': st.session_state.top_margin_mm,
                'rows': st.session_state.rows,
                'columns': st.session_state.columns,
                # Border Configuration
                'print_borders': st.session_state.print_borders
            }
            
            def generate_pdf_thread():
                try:
                    # Use the captured layout_params instead of st.session_state
                    pdf_path = self.price_tag_handler.generate_pdf(df, barcode_mapping, layout_params)
                    result_queue.put(('success', pdf_path))
                except Exception as e:
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
                        
                        try:
                            os.unlink(result_data)
                        except:
                            pass
                        
                        st.session_state.print_status = "completed"
                        st.session_state.print_message = f"✅ Successfully generated price tags for {len(record_ids)} records"
                        st.session_state.print_success = True
                    else:
                        st.session_state.print_status = "error"
                        st.session_state.print_message = f"❌ PDF generation failed: {result_data}"
                        st.session_state.print_success = False
                        
                except queue.Empty:
                    st.session_state.print_status = "error"
                    st.session_state.print_message = "❌ PDF generation failed - no result received"
                    st.session_state.print_success = False
            
            progress_bar.empty()
            status_text.empty()
            
        except Exception as e:
            st.session_state.print_status = "error"
            st.session_state.print_message = f"❌ Unexpected error: {str(e)}"
            st.session_state.print_success = False
        
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
     
    def _quick_assign_barcodes(self, record_ids):
        """Quickly assign barcodes without PDF generation"""
        if not record_ids:
            st.session_state.print_status = "error"
            st.session_state.print_message = "❌ No records selected"
            st.session_state.print_success = False
            st.rerun()
            return
        
        try:
            st.session_state.print_status = "processing"
            st.session_state.print_message = f"🔄 Assigning barcodes to {len(record_ids)} records..."
            st.session_state.print_success = False
            st.rerun()
            
            barcode_mapping = self.price_tag_handler.assign_barcodes(record_ids)
            
            if barcode_mapping:
                st.session_state.print_status = "completed"
                st.session_state.print_message = f"✅ Successfully assigned barcodes to {len(record_ids)} records. You can print labels later."
                st.session_state.print_success = True
            else:
                st.session_state.print_status = "error"
                st.session_state.print_message = "❌ Failed to assign barcodes"
                st.session_state.print_success = False
                
        except Exception as e:
            st.session_state.print_status = "error"
            st.session_state.print_message = f"❌ Error assigning barcodes: {str(e)}"
            st.session_state.print_success = False
        
        st.rerun()
    
    def _clear_barcodes(self):
        """Clear all barcodes"""
        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE records SET barcode = NULL')
            conn.commit()
            conn.close()
            
            st.session_state.print_status = "completed"
            st.session_state.print_message = "✅ All barcodes cleared successfully!"
            st.session_state.print_success = True
        except Exception as e:
            st.session_state.print_status = "error"
            st.session_state.print_message = f"❌ Error clearing barcodes: {e}"
            st.session_state.print_success = False
        
        st.rerun()