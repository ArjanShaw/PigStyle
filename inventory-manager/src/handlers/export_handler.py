import streamlit as st
import pandas as pd
from datetime import datetime
import time
from handlers.draft_csv_handler import DraftCSVHandler
import math

class ExportHandler:
    def __init__(self, price_handler, genre_handler):
        self.price_handler = price_handler
        self.genre_handler = genre_handler

    def export_ebay_list(self):
        """Export selected records as eBay draft listings"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
        
        # Get selected records data
        selected_ids = st.session_state.selected_records
        placeholders = ','.join(['?'] * len(selected_ids))
        
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql(f'SELECT * FROM records_with_genres WHERE id IN ({placeholders})', conn, params=selected_ids)
        conn.close()
        
        records_list = df.to_dict('records')
        
        # Generate eBay formatted TXT
        draft_handler = DraftCSVHandler()
        ebay_content = draft_handler.generate_ebay_txt_from_records(records_list, self.price_handler)
        
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
        
        st.success(f"✅ eBay draft file ready! {len(records_list)} records formatted for eBay import.")

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
        # Get SHIPPING_COST from config
        shipping_cost = st.session_state.db_manager.get_config_value('SHIPPING_COST', '5.72')
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
        
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres', conn)
        conn.close()
        
        updated_count = 0
        failed_count = 0
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        with results_container:
            st.subheader("Update Progress")
            results_placeholder = st.empty()
        
        results = []
        
        for i, (_, record) in enumerate(df.iterrows()):
            artist = record.get('artist', '')
            title = record.get('title', '')
            record_id = record.get('id')
            
            status_text.text(f"Updating {i+1}/{len(df)}: {artist} - {title}")
            
            try:
                ebay_pricing = ebay_handler.get_ebay_pricing(artist, title)
                if ebay_pricing:
                    # Get eBay pricing data but DO NOT calculate ebay_sell_at here
                    ebay_lowest_price = float(ebay_pricing.get('ebay_lowest_price', 0))
                    ebay_low_shipping = float(ebay_pricing.get('ebay_low_shipping', 0))
                    
                    # Use update_record to track changes properly - NO ebay_sell_at update
                    updates = {
                        'ebay_median_price': ebay_pricing.get('ebay_median_price'),
                        'ebay_lowest_price': ebay_lowest_price,
                        'ebay_highest_price': ebay_pricing.get('ebay_highest_price'),
                        'ebay_count': ebay_pricing.get('ebay_listings_count', 0),
                        'ebay_low_shipping': ebay_low_shipping,
                        'ebay_low_url': ebay_pricing.get('ebay_search_url', '')
                    }
                    success = st.session_state.db_manager.update_record(record_id, updates)
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
                    success = st.session_state.db_manager.update_record(record_id, updates)
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
            progress_bar.progress((i + 1) / len(df))
            
            # Update results display every 5 records or at the end
            if (i + 1) % 5 == 0 or (i + 1) == len(df):
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
        
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres WHERE id = ?', conn, params=(record_id,))
        conn.close()
        
        if len(df) == 0:
            st.error(f"Record ID {record_id} not found")
            return 0
        
        record = df.iloc[0]
        artist = record.get('artist', '')
        title = record.get('title', '')
        
        try:
            ebay_pricing = ebay_handler.get_ebay_pricing(artist, title)
            if ebay_pricing:
                # Get eBay pricing data but DO NOT calculate ebay_sell_at here
                ebay_lowest_price = float(ebay_pricing.get('ebay_lowest_price', 0))
                ebay_low_shipping = float(ebay_pricing.get('ebay_low_shipping', 0))
                
                # Use update_record to track changes properly - NO ebay_sell_at update
                updates = {
                    'ebay_median_price': ebay_pricing.get('ebay_median_price'),
                    'ebay_lowest_price': ebay_lowest_price,
                    'ebay_highest_price': ebay_pricing.get('ebay_highest_price'),
                    'ebay_count': ebay_pricing.get('ebay_listings_count', 0),
                    'ebay_low_shipping': ebay_low_shipping,
                    'ebay_low_url': ebay_pricing.get('ebay_search_url', '')
                }
                success = st.session_state.db_manager.update_record(record_id, updates)
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
                success = st.session_state.db_manager.update_record(record_id, updates)
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
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres', conn)
        conn.close()
        
        updated_count = 0
        failed_count = 0
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        with results_container:
            st.subheader("Update Progress")
            results_placeholder = st.empty()
        
        results = []
        
        for i, (_, record) in enumerate(df.iterrows()):
            artist = record.get('artist', '')
            title = record.get('title', '')
            record_id = record.get('id')
            ebay_lowest_price = record.get('ebay_lowest_price')
            ebay_low_shipping = record.get('ebay_low_shipping')
            discogs_median_price = record.get('discogs_median_price')
            
            status_text.text(f"Updating {i+1}/{len(df)}: {artist} - {title}")
            
            try:
                # Use the unified calculation function
                ebay_sell_at = self._calculate_ebay_sell_at(ebay_lowest_price, ebay_low_shipping, discogs_median_price)
                
                # Update only the ebay_sell_at field
                success = st.session_state.db_manager.update_record(record_id, {'ebay_sell_at': ebay_sell_at})
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
            progress_bar.progress((i + 1) / len(df))
            
            # Update results display every 5 records or at the end
            if (i + 1) % 5 == 0 or (i + 1) == len(df):
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
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres WHERE id = ?', conn, params=(record_id,))
        conn.close()
        
        if len(df) == 0:
            st.error(f"Record ID {record_id} not found")
            return 0
        
        record = df.iloc[0]
        artist = record.get('artist', '')
        title = record.get('title', '')
        ebay_lowest_price = record.get('ebay_lowest_price')
        ebay_low_shipping = record.get('ebay_low_shipping')
        discogs_median_price = record.get('discogs_median_price')
        
        try:
            # Use the unified calculation function
            ebay_sell_at = self._calculate_ebay_sell_at(ebay_lowest_price, ebay_low_shipping, discogs_median_price)
            
            # Update only the ebay_sell_at field
            success = st.session_state.db_manager.update_record(record_id, {'ebay_sell_at': ebay_sell_at})
            if success:
                st.success(f"✅ Updated eBay sell price for {artist} - {title}")
                return 1
            else:
                st.error(f"❌ Database update failed for {artist} - {title}")
                return 0
                
        except Exception as e:
            st.error(f"❌ Error updating {artist} - {title}: {str(e)}")
            return 0