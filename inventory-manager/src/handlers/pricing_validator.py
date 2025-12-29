"""
Pricing Validator for Consignment System
Validates user prices against advised prices from Discogs/eBay
"""
import streamlit as st
import pandas as pd
from datetime import datetime

class PricingValidator:
    def __init__(self, db_manager, discogs_handler=None, ebay_handler=None):
        self.db_manager = db_manager
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
    
    def calculate_advised_price(self, record_data):
        """
        Calculate advised price from Discogs and eBay data
        Returns the lower of Discogs median or eBay lowest+shipping
        """
        try:
            advised_price = None
            
            # Get Discogs price if available
            discogs_price = record_data.get('discogs_suggested_price')
            if discogs_price and discogs_price > 0:
                advised_price = float(discogs_price)
            
            # Get eBay price if available
            ebay_lowest = record_data.get('ebay_lowest_price')
            ebay_shipping = record_data.get('ebay_low_shipping')
            
            if ebay_lowest and ebay_shipping:
                ebay_total = float(ebay_lowest) + float(ebay_shipping)
                shipping_cost = self._get_shipping_cost()
                ebay_net = ebay_total - shipping_cost
                
                if advised_price is None or ebay_net < advised_price:
                    advised_price = ebay_net
            
            # Apply catalog weighting if available
            catalog_weight = self.db_manager.get_config_value('CATALOG_PRICE_WEIGHTING', '0.3')
            try:
                catalog_weight = float(catalog_weight)
                if 0 <= catalog_weight <= 1:
                    # In a real system, you might have catalog pricing data
                    # For now, just return the calculated price
                    pass
            except:
                pass
            
            return max(advised_price, 0) if advised_price is not None else 0
            
        except Exception as e:
            st.error(f"Error calculating advised price: {e}")
            return 0
    
    def validate_user_price(self, user_price, record_data):
        """
        Validate user price against maximum allowed ratio
        """
        try:
            max_ratio = float(self.db_manager.get_config_value('MAX_PRICE_TO_ADV_RATIO', '1.3'))
            
            advised_price = self.calculate_advised_price(record_data)
            if advised_price <= 0:
                return {
                    'is_valid': True,
                    'user_price': user_price,
                    'advised_price': advised_price,
                    'max_allowed': user_price,
                    'reason': 'No advised price available'
                }
            
            max_allowed = advised_price * max_ratio
            
            is_valid = user_price <= max_allowed
            
            return {
                'is_valid': is_valid,
                'user_price': user_price,
                'advised_price': round(advised_price, 2),
                'max_allowed': round(max_allowed, 2),
                'max_ratio': max_ratio,
                'reason': f'Price exceeds maximum allowed ({max_ratio}x advised price)' if not is_valid else 'Price is valid'
            }
            
        except Exception as e:
            st.error(f"Error validating price: {e}")
            return {
                'is_valid': False,
                'user_price': user_price,
                'reason': f'Validation error: {str(e)}'
            }
    
    def check_for_duplicates(self, record_data):
        """
        Enhanced duplicate checking against existing inventory
        """
        try:
            artist = record_data.get('artist', '')
            title = record_data.get('title', '')
            catalog = record_data.get('catalog_number', '')
            
            all_records = self.db_manager.get_all_records()
            
            duplicates = []
            
            # Check artist/title match
            if artist and title:
                artist_title_match = all_records[
                    (all_records['artist'].str.lower() == artist.lower()) & 
                    (all_records['title'].str.lower() == title.lower())
                ]
                if not artist_title_match.empty:
                    for _, dup in artist_title_match.iterrows():
                        duplicates.append({
                            'record_id': dup['id'],
                            'artist': dup['artist'],
                            'title': dup['title'],
                            'match_type': 'artist/title',
                            'catalog': dup.get('catalog_number', '')
                        })
            
            # Check catalog number match
            if catalog:
                catalog_match = all_records[
                    (all_records['catalog_number'].str.lower() == catalog.lower())
                ]
                if not catalog_match.empty:
                    for _, dup in catalog_match.iterrows():
                        # Avoid duplicate entries
                        if dup['id'] not in [d['record_id'] for d in duplicates]:
                            duplicates.append({
                                'record_id': dup['id'],
                                'artist': dup['artist'],
                                'title': dup['title'],
                                'match_type': 'catalog',
                                'catalog': dup.get('catalog_number', '')
                            })
            
            # Log duplicate check
            if duplicates:
                self._log_duplicate_check(record_data, duplicates)
            
            return duplicates
            
        except Exception as e:
            st.error(f"Error checking duplicates: {e}")
            return []
    
    def apply_time_based_discount(self, record_id):
        """
        Apply discount after full price period
        """
        try:
            record = self.db_manager.get_record_by_id(record_id)
            if record is None:
                return False
            
            consignment_start = record.get('consignment_start_date')
            if not consignment_start:
                return False
            
            # Check if in discount period
            from datetime import datetime, timedelta
            
            start_date = datetime.strptime(str(consignment_start), '%Y-%m-%d').date()
            full_price_days = int(self.db_manager.get_config_value('CONSIGNMENT_FULL_PRICE_DAYS', '90'))
            discount_days = int(self.db_manager.get_config_value('CONSIGNMENT_DISCOUNT_DAYS', '90'))
            discount_percent = int(self.db_manager.get_config_value('DISCOUNT_PERCENTAGE', '50'))
            
            today = datetime.now().date()
            days_in_consignment = (today - start_date).days
            
            if days_in_consignment > full_price_days and days_in_consignment <= (full_price_days + discount_days):
                # Apply discount
                current_price = record.get('store_price', 0)
                original_price = record.get('original_consignor_price', current_price)
                discounted_price = original_price * (1 - discount_percent/100)
                
                # Update record
                success = self.db_manager.update_record(record_id, {
                    'store_price': round(discounted_price, 2),
                    'discount_eligible_date': today
                })
                
                return success
            
            return False
            
        except Exception as e:
            st.error(f"Error applying discount: {e}")
            return False
    
    def _get_shipping_cost(self):
        """Get shipping cost from config"""
        try:
            shipping_cost = self.db_manager.get_config_value('SHIPPING_COST', '5.72')
            return float(shipping_cost)
        except:
            return 5.72
    
    def _log_duplicate_check(self, record_data, duplicates):
        """Log duplicate check results"""
        try:
            # This would save to duplicate_check_log table
            # For now, just log to console
            if duplicates:
                st.warning(f"Found {len(duplicates)} potential duplicates")
        except:
            pass