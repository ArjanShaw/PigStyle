import streamlit as st
import pandas as pd
from datetime import datetime

class PricingValidator:
    """Validate pricing against Discogs and eBay data"""
    
    def __init__(self, api_client, discogs_handler, ebay_handler):
        self.api_client = api_client
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
    
    def validate_user_price(self, user_price, record_data):
        """Validate user-entered price against advised price"""
        try:
            # Get max price ratio from config
            max_ratio_value = self.api_client.get_config_value('MAX_PRICE_TO_ADV_RATIO', '1.3')
            max_ratio = float(max_ratio_value) if max_ratio_value else 1.3
            
            # Get advised price from record data
            advised_price = record_data.get('advised_price')
            if not advised_price or advised_price <= 0:
                # Try to calculate advised price
                advised_price = self._calculate_advised_price(record_data)
            
            if not advised_price or advised_price <= 0:
                # If we can't get an advised price, accept the user price
                return {
                    'is_valid': True,
                    'reason': 'No advised price available',
                    'advised_price': 0,
                    'max_allowed': user_price * 2,  # Arbitrary high limit
                    'user_price': user_price
                }
            
            # Calculate maximum allowed price
            max_allowed = advised_price * max_ratio
            
            # Validate
            if user_price <= 0:
                return {
                    'is_valid': False,
                    'reason': 'Price must be greater than 0',
                    'advised_price': advised_price,
                    'max_allowed': max_allowed,
                    'user_price': user_price
                }
            
            if user_price > max_allowed:
                return {
                    'is_valid': False,
                    'reason': f'Price exceeds maximum allowed (max: ${max_allowed:.2f})',
                    'advised_price': advised_price,
                    'max_allowed': max_allowed,
                    'user_price': user_price
                }
            
            return {
                'is_valid': True,
                'reason': 'Price is within acceptable range',
                'advised_price': advised_price,
                'max_allowed': max_allowed,
                'user_price': user_price
            }
            
        except Exception as e:
            st.error(f"Error validating price: {e}")
            # Return valid in case of error to not block user
            return {
                'is_valid': True,
                'reason': f'Validation error: {str(e)}',
                'advised_price': 0,
                'max_allowed': user_price * 2,
                'user_price': user_price
            }
    
    def _calculate_advised_price(self, record_data):
        """Calculate advised price from Discogs and eBay data"""
        try:
            selected_condition = record_data.get('selected_condition')
            if not selected_condition:
                return 0
            
            # Get Discogs price
            discogs_price = None
            if self.discogs_handler and record_data.get('discogs_id'):
                pricing_data = self.discogs_handler.get_release_statistics_pricing(
                    str(record_data['discogs_id'])
                )
                if pricing_data and 'price_suggestions' in pricing_data:
                    # Try to find price for selected condition
                    price_suggestions = pricing_data['price_suggestions']
                    for condition, price in price_suggestions.items():
                        if price and selected_condition.lower() in condition.lower():
                            discogs_price = float(price)
                            break
            
            # Get eBay price
            ebay_price = None
            if self.ebay_handler:
                artist = record_data.get('artist', '')
                title = record_data.get('title', '')
                ebay_data = self.ebay_handler.get_ebay_pricing(artist, title)
                if ebay_data:
                    # Use median price from eBay
                    all_prices = []
                    for condition_group in ebay_data.get('condition_pricing', {}).values():
                        for listing in condition_group.get('listings', []):
                            if listing.get('base_price', 0) > 0:
                                all_prices.append(listing['base_price'])
                    
                    if all_prices:
                        ebay_price = float(sorted(all_prices)[len(all_prices) // 2])
            
            # Calculate advised price as minimum of available prices
            candidates = []
            if discogs_price and discogs_price > 0:
                candidates.append(discogs_price)
            if ebay_price and ebay_price > 0:
                candidates.append(ebay_price)
            
            if candidates:
                return min(candidates)
            else:
                return 0
                
        except Exception as e:
            st.error(f"Error calculating advised price: {e}")
            return 0
    
    def check_for_duplicates(self, record_data):
        """Check if similar record already exists in database"""
        try:
            artist = record_data.get('artist', '').lower()
            title = record_data.get('title', '').lower()
            catalog = record_data.get('catalog_number', '').lower()
            
            if not artist or not title:
                return False
            
            # Search for similar records
            search_results = self.api_client.search_records(f"{artist} {title}")
            
            for record in search_results:
                record_artist = record.get('artist', '').lower()
                record_title = record.get('title', '').lower()
                record_catalog = record.get('catalog_number', '').lower()
                
                # Check for close matches
                if (artist in record_artist or record_artist in artist) and \
                   (title in record_title or record_title in title):
                    # Check if catalog numbers match (if both have them)
                    if catalog and record_catalog:
                        if catalog == record_catalog:
                            return True
                    else:
                        # If no catalog numbers, still flag as potential duplicate
                        return True
            
            return False
            
        except Exception as e:
            st.error(f"Error checking for duplicates: {e}")
            return False