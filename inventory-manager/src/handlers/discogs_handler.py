import requests
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

class DiscogsHandler:
    def __init__(self, user_token: str, debug_tab=None):
        self.user_token = user_token
        self.base_url = "https://api.discogs.com"
        self.headers = {
            "User-Agent": "PigStyleInventory/1.0",
            "Authorization": f"Discogs token={self.user_token}"
        }
        self.debug_tab = debug_tab
    
    def _log_debug(self, category, message, data=None):
        """Log to debug tab if available"""
        if self.debug_tab:
            self.debug_tab.add_log(category, message, data)
    
    def search_multiple_results(self, query: str, filename_base: str = None):
        """Search Discogs and return multiple results for user selection"""
        endpoint_url = f"{self.base_url}/database/search"
        params = {
            'q': query,
            'type': 'release',
            'per_page': 50,
            'currency': 'USD'
        }
        
        self._log_debug("DISCOGS_SEARCH", f"{endpoint_url} - {query}", {
            'endpoint': endpoint_url,
            'request': {
                'params': params,
                'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()}
            }
        })
        
        response = requests.get(
            endpoint_url,
            params=params,
            headers=self.headers,
            timeout=15
        )
        
        if response.status_code != 200:
            error_msg = f"Discogs API returned status {response.status_code}: {response.text}"
            self._log_debug("DISCOGS_ERROR", f"{endpoint_url} - {query} - {error_msg}")
            raise Exception(error_msg)
        
        data = response.json()
        
        self._log_debug("DISCOGS_SEARCH_SUCCESS", f"{endpoint_url} - {query} - {len(data.get('results', []))} results", {
            'endpoint': endpoint_url,
            'request': {
                'params': params,
                'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()}
            },
            'response': {
                'status_code': response.status_code,
                'result_count': len(data.get('results', [])),
                'results_sample': data.get('results', [])[:2] if data.get('results') else []
            }
        })
        
        return data
    
    def get_release_pricing(self, release_id: str, query: str, filename_base: str = None):
        """Get pricing information for a specific release"""
        endpoint_url = f"{self.base_url}/marketplace/listings"
        params = {
            'release_id': release_id,
            'per_page': 100,
            'currency': 'USD'
        }
        
        self._log_debug("DISCOGS_PRICING", f"{endpoint_url} - Release {release_id}", {
            'endpoint': endpoint_url,
            'request': {
                'params': params,
                'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()}
            }
        })

        response = requests.get(
            endpoint_url,
            params=params,
            headers=self.headers,
            timeout=15
        )
        
        if response.status_code != 200:
            self._log_debug("DISCOGS_PRICING_ERROR", f"{endpoint_url} - Release {release_id} - Status {response.status_code}")
            
            release_data = self._get_release_stats(release_id)
            if not release_data:
                self._log_debug("DISCOGS_ERROR", f"No release data found for {release_id}")
                return self._create_no_results_response(0, query)
            
            price = self._extract_price_from_release(release_data)
            image_url = self._extract_image_from_release(release_data)
            
            if price is not None:
                result = self._calculate_pricing_stats([price], 1, 1, query, 'release_stats')
                result['image_url'] = image_url
                result['release_data'] = release_data
                self._log_debug("DISCOGS_PRICING_FALLBACK", f"{endpoint_url} - Release {release_id} - Using release stats: ${price}")
                return result
            else:
                result = self._create_no_results_response(1, query)
                result['image_url'] = image_url
                result['release_data'] = release_data
                self._log_debug("DISCOGS_PRICING_NO_DATA", f"{endpoint_url} - Release {release_id} - No pricing data found")
                return result
        
        listings_data = response.json()
        
        prices = []
        for listing in listings_data.get('listings', []):
            price_str = listing.get('price', {}).get('value')
            if price_str:
                price = self._parse_price(price_str)
                if price is not None:
                    prices.append(price)
        
        release_data = self._get_release_stats(release_id)
        image_url = self._extract_image_from_release(release_data)
        
        if prices:
            result = self._calculate_pricing_stats(prices, len(prices), len(listings_data.get('listings', [])), query, 'marketplace')
            result['image_url'] = image_url
            result['release_data'] = release_data
            self._log_debug("DISCOGS_PRICING_SUCCESS", f"{endpoint_url} - Release {release_id} - ${result['median_price']} median from {len(prices)} prices", {
                'endpoint': endpoint_url,
                'request': {
                    'params': params,
                    'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()}
                },
                'response': {
                    'status_code': response.status_code,
                    'listings_count': len(listings_data.get('listings', [])),
                    'prices_found': len(prices),
                    'pricing_result': result
                }
            })
            return result
        else:
            price = self._extract_price_from_release(release_data)
            if price is not None:
                result = self._calculate_pricing_stats([price], 1, 1, query, 'release_stats')
                result['image_url'] = image_url
                result['release_data'] = release_data
                self._log_debug("DISCOGS_PRICING_FALLBACK", f"{endpoint_url} - Release {release_id} - Using release stats fallback: ${price}")
                return result
            else:
                result = self._create_no_results_response(len(listings_data.get('listings', [])), query)
                result['image_url'] = image_url
                result['release_data'] = release_data
                self._log_debug("DISCOGS_PRICING_NO_DATA", f"{endpoint_url} - Release {release_id} - No pricing data available")
                return result

    def _get_release_stats(self, release_id: str):
        """Get release statistics from Discogs API"""
        endpoint_url = f"{self.base_url}/releases/{release_id}"
        
        self._log_debug("DISCOGS_RELEASE", f"{endpoint_url} - Release {release_id}", {
            'endpoint': endpoint_url,
            'request': {
                'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()}
            }
        })
        
        response = requests.get(
            endpoint_url,
            headers=self.headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            self._log_debug("DISCOGS_RELEASE_SUCCESS", f"{endpoint_url} - Release {release_id}", {
                'endpoint': endpoint_url,
                'request': {
                    'headers': {k: '***' if 'Authorization' in k else v for k, v in self.headers.items()}
                },
                'response': {
                    'status_code': response.status_code,
                    'release_data_keys': list(data.keys()) if data else []
                }
            })
            return data
        else:
            error_msg = f"Failed to get release {release_id}: {response.status_code}"
            self._log_debug("DISCOGS_RELEASE_ERROR", f"{endpoint_url} - Release {release_id} - {error_msg}")
            raise Exception(error_msg)
    
    def _extract_price_from_release(self, release_data):
        """Extract price from release data"""
        price_fields = [
            release_data.get('lowest_price'),
            release_data.get('estimated_price'),
        ]
        
        for price_str in price_fields:
            if price_str:
                price = self._parse_price(price_str)
                if price is not None:
                    return price
        
        return None
    
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
    
    def _calculate_pricing_stats(self, prices, listings_with_prices: int, total_results: int, query: str, search_type: str):
        """Calculate pricing statistics from price list"""
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        
        if n % 2 == 1:
            median = sorted_prices[n//2]
        else:
            median = (sorted_prices[n//2 - 1] + sorted_prices[n//2]) / 2
        
        return {
            'median_price': round(median, 2),
            'lowest_price': min(prices),
            'highest_price': max(prices),
            'url': self._generate_marketplace_url(query),
            'currency': 'USD',
            'listings_with_prices': listings_with_prices,
            'prices_found': len(prices),
            'search_type': search_type,
            'success': True
        }
    
    def _create_no_results_response(self, total_results: int, query: str):
        """Create response when no pricing data is found"""
        return {
            'median_price': None,
            'lowest_price': None,
            'highest_price': None,
            'url': self._generate_marketplace_url(query),
            'listings_with_prices': 0,
            'prices_found': 0,
            'search_type': 'no_prices',
            'success': False,
            'error': 'No pricing data found'
        }
    
    def _parse_price(self, price_str):
        """Parse price string to float"""
        if not price_str:
            return None
        
        cleaned = re.sub(r'[^\d.,]', '', str(price_str))
        
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
    
    def _generate_marketplace_url(self, query: str):
        """Generate Discogs marketplace URL for the query"""
        encoded_query = requests.utils.quote(query)
        return f"https://www.discogs.com/sell/list?q={encoded_query}&currency=USD"
    
    def _save_payload(self, filename, data):
        """Save payload data to JSON file"""
        payloads_folder = Path("payloads")
        payloads_folder.mkdir(parents=True, exist_ok=True)
        file_path = payloads_folder / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)