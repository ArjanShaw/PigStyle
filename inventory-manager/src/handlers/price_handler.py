import math
import pandas as pd
from handlers.rounding_handler import RoundingHandler

class PriceHandler:
    def __init__(self):
        pass
    
    def calculate_store_price(self, discogs_median_price):
        """
        Calculate store price from Discogs median price.
        Uses new rounding rules: $1.99 for ≤ $3.75, $4.99 for $3.76-$4.99, nearest .99 for > $4.99
        """
        # Handle None, NaN, or invalid values
        if (discogs_median_price is None or 
            pd.isna(discogs_median_price) or 
            discogs_median_price <= 0):
            return 0.0
        
        try:
            # Convert to float and ensure it's a valid number
            price = float(discogs_median_price)
            if price <= 0:
                return 0.0
            
            # Use RoundingHandler to round with new rules
            return RoundingHandler.round_to_99(price)
        except (ValueError, TypeError):
            return 0.0
    
    def calculate_ebay_price(self, ebay_lowest_price):
        """
        Calculate eBay price from eBay lowest price.
        Uses new rounding rules: $1.99 for ≤ $3.75, $4.99 for $3.76-$4.99, nearest .99 for > $4.99
        """
        # Handle None, NaN, or invalid values
        if (ebay_lowest_price is None or 
            pd.isna(ebay_lowest_price) or 
            ebay_lowest_price <= 0):
            return 0.0
        
        try:
            # Convert to float and ensure it's a valid number
            ebay_price = float(ebay_lowest_price)
            if ebay_price <= 0:
                return 0.0
            
            # Use RoundingHandler to round with new rules
            return RoundingHandler.round_to_99(ebay_price)
        except (ValueError, TypeError):
            return 0.0
    
    def calculate_prices_for_record(self, record):
        """
        Calculate both store and eBay prices for a record
        Returns: (store_price, ebay_price)
        """
        discogs_median = record.get('discogs_median_price') or 0
        ebay_lowest = record.get('ebay_lowest_price') or 0
        
        store_price = self.calculate_store_price(discogs_median)
        ebay_price = self.calculate_ebay_price(ebay_lowest)
        
        return store_price, ebay_price