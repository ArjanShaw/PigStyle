import requests
import json
import re
import time
import streamlit as st
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter
from conditions import DiscogsConditions  # Added import

class DiscogsHandler:
    def __init__(self, user_token: str):
        self.user_token = user_token
        self.base_url = "https://api.discogs.com"
        self.headers = {
            "User-Agent": "PigStyleInventory/1.0",
            "Authorization": f"Discogs token={self.user_token}"
        }
    
    def get_release_statistics_pricing(self, release_id: str):
        """Get pricing data with timing measurement"""
        endpoint_url = f"{self.base_url}/marketplace/price_suggestions/{release_id}"
        
        start_time = time.time()  # START TIMING
        
        response = requests.get(
            endpoint_url,
            headers=self.headers,
            timeout=15
        )
        
        duration = time.time() - start_time  # END TIMING
        
        print(f"Discogs Price Suggestions ({release_id}) took {duration:.2f}s")

        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        price_suggestions = {}
        for condition, price_data in data.items():
            price_value = self._parse_price_from_suggestion(price_data)
            if price_value:
                price_suggestions[condition] = price_value
        
        return {
            'price_suggestions': price_suggestions,
            'success': True,
            'total_conditions': len(price_suggestions)
        }

    def _parse_price_from_suggestion(self, price_data):
        if not price_data:
            return None
        
        if isinstance(price_data, dict):
            if 'value' in price_data:
                price_float = float(price_data['value'])
                if 0.1 <= price_float <= 10000:
                    return round(price_float, 2)
        
        return self._parse_price(price_data)

    def search_multiple_results(self, query: str, filename_base: str = None):
        """Search with timing measurement"""
        endpoint_url = f"{self.base_url}/database/search"
        params = {
            'q': query,
            'type': 'release',
            'per_page': 50,
            'currency': 'USD'
        }
        
        start_time = time.time()  # START TIMING
        
        response = requests.get(
            endpoint_url,
            params=params,
            headers=self.headers,
            timeout=15
        )
        
        duration = time.time() - start_time  # END TIMING
        
        print(f"Discogs Search: {query[:30]}... took {duration:.2f}s")
        
        if response.status_code != 200:
            error_msg = f"Discogs API returned status {response.status_code}: {response.text}"
            raise Exception(error_msg)
        
        data = response.json()
        
        return data

    def get_release_data(self, release_id: str, query: str):
        """Get release data with timing measurement"""
        release_info = self._get_basic_release_info(release_id)
        image_url = release_info.get('image_url', '')
        
        pricing_data = self.get_release_statistics_pricing(release_id)
        
        if pricing_data:
            return {
                'price_suggestions': pricing_data.get('price_suggestions', {}),
                'image_url': image_url,
                'release_data': release_info.get('release_data', {}),
                'success': True,
                'total_conditions': pricing_data.get('total_conditions', 0)
            }
        else:
            return {
                'price_suggestions': {},
                'image_url': image_url,
                'release_data': release_info.get('release_data', {}),
                'success': False
            }

    def _get_basic_release_info(self, release_id: str):
        """Get basic release info with timing measurement"""
        endpoint_url = f"{self.base_url}/releases/{release_id}"

        start_time = time.time()  # START TIMING
        
        response = requests.get(
            endpoint_url,
            headers=self.headers,
            timeout=10
        )
        
        duration = time.time() - start_time  # END TIMING
        
        print(f"Discogs Release Info ({release_id}) took {duration:.2f}s")
        
        if response.status_code == 200:
            release_data = response.json()
            
            image_url = self._extract_image_from_release(release_data)
            return {
                'image_url': image_url,
                'release_data': release_data
            }
        else:
            return {'image_url': '', 'release_data': {}}

    def get_release_tracklist(self, release_id: str):
        """Get tracklist with timing measurement"""
        endpoint_url = f"{self.base_url}/releases/{release_id}"

        start_time = time.time()  # START TIMING
        
        response = requests.get(
            endpoint_url,
            headers=self.headers,
            timeout=10
        )
        
        duration = time.time() - start_time  # END TIMING
        
        print(f"Discogs Tracklist ({release_id}) took {duration:.2f}s")
        
        if response.status_code == 200:
            release_data = response.json()
            
            tracklist = release_data.get('tracklist', [])
            track_titles = []
            
            for track in tracklist:
                if track.get('type') == 'track':
                    title = track.get('title', '').strip()
                    if title and title not in track_titles:
                        track_titles.append(title)
            
            return track_titles
        else:
            return []

    def get_simple_search_results(self, query: str, filename_base: str = None):
        """Get simple search results with timing measurement"""
        endpoint_url = f"{self.base_url}/database/search"
        params = {
            'q': query,
            'type': 'release',
            'per_page': 50,
            'currency': 'USD'
        }

        start_time = time.time()  # START TIMING
        
        response = requests.get(
            endpoint_url,
            params=params,
            headers=self.headers,
            timeout=15
        )
        
        duration = time.time() - start_time  # END TIMING
        
        print(f"Discogs Simple Search: {query[:30]}... took {duration:.2f}s")
        
        if response.status_code != 200:
            error_msg = f"Discogs API returned status {response.status_code}: {response.text}"
            raise Exception(error_msg)
        
        search_data = response.json()
        
        formatted_results = []
        seen_masters = set()
        
        for result in search_data.get('results', []):
            master_id = result.get('master_id')
            
            if master_id and master_id in seen_masters:
                continue
                
            if master_id:
                seen_masters.add(master_id)
            
            artist = self._extract_artist_from_result(result)
            title = self._extract_title_from_result(result)
            image_url = self._extract_image_from_result(result)
            catalog_number = self._extract_catalog_number(result)
            release_id = result.get('id')
            year = result.get('year', '')
            format_info = self._extract_format_info(result)
            # REMOVED: label_info = self._extract_label_info(result)
            country = result.get('country', '')
            genre = self._extract_genre_from_result(result)
            
            formatted_result = {
                'type': 'discogs',
                'artist': artist,
                'title': title,
                'image_url': image_url,
                'catalog_number': catalog_number,
                'discogs_id': release_id,
                'year': year,
                'format': format_info,
                # REMOVED: 'label': label_info,
                'country': country,
                'master_id': master_id,
                'genre': genre,
            }
            formatted_results.append(formatted_result)
        
        return formatted_results

    def _extract_genre_from_result(self, result):
        if not isinstance(result, dict):
            return ""
        
        genres = result.get('genre', [])
        if genres and isinstance(genres, list) and len(genres) > 0:
            return genres[0]
        
        styles = result.get('style', [])
        if styles and isinstance(styles, list) and len(styles) > 0:
            return styles[0]
                
        return ""

    def _extract_image_from_release(self, release_data):
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
        return {
            'price_suggestions': {},
            'success': False,
            'error': 'No pricing data found'
        }
    
    def _parse_price(self, price_data):
        if not price_data:
            return None
        
        if isinstance(price_data, (int, float)):
            price_float = float(price_data)
            if 0.1 <= price_float <= 10000:
                return round(price_float, 2)
            return None
        
        if isinstance(price_data, dict):
            for key in ['value', 'amount', 'price']:
                if key in price_data:
                    return self._parse_price(price_data[key])
            return None
        
        if isinstance(price_data, str):
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
        if isinstance(result, dict):
            if result.get('title'):
                title_text = result['title']
                if ' - ' in title_text:
                    parts = title_text.split(' - ', 1)
                    return parts[1].strip()
                return title_text
        return 'Unknown Title'

    def _extract_catalog_number(self, result):
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

    def _extract_format_info(self, result):
        if not isinstance(result, dict):
            return ''
            
        format_list = result.get('format', [])
        if isinstance(format_list, list):
            return ', '.join([str(f) for f in format_list])
        elif isinstance(format_list, str):
            return format_list
        return ''

    # REMOVED: _extract_label_info method completely
    # def _extract_label_info(self, result):
    #     if not isinstance(result, dict):
    #         return ''
    #     
    #     label_list = result.get('label', [])
    #     if isinstance(label_list, list):
    #         labels = []
    #         for label in label_list:
    #             if isinstance(label, str):
    #                 labels.append(label)
    #             elif isinstance(label, dict) and label.get('name'):
    #                 labels.append(label['name'])
    #         return ', '.join(labels)
    #     elif isinstance(label_list, str):
    #         return label_list
    #     return ''

    def _save_payload(self, filename, data):
        payloads_folder = Path("payloads")
        payloads_folder.mkdir(parents=True, exist_ok=True)
        file_path = payloads_folder / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)