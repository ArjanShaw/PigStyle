import streamlit as st
import pandas as pd
from datetime import datetime
import time
from handlers.draft_csv_handler import DraftCSVHandler
import math
import requests

class ExportHandler:
    def __init__(self, price_handler, base_url="https://arjanshaw.pythonanywhere.com"):
        self.price_handler = price_handler
        self.base_url = base_url
 
    def export_ebay_list(self):
        """Export selected records as eBay draft listings"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
        
        # Get selected records data using API
        selected_ids = st.session_state.selected_records
        records = self._get_records_by_ids(selected_ids)
        
        if not records:
            st.warning("No records found for the selected IDs")
            return
        
        # Generate eBay formatted TXT
        draft_handler = DraftCSVHandler()
        ebay_content = draft_handler.generate_ebay_txt_from_records(records, self.price_handler)
        
        # Create download button
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ebay_drafts_{timestamp}.txt"
        
        st.download_button(
            label="⬇️ Download eBay Drafts",
            data=ebay_content,
            file_name=filename,
            mime="text/plain",
            key=f"download_ebay_{timestamp}"
        )
        
        st.success(f"✅ eBay draft file ready! {len(records)} records formatted for eBay import.")

    def _round_down_to_49_or_99(self, price):
        """Round down to nearest .49 or .99 that is less than or equal to original price"""
        if price <= 0:
            return 0.0
        
        # Check if price already ends with .49 or .99
        if abs(price % 1 - 0.49) < 0.001 or abs(price % 1 - 0.99) < 0.001:
            return price
        
        base_price = math.floor(price)
        
        # Calculate candidate prices
        candidate_99 = base_price + 0.99
        candidate_49 = base_price + 0.49
        
        # Return the highest candidate that is <= original price
        if candidate_99 <= price:
            return candidate_99
        elif candidate_49 <= price:
            return candidate_49
        else:
            # If both are too high, go down one dollar and use .99
            return (base_price - 1) + 0.99

    def _calculate_ebay_sell_at(self, ebay_lowest_price, ebay_low_shipping, discogs_median_price):
        """Calculate eBay sell price with all rules applied"""
        # Get SHIPPING_COST from config via API
        shipping_cost = self._get_config_value('SHIPPING_COST', '5.72')
        try:
            shipping_cost = float(shipping_cost)
        except (ValueError, TypeError):
            shipping_cost = 5.72
        
        if ebay_lowest_price is not None and ebay_low_shipping is not None:
            # Convert to float to ensure numeric operations
            ebay_lowest_price = float(ebay_lowest_price)
            ebay_low_shipping = float(ebay_low_shipping)
            
            # Calculate ebay_sell_at = ebay_lowest_price + ebay_low_shipping - SHIPPING_COST
            ebay_sell_at_raw = ebay_lowest_price + ebay_low_shipping - shipping_cost
            
            # Ensure ebay_sell_at is not negative - hardcoded minimum of 0.00
            ebay_sell_at_raw = max(ebay_sell_at_raw, 0.00)
            
            # Cap ebay_sell_at at discogs_median_price if available
            if discogs_median_price is not None and discogs_median_price > 0:
                discogs_median = float(discogs_median_price)
                if ebay_sell_at_raw > discogs_median:
                    # If calculated price exceeds Discogs median, use Discogs median rounded down
                    ebay_sell_at = self._round_down_to_49_or_99(discogs_median)
                else:
                    # Use calculated price rounded down
                    ebay_sell_at = self._round_down_to_49_or_99(ebay_sell_at_raw)
            else:
                # No Discogs price, use calculated price rounded down
                ebay_sell_at = self._round_down_to_49_or_99(ebay_sell_at_raw)
        else:
            # No eBay data - use Discogs median price
            if discogs_median_price is not None and discogs_median_price > 0:
                # Round down Discogs median price for eBay
                ebay_sell_at = self._round_down_to_49_or_99(float(discogs_median_price))
            else:
                # No pricing data available
                ebay_sell_at = 0.0
        
        # Apply hardcoded minimum for eBay sell price
        return max(ebay_sell_at, 0.00)

    def update_all_ebay_prices(self, ebay_handler):
        """Update eBay prices for all inventory records - DO NOT update ebay_sell_at here"""
        if not ebay_handler:
            st.error("eBay handler not available. Check your eBay API credentials.")
            return 0
        
        # Get all records using API
        records = self._get_all_records()
        
        if not records:
            st.info("No records found to update")
            return 0
        
        updated_count = 0
        failed_count = 0
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        with results_container:
            st.subheader("Update Progress")
            results_placeholder = st.empty()
        
        results = []
        
        for i, record in enumerate(records):
            artist = record.get('artist', '')
            title = record.get('title', '')
            record_id = record.get('id')
            
            status_text.text(f"Updating {i+1}/{len(records)}: {artist} - {title}")
            
            try:
                ebay_pricing = ebay_handler.get_ebay_pricing(artist, title)
                if ebay_pricing:
                    # Get eBay pricing data but DO NOT calculate ebay_sell_at here
                    ebay_lowest_price = float(ebay_pricing.get('ebay_lowest_price', 0))
                    ebay_low_shipping = float(ebay_pricing.get('ebay_low_shipping', 0))
                    
                    # Update record via API - NO ebay_sell_at update
                    updates = {
                        'ebay_median_price': ebay_pricing.get('ebay_median_price'),
                        'ebay_lowest_price': ebay_lowest_price,
                        'ebay_highest_price': ebay_pricing.get('ebay_highest_price'),
                        'ebay_count': ebay_pricing.get('ebay_listings_count', 0),
                        'ebay_low_shipping': ebay_low_shipping,
                        'ebay_low_url': ebay_pricing.get('ebay_search_url', '')
                    }
                    success = self._update_record(record_id, updates)
                    if success:
                        updated_count += 1
                        results.append(f"✅ {artist} - {title}: {ebay_pricing.get('ebay_listings_count', 0)} listings")
                    else:
                        failed_count += 1
                        results.append(f"❌ {artist} - {title}: Database update failed")
                else:
                    # No eBay data found - only clear eBay pricing fields, leave ebay_sell_at unchanged
                    updates = {
                        'ebay_median_price': None,
                        'ebay_lowest_price': None,
                        'ebay_highest_price': None,
                        'ebay_count': 0,
                        'ebay_low_shipping': None,
                        'ebay_low_url': None
                    }
                    success = self._update_record(record_id, updates)
                    if success:
                        updated_count += 1
                        results.append(f"✅ {artist} - {title}: No eBay data found")
                    else:
                        failed_count += 1
                        results.append(f"❌ {artist} - {title}: Database update failed")
                    
            except Exception as e:
                failed_count += 1
                results.append(f"❌ {artist} - {title}: {str(e)}")
            
            # Update progress
            progress_bar.progress((i + 1) / len(records))
            
            # Update results display every 5 records or at the end
            if (i + 1) % 5 == 0 or (i + 1) == len(records):
                with results_placeholder:
                    # Show last 10 results
                    display_results = results[-10:] if len(results) > 10 else results
                    for result in display_results:
                        st.write(result)
        
        status_text.empty()
        progress_bar.empty()
        
        # Show final summary
        with results_container:
            st.success(f"✅ eBay prices update completed!")
            st.write(f"**Results:** {updated_count} updated, {failed_count} failed")
            
        return updated_count

    def update_single_ebay_prices(self, ebay_handler, record_id):
        """Update eBay prices for a single record - DO NOT update ebay_sell_at here"""
        if not ebay_handler:
            st.error("eBay handler not available. Check your eBay API credentials.")
            return 0
        
        # Get single record using API
        record = self._get_record_by_id(record_id)
        if not record:
            st.error(f"Record ID {record_id} not found")
            return 0
        
        artist = record.get('artist', '')
        title = record.get('title', '')
        
        try:
            ebay_pricing = ebay_handler.get_ebay_pricing(artist, title)
            if ebay_pricing:
                # Get eBay pricing data but DO NOT calculate ebay_sell_at here
                ebay_lowest_price = float(ebay_pricing.get('ebay_lowest_price', 0))
                ebay_low_shipping = float(ebay_pricing.get('ebay_low_shipping', 0))
                
                # Update record via API - NO ebay_sell_at update
                updates = {
                    'ebay_median_price': ebay_pricing.get('ebay_median_price'),
                    'ebay_lowest_price': ebay_lowest_price,
                    'ebay_highest_price': ebay_pricing.get('ebay_highest_price'),
                    'ebay_count': ebay_pricing.get('ebay_listings_count', 0),
                    'ebay_low_shipping': ebay_low_shipping,
                    'ebay_low_url': ebay_pricing.get('ebay_search_url', '')
                }
                success = self._update_record(record_id, updates)
                if success:
                    st.success(f"✅ Updated eBay prices for {artist} - {title}")
                    return 1
                else:
                    st.error(f"❌ Database update failed for {artist} - {title}")
                    return 0
            else:
                # No eBay data found - only clear eBay pricing fields, leave ebay_sell_at unchanged
                updates = {
                    'ebay_median_price': None,
                    'ebay_lowest_price': None,
                    'ebay_highest_price': None,
                    'ebay_count': 0,
                    'ebay_low_shipping': None,
                    'ebay_low_url': None
                }
                success = self._update_record(record_id, updates)
                if success:
                    st.success(f"✅ Updated {artist} - {title}: No eBay data found")
                    return 1
                else:
                    st.error(f"❌ Database update failed for {artist} - {title}")
                    return 0
                
        except Exception as e:
            st.error(f"❌ Error updating {artist} - {title}: {str(e)}")
            return 0

    def update_all_ebay_sell_at(self):
        """Update eBay sell prices for all inventory records using existing lowest prices"""
        # Get all records using API
        records = self._get_all_records()
        
        if not records:
            st.info("No records found to update")
            return 0
        
        updated_count = 0
        failed_count = 0
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        with results_container:
            st.subheader("Update Progress")
            results_placeholder = st.empty()
        
        results = []
        
        for i, record in enumerate(records):
            artist = record.get('artist', '')
            title = record.get('title', '')
            record_id = record.get('id')
            ebay_lowest_price = record.get('ebay_lowest_price')
            ebay_low_shipping = record.get('ebay_low_shipping')
            discogs_median_price = record.get('discogs_median_price')
            
            status_text.text(f"Updating {i+1}/{len(records)}: {artist} - {title}")
            
            try:
                # Use the unified calculation function
                ebay_sell_at = self._calculate_ebay_sell_at(ebay_lowest_price, ebay_low_shipping, discogs_median_price)
                
                # Update only the ebay_sell_at field
                success = self._update_record(record_id, {'ebay_sell_at': ebay_sell_at})
                if success:
                    updated_count += 1
                    results.append(f"✅ {artist} - {title}")
                else:
                    failed_count += 1
                    results.append(f"❌ {artist} - {title}: Database update failed")
                    
            except Exception as e:
                failed_count += 1
                results.append(f"❌ {artist} - {title}: {str(e)}")
            
            # Update progress
            progress_bar.progress((i + 1) / len(records))
            
            # Update results display every 5 records or at the end
            if (i + 1) % 5 == 0 or (i + 1) == len(records):
                with results_placeholder:
                    # Show last 10 results
                    display_results = results[-10:] if len(results) > 10 else results
                    for result in display_results:
                        st.write(result)
        
        status_text.empty()
        progress_bar.empty()
        
        # Show final summary
        with results_container:
            st.success(f"✅ eBay sell price update completed!")
            st.write(f"**Results:** {updated_count} updated, {failed_count} failed")
            
        return updated_count

    def update_single_ebay_sell_at(self, record_id):
        """Update eBay sell price for a single record using existing lowest price"""
        # Get single record using API
        record = self._get_record_by_id(record_id)
        if not record:
            st.error(f"Record ID {record_id} not found")
            return 0
        
        artist = record.get('artist', '')
        title = record.get('title', '')
        ebay_lowest_price = record.get('ebay_lowest_price')
        ebay_low_shipping = record.get('ebay_low_shipping')
        discogs_median_price = record.get('discogs_median_price')
        
        try:
            # Use the unified calculation function
            ebay_sell_at = self._calculate_ebay_sell_at(ebay_lowest_price, ebay_low_shipping, discogs_median_price)
            
            # Update only the ebay_sell_at field
            success = self._update_record(record_id, {'ebay_sell_at': ebay_sell_at})
            if success:
                st.success(f"✅ Updated eBay sell price for {artist} - {title}")
                return 1
            else:
                st.error(f"❌ Database update failed for {artist} - {title}")
                return 0
                
        except Exception as e:
            st.error(f"❌ Error updating {artist} - {title}: {str(e)}")
            return 0
    
    def _get_all_records(self):
        """Get all records via API"""
        try:
            response = requests.get(f"{self.base_url}/records?limit=1000")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('records', [])
            return []
        except Exception as e:
            st.error(f"Error getting all records: {e}")
            return []
    
    def _get_record_by_id(self, record_id):
        """Get single record via API"""
        try:
            response = requests.get(f"{self.base_url}/records/{record_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"Error getting record: {e}")
            return None
    
    def _get_records_by_ids(self, record_ids):
        """Get records by IDs via API"""
        try:
            response = requests.post(
                f"{self.base_url}/records/by-ids",
                json={'record_ids': record_ids}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('records', [])
            return []
        except Exception as e:
            st.error(f"Error getting records by IDs: {e}")
            return []
    
    def _update_record(self, record_id, updates):
        """Update record via API"""
        try:
            response = requests.put(
                f"{self.base_url}/records/{record_id}",
                json=updates
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error updating record: {e}")
            return False
    
    def _get_config_value(self, config_key, default=None):
        """Get config value via API"""
        try:
            response = requests.get(f"{self.base_url}/config/{config_key}")
            if response.status_code == 200:
                data = response.json()
                return data.get('config_value', default)
            return default
        except Exception as e:
            st.error(f"Error getting config: {e}")
            return default