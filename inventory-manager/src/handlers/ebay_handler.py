import requests
import time
import re
import json
from pathlib import Path

class EbayHandler:
    EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

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

        try:
            self._log_debug("EBAY_REQUEST", "Getting access token", {
                'endpoint': self.EBAY_TOKEN_URL,
                'headers': headers
            })
            
            resp = requests.post(self.EBAY_TOKEN_URL, headers=headers, data=data, auth=(self.client_id, self.client_secret))
            resp.raise_for_status()
            token_data = resp.json()
            self.token = token_data["access_token"]
            self.token_expiry = time.time() + token_data["expires_in"] - 60
            
            self._log_debug("EBAY_RESPONSE", "Access token obtained successfully", {
                'endpoint': self.EBAY_TOKEN_URL,
                'token_expires_in': token_data["expires_in"]
            })
            
            return self.token
        except Exception as e:
            self._log_debug("EBAY_ERROR", f"Failed to get access token: {e}")
            return None

    def get_ebay_pricing(self, artist, title, category_id="176985", exclude_foreign=True):
        """Get eBay pricing for a record"""
        if not self.get_access_token():
            self._log_debug("EBAY_ERROR", "No access token available")
            return None

        headers = {"Authorization": f"Bearer {self.token}"}
        query = f"{artist} {title}".strip()
        params = {
            "q": query, 
            "limit": 50, 
            "category_ids": category_id,
            "filter": "conditions:USED|NEW"
        }

        try:
            self._log_debug("EBAY_REQUEST", f"Searching eBay for: {query}", {
                'endpoint': self.EBAY_SEARCH_URL,
                'params': params,
                'headers': {k: '***' if 'Authorization' in k else v for k, v in headers.items()}
            })
            
            resp = requests.get(self.EBAY_SEARCH_URL, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            items = data.get("itemSummaries", [])
            
            self._log_debug("EBAY_RESPONSE", f"eBay search completed: {len(items)} listings found", {
                'endpoint': self.EBAY_SEARCH_URL,
                'result_count': len(items),
                'pricing_sample': [{
                    'title': item.get('title', '')[:50] + '...' if len(item.get('title', '')) > 50 else item.get('title', ''),
                    'price': item.get('price', {}).get('value'),
                    'condition': item.get('condition', 'Unknown')
                } for item in items[:3]] if items else []
            })

            prices = []
            for item in items:
                try:
                    # Filter out foreign listings if requested
                    if exclude_foreign:
                        marketplace_id = item.get("listingMarketplaceId")
                        if marketplace_id and marketplace_id != "EBAY_US":
                            continue

                    price_data = item.get("price", {})
                    if "value" in price_data:
                        price = float(price_data["value"])
                        prices.append(price)
                except Exception as e:
                    continue

            if prices:
                sorted_prices = sorted(prices)
                n = len(sorted_prices)
                
                # Calculate median
                if n % 2 == 1:
                    median = sorted_prices[n//2]
                else:
                    median = (sorted_prices[n//2 - 1] + sorted_prices[n//2]) / 2

                result = {
                    'ebay_median_price': round(median, 2),
                    'ebay_lowest_price': min(prices),
                    'ebay_highest_price': max(prices),
                    'ebay_listings_count': len(prices)
                }
                
                self._log_debug("EBAY_SUCCESS", f"eBay pricing calculated: ${result['ebay_median_price']} median from {len(prices)} prices", {
                    'median_price': result['ebay_median_price'],
                    'price_range': f"${result['ebay_lowest_price']} - ${result['ebay_highest_price']}",
                    'listings_count': len(prices)
                })
                
                return result
            else:
                self._log_debug("EBAY_WARNING", "No eBay pricing data found for the search")
                return None

        except Exception as e:
            self._log_debug("EBAY_ERROR", f"eBay API error: {e}")
            return None