import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sqlite3
from typing import Dict, List, Optional, Tuple
from handlers.draft_csv_handler import DraftCSVHandler
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128
import io
import json
import re
import time
from handlers.barcode_generator import BarcodeGenerator
from handlers.ebay_handler import EbayHandler
from handlers.price_handler import PriceHandler
from handlers.genre_handler import GenreHandler
from config import PrintConfig

class InventoryTab:
    def __init__(self, discogs_handler, debug_tab, ebay_handler=None):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
        self.barcode_generator = BarcodeGenerator()
        self.debug_tab = debug_tab
        self.config = PrintConfig()
        self.price_handler = PriceHandler()
        self.genre_handler = GenreHandler()
        self._update_dimensions_from_config()
        
        # Initialize session state for eBay cutoff price
        if 'ebay_cutoff_price' not in st.session_state:
            st.session_state.ebay_cutoff_price = 3.99
        
        # Initialize column visibility states
        if 'show_ebay_columns' not in st.session_state:
            st.session_state.show_ebay_columns = True
        if 'show_discogs_columns' not in st.session_state:
            st.session_state.show_discogs_columns = True
        if 'show_filing_columns' not in st.session_state:
            st.session_state.show_filing_columns = True
            
        self.price_handler.set_ebay_cutoff_price(st.session_state.ebay_cutoff_price)
        
    def _update_dimensions_from_config(self):
        """Update dimensions from configuration"""
        config = self.config.get_all()
        self.label_width = config["label_width_mm"] * mm
        self.label_height = config["label_height_mm"] * mm
        self.left_margin = config["left_margin_mm"] * mm
        self.gutter_spacing = config["gutter_spacing_mm"] * mm
        self.top_margin = config["top_margin_mm"] * mm
        self.font_size = config["font_size"]
        self.page_width, self.page_height = letter

    def render_inventory_tab(self):
        """Render the inventory table functionality"""
        
        # Database statistics - direct count from inventory records
        stats = self._get_database_stats_direct('inventory')
            
        # Top row: Stats and action buttons - left aligned
        col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1, 1, 1, 1, 1])
        with col1:
            st.metric("Inventory Records", stats['records_count'])
        with col2:
            if st.button("📦 Ebay List", use_container_width=True, help="Export selected records for eBay"):
                self._export_ebay_list()
        with col3:
            if st.button("🔢 Gen Barcodes", use_container_width=True, help="Generate missing barcodes"):
                self._generate_barcodes_for_existing_records()
        with col4:
            if st.button("📁 Gen File At", use_container_width=True, help="Regenerate file_at for selected records"):
                self._generate_file_at_for_selected_records()
        with col5:
            if st.button("🖨️ Print Selected", use_container_width=True, help="Print selected records"):
                self._generate_price_tags_pdf()
        with col6:
            if st.button("🗑️ Delete Selected", use_container_width=True, help="Delete selected records"):
                self._delete_selected_records()
        with col7:
            if st.button("🔄 Update eBay Prices", use_container_width=True, help="Update eBay prices for selected records"):
                self._update_ebay_prices_for_selected()
        
        # Price Settings and Genre Management in expandable sections
        with st.expander("💰 Price Settings", expanded=False):
            st.subheader("eBay Pricing Strategy")
            st.write("Dynamic calculation from eBay lowest price with cutoff and .49/.99 rounding")
            
            new_cutoff = st.number_input(
                "eBay Cutoff Price",
                min_value=0.0,
                max_value=100.0,
                value=st.session_state.ebay_cutoff_price,
                step=0.5,
                help="Minimum price for eBay listings"
            )
            if new_cutoff != st.session_state.ebay_cutoff_price:
                st.session_state.ebay_cutoff_price = new_cutoff
                self.price_handler.set_ebay_cutoff_price(new_cutoff)
                st.success(f"eBay cutoff price updated to ${new_cutoff:.2f}")
            
        with st.expander("🎵 Genre Management & Import/Export", expanded=False):
            genre_col1, genre_col2 = st.columns(2)
                
            with genre_col1:
                if st.button("📤 Export Genre CSV", use_container_width=True, help="Export ID, Artist, Title, and Genre for all inventory records"):
                    self._export_genre_csv()
                
            with genre_col2:
                uploaded_file = st.file_uploader(
                    "Upload genre CSV to update genres",
                    type=['csv'],
                    help="Upload CSV with id and genre columns to update genres",
                    key="genre_import_uploader"
                )
                    
                if uploaded_file is not None:
                    import_df = pd.read_csv(uploaded_file)
                            
                    if 'id' not in import_df.columns or 'genre' not in import_df.columns:
                        st.error("CSV must contain 'id' and 'genre' columns")
                    else:
                        if st.button("🔄 Update Genres", use_container_width=True):
                            updated_count = self._update_genres_from_csv(import_df)
                            if updated_count > 0:
                                st.success(f"✅ Updated genres for {updated_count} records!")
                                st.session_state.records_updated += 1
                                st.rerun()
                            else:
                                st.warning("No genres were updated.")
            
        with st.expander("🖨️ Genre Signs Printing", expanded=False):
            print_option = st.radio(
                "Print option:",
                ["Single Genre", "All Genres"],
                key="print_option"
            )
            
            if print_option == "Single Genre":
                genre_options = self.genre_handler.get_unique_genres()
                genre_text = st.selectbox("Select genre:", options=genre_options, key="genre_select")
            else:
                genre_text = "ALL_GENRES"
            
            font_size = st.slider("Font Size", min_value=24, max_value=96, value=48, key="genre_font_size")
            
            if st.button("🖨️ Generate Genre Sign PDF", use_container_width=True):
                if print_option == "All Genres":
                    genre_options = self.genre_handler.get_unique_genres()
                    pdf_buffer = self.genre_handler.generate_all_genre_signs_pdf(genre_options, font_size)
                    filename = f"all_genre_signs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                else:
                    pdf_buffer = self.genre_handler.generate_genre_sign_pdf(genre_text, font_size)
                    filename = f"genre_sign_{genre_text.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                
                st.download_button(
                    label="⬇️ Download Genre Sign PDF",
                    data=pdf_buffer.getvalue(),
                    file_name=filename,
                    mime="application/pdf"
                )
        
        # Column visibility controls in expandable section - MOVED BELOW GENRE PRINTING
        with st.expander("📊 Column Visibility Controls", expanded=False):
            # Changed from row to array layout
            st.session_state.show_ebay_columns = st.checkbox(
                "Show eBay Columns", 
                value=st.session_state.show_ebay_columns,
                help="Show/hide eBay pricing columns"
            )
            st.session_state.show_discogs_columns = st.checkbox(
                "Show Discogs Columns", 
                value=st.session_state.show_discogs_columns,
                help="Show/hide Discogs pricing columns"
            )
            st.session_state.show_filing_columns = st.checkbox(
                "Show Filing Columns", 
                value=st.session_state.show_filing_columns,
                help="Show/hide filing columns (Genre, File At, Barcode)"
            )
            
        # Second row: Search and filters
        col1, col2 = st.columns([2, 1])
        
        with col1:
            search_term = st.text_input(
                "Search by artist, title, or barcode:",
                key="search_inventory",
                placeholder="Enter search term..."
            )
        
        with col2:
            # Quick filters
            filter_option = st.selectbox(
                "Filter by",
                options=["All Records", "No Barcode", "No Price Data", "No Genre", "No File At", "No eBay Price", "Price Tags Not Printed"],
                key="quick_filter_inventory"
            )

        if stats['records_count'] > 0:
            self._render_records_table('inventory', search_term, filter_option)
        else:
            st.info("No records in inventory. Start by searching and adding records above!")
                
         

    def render_sold_tab(self):
        """Render the sold records table functionality - renamed to Income"""
        # Database statistics - direct count from sold records
        stats = self._get_database_stats_direct('sold')
        
        # Top row: Stats and action buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            st.metric("Sold Records", stats['records_count'])
        with col2:
            if st.button("🔄 Return to Inventory", use_container_width=True, help="Return selected sold records to inventory"):
                self._return_to_inventory()
        
        # Second row: Search and filters
        col1, col2 = st.columns([2, 1])
        
        with col1:
            search_term = st.text_input(
                "Search by artist, title, or barcode:",
                key="search_sold",
                placeholder="Enter search term..."
            )
        
        with col2:
            # Quick filters
            filter_option = st.selectbox(
                "Filter by",
                options=["All Records", "No Barcode", "No Price Data", "No Genre", "No File At", "No eBay Price"],
                key="quick_filter_sold"
            )

        if stats['records_count'] > 0:
            self._render_records_table('sold', search_term, filter_option)
        else:
            st.info("No sold records yet.")

    def _export_genre_csv(self):
        """Export ID, Artist, Title, and Genre for all inventory records"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql(
            "SELECT id, artist, title, genre FROM records WHERE status = 'inventory' ORDER BY artist, title",
            conn
        )
        conn.close()
        
        if len(df) > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"genre_export_{timestamp}.csv"
            
            csv_data = df.to_csv(index=False)
            
            st.download_button(
                label="⬇️ Download Genre CSV",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                key=f"download_genre_{timestamp}"
            )
            
            st.success(f"✅ Export ready! {len(df)} inventory records.")
        else:
            st.warning("No inventory records to export.")

    def _update_genres_from_csv(self, import_df):
        """Update genres from CSV data (only id and genre columns are used)"""
        updated_count = 0
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        
        for _, row in import_df.iterrows():
            record_id = row.get('id')
            new_genre = row.get('genre')
            
            if record_id and pd.notna(new_genre):
                # Use update_record to track changes properly
                success = st.session_state.db_manager.update_record(record_id, {'genre': new_genre})
                if success:
                    updated_count += 1
        
        conn.close()
        return updated_count

    def _return_to_inventory(self):
        """Return selected sold records back to inventory"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
            
        selected_ids = st.session_state.selected_records
        if self._update_record_status(selected_ids, 'inventory'):
            st.success(f"✅ Returned {len(selected_ids)} records to inventory!")
            # Clear selection after operation
            st.session_state.selected_records = []
            st.session_state.records_updated += 1
            st.rerun()

    def _update_record_status(self, record_ids, new_status):
        """Update status of records"""
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        cursor.executemany('UPDATE records SET status = ? WHERE id = ?', [(new_status, id) for id in record_ids])
        conn.commit()
        conn.close()
        return True

    def _update_ebay_prices_for_selected(self):
        """Update eBay prices for selected records - NOW STORES IN ebay_sell_at"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
        
        if not self.ebay_handler:
            st.error("eBay handler not available. Check your eBay API credentials.")
            return
        
        selected_ids = st.session_state.selected_records
        placeholders = ','.join(['?'] * len(selected_ids))
        
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql(f'SELECT * FROM records WHERE id IN ({placeholders})', conn, params=selected_ids)
        conn.close()
        
        updated_count = 0
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (_, record) in enumerate(df.iterrows()):
            artist = record.get('artist', '')
            title = record.get('title', '')
            
            status_text.text(f"Updating {i+1}/{len(df)}: {artist} - {title}")
            
            ebay_pricing = self.ebay_handler.get_ebay_pricing(artist, title)
            if ebay_pricing:
                # Calculate final eBay selling price
                ebay_sell_price = self.price_handler.calculate_ebay_price(ebay_pricing.get('ebay_lowest_price'))
                
                # Set to NULL if below cutoff - FIXED LOGIC
                if ebay_sell_price and ebay_sell_price < self.price_handler.ebay_cutoff_price:
                    ebay_sell_price = None
                
                # Use update_record to track changes properly
                updates = {
                    'ebay_median_price': ebay_pricing.get('ebay_median_price'),
                    'ebay_lowest_price': ebay_pricing.get('ebay_lowest_price'),
                    'ebay_highest_price': ebay_pricing.get('ebay_highest_price'),
                    'ebay_count': ebay_pricing.get('ebay_listings_count', 0),
                    'ebay_sell_at': ebay_sell_price
                }
                success = st.session_state.db_manager.update_record(record['id'], updates)
                if success:
                    updated_count += 1
            
            progress_bar.progress((i + 1) / len(df))
        
        status_text.empty()
        progress_bar.empty()
        
        if updated_count > 0:
            st.success(f"✅ Updated eBay prices for {updated_count} records! Stored in ebay_sell_at.")
            st.session_state.records_updated += 1
            st.rerun()
        else:
            st.warning("No eBay prices were updated. Check debug tab for details.")

    def _export_ebay_list(self):
        """Export selected records as eBay draft listings - NOW USES ebay_sell_at"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
        
        # Get selected records data
        selected_ids = st.session_state.selected_records
        placeholders = ','.join(['?'] * len(selected_ids))
        
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql(f'SELECT * FROM records WHERE id IN ({placeholders}) AND status = "inventory"', conn, params=selected_ids)
        conn.close()
        
        records_list = df.to_dict('records')
        
        # Generate eBay formatted TXT
        draft_handler = DraftCSVHandler()
        ebay_content = draft_handler.generate_ebay_txt_from_records(records_list, self.price_handler)
        
        # Create download button
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ebay_drafts_{timestamp}.txt"
        
        st.download_button(
            label="⬇️ Download eBay Drafts",
            data=ebay_content,
            file_name=filename,
            mime="text/plain",
            key=f"download_ebay_{timestamp}"
        )
        
        st.success(f"✅ eBay draft file ready! {len(records_list)} records formatted for eBay import.")

    def _get_database_stats_direct(self, status='inventory') -> Dict:
        """Get database statistics directly from records table"""
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM records WHERE status = ?', (status,))
        records_count_result = cursor.fetchone()
        records_count = records_count_result[0] if records_count_result else 0
        
        cursor.execute('SELECT COUNT(*) FROM records WHERE status = ? AND (barcode IS NULL OR barcode = "")', (status,))
        no_barcode_result = cursor.fetchone()
        no_barcode_count = no_barcode_result[0] if no_barcode_result else 0
        
        cursor.execute('SELECT COUNT(*) FROM records WHERE status = ? AND (file_at IS NULL OR file_at = "")', (status,))
        no_file_at_result = cursor.fetchone()
        no_file_at_count = no_file_at_result[0] if no_file_at_result else 0
        
        cursor.execute('SELECT COUNT(*) FROM records WHERE status = ? AND (ebay_sell_at IS NULL OR ebay_sell_at = 0)', (status,))
        no_ebay_price_result = cursor.fetchone()
        no_ebay_price_count = no_ebay_price_result[0] if no_ebay_price_result else 0
        
        cursor.execute('SELECT COUNT(*) FROM records WHERE status = ? AND price_tag_printed = 0', (status,))
        price_tags_not_printed_result = cursor.fetchone()
        price_tags_not_printed_count = price_tags_not_printed_result[0] if price_tags_not_printed_result else 0
        
        conn.close()
        
        return {
            'records_count': int(records_count) if records_count is not None else 0,
            'no_barcode_count': int(no_barcode_count) if no_barcode_count is not None else 0,
            'no_file_at_count': int(no_file_at_count) if no_file_at_count is not None else 0,
            'no_ebay_price_count': int(no_ebay_price_count) if no_ebay_price_count is not None else 0,
            'price_tags_not_printed_count': int(price_tags_not_printed_count) if price_tags_not_printed_count is not None else 0
        }

    def _get_all_records_direct(self, status: str, search_term: str = None, filter_option: str = None) -> pd.DataFrame:
        """Get all records directly from records table with optional filtering"""
        conn = st.session_state.db_manager._get_connection()
        
        # Simple query - only from records table with correct column names
        base_query = """
        SELECT 
            id, artist, title, 
            discogs_median_price, discogs_lowest_price, discogs_highest_price,
            ebay_median_price, ebay_lowest_price, ebay_highest_price, ebay_count, ebay_sell_at,
            image_url, barcode, format, condition, created_at, genre, file_at, price_tag_printed, price
        FROM records 
        WHERE status = ?
        """
        
        params = [status]
        
        # Apply search filter
        if search_term:
            base_query += """
            AND (artist LIKE ? 
                OR title LIKE ? 
                OR barcode LIKE ?)
            """
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern])
        
        # Apply quick filters
        if filter_option == "No Barcode":
            base_query += " AND (barcode IS NULL OR barcode = '')"
        elif filter_option == "No Price Data":
            base_query += " AND (discogs_median_price IS NULL OR discogs_median_price = 0)"
        elif filter_option == "No Genre":
            base_query += " AND (genre IS NULL OR genre = '')"
        elif filter_option == "No File At":
            base_query += " AND (file_at IS NULL OR file_at = '')"
        elif filter_option == "No eBay Price":
            base_query += " AND (ebay_sell_at IS NULL OR ebay_sell_at = 0)"
        elif filter_option == "Price Tags Not Printed":
            base_query += " AND price_tag_printed = 0"
        
        # FIXED: Proper numerical sorting for ALL price columns with NULLs at bottom
        base_query += """ 
        ORDER BY 
            CASE 
                WHEN ebay_median_price IS NULL OR ebay_median_price = '' OR ebay_median_price = 0 THEN 999999
                ELSE CAST(ebay_median_price AS REAL)
            END ASC,
            CASE 
                WHEN discogs_median_price IS NULL OR discogs_median_price = '' OR discogs_median_price = 0 THEN 999999
                ELSE CAST(discogs_median_price AS REAL)
            END ASC,
            CASE 
                WHEN ebay_lowest_price IS NULL OR ebay_lowest_price = '' OR ebay_lowest_price = 0 THEN 999999
                ELSE CAST(ebay_lowest_price AS REAL)
            END ASC,
            CASE 
                WHEN ebay_highest_price IS NULL OR ebay_highest_price = '' OR ebay_highest_price = 0 THEN 999999
                ELSE CAST(ebay_highest_price AS REAL)
            END ASC,
            CASE 
                WHEN discogs_lowest_price IS NULL OR discogs_lowest_price = '' OR discogs_lowest_price = 0 THEN 999999
                ELSE CAST(discogs_lowest_price AS REAL)
            END ASC,
            CASE 
                WHEN discogs_highest_price IS NULL OR discogs_highest_price = '' OR discogs_highest_price = 0 THEN 999999
                ELSE CAST(discogs_highest_price AS REAL)
            END ASC
        """
        
        df = pd.read_sql_query(base_query, conn, params=params)
        conn.close()
        return df

    def _get_total_filtered_count(self, status: str, search_term: str = None, filter_option: str = None) -> int:
        """Get total count of records after applying filters"""
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        
        base_query = "SELECT COUNT(*) FROM records WHERE status = ?"
        params = [status]
        
        if search_term:
            base_query += """
            AND (artist LIKE ? 
                OR title LIKE ? 
                OR barcode LIKE ?)
            """
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern])
        
        if filter_option == "No Barcode":
            base_query += " AND (barcode IS NULL OR barcode = '')"
        elif filter_option == "No Price Data":
            base_query += " AND (discogs_median_price IS NULL OR discogs_median_price = 0)"
        elif filter_option == "No Genre":
            base_query += " AND (genre IS NULL OR genre = '')"
        elif filter_option == "No File At":
            base_query += " AND (file_at IS NULL OR file_at = '')"
        elif filter_option == "No eBay Price":
            base_query += " AND (ebay_sell_at IS NULL OR ebay_sell_at = 0)"
        elif filter_option == "Price Tags Not Printed":
            base_query += " AND price_tag_printed = 0"
        
        cursor.execute(base_query, params)
        count_result = cursor.fetchone()
        count = count_result[0] if count_result else 0
        conn.close()
        return int(count) if count is not None else 0

    def _render_records_table(self, status, search_term, filter_option):
        """Render records with pagination"""
        
        # Get current filter state
        search_term = st.session_state.get(f'search_{status}', '')
        filter_option = st.session_state.get(f'quick_filter_{status}', 'All Records')
        
        # Get total count for pagination
        total_records = self._get_total_filtered_count(status, search_term, filter_option)
        
        if total_records == 0:
            st.info("No records found matching your criteria.")
            return
        
        # Load all records (no pagination)
        records = self._get_all_records_direct(status, search_term, filter_option)
        
        # Display record count
        if search_term:
            st.write(f"**Showing {len(records)} of {total_records} {status} records matching '{search_term}'**")
        elif filter_option != "All Records":
            st.write(f"**Showing {len(records)} of {total_records} {status} {filter_option.lower()}**")
        else:
            st.write(f"**Showing {len(records)} {status} records**")
        
        # Render the records table with selection
        self._render_records_dataframe(records, status)

    def _render_records_dataframe(self, records: pd.DataFrame, status: str):
        """Render records in an optimized dataframe with selection"""
        if len(records) == 0:
            return
        
        # Initialize selection state
        if 'selected_records' not in st.session_state:
            st.session_state.selected_records = []
        
        # Prepare display data with selection
        display_data = []
        for _, record in records.iterrows():
            is_selected = record['id'] in st.session_state.selected_records
            price_tag_status = "✅" if record.get('price_tag_printed') else "❌"
            
            display_record = {
                'Select': is_selected,
                'Price Tag': price_tag_status,
                'Cover': record.get('image_url', ''),
                'Artist': record.get('artist', ''),
                'Title': record.get('title', ''),
                'Store Price': self._format_currency(record.get('price')),  # Store price from database
                'eBay Price': self._format_currency(record.get('ebay_sell_at')),  # NOW FROM ebay_sell_at
            }
            
            # Add eBay columns if enabled
            if st.session_state.show_ebay_columns:
                display_record.update({
                    'eBay Count': record.get('ebay_count', 0) or 0,
                    'eBay Median': self._format_currency(record.get('ebay_median_price')),
                    'eBay Lowest': self._format_currency(record.get('ebay_lowest_price')),
                    'eBay Highest': self._format_currency(record.get('ebay_highest_price'))
                })
            
            # Add Discogs columns if enabled
            if st.session_state.show_discogs_columns:
                display_record.update({
                    'Discogs Median': self._format_currency(record.get('discogs_median_price')),
                    'Discogs Lowest': self._format_currency(record.get('discogs_lowest_price')),
                    'Discogs Highest': self._format_currency(record.get('discogs_highest_price'))
                })
            
            # Add filing columns if enabled
            if st.session_state.show_filing_columns:
                display_record.update({
                    'Genre': record.get('genre', ''),
                    'File At': record.get('file_at', ''),
                    'Barcode': record.get('barcode', ''),
                    'Condition': record.get('condition', ''),
                    'Format': record.get('format', '')
                })
            
            # Add "Added" column at the end
            display_record['Added'] = record.get('created_at', '')[:16] if record.get('created_at') else ''
            
            display_data.append(display_record)
        
        display_df = pd.DataFrame(display_data)
        
        # Configure columns for better display
        column_config = {
            'Select': st.column_config.CheckboxColumn('Select', width='small'),
            'Price Tag': st.column_config.TextColumn('Price Tag', width='small'),
            'Cover': st.column_config.ImageColumn('Cover', width='small'),
            'Artist': st.column_config.TextColumn('Artist', width='medium'),
            'Title': st.column_config.TextColumn('Title', width='large'),
            'Store Price': st.column_config.TextColumn('Store Price', width='small'),
            'eBay Price': st.column_config.TextColumn('eBay Price', width='small'),
        }
        
        # Add eBay columns to config if enabled
        if st.session_state.show_ebay_columns:
            column_config.update({
                'eBay Count': st.column_config.NumberColumn('eBay Count', width='small'),
                'eBay Median': st.column_config.TextColumn('eBay Median', width='small'),
                'eBay Lowest': st.column_config.TextColumn('eBay Lowest', width='small'),
                'eBay Highest': st.column_config.TextColumn('eBay Highest', width='small')
            })
        
        # Add Discogs columns to config if enabled
        if st.session_state.show_discogs_columns:
            column_config.update({
                'Discogs Median': st.column_config.TextColumn('Discogs Median', width='small'),
                'Discogs Lowest': st.column_config.TextColumn('Discogs Lowest', width='small'),
                'Discogs Highest': st.column_config.TextColumn('Discogs Highest', width='small')
            })
        
        # Add filing columns to config if enabled
        if st.session_state.show_filing_columns:
            column_config.update({
                'Genre': st.column_config.TextColumn('Genre', width='medium'),
                'File At': st.column_config.TextColumn('File At', width='small'),
                'Barcode': st.column_config.TextColumn('Barcode', width='small'),
                'Condition': st.column_config.TextColumn('Condition', width='small'),
                'Format': st.column_config.TextColumn('Format', width='small')
            })
        
        # Add "Added" column at the end
        column_config['Added'] = st.column_config.TextColumn('Added', width='small')
        
        # Add select all checkbox with toggle functionality
        col1, col2 = st.columns([1, 5])
        with col1:
            all_currently_selected = st.checkbox("Select All", key=f"select_all_{status}")
        
        # Display editable dataframe with selection - FIXED: use full width
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            use_container_width=True,  # This ensures full width
            height=min(600, 35 * len(display_df) + 40),
            hide_index=True,
            key=f"records_editor_{status}"
        )
        
        # Handle select all functionality - FIXED TOGGLE BEHAVIOR
        if all_currently_selected:
            selected_ids = records['id'].tolist()
        else:
            selected_ids = []
        
        # Update selection state based on editor changes
        if set(selected_ids) != set(st.session_state.selected_records):
            st.session_state.selected_records = selected_ids
            st.rerun()

    def _delete_selected_records(self):
        """Delete selected records"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
            
        selected_ids = st.session_state.selected_records
        if self._delete_records(selected_ids):
            st.success(f"Deleted {len(selected_ids)} records!")
            # Clear selection after deletion
            st.session_state.selected_records = []
            st.session_state.records_updated += 1
            st.rerun()

    def _format_currency(self, value):
        """Format currency values"""
        if not value:
            return "$N/A"
        return f"${float(value):.2f}"

    def _delete_records(self, record_ids):
        """Delete records from the database"""
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        cursor.executemany('DELETE FROM records WHERE id = ?', [(id,) for id in record_ids])
        conn.commit()
        conn.close()
        return True

    def _generate_barcodes_for_existing_records(self):
        """Generate barcodes for records without them"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
            
        selected_ids = st.session_state.selected_records
        placeholders = ','.join(['?'] * len(selected_ids))
        
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f'SELECT id FROM records WHERE id IN ({placeholders}) AND (barcode IS NULL OR barcode = "" OR barcode NOT GLOB "[0-9]*")', selected_ids)
        records_without_barcodes = cursor.fetchall()
        
        cursor.execute('SELECT MAX(CAST(barcode AS INTEGER)) as max_barcode FROM records WHERE barcode GLOB "[0-9]*"')
        result = cursor.fetchone()
        current_max = result[0] if result[0] is not None else 100000
        
        updated_count = 0
        for record in records_without_barcodes:
            record_id = record[0]
            current_max += 1
            # Use update_record to track changes properly
            success = st.session_state.db_manager.update_record(record_id, {'barcode': str(current_max)})
            if success:
                updated_count += 1
        
        conn.close()
        
        if updated_count > 0:
            st.success(f"✅ Generated barcodes for {updated_count} records!")
        else:
            st.info("✅ All selected records already have barcodes!")
            
        st.session_state.records_updated += 1
        st.rerun()

    def _generate_file_at_for_selected_records(self):
        """Generate file_at values for selected records"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
            
        selected_ids = st.session_state.selected_records
        placeholders = ','.join(['?'] * len(selected_ids))
        
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql(f'SELECT * FROM records WHERE id IN ({placeholders})', conn, params=selected_ids)
        conn.close()
        
        updated_count = 0
        for _, record in df.iterrows():
            artist = record.get('artist', '')
            genre = record.get('genre', 'Unknown')
            file_at_letter = self._calculate_file_at(artist)
            file_at = f"{genre}({file_at_letter})"
            
            # Use update_record to track changes properly
            success = st.session_state.db_manager.update_record(record['id'], {'file_at': file_at})
            if success:
                updated_count += 1
        
        if updated_count > 0:
            st.success(f"✅ Regenerated file_at for {updated_count} records!")
            st.session_state.records_updated += 1
            st.rerun()
        else:
            st.info("✅ File_at values updated!")

    def _generate_price_tags_pdf(self):
        """Generate price tags PDF for selected records"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
        
        # Get selected records data
        selected_ids = st.session_state.selected_records
        placeholders = ','.join(['?'] * len(selected_ids))
        
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql(f'SELECT * FROM records WHERE id IN ({placeholders}) AND status = "inventory"', conn, params=selected_ids)
        conn.close()
        
        records_list = df.to_dict('records')
        pdf_buffer = self._generate_price_tags_pdf_for_records(records_list)
        
        # Mark price tags as printed
        st.session_state.db_manager.mark_price_tags_printed(selected_ids)
        
        st.download_button(
            label="⬇️ Download Price Tags PDF",
            data=pdf_buffer.getvalue(),
            file_name=f"price_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )
        
        st.success(f"✅ Price tags PDF ready! {len(records_list)} records marked as printed.")
        st.session_state.records_updated += 1

    def _generate_price_tags_pdf_for_records(self, records):
        """Generate PDF with price tags for given records"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Calculate positions
        array_positions = []
        for array_num in range(4):
            x_start = self.left_margin + (array_num * (self.label_width + self.gutter_spacing))
            array_positions.append(x_start)
        
        # Draw price tags
        self._draw_price_tags(c, records, array_positions, self.top_margin)
        
        c.save()
        buffer.seek(0)
        return buffer

    def _draw_price_tags(self, c, records, array_positions, top_margin):
        """Draw price tags with record information"""
        current_label = 0
        total_labels = len(records)
        
        for array_num, x_start in enumerate(array_positions):
            for row in range(15):
                if current_label >= total_labels:
                    break
                
                y_pos = self.page_height - top_margin - (row * self.label_height)
                
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(0.25)
                c.rect(x_start, y_pos - self.label_height, self.label_width, self.label_height)
                
                record = records[current_label]
                self._draw_label_content(c, record, x_start, y_pos)
                
                current_label += 1
            
            if current_label >= total_labels:
                break
        
        while current_label < total_labels:
            c.showPage()
            current_label = self._draw_next_page(c, records, current_label)

    def _draw_next_page(self, c, records, start_index):
        """Draw additional page with price tags"""
        array_positions = []
        for array_num in range(4):
            x_start = self.left_margin + (array_num * (self.label_width + self.gutter_spacing))
            array_positions.append(x_start)
        
        current_label = start_index
        total_labels = len(records)
        
        for array_num, x_start in enumerate(array_positions):
            for row in range(15):
                if current_label >= total_labels:
                    return current_label
                
                y_pos = self.page_height - self.top_margin - (row * self.label_height)
                
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(0.25)
                c.rect(x_start, y_pos - self.label_height, self.label_width, self.label_height)
                
                record = records[current_label]
                self._draw_label_content(c, record, x_start, y_pos)
                
                current_label += 1
        
        return current_label

    def _draw_label_content(self, c, record, x, y):
        """Draw content for a single price tag"""
        padding = 2
        content_width = self.label_width - (2 * padding)
        font_size = self.font_size
        
        # Artist/title abbreviation
        artist = record.get('artist', '')
        title = record.get('title', '')
        abbreviation = self._create_abbreviation(artist, title)
        
        # Price - use store price from database
        price = record.get('price', 0)
        if price:
            c.setFont("Helvetica-Bold", font_size + 2)
            price_text = f"${float(price):.2f}"
            c.drawString(x + padding, y - 10, price_text)
        
        # Date
        c.setFont("Helvetica", font_size - 1)
        date_text = datetime.now().strftime("%m/%d/%y")
        date_width = c.stringWidth(date_text, "Helvetica", font_size - 1)
        c.drawString(x + self.label_width - date_width - padding, y - 10, date_text)
        
        # Artist/title
        if abbreviation:
            c.setFont("Helvetica", font_size - 1)
            if c.stringWidth(abbreviation, "Helvetica", font_size - 1) > content_width:
                abbreviation = self._truncate_text(c, abbreviation, content_width, font_size - 1)
            c.drawString(x + padding, y - 20, abbreviation)
        
        # File location string - right of artist-title field
        file_at = record.get('file_at', '')
        if file_at:
            c.setFont("Helvetica-Bold", font_size)
            location_width = c.stringWidth(file_at, "Helvetica-Bold", font_size)
            c.drawString(x + self.label_width - location_width - padding, y - 20, file_at)
        
        # Barcode
        barcode = record.get('barcode', '')
        if barcode:
            barcode_obj = code128.Code128(barcode, barWidth=0.4*mm, barHeight=4*mm)
            barcode_x = x + padding - (5 * mm)
            barcode_y = y - 42 - (1.5 * mm)
            barcode_obj.drawOn(c, barcode_x, barcode_y)

    def _create_abbreviation(self, artist, title):
        """Create abbreviation from artist and title"""
        if not artist and not title:
            return ""
        
        artist_words = artist.split()[:3]
        title_words = title.split()[:2]
        
        abbreviation = ""
        if artist_words:
            abbreviation = " ".join(artist_words)
        if title_words:
            if abbreviation:
                abbreviation += " - "
            abbreviation += " ".join(title_words)
        
        if len(abbreviation) > 25:
            abbreviation = abbreviation[:22] + "..."
        
        return abbreviation

    def _truncate_text(self, c, text, max_width, font_size):
        """Truncate text to fit within max width"""
        font_name = "Helvetica"
        if c.stringWidth(text, font_name, font_size) <= max_width:
            return text
        
        low, high = 0, len(text)
        while low < high:
            mid = (low + high) // 2
            test_text = text[:mid] + "..."
            if c.stringWidth(test_text, font_name, font_size) <= max_width:
                low = mid + 1
            else:
                high = mid
        
        return text[:low-1] + "..."

    def _calculate_file_at(self, artist):
        """Calculate file_at value for an artist"""
        if not artist:
            return "?"
        
        # Remove leading/trailing whitespace and convert to lowercase for processing
        artist_clean = artist.strip().lower()
        
        # Handle "The " prefix
        if artist_clean.startswith('the '):
            artist_clean = artist_clean[4:]
        
        # Handle numbers
        if artist_clean and artist_clean[0].isdigit():
            number_words = {
                '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
                '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
            }
            first_char = artist_clean[0]
            return number_words.get(first_char, '?')[0].upper()
        
        # Return first character if it's a letter
        if artist_clean and artist_clean[0].isalpha():
            return artist_clean[0].upper()
        
        return "?"