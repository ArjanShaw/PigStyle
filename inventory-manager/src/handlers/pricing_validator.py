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
            # Get advised price from record data (already rounded to .49/.99)
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
                    'user_price': user_price
                }
            
            # REMOVED: Maximum price ratio check
            
            # Validate minimum price only
            if user_price <= 0:
                return {
                    'is_valid': False,
                    'reason': 'Price must be greater than 0',
                    'advised_price': advised_price,
                    'user_price': user_price
                }
            
            # REMOVED: Maximum price validation
            
            return {
                'is_valid': True,
                'reason': 'Price is acceptable',
                'advised_price': advised_price,
                'user_price': user_price
            }
            
        except Exception as e:
            st.error(f"Error validating price: {e}")
            # Return valid in case of error to not block user
            return {
                'is_valid': True,
                'reason': f'Validation error: {str(e)}',
                'advised_price': 0,
                'user_price': user_price
            } 
        
    def _calculate_advised_price(self, record_data):
        """Calculate advised price from Discogs and eBay data"""
        try:
            selected_condition = record_data.get('selected_condition')
            if not selected_condition:
                return 0
            
            # Use PriceAdviseHandler to calculate advised price
            from handlers.price_advise_handler import PriceAdviseHandler
            price_advise_handler = PriceAdviseHandler(self.discogs_handler, self.ebay_handler)
            
            artist = record_data.get('artist', '')
            title = record_data.get('title', '')
            
            price_advice = price_advise_handler.get_price_advice(
                artist, title, selected_condition, record_data
            )
            
            if price_advice['success']:
                return price_advice['advised_store_price']
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