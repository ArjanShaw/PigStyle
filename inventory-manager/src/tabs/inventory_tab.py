import streamlit as st
import pandas as pd
from datetime import datetime
import time
from handlers.search_handler import SearchHandler
from handlers.record_operations_handler import RecordOperationsHandler
from handlers.display_handler import DisplayHandler
from handlers.export_handler import ExportHandler
from handlers.price_handler import PriceHandler
from handlers.genre_handler import GenreHandler
from handlers.youtube_handler import YouTubeHandler
from config import PrintConfig

class InventoryTab:
    def __init__(self, discogs_handler, debug_tab, ebay_handler=None, gallery_json_manager=None):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
        self.debug_tab = debug_tab
        self.gallery_json_manager = gallery_json_manager
        self.config = PrintConfig()
        self.price_handler = PriceHandler()
        self.genre_handler = GenreHandler()
        self.youtube_handler = YouTubeHandler(debug_tab)
        
        # Initialize handlers - pass ebay_handler and gallery_json_manager to record_ops_handler
        self.search_handler = SearchHandler(discogs_handler)
        self.record_ops_handler = RecordOperationsHandler(discogs_handler, ebay_handler, gallery_json_manager)
        self.display_handler = DisplayHandler(self.youtube_handler)
        self.export_handler = ExportHandler(self.price_handler, self.genre_handler)

    def render(self):
        """Render the combined inventory, check-in, and checkout functionality"""
        
        # Database statistics - direct count from inventory records
        stats = self._get_database_stats_direct()
            
        # Top row: Stats
        col1, col2 = st.columns([1, 1])
        with col1:
            st.metric("Inventory Records", stats['records_count'])
        
        # Inventory
        with st.expander("📦 Inventory", expanded=False):
            self._render_unified_operations()
            
        # Pricing Settings
        with st.expander("💰 Pricing", expanded=False):
            self._render_pricing_section()
            
        # Genre Management & Import/Export & Signs Printing
        with st.expander("🎵 Genre Management & Printing", expanded=False):
            self.display_handler.render_genre_management()
            
        # Price Tag Management
        with st.expander("🖨️ Price Tag Management", expanded=False):
            self.display_handler.render_price_tag_management()
            
        # API Requests & Responses - MOVED TO SAME LEVEL
        self._render_api_logs_section()

    def _render_unified_operations(self):
        """Render the unified search/add/checkout operations"""
        # Initialize session state for search
        if 'search_type' not in st.session_state:
            st.session_state.search_type = "Edit or Delete item"
        if 'current_search' not in st.session_state:
            st.session_state.current_search = ""
        if 'search_results' not in st.session_state:
            st.session_state.search_results = {}
        if 'selected_record' not in st.session_state:
            st.session_state.selected_record = None
        if 'checkout_records' not in st.session_state:
            st.session_state.checkout_records = []
        if 'record_added' not in st.session_state:
            st.session_state.record_added = None
        if 'last_condition' not in st.session_state:
            st.session_state.last_condition = "5"  # Default to condition 5
        
        # Action type selection - renamed from Search Type
        col1, col2 = st.columns([1, 3])
        with col1:
            search_type = st.radio(
                "Action:",
                ["Add item", "Edit or Delete item"],
                key="search_type_radio"
            )
        
        # Search input and button - button moved under input
        search_input = st.text_input(
            "Search:",
            placeholder="Enter barcode, artist, or title...",
            key="unified_search_input"
        )
        
        col1, col2 = st.columns([3, 1])
        with col1:
            search_submitted = st.button("🔍 Search", use_container_width=True)
        
        # Handle Enter key press in search input
        if st.session_state.get('unified_search_input') and st.session_state.unified_search_input.strip():
            if st.session_state.unified_search_input != st.session_state.get('last_search', ''):
                st.session_state.current_search = st.session_state.unified_search_input.strip()
                st.session_state.selected_record = None
                st.session_state.record_added = None
                
                if search_type == "Add item":
                    results = self.search_handler.perform_discogs_search(st.session_state.unified_search_input.strip())
                    st.session_state.search_results[st.session_state.unified_search_input.strip()] = results
                else:
                    results = self.search_handler.perform_database_search(st.session_state.unified_search_input.strip())
                    st.session_state.search_results[st.session_state.unified_search_input.strip()] = results
                
                st.session_state.last_search = st.session_state.unified_search_input.strip()
                st.rerun()
        
        # Handle search button click
        if search_submitted and search_input and search_input.strip():
            st.session_state.current_search = search_input.strip()
            st.session_state.selected_record = None
            st.session_state.record_added = None
            
            if search_type == "Add item":
                results = self.search_handler.perform_discogs_search(search_input.strip())
                st.session_state.search_results[search_input.strip()] = results
            else:
                results = self.search_handler.perform_database_search(search_input.strip())
                st.session_state.search_results[search_input.strip()] = results
        
        # Display search results
        if (st.session_state.current_search and 
            st.session_state.current_search in st.session_state.search_results and
            st.session_state.record_added is None):
            
            results = st.session_state.search_results[st.session_state.current_search]
            
            if st.session_state.selected_record:
                # Show only the selected record
                self.display_handler.render_selected_record_only(st.session_state.selected_record)
            else:
                # Show all results
                if search_type == "Add item":
                    self.display_handler.render_discogs_results(results, search_type)
                else:
                    self.display_handler.render_database_results(results, search_type)
        
        # Edit properties and action button (only show when selection is made and no record was just added)
        if (st.session_state.selected_record and 
            st.session_state.record_added is None):
            self.display_handler.render_edit_section(st.session_state.selected_record, self._handle_add_record, self._handle_update_record, st.session_state.last_condition)
        
        # Checkout section for database search
        if (search_type == "Edit or Delete item" and 
            st.session_state.checkout_records and
            st.session_state.record_added is None):
            self.display_handler.render_checkout_section(st.session_state.checkout_records, self._process_checkout)

    def _handle_add_record(self, condition, genre):
        """Handle adding an inventory record to database"""
        try:
            record_data = st.session_state.selected_record['data']
            # Store the condition for next time
            st.session_state.last_condition = condition
            
            success, record_id = self.record_ops_handler.add_inventory_record(
                record_data, 
                condition, 
                genre, 
                st.session_state.current_search
            )
            
            if success:
                # Clear API logs after successful addition
                if 'api_logs' in st.session_state:
                    st.session_state.api_logs = []
                if 'api_details' in st.session_state:
                    st.session_state.api_details = {}
                
                # Get the full record data using the row ID
                import time
                time.sleep(0.5)  # Small delay to ensure triggers complete
                
                record = st.session_state.db_manager.get_record_by_id(record_id)
                if record is not None:
                    # Convert Series to dict to avoid truth value issues
                    st.session_state.record_added = record.to_dict() if hasattr(record, 'to_dict') else record
                else:
                    # Fallback: create basic record data
                    st.session_state.record_added = {
                        'file_at': '',
                    }
                
                st.session_state.selected_record = None
                st.session_state.records_updated += 1
                
                # Log rerun timing
                start_time = time.time()
                st.rerun()
                duration = time.time() - start_time
                self.debug_tab.add_log("RERUN", f"Rerun called after add record - Duration: {duration:.3f}s")
            else:
                st.error("Failed to add record to database")
                
        except Exception as e:
            st.error(f"Error adding to database: {str(e)}")

    def _handle_update_record(self, condition, genre):
        """Handle updating a database record"""
        try:
            record_data = st.session_state.selected_record['data']
            # Store the condition for next time
            st.session_state.last_condition = condition
            
            success = self.record_ops_handler.update_database_record(record_data, condition, genre)
            
            if success:
                st.success("✅ Record updated successfully!")
                st.session_state.records_updated += 1
                st.session_state.selected_record = None
                
                # Log rerun timing
                start_time = time.time()
                st.rerun()
                duration = time.time() - start_time
                self.debug_tab.add_log("RERUN", f"Rerun called after update record - Duration: {duration:.3f}s")
            else:
                st.error("❌ Failed to update record")
                
        except Exception as e:
            st.error(f"Error updating record: {str(e)}")

    def _process_checkout(self):
        """Process checkout of selected records"""
        try:
            # Since we removed the status column, checkout is not functional anymore
            st.warning("Checkout functionality is not available. The status column has been removed from the database.")
            return 0
                
        except Exception as e:
            st.error(f"Error processing checkout: {e}")
            return 0

    def _render_pricing_section(self):
        """Render pricing settings and actions"""
        st.subheader("Pricing Strategy")
        
        # Detailed pricing calculation explanation
        st.write("""
        **eBay Sell Price Calculation:**
        1. Find lowest eBay listing price + shipping cost
        2. Subtract configured shipping cost ($5.72)
        3. Cap at Discogs median price if available
        4. Round down to nearest .49 or .99 price point
        5. Apply minimum price of $0.00
        
        **Store Price Calculation:**
        1. Use Discogs median price
        2. Round down to nearest .49 or .99 price point
        3. Apply minimum store price (configurable, default $1.99)
        
        **Note:** Adding records only imports raw pricing data from Discogs/eBay. 
        Use the buttons below to calculate your custom prices.
        """)
        
        # Test record input
        st.subheader("Test Single Record")
        col1, col2 = st.columns([1, 1])
        with col1:
            test_record_id = st.text_input("Record ID for testing:", placeholder="Enter record ID")
        
        # Pricing action buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 Update eBay Prices", use_container_width=True, help="Call eBay API to update pricing data for all inventory"):
                if test_record_id and test_record_id.strip():
                    self._update_single_ebay_prices(test_record_id.strip())
                else:
                    self._update_all_ebay_prices()
        with col2:
            if st.button("💰 Update eBay Sell At", use_container_width=True, help="Calculate eBay sell prices from existing lowest prices"):
                if test_record_id and test_record_id.strip():
                    self._update_single_ebay_sell_at(test_record_id.strip())
                else:
                    self._update_all_ebay_sell_at()
        with col3:
            if st.button("🏪 Update Store Price", use_container_width=True, help="Calculate store price from Discogs median price using .49/.99 rounding"):
                if test_record_id and test_record_id.strip():
                    self._calculate_single_store_price(test_record_id.strip())
                else:
                    self._calculate_all_store_prices()
        
        # Show individual listings table
        self._render_individual_listings_table()

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
            
        with st.expander("📊 Individual eBay Listings", expanded=False):
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
                    use_container_width=True,
                    height=400,
                    hide_index=True,
                    column_config=column_config
                )

    def _render_api_logs_section(self):
        """Render API logs section at the same level as other main sections"""
        if 'api_logs' in st.session_state and st.session_state.api_logs:
            with st.expander("📡 API Requests & Responses", expanded=False):
                for api_title in st.session_state.api_logs:
                    if api_title in st.session_state.api_details:
                        details = st.session_state.api_details[api_title]
                        duration = details.get('duration', 'N/A')
                        display_title = f"{api_title} ({duration}s)" if duration != 'N/A' else api_title
                        with st.expander(display_title, expanded=False):
                            st.write("**Request:**")
                            st.json(details['request'])
                            if 'response' in details:
                                st.write("**Response:**")
                                st.json(details['response'])

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

    def _get_database_stats_direct(self) -> dict:
        """Get database statistics directly from records table"""
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM records')
        records_count_result = cursor.fetchone()
        records_count = records_count_result[0] if records_count_result else 0
        
        conn.close()
        
        return {
            'records_count': int(records_count) if records_count is not None else 0
        }

    def _update_all_ebay_prices(self):
        """Update eBay prices for all inventory records"""
        if not self.ebay_handler:
            st.error("eBay handler not available. Check your eBay API credentials.")
            return
        
        updated_count = self.export_handler.update_all_ebay_prices(self.ebay_handler)
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time
            self.debug_tab.add_log("RERUN", f"Rerun called after update all eBay prices - Duration: {duration:.3f}s")

    def _update_single_ebay_prices(self, record_id):
        """Update eBay prices for a single record"""
        if not self.ebay_handler:
            st.error("eBay handler not available. Check your eBay API credentials.")
            return
        
        updated_count = self.export_handler.update_single_ebay_prices(self.ebay_handler, record_id)
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time
            self.debug_tab.add_log("RERUN", f"Rerun called after update single eBay prices - Duration: {duration:.3f}s")

    def _update_all_ebay_sell_at(self):
        """Update eBay sell prices for all inventory records using existing lowest prices"""
        updated_count = self.export_handler.update_all_ebay_sell_at()
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time
            self.debug_tab.add_log("RERUN", f"Rerun called after update all eBay sell at - Duration: {duration:.3f}s")

    def _update_single_ebay_sell_at(self, record_id):
        """Update eBay sell price for a single record using existing lowest price"""
        updated_count = self.export_handler.update_single_ebay_sell_at(record_id)
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time
            self.debug_tab.add_log("RERUN", f"Rerun called after update single eBay sell at - Duration: {duration:.3f}s")

    def _calculate_all_store_prices(self):
        """Calculate store prices for all inventory records using Discogs median price"""
        updated_count = self._update_all_store_prices()
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time
            self.debug_tab.add_log("RERUN", f"Rerun called after calculate all store prices - Duration: {duration:.3f}s")

    def _calculate_single_store_price(self, record_id):
        """Calculate store price for a single record using Discogs median price"""
        updated_count = self._update_single_store_price(record_id)
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time
            self.debug_tab.add_log("RERUN", f"Rerun called after calculate single store price - Duration: {duration:.3f}s")

    def _update_all_store_prices(self):
        """Update store prices for all inventory records using Discogs median price with .49/.99 rounding"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres', conn)
        conn.close()
        
        # Get MIN_STORE_PRICE from config, default to 1.99
        min_store_price = st.session_state.db_manager.get_config_value('MIN_STORE_PRICE', '1.99')
        try:
            min_store_price = float(min_store_price)
        except (ValueError, TypeError):
            min_store_price = 1.99
        
        updated_count = 0
        failed_count = 0
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_container = st.container()
        
        with results_container:
            st.subheader("Store Price Update Progress")
            results_placeholder = st.empty()
        
        results = []
        
        for i, (_, record) in enumerate(df.iterrows()):
            artist = record.get('artist', '')
            title = record.get('title', '')
            record_id = record.get('id')
            discogs_median_price = record.get('discogs_median_price')
            
            status_text.text(f"Updating {i+1}/{len(df)}: {artist} - {title}")
            
            try:
                if discogs_median_price is not None and discogs_median_price > 0:
                    # Use the same rounding function as eBay sell prices
                    store_price = self.export_handler._round_down_to_49_or_99(float(discogs_median_price))
                    
                    # Apply MIN_STORE_PRICE minimum
                    store_price = max(store_price, min_store_price)
                    
                    # Update the store_price field
                    success = st.session_state.db_manager.update_record(record_id, {'store_price': store_price})
                    if success:
                        updated_count += 1
                        results.append(f"✅ {artist} - {title}: ${discogs_median_price:.2f} → ${store_price:.2f}")
                    else:
                        failed_count += 1
                        results.append(f"❌ {artist} - {title}: Database update failed")
                else:
                    # No Discogs price available
                    failed_count += 1
                    results.append(f"❌ {artist} - {title}: No Discogs price available")
                    
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
            st.success(f"✅ Store price update completed!")
            st.write(f"**Results:** {updated_count} updated, {failed_count} failed")
            
        return updated_count

    def _update_single_store_price(self, record_id):
        """Update store price for a single record using Discogs median price with .49/.99 rounding"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres WHERE id = ?', conn, params=(record_id,))
        conn.close()
        
        if len(df) == 0:
            st.error(f"Record ID {record_id} not found")
            return 0
        
        # Get MIN_STORE_PRICE from config, default to 1.99
        min_store_price = st.session_state.db_manager.get_config_value('MIN_STORE_PRICE', '1.99')
        try:
            min_store_price = float(min_store_price)
        except (ValueError, TypeError):
            min_store_price = 1.99
        
        record = df.iloc[0]
        artist = record.get('artist', '')
        title = record.get('title', '')
        discogs_median_price = record.get('discogs_median_price')
        
        try:
            if discogs_median_price is not None and discogs_median_price > 0:
                # Use the same rounding function as eBay sell prices
                store_price = self.export_handler._round_down_to_49_or_99(float(discogs_median_price))
                
                # Apply MIN_STORE_PRICE minimum
                store_price = max(store_price, min_store_price)
                
                # Update the store_price field
                success = st.session_state.db_manager.update_record(record_id, {'store_price': store_price})
                if success:
                    st.success(f"✅ Updated store price for {artist} - {title}: ${discogs_median_price:.2f} → ${store_price:.2f}")
                    return 1
                else:
                    st.error(f"❌ Database update failed for {artist} - {title}")
                    return 0
            else:
                st.error(f"❌ No Discogs price available for {artist} - {title}")
                return 0
                
        except Exception as e:
            st.error(f"❌ Error updating {artist} - {title}: {str(e)}")
            return 0

    def render_sold_tab(self):
        """Render the sold records table functionality - renamed to Income"""
        st.info("The 'Sold Records' functionality is not available. The status column has been removed from the database.")
        return

    def _return_to_inventory(self):
        """Return selected sold records back to inventory"""
        st.warning("Return to inventory functionality is not available. The status column has been removed from the database.")
        return

    def _update_record_status(self, record_ids, new_status):
        """Update status of records - not available anymore"""
        st.warning("Record status update functionality is not available. The status column has been removed from the database.")
        return False

    def _render_records_table(self, status, search_term, filter_option):
        """Render records with pagination"""
        st.info(f"The '{status} records' table is not available. The status column has been removed from the database.")
        return

    def _render_records_dataframe(self, records: pd.DataFrame, status: str):
        """Render records in an optimized dataframe with selection"""
        st.info(f"The records table is not available. The status column has been removed from the database.")
        return

    def _format_currency(self, value):
        """Format currency values"""
        if not value:
            return "$N/A"
        return f"${float(value):.2f}"

    def _get_all_records_direct(self, status: str, search_term: str = None, filter_option: str = None) -> pd.DataFrame:
        """Get all records directly from records_with_genres view with optional filtering"""
        # Return empty dataframe since status functionality is removed
        return pd.DataFrame()

    def _get_total_filtered_count(self, status: str, search_term: str = None, filter_option: str = None) -> int:
        """Get total count of records after applying filters"""
        # Return 0 since status functionality is removed
        return 0