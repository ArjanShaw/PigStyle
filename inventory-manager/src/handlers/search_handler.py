import streamlit as st
import pandas as pd
import re

class SearchHandler:
    def __init__(self, discogs_handler):
        self.discogs_handler = discogs_handler

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
                
                # Use the new simple search method - NO GROUPED PRICING, NO EXTRA API CALLS
                results = self.discogs_handler.get_simple_search_results(search_query)
                
                if results:
                    return results
                else:
                    st.error(f"No results found for: {search_term}")
                    return []
                    
            except Exception as e:
                st.error(f"Error searching Discogs: {str(e)}")
                return []

    def perform_database_search(self, search_term):
        """Perform database search - NOW INCLUDES CATALOG NUMBER SEARCH"""
        try:
            conn = st.session_state.db_manager._get_connection()
            
            # Updated query to include catalog_number search
            df = pd.read_sql(
                '''SELECT r.*, g.genre_name as genre 
                   FROM records r 
                   LEFT JOIN genres g ON r.genre_id = g.id 
                   WHERE (r.artist LIKE ? OR r.title LIKE ? OR r.barcode LIKE ? OR r.catalog_number LIKE ?) 
                   ORDER BY r.artist, r.title''',
                conn,
                params=(f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%')
            )
            conn.close()
            
            # Convert database results to same format
            formatted_results = []
            for _, record in df.iterrows():
                formatted_result = {
                    'type': 'database',
                    'id': record['id'],
                    'artist': record.get('artist', ''),
                    'title': record.get('title', ''),
                    'image_url': record.get('image_url', ''),
                    'barcode': record.get('barcode', ''),
                    'catalog_number': record.get('catalog_number', ''),  # Include catalog number
                    'file_at': record.get('file_at', ''),
                    'store_price': record.get('store_price', ''),
                    'ebay_sell_at': record.get('ebay_sell_at', ''),
                    'discogs_lowest_price': record.get('discogs_lowest_price', ''),
                    'discogs_estimated_price': record.get('discogs_estimated_price', ''),
                    'ebay_lowest_price': record.get('ebay_lowest_price', ''),
                    'condition': record.get('condition', ''),
                    'genre': record.get('genre', ''),
                    'youtube_url': record.get('youtube_url', '')
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