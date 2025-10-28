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

    def __init__(self, client_id, client_secret, debug_tab=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.debug_tab = debug_tab
        self.token = None
        self.token_expiry = 0

    def _log_debug(self, category, message, data=None):
        """Log to debug tab if available"""
        if self.debug_tab:
            self.debug_tab.add_log(category, message, data)

    def get_access_token(self):
        if self.token and time.time() < self.token_expiry:
            return self.token

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}

        # Log token API call
        api_title = f"🔑 eBay Token API: {self.EBAY_TOKEN_URL}"
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
        
        # Log token response
        self._log_api_response(api_title, token_data)
        
        return self.token

    def get_ebay_pricing(self, artist, title, category_id="176985", exclude_foreign=True):
        """Get eBay pricing for a record"""
        if not self.get_access_token():
            self._log_debug("EBAY_ERROR", f"{self.EBAY_SEARCH_URL} - No access token available")
            return None

        headers = {"Authorization": f"Bearer {self.token}"}
        query = f"{artist} {title}".strip()
        params = {
            "q": query, 
            "limit": 50, 
            "category_ids": category_id,
            "filter": "conditions:USED|NEW",
            "fieldgroups": "EXTENDED"  # Get more detailed info including shipping
        }

        # Log search API call with unified format
        api_title = f"🛒 eBay Search API: {self.EBAY_SEARCH_URL}?q={query}"
        self._log_api_call(api_title, {
            'endpoint': self.EBAY_SEARCH_URL,
            'request': {
                'params': params,
                'headers': {k: '***' if 'Authorization' in k else v for k, v in headers.items()}
            }
        })

        resp = requests.get(self.EBAY_SEARCH_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Log the ACTUAL raw response from eBay - no wrapper, just the raw JSON
        self._log_api_response(api_title, data)

        items = data.get("itemSummaries", [])
        
        listings = []
        
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
                
                listings.append({
                    'base_price': base_price,
                    'shipping_type': shipping_type,
                    'shipping_cost': shipping_cost_value,
                    'total_cost': total_cost
                })

        if listings:
            # Sort by total cost to find the cheapest listing
            listings.sort(key=lambda x: x['total_cost'])
            cheapest_listing = listings[0]
            
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
                'ebay_low_shipping': round(cheapest_listing['shipping_cost'] or 0, 2),
                'ebay_low_total': round(cheapest_listing['total_cost'], 2),
                'ebay_search_url': f"https://www.ebay.com/sch/i.html?_nkw={requests.utils.quote(query)}"
            }
            
            return result
        else:
            return None

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
            
            # Log successful response - raw eBay data
            self._log_api_response(api_title, item_data)
            
            return item_data
        except Exception as e:
            # Log error response
            self._log_api_response(api_title, {
                'status_code': resp.status_code if 'resp' in locals() else 'No response',
                'error': str(e)
            })
            return None

    def _log_api_call(self, title, request_data):
        """Log API call in unified format"""
        if 'api_logs' not in st.session_state:
            st.session_state.api_logs = []
        if 'api_details' not in st.session_state:
            st.session_state.api_details = {}
            
        st.session_state.api_logs.append(title)
        st.session_state.api_details[title] = {'request': request_data}

    def _log_api_response(self, title, response_data):
        """Log API response in unified format"""
        if 'api_details' in st.session_state and title in st.session_state.api_details:
            st.session_state.api_details[title]['response'] = response_data