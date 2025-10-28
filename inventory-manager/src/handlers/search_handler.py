import streamlit as st
import pandas as pd
import re

class SearchHandler:
    def __init__(self, discogs_handler):
        self.discogs_handler = discogs_handler

    def perform_discogs_search(self, search_term):
        """Perform Discogs search"""
        with st.spinner(f"Searching Discogs for: {search_term}..."):
            try:
                # Get format from session state or default to Vinyl
                format_selected = st.session_state.get('format_select', 'Vinyl')
                search_query = f"{search_term} {format_selected}"
                filename_base = self._generate_filename(search_term, format_selected)
                
                search_data = self.discogs_handler.search_multiple_results(
                    search_query, 
                    filename_base
                )
                
                if search_data and search_data.get('results'):
                    # Convert Discogs results to same format as database results
                    formatted_results = []
                    for result in search_data['results']:
                        formatted_result = {
                            'type': 'discogs',
                            'artist': self._extract_artist_from_result(result),
                            'title': self._extract_title_from_result(result),
                            'image_url': self._extract_image_from_result(result),
                            'year': result.get('year', 'Unknown'),
                            'genre': ', '.join(result.get('genre', [])) or 'Unknown',
                            'catalog_number': self._extract_catalog_number(result),
                            'discogs_id': result.get('id')
                        }
                        formatted_results.append(formatted_result)
                    
                    return formatted_results
                else:
                    st.error(f"No results found for: {search_term}")
                    return []
                    
            except Exception as e:
                st.error(f"Error searching Discogs: {str(e)}")
                return []

    def perform_database_search(self, search_term):
        """Perform database search"""
        try:
            conn = st.session_state.db_manager._get_connection()
            df = pd.read_sql(
                'SELECT * FROM records_with_genres WHERE status = "inventory" AND (artist LIKE ? OR title LIKE ? OR barcode LIKE ?) ORDER BY artist, title',
                conn,
                params=(f'%{search_term}%', f'%{search_term}%', f'%{search_term}%')
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
                    'file_at': record.get('file_at', ''),
                    'price': f"${record.get('store_price', 0) or 0:.2f}",
                    'condition': record.get('condition', ''),
                    'genre': record.get('genre', '')
                }
                formatted_results.append(formatted_result)
            
            return formatted_results
            
        except Exception as e:
            st.error(f"Error searching database: {str(e)}")
            return []

    def _extract_artist_from_result(self, result):
        """Extract artist name from Discogs result"""
        if isinstance(result, dict):
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
        if isinstance(result, dict):
            if result.get('title'):
                title_text = result['title']
                if ' - ' in title_text:
                    parts = title_text.split(' - ', 1)
                    return parts[1].strip()
                return title_text
        return 'Unknown Title'

    def _extract_image_from_result(self, result):
        """Extract image URL from Discogs result"""
        if not isinstance(result, dict):
            return ""
            
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
        """Extract catalog number from Discogs result"""
        try:
            if not isinstance(result, dict):
                return ''
                
            if result.get('catno'):
                return result['catno']
            
            if result.get('label'):
                labels = result['label']
                if isinstance(labels, list):
                    for label in labels:
                        if isinstance(label, dict) and label.get('catno'):
                            return label['catno']
                        elif isinstance(label, str):
                            if any(char.isdigit() for char in label):
                                return label
                elif isinstance(labels, str):
                    if any(char.isdigit() for char in labels):
                        return labels
            
            if result.get('format') and isinstance(result['format'], list):
                for format_item in result['format']:
                    if isinstance(format_item, str) and any(char.isdigit() for char in format_item):
                        return format_item
            
            return ''
        except Exception as e:
            return ''

    def _generate_filename(self, search_query, format_name):
        """Generate a safe filename"""
        clean_query = re.sub(r'[^\w\s-]', '', search_query)
        clean_query = re.sub(r'[-\s]+', '_', clean_query)
        clean_format = re.sub(r'[^\w\s-]', '', format_name)
        clean_format = re.sub(r'[-\s]+', '_', clean_format)
        return f"batch_{clean_query}_{clean_format}".lower()