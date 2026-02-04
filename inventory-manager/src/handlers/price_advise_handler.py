"""
Centralized price advice handler that makes API calls to eBay and Discogs
and calculates advised prices with calculation_lines and eBay listings data.
"""

import streamlit as st
import re
import time
import requests
import os
import base64
from datetime import datetime
from conditions import DiscogsConditions
from handlers.rounding_handler import RoundingHandler
from handlers.env_pars_handler import EnvParsHandler
import numpy as np
import logging

logger = logging.getLogger(__name__)

class PriceAdviseHandler:
    def __init__(self, discogs_handler=None, ebay_handler=None):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
        
        # Load environment variables through centralized handler
        env_handler = EnvParsHandler()
        env_vars = env_handler.get_environment_variables()
        
        # Get eBay credentials
        self.ebay_client_id = env_vars.get("EBAY_CLIENT_ID")
        self.ebay_client_secret = env_vars.get("EBAY_CLIENT_SECRET")
        self.ebay_access_token = None
        self.token_expiry = None
        
        # Validate that eBay credentials are present
        if not self.ebay_client_id or not self.ebay_client_secret:
            raise ValueError("EBAY_CLIENT_ID and EBAY_CLIENT_SECRET must be set in environment variables")
    
    def get_price_advice(self, artist, title, selected_condition, record_data=None):
        """
        Get comprehensive price advice including:
        1. Discogs price for selected condition (FROM CACHE)
        2. eBay prices for selected condition
        3. Calculated advised store price
        4. Calculation lines for display
        5. eBay listings summary
        """
        result = {
            'discogs_price': None,
            'ebay_prices': None,
            'advised_store_price': 0.0,
            'calculation_lines': [],
            'ebay_listings': [],
            'success': False
        }
        
        # Get Discogs price FROM CACHE (already fetched during search)
        discogs_price = self._get_discogs_price_from_cache(record_data, selected_condition)
        result['discogs_price'] = discogs_price
        
        if discogs_price:
            result['calculation_lines'].append(f"• **Discogs Price (cached):** ${discogs_price:.2f}")
        
        # Get eBay prices (only if we have eBay credentials)
        if self.ebay_client_id and self.ebay_client_secret:
            ebay_prices = self._get_ebay_prices_for_condition(artist, title, selected_condition)
            result['ebay_prices'] = ebay_prices
        else:
            result['calculation_lines'].append("• **eBay Search:** Not configured")
            ebay_prices = None
        
        # Get eBay condition count
        ebay_condition_count = ebay_prices.get('condition_count', 0) if ebay_prices else 0
        
        # Calculate advised store price
        advised_store_price, calculation_lines = self.calculate_advised_store_price(
            discogs_price,
            ebay_prices,
            selected_condition,
            ebay_condition_count
        )
        
        result['advised_store_price'] = advised_store_price
        result['calculation_lines'].extend(calculation_lines)
        result['ebay_listings'] = ebay_prices.get('all_listings', []) if ebay_prices else []
        result['success'] = True
        
        return result
    
    def _get_discogs_price_from_cache(self, record_data, selected_condition):
        """Get Discogs price from cache (already fetched during search)"""
        try:
            if not record_data:
                return None
            
            # Check if price suggestions are already in the record data
            price_suggestions = record_data.get('price_suggestions', {})
            
            if not price_suggestions:
                # Fallback: check if discogs_id exists and try to get from handler cache
                release_id = record_data.get('discogs_id')
                if release_id and self.discogs_handler:
                    pricing_data = self.discogs_handler.get_release_statistics_pricing(str(release_id), use_cache=True)
                    if pricing_data and 'price_suggestions' in pricing_data:
                        price_suggestions = pricing_data.get('price_suggestions', {})
            
            if not price_suggestions:
                return None
            
            # Find price for selected condition
            for discogs_condition, price in price_suggestions.items():
                if price and price > 0:
                    # Check if this Discogs condition matches our selected condition
                    condition_abbrs = DiscogsConditions.CONDITION_ABBREVIATIONS.get(selected_condition, [])
                    for pattern in condition_abbrs:
                        if pattern.lower() in discogs_condition.lower():
                            logger.info(f"Price found in cache: {selected_condition} = ${price}")
                            return float(price)
            
            # If no exact match, return first available price
            for discogs_condition, price in price_suggestions.items():
                if price and price > 0:
                    logger.info(f"Using fallback price from cache: {discogs_condition} = ${price}")
                    return float(price)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Discogs price from cache: {e}")
            return None
    
    def _get_ebay_access_token(self):
        """Get eBay OAuth access token"""
        if self.ebay_access_token and self.token_expiry and time.time() < self.token_expiry:
            return self.ebay_access_token
        
        if not self.ebay_client_id or not self.ebay_client_secret:
            raise ValueError("eBay credentials not configured")
        
        try:
            start_time = time.time()
            logger.info("EBAY API CALL [START]: Get OAuth token")
            
            token_url = "https://api.ebay.com/identity/v1/oauth2/token"
            auth_string = base64.b64encode(
                f"{self.ebay_client_id}:{self.ebay_client_secret}".encode()
            ).decode()
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {auth_string}"
            }
            
            data = {
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope"
            }
            
            response = requests.post(token_url, headers=headers, data=data)
            
            duration = time.time() - start_time
            logger.info(f"EBAY API CALL [END]: Get OAuth token - {duration:.3f}s - Status: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                self.ebay_access_token = token_data.get('access_token')
                self.token_expiry = time.time() + token_data.get('expires_in', 7200) - 300
                return self.ebay_access_token
            else:
                error_msg = f"eBay token error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Error getting eBay token: {e}")
            raise Exception(f"Error getting eBay token: {e}")
    
    def _search_ebay_listings(self, search_query, limit=50):
        """Search eBay listings with the proper API"""
        access_token = self._get_ebay_access_token()
        if not access_token:
            raise Exception("Failed to obtain eBay access token")
        
        try:
            start_time = time.time()
            logger.info(f"EBAY API CALL [START]: Search listings for '{search_query[:50]}...'")
            
            # Build the search query - artist - title - VINYL
            ebay_search_query = f"{search_query} VINYL"
            
            # Make eBay API call
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"
            }
            
            params = {
                "q": ebay_search_query,
                "limit": str(limit),
                "filter": "conditions:{NEW|USED}"
            }
            
            response = requests.get(
                "https://api.ebay.com/buy/browse/v1/item_summary/search",
                headers=headers,
                params=params,
                timeout=10
            )
            
            duration = time.time() - start_time
            logger.info(f"EBAY API CALL [END]: Search listings for '{search_query[:50]}...' - {duration:.3f}s - Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                return data.get('itemSummaries', [])
            else:
                error_msg = f"eBay search error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logger.error(f"Error searching eBay: {e}")
            raise Exception(f"Error searching eBay: {e}")
    
    def _get_ebay_prices_for_condition(self, artist, title, selected_condition):
        """Get eBay prices for specific condition with proper grouping"""
        try:
            # Create search query: artist - title
            search_query = f"{artist} - {title}"
            
            # Get eBay listings
            ebay_listings = self._search_ebay_listings(search_query, limit=30)
            
            if not ebay_listings:
                # Return empty structure if no listings found (but API call succeeded)
                logger.info(f"No eBay listings found for: {search_query}")
                return {
                    'generic_median': 0,
                    'condition_median': 0,
                    'generic_count': 0,
                    'condition_count': 0,
                    'all_listings': [],
                    'condition_listings': [],
                    'search_query': f"{artist} - {title} - VINYL",
                    'condition': selected_condition,
                    'all_prices_raw': [],
                    'condition_prices_raw': []
                }
            
            # Process all listings
            all_listings = []
            condition_listings = []
            
            for item in ebay_listings:
                # Extract price
                price_data = item.get('price', {})
                base_price = float(price_data.get('value', 0))
                
                # Extract shipping info
                shipping_info = self._extract_ebay_shipping_info(item)
                shipping_type = shipping_info['type']
                shipping_cost = shipping_info['cost']
                
                # Get shipping cost value
                shipping_cost_value = 0.0
                if shipping_type == 'FREE':
                    shipping_cost_value = 0.0
                elif shipping_type == 'FIXED' and shipping_cost is not None:
                    shipping_cost_value = float(shipping_cost)
                elif shipping_type == 'CALC':
                    # Use configured shipping cost as estimate
                    shipping_cost_value = self._get_config_value('SHIPPING_COST', 5.72)
                
                # Create listing object
                listing = {
                    'base_price': base_price,
                    'shipping_type': shipping_type,
                    'shipping_cost': shipping_cost_value,
                    'item_data': item,
                    'total_cost': base_price + shipping_cost_value,
                    'title': item.get('title', ''),
                    'url': item.get('itemWebUrl', ''),
                    'condition': item.get('condition', 'Unknown')
                }
                
                all_listings.append(listing)
                
                # Check if this listing matches the selected condition
                item_title = item.get('title', '').lower()
                if self._listing_matches_condition(item_title, selected_condition):
                    condition_listings.append(listing)
            
            # Calculate statistics for all listings
            all_prices = [listing['base_price'] for listing in all_listings if listing['base_price'] > 0]
            generic_median = self._calculate_robust_median(all_prices) if all_prices else 0
            
            # Calculate statistics for condition-specific listings
            condition_prices = [listing['base_price'] for listing in condition_listings if listing['base_price'] > 0]
            condition_median = self._calculate_robust_median(condition_prices) if condition_prices else 0
            
            logger.info(f"eBay analysis: {len(all_prices)} total listings, {len(condition_prices)} condition matches")
            
            return {
                'generic_median': generic_median,
                'condition_median': condition_median,
                'generic_count': len(all_prices),
                'condition_count': len(condition_prices),
                'all_listings': all_listings,
                'condition_listings': condition_listings,
                'search_query': f"{artist} - {title} - VINYL",
                'condition': selected_condition,
                'all_prices_raw': all_prices,
                'condition_prices_raw': condition_prices
            }
            
        except Exception as e:
            # Log error and return empty structure
            logger.error(f"Error getting eBay prices: {e}")
            raise Exception(f"Error getting eBay prices: {e}")
    
    def _calculate_robust_median(self, prices):
        """Calculate median using robust method to filter outliers"""
        if not prices:
            return 0.0
        
        # Remove extreme outliers first
        valid_prices = [p for p in prices if p is not None and p > 0]
        if not valid_prices:
            return 0.0
        
        if len(valid_prices) <= 2:
            # For small samples, use average
            return sum(valid_prices) / len(valid_prices)
        
        # Sort prices
        sorted_prices = sorted(valid_prices)
        
        # Use Tukey's fences to identify outliers
        q1 = np.percentile(sorted_prices, 25)
        q3 = np.percentile(sorted_prices, 75)
        iqr = q3 - q1
        
        # Define outlier boundaries (1.5 * IQR rule)
        lower_bound = q1 - (1.5 * iqr)
        upper_bound = q3 + (1.5 * iqr)
        
        # Filter out outliers
        filtered_prices = [p for p in sorted_prices if lower_bound <= p <= upper_bound]
        
        if not filtered_prices:
            # If all prices are outliers, use the original median
            filtered_prices = sorted_prices
        
        # Calculate median of filtered prices
        n = len(filtered_prices)
        if n % 2 == 1:
            return float(filtered_prices[n // 2])
        else:
            mid1 = filtered_prices[n // 2 - 1]
            mid2 = filtered_prices[n // 2]
            return float((mid1 + mid2) / 2)
    
    def _listing_matches_condition(self, item_title, selected_condition):
        """Check if eBay listing title matches the selected condition"""
        # Get condition patterns from centralized class
        condition_patterns = DiscogsConditions.CONDITION_PATTERNS.get(selected_condition, [])
        
        for pattern in condition_patterns:
            if re.search(pattern, item_title, re.IGNORECASE):
                return True
        
        return False
    
    def _extract_ebay_shipping_info(self, item):
        """Extract shipping info from eBay item"""
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
        
        return {'type': 'FREE', 'cost': 0}
    
    def calculate_advised_store_price(self, discogs_price, ebay_prices, selected_condition, ebay_condition_count):
        """Calculate advised store price using unified formula"""
        # Get configuration values
        estimated_multiplier = self._get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', '2.0')
        minimum_price = self._get_config_value('STORE_PRICE_MINIMUM', '5.0')
        ebay_cond_thresh = self._get_config_value('EBAY_COND_TRESH', '3')  # Threshold for using condition-specific prices
        
        calculation_lines = []
        
        # NEW: Add eBay search query information
        search_term_info = ebay_prices.get('search_query', 'Unknown search term') if ebay_prices else 'Search not performed'
        calculation_lines.append(f"**eBay Search:** `{search_term_info}`")
        
        # Collect all available market prices
        available_prices = []
        
        # Add Discogs price if available
        if discogs_price and discogs_price > 0:
            calculation_lines.append(f"• **Discogs:** ${discogs_price:.2f}")
            available_prices.append(discogs_price)
        
        # Add eBay prices
        if ebay_prices:
            # Get eBay condition-specific median
            condition_median = ebay_prices.get('condition_median', 0)
            condition_count = ebay_prices.get('condition_count', 0)
            
            # Get eBay generic median
            generic_median = ebay_prices.get('generic_median', 0)
            generic_count = ebay_prices.get('generic_count', 0)
            
            # NEW: Check if eBay search was performed but returned no listings
            all_listings = ebay_prices.get('all_listings', [])
            condition_listings = ebay_prices.get('condition_listings', [])
            
            if not all_listings:
                calculation_lines.append(f"• **eBay Search:** No matching listings found")
            else:
                # Add condition-specific price if available
                if condition_median and condition_median > 0:
                    calculation_lines.append(f"• **eBay ({selected_condition}):** ${condition_median:.2f} (n={condition_count})")
                    if condition_count >= ebay_cond_thresh:  # Only use if above threshold
                        available_prices.append(condition_median)
                
                # Add generic price if available
                if generic_median and generic_median > 0:
                    calculation_lines.append(f"• **eBay (generic):** ${generic_median:.2f} (n={generic_count})")
                    available_prices.append(generic_median)
        else:
            # NEW: Handle case when ebay_prices is None (API failure)
            calculation_lines.append(f"• **eBay Search:** Failed - API call returned no data")
        
        # Determine which eBay price to use for minimum calculation
        ebay_price_to_use = 0
        if ebay_prices:
            condition_median = ebay_prices.get('condition_median', 0)
            generic_median = ebay_prices.get('generic_median', 0)
            condition_count = ebay_prices.get('condition_count', 0)
            
            # Use condition-specific price if enough listings, otherwise use generic
            if condition_median and condition_median > 0 and condition_count >= ebay_cond_thresh:
                ebay_price_to_use = condition_median
                calculation_lines.append(f"• **Using eBay condition price (n={condition_count} ≥ {ebay_cond_thresh})**")
            elif generic_median and generic_median > 0:
                ebay_price_to_use = generic_median
                calculation_lines.append(f"• **Using eBay generic price (condition n={condition_count} < {ebay_cond_thresh})**")
            elif not ebay_prices.get('all_listings', []):
                # NEW: Special case when no listings at all
                calculation_lines.append(f"• **No eBay listings found for search term**")
            elif condition_median == 0 and generic_median == 0 and ebay_prices.get('all_listings'):
                # NEW: Special case when listings exist but median is 0
                calculation_lines.append(f"• **eBay listings found but median price calculation failed**")
        
        # Calculate minimum market price: min(Discogs, eBay[selected price])
        raw_market_price = 0
        if discogs_price and discogs_price > 0 and ebay_price_to_use > 0:
            # Both Discogs and eBay prices available - use the minimum
            raw_market_price = min(discogs_price, ebay_price_to_use)
            calculation_lines.append(f"• **Minimum market price:** ${raw_market_price:.2f} (min of Discogs and eBay)")
        elif discogs_price and discogs_price > 0:
            # Only Discogs price available
            raw_market_price = discogs_price
            calculation_lines.append(f"• **Minimum market price:** ${raw_market_price:.2f} (Discogs only)")
        elif ebay_price_to_use > 0:
            # Only eBay price available
            raw_market_price = ebay_price_to_use
            calculation_lines.append(f"• **Minimum market price:** ${raw_market_price:.2f} (eBay only)")
        else:
            # No market prices available
            raw_market_price = minimum_price
            calculation_lines.append(f"• **Minimum price:** ${minimum_price:.2f} (no market data)")
        
        # Calculate store price: multiplier × market price
        if raw_market_price > 0:
            calculation_lines.append(f"• **Multiplier:** {estimated_multiplier}× = ${raw_market_price * estimated_multiplier:.2f}")
            advised_store_price = estimated_multiplier * raw_market_price
        else:
            advised_store_price = minimum_price
        
        # Ensure minimum price
        if advised_store_price < minimum_price:
            calculation_lines.append(f"• **Apply minimum:** ${minimum_price:.2f}")
            advised_store_price = minimum_price
        
        # Round using new pricing rules
        raw_advised_price = advised_store_price
        advised_store_price = RoundingHandler.round_to_99(advised_store_price)
        
        # Add rounding step if it changed the price
        if abs(advised_store_price - raw_advised_price) > 0.01:
            calculation_lines.append(f"• **Rounded to store pricing rules:** ${advised_store_price:.2f}")
        
        return advised_store_price, calculation_lines

    def _round_to_49_or_99(self, price):
        """Round to nearest .49 or .99 - DEPRECATED: Use RoundingHandler.round_to_99() instead"""
        return RoundingHandler.round_to_99(price)
    
    def _get_config_value(self, config_key, default=None):
        """Get config value from config cache or API"""
        try:
            # First check if config_cache exists in session state
            if hasattr(st.session_state, 'config_cache') and st.session_state.config_cache:
                value = st.session_state.config_cache.get(config_key)
                if value is not None:
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return value
            
            # If not in session state, try to get it from API
            try:
                start_time = time.time()
                logger.info(f"CONFIG API CALL [START]: GET /config/{config_key}")
                
                response = requests.get(f"https://www.pigstylemusic.com/config/{config_key}")
                
                duration = time.time() - start_time
                logger.info(f"CONFIG API CALL [END]: GET /config/{config_key} - {duration:.3f}s - Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    value = data.get('config_value', default)
                    try:
                        return float(value) if value else default
                    except (ValueError, TypeError):
                        return value
            except Exception as e:
                logger.error(f"Error fetching config {config_key}: {e}")
                return float(default) if default else default
            
            return float(default) if default else default
                
        except Exception as e:
            logger.error(f"Error getting config {config_key}: {e}")
            return float(default) if default else default