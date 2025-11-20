# FILE: inventory-manager/src/handlers/discogs_handler.py
import requests
import json
import re
import time
import streamlit as st
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter

class DiscogsHandler:
    def __init__(self, user_token: str):
        self.user_token = user_token
        self.base_url = "https://api.discogs.com"
        self.headers = {
            "User-Agent": "PigStyleInventory/1.0",
            "Authorization": f"Discogs token={self.user_token}"
        }
    
    def get_release_statistics_pricing(self, release_id: str, condition_grade: int = None):
        """Get pricing statistics for a release using marketplace price suggestions"""
        if condition_grade is None:
            # Default to condition 4 if not specified
            condition_grade = 4
        
        print(f"🔴 DEBUG get_release_statistics_pricing: release_id={release_id}, condition_grade={condition_grade}")
        
        # Use marketplace price suggestions endpoint
        return self._get_price_suggestions_pricing(release_id, condition_grade)
    
    def _get_price_suggestions_pricing(self, release_id: str, condition_grade: int):
        """Get pricing from Discogs marketplace price suggestions endpoint"""
        # FIXED: Use price_suggestions endpoint
        endpoint_url = f"{self.base_url}/marketplace/price_suggestions/{release_id}"
        
        # Log the API call
        api_title = f"💰 Discogs Price Suggestions API (GET): {endpoint_url}"
        start_time = time.time()
        self._log_api_call(api_title, {
            'endpoint': endpoint_url,
            'method': 'GET',
            'params': {},
            'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()}
        })

        try:
            response = requests.get(
                endpoint_url,
                headers=self.headers,
                timeout=15
            )
            
            duration = round(time.time() - start_time, 2)
            
            if response.status_code != 200:
                error_data = {'error': f'Status {response.status_code}', 'response_text': response.text}
                self._log_api_response(api_title, error_data, duration)
                return None
            
            data = response.json()
            
            # Log RAW DISCOGS PRICE SUGGESTIONS PAYLOAD
            self._log_api_response(api_title, data, duration)
            
            # Map condition grade to Discogs conditions
            condition_map = {
                5: "Mint (M)",
                4: "Very Good Plus (VG+)", 
                3: "Very Good (VG)",
                2: "Good Plus (G+)",
                1: "Good (G)"
            }
            
            target_condition = condition_map.get(condition_grade, "Very Good Plus (VG+)")
            
            # Extract pricing for the target condition
            if target_condition in data:
                price_data = data[target_condition]
                price_value = self._parse_price(price_data)
                
                if price_value:
                    return {
                        'discogs_lowest_price': price_value,
                        'discogs_median_price': price_value,  # Price suggestions are typically median estimates
                        'discogs_highest_price': price_value,
                        'discogs_listings_count': 0,  # Price suggestions don't include listing count
                        'success': True,
                        'condition_specific': True,
                        'condition_matched': target_condition
                    }
            
            return None
            
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            error_data = {'error': str(e)}
            self._log_api_response(api_title, error_data, duration)
            return None

    # ... KEEP ALL THE EXISTING METHODS BELOW EXACTLY AS THEY WERE ...
    # (search_multiple_results, get_release_data, _get_basic_release_info, 
    # get_simple_search_results, and all the helper methods)

    def search_multiple_results(self, query: str, filename_base: str = None):
        """Search Discogs and return multiple results for user selection"""
        endpoint_url = f"{self.base_url}/database/search"
        params = {
            'q': query,
            'type': 'release',
            'per_page': 50,
            'currency': 'USD'
        }
        
        # Log the API call with unified format
        api_title = f"🔍 Discogs Search API: {endpoint_url}"
        start_time = time.time()
        self._log_api_call(api_title, {
            'endpoint': endpoint_url,
            'params': params,
            'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()}
        })
        
        response = requests.get(
            endpoint_url,
            params=params,
            headers=self.headers,
            timeout=15
        )
        
        duration = round(time.time() - start_time, 2)
        
        if response.status_code != 200:
            error_msg = f"Discogs API returned status {response.status_code}: {response.text}"
            raise Exception(error_msg)
        
        data = response.json()
        
        # Log successful response - RAW DISCOGS PAYLOAD
        self._log_api_response(api_title, data, duration)
        
        return data

    def get_release_data(self, release_id: str, query: str, condition_grade: int):
        """Get release data including pricing information - NOW USES PRICE SUGGESTIONS"""
        if condition_grade is None:
            raise Exception("condition_grade parameter is required but was None")
        
        print(f"🔴 DEBUG get_release_data: release_id={release_id}, condition_grade={condition_grade}")
        
        # First try to get basic release info for images
        release_info = self._get_basic_release_info(release_id)
        image_url = release_info.get('image_url', '')
        
        # Use price suggestions for pricing
        pricing_data = self._get_price_suggestions_pricing(release_id, condition_grade)
        
        if pricing_data:
            # Use price suggestions data
            return {
                'discogs_lowest_price': pricing_data.get('discogs_lowest_price'),
                'discogs_estimated_price': pricing_data.get('discogs_median_price'),
                'image_url': image_url,
                'release_data': release_info.get('release_data', {}),
                'success': True,
                'condition_applied': True,
                'condition_specific': True,
                'discogs_listings_count': pricing_data.get('discogs_listings_count', 0)
            }
        else:
            # No pricing data available
            return {
                'discogs_lowest_price': None,
                'discogs_estimated_price': None,
                'image_url': image_url,
                'release_data': release_info.get('release_data', {}),
                'success': False,
                'condition_applied': True,
                'condition_specific': False,
                'discogs_listings_count': 0
            }

    def _get_basic_release_info(self, release_id: str):
        """Get basic release info for images and metadata"""
        endpoint_url = f"{self.base_url}/releases/{release_id}"
        
        # Log the API call
        api_title = f"📀 Discogs Release API: {endpoint_url}"
        start_time = time.time()
        self._log_api_call(api_title, {
            'endpoint': endpoint_url,
            'params': {},
            'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()}
        })

        response = requests.get(
            endpoint_url,
            headers=self.headers,
            timeout=10
        )
        
        duration = round(time.time() - start_time, 2)
        
        if response.status_code == 200:
            release_data = response.json()
            # Log the response
            self._log_api_response(api_title, release_data, duration)
            
            image_url = self._extract_image_from_release(release_data)
            return {
                'image_url': image_url,
                'release_data': release_data
            }
        else:
            # Log error response
            self._log_api_response(api_title, {'error': f'Status {response.status_code}', 'response_text': response.text}, duration)
            return {'image_url': '', 'release_data': {}}

    def get_simple_search_results(self, query: str, filename_base: str = None):
        """Get simple search results with basic info - NO EXTRA API CALLS"""
        endpoint_url = f"{self.base_url}/database/search"
        params = {
            'q': query,
            'type': 'release',
            'per_page': 50,
            'currency': 'USD'
        }
        
        # Log the API call with unified format
        api_title = f"🔍 Discogs Simple Search API: {endpoint_url}?q={query}"
        start_time = time.time()
        self._log_api_call(api_title, {
            'endpoint': endpoint_url,
            'params': params,
            'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()}
        })

        response = requests.get(
            endpoint_url,
            params=params,
            headers=self.headers,
            timeout=15
        )
        
        duration = round(time.time() - start_time, 2)
        
        if response.status_code != 200:
            error_msg = f"Discogs API returned status {response.status_code}: {response.text}"
            raise Exception(error_msg)
        
        search_data = response.json()
        
        # Log RAW DISCOGS SEARCH PAYLOAD
        self._log_api_response(api_title, search_data, duration)
        
        # Process results - just basic info, no pricing calls
        formatted_results = []
        for result in search_data.get('results', []):
            artist = self._extract_artist_from_result(result)
            title = self._extract_title_from_result(result)
            image_url = self._extract_image_from_result(result)
            catalog_number = self._extract_catalog_number(result)
            release_id = result.get('id')
            
            formatted_result = {
                'type': 'discogs',
                'artist': artist,
                'title': title,
                'image_url': image_url,
                'catalog_number': catalog_number,
                'discogs_id': release_id,
                # Note: No pricing data here - that will be fetched later when user selects a record
            }
            formatted_results.append(formatted_result)
        
        return formatted_results

    # ... KEEP ALL THE EXISTING HELPER METHODS EXACTLY AS THEY WERE ...

    def _extract_image_from_release(self, release_data):
        """Extract image URL from release data"""
        image_fields = [
            release_data.get('images', [{}])[0].get('uri'),
            release_data.get('images', [{}])[0].get('uri150'),
            release_data.get('thumb'),
            release_data.get('cover_image')
        ]
        
        for image_field in image_fields:
            if image_field and isinstance(image_field, str) and image_field.startswith('http'):
                return image_field
        
        return ""

    def _extract_image_from_result(self, result):
        """Extract image URL from search result"""
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
    
    def _create_no_results_response(self, query: str):
        """Create response when no pricing data is found"""
        return {
            'discogs_lowest_price': None,
            'discogs_estimated_price': None,
            'success': False,
            'error': 'No pricing data found'
        }
    
    def _parse_price(self, price_data):
        """Parse price from Discogs listing data"""
        if not price_data:
            return None
        
        # Handle different price formats from Discogs API
        if isinstance(price_data, (int, float)):
            price_float = float(price_data)
            if 0.1 <= price_float <= 10000:
                return round(price_float, 2)
            return None
        
        if isinstance(price_data, dict):
            # Try different keys that might contain the price
            for key in ['value', 'amount', 'price']:
                if key in price_data:
                    return self._parse_price(price_data[key])
            return None
        
        if isinstance(price_data, str):
            # Clean string price
            cleaned = re.sub(r'[^\d.,]', '', str(price_data))
            
            if not cleaned:
                return None
            
            if ',' in cleaned and '.' in cleaned:
                cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                parts = cleaned.split(',')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    cleaned = cleaned.replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            
            cleaned = re.sub(r'[^\d.]', '', cleaned)
            
            if cleaned:
                price_float = float(cleaned)
                if 0.1 <= price_float <= 10000:
                    return round(price_float, 2)
        
        return None
    
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

    def _save_payload(self, filename, data):
        """Save payload data to JSON file"""
        payloads_folder = Path("payloads")
        payloads_folder.mkdir(parents=True, exist_ok=True)
        file_path = payloads_folder / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _log_api_call(self, title, request_data):
        """Log API call in unified format"""
        if 'api_logs' not in st.session_state:
            st.session_state.api_logs = []
        if 'api_details' not in st.session_state:
            st.session_state.api_details = {}
            
        st.session_state.api_logs.append(title)
        st.session_state.api_details[title] = {
            'request': request_data,
            'raw_request': request_data  # Store raw request data
        }

    def _log_api_response(self, title, response_data, duration):
        """Log API response in unified format - RAW PAYLOADS ONLY"""
        if 'api_details' in st.session_state and title in st.session_state.api_details:
            st.session_state.api_details[title]['response'] = response_data
            st.session_state.api_details[title]['duration'] = duration
            st.session_state.api_details[title]['raw_response'] = response_data  # Store raw response data