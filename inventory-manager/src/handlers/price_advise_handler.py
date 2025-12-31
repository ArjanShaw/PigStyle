"""
Centralized price advice handler that makes API calls to eBay and Discogs
and calculates advised prices with calculation_lines and eBay listings data.
"""

import streamlit as st
import re
import time
import requests
from conditions import DiscogsConditions

class PriceAdviseHandler:
    def __init__(self, discogs_handler=None, ebay_handler=None):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
    
    def get_price_advice(self, artist, title, selected_condition, record_data=None):
        """
        Get comprehensive price advice including:
        1. Discogs price for selected condition
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
        
        # Get Discogs price
        discogs_price = self._get_discogs_price_for_condition(record_data, selected_condition)
        result['discogs_price'] = discogs_price
        
        # Get eBay prices
        ebay_prices = self._get_ebay_prices_for_condition(artist, title, selected_condition)
        result['ebay_prices'] = ebay_prices
        
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
        result['calculation_lines'] = calculation_lines
        result['ebay_listings'] = ebay_prices.get('all_listings', []) if ebay_prices else []
        result['success'] = True
        
        return result
    
    def _get_discogs_price_for_condition(self, record_data, selected_condition):
        """Get Discogs price for specific condition"""
        try:
            if not self.discogs_handler or not record_data or 'discogs_id' not in record_data:
                return None
            
            release_id = record_data.get('discogs_id')
            if not release_id:
                return None
            
            pricing_data = self.discogs_handler.get_release_statistics_pricing(str(release_id))
            if not pricing_data or 'price_suggestions' not in pricing_data:
                return None
            
            price_suggestions = pricing_data.get('price_suggestions', {})
            
            # Use centralized condition abbreviations
            for discogs_condition, price in price_suggestions.items():
                if price and price > 0:
                    # Check if this Discogs condition matches our selected condition
                    condition_abbrs = DiscogsConditions.CONDITION_ABBREVIATIONS.get(selected_condition, [])
                    for pattern in condition_abbrs:
                        if pattern.lower() in discogs_condition.lower():
                            return float(price)
            
            # If no exact match, return first available price
            for discogs_condition, price in price_suggestions.items():
                if price and price > 0:
                    return float(price)
            
            return None
            
        except Exception as e:
            st.error(f"Error getting Discogs price: {e}")
            return None
    
    def _get_ebay_prices_for_condition(self, artist, title, selected_condition):
        """Get eBay prices for specific condition"""
        try:
            if not self.ebay_handler:
                return None
            
            ebay_data = self.ebay_handler.get_ebay_pricing(artist, title)
            if not ebay_data:
                return None
            
            all_listings = []
            for condition_group in ebay_data.get('condition_pricing', {}).values():
                all_listings.extend(condition_group.get('listings', []))
            
            all_prices = [listing.get('base_price', 0) for listing in all_listings if listing.get('base_price', 0) > 0]
            generic_median = self._calculate_median(all_prices) if all_prices else 0
            
            # Get condition patterns from centralized class
            condition_patterns = DiscogsConditions.CONDITION_PATTERNS.get(selected_condition, [])
            
            condition_listings = []
            
            for listing in all_listings:
                item_data = listing.get('item_data', {})
                title_text = item_data.get('title', '').lower()
                
                for pattern in condition_patterns:
                    if re.search(pattern, title_text, re.IGNORECASE):
                        condition_listings.append(listing)
                        break
            
            condition_prices = [listing.get('base_price', 0) for listing in condition_listings if listing.get('base_price', 0) > 0]
            condition_median = self._calculate_median(condition_prices) if condition_prices else 0
            
            return {
                'generic_median': generic_median,
                'condition_median': condition_median,
                'generic_count': len(all_prices),
                'condition_count': len(condition_prices),
                'all_listings': all_listings,
                'condition_listings': condition_listings,
                'search_query': f"{artist} {title}",
                'condition': selected_condition,
                'raw_data': ebay_data
            }
            
        except Exception as e:
            st.error(f"Error getting eBay prices: {e}")
            return None
    
    def calculate_advised_store_price(self, discogs_price, ebay_prices, selected_condition, ebay_condition_count):
        """Calculate advised store price using unified formula - FIXED to use minimum of Discogs and eBay prices"""
        # Get configuration values
        estimated_multiplier = self._get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', '2.0')
        minimum_price = self._get_config_value('STORE_PRICE_MINIMUM', '5.0')
        ebay_cond_thresh = self._get_config_value('EBAY_COND_TRESH', '3')
        
        calculation_lines = []
        
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
            
            # Add condition-specific price if available and has enough listings
            if condition_median and condition_median > 0:
                calculation_lines.append(f"• **eBay ({selected_condition}):** ${condition_median:.2f} (n={condition_count})")
                available_prices.append(condition_median)
            
            # Add generic price if available
            if generic_median and generic_median > 0:
                calculation_lines.append(f"• **eBay (generic):** ${generic_median:.2f} (n={generic_count})")
                available_prices.append(generic_median)
        
        # Determine which eBay price to use for minimum calculation
        ebay_price_to_use = 0
        if ebay_prices:
            condition_median = ebay_prices.get('condition_median', 0)
            generic_median = ebay_prices.get('generic_median', 0)
            
            # Use condition-specific price if enough listings, otherwise use generic
            if condition_median and condition_median > 0 and ebay_condition_count > ebay_cond_thresh:
                ebay_price_to_use = condition_median
            elif generic_median and generic_median > 0:
                ebay_price_to_use = generic_median
        
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
        
        # Round to .49 or .99
        raw_advised_price = advised_store_price
        advised_store_price = self._round_to_49_or_99(advised_store_price)
        
        # Add rounding step if it changed the price
        if abs(advised_store_price - raw_advised_price) > 0.01:
            calculation_lines.append(f"• **Rounded to 0.49 or 0.99:** ${advised_store_price:.2f}")
        
        return advised_store_price, calculation_lines
    
    def _calculate_median(self, prices):
        """Calculate median of prices"""
        if not prices:
            return 0.0
        
        valid_prices = [p for p in prices if p is not None and p > 0]
        if not valid_prices:
            return 0.0
        
        sorted_prices = sorted(valid_prices)
        n = len(sorted_prices)
        
        if n % 2 == 1:
            return float(sorted_prices[n // 2])
        else:
            return float((sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) / 2)
    
    def _round_to_49_or_99(self, price):
        """Round to nearest .49 or .99"""
        import math
        
        if price <= 0:
            return 0.0
        
        # Check if price already ends with .49 or .99
        if abs(price % 1 - 0.49) < 0.001 or abs(price % 1 - 0.99) < 0.001:
            return price
        
        base_price = math.floor(price)
        decimal_part = price - base_price
        
        if decimal_part < 0.25:
            return base_price + 0.49
        elif decimal_part < 0.75:
            return base_price + 0.49
        else:
            return base_price + 0.99
    
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
                response = requests.get(f"https://arjanshaw.pythonanywhere.com/config/{config_key}")
                if response.status_code == 200:
                    data = response.json()
                    value = data.get('config_value', default)
                    try:
                        return float(value) if value else default
                    except (ValueError, TypeError):
                        return value
            except:
                return float(default) if default else default
            
            return float(default) if default else default
                
        except Exception as e:
            print(f"Error getting config {config_key}: {e}")
            return float(default) if default else default