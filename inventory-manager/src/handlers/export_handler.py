import streamlit as st
import pandas as pd
from datetime import datetime
from handlers.draft_csv_handler import DraftCSVHandler

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
        df = pd.read_sql(f'SELECT * FROM records_with_genres WHERE id IN ({placeholders}) AND status = "inventory"', conn, params=selected_ids)
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

    def update_all_ebay_prices(self, ebay_handler):
        """Update eBay prices for all inventory records"""
        if not ebay_handler:
            st.error("eBay handler not available. Check your eBay API credentials.")
            return 0
        
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres WHERE status = "inventory"', conn)
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
                    # Calculate final eBay selling price (ebay_sell_at will be set by trigger)
                    ebay_sell_price = self.price_handler.calculate_ebay_price(ebay_pricing.get('ebay_lowest_price'))
                    
                    # Use update_record to track changes properly
                    updates = {
                        'ebay_median_price': ebay_pricing.get('ebay_median_price'),
                        'ebay_lowest_price': ebay_pricing.get('ebay_lowest_price'),
                        'ebay_highest_price': ebay_pricing.get('ebay_highest_price'),
                        'ebay_count': ebay_pricing.get('ebay_listings_count', 0),
                        'ebay_sell_at': ebay_sell_price
                    }
                    success = st.session_state.db_manager.update_record(record_id, updates)
                    if success:
                        updated_count += 1
                        results.append(f"✅ {artist} - {title}: ${ebay_pricing.get('ebay_median_price', 0):.2f} (found {ebay_pricing.get('ebay_listings_count', 0)} listings)")
                    else:
                        failed_count += 1
                        results.append(f"❌ {artist} - {title}: Database update failed")
                else:
                    failed_count += 1
                    results.append(f"❌ {artist} - {title}: No eBay data found")
                    
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
            st.success(f"✅ eBay update completed!")
            st.write(f"**Results:** {updated_count} updated, {failed_count} failed")
            
        return updated_count

    def update_single_ebay_prices(self, ebay_handler, record_id):
        """Update eBay prices for a single record"""
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
                # Calculate final eBay selling price
                ebay_sell_price = self.price_handler.calculate_ebay_price(ebay_pricing.get('ebay_lowest_price'))
                
                # Use update_record to track changes properly
                updates = {
                    'ebay_median_price': ebay_pricing.get('ebay_median_price'),
                    'ebay_lowest_price': ebay_pricing.get('ebay_lowest_price'),
                    'ebay_highest_price': ebay_pricing.get('ebay_highest_price'),
                    'ebay_count': ebay_pricing.get('ebay_listings_count', 0),
                    'ebay_sell_at': ebay_sell_price
                }
                success = st.session_state.db_manager.update_record(record_id, updates)
                if success:
                    st.success(f"✅ Updated eBay prices for {artist} - {title}")
                    st.write(f"Median: ${ebay_pricing.get('ebay_median_price', 0):.2f}")
                    st.write(f"Lowest: ${ebay_pricing.get('ebay_lowest_price', 0):.2f}")
                    st.write(f"Listings: {ebay_pricing.get('ebay_listings_count', 0)}")
                    st.write(f"Sell At: ${ebay_sell_price:.2f}")
                    return 1
                else:
                    st.error(f"❌ Database update failed for {artist} - {title}")
                    return 0
            else:
                st.warning(f"❌ No eBay data found for {artist} - {title}")
                return 0
                
        except Exception as e:
            st.error(f"❌ Error updating {artist} - {title}: {str(e)}")
            return 0

    def update_all_ebay_sell_at(self):
        """Update eBay sell prices for all inventory records using existing lowest prices"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres WHERE status = "inventory"', conn)
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
            
            status_text.text(f"Updating {i+1}/{len(df)}: {artist} - {title}")
            
            try:
                if ebay_lowest_price and ebay_lowest_price > 0:
                    # Calculate eBay sell price from existing lowest price
                    ebay_sell_price = self.price_handler.calculate_ebay_price(ebay_lowest_price)
                    
                    # Update only the ebay_sell_at field
                    success = st.session_state.db_manager.update_record(record_id, {'ebay_sell_at': ebay_sell_price})
                    if success:
                        updated_count += 1
                        results.append(f"✅ {artist} - {title}: ${ebay_sell_price:.2f} (from ${ebay_lowest_price:.2f})")
                    else:
                        failed_count += 1
                        results.append(f"❌ {artist} - {title}: Database update failed")
                else:
                    failed_count += 1
                    results.append(f"❌ {artist} - {title}: No eBay lowest price available")
                    
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
        
        try:
            if ebay_lowest_price and ebay_lowest_price > 0:
                # Calculate eBay sell price from existing lowest price
                ebay_sell_price = self.price_handler.calculate_ebay_price(ebay_lowest_price)
                
                # Update only the ebay_sell_at field
                success = st.session_state.db_manager.update_record(record_id, {'ebay_sell_at': ebay_sell_price})
                if success:
                    st.success(f"✅ Updated eBay sell price for {artist} - {title}")
                    st.write(f"Lowest Price: ${ebay_lowest_price:.2f}")
                    st.write(f"Sell At: ${ebay_sell_price:.2f}")
                    return 1
                else:
                    st.error(f"❌ Database update failed for {artist} - {title}")
                    return 0
            else:
                st.warning(f"❌ No eBay lowest price available for {artist} - {title}")
                return 0
                
        except Exception as e:
            st.error(f"❌ Error updating {artist} - {title}: {str(e)}")
            return 0