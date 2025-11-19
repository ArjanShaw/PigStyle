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

class InventoryTab:
    def __init__(self, discogs_handler, ebay_handler=None, gallery_json_manager=None, youtube_handler=None):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
        self.gallery_json_manager = gallery_json_manager
        self.youtube_handler = youtube_handler
        self.price_handler = PriceHandler()
        self.genre_handler = GenreHandler()
        
        # Initialize handlers - pass ebay_handler to record_ops_handler
        self.search_handler = SearchHandler(discogs_handler)
        self.record_ops_handler = RecordOperationsHandler(discogs_handler, ebay_handler)
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
            
        # Store Pricing Settings
        with st.expander("🏪 Store Pricing", expanded=False):
            self._render_store_pricing_section()
            
        # Genre Management & Import/Export & Signs Printing
        with st.expander("🎵 Genre Management & Printing", expanded=False):
            self.display_handler.render_genre_management()
            
        # Price Tag Management
        with st.expander("🖨️ Price Tag Management", expanded=False):
            self.display_handler.render_price_tag_management()
        
        # API Requests & Responses
        self._render_api_logs_section()
        
        # Tools & Sync
        self._render_tools_sync_section()

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
        else:
            st.error("Failed to add record to database")

    def _handle_update_record(self, condition, genre):
        """Handle updating a database record"""
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
        else:
            st.error("❌ Failed to update record")

    def _process_checkout(self):
        """Process checkout of selected records"""
        # Since we removed the status column, checkout is not functional anymore
        st.warning("Checkout functionality is not available. The status column has been removed from the database.")
        return 0

    def _render_store_pricing_section(self):
        """Render store pricing settings and actions"""
        st.subheader("🏪 Store Pricing Strategy")
        
        # Detailed store pricing calculation explanation
        st.write("""
        **Store Price Calculation:**
        1. Use Discogs median price
        2. Round down to nearest .49 or .99 price point
        3. Apply minimum store price (configurable, default $1.99)
        
        **Note:** Adding records only imports raw pricing data from Discogs. 
        Use the button below to calculate your custom store prices.
        """)
        
        # Test record input
        st.subheader("Test Single Record")
        col1, col2 = st.columns([1, 1])
        with col1:
            test_record_id = st.text_input("Record ID for testing:", placeholder="Enter record ID", key="store_test_record_id")
        
        # Store pricing action buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏪 Update Store Price", use_container_width=True, help="Calculate store price from Discogs median price using .49/.99 rounding"):
                if test_record_id and test_record_id.strip():
                    self._calculate_single_store_price(test_record_id.strip())
                else:
                    self._calculate_all_store_prices()

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

    def _render_tools_sync_section(self):
        """Render tools and sync section with Gallery JSON Test and GitHub Sync"""
        with st.expander("🛠️ Tools & Sync", expanded=False):
            # Gallery JSON Test
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔄 Manual JSON Rebuild", use_container_width=True):
                    if st.session_state.get('gallery_json_manager'):
                        with st.spinner("Rebuilding gallery JSON..."):
                            success = st.session_state.gallery_json_manager.trigger_rebuild(async_mode=False)
                        if success:
                            st.success("✅ Gallery JSON rebuilt successfully!")
                        else:
                            st.error("❌ Gallery JSON rebuild failed")
                    else:
                        st.error("Gallery JSON manager not initialized")
            
            with col2:
                if st.session_state.get('gallery_json_manager'):
                    status = st.session_state.gallery_json_manager.get_rebuild_status()
                    st.write(f"**Status:** {'Rebuilding...' if status['in_progress'] else 'Ready'}")
                    json_path = st.session_state.gallery_json_manager.get_json_path()
                    st.write(f"**JSON Path:** `{json_path}`")
            
            # GitHub Sync Section
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🔄 Manual GitHub Sync", use_container_width=True):
                    if hasattr(st.session_state, 'github_sync_handler'):
                        with st.spinner("Syncing with GitHub..."):
                            success, message = st.session_state.github_sync_handler.trigger_sync()
                            if success:
                                st.success(f"✅ {message}")
                            else:
                                st.error(f"❌ {message}")
                    else:
                        st.error("GitHub sync handler not initialized")
            
            with col2:
                if hasattr(st.session_state, 'github_sync_handler'):
                    status = st.session_state.github_sync_handler.get_sync_status()
                    st.write(f"**Repo:** `{status['repo_path']}`")
                    st.write(f"**Script:** {'✅ Found' if status['script_exists'] else '❌ Missing'}")
                    st.write(f"**Changes pending:** {'✅ Yes' if status['has_changes'] else '❌ No'}")
                    st.write(f"**Last commit:** {status['last_commit']}")

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

    def _calculate_all_store_prices(self):
        """Calculate store prices for all inventory records using Discogs median price"""
        updated_count = self._update_all_store_prices()
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time

    def _calculate_single_store_price(self, record_id):
        """Calculate store price for a single record using Discogs median price"""
        updated_count = self._update_single_store_price(record_id)
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            start_time = time.time()
            st.rerun()
            duration = time.time() - start_time

    def _update_all_store_prices(self):
        """Update store prices for all inventory records using Discogs median price with .49/.99 rounding"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT * FROM records_with_genres', conn)
        conn.close()
        
        # Get MIN_STORE_PRICE from config, default to 1.99
        min_store_price = st.session_state.db_manager.get_config_value('MIN_STORE_PRICE', '1.99')
        min_store_price = float(min_store_price)
        
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
        min_store_price = float(min_store_price)
        
        record = df.iloc[0]
        artist = record.get('artist', '')
        title = record.get('title', '')
        discogs_median_price = record.get('discogs_median_price')
        
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