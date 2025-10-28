import streamlit as st
import pandas as pd
from datetime import datetime
from handlers.search_handler import SearchHandler
from handlers.record_operations_handler import RecordOperationsHandler
from handlers.display_handler import DisplayHandler
from handlers.export_handler import ExportHandler
from handlers.price_handler import PriceHandler
from handlers.genre_handler import GenreHandler
from config import PrintConfig

class InventoryTab:
    def __init__(self, discogs_handler, debug_tab, ebay_handler=None):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
        self.debug_tab = debug_tab
        self.config = PrintConfig()
        self.price_handler = PriceHandler()
        self.genre_handler = GenreHandler()
        
        # Initialize handlers - pass ebay_handler to record_ops_handler
        self.search_handler = SearchHandler(discogs_handler)
        self.record_ops_handler = RecordOperationsHandler(discogs_handler, ebay_handler)
        self.display_handler = DisplayHandler()
        self.export_handler = ExportHandler(self.price_handler, self.genre_handler)

    def render(self):
        """Render the combined inventory, check-in, and checkout functionality"""
        
        # Database statistics - direct count from inventory records
        stats = self._get_database_stats_direct('inventory')
            
        # Top row: Stats
        col1, col2 = st.columns([1, 1])
        with col1:
            st.metric("Inventory Records", stats['records_count'])
        
        # Unified Inventory Operations
        with st.expander("📦 Inventory Operations", expanded=False):
            self._render_unified_operations()
            
        # eBay Settings
        with st.expander("💰 eBay", expanded=False):
            self._render_ebay_section()
            
        # Genre Management & Import/Export & Signs Printing
        with st.expander("🎵 Genre Management & Printing", expanded=False):
            self.display_handler.render_genre_management()
            
        # Price Tag Management
        with st.expander("🖨️ Price Tag Management", expanded=False):
            self.display_handler.render_price_tag_management()

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
        
        search_submitted = st.button("🔍 Search", use_container_width=True)
        
        # Handle search
        if search_submitted and search_input and search_input.strip():
            st.session_state.current_search = search_input.strip()
            st.session_state.selected_record = None  # Clear previous selection
            st.session_state.record_added = None  # Clear added record
            
            if search_type == "Add item":
                results = self.search_handler.perform_discogs_search(search_input.strip())
                st.session_state.search_results[search_input.strip()] = results
            else:
                results = self.search_handler.perform_database_search(search_input.strip())
                st.session_state.search_results[search_input.strip()] = results
        
        # Show success message and display added record details
        if st.session_state.get('record_added') is not None:
            record_data = st.session_state.record_added
            
            # Display success message with record details inside the success box
            file_at = record_data.get('file_at', 'N/A')
            store_price = record_data.get('store_price')
            ebay_sell_at = record_data.get('ebay_sell_at')
            
            success_message = f"✅ Record added to database! | File At: {file_at} | Store Price: ${store_price:.2f}" if store_price else f"✅ Record added to database! | File At: {file_at} | Store Price: N/A"
            if ebay_sell_at:
                success_message += f" | eBay Sell At: ${ebay_sell_at:.2f}"
            else:
                success_message += " | eBay Sell At: N/A"
                
            st.success(success_message)
        
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
                        'store_price': 0,
                        'ebay_sell_at': 0
                    }
                
                st.session_state.selected_record = None
                st.session_state.records_updated += 1
                st.rerun()
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
                st.rerun()
            else:
                st.error("❌ Failed to update record")
                
        except Exception as e:
            st.error(f"Error updating record: {str(e)}")

    def _process_checkout(self):
        """Process checkout of selected records"""
        try:
            updated_count = self.record_ops_handler.process_checkout(st.session_state.checkout_records)
            
            if updated_count > 0:
                receipt_content = self.record_ops_handler.generate_receipt_content(st.session_state.checkout_records)
                st.session_state.receipt_content = receipt_content
                st.session_state.show_receipt_download = True
                
                st.session_state.checkout_records = []
                st.session_state.records_updated += 1
                st.success(f"✅ Processed {updated_count} records for checkout!")
                st.rerun()
            else:
                st.error("Failed to update any records.")
                
        except Exception as e:
            st.error(f"Error processing checkout: {e}")

    def _render_ebay_section(self):
        """Render eBay settings and actions"""
        st.subheader("eBay Pricing Strategy")
        st.write("Dynamic calculation from eBay lowest price with .49/.99 rounding")
        st.write("Store price calculated automatically from Discogs median price")
        
        # Test record input
        st.subheader("Test Single Record")
        col1, col2 = st.columns([1, 1])
        with col1:
            test_record_id = st.text_input("Record ID for testing:", placeholder="Enter record ID")
        
        # eBay action buttons
        col1, col2 = st.columns(2)
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
        
        # Show eBay API logs in separate expander
        if 'api_logs' in st.session_state and st.session_state.api_logs:
            with st.expander("📡 eBay API Requests & Responses", expanded=False):
                for api_title in st.session_state.api_logs:
                    if api_title in st.session_state.api_details:
                        details = st.session_state.api_details[api_title]
                        with st.expander(api_title, expanded=False):
                            st.write("**Request:**")
                            st.json(details['request'])
                            if 'response' in details:
                                st.write("**Response:**")
                                st.json(details['response'])

    def _get_database_stats_direct(self, status='inventory') -> dict:
        """Get database statistics directly from records table"""
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM records WHERE status = ?', (status,))
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
            st.rerun()

    def _update_single_ebay_prices(self, record_id):
        """Update eBay prices for a single record"""
        if not self.ebay_handler:
            st.error("eBay handler not available. Check your eBay API credentials.")
            return
        
        updated_count = self.export_handler.update_single_ebay_prices(self.ebay_handler, record_id)
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            st.rerun()

    def _update_all_ebay_sell_at(self):
        """Update eBay sell prices for all inventory records using existing lowest prices"""
        updated_count = self.export_handler.update_all_ebay_sell_at()
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            st.rerun()

    def _update_single_ebay_sell_at(self, record_id):
        """Update eBay sell price for a single record using existing lowest price"""
        updated_count = self.export_handler.update_single_ebay_sell_at(record_id)
        
        if updated_count > 0:
            st.session_state.records_updated += 1
            st.rerun()

    def render_sold_tab(self):
        """Render the sold records table functionality - renamed to Income"""
        # Database statistics - direct count from sold records
        stats = self._get_database_stats_direct('sold')
        
        # Top row: Stats and action buttons
        col1, col2 = st.columns([1, 1])
        with col1:
            st.metric("Sold Records", stats['records_count'])
        with col2:
            if st.button("🔄 Return to Inventory", use_container_width=True, help="Return selected sold records to inventory"):
                self._return_to_inventory()
        
        # Second row: Search and filters
        col1, col2 = st.columns([2, 1])
        
        with col1:
            search_term = st.text_input(
                "Search by artist, title, or barcode:",
                key="search_sold",
                placeholder="Enter search term..."
            )
        
        with col2:
            # Quick filters
            filter_option = st.selectbox(
                "Filter by",
                options=["All Records", "No Barcode", "No Price Data", "No Genre", "No File At", "No eBay Price"],
                key="quick_filter_sold"
            )

        if stats['records_count'] > 0:
            self._render_records_table('sold', search_term, filter_option)
        else:
            st.info("No sold records yet.")

    def _return_to_inventory(self):
        """Return selected sold records back to inventory"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
            
        selected_ids = st.session_state.selected_records
        if self._update_record_status(selected_ids, 'inventory'):
            st.success(f"✅ Returned {len(selected_ids)} records to inventory!")
            st.session_state.selected_records = []
            st.session_state.records_updated += 1
            st.rerun()

    def _update_record_status(self, record_ids, new_status):
        """Update status of records"""
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        cursor.executemany('UPDATE records SET status = ? WHERE id = ?', [(new_status, id) for id in record_ids])
        conn.commit()
        conn.close()
        return True

    def _render_records_table(self, status, search_term, filter_option):
        """Render records with pagination"""
        
        # Get current filter state
        search_term = st.session_state.get(f'search_{status}', '')
        filter_option = st.session_state.get(f'quick_filter_{status}', 'All Records')
        
        # Get total count for pagination
        total_records = self._get_total_filtered_count(status, search_term, filter_option)
        
        if total_records == 0:
            st.info("No records found matching your criteria.")
            return
        
        # Load all records (no pagination)
        records = self._get_all_records_direct(status, search_term, filter_option)
        
        # Display record count
        if search_term:
            st.write(f"**Showing {len(records)} of {total_records} {status} records matching '{search_term}'**")
        elif filter_option != "All Records":
            st.write(f"**Showing {len(records)} of {total_records} {status} {filter_option.lower()}**")
        else:
            st.write(f"**Showing {len(records)} {status} records**")
        
        # Render the records table with selection
        self._render_records_dataframe(records, status)

    def _render_records_dataframe(self, records: pd.DataFrame, status: str):
        """Render records in an optimized dataframe with selection"""
        if len(records) == 0:
            return
        
        # Initialize selection state
        if 'selected_records' not in st.session_state:
            st.session_state.selected_records = []
        
        # Prepare display data with selection
        display_data = []
        for _, record in records.iterrows():
            is_selected = record['id'] in st.session_state.selected_records
            
            display_record = {
                'Select': is_selected,
                'Cover': record.get('image_url', ''),
                'Artist': record.get('artist', ''),
                'Title': record.get('title', ''),
                'Store Price': self._format_currency(record.get('store_price')),
                'eBay Sell At': self._format_currency(record.get('ebay_sell_at')),
                'eBay Low Shipping': self._format_currency(record.get('ebay_low_shipping')),
                'Genre': record.get('genre', ''),
                'File At': record.get('file_at', ''),
                'Barcode': record.get('barcode', ''),
                'Condition': record.get('condition', ''),
                'Format': record.get('format', ''),
                'Added': record.get('created_at', '')[:16] if record.get('created_at') else ''
            }
            
            display_data.append(display_record)
        
        display_df = pd.DataFrame(display_data)
        
        # Configure columns for better display
        column_config = {
            'Select': st.column_config.CheckboxColumn('Select', width='small'),
            'Cover': st.column_config.ImageColumn('Cover', width='small'),
            'Artist': st.column_config.TextColumn('Artist', width='medium'),
            'Title': st.column_config.TextColumn('Title', width='large'),
            'Store Price': st.column_config.TextColumn('Store Price', width='small'),
            'eBay Sell At': st.column_config.TextColumn('eBay Sell At', width='small'),
            'eBay Low Shipping': st.column_config.TextColumn('eBay Low Shipping', width='small'),
            'Genre': st.column_config.TextColumn('Genre', width='medium'),
            'File At': st.column_config.TextColumn('File At', width='small'),
            'Barcode': st.column_config.TextColumn('Barcode', width='small'),
            'Condition': st.column_config.TextColumn('Condition', width='small'),
            'Format': st.column_config.TextColumn('Format', width='small'),
            'Added': st.column_config.TextColumn('Added', width='small')
        }
        
        # Add select all checkbox with toggle functionality
        col1, col2 = st.columns([1, 5])
        with col1:
            all_currently_selected = st.checkbox("Select All", key=f"select_all_{status}")
        
        # Display editable dataframe with selection - FIXED: use full width
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            use_container_width=True,
            height=min(600, 35 * len(display_df) + 40),
            hide_index=True,
            key=f"records_editor_{status}"
        )
        
        # Handle select all functionality - FIXED TOGGLE BEHAVIOR
        if all_currently_selected:
            selected_ids = records['id'].tolist()
        else:
            selected_ids = []
        
        # Update selection state based on editor changes
        if set(selected_ids) != set(st.session_state.selected_records):
            st.session_state.selected_records = selected_ids
            st.rerun()

    def _format_currency(self, value):
        """Format currency values"""
        if not value:
            return "$N/A"
        return f"${float(value):.2f}"

    def _get_all_records_direct(self, status: str, search_term: str = None, filter_option: str = None) -> pd.DataFrame:
        """Get all records directly from records_with_genres view with optional filtering"""
        conn = st.session_state.db_manager._get_connection()
        
        # Simple query - using the records_with_genres view
        base_query = """
        SELECT 
            id, artist, title, 
            discogs_median_price, discogs_lowest_price, discogs_highest_price,
            ebay_median_price, ebay_lowest_price, ebay_highest_price, ebay_count, ebay_sell_at, ebay_low_shipping,
            image_url, barcode, format, condition, created_at, genre, file_at, store_price
        FROM records_with_genres 
        WHERE status = ?
        """
        
        params = [status]
        
        # Apply search filter
        if search_term:
            base_query += """
            AND (artist LIKE ? 
                OR title LIKE ? 
                OR barcode LIKE ?)
            """
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern])
        
        # Apply quick filters
        if filter_option == "No Barcode":
            base_query += " AND (barcode IS NULL OR barcode = '')"
        elif filter_option == "No Price Data":
            base_query += " AND (discogs_median_price IS NULL OR discogs_median_price = 0)"
        elif filter_option == "No Genre":
            base_query += " AND (genre IS NULL OR genre = '')"
        elif filter_option == "No File At":
            base_query += " AND (file_at IS NULL OR file_at = '')"
        elif filter_option == "No eBay Price":
            base_query += " AND (ebay_sell_at IS NULL OR ebay_sell_at = 0)"
        
        # FIXED: Proper numerical sorting for ALL price columns with NULLs at bottom
        base_query += """ 
        ORDER BY 
            CASE 
                WHEN ebay_median_price IS NULL OR ebay_median_price = '' OR ebay_median_price = 0 THEN 999999
                ELSE CAST(ebay_median_price AS REAL)
            END ASC,
            CASE 
                WHEN discogs_median_price IS NULL OR discogs_median_price = '' OR discogs_median_price = 0 THEN 999999
                ELSE CAST(discogs_median_price AS REAL)
            END ASC,
            CASE 
                WHEN ebay_lowest_price IS NULL OR ebay_lowest_price = '' OR ebay_lowest_price = 0 THEN 999999
                ELSE CAST(ebay_lowest_price AS REAL)
            END ASC,
            CASE 
                WHEN ebay_highest_price IS NULL OR ebay_highest_price = '' OR ebay_highest_price = 0 THEN 999999
                ELSE CAST(ebay_highest_price AS REAL)
            END ASC,
            CASE 
                WHEN discogs_lowest_price IS NULL OR discogs_lowest_price = '' OR discogs_lowest_price = 0 THEN 999999
                ELSE CAST(discogs_lowest_price AS REAL)
            END ASC,
            CASE 
                WHEN discogs_highest_price IS NULL OR discogs_highest_price = '' OR discogs_highest_price = 0 THEN 999999
                ELSE CAST(discogs_highest_price AS REAL)
            END ASC
        """
        
        df = pd.read_sql_query(base_query, conn, params=params)
        conn.close()
        return df

    def _get_total_filtered_count(self, status: str, search_term: str = None, filter_option: str = None) -> int:
        """Get total count of records after applying filters"""
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        
        base_query = "SELECT COUNT(*) FROM records WHERE status = ?"
        params = [status]
        
        if search_term:
            base_query += """
            AND (artist LIKE ? 
                OR title LIKE ? 
                OR barcode LIKE ?)
            """
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern, search_pattern, search_pattern])
        
        if filter_option == "No Barcode":
            base_query += " AND (barcode IS NULL OR barcode = '')"
        elif filter_option == "No Price Data":
            base_query += " AND (discogs_median_price IS NULL OR discogs_median_price = 0)"
        elif filter_option == "No Genre":
            base_query += " AND (genre_id IS NULL)"
        elif filter_option == "No File At":
            base_query += " AND (file_at IS NULL OR file_at = '')"
        elif filter_option == "No eBay Price":
            base_query += " AND (ebay_sell_at IS NULL OR ebay_sell_at = 0)"
        
        cursor.execute(base_query, params)
        count_result = cursor.fetchone()
        count = count_result[0] if count_result else 0
        conn.close()
        return int(count) if count is not None else 0