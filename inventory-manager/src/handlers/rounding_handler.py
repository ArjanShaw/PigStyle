"""
Centralized rounding handler for consistent price rounding across the application.
Handles rounding to .99 cents only with new minimum price rules.
"""

import math


class RoundingHandler:
    """Provides consistent rounding with new minimum price rules"""
    
    @staticmethod
    def round_to_99(price):
        """
        Round price according to new pricing rules:
        1. Minimum store price: $4.99
        2. Price ≤ $3.75: Round down to $1.99 (minimum price)
        3. Price $3.76 - $4.99: Round up to $4.99
        4. Price > $4.99: Round to nearest .99
        
        Args:
            price (float): Price to round
            
        Returns:
            float: Price rounded according to new rules
        """
        if price <= 0:
            return 0.0
        
        # Rule 1: Minimum store price is $4.99 for anything above $3.75
        # Rule 2: Price ≤ $3.75 goes to $1.99
        if price <= 3.75:
            return 1.99
        
        # Rule 3: Price between $3.76 and $4.99 goes to $4.99
        if price <= 4.99:
            return 4.99
        
        # Rule 4: Price > $4.99 - round to nearest .99
        # Check if price already ends with .99
        if abs(price % 1 - 0.99) < 0.001:
            return price
        
        # Get the integer part
        base_price = math.floor(price)
        
        # Calculate two candidate prices: base.99 and (base+1).99
        candidate_99 = base_price + 0.99
        candidate_next_99 = (base_price + 1) + 0.99
        
        # Find which .99 price is closest to the original price
        diff_current = abs(price - candidate_99)
        diff_next = abs(price - candidate_next_99)
        
        # Return the closest .99 price
        if diff_current <= diff_next:
            return candidate_99
        else:
            return candidate_next_99
    
    @staticmethod
    def calculate_ebay_sell_at(ebay_lowest_price, ebay_low_shipping, discogs_median_price, shipping_cost):
        """
        Calculate eBay sell price using the standard formula and round according to new rules
        
        Args:
            ebay_lowest_price (float): Lowest eBay price
            ebay_low_shipping (float): Shipping cost for lowest eBay listing
            discogs_median_price (float): Discogs median price
            shipping_cost (float): Store shipping cost from config
            
        Returns:
            float: eBay sell price rounded according to new rules
        """
        if ebay_lowest_price is not None and ebay_low_shipping is not None:
            ebay_lowest_price = float(ebay_lowest_price)
            ebay_low_shipping = float(ebay_low_shipping)
            
            # Calculate raw eBay sell price
            ebay_sell_at_raw = ebay_lowest_price + ebay_low_shipping - shipping_cost
            
            # Ensure not negative
            ebay_sell_at_raw = max(ebay_sell_at_raw, 0.00)
            
            # Cap at Discogs median if available
            if discogs_median_price is not None and discogs_median_price > 0:
                discogs_median = float(discogs_median_price)
                if ebay_sell_at_raw > discogs_median:
                    ebay_sell_at = RoundingHandler.round_to_99(discogs_median)
                else:
                    ebay_sell_at = RoundingHandler.round_to_99(ebay_sell_at_raw)
            else:
                ebay_sell_at = RoundingHandler.round_to_99(ebay_sell_at_raw)
        else:
            # No eBay data - use Discogs median price
            if discogs_median_price is not None and discogs_median_price > 0:
                ebay_sell_at = RoundingHandler.round_to_99(float(discogs_median_price))
            else:
                # No pricing data available
                ebay_sell_at = 0.0
        
        # Apply hardcoded minimum (though round_to_99 already handles minimums)
        return max(ebay_sell_at, 0.00)