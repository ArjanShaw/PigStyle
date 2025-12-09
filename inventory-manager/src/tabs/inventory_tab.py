import streamlit as st
import pandas as pd
from datetime import datetime
import time
from handlers.search_handler import SearchHandler
from handlers.record_operations_handler import RecordOperationsHandler
from handlers.display_handler import DisplayHandler
from handlers.export_handler import ExportHandler
from handlers.price_handler import PriceHandler
from handlers.youtube_handler import YouTubeHandler

class InventoryTab:
    def __init__(self, discogs_handler, ebay_handler=None, youtube_handler=None):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
        self.youtube_handler = youtube_handler
        self.price_handler = PriceHandler()
        
        self.search_handler = SearchHandler(discogs_handler)
        self.record_ops_handler = RecordOperationsHandler(discogs_handler, ebay_handler)
        self.display_handler = DisplayHandler(self.youtube_handler)
        self.export_handler = ExportHandler(self.price_handler)

    def _get_config_value(self, config_key):
        value = st.session_state.db_manager.get_config_value(config_key, None)
        if value is None:
            raise ValueError(f"Configuration key '{config_key}' not found in app_config table")
        if config_key == 'STORE_CAPACITY':
            return int(value)
        else:
            return float(value)

    def render(self):
        stats = self._get_user_database_stats()
        
        store_fill_info = self._get_store_fill_info()
        consignment_rate = self._calculate_consignment_rate(store_fill_info['fill_fraction'])
        
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        with col1:
            st.metric("Inventory Records", stats['records_count'])
        with col2:
            st.metric("Store Fill", f"{store_fill_info['fill_percentage']:.1f}%")
        with col3:
            st.metric("Consignment Rate", f"{consignment_rate:.1%}")
        
        # Display last added record - single line, no image
        self._render_last_added_record_simple()
        
        if store_fill_info['fill_fraction'] > 1.10:
            st.error("🚨 Store is over capacity! Cannot add new items.")
        
        self._render_unified_operations(store_fill_info['fill_fraction'])

    def _render_last_added_record_simple(self):
        """Display the last record added to the database - simple single line"""
        # Get the most recent record using API
        recent_records = st.session_state.db_manager.get_recent_records(limit=1)
        
        if not recent_records.empty:
            last_record = recent_records.iloc[0]
            
            artist = last_record.get('artist', 'Unknown Artist')
            title = last_record.get('title', 'Unknown Title')
            store_price = last_record.get('store_price', 0.0)
            
            # Single line display with minimal styling
            st.markdown(f"**📝 Last Added:** {artist} - {title} (${store_price:.2f})")
        else:
            st.markdown("**📝 Last Added:** No records yet")

    def _render_unified_operations(self, store_fill_fraction):
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
        if 'search_triggered' not in st.session_state:
            st.session_state.search_triggered = False
        if 'search_query' not in st.session_state:
            st.session_state.search_query = ""
        
        # Clear selected record after successful addition
        if st.session_state.get('record_added'):
            st.session_state.selected_record = None
            st.session_state.record_added = None
            st.session_state.search_results = {}
            st.session_state.current_search = ""
            st.session_state.search_query = ""
        
        col1, col2 = st.columns([1, 3])
        with col1:
            search_type = st.radio(
                "Action:",
                ["Add item", "Edit or Delete item"],
                key="search_type_radio",
                disabled=(store_fill_fraction > 1.10 and "Add item" in ["Add item"])
            )
        
        search_disabled = (store_fill_fraction > 1.10 and search_type == "Add item")
        
        with st.form(key="search_form", clear_on_submit=False):
            search_input = st.text_input(
                "Search:",
                value=st.session_state.get('search_query', ''),
                placeholder="Enter barcode, artist, or title...",
                key="unified_search_input",
                disabled=search_disabled
            )
            
            col1, col2 = st.columns([3, 1])
            with col1:
                search_submitted = st.form_submit_button("🔍 Search", width='stretch', disabled=search_disabled)
        
        if search_submitted:
            st.session_state.search_query = search_input
            st.session_state.search_triggered = True
        
        if (st.session_state.search_triggered and 
            st.session_state.search_query and 
            st.session_state.search_query.strip()):
            
            search_term = st.session_state.search_query.strip()
            st.session_state.current_search = search_term
            st.session_state.selected_record = None
            st.session_state.record_added = None
            
            if search_type == "Add item":
                results = self.search_handler.perform_discogs_search(search_term)
                st.session_state.search_results[search_term] = results
            else:
                results = self.search_handler.perform_database_search(search_term)
                st.session_state.search_results[search_term] = results
            
            st.session_state.search_triggered = False
            st.session_state.last_search = search_term
            st.rerun()
        
        if (st.session_state.current_search and 
            st.session_state.current_search in st.session_state.search_results and
            st.session_state.record_added is None):
            
            results = st.session_state.search_results[st.session_state.current_search]
            
            if st.session_state.selected_record:
                self.display_handler.render_selected_record_only(st.session_state.selected_record)
            else:
                if search_type == "Add item":
                    self.display_handler.render_discogs_results(results, search_type)
                else:
                    self.display_handler.render_database_results(results, search_type)
        
        if (st.session_state.selected_record and 
            st.session_state.record_added is None):
            self.display_handler.render_edit_section(
                st.session_state.selected_record, 
                self._handle_add_record, 
                self._handle_update_record, 
                self.discogs_handler, 
                self.ebay_handler,
                store_fill_fraction
            )
        
        if (search_type == "Edit or Delete item" and 
            st.session_state.checkout_records and
            st.session_state.record_added is None):
            self.display_handler.render_checkout_section(st.session_state.checkout_records, self._process_checkout)

    def _get_store_fill_info(self):
        store_capacity = self._get_config_value('STORE_CAPACITY')
        
        records_df = st.session_state.db_manager.get_all_records()
        total_inventory = len(records_df)
        
        fill_fraction = total_inventory / store_capacity if store_capacity > 0 else 0
        fill_percentage = fill_fraction * 100
        
        return {
            'total_inventory': total_inventory,
            'store_capacity': store_capacity,
            'fill_fraction': fill_fraction,
            'fill_percentage': fill_percentage
        }

    def _calculate_consignment_rate(self, fill_fraction):
        if fill_fraction < 0.60:
            return 0.10
        elif fill_fraction <= 1.10:
            slope = (0.40 - 0.10) / (1.10 - 0.60)
            return 0.10 + slope * (fill_fraction - 0.60)
        else:
            return 0.40

    def _handle_add_record(self, genre):
        record_data = st.session_state.selected_record['data']
        
        success, record_id = self.record_ops_handler.add_inventory_record(
            record_data, 
            genre, 
            st.session_state.current_search
        )
        
        if success:
            import time
            time.sleep(0.5)
            
            # Set flag to clear UI
            st.session_state.record_added = True
            st.session_state.records_updated += 1
            
            # Show success message
            st.success(f"✅ Record added successfully!")
            
            # Force a rerun to clear the UI
            st.rerun()
        else:
            st.error("Failed to add record to database")

    def _handle_update_record(self, genre):
        record_data = st.session_state.selected_record['data']
        
        success = self.record_ops_handler.update_database_record(record_data, genre)
        
        if success:
            st.success("✅ Record updated successfully!")
            st.session_state.records_updated += 1
            st.session_state.selected_record = None
            
            st.rerun()
        else:
            st.error("❌ Failed to update record")

    def _process_checkout(self):
        st.warning("Checkout functionality is not available. The status column has been removed from the database.")
        return 0

    def _get_user_database_stats(self) -> dict:
        user = st.session_state.get('user', {})
        user_role = user.get('role', 'consignor')
        user_id = user.get('id')
        
        stats = st.session_state.db_manager.get_user_database_stats(user_id) if user_role == 'consignor' and user_id else st.session_state.db_manager.get_database_stats()
        
        return {
            'records_count': stats.get('records_count', 0)
        }