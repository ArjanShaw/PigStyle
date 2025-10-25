import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sqlite3
from typing import Dict, List, Optional, Tuple
from draft_csv_handler import DraftCSVHandler
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128
import io
import json
import re
import time
from barcode_generator import BarcodeGenerator

CATEGORY_MAP = {
    "Vinyl": "176985",
    "CDs": "176984", 
    "Cassettes": "176983"
}

class PrintConfig:
    def __init__(self, config_file="print_config.json"):
        self.config_file = config_file
        self.defaults = {
            "label_width_mm": 45.0,
            "label_height_mm": 16.80,
            "left_margin_mm": 6.50,
            "gutter_spacing_mm": 6.50,
            "top_margin_mm": 14.00,
            "font_size": 7
        }
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file or use defaults"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    config = self.defaults.copy()
                    config.update(loaded_config)
                    return config
            except Exception as e:
                print(f"Error loading config file: {e}. Using defaults.")
                return self.defaults.copy()
        else:
            # Create default config file
            self._save_config(self.defaults)
            return self.defaults.copy()
    
    def _save_config(self, config):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config file: {e}")
    
    def get(self, key, default=None):
        """Get a configuration value with optional default"""
        return self.config.get(key, default if default is not None else self.defaults.get(key))
    
    def update(self, new_config):
        """Update configuration and save to file"""
        self.config.update(new_config)
        self._save_config(self.config)
    
    def get_all(self):
        """Get all configuration values"""
        return self.config.copy()

