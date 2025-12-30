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
    
    # API base URL - update with your actual API endpoint
    API_BASE_URL = "https://arjanshaw.pythonanywhere.com"  # Replace with your actual API URL

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expiry = 0

    def _get_config_value(self, config_key):
        """Get config value from API and throw exception if not found"""
        try:
            # Call API endpoint to get config value
            response = requests.get(f"{self.API_BASE_URL}/config/{config_key}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    value = data.get('config_value')
                    if value is None:
                        raise ValueError(f"Configuration key '{config_key}' not found in app_config table")
                    
                    try:
                        return float(value)
                    except ValueError:
                        raise ValueError(f"Configuration key '{config_key}' has invalid value: '{value}'. Must be a number.")
                else:
                    raise ValueError(f"API error: {data.get('error', 'Unknown error')}")
            else:
                raise ValueError(f"API request failed with status {response.status_code}")
                
        except requests.RequestException as e:
            raise ValueError(f"Failed to connect to API: {str(e)}")

    def get_access_token(self):
        if self.token and time.time() < self.token_expiry:
            return self.token

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"}

        resp = requests.post(self.EBAY_TOKEN_URL, headers=headers, data=data, auth=(self.client_id, self.client_secret))
        resp.raise_for_status()
        token_data = resp.json()
        self.token = token_data["access_token"]
        self.token_expiry = time.time() + token_data["expires_in"] - 60
        
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

        resp = requests.get(self.EBAY_SEARCH_URL, headers=headers, params=params, timeout=15)
        
        # Handle API errors gracefully
        if resp.status_code != 200:
            error_msg = f'Status {resp.status_code}: {resp.text}'
            return None
            
        data = resp.json()

        items = data.get("itemSummaries", [])
        
        # Group listings by detected Discogs condition
        condition_groups = {}
        
        # Get shipping cost from config for CALC items
        shipping_cost = self._get_config_value('SHIPPING_COST')
        
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
                
                # Skip items that are local pickup only (ignore them for pricing)
                if shipping_type == 'LOCAL_PICKUP_ONLY':
                    continue

                # Calculate total cost for ranking - use config shipping for CALC items
                if shipping_type == 'CALC':
                    total_cost_for_ranking = base_price + shipping_cost  # Use config shipping cost
                elif shipping_cost_value is not None:
                    total_cost_for_ranking = base_price + shipping_cost_value
                else:
                    total_cost_for_ranking = base_price  # For FREE shipping
                
                item_url = item.get("itemWebUrl", "")
                item_id = item.get("itemId", "")
                
                # Detect Discogs condition from title and description
                detected_condition = self._detect_discogs_condition(item)
                
                listing_data = {
                    'base_price': base_price,
                    'shipping_type': shipping_type,
                    'shipping_cost': shipping_cost_value,
                    'total_cost_for_ranking': total_cost_for_ranking,
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
                
                # Sort by total cost for ranking (using config shipping for CALC items)
                listings_sorted = sorted(listings, key=lambda x: x['total_cost_for_ranking'])
                
                n = len(base_prices)
                
                # Calculate median base price
                if n % 2 == 1:
                    median_base = base_prices[n//2]
                else:
                    median_base = (base_prices[n//2 - 1] + base_prices[n//2]) / 2
                
                # Find cheapest listing in this condition group (using ranking logic)
                cheapest_listing = listings_sorted[0]
                
                condition_pricing[condition] = {
                    'count': len(listings),
                    'lowest_price': round(cheapest_listing['base_price'], 2),
                    'lowest_shipping': cheapest_listing['shipping_cost'],  # Keep as None for CALC
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
            overall_cheapest = min(all_listings, key=lambda x: x['total_cost_for_ranking'])
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

    def _extract_shipping_info(self, item):
        """Extract shipping information from eBay item data - IMPROVED VERSION"""
        try:
            # Priority 1: Check shippingOptions first (most reliable)
            shipping_options = item.get('shippingOptions', [])
            if shipping_options:
                for option in shipping_options:
                    shipping_cost_type = option.get('shippingCostType', '')
                    if shipping_cost_type == 'CALCULATED':
                        # For CALCULATED shipping, return None for cost
                        return {'type': 'CALC', 'cost': None}
                    elif shipping_cost_type == 'FIXED':
                        shipping_cost = option.get('shippingCost', {})
                        if 'value' in shipping_cost:
                            cost = float(shipping_cost['value'])
                            return {'type': 'FIXED', 'cost': cost}
                    elif shipping_cost_type == 'FREE':
                        return {'type': 'FREE', 'cost': 0}

            # Priority 2: Check shippingCostSummary
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
                elif shipping_cost_type == 'FREE':
                    return {'type': 'FREE', 'cost': 0}

            # Priority 3: Check for legacy shipping fields
            if 'shippingCostFixed' in item:
                cost = float(item['shippingCostFixed'])
                return {'type': 'FIXED', 'cost': cost}

            # Priority 4: Check estimatedAvailabilities for pickup info
            estimated_availabilities = item.get('estimatedAvailabilities', [])
            for availability in estimated_availabilities:
                delivery_options = availability.get('deliveryOptions', [])
                # If only local pickup is available and no shipping, treat as local pickup only
                if (delivery_options and 
                    all(option == 'SELLER_ARRANGED_LOCAL_PICKUP' for option in delivery_options)):
                    return {'type': 'LOCAL_PICKUP_ONLY', 'cost': None}

            # If no shipping cost found and not local pickup only, assume calculated shipping
            # Many eBay listings default to calculated shipping when not explicitly set
            return {'type': 'CALC', 'cost': None}
                
        except Exception as e:
            # Default to calculated shipping on error
            return {'type': 'CALC', 'cost': None}

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

    def get_item_details(self, item_id):
        """Get detailed information for a specific eBay item"""
        if not self.get_access_token():
            return None

        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{self.EBAY_ITEM_URL}{item_id}"

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            item_data = resp.json()
            
            return item_data
        except Exception as e:
            return None