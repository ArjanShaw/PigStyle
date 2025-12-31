import streamlit as st
import pandas as pd
import re
import requests
import time  # ADDED

class SearchHandler:
    def __init__(self, discogs_handler, base_url="https://arjanshaw.pythonanywhere.com"):
        self.discogs_handler = discogs_handler
        self.base_url = base_url

    def clean_artist_name(self, artist_name):
        """
        Clean artist name by removing discogs suffixes like (n) and *
        """
        if not artist_name:
            return artist_name
        
        # Remove patterns like (2), (3), etc.
        cleaned = re.sub(r'\s*\(\d+\)\s*$', '', artist_name)
        
        # Remove trailing asterisk and any surrounding whitespace
        cleaned = re.sub(r'\s*\*\s*$', '', cleaned)
        
        # Remove trailing slash and anything after it
        cleaned = re.sub(r'\s*\/.*$', '', cleaned)
        
        return cleaned.strip()

    def perform_discogs_search(self, search_term):
        """Perform Discogs search - NOW USES SIMPLE SEARCH WITH NO EXTRA API CALLS"""
        with st.spinner(f"Searching Discogs for: {search_term}..."):
            try:
                # Get format from session state or default to Vinyl
                format_selected = st.session_state.get('format_select', 'Vinyl')
                search_query = f"{search_term} {format_selected}"
                
                start_time = time.time()  # START TIMING
                
                # Use the new simple search method - NO GROUPED PRICING, NO EXTRA API CALLS
                results = self.discogs_handler.get_simple_search_results(search_query)
                
                duration = time.time() - start_time  # END TIMING
                
                print(f"SearchHandler Discogs Search '{search_term[:30]}...' took {duration:.2f}s")

                
                if results:
                    return results
                else:
                    st.error(f"No results found for: {search_term}")
                    return []
                    
            except Exception as e:
                st.error(f"Error searching Discogs: {str(e)}")
                return []

    def perform_database_search(self, search_term, user=None):
        """Perform database search - NOW INCLUDES CATALOG NUMBER SEARCH AND FILTERS BY CONSIGNOR"""
        try:
            start_time = time.time()  # START TIMING
            
            # Get user role and ID
            user_role = user.get('role', 'consignor') if user else 'consignor'
            user_id = user.get('id') if user else None
            
            # Build query parameters
            params = f"q={search_term}"
            
            # If user is a consignor, only show their own records
            if user_role == 'consignor' and user_id:
                params += f"&consignor_id={user_id}"
            
            # Use API-based search with consignor filter if applicable
            response = requests.get(f"{self.base_url}/search?{params}", timeout=10)
            
            duration = time.time() - start_time  # END TIMING
            
            print(f"SearchHandler DB Search: {search_term[:30]}... took {duration:.2f}s")
         
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    records = data.get('records', [])
                    df = pd.DataFrame(records) if records else pd.DataFrame()
                else:
                    return []
            else:
                return []
            
            # Convert database results to same format
            formatted_results = []
            for _, record in df.iterrows():
                formatted_result = {
                    'type': 'database',
                    'id': record.get('id', ''),
                    'artist': record.get('artist', ''),
                    'title': record.get('title', ''),
                    'image_url': record.get('image_url', ''),
                    'barcode': record.get('barcode', ''),
                    'catalog_number': record.get('catalog_number', ''),  # Include catalog number
                    'file_at': record.get('file_at', ''),
                    'store_price': record.get('store_price', ''),
                    'ebay_sell_at': record.get('ebay_sell_at', ''),
                    'discogs_suggested_price': record.get('discogs_suggested_price', ''),
                    'ebay_lowest_price': record.get('ebay_lowest_price', ''),
                    'condition': record.get('condition', ''),
                    'genre': record.get('genre_name', record.get('genre', '')),  # FIXED: API returns 'genre_name'
                    'youtube_url': record.get('youtube_url', ''),
                    'consignor_id': record.get('consignor_id', ''),  # ADDED: Include consignor_id
                    'consignor_name': record.get('consignor_name', ''),  # Add consignor name
                    'commission_rate': record.get('commission_rate', ''),
                    'compilation': record.get('compilation', False)
                }
                
                formatted_results.append(formatted_result)
            
            return formatted_results
            
        except Exception as e:
            st.error(f"Error searching database: {str(e)}")
            return []

    def _generate_filename(self, search_query, format_name):
        """Generate a safe filename"""
        clean_query = re.sub(r'[^\w\s-]', '', search_query)
        clean_query = re.sub(r'[-\s]+', '_', clean_query)
        clean_format = re.sub(r'[^\w\s-]', '', format_name)
        clean_format = re.sub(r'[-\s]+', '_', clean_format)
        return f"batch_{clean_query}_{clean_format}".lower()