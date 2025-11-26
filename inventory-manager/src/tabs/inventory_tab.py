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
        
        # Database statistics - show only user's records for consignors
        stats = self._get_user_database_stats()
            
        # Top row: Stats
        col1, col2 = st.columns([1, 1])
        with col1:
            st.metric("Inventory Records", stats['records_count'])
        
        # Inventory Controls (NO EXPANDER)
        self._render_unified_operations()
        
        # API Requests & Responses - Show immediately when available
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
        
        # Action type selection - renamed from Search Type
        col1, col2 = st.columns([1, 3])
        with col1:
            search_type = st.radio(
                "Action:",
                ["Add item", "Edit or Delete item"],
                key="search_type_radio"
            )
        
        # Search input and button
        search_input = st.text_input(
            "Search:",
            placeholder="Enter barcode, artist, or title...",
            key="unified_search_input"
        )
        
        col1, col2 = st.columns([3, 1])
        with col1:
            search_submitted = st.button("🔍 Search", width='stretch')
        
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
            self.display_handler.render_edit_section(st.session_state.selected_record, self._handle_add_record, self._handle_update_record, self.discogs_handler, self.ebay_handler)
        
        # Checkout section for database search
        if (search_type == "Edit or Delete item" and 
            st.session_state.checkout_records and
            st.session_state.record_added is None):
            self.display_handler.render_checkout_section(st.session_state.checkout_records, self._process_checkout)

    def _handle_add_record(self, genre):
        """Handle adding an inventory record to database"""
        record_data = st.session_state.selected_record['data']
        
        success, record_id = self.record_ops_handler.add_inventory_record(
            record_data, 
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

    def _handle_update_record(self, genre):
        """Handle updating a database record"""
        record_data = st.session_state.selected_record['data']
        
        success = self.record_ops_handler.update_database_record(record_data, genre)
        
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

    def _render_api_logs_section(self):
        """Render API logs section immediately when available"""
        if 'api_logs' in st.session_state and st.session_state.api_logs:
            with st.expander("📡 API Requests & Responses", expanded=False):
                for api_title in st.session_state.api_logs:
                    if api_title in st.session_state.api_details:
                        details = st.session_state.api_details[api_title]
                        duration = details.get('duration', 'N/A')
                        display_title = f"{api_title} ({duration}s)" if duration != 'N/A' else api_title
                        with st.expander(display_title, expanded=False):
                            # FIX: Check if raw_request exists before accessing it
                            request_data = details.get('raw_request', details.get('request', {}))
                            st.write("**Request:**")
                            st.json(request_data)
                            
                            # FIX: Check if raw_response exists before accessing it
                            response_data = details.get('raw_response', details.get('response', {}))
                            if response_data:
                                st.write("**Response:**")
                                st.json(response_data)

    def _get_user_database_stats(self) -> dict:
        """Get database statistics filtered by user for consignors"""
        user = st.session_state.get('user', {})
        user_role = user.get('role', 'consignor')
        user_id = user.get('id')
        
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        
        if user_role == 'consignor' and user_id:
            # For consignors, only count their own records
            cursor.execute('''
                SELECT COUNT(*) FROM records r
                WHERE r.consignor_id = ?
            ''', (user_id,))
        else:
            # For admins, count all records
            cursor.execute('SELECT COUNT(*) FROM records')
        
        records_count_result = cursor.fetchone()
        records_count = records_count_result[0] if records_count_result else 0
        
        conn.close()
        
        return {
            'records_count': int(records_count) if records_count is not None else 0
        }