class RecordsTab:
    def __init__(self, discogs_handler, debug_tab):
        self.discogs_handler = discogs_handler
        self.barcode_generator = BarcodeGenerator()
        self.debug_tab = debug_tab
        self.page_size = 50
        self.current_page = 1
        self.config = PrintConfig()
        self._update_dimensions_from_config()
        
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
        
    def render(self):
        tab1, tab2 = st.tabs(["📥 Search & Add", "📊 Table"])
        
        with tab1:
            self._render_search_tab()
        
        with tab2:
            self._render_table_tab()

    def _render_search_tab(self):
        """Render the search and add functionality"""
        st.subheader("Search Discogs")
        
        # Format and Condition selection
        col1, col2 = st.columns([1, 1])
        with col1:
            format_selected = st.selectbox(
                "Format",
                options=list(CATEGORY_MAP.keys()),
                key="format_select"
            )
        with col2:
            condition = st.selectbox(
                "Condition",
                options=["1", "2", "3", "4", "5"],
                index=4,
                key="condition_select"
            )
        
        # Simple search form
        with st.form(key="search_form"):
            search_input = st.text_input(
                "Search",
                placeholder="Enter search term and press Enter or click Search",
                key="search_input"
            )
            
            col1, col2 = st.columns([1, 1])
            with col1:
                search_submitted = st.form_submit_button("Search", use_container_width=True)
            with col2:
                clear_submitted = st.form_submit_button("Clear Results", use_container_width=True)
        
        # Handle search
        if search_submitted and search_input and search_input.strip():
            self._perform_search(search_input.strip(), format_selected)
        
        # Handle clear
        if clear_submitted:
            st.session_state.current_search = ""
            st.rerun()
        
        # Show success message if record was just added
        if st.session_state.last_added:
            st.success(f"✅ Record added to database! (Barcode: {st.session_state.last_added})")
            # Increment update counter to refresh records tab
            st.session_state.records_updated += 1
            st.session_state.last_added = None
        
        # Display search results if available
        if st.session_state.current_search and st.session_state.current_search in st.session_state.search_results:
            self._render_search_results(st.session_state.current_search, st.session_state.search_results[st.session_state.current_search], format_selected, condition)

    def _perform_search(self, search_term, format_selected):
        """Perform the Discogs search"""
        with st.spinner(f"Searching Discogs for: {search_term}..."):
            try:
                search_results = self._search_discogs(search_term, format_selected)
                
                if search_results and search_results.get('results'):
                    st.session_state.current_search = search_term
                    st.session_state.search_results[search_term] = search_results
                    self.debug_tab.add_log("SEARCH", f"Found {len(search_results['results'])} results for: {search_term}")
                else:
                    st.error(f"No results found for: {search_term}")
                    self.debug_tab.add_log("SEARCH", f"No results found for: {search_term}")
                    
            except Exception as e:
                st.error(f"Error searching Discogs: {str(e)}")
                self.debug_tab.add_log("ERROR", f"Search error for {search_term}: {str(e)}")

    def _search_discogs(self, search_term, format_selected):
        """Search Discogs and return multiple results"""
        try:
            search_query = f"{search_term} {format_selected}"
            filename_base = self._generate_filename(search_term, format_selected)
            
            self.debug_tab.add_log("DISCOGS", f"Searching: {search_query}")
            
            search_data = self.discogs_handler.search_multiple_results(
                search_query, 
                filename_base
            )
            
            if search_data:
                self.debug_tab.add_log("DISCOGS", f"Search successful: {len(search_data.get('results', []))} results")
            else:
                self.debug_tab.add_log("DISCOGS", "Search returned no data")
            
            return search_data
            
        except Exception as e:
            self.debug_tab.add_log("ERROR", f"Search error: {str(e)}")
            return None

    def _get_discogs_url(self, result):
        """Convert Discogs API URI to proper Discogs website URL"""
        uri = result.get('uri') or result.get('resource_url')
        if not uri:
            return None
        
        if uri.startswith('/'):
            if '/releases/' in uri:
                release_id = uri.split('/releases/')[-1].split('-')[0]
                return f"https://www.discogs.com/release/{release_id}"
            elif '/masters/' in uri:
                master_id = uri.split('/masters/')[-1].split('-')[0]
                return f"https://www.discogs.com/master/{master_id}"
        
        release_id = result.get('id')
        if release_id:
            return f"https://www.discogs.com/release/{release_id}"
        
        return None

    def _render_search_results(self, search_term, search_data, format_selected, condition):
        """Render Discogs search results"""
        st.subheader(f"Results for: '{search_term}'")
        
        if not search_data or 'results' not in search_data or not search_data['results']:
            st.warning("No results found on Discogs")
            return
        
        results = search_data['results']
        st.write(f"Found **{len(results)}** results:")
        
        # Display results in a simple, performant way
        for i, result in enumerate(results):
            with st.container():
                col1, col2, col3, col4 = st.columns([1, 3, 2, 1])
                
                with col1:
                    image_url = self._extract_image_from_result(result)
                    if image_url:
                        st.image(image_url, width=80, use_container_width=False)
                
                with col2:
                    artist = self._extract_artist_from_result(result)
                    title = self._extract_title_from_result(result)
                    st.write(f"**{artist}**")
                    st.write(f"*{title}*")
                    
                    year = result.get('year', 'Unknown')
                    genre = ', '.join(result.get('genre', [])) or 'Unknown'
                    st.write(f"{year} • {genre}")
                    
                    catalog_number = self._extract_catalog_number(result)
                    if catalog_number:
                        st.write(f"Catalog: {catalog_number}")
                
                with col3:
                    # Show additional info
                    discogs_url = self._get_discogs_url(result)
                    if discogs_url:
                        st.markdown(f'[🔗 Discogs Page]({discogs_url})')
                
                with col4:
                    # Add button - this is the key functionality
                    if st.button("Add to DB", key=f"add_{i}_{hash(search_term)}", use_container_width=True):
                        success = self._add_result_to_database(result, search_term, format_selected, condition)
                        if success:
                            # Just show success message, don't clear search results
                            st.session_state.last_added = success
                            st.rerun()
                
                st.divider()

    def _add_result_to_database(self, result, search_term, format_selected, condition):
        """Add the selected result to the database"""
        try:
            release_id = result.get('id')
            if not release_id:
                st.error("No release ID found")
                return False
            
            filename_base = self._generate_filename(f"{search_term}_release_{release_id}", format_selected)
            
            # Get pricing information
            with st.spinner("Getting pricing data..."):
                self.debug_tab.add_log("DISCOGS", f"Getting pricing for release {release_id}")
                pricing_data = self.discogs_handler.get_release_pricing(
                    str(release_id), 
                    search_term, 
                    filename_base
                )
            
            if not pricing_data or not pricing_data.get('success'):
                error_msg = pricing_data.get('error', 'Unable to get pricing data') if pricing_data else 'No pricing data returned'
                st.error(f"Failed to get pricing: {error_msg}")
                self.debug_tab.add_log("ERROR", f"Pricing failed for {release_id}: {error_msg}")
                return False
            
            # Extract result information
            artist = self._extract_artist_from_result(result)
            title = self._extract_title_from_result(result)
            image_url = self._extract_image_from_result(result)
            genre = ', '.join(result.get('genre', [])) or 'Unknown'
            year = result.get('year', '')
            catalog_number = self._extract_catalog_number(result)
            
            # Generate sequential barcode number
            next_barcode = self._generate_next_barcode()
            
            # Save to database - using correct column names
            result_data = {
                'artist': artist,
                'title': title,
                'discogs_median_price': pricing_data['median_price'],
                'discogs_lowest_price': pricing_data.get('lowest_price'),
                'discogs_highest_price': pricing_data.get('highest_price'),
                'genre': genre,
                'image_url': image_url,
                'format': format_selected,
                'catalog_number': catalog_number,
                'barcode': next_barcode,
                'condition': condition,
                'year': year,
                'discogs_have': 0,
                'discogs_want': 0
            }
            
            record_id = st.session_state.db_manager.save_record(result_data)
            self.debug_tab.add_log("DATABASE", f"Added record to database: {artist} - {title}", {
                'barcode': next_barcode,
                'release_id': release_id
            })
            return next_barcode  # Return barcode for success message
            
        except Exception as e:
            st.error(f"Error adding to database: {str(e)}")
            self.debug_tab.add_log("ERROR", f"Database add error: {str(e)}")
            return False

    def _generate_next_barcode(self):
        """Generate next sequential barcode number"""
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(CAST(barcode AS INTEGER)) as max_barcode FROM records WHERE barcode GLOB "[0-9]*"')
            result = cursor.fetchone()
            conn.close()
            
            current_max = result[0] if result[0] is not None else 100000
            next_barcode = current_max + 1
            return str(next_barcode)
        except Exception as e:
            return str(int(time.time() * 1000))[-9:]

    def _extract_artist_from_result(self, result):
        """Extract artist name from Discogs result"""
        if result.get('artists') and isinstance(result['artists'], list):
            for artist in result['artists']:
                if artist.get('name'):
                    artist_name = artist['name']
                    artist_name = re.sub(r'\s*\(\d+\)\s*$', '', artist_name)
                    return artist_name.strip()
        
        if result.get('artist'):
            artist_name = result['artist']
            artist_name = re.sub(r'\s*\(\d+\)\s*$', '', artist_name)
            return artist_name.strip()
        
        if result.get('title'):
            title = result['title']
            if ' - ' in title:
                artist_name = title.split(' - ')[0].strip()
                artist_name = re.sub(r'\s*\(\d+\)\s*$', '', artist_name)
                return artist_name.strip()
        
        return 'Unknown Artist'

    def _extract_title_from_result(self, result):
        """Extract title from Discogs result"""
        if result.get('title'):
            title_text = result['title']
            if ' - ' in title_text:
                parts = title_text.split(' - ', 1)
                return parts[1].strip()
            return title_text
        return 'Unknown Title'

    def _extract_image_from_result(self, result):
        """Extract image URL from Discogs result"""
        image_fields = [
            result.get('cover_image'),
            result.get('thumb'),
            result.get('images', [{}])[0].get('uri'),
            result.get('images', [{}])[0].get('uri150'),
        ]
        
        for image_field in image_fields:
            if image_field and isinstance(image_field, str) and image_field.startswith('http'):
                return image_field
        
        return ""

    def _extract_catalog_number(self, result):
        """Extract catalog number from Discogs result - FIXED VERSION"""
        try:
            # Priority 1: Direct catno field
            if result.get('catno'):
                return result['catno']
            
            # Priority 2: Check labels array - FIXED: Handle both dict and string labels
            if result.get('label'):
                labels = result['label']
                if isinstance(labels, list):
                    for label in labels:
                        if isinstance(label, dict) and label.get('catno'):
                            return label['catno']
                        elif isinstance(label, str):
                            # If label is a string, it might contain catalog info
                            if any(char.isdigit() for char in label):
                                return label
                elif isinstance(labels, str):
                    # If label is a single string, check if it contains catalog info
                    if any(char.isdigit() for char in labels):
                        return labels
            
            # Priority 3: Check format array for catalog number
            if result.get('format') and isinstance(result['format'], list):
                for format_item in result['format']:
                    if isinstance(format_item, str) and any(char.isdigit() for char in format_item):
                        return format_item
            
            return ''
        except Exception as e:
            # If any error occurs, return empty string
            return ''

    def _generate_filename(self, search_query, format_name):
        """Generate a safe filename"""
        import re
        clean_query = re.sub(r'[^\w\s-]', '', search_query)
        clean_query = re.sub(r'[-\s]+', '_', clean_query)
        clean_format = re.sub(r'[^\w\s-]', '', format_name)
        clean_format = re.sub(r'[-\s]+', '_', clean_format)
        return f"batch_{clean_query}_{clean_format}".lower()

    def _render_table_tab(self):
        """Render the records table functionality"""
        try:
            # Database statistics - direct count from records table
            stats = self._get_database_stats_direct()
            
            # Top row: Stats and action buttons - left aligned
            col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1, 1, 1, 1, 2])
            with col1:
                st.metric("Total Records", stats['records_count'])
            with col2:
                if st.button("📊 Export CSV", use_container_width=True, help="Export all records to CSV"):
                    self._export_all_records()
            with col3:
                if st.button("📦 Ebay List", use_container_width=True, help="Export selected records for eBay"):
                    self._export_ebay_list()
            with col4:
                if st.button("🔢 Gen Barcodes", use_container_width=True, help="Generate missing barcodes"):
                    self._generate_barcodes_for_existing_records()
            with col5:
                if st.button("🖨️ Print Selected", use_container_width=True, help="Print selected records"):
                    self._generate_price_tags_pdf()
            with col6:
                if st.button("🗑️ Delete Selected", use_container_width=True, help="Delete selected records"):
                    self._delete_selected_records()
            
            # Second row: Search and filters
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                search_term = st.text_input(
                    "Search by artist, title, or barcode:",
                    key="search_records",
                    placeholder="Enter search term..."
                )
            
            with col2:
                # Quick filters
                filter_option = st.selectbox(
                    "Filter by",
                    options=["All Records", "No Barcode", "No Price Data", "No Genre"],
                    key="quick_filter"
                )
            
            with col3:
                # Page size selector
                new_page_size = st.selectbox(
                    "Records per page:",
                    options=[25, 50, 100],
                    index=1,  # Default to 50
                    key="page_size_selector"
                )
                if new_page_size != self.page_size:
                    self.page_size = new_page_size
                    st.session_state.current_page = 1
                    st.rerun()

            if stats['records_count'] > 0:
                self._render_records_table()
            else:
                st.info("No records in database yet. Start by searching and adding records above!")
                
        except Exception as e:
            st.error(f"Error loading records: {e}")

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

    def _export_ebay_list(self):
        """Export selected records as eBay draft listings"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
        
        try:
            # Get selected records data
            selected_ids = st.session_state.selected_records
            placeholders = ','.join(['?'] * len(selected_ids))
            
            conn = st.session_state.db_manager._get_connection()
            df = pd.read_sql(f'SELECT * FROM records WHERE id IN ({placeholders})', conn, params=selected_ids)
            conn.close()
            
            records_list = df.to_dict('records')
            
            # Generate eBay formatted TXT
            draft_handler = DraftCSVHandler()
            ebay_content = draft_handler.generate_ebay_txt_from_records(records_list)
            
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
                
        except Exception as e:
            st.error(f"Error generating eBay list: {e}")

    def _get_database_stats_direct(self) -> Dict:
        """Get database statistics directly from records table"""
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM records')
            records_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM records WHERE barcode IS NULL OR barcode = ""')
            no_barcode_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'records_count': records_count,
                'no_barcode_count': no_barcode_count
            }
        except Exception as e:
            st.error(f"Error getting stats: {e}")
            return {'records_count': 0, 'no_barcode_count': 0}

    def _get_paginated_records_direct(self, offset: int, limit: int, search_term: str = None, filter_option: str = None) -> pd.DataFrame:
        """Get paginated records directly from records table with optional filtering"""
        try:
            conn = st.session_state.db_manager._get_connection()
            
            # Simple query - only from records table with correct column names
            base_query = """
            SELECT 
                id, artist, title, 
                discogs_median_price, discogs_lowest_price, discogs_highest_price, 
                image_url, barcode, format, condition, created_at, genre
            FROM records 
            WHERE 1=1
            """
            
            params = []
            
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
            
            # Add ordering and pagination
            base_query += " ORDER BY discogs_median_price DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            df = pd.read_sql_query(base_query, conn, params=params)
            conn.close()
            return df
            
        except Exception as e:
            st.error(f"Error loading records: {e}")
            return pd.DataFrame()

    def _get_total_filtered_count(self, search_term: str = None, filter_option: str = None) -> int:
        """Get total count of records after applying filters"""
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            
            base_query = "SELECT COUNT(*) FROM records WHERE 1=1"
            params = []
            
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
            
            cursor.execute(base_query, params)
            count = cursor.fetchone()[0]
            conn.close()
            return count
            
        except Exception as e:
            st.error(f"Error counting records: {e}")
            return 0

    def _render_records_table(self):
        """Render records with pagination"""
        
        # Get current filter state
        search_term = st.session_state.get('search_records', '')
        filter_option = st.session_state.get('quick_filter', 'All Records')
        
        # Initialize pagination
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 1
        
        # Get total count for pagination
        total_records = self._get_total_filtered_count(search_term, filter_option)
        
        if total_records == 0:
            st.info("No records found matching your criteria.")
            return
        
        # Calculate pagination
        total_pages = max(1, (total_records + self.page_size - 1) // self.page_size)
        current_page = min(st.session_state.current_page, total_pages)
        offset = (current_page - 1) * self.page_size
        
        # Load only the current page of records
        records = self._get_paginated_records_direct(offset, self.page_size, search_term, filter_option)
        
        if len(records) == 0 and current_page > 1:
            # If no records on current page but we're not on page 1, go to page 1
            st.session_state.current_page = 1
            st.rerun()
            return
        
        # Display record count and pagination info
        self._render_pagination_info(total_records, current_page, total_pages, search_term, filter_option)
        
        # Render the records table with selection
        self._render_records_dataframe(records)
        
        # Pagination controls
        if total_pages > 1:
            self._render_pagination_controls(current_page, total_pages)

    def _render_pagination_info(self, total_records: int, current_page: int, total_pages: int, search_term: str, filter_option: str):
        """Render pagination information and filters"""
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            start_record = (current_page - 1) * self.page_size + 1
            end_record = min(current_page * self.page_size, total_records)
            
            if search_term:
                st.write(f"**Showing {start_record}-{end_record} of {total_records} records matching '{search_term}'**")
            elif filter_option != "All Records":
                st.write(f"**Showing {start_record}-{end_record} of {total_records} {filter_option.lower()}**")
            else:
                st.write(f"**Showing {start_record}-{end_record} of {total_records} records**")
        
        with col3:
            st.write(f"**Page {current_page} of {total_pages}**")

    def _render_records_dataframe(self, records: pd.DataFrame):
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
            display_data.append({
                'Select': is_selected,
                'Cover': record.get('image_url', ''),
                'Artist': record.get('artist', ''),
                'Title': record.get('title', ''),
                'Barcode': record.get('barcode', ''),
                'Condition': f"{record.get('condition', '')}/5",
                'Format': record.get('format', ''),
                'Median Price': self._format_currency(record.get('discogs_median_price')),
                'Lowest Price': self._format_currency(record.get('discogs_lowest_price')),
                'Highest Price': self._format_currency(record.get('discogs_highest_price')),
                'Added': record.get('created_at', '')[:16] if record.get('created_at') else ''
            })
        
        display_df = pd.DataFrame(display_data)
        
        # Configure columns for better display
        column_config = {
            'Select': st.column_config.CheckboxColumn('Select', width='small'),
            'Cover': st.column_config.ImageColumn('Cover', width='small'),
            'Artist': st.column_config.TextColumn('Artist', width='medium'),
            'Title': st.column_config.TextColumn('Title', width='large'),
            'Barcode': st.column_config.TextColumn('Barcode', width='small'),
            'Condition': st.column_config.TextColumn('Condition', width='small'),
            'Format': st.column_config.TextColumn('Format', width='small'),
            'Median Price': st.column_config.TextColumn('Median Price', width='small'),
            'Lowest Price': st.column_config.TextColumn('Low Price', width='small'),
            'Highest Price': st.column_config.TextColumn('High Price', width='small'),
            'Added': st.column_config.TextColumn('Added', width='small'),
        }
        
        # Display editable dataframe with selection
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            use_container_width=True,
            height=min(600, 35 * len(display_df) + 40),
            hide_index=True,
            key="records_editor"
        )
        
        # Update selection state based on editor changes
        if edited_df is not None:
            selected_ids = []
            for i, (_, original_record) in enumerate(records.iterrows()):
                if i < len(edited_df) and edited_df.iloc[i]['Select']:
                    selected_ids.append(original_record['id'])
            
            # Only update if selection actually changed
            if set(selected_ids) != set(st.session_state.selected_records):
                st.session_state.selected_records = selected_ids
                st.rerun()

    def _delete_selected_records(self):
        """Delete selected records"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
            
        try:
            selected_ids = st.session_state.selected_records
            if self._delete_records(selected_ids):
                st.success(f"Deleted {len(selected_ids)} records!")
                # Clear selection after deletion
                st.session_state.selected_records = []
                st.session_state.records_updated += 1
                st.rerun()
        except Exception as e:
            st.error(f"Error deleting records: {e}")

    def _render_pagination_controls(self, current_page: int, total_pages: int):
        """Render pagination controls"""
        st.divider()
        
        col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
        
        with col1:
            if st.button("⏮️ First", disabled=current_page == 1, use_container_width=True):
                st.session_state.current_page = 1
                st.rerun()
        
        with col2:
            if st.button("◀️ Previous", disabled=current_page == 1, use_container_width=True):
                st.session_state.current_page = current_page - 1
                st.rerun()
        
        with col3:
            # Page jumper
            new_page = st.number_input(
                "Go to page:",
                min_value=1,
                max_value=total_pages,
                value=current_page,
                key="page_jumper"
            )
            if new_page != current_page:
                st.session_state.current_page = new_page
                st.rerun()
        
        with col4:
            if st.button("Next ▶️", disabled=current_page == total_pages, use_container_width=True):
                st.session_state.current_page = current_page + 1
                st.rerun()
        
        with col5:
            if st.button("Last ⏭️", disabled=current_page == total_pages, use_container_width=True):
                st.session_state.current_page = total_pages
                st.rerun()

    def _format_currency(self, value):
        """Format currency values"""
        if not value:
            return "$N/A"
        try:
            return f"${float(value):.2f}"
        except (ValueError, TypeError):
            return "$N/A"

    def _delete_records(self, record_ids):
        """Delete records from the database"""
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.executemany('DELETE FROM records WHERE id = ?', [(id,) for id in record_ids])
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error deleting records: {e}")
            return False

    def _export_all_records(self):
        """Export all records to CSV directly from table"""
        try:
            # Get all records in chunks to avoid memory issues
            all_records = []
            limit = 1000
            offset = 0
            
            while True:
                chunk = self._get_paginated_records_direct(offset, limit)
                if len(chunk) == 0:
                    break
                all_records.append(chunk)
                offset += limit
            
            if all_records:
                export_df = pd.concat(all_records, ignore_index=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"vinyl_records_export_{timestamp}.csv"
                
                csv_data = export_df.to_csv(index=False)
                
                st.download_button(
                    label="⬇️ Download CSV File",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    key=f"download_{timestamp}"
                )
                
                st.success(f"✅ Export ready! {len(export_df)} records.")
            else:
                st.warning("No records to export.")
                
        except Exception as e:
            st.error(f"Error exporting records: {e}")

    def _generate_barcodes_for_existing_records(self):
        """Generate barcodes for records without them"""
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM records WHERE barcode IS NULL OR barcode = "" OR barcode NOT GLOB "[0-9]*"')
            records_without_barcodes = cursor.fetchall()
            
            cursor.execute('SELECT MAX(CAST(barcode AS INTEGER)) as max_barcode FROM records WHERE barcode GLOB "[0-9]*"')
            result = cursor.fetchone()
            current_max = result[0] if result[0] is not None else 100000
            
            updated_count = 0
            for record in records_without_barcodes:
                record_id = record[0]
                current_max += 1
                cursor.execute('UPDATE records SET barcode = ? WHERE id = ?', (str(current_max), record_id))
                updated_count += 1
            
            conn.commit()
            conn.close()
            
            if updated_count > 0:
                st.success(f"✅ Generated barcodes for {updated_count} records!")
            else:
                st.info("✅ All records already have barcodes!")
                
            st.session_state.records_updated += 1
            st.rerun()
            
        except Exception as e:
            st.error(f"Error generating barcodes: {e}")

    def _generate_price_tags_pdf(self):
        """Generate price tags PDF for selected records"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
        
        try:
            # Get selected records data
            selected_ids = st.session_state.selected_records
            placeholders = ','.join(['?'] * len(selected_ids))
            
            conn = st.session_state.db_manager._get_connection()
            df = pd.read_sql(f'SELECT * FROM records WHERE id IN ({placeholders})', conn, params=selected_ids)
            conn.close()
            
            records_list = df.to_dict('records')
            pdf_buffer = self._generate_price_tags_pdf_for_records(records_list)
            
            st.download_button(
                label="⬇️ Download Price Tags PDF",
                data=pdf_buffer.getvalue(),
                file_name=f"price_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )
            
            st.success(f"✅ Price tags PDF ready! {len(records_list)} records.")
            
        except Exception as e:
            st.error(f"Error generating price tags: {e}")

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
        
        # Price
        price = record.get('discogs_median_price', 0)
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
        
        # File location string
        genre = record.get('genre', '')
        file_at = self._calculate_file_at(artist)
        location_string = f"[{genre}]({file_at})"
        c.setFont("Helvetica", font_size - 1)
        location_width = c.stringWidth(location_string, "Helvetica", font_size - 1)
        c.drawString(x + self.label_width - location_width - padding, y - 30, location_string)
        
        # Barcode
        barcode = record.get('barcode', '')
        if barcode:
            try:
                barcode_obj = code128.Code128(barcode, barWidth=0.4*mm, barHeight=4*mm)
                barcode_x = x + padding - (5 * mm)
                barcode_y = y - 42 - (1.5 * mm)
                barcode_obj.drawOn(c, barcode_x, barcode_y)
            except:
                c.setFont("Helvetica", font_size - 2)
                barcode_text = f"#{barcode}"
                barcode_x = x + padding - (5 * mm)
                barcode_y = y - 42 - (1.5 * mm)
                c.drawString(barcode_x, barcode_y, barcode_text)

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