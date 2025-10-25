import streamlit as st
import time
import re
from barcode_generator import BarcodeGenerator

CATEGORY_MAP = {
    "Vinyl": "176985",
    "CDs": "176984", 
    "Cassettes": "176983"
}

class SearchTab:
    def __init__(self, discogs_handler, debug_tab):
        self.discogs_handler = discogs_handler
        self.barcode_generator = BarcodeGenerator()
        self.debug_tab = debug_tab
        
    def render(self):
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