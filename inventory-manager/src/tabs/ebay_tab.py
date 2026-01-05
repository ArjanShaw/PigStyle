import streamlit as st
import pandas as pd
from datetime import datetime
import time
import io
import csv
import requests
from handlers.rounding_handler import RoundingHandler
from handlers.config_handler import ConfigHandler
import math

class EBayTab:
    """Combined eBay handler and tab functionality in one class"""
    
    def __init__(self, client_id=None, client_secret=None, base_url="https://arjanshaw.pythonanywhere.com"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.config_handler = ConfigHandler()
        self.access_token = None
        self.token_expiry = None
    
    def _get_config_value(self, config_key, default=None):
        """Get config value via ConfigHandler"""
        return self.config_handler.get(config_key, default)
    
    def _get_all_records(self):
        """Get all records via API"""
        try:
            response = requests.get(f"{self.base_url}/records")
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])
                return pd.DataFrame(records) if records else pd.DataFrame()
            return pd.DataFrame()
        except Exception as e:
            st.error(f"API Error getting records: {e}")
            return pd.DataFrame()
    
    def _update_record(self, record_id, updates):
        """Update a record via API"""
        try:
            response = requests.put(
                f"{self.base_url}/records/{record_id}",
                json=updates
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"API Error updating record: {e}")
            return False
    
    def _search_records(self, search_term):
        """Search records via API"""
        try:
            response = requests.get(f"{self.base_url}/search?q={search_term}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('records', [])
            return []
        except Exception as e:
            st.error(f"Search error: {e}")
            return []
    
    # eBay API functionality
    def get_ebay_pricing(self, artist, title):
        """Get eBay pricing data for a record"""
        try:
            # This would make actual eBay API calls
            # For now, return placeholder data
            return {
                'ebay_lowest_price': 19.99,
                'ebay_low_shipping': 4.99,
                'ebay_median_price': 24.99,
                'ebay_highest_price': 34.99,
                'ebay_listings_count': 5,
                'ebay_search_url': f"https://www.ebay.com/sch/i.html?_nkw={artist}+{title}"
            }
        except Exception as e:
            st.error(f"Error getting eBay pricing: {e}")
            return None

    def render(self):
        st.header("🛒 eBay Management")
        
        user = st.session_state.get('user', {})
        user_role = user.get('role')
        
        # Only admin can view eBay tab
        if user_role != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view eBay tab.")
            return
        
        with st.expander("💰 eBay Pricing Strategy", expanded=True):
            st.write("""
            **eBay Sell Price Calculation:**
            1. Find lowest eBay listing price + shipping cost
            2. Subtract configured shipping cost ($5.72)
            3. Cap at Discogs median price if available
            4. Round down to nearest .99 price point
            5. Apply minimum price of $0.00
            
            **Note:** Use the buttons below to update eBay data and calculate sell prices.
            """)
            
            st.subheader("Test Single Record")
            col1, col2 = st.columns([1, 1])
            with col1:
                test_record_id = st.text_input("Record ID for testing:", placeholder="Enter record ID", key="ebay_test_record_id")
            
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
        
        with st.expander("📥 Import eBay Listings", expanded=True):
            st.subheader("Upload Current eBay Listings CSV")
            
            uploaded_file = st.file_uploader(
                "Upload eBay active listings CSV",
                type=['csv'],
                help="Upload CSV from eBay with your current active listings"
            )
            
            if uploaded_file is not None:
                content = uploaded_file.getvalue().decode('utf-8')
                csv_reader = csv.reader(io.StringIO(content))
                
                lines = list(csv_reader)
                if len(lines) < 2:
                    st.error("Invalid CSV file - not enough lines")
                    return
                
                listings_data = []
                header = lines[1]
                
                for i, row in enumerate(lines[2:], start=2):
                    if len(row) >= 12:
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
                
                if listings_data:
                    st.subheader("Listings Preview")
                    preview_df = pd.DataFrame(listings_data[:10])
                    st.dataframe(preview_df)
                    
                    if st.button("🔗 Match Listings to Database", width='stretch'):
                        self._process_ebay_listings(listings_data)
        
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
        
        self._render_individual_listings_table()

    def _update_all_ebay_prices(self):
        updated_count = self._update_all_ebay_prices_internal()
        
        if updated_count > 0:
            st.session_state.records_updated = st.session_state.get('records_updated', 0) + 1
            st.rerun()

    def _update_single_ebay_prices(self, record_id):
        updated_count = self._update_single_ebay_prices_internal(record_id)
        
        if updated_count > 0:
            st.session_state.records_updated = st.session_state.get('records_updated', 0) + 1
            st.rerun()

    def _update_all_ebay_sell_at(self):
        updated_count = self._update_all_ebay_sell_at_internal()
        
        if updated_count > 0:
            st.session_state.records_updated = st.session_state.get('records_updated', 0) + 1
            st.rerun()

    def _update_single_ebay_sell_at(self, record_id):
        updated_count = self._update_single_ebay_sell_at_internal(record_id)
        
        if updated_count > 0:
            st.session_state.records_updated = st.session_state.get('records_updated', 0) + 1
            st.rerun()

    def _process_ebay_listings(self, listings_data):
        st.subheader("Matching eBay Listings to Database")
        
        matched_count = 0
        updated_count = 0
        progress_bar = st.progress(0)
        status_text = st.empty()
        
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
            
            record = None
            if sku:
                if ' - ' in title:
                    artist, record_title = title.split(' - ', 1)
                    record = self._find_record_by_artist_title(artist.strip(), record_title.strip())
            
            if not record and ' - ' in title:
                artist, record_title = title.split(' - ', 1)
                record = self._find_record_by_artist_title(artist.strip(), record_title.strip())
            
            if record:
                matched_count += 1
                success = self._update_record(
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
            
            progress_bar.progress((i + 1) / len(listings_data))
            
            if (i + 1) % 5 == 0 or (i + 1) == len(listings_data):
                with results_placeholder:
                    display_results = results[-10:] if len(results) > 10 else results
                    for result in display_results:
                        st.write(result)
        
        status_text.empty()
        progress_bar.empty()
        
        with results_container:
            st.success(f"✅ eBay listings processing completed!")
            st.write(f"**Results:** {matched_count} matched, {updated_count} updated out of {len(listings_data)} listings")
            
            all_results = matched_listings + unmatched_listings
            
            if all_results:
                st.subheader("All Listings Results")
                
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
                
                st.dataframe(
                    df, 
                    width='stretch',
                    height=400
                )
                
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
    
    def _find_record_by_artist_title(self, artist, title):
        search_results = self._search_records(f"{artist} {title}")
        
        if search_results:
            return search_results[0]
        return None

    def _export_ebay_draft_csv(self, num_listings):
        st.subheader("Generating eBay Draft Listings")
        
        all_records = self._get_all_records()
        
        if all_records.empty:
            st.warning("No records found")
            return
        
        records_without_ebay = all_records[
            (all_records['ebay_item_number'].isna()) | 
            (all_records['ebay_item_number'] == '')
        ]
        
        records_to_export = records_without_ebay.sort_values('ebay_sell_at', ascending=False).head(num_listings)
        
        if len(records_to_export) == 0:
            st.warning("No records found without eBay item numbers")
            return
        
        output = io.StringIO()
        
        output.write("#INFO,Version=0.0.2,Template= eBay-draft-listings-template_US,,,,,,,,,\n")
        
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
        
        for _, record in records_to_export.iterrows():
            row_data = self._format_record_for_ebay_draft(record)
            if row_data:
                row_values = [str(row_data.get(header, "")) for header in headers]
                output.write(",".join(row_values) + "\n")
        
        csv_content = output.getvalue()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ebay_draft_listings_{timestamp}.csv"
        
        st.download_button(
            label=f"⬇️ Download eBay Draft CSV ({len(records_to_export)} listings)",
            data=csv_content,
            file_name=filename,
            mime="text/csv",
            width='stretch',
            key=f"download_ebay_draft_{timestamp}"
        )
        
        st.success(f"✅ eBay draft CSV ready! {len(records_to_export)} records formatted for eBay import.")

    def _format_record_for_ebay_draft(self, record):
        category_map = {
            "Vinyl": "176985",
            "CDs": "176984", 
            "Cassettes": "176983"
        }
        
        condition_map = {
            "1": "3000",
            "2": "3000",  
            "3": "3000",
            "4": "3000",
            "5": "1000",
        }
        
        artist = record.get('artist', 'Unknown Artist')
        title = record.get('title', 'Unknown Title')
        format_type = record.get('format', 'Vinyl')
        condition = record.get('condition', '4')
        barcode = record.get('barcode', '')
        image_url = record.get('image_url', '')
        ebay_sell_at = record.get('ebay_sell_at', 0)
        
        sku = f"{artist.replace(' ', '').upper()}-{title.replace(' ', '').upper()}-{format_type.upper()}"[:30]
        
        description = f"{artist} - {title}"
        
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
        if 'api_details' not in st.session_state:
            return
            
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
            
            shipping_cost_str = self._get_config_value('SHIPPING_COST')
            if shipping_cost_str is None:
                st.error("SHIPPING_COST config value not found")
                return
            shipping_cost = float(shipping_cost_str)
            
            item_summaries = recent_ebay_response.get('itemSummaries', [])
            
            table_data = []
            for item in item_summaries:
                price_data = item.get('price', {})
                base_price = float(price_data.get('value', 0))
                
                shipping_info = self._extract_shipping_info(item)
                shipping_type = shipping_info['type']
                shipping_cost_value = shipping_info['cost']
                
                assumed_shipping_cost = None
                if shipping_type == 'CALC':
                    assumed_shipping_cost = shipping_cost
                
                if shipping_type == 'CALC':
                    base_and_shipping = base_price + shipping_cost
                elif shipping_cost_value is not None:
                    base_and_shipping = base_price + shipping_cost_value
                else:
                    base_and_shipping = base_price
                
                item_url = item.get('itemWebUrl', '')
                
                table_data.append({
                    'Title': item.get('title', '')[:80] + '...' if len(item.get('title', '')) > 80 else item.get('title', ''),
                    'Base Price': base_price,
                    'Shipping Type': shipping_type,
                    'Shipping Cost': shipping_cost_value,
                    'Assumed Shipping Cost': assumed_shipping_cost,
                    'Base + Shipping': base_and_shipping,
                    'URL': item_url
                })
            
            table_data.sort(key=lambda x: x['Base + Shipping'])
            
            if table_data:
                df = pd.DataFrame(table_data)
                
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
        
        if 'shippingCostFixed' in item:
            cost = float(item['shippingCostFixed'])
            return {'type': 'FIXED', 'cost': cost}
        
        return {'type': 'FREE', 'cost': 0}

    def _update_all_ebay_prices_internal(self):
        records_df = self._get_all_records()
        
        if records_df.empty:
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
        
        for i, (_, record) in enumerate(records_df.iterrows()):
            artist = record.get('artist', '')
            title = record.get('title', '')
            record_id = record.get('id')
            
            status_text.text(f"Updating {i+1}/{len(records_df)}: {artist} - {title}")
            
            ebay_pricing = self.get_ebay_pricing(artist, title)
            if ebay_pricing:
                ebay_lowest_price = float(ebay_pricing.get('ebay_lowest_price', 0))
                ebay_low_shipping = float(ebay_pricing.get('ebay_low_shipping', 0))
                
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
            
            progress_bar.progress((i + 1) / len(records_df))
            
            if (i + 1) % 5 == 0 or (i + 1) == len(records_df):
                with results_placeholder:
                    display_results = results[-10:] if len(results) > 10 else results
                    for result in display_results:
                        st.write(result)
        
        status_text.empty()
        progress_bar.empty()
        
        with results_container:
            st.success(f"✅ eBay prices update completed!")
            st.write(f"**Results:** {updated_count} updated, {failed_count} failed")
            
        return updated_count

    def _update_single_ebay_prices_internal(self, record_id):
        # Get single record using API
        try:
            response = requests.get(f"{self.base_url}/records/{record_id}")
            if response.status_code == 200:
                record = response.json()
            else:
                st.error(f"Record ID {record_id} not found")
                return 0
        except Exception as e:
            st.error(f"API Error getting record: {e}")
            return 0
        
        artist = record.get('artist', '')
        title = record.get('title', '')
        
        ebay_pricing = self.get_ebay_pricing(artist, title)
        if ebay_pricing:
            ebay_lowest_price = float(ebay_pricing.get('ebay_lowest_price', 0))
            ebay_low_shipping = float(ebay_pricing.get('ebay_low_shipping', 0))
            
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

    def _update_all_ebay_sell_at_internal(self):
        records_df = self._get_all_records()
        
        if records_df.empty:
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
        
        for i, (_, record) in enumerate(records_df.iterrows()):
            artist = record.get('artist', '')
            title = record.get('title', '')
            record_id = record.get('id')
            ebay_lowest_price = record.get('ebay_lowest_price')
            ebay_low_shipping = record.get('ebay_low_shipping')
            discogs_median_price = record.get('discogs_median_price')
            
            status_text.text(f"Updating {i+1}/{len(records_df)}: {artist} - {title}")
            
            ebay_sell_at = self._calculate_ebay_sell_at(ebay_lowest_price, ebay_low_shipping, discogs_median_price)
            
            success = self._update_record(record_id, {'ebay_sell_at': ebay_sell_at})
            if success:
                updated_count += 1
                results.append(f"✅ {artist} - {title}")
            else:
                failed_count += 1
                results.append(f"❌ {artist} - {title}: Database update failed")
            
            progress_bar.progress((i + 1) / len(records_df))
            
            if (i + 1) % 5 == 0 or (i + 1) == len(records_df):
                with results_placeholder:
                    display_results = results[-10:] if len(results) > 10 else results
                    for result in display_results:
                        st.write(result)
        
        status_text.empty()
        progress_bar.empty()
        
        with results_container:
            st.success(f"✅ eBay sell price update completed!")
            st.write(f"**Results:** {updated_count} updated, {failed_count} failed")
            
        return updated_count

    def _update_single_ebay_sell_at_internal(self, record_id):
        # Get single record using API
        try:
            response = requests.get(f"{self.base_url}/records/{record_id}")
            if response.status_code == 200:
                record = response.json()
            else:
                st.error(f"Record ID {record_id} not found")
                return 0
        except Exception as e:
            st.error(f"API Error getting record: {e}")
            return 0
        
        artist = record.get('artist', '')
        title = record.get('title', '')
        ebay_lowest_price = record.get('ebay_lowest_price')
        ebay_low_shipping = record.get('ebay_low_shipping')
        discogs_median_price = record.get('discogs_median_price')
        
        ebay_sell_at = self._calculate_ebay_sell_at(ebay_lowest_price, ebay_low_shipping, discogs_median_price)
        
        success = self._update_record(record_id, {'ebay_sell_at': ebay_sell_at})
        if success:
            st.success(f"✅ Updated eBay sell price for {artist} - {title}")
            return 1
        else:
            st.error(f"❌ Database update failed for {artist} - {title}")
            return 0

    def _calculate_ebay_sell_at(self, ebay_lowest_price, ebay_low_shipping, discogs_median_price):
        shipping_cost = self._get_config_value('SHIPPING_COST')
        if shipping_cost is None:
            raise ValueError("SHIPPING_COST config value not found in database")
        
        return RoundingHandler.calculate_ebay_sell_at(
            ebay_lowest_price, 
            ebay_low_shipping, 
            discogs_median_price, 
            shipping_cost
        )