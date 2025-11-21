import streamlit as st
import requests
import time
import re
import json
from pathlib import Path

class EbayHandler:
    EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    EBAY_ITEM_URL = "https://api.ebay.com/buy/browse/v1/item/"

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expiry = 0

    def get_access_token(self):
        if self.token and time.time() < self.token_expiry:
            return self.token

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}

        # Log token API call
        api_title = f"🔑 eBay Token API: {self.EBAY_TOKEN_URL}"
        start_time = time.time()
        self._log_api_call(api_title, {
            'endpoint': self.EBAY_TOKEN_URL,
            'request': {
                'headers': headers,
                'data': data
            }
        })
        
        resp = requests.post(self.EBAY_TOKEN_URL, headers=headers, data=data, auth=(self.client_id, self.client_secret))
        resp.raise_for_status()
        token_data = resp.json()
        self.token = token_data["access_token"]
        self.token_expiry = time.time() + token_data["expires_in"] - 60
        
        duration = round(time.time() - start_time, 2)
        
        # Log token response
        self._log_api_response(api_title, token_data, duration)
        
        return self.token

    def get_ebay_pricing(self, artist, title, discogs_condition=None, category_id="176985", exclude_foreign=True):
        """Get eBay pricing for a record with condition mapping from Discogs"""
        if not self.get_access_token():
            return None

        headers = {"Authorization": f"Bearer {self.token}"}
        query = f"{artist} {title}".strip()
        
        # Don't filter by condition - we want all conditions to scan for Discogs terms
        params = {
            "q": query, 
            "limit": 50, 
            "category_ids": category_id,
            "fieldgroups": "EXTENDED"  # Get more detailed info including shipping
        }

        # Log search API call with unified format
        api_title = f"🛒 eBay Search API: {self.EBAY_SEARCH_URL}?q={query}"
        start_time = time.time()
        self._log_api_call(api_title, {
            'endpoint': self.EBAY_SEARCH_URL,
            'request': {
                'params': params,
                'headers': {k: '***' if 'Authorization' in k else v for k, v in headers.items()}
            }
        })

        resp = requests.get(self.EBAY_SEARCH_URL, headers=headers, params=params, timeout=15)
        
        # Handle API errors gracefully
        if resp.status_code != 200:
            duration = round(time.time() - start_time, 2)
            error_data = {
                'error': f'Status {resp.status_code}',
                'response_text': resp.text
            }
            self._log_api_response(api_title, error_data, duration)
            return None
            
        data = resp.json()

        duration = round(time.time() - start_time, 2)

        # Log the ACTUAL raw response from eBay - no wrapper, just the raw JSON
        self._log_api_response(api_title, data, duration)

        items = data.get("itemSummaries", [])
        
        # Group listings by detected Discogs condition
        condition_groups = {}
        
        # Get shipping cost from config for CALC items
        shipping_cost = st.session_state.db_manager.get_config_value('SHIPPING_COST', '5.72')
        try:
            shipping_cost = float(shipping_cost)
        except (ValueError, TypeError):
            shipping_cost = 5.72
        
        for item in items:
            if exclude_foreign:
                marketplace_id = item.get("listingMarketplaceId")
                if marketplace_id and marketplace_id != "EBAY_US":
                    continue

            price_data = item.get("price", {})
            if "value" in price_data:
                base_price = float(price_data["value"])
                
                # Extract shipping cost from the item data
                shipping_info = self._extract_shipping_info(item)
                shipping_type = shipping_info['type']
                shipping_cost_value = shipping_info['cost']
                
                # Calculate total cost (base + shipping)
                if shipping_type == 'CALC':
                    total_cost = base_price + shipping_cost
                elif shipping_cost_value is not None:
                    total_cost = base_price + shipping_cost_value
                else:
                    total_cost = base_price  # For FREE shipping
                
                item_url = item.get("itemWebUrl", "")
                item_id = item.get("itemId", "")
                
                # Detect Discogs condition from title and description
                detected_condition = self._detect_discogs_condition(item)
                
                listing_data = {
                    'base_price': base_price,
                    'shipping_type': shipping_type,
                    'shipping_cost': shipping_cost_value,
                    'total_cost': total_cost,
                    'item_url': item_url,
                    'item_id': item_id,
                    'item_data': item  # Store full item data for later use
                }
                
                # Add to condition group
                if detected_condition not in condition_groups:
                    condition_groups[detected_condition] = []
                condition_groups[detected_condition].append(listing_data)

        # Calculate pricing statistics for each condition group
        condition_pricing = {}
        for condition, listings in condition_groups.items():
            if listings:
                base_prices = [listing['base_price'] for listing in listings]
                total_costs = [listing['total_cost'] for listing in listings]
                
                # Sort for median calculation
                base_prices.sort()
                total_costs.sort()
                
                n = len(base_prices)
                
                # Calculate median base price
                if n % 2 == 1:
                    median_base = base_prices[n//2]
                else:
                    median_base = (base_prices[n//2 - 1] + base_prices[n//2]) / 2
                
                # Calculate median total cost
                if n % 2 == 1:
                    median_total = total_costs[n//2]
                else:
                    median_total = (total_costs[n//2 - 1] + total_costs[n//2]) / 2
                
                # Find cheapest listing in this condition group
                cheapest_listing = min(listings, key=lambda x: x['total_cost'])
                
                condition_pricing[condition] = {
                    'count': len(listings),
                    'lowest_price': round(cheapest_listing['base_price'], 2),
                    'median_price': round(median_base, 2),
                    'highest_price': round(max(base_prices), 2),
                    'lowest_total': round(cheapest_listing['total_cost'], 2),
                    'median_total': round(median_total, 2),
                    'lowest_shipping': round(cheapest_listing['shipping_cost'] or 0, 2),
                    'cheapest_item_url': cheapest_listing['item_url'],
                    'cheapest_item_id': cheapest_listing['item_id'],
                    'listings': listings
                }

        # Get overall cheapest listing across all conditions
        all_listings = []
        for listings in condition_groups.values():
            all_listings.extend(listings)
        
        overall_cheapest = None
        if all_listings:
            overall_cheapest = min(all_listings, key=lambda x: x['total_cost'])
            overall_cheapest_details = self.get_item_details(overall_cheapest['item_id']) if overall_cheapest['item_id'] else None
        else:
            overall_cheapest_details = None

        result = {
            'condition_pricing': condition_pricing,
            'total_items_found': len(items),
            'overall_cheapest_url': overall_cheapest['item_url'] if overall_cheapest else None,
            'overall_cheapest_details': overall_cheapest_details,
            'search_url': f"https://www.ebay.com/sch/i.html?_nkw={requests.utils.quote(query)}"
        }
        
        return result

    def _detect_discogs_condition(self, item):
        """Detect Discogs condition from eBay item title and description"""
        # Get text to scan
        title = item.get('title', '').lower()
        
        # Try to get description if available
        description = ''
        if 'legacy' in item:
            description = item.get('legacy', {}).get('itemDescription', '').lower()
        
        # Combine text for scanning
        text_to_scan = f"{title} {description}"
        
        # Discogs condition patterns - both full names and abbreviations
        condition_patterns = {
            'Mint (M)': [r'\bmint\b', r'\bm\b', r'\bstill sealed\b', r'\bsealed\b'],
            'Near Mint (NM or M-)': [r'\bnear mint\b', r'\bnm\b', r'\bm-\b', r'\bm\s*-\s*'],
            'Very Good Plus (VG+)': [r'\bvery good plus\b', r'\bvg\+\b', r'\bvg\s*\+\s*'],
            'Very Good (VG)': [r'\bvery good\b', r'\bvg\b'],
            'Good Plus (G+)': [r'\bgood plus\b', r'\bg\+\b', r'\bg\s*\+\s*'],
            'Good (G)': [r'\bgood\b', r'\bg\b'],
            'Fair (F)': [r'\bfair\b', r'\bf\b'],
            'Poor (P)': [r'\bpoor\b', r'\bp\b']
        }
        
        # Check each condition pattern
        for condition, patterns in condition_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_to_scan, re.IGNORECASE):
                    return condition
        
        # Default to "Generic" if no condition detected
        return "Generic"

    def _extract_shipping_info(self, item):
        """Extract shipping information from eBay item data"""
        try:
            # Try to get shipping cost from shippingOptions first
            shipping_options = item.get('shippingOptions', [])
            if shipping_options:
                for option in shipping_options:
                    shipping_cost_type = option.get('shippingCostType', '')
                    if shipping_cost_type == 'CALCULATED':
                        return {'type': 'CALC', 'cost': None}
                    elif shipping_cost_type == 'FIXED':
                        shipping_cost = option.get('shippingCost', {})
                        if 'value' in shipping_cost:
                            cost = float(shipping_cost['value'])
                            return {'type': 'FIXED', 'cost': cost}
            
            # If no shipping options, check for calculated shipping
            shipping_cost_summary = item.get('shippingCostSummary', {})
            if shipping_cost_summary:
                shipping_cost_type = shipping_cost_summary.get('shippingCostType', '')
                if shipping_cost_type == 'CALCULATED':
                    return {'type': 'CALC', 'cost': None}
                elif shipping_cost_type == 'FIXED':
                    shipping_cost = shipping_cost_summary.get('shippingCost', {})
                    if 'value' in shipping_cost:
                        cost = float(shipping_cost['value'])
                        return {'type': 'FIXED', 'cost': cost}
            
            # Check for fixed shipping cost
            if 'shippingCostFixed' in item:
                cost = float(item['shippingCostFixed'])
                return {'type': 'FIXED', 'cost': cost}
            
            # If no shipping cost found, assume free shipping
            return {'type': 'FREE', 'cost': 0}
                
        except Exception as e:
            return {'type': 'FREE', 'cost': 0}

    def get_item_details(self, item_id):
        """Get detailed information for a specific eBay item"""
        if not self.get_access_token():
            return None

        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.EBAY_ITEM_URL}{item_id}"

        # Log item API call
        api_title = f"📦 eBay Item API: {url}"
        start_time = time.time()
        self._log_api_call(api_title, {
            'endpoint': url,
            'request': {
                'headers': {k: '***' if 'Authorization' in k else v for k, v in headers.items()}
            }
        })

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            item_data = resp.json()
            
            duration = round(time.time() - start_time, 2)
            
            # Log successful response - raw eBay data
            self._log_api_response(api_title, item_data, duration)
            
            return item_data
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            # Log error response
            self._log_api_response(api_title, {
                'status_code': resp.status_code if 'resp' in locals() else 'No response',
                'error': str(e)
            }, duration)
            return None

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
        """Log API response in unified format"""
        if 'api_details' in st.session_state and title in st.session_state.api_details:
            st.session_state.api_details[title]['response'] = response_data
            st.session_state.api_details[title]['duration'] = duration
            st.session_state.api_details[title]['raw_response'] = response_data  # Store raw response data