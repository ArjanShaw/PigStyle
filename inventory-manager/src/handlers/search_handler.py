import streamlit as st
import pandas as pd
import re
import requests
import time
import logging

logger = logging.getLogger(__name__)

class SearchHandler:
    def __init__(self, discogs_handler, base_url="https://arjanshaw.pythonanywhere.com"):
        self.discogs_handler = discogs_handler
        self.base_url = base_url
        self._search_cache = {}

    def clean_artist_name(self, artist_name):
        if not artist_name:
            return artist_name
        
        cleaned = re.sub(r'\s*\(\d+\)\s*$', '', artist_name)
        cleaned = re.sub(r'\s*\*\s*$', '', cleaned)
        cleaned = re.sub(r'\s*\/.*$', '', cleaned)
        
        return cleaned.strip()

    def perform_discogs_search(self, search_term):
        cache_key = f"search_{search_term}"
        
        if cache_key in self._search_cache:
            cache_entry = self._search_cache[cache_key]
            if time.time() - cache_entry['timestamp'] < 300:
                return cache_entry['results']
        
        with st.spinner(f"Searching Discogs for: {search_term}..."):
            try:
                format_selected = st.session_state.get('format_select', 'Vinyl')
                search_query = f"{search_term} {format_selected}"
                
                start_time = time.time()
                logger.info(f"SEARCH API CALL [START]: Discogs search for '{search_term}'")
                
                results = self.discogs_handler.get_simple_search_results(search_query)
                
                enhanced_results = []
                for result in results:
                    release_id = result.get('discogs_id')
                    if release_id:
                        pricing_data = self.discogs_handler.get_release_statistics_pricing(str(release_id))
                        if pricing_data and pricing_data.get('success'):
                            result['price_suggestions'] = pricing_data.get('price_suggestions', {})
                            result['has_pricing'] = True
                        else:
                            result['price_suggestions'] = {}
                            result['has_pricing'] = False
                    else:
                        result['price_suggestions'] = {}
                        result['has_pricing'] = False
                    
                    enhanced_results.append(result)
                
                duration = time.time() - start_time
                logger.info(f"SEARCH API CALL [END]: Discogs search for '{search_term}' - {duration:.3f}s - Found: {len(enhanced_results)} results")
                
                self._search_cache[cache_key] = {
                    'results': enhanced_results,
                    'timestamp': time.time()
                }
                
                if enhanced_results:
                    return enhanced_results
                else:
                    st.error(f"No results found for: {search_term}")
                    return []
                    
            except Exception as e:
                logger.error(f"Error searching Discogs: {str(e)}")
                st.error(f"Error searching Discogs: {str(e)}")
                return []

    def perform_database_search(self, search_term, user=None):
        try:
            start_time = time.time()
            logger.info(f"DB API CALL [START]: Search for '{search_term}'")
            
            user_role = user.get('role', 'consignor') if user else 'consignor'
            user_id = user.get('id') if user else None
            
            params = f"q={search_term}"
            
            if user_role == 'consignor' and user_id:
                params += f"&consignor_id={user_id}"
            
            response = requests.get(f"{self.base_url}/search?{params}", timeout=10)
            
            duration = time.time() - start_time
            logger.info(f"DB API CALL [END]: Search for '{search_term}' - {duration:.3f}s - Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    records = data.get('records', [])
                    
                    formatted_results = []
                    for record in records:
                        if isinstance(record, dict):
                            formatted_result = {
                                'type': 'database',
                                'id': record.get('id', ''),
                                'artist': record.get('artist', ''),
                                'title': record.get('title', ''),
                                'image_url': record.get('image_url', ''),
                                'barcode': record.get('barcode', ''),
                                'catalog_number': record.get('catalog_number', ''),
                                'store_price': record.get('store_price', ''),
                                'condition': record.get('condition', ''),
                                'genre': record.get('genre_name', record.get('genre', '')),
                                'youtube_url': record.get('youtube_url', ''),
                                'consignor_id': record.get('consignor_id', ''),
                                'consignor_name': record.get('consignor_name', ''),
                                'compilation': record.get('compilation', False),
                                'created_at': record.get('created_at', ''),
                                'status': record.get('status', 'active'),
                                'status_id': record.get('status_id', 2)
                            }
                        else:
                            record_dict = dict(record) if hasattr(record, '_asdict') else {}
                            formatted_result = {
                                'type': 'database',
                                'id': record_dict.get('id', ''),
                                'artist': record_dict.get('artist', ''),
                                'title': record_dict.get('title', ''),
                                'image_url': record_dict.get('image_url', ''),
                                'barcode': record_dict.get('barcode', ''),
                                'catalog_number': record_dict.get('catalog_number', ''),
                                'store_price': record_dict.get('store_price', ''),
                                'condition': record_dict.get('condition', ''),
                                'genre': record_dict.get('genre_name', record_dict.get('genre', '')),
                                'youtube_url': record_dict.get('youtube_url', ''),
                                'consignor_id': record_dict.get('consignor_id', ''),
                                'consignor_name': record_dict.get('consignor_name', ''),
                                'compilation': record_dict.get('compilation', False),
                                'created_at': record_dict.get('created_at', ''),
                                'status': record_dict.get('status', 'active'),
                                'status_id': record_dict.get('status_id', 2)
                            }
                        
                        formatted_results.append(formatted_result)
                    
                    return formatted_results
                else:
                    return []
            else:
                return []
            
        except Exception as e:
            logger.error(f"Error searching database: {str(e)}")
            st.error(f"Error searching database: {str(e)}")
            return []
        
    def _generate_filename(self, search_query, format_name):
        clean_query = re.sub(r'[^\w\s-]', '', search_query)
        clean_query = re.sub(r'[-\s]+', '_', clean_query)
        clean_format = re.sub(r'[^\w\s-]', '', format_name)
        clean_format = re.sub(r'[-\s]+', '_', clean_format)
        return f"batch_{clean_query}_{clean_format}".lower()
    
    def clear_cache(self):
        self._search_cache = {}