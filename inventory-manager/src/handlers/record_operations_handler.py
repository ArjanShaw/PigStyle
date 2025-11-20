# FILE: inventory-manager/src/handlers/record_operations_handler.py
import streamlit as st
import pandas as pd
from datetime import datetime
import time
import re
import threading
import subprocess
from pathlib import Path
import math

class RecordOperationsHandler:
    def __init__(self, discogs_handler=None, ebay_handler=None):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
    
    def add_inventory_record(self, record_data, condition, genre, search_term):
        """Add inventory record to database with condition-specific pricing"""
        if condition is None:
            raise Exception("condition parameter is required but was None")
        if genre is None:
            raise Exception("genre parameter is required but was None")
            
        print(f"🔴 DEBUG add_inventory_record: condition={condition}, genre={genre}")
        
        release_id = record_data.get('discogs_id')
        
        if not release_id:
            st.error("No release ID found")
            return False, None
        
        # Get format from session state or default
        format_selected = st.session_state.get('format_select', 'Vinyl')
        
        # Get Discogs pricing information - USE MARKETPLACE SEARCH WITH CONDITION FILTERING
        condition_grade = int(condition)
        condition_specific_data = None
        
        print(f"🔴 DEBUG calling get_condition_specific_pricing with condition_grade={condition_grade}")
        
        if self.discogs_handler:
            # Use marketplace search with condition filtering
            with st.spinner(f"Fetching condition-specific pricing (Grade {condition})..."):
                condition_specific_data = self.discogs_handler.get_condition_specific_pricing(
                    str(release_id), 
                    condition_grade
                )
            
            print(f"🔴 DEBUG condition_specific_data result: {condition_specific_data}")
            
            if condition_specific_data:
                # Use condition-specific data from marketplace search
                pricing_data = {
                    'discogs_lowest_price': condition_specific_data.get('discogs_lowest_price'),
                    'discogs_estimated_price': condition_specific_data.get('discogs_median_price'),
                    'image_url': '',
                    'success': True,
                    'condition_specific': True,
                    'discogs_listings_count': condition_specific_data.get('discogs_listings_count', 0)
                }
            else:
                # Fall back to basic release data if no condition-specific data found
                print(f"🔴 DEBUG no condition-specific data found, using basic release data")
                pricing_data = {
                    'discogs_lowest_price': None,
                    'discogs_estimated_price': None,
                    'image_url': '',
                    'success': False,
                    'condition_specific': False
                }
        else:
            st.error("Discogs handler not available")
            return False, None
        
        # Extract result information - use the edited artist name if available
        artist = record_data.get('artist', '')  # This will be the edited version
        title = record_data.get('title', '')    # This will be the edited version
        image_url = record_data.get('image_url', '')
        catalog_number = record_data.get('catalog_number', '')
        discogs_genre = record_data.get('genre', '')  # Store the original Discogs genre
        youtube_url = record_data.get('youtube_url', '')  # Get YouTube URL from record data
        
        # Get eBay pricing if handler is available - USE CONDITION-SPECIFIC
        ebay_pricing = None
        if self.ebay_handler and artist and title:
            with st.spinner("Fetching condition-specific eBay pricing..."):
                ebay_pricing = self.ebay_handler.get_condition_specific_ebay_pricing(
                    artist, 
                    title, 
                    condition_grade
                )
            
            # Fall back to general eBay pricing if condition-specific has few listings
            if not ebay_pricing or ebay_pricing.get('ebay_listings_count', 0) < 3:
                with st.spinner("Falling back to general eBay pricing..."):
                    ebay_pricing = self.ebay_handler.get_ebay_pricing(artist, title)
        
        # Get genre_id for the genre
        genre_id = None
        if genre:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM genres WHERE genre_name = ?', (genre,))
            genre_result = cursor.fetchone()
            if genre_result:
                genre_id = genre_result[0]
            else:
                # Create new genre
                cursor.execute('INSERT INTO genres (genre_name) VALUES (?)', (genre,))
                genre_id = cursor.lastrowid
                conn.commit()
            conn.close()
        
        # Calculate file_at for confirmation message
        file_at_value = self._calculate_file_at(artist, genre)
        
        # Store pricing data in record_data for display
        record_data['discogs_lowest_price'] = pricing_data.get('discogs_lowest_price')
        record_data['discogs_estimated_price'] = pricing_data.get('discogs_estimated_price')
        record_data['discogs_condition_specific'] = pricing_data.get('condition_specific', False)
        record_data['discogs_listings_count'] = pricing_data.get('discogs_listings_count', 0)
        
        # CALCULATE STORE PRICE USING CONFIGURABLE PARAMETERS
        store_price = self._calculate_store_price(
            pricing_data.get('discogs_lowest_price'),
            pricing_data.get('discogs_estimated_price')
        )
        
        if ebay_pricing:
            record_data['ebay_lowest_price'] = ebay_pricing.get('ebay_lowest_price')
            record_data['ebay_median_price'] = ebay_pricing.get('ebay_median_price')
            record_data['ebay_highest_price'] = ebay_pricing.get('ebay_highest_price')
            record_data['ebay_low_shipping'] = ebay_pricing.get('ebay_low_shipping')
            record_data['ebay_listings_count'] = ebay_pricing.get('ebay_listings_count', 0)
            record_data['ebay_total_items_found'] = ebay_pricing.get('ebay_total_items_found', 0)
            record_data['ebay_condition_specific'] = ebay_pricing.get('condition_specific', False)
            record_data['ebay_condition_grade'] = ebay_pricing.get('condition_grade')
        
        # Save to database - include calculated store price
        result_data = {
            'artist': artist,  # Use the edited artist name
            'title': title,    # Use the edited title
            'barcode': '',  # Will be generated by trigger
            'genre_id': genre_id,
            'image_url': image_url,
            'discogs_lowest_price': pricing_data.get('discogs_lowest_price'),
            'discogs_estimated_price': pricing_data.get('discogs_estimated_price'),
            # eBay data - use actual values if available, otherwise NULL
            'ebay_median_price': ebay_pricing.get('ebay_median_price') if ebay_pricing else None,
            'ebay_lowest_price': ebay_pricing.get('ebay_lowest_price') if ebay_pricing else None,
            'ebay_highest_price': ebay_pricing.get('ebay_highest_price') if ebay_pricing else None,
            'ebay_count': ebay_pricing.get('ebay_listings_count') if ebay_pricing else None,
            'ebay_low_shipping': ebay_pricing.get('ebay_low_shipping') if ebay_pricing else None,
            'ebay_low_url': ebay_pricing.get('ebay_search_url') if ebay_pricing else None,
            'catalog_number': catalog_number,
            'format': format_selected,
            'condition': condition,
            'file_at': file_at_value,  # Use calculated file_at
            'store_price': store_price,  # CALCULATED STORE PRICE
            'discogs_genre': discogs_genre,  # Store the original Discogs genre
            'youtube_url': youtube_url  # Include YouTube URL
        }
        
        record_id = st.session_state.db_manager.save_record(result_data)
        
        # Trigger GitHub sync after successful addition
        if record_id:
            self._trigger_github_sync()
        
        return True, record_id

    def _calculate_store_price(self, discogs_lowest_price, discogs_estimated_price):
        """Calculate store price using configurable parameters"""
        # Get current configuration
        lowest_multiplier = float(st.session_state.db_manager.get_config_value('STORE_PRICE_LOWEST_MULTIPLIER', '1.1'))
        estimated_multiplier = float(st.session_state.db_manager.get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', '0.9'))
        minimum_price = float(st.session_state.db_manager.get_config_value('STORE_PRICE_MINIMUM', '4.99'))
        
        candidates = []
        
        if discogs_lowest_price and discogs_lowest_price > 0:
            candidates.append(discogs_lowest_price * lowest_multiplier)
        
        if discogs_estimated_price and discogs_estimated_price > 0:
            candidates.append(discogs_estimated_price * estimated_multiplier)
        
        if candidates:
            raw_price = max(candidates)
            raw_price = max(raw_price, minimum_price)
        else:
            raw_price = minimum_price
        
        # Round to nearest .49 or .99
        store_price = self._round_to_49_or_99(raw_price)
        
        return store_price

    def _round_to_49_or_99(self, price):
        """Round to nearest .49 or .99"""
        if price <= 0:
            return 0.0
        
        base_price = math.floor(price)
        decimal_part = price - base_price
        
        if decimal_part < 0.25:
            return base_price + 0.49
        elif decimal_part < 0.75:
            return base_price + 0.49
        else:
            return base_price + 0.99

    def _calculate_file_at(self, artist, genre):
        """Calculate file_at value for an artist and genre"""
        if not artist:
            return "?"
        
        artist_clean = artist.strip().lower()
        
        if artist_clean.startswith('the '):
            artist_clean = artist_clean[4:]
        
        if artist_clean and artist_clean[0].isdigit():
            number_words = {
                '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
                '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
            }
            first_char = artist_clean[0]
            file_at_letter = number_words.get(first_char, '?')[0].upper()
        elif artist_clean and artist_clean[0].isalpha():
            file_at_letter = artist_clean[0].upper()
        else:
            file_at_letter = "?"
        
        return f"{genre}({file_at_letter})"

    def update_database_record(self, record_data, condition, genre):
        """Update database record"""
        if condition is None:
            raise Exception("condition parameter is required but was None")
        if genre is None:
            raise Exception("genre parameter is required but was None")
            
        print(f"🔴 DEBUG update_database_record: condition={condition}, genre={genre}")
        
        record_id = record_data['id']
        
        # Get genre_id for the genre
        genre_id = None
        if genre:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM genres WHERE genre_name = ?', (genre,))
            genre_result = cursor.fetchone()
            if genre_result:
                genre_id = genre_result[0]
            conn.close()
        
        updates = {
            'condition': condition,
            'genre_id': genre_id
        }
        
        success = st.session_state.db_manager.update_record(record_id, updates)
        
        # Trigger GitHub sync after successful update
        if success:
            self._trigger_github_sync()
            
        return success

    def _trigger_github_sync(self):
        """Trigger GitHub sync in background"""
        if hasattr(st.session_state, 'github_sync_handler'):
            success, message = st.session_state.github_sync_handler.trigger_sync()
            if success:
                print("✅ GitHub sync completed successfully")
            else:
                print(f"❌ GitHub sync failed: {message}")
        else:
            print("❌ GitHub sync handler not available")

    def process_checkout(self, checkout_records):
        """Process checkout of selected records - not available anymore"""
        st.warning("Checkout functionality is not available. The status column has been removed from the database.")
        return 0

    def generate_receipt_content(self, checkout_records):
        """Generate receipt content for checkout records"""
        receipt_lines = []
        receipt_lines.append("PIGSTYLE RECORDS - CHECKOUT RECEIPT")
        receipt_lines.append("=" * 40)
        receipt_lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        receipt_lines.append(f"Items: {len(checkout_records)}")
        receipt_lines.append("")
        
        total = 0
        for i, record in enumerate(checkout_records, 1):
            artist = record.get('artist', 'Unknown Artist')
            title = record.get('title', 'Unknown Title')
            price = record.get('store_price', 0) or 0
            total += price
            
            # Truncate long titles for receipt format
            if len(title) > 30:
                title = title[:27] + "..."
            if len(artist) > 20:
                artist = artist[:17] + "..."
            
            receipt_lines.append(f"{i:2d}. {artist:<20} {title:<30} ${price:>6.2f}")
        
        receipt_lines.append("")
        receipt_lines.append("=" * 40)
        receipt_lines.append(f"TOTAL: ${total:>33.2f}")
        receipt_lines.append("")
        receipt_lines.append("Thank you for your purchase!")
        
        return "\n".join(receipt_lines)