import streamlit as st
import pandas as pd
from datetime import datetime
import time
import io
import csv

class EBayTab:
    def __init__(self, ebay_handler, gallery_json_manager):
        self.ebay_handler = ebay_handler
        self.gallery_json_manager = gallery_json_manager

    def render(self):
        st.header("🛒 eBay Management")
        
        # eBay Pricing Strategy
        with st.expander("💰 eBay Pricing Strategy", expanded=True):
            st.write("""
            **eBay Sell Price Calculation:**
            1. Find lowest eBay listing price + shipping cost
            2. Subtract configured shipping cost ($5.72)
            3. Cap at Discogs median price if available
            4. Round down to nearest .49 or .99 price point
            5. Apply minimum price of $0.00
            
            **Note:** Use the buttons below to update eBay data and calculate sell prices.
            """)
            
            # Test record input
            st.subheader("Test Single Record")
            col1, col2 = st.columns([1, 1])
            with col1:
                test_record_id = st.text_input("Record ID for testing:", placeholder="Enter record ID", key="ebay_test_record_id")
            
            # eBay pricing action buttons
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🔄 Update eBay Prices", width='stretch', help="Call eBay API to update pricing data for all inventory"):
                    if test_record_id and test_record_id.strip():
                        self._update_single_ebay_prices(test_record_id.strip())
                    else:
                        self._update_all_ebay_prices()
            with col2:
                if st.button("💰 Update eBay Sell At", width='stretch', help="Calculate eBay sell prices from existing lowest prices"):
                    if test_record_id and test_record_id.strip():
                        self._update_single_ebay_sell_at(test_record_id.strip())
                    else:
                        self._update_all_ebay_sell_at()
        
        # Import eBay Listings
        with st.expander("📥 Import eBay Listings", expanded=True):
            st.subheader("Upload Current eBay Listings CSV")
            
            uploaded_file = st.file_uploader(
                "Upload eBay active listings CSV",
                type=['csv'],
                help="Upload CSV from eBay with your current active listings"
            )
            
            if uploaded_file is not None:
                try:
                    # Read the CSV file
                    content = uploaded_file.getvalue().decode('utf-8')
                    csv_reader = csv.reader(io.StringIO(content))
                    
                    # Skip the info line and header
                    lines = list(csv_reader)
                    if len(lines) < 2:
                        st.error("Invalid CSV file - not enough lines")
                        return
                    
                    # Parse the data
                    listings_data = []
                    header = lines[1]  # Second line is header
                    
                    for i, row in enumerate(lines[2:], start=2):  # Start from third line
                        if len(row) >= 12:  # Ensure we have enough columns
                            listing = {
                                'action': row[0],
                                'category': row[1],
                                'item_number': row[2],
                                'title': row[3],
                                'site': row[4],
                                'currency': row[5],
                                'start_price': row[6],
                                'buy_it_now_price': row[7],
                                'quantity': row[8],
                                'relationship': row[9],
                                'relationship_details': row[10],
                                'sku': row[11]
                            }
                            listings_data.append(listing)
                    
                    st.success(f"✅ Successfully parsed {len(listings_data)} eBay listings")
                    
                    # Show preview
                    if listings_data:
                        st.subheader("Listings Preview")
                        preview_df = pd.DataFrame(listings_data[:10])  # Show first 10
                        st.dataframe(preview_df)
                        
                        # Process button
                        if st.button("🔗 Match Listings to Database", width='stretch'):
                            self._process_ebay_listings(listings_data)
                            
                except Exception as e:
                    st.error(f"Error processing CSV file: {str(e)}")
        
        # Export eBay Draft Listings
        with st.expander("📤 Export eBay Draft Listings", expanded=True):
            st.subheader("Generate Draft Listings CSV")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                num_listings = st.number_input(
                    "Number of listings to export:",
                    min_value=1,
                    max_value=1000,
                    value=50,
                    help="Number of records to include in draft CSV"
                )
            
            with col2:
                if st.button("🛒 Export eBay Draft CSV", width='stretch'):
                    self._export_ebay_draft_csv(num_listings)
        
        # Show individual listings table if available
        self._render_individual_listings_table()

    def _update_all_ebay_prices(self):
        """Update eBay prices for all inventory records"""
        if not self.ebay_handler:
            st.error("eBay handler not available. Check your eBay API credentials.")
            return
        
        updated_count = self._update_all_ebay_prices_internal()
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time

    def _update_single_ebay_prices(self, record_id):
        """Update eBay prices for a single record"""
        if not self.ebay_handler:
            st.error("eBay handler not available. Check your eBay API credentials.")
            return
        
        updated_count = self._update_single_ebay_prices_internal(record_id)
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time

    def _update_all_ebay_sell_at(self):
        """Update eBay sell prices for all inventory records using existing lowest prices"""
        updated_count = self._update_all_ebay_sell_at_internal()
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time

    def _update_single_ebay_sell_at(self, record_id):
        """Update eBay sell price for a single record using existing lowest price"""
        updated_count = self._update_single_ebay_sell_at_internal(record_id)
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time

    def _process_ebay_listings(self, listings_data):
        """Process eBay listings and match them to database records"""
        st.subheader("Matching eBay Listings to Database")
        
        matched_count = 0
        updated_count = 0
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Create containers for results display
        results_container = st.container()
        
        with results_container:
            st.write("Matching progress:")
            results_placeholder = st.empty()
        
        results = []
        matched_listings = []
        unmatched_listings = []
        
        for i, listing in enumerate(listings_data):
            item_number = listing.get('item_number', '')
            title = listing.get('title', '')
            sku = listing.get('sku', '')
            
            status_text.text(f"Processing {i+1}/{len(listings_data)}: {title}")
            
            try:
                # Try to find matching record by SKU first
                record = None
                if sku:
                    # SKU might be in format ARTIST-TITLE-FORMAT
                    # Try to find by artist and title
                    if ' - ' in title:
                        artist, record_title = title.split(' - ', 1)
                        record = self._find_record_by_artist_title(artist.strip(), record_title.strip())
                
                if not record and ' - ' in title:
                    # Fallback: try to split title and search
                    artist, record_title = title.split(' - ', 1)
                    record = self._find_record_by_artist_title(artist.strip(), record_title.strip())
                
                if record:
                    matched_count += 1
                    # Update the record with eBay item number
                    success = st.session_state.db_manager.update_record(
                        record['id'], 
                        {'ebay_item_number': item_number}
                    )
                    if success:
                        updated_count += 1
                        results.append(f"✅ Matched: {title} → {item_number}")
                        matched_listings.append({
                            'title': title,
                            'item_number': item_number,
                            'record_id': record['id'],
                            'artist': record.get('artist', 'Unknown'),
                            'status': 'MATCHED'
                        })
                    else:
                        results.append(f"❌ Failed to update: {title}")
                        unmatched_listings.append({
                            'title': title,
                            'item_number': item_number,
                            'status': 'FAILED_UPDATE'
                        })
                else:
                    results.append(f"❌ No match found: {title}")
                    unmatched_listings.append({
                        'title': title,
                        'item_number': item_number,
                        'status': 'NO_MATCH'
                    })
                    
            except Exception as e:
                results.append(f"❌ Error: {title} - {str(e)}")
                unmatched_listings.append({
                    'title': title,
                    'item_number': item_number,
                    'status': 'ERROR',
                    'error': str(e)
                })
            
            # Update progress
            progress_bar.progress((i + 1) / len(listings_data))
            
            # Update results display every 5 records or at the end
            if (i + 1) % 5 == 0 or (i + 1) == len(listings_data):
                with results_placeholder:
                    # Show last 10 results
                    display_results = results[-10:] if len(results) > 10 else results
                    for result in display_results:
                        st.write(result)
        
        status_text.empty()
        progress_bar.empty()
        
        # Show final summary with ALL listings in a scrollable table
        with results_container:
            st.success(f"✅ eBay listings processing completed!")
            st.write(f"**Results:** {matched_count} matched, {updated_count} updated out of {len(listings_data)} listings")
            
            # Create combined results table with status
            all_results = matched_listings + unmatched_listings
            
            if all_results:
                st.subheader("All Listings Results")
                
                # Create a DataFrame for display
                display_data = []
                for listing in all_results:
                    status_icon = "✅" if listing['status'] == 'MATCHED' else "❌"
                    status_text = {
                        'MATCHED': 'Matched & Updated',
                        'NO_MATCH': 'No Database Match',
                        'FAILED_UPDATE': 'Match Found but Update Failed',
                        'ERROR': 'Error Processing'
                    }.get(listing['status'], listing['status'])
                    
                    display_data.append({
                        'Status': f"{status_icon} {status_text}",
                        'Title': listing['title'],
                        'eBay Item #': listing['item_number'],
                        'Record ID': listing.get('record_id', 'N/A'),
                        'Artist': listing.get('artist', 'N/A')
                    })
                
                df = pd.DataFrame(display_data)
                
                # Display in a scrollable container
                st.dataframe(
                    df, 
                    width='stretch',
                    height=400  # Fixed height with scrollbar
                )
                
                # Export results option
                if st.button("📊 Export Results CSV", width='stretch'):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"ebay_listing_matches_{timestamp}.csv"
                    csv_data = df.to_csv(index=False)
                    
                    st.download_button(
                        label="⬇️ Download Results CSV",
                        data=csv_data,
                        file_name=filename,
                        mime="text/csv",
                        width='stretch',
                        key=f"download_ebay_results_{timestamp}"
                    )
        
        # Trigger JSON rebuild to include eBay item numbers
        if updated_count > 0 and self.gallery_json_manager:
            self.gallery_json_manager.trigger_rebuild(async_mode=True)

    def _find_record_by_artist_title(self, artist, title):
        """Find a record by artist and title"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql(
            'SELECT * FROM records_with_genres WHERE artist LIKE ? AND title LIKE ?',
            conn,
            params=(f'%{artist}%', f'%{title}%')
        )
        conn.close()
        
        if len(df) > 0:
            return df.iloc[0].to_dict()
        return None

    def _export_ebay_draft_csv(self, num_listings):
        """Export eBay draft listings CSV"""
        st.subheader("Generating eBay Draft Listings")
        
        # Get records sorted by eBay sell price descending, without eBay item numbers
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql(f'''
            SELECT * FROM records_with_genres 
            WHERE ebay_item_number IS NULL OR ebay_item_number = ''
            ORDER BY ebay_sell_at DESC 
            LIMIT {num_listings}
        ''', conn)
        conn.close()
        
        if len(df) == 0:
            st.warning("No records found without eBay item numbers")
            return
        
        # Generate CSV content
        output = io.StringIO()
        
        # Write info line
        output.write("#INFO,Version=0.0.2,Template= eBay-draft-listings-template_US,,,,,,,,,\n")
        
        # Write headers
        headers = [
            "Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8)",
            "Custom label (SKU)",
            "Category ID",
            "Title",
            "UPC",
            "Price",
            "Quantity",
            "Item photo URL",
            "Condition ID",
            "Description",
            "C:Artist"
        ]
        output.write(",".join(headers) + "\n")
        
        # Write data rows
        for _, record in df.iterrows():
            row_data = self._format_record_for_ebay_draft(record)
            if row_data:
                row_values = [str(row_data.get(header, "")) for header in headers]
                output.write(",".join(row_values) + "\n")
        
        csv_content = output.getvalue()
        
        # Create download button
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ebay_draft_listings_{timestamp}.csv"
        
        st.download_button(
            label=f"⬇️ Download eBay Draft CSV ({len(df)} listings)",
            data=csv_content,
            file_name=filename,
            mime="text/csv",
            width='stretch',
            key=f"download_ebay_draft_{timestamp}"
        )
        
        st.success(f"✅ eBay draft CSV ready! {len(df)} records formatted for eBay import.")

    def _format_record_for_ebay_draft(self, record):
        """Format a single record for eBay draft import"""
        # Map format to eBay category ID
        category_map = {
            "Vinyl": "176985",
            "CDs": "176984", 
            "Cassettes": "176983"
        }
        
        # Map condition to eBay condition ID
        condition_map = {
            "1": "3000",
            "2": "3000",  
            "3": "3000",
            "4": "3000",
            "5": "1000",
        }
        
        # Get basic fields
        artist = record.get('artist', 'Unknown Artist')
        title = record.get('title', 'Unknown Title')
        format_type = record.get('format', 'Vinyl')
        condition = record.get('condition', '4')
        barcode = record.get('barcode', '')
        image_url = record.get('image_url', '')
        ebay_sell_at = record.get('ebay_sell_at', 0)
        
        # Simple SKU from artist and title
        sku = f"{artist.replace(' ', '').upper()}-{title.replace(' ', '').upper()}-{format_type.upper()}"[:30]
        
        # Simple description
        description = f"{artist} - {title}"
        
        # Title includes artist
        ebay_title = f"{artist} - {title}"
        
        return {
            "Action(SiteID=US|Country=US|Currency=USD|Version=1193|CC=UTF-8)": "Draft",
            "Custom label (SKU)": sku,
            "Category ID": category_map.get(format_type, "176985"),
            "Title": ebay_title,
            "UPC": barcode,
            "Price": f"{float(ebay_sell_at):.2f}" if ebay_sell_at else "0.00",
            "Quantity": "1",
            "Item photo URL": image_url,
            "Condition ID": condition_map.get(condition, "3000"),
            "Description": description,
            "C:Artist": artist,
        }

    def _render_individual_listings_table(self):
        """Render a table with individual eBay listings showing base price and shipping costs"""
        if 'api_details' not in st.session_state:
            return
            
        # Find the most recent eBay search response
        recent_ebay_response = None
        recent_ebay_title = None
        for api_title, details in st.session_state.api_details.items():
            if "eBay Search API" in api_title and 'response' in details:
                recent_ebay_response = details['response']
                recent_ebay_title = api_title
                break
        
        if not recent_ebay_response:
            return
            
        with st.expander("📊 Individual eBay Listings Analysis", expanded=False):
            st.subheader("Individual Listings Analysis")
            
            # Get shipping cost from config for CALC items
            shipping_cost = st.session_state.db_manager.get_config_value('SHIPPING_COST', '5.72')
            try:
                shipping_cost = float(shipping_cost)
            except (ValueError, TypeError):
                shipping_cost = 5.72
            
            # Extract item summaries from eBay response
            item_summaries = recent_ebay_response.get('itemSummaries', [])
            
            # Create table data with proper numeric values for sorting
            table_data = []
            for item in item_summaries:
                # Get base price
                price_data = item.get('price', {})
                base_price = float(price_data.get('value', 0))
                
                # Determine shipping type and cost
                shipping_info = self._extract_shipping_info(item)
                shipping_type = shipping_info['type']
                shipping_cost_value = shipping_info['cost']
                
                # Calculate assumed shipping cost - only for CALC shipping, otherwise null
                assumed_shipping_cost = None
                if shipping_type == 'CALC':
                    assumed_shipping_cost = shipping_cost
                
                # Calculate base + shipping (use actual shipping cost when available, assumed for CALC)
                if shipping_type == 'CALC':
                    base_and_shipping = base_price + shipping_cost
                elif shipping_cost_value is not None:
                    base_and_shipping = base_price + shipping_cost_value
                else:
                    base_and_shipping = base_price  # For FREE shipping
                
                # Get URL
                item_url = item.get('itemWebUrl', '')
                
                # Create table row with numeric values for sorting
                table_data.append({
                    'Title': item.get('title', '')[:80] + '...' if len(item.get('title', '')) > 80 else item.get('title', ''),
                    'Base Price': base_price,
                    'Shipping Type': shipping_type,
                    'Shipping Cost': shipping_cost_value,
                    'Assumed Shipping Cost': assumed_shipping_cost,
                    'Base + Shipping': base_and_shipping,
                    'URL': item_url
                })
            
            # Sort by Base + Shipping to find the cheapest total cost
            table_data.sort(key=lambda x: x['Base + Shipping'])
            
            # Create and display dataframe with proper column configuration
            if table_data:
                df = pd.DataFrame(table_data)
                
                # Configure columns for proper display and sorting
                column_config = {
                    "Title": st.column_config.TextColumn("Title"),
                    "Base Price": st.column_config.NumberColumn(
                        "Base Price",
                        format="$%.2f"
                    ),
                    "Shipping Type": st.column_config.TextColumn("Shipping Type"),
                    "Shipping Cost": st.column_config.NumberColumn(
                        "Shipping Cost",
                        format="$%.2f"
                    ),
                    "Assumed Shipping Cost": st.column_config.NumberColumn(
                        "Assumed Shipping Cost",
                        format="$%.2f"
                    ),
                    "Base + Shipping": st.column_config.NumberColumn(
                        "Base + Shipping",
                        format="$%.2f"
                    ),
                    "URL": st.column_config.LinkColumn("URL")
                }
                
                st.dataframe(
                    df,
                    width='stretch',
                    height=400,
                    hide_index=True,
                    column_config=column_config
                )

    def _extract_shipping_info(self, item):
        """Extract shipping information from eBay item data"""
        try:
            # Check shipping options first
            shipping_options = item.get('shippingOptions', [])
            if shipping_options:
                for option in shipping_options:
                    shipping_cost_type = option.get('shippingCostType', '')
                    if shipping_cost_type == 'CALCULATED':
                        return {'type': 'CALC', 'cost': None}
                    elif shipping_cost_type == 'FIXED':
                        shipping_cost = option.get('shippingCost', {})
                        if 'value' in shipping_cost:
                            cost = float(shipping_cost['value'])
                            return {'type': 'FIXED', 'cost': cost}
            
            # Check for calculated shipping in shippingCostSummary
            shipping_cost_summary = item.get('shippingCostSummary', {})
            if shipping_cost_summary:
                shipping_cost_type = shipping_cost_summary.get('shippingCostType', '')
                if shipping_cost_type == 'CALCULATED':
                    return {'type': 'CALC', 'cost': None}
                elif shipping_cost_type == 'FIXED':
                    shipping_cost = shipping_cost_summary.get('shippingCost', {})
                    if 'value' in shipping_cost:
                        cost = float(shipping_cost['value'])
                        return {'type': 'FIXED', 'cost': cost}
            
            # Check for fixed shipping cost
            if 'shippingCostFixed' in item:
                cost = float(item['shippingCostFixed'])
                return {'type': 'FIXED', 'cost': cost}
            
            # If no shipping cost found, assume free shipping
            return {'type': 'FREE', 'cost': 0}
                
        except Exception as e:
            return {'type': 'FREE', 'cost': 0}

    def _update_all_ebay_prices_internal(self):
        """Update eBay prices for all inventory records - DO NOT update ebay_sell_at here"""
        if not self.ebay_handler:
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
                ebay_pricing = self.ebay_handler.get_ebay_pricing(artist, title)
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

    def _update_single_ebay_prices_internal(self, record_id):
        """Update eBay prices for a single record - DO NOT update ebay_sell_at here"""
        if not self.ebay_handler:
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
            ebay_pricing = self.ebay_handler.get_ebay_pricing(artist, title)
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

    def _update_all_ebay_sell_at_internal(self):
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

    def _update_single_ebay_sell_at_internal(self, record_id):
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

    def _round_down_to_49_or_99(self, price):
        """Round down to nearest .49 or .99 that is less than or equal to original price"""
        import math
        
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