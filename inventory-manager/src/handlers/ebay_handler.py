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

        self._log_debug("EBAY_TOKEN", f"{self.EBAY_TOKEN_URL} - Getting access token", {
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
        
        self._log_debug("EBAY_TOKEN_SUCCESS", f"{self.EBAY_TOKEN_URL} - Access token obtained", {
            'endpoint': self.EBAY_TOKEN_URL,
            'request': {
                'headers': headers,
                'data': data
            },
            'response': {
                'status_code': resp.status_code,
                'token_expires_in': token_data["expires_in"]
            }
        })
        
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
            "filter": "conditions:USED|NEW"
        }

        self._log_debug("EBAY_SEARCH", f"{self.EBAY_SEARCH_URL} - {query}", {
            'endpoint': self.EBAY_SEARCH_URL,
            'request': {
                'params': params,
                'headers': {k: '***' if 'Authorization' in k else v for k, v in headers.items()}
            }
        })

        resp = requests.get(self.EBAY_SEARCH_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("itemSummaries", [])
        
        prices = []
        for item in items:
            if exclude_foreign:
                marketplace_id = item.get("listingMarketplaceId")
                if marketplace_id and marketplace_id != "EBAY_US":
                    continue

            price_data = item.get("price", {})
            if "value" in price_data:
                price = float(price_data["value"])
                prices.append(price)

        if prices:
            sorted_prices = sorted(prices)
            n = len(sorted_prices)
            
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
            
            self._log_debug("EBAY_SEARCH_SUCCESS", f"{self.EBAY_SEARCH_URL} - {query} - ${result['ebay_median_price']} median from {len(prices)} listings", {
                'endpoint': self.EBAY_SEARCH_URL,
                'request': {
                    'params': params,
                    'headers': {k: '***' if 'Authorization' in k else v for k, v in headers.items()}
                },
                'response': {
                    'status_code': resp.status_code,
                    'listings_count': len(items),
                    'prices_found': len(prices),
                    'pricing_result': result
                }
            })
            
            return result
        else:
            self._log_debug("EBAY_SEARCH_NO_DATA", f"{self.EBAY_SEARCH_URL} - {query} - No pricing data found", {
                'endpoint': self.EBAY_SEARCH_URL,
                'request': {
                    'params': params,
                    'headers': {k: '***' if 'Authorization' in k else v for k, v in headers.items()}
                },
                'response': {
                    'status_code': resp.status_code,
                    'listings_count': len(items),
                    'items_sample': items[:3] if items else []
                }
            })
            return None