import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import re
import threading
import subprocess
from pathlib import Path
import math
import requests

class RecordOperationsHandler:
    def __init__(self, discogs_handler=None, ebay_handler=None, api_client=None):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
        self.api_client = api_client
    
    def _get_config_value(self, config_key):
        """Get config value from API client"""
        try:
            value = self.api_client.get_config_value(config_key, None)
            if value is None:
                raise ValueError(f"Configuration key '{config_key}' not found")
            return float(value)
        except Exception as e:
            raise ValueError(f"Error getting config '{config_key}': {e}")
    
    def add_inventory_record(self, record_data, genre, search_term, store_credit_option=False, consignor_id=None):
        """Add inventory record to database via API with enhanced consignment features"""
        if genre is None:
            raise Exception("genre parameter is required but was None")
        
        # Check for duplicates BEFORE adding
        from handlers.pricing_validator import PricingValidator
        pricing_validator = PricingValidator(self.api_client, self.discogs_handler, self.ebay_handler)
        duplicates_found = pricing_validator.check_for_duplicates(record_data)
        
        if duplicates_found:
            user = st.session_state.get('user', {})
            user_role = user.get('role', 'consignor')
            
            if user_role != 'admin':
                st.error("❌ **Cannot add duplicate record!**")
                return False, None
            else:
                st.warning("⚠️ **Duplicate detected - you may proceed as admin**")
        
        release_id = record_data.get('discogs_id')
        
        if not release_id:
            st.error("No release ID found")
            return False, None
        
        # Get format from session state or default
        format_selected = st.session_state.get('format_select', 'Vinyl')
        
        # Get Discogs pricing information - USE PRICE SUGGESTIONS
        pricing_data = None
        
        if self.discogs_handler:
            with st.spinner("Fetching Discogs price suggestions..."):
                pricing_data = self.discogs_handler.get_release_statistics_pricing(str(release_id))
        else:
            st.error("Discogs handler not available")
            return False, None
        
        # Extract result information - use the edited artist name if available
        artist = record_data.get('artist', '')  # This will be the edited version
        title = record_data.get('title', '')    # This will be the edited version
        image_url = record_data.get('image_url', '')
        catalog_number = record_data.get('catalog_number', '')
        youtube_url = record_data.get('youtube_url', '')  # Get YouTube URL from record data
        
        # Get selected condition and price from record_data
        selected_condition = record_data.get('selected_condition')
        user_price = record_data.get('user_price')
        
        # Get compilation status from record_data
        compilation = record_data.get('compilation', False)
        
        # Get consignor_id - use provided parameter or from record_data
        if consignor_id is None:
            consignor_id = record_data.get('consignor_id')
        
        # Get commission info from user's master agreement if consignor_id exists
        commission_rate = None
        store_return_days = None
        
        if consignor_id:
            # Try to get user's master agreement details
            user_data = self.api_client.get_user(consignor_id)
            if user_data and user_data.get('agreement_details'):
                commission_rate = user_data['agreement_details'].get('commission_rate')
                store_return_days = user_data['agreement_details'].get('store_return_days')
        
        # If no agreement details, use defaults
        if commission_rate is None:
            try:
                commission_rate = float(self.api_client.get_config_value('DEFAULT_COMMISSION_RATE', '0.20'))
            except:
                commission_rate = 0.20
        
        if store_return_days is None:
            try:
                store_return_days = int(self.api_client.get_config_value('DEFAULT_STORE_RETURN_DAYS', '90'))
            except:
                store_return_days = 90
        
        # Get discogs_genre for mapping
        discogs_genre = record_data.get('discogs_genre', '')
        
        # Get genre_id for the genre using API
        genre_id = None
        if genre:
            genres_df = self.api_client.get_all_genres()
            if not genres_df.empty:
                genre_rows = genres_df[genres_df['genre_name'] == genre]
                if not genre_rows.empty:
                    genre_id = int(genre_rows.iloc[0]['id'])
                else:
                    # Create new genre using API
                    success, new_genre_id = self.api_client.add_genre(genre)
                    if success:
                        genre_id = int(new_genre_id)
                    else:
                        st.error(f"Failed to create new genre: {genre}")
                        return False, None
        
        # Store pricing data in record_data for display
        if pricing_data:
            record_data['price_suggestions'] = pricing_data.get('price_suggestions', {})
        
        # Use user_price as store_price
        store_price = user_price if user_price else 0.0
        
        # Get eBay sell price from record_data if available
        ebay_sell_at = record_data.get('ebay_sell_at', 0.0)
        
        # Set consignment dates if consigning
        consignment_start_date = None
        discount_eligible_date = None
        original_consignor_price = None
        
        if consignor_id:
            consignment_start_date = datetime.now().date()
            try:
                full_price_days = int(self.api_client.get_config_value('CONSIGNMENT_FULL_PRICE_DAYS', '90'))
            except:
                full_price_days = 90
            discount_eligible_date = consignment_start_date + timedelta(days=full_price_days)
            original_consignor_price = store_price
        
        # Save to database via API - SIMPLIFIED VERSION
        try:
            # Prepare data for API
            record_data_to_save = {
                'artist': artist,
                'title': title,
                'barcode': '',
                'genre_id': genre_id,
                'image_url': image_url,
                'catalog_number': catalog_number,
                'format': format_selected,
                'condition': selected_condition,
                'store_price': float(store_price),
                'ebay_sell_at': float(ebay_sell_at) if ebay_sell_at else 0.0,
                'youtube_url': youtube_url,
                'compilation': bool(compilation)
            }
            
            # Add consignor fields only if consignor_id exists
            if consignor_id:
                record_data_to_save['consignor_id'] = int(consignor_id)
                record_data_to_save['commission_rate'] = float(commission_rate)
                record_data_to_save['store_return_days'] = int(store_return_days)
                record_data_to_save['store_credit_option'] = bool(store_credit_option)
                record_data_to_save['consignment_start_date'] = consignment_start_date.isoformat() if consignment_start_date else None
                record_data_to_save['discount_eligible_date'] = discount_eligible_date.isoformat() if discount_eligible_date else None
                record_data_to_save['original_consignor_price'] = float(original_consignor_price) if original_consignor_price else None
            
            # Call API to create record
            base_url = "https://arjanshaw.pythonanywhere.com"
            response = requests.post(
                f"{base_url}/records",
                json=record_data_to_save,
                timeout=10
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == 'success':
                    record_id = response_data.get('record_id')
                    
                    # Save Discogs genre mapping if available
                    if discogs_genre and genre_id:
                        mapping_data = {
                            'discogs_genre': discogs_genre,
                            'local_genre_id': genre_id
                        }
                        mapping_response = requests.post(
                            f"{base_url}/discogs-genre-mappings",
                            json=mapping_data,
                            timeout=5
                        )
                        if mapping_response.status_code == 200:
                            mapping_data = mapping_response.json()
                            if mapping_data.get('status') == 'success':
                                pass  # Success, no need to show message
                    
                    return True, record_id
                else:
                    error_msg = response_data.get('error', 'Unknown error from API')
                    st.error(f"Failed to save record: {error_msg}")
                    return False, None
            else:
                st.error(f"API request failed with status {response.status_code}")
                return False, None
                
        except requests.exceptions.Timeout:
            st.error("API request timed out. Please try again.")
            return False, None
        except Exception as e:
            st.error(f"Error saving record: {str(e)}")
            return False, None

    def update_database_record(self, record_data, genre, store_credit_option=None, user_price=None):
        """Update database record with enhanced consignment features via API"""
        if genre is None:
            raise Exception("genre parameter is required but was None")
        
        record_id = record_data.get('id')
        
        if not record_id:
            st.error("No record ID provided")
            return False
        
        # Get compilation status from record_data
        compilation = record_data.get('compilation', False)
        
        # Get consignment info from record_data
        consignor_id = record_data.get('consignor_id')
        commission_rate = record_data.get('commission_rate')
        store_return_days = record_data.get('store_return_days')
        
        # Get genre_id for the genre using API
        genre_id = None
        if genre:
            genres_df = self.api_client.get_all_genres()
            if not genres_df.empty:
                genre_rows = genres_df[genres_df['genre_name'] == genre]
                if not genre_rows.empty:
                    genre_id = int(genre_rows.iloc[0]['id'])
        
        updates = {
            'genre_id': genre_id,
            'compilation': compilation
        }
        
        # Add consignor fields if provided
        if consignor_id is not None:
            updates['consignor_id'] = int(consignor_id) if consignor_id else None
        
        if commission_rate is not None:
            updates['commission_rate'] = float(commission_rate)
        
        if store_return_days is not None:
            updates['store_return_days'] = int(store_return_days)
        
        # Update store credit option if provided
        if store_credit_option is not None:
            updates['store_credit_option'] = bool(store_credit_option)
        
        # Update price if provided
        if user_price is not None:
            updates['store_price'] = float(user_price)
            updates['original_consignor_price'] = float(user_price)
        
        # If consignor is being added, set consignment dates
        if consignor_id and not record_data.get('consignment_start_date'):
            updates['consignment_start_date'] = datetime.now().date().isoformat()
            try:
                full_price_days = int(self.api_client.get_config_value('CONSIGNMENT_FULL_PRICE_DAYS', '90'))
            except:
                full_price_days = 90
            updates['discount_eligible_date'] = (datetime.now().date() + timedelta(days=full_price_days)).isoformat()
        
        # Call API to update record
        try:
            base_url = "https://arjanshaw.pythonanywhere.com"
            response = requests.put(
                f"{base_url}/records/{record_id}",
                json=updates,
                timeout=10
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == 'success':
                    return True
                else:
                    error_msg = response_data.get('error', 'Unknown error')
                    st.error(f"API returned error: {error_msg}")
                    return False
            else:
                st.error(f"API request failed with status {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            st.error("API request timed out")
            return False
        except Exception as e:
            st.error(f"Error updating record: {str(e)}")
            return False