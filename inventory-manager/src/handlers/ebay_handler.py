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
        
        # Map Discogs condition to eBay condition IDs
        condition_ids = self._map_discogs_to_ebay_condition(discogs_condition)
        
        params = {
            "q": query, 
            "limit": 50, 
            "category_ids": category_id,
            "fieldgroups": "EXTENDED"  # Get more detailed info including shipping
        }
        
        # Add condition filter if we have valid condition IDs
        if condition_ids:
            # Use the correct filter format: conditionIds:{1000|3000}
            params["filter"] = f"conditionIds:{{{'|'.join(condition_ids)}}}"

        # Log search API call with unified format
        api_title = f"🛒 eBay Search API: {self.EBAY_SEARCH_URL}?q={query}"
        if discogs_condition:
            api_title += f"&condition={discogs_condition}"
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
        
        listings = []
        cheapest_item_url = None
        cheapest_item_id = None
        
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
                
                listings.append({
                    'base_price': base_price,
                    'shipping_type': shipping_type,
                    'shipping_cost': shipping_cost_value,
                    'total_cost': total_cost,
                    'item_url': item_url,
                    'item_id': item_id,
                    'item_data': item  # Store full item data for later use
                })

        if listings:
            # Sort by total cost to find the cheapest listing
            listings.sort(key=lambda x: x['total_cost'])
            cheapest_listing = listings[0]
            cheapest_item_url = cheapest_listing['item_url']
            cheapest_item_id = cheapest_listing['item_id']
            
            # Get detailed item information for the cheapest listing
            cheapest_item_details = self.get_item_details(cheapest_item_id) if cheapest_item_id else None
            
            # Calculate median base price
            base_prices = [listing['base_price'] for listing in listings]
            base_prices.sort()
            n = len(base_prices)
            if n % 2 == 1:
                median_base = base_prices[n//2]
            else:
                median_base = (base_prices[n//2 - 1] + base_prices[n//2]) / 2
            
            # Calculate median total cost
            total_costs = [listing['total_cost'] for listing in listings]
            total_costs.sort()
            if n % 2 == 1:
                median_total = total_costs[n//2]
            else:
                median_total = (total_costs[n//2 - 1] + total_costs[n//2]) / 2

            result = {
                'ebay_median_price': round(median_base, 2),
                'ebay_lowest_price': round(cheapest_listing['base_price'], 2),  # Base price from cheapest total listing
                'ebay_highest_price': max(base_prices),
                'ebay_listings_count': len(listings),
                'ebay_total_items_found': len(items),  # Add total items found count
                'ebay_low_shipping': round(cheapest_listing['shipping_cost'] or 0, 2),
                'ebay_low_total': round(cheapest_listing['total_cost'], 2),
                'ebay_search_url': f"https://www.ebay.com/sch/i.html?_nkw={requests.utils.quote(query)}",
                'ebay_lowest_item_url': cheapest_item_url,  # URL of the actual cheapest item
                'ebay_lowest_item_id': cheapest_item_id,  # ID of the cheapest item
                'ebay_lowest_item_details': cheapest_item_details,  # Detailed info for cheapest item
                'ebay_condition_filter': discogs_condition,
                'ebay_condition_ids': condition_ids
            }
            
            return result
        else:
            return {
                'ebay_median_price': None,
                'ebay_lowest_price': None,
                'ebay_highest_price': None,
                'ebay_listings_count': 0,
                'ebay_total_items_found': len(items),  # Add total items found count even when no valid listings
                'ebay_low_shipping': None,
                'ebay_low_total': None,
                'ebay_search_url': f"https://www.ebay.com/sch/i.html?_nkw={requests.utils.quote(query)}",
                'ebay_lowest_item_url': None,
                'ebay_lowest_item_id': None,
                'ebay_lowest_item_details': None,
                'ebay_condition_filter': discogs_condition,
                'ebay_condition_ids': condition_ids
            }

    def _map_discogs_to_ebay_condition(self, discogs_condition):
        """Map Discogs condition to eBay condition IDs"""
        if not discogs_condition:
            return ["3000"]  # Default to Used
        
        condition_lower = discogs_condition.lower()
        
        # Mint/Near Mint → 1000 (New) or 3000 (Used - Very Good)
        if any(term in condition_lower for term in ['mint', 'near mint', 'nm']):
            return ["1000", "3000"]
        
        # Very Good Plus/Good Plus → 3000 (Used)
        elif any(term in condition_lower for term in ['very good plus', 'vg+', 'good plus', 'g+']):
            return ["3000"]
        
        # Very Good/Good → 3000 (Used)
        elif any(term in condition_lower for term in ['very good', 'vg', 'good', 'g']):
            return ["3000"]
        
        # Lower grades → 3000 (Used)
        elif any(term in condition_lower for term in ['fair', 'poor', 'f', 'p']):
            return ["3000"]
        
        # Generic/Not Graded → 3000 (Used)
        else:
            return ["3000"]

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