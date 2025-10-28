import math
import pandas as pd

class PriceHandler:
    def __init__(self):
        pass
    
    def calculate_store_price(self, discogs_median_price):
        """
        Calculate store price from Discogs median price.
        Rounds up to .99 (3.56 becomes 3.99, 54 becomes 53.99)
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
            
            # Round up to nearest whole number then subtract 0.01 to get .99
            rounded_up = math.ceil(price)
            store_price = rounded_up - 0.01
            
            return round(store_price, 2)
        except (ValueError, TypeError):
            return 0.0
    
    def calculate_ebay_price(self, ebay_lowest_price):
        """
        Calculate eBay price from eBay lowest price.
        Rounds down to .49 or .99 (no cutoff)
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
            
            # Round down to nearest .49 or .99 (no cutoff)
            base_price = math.floor(ebay_price)
            
            # If the decimal part is >= 0.50, use .99, otherwise use .49
            decimal_part = ebay_price - base_price
            if decimal_part >= 0.50:
                ebay_price = base_price + 0.99
            else:
                ebay_price = base_price + 0.49
            
            return round(ebay_price, 2)
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