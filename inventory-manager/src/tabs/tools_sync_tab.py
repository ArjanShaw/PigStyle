# FILE: inventory-manager/src/tabs/tools_sync_tab.py
import streamlit as st
import subprocess
import os
from pathlib import Path
from datetime import datetime

class ToolsSyncTab:
    def __init__(self, gallery_json_manager=None, github_sync_handler=None):
        self.gallery_json_manager = gallery_json_manager
        self.github_sync_handler = github_sync_handler
    
    def render(self):
        st.header("🛠️ Tools & Sync")
        
        col1, col2 = st.columns(2)
        
        # Gallery JSON Management
        with col1:
            st.subheader("🔄 Gallery JSON")
            if st.button("🔄 Manual JSON Rebuild", width='stretch'):
                if self.gallery_json_manager:
                    with st.spinner("Rebuilding gallery JSON..."):
                        success = self.gallery_json_manager.trigger_rebuild(async_mode=False)
                    if success:
                        st.success("✅ Gallery JSON rebuilt successfully!")
                    else:
                        st.error("❌ Gallery JSON rebuild failed")
                else:
                    st.error("Gallery JSON manager not initialized")
            
            if self.gallery_json_manager:
                status = self.gallery_json_manager.get_rebuild_status()
                st.write(f"**Status:** {'Rebuilding...' if status['in_progress'] else 'Ready'}")
                json_path = self.gallery_json_manager.get_json_path()
                st.write(f"**JSON Path:** `{json_path}`")
        
        # GitHub Sync Section
        with col2:
            st.subheader("🔄 GitHub Sync")
            if st.button("🔄 Manual GitHub Sync", width='stretch'):
                if self.github_sync_handler:
                    with st.spinner("Syncing with GitHub..."):
                        success, message = self.github_sync_handler.trigger_sync()
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
                else:
                    st.error("GitHub sync handler not initialized")
            
            if self.github_sync_handler:
                status = self.github_sync_handler.get_sync_status()
                st.write(f"**Repo:** `{status['repo_path']}`")
                st.write(f"**Script:** {'✅ Found' if status['script_exists'] else '❌ Missing'}")
                st.write(f"**Changes pending:** {'✅ Yes' if status['has_changes'] else '❌ No'}")
                st.write(f"**Last commit:** {status['last_commit']}")
        
        # Store Capacity Configuration
        st.subheader("🏪 Store Capacity Configuration")
        col1, col2 = st.columns(2)
        
        with col1:
            current_capacity = st.session_state.db_manager.get_config_value('STORE_CAPACITY', '1000')
            store_capacity = st.number_input(
                "Store Capacity (total records):",
                min_value=100,
                max_value=10000,
                value=int(current_capacity),
                step=100,
                help="Total number of records the store can hold",
                key="store_capacity_input"
            )
            if st.button("💾 Save Store Capacity", width='stretch'):
                success = st.session_state.db_manager.set_config_value('STORE_CAPACITY', str(store_capacity))
                if success:
                    st.success("✅ Store capacity saved!")
                    # Clear cached store fill info to force refresh
                    if 'store_fill_info' in st.session_state:
                        del st.session_state.store_fill_info
                    if 'store_capacity_cache' in st.session_state:
                        del st.session_state.store_capacity_cache
                    st.rerun()
                else:
                    st.error("❌ Failed to save store capacity")
        
        with col2:
            # Show store fill information
            store_fill_info = self._get_store_fill_info()
            st.metric(
                "Store Fill Percentage", 
                f"{store_fill_info['fill_percentage']:.1f}%",
                f"{store_fill_info['total_inventory']} / {store_fill_info['store_capacity']} records"
            )
            
            # Show commission rate based on store fill
            commission_rate = self._calculate_commission_rate(store_fill_info['fill_percentage'])
            st.metric(
                "Current Commission Rate",
                f"{commission_rate:.1%}",
                "Based on store fill"
            )
        
        # Database Management
        st.subheader("🗃️ Database Tools")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Update File Locations", width='stretch'):
                if hasattr(st.session_state, 'db_manager'):
                    updated_count = st.session_state.db_manager.update_file_at_for_all_records()
                    st.success(f"✅ Updated file locations for {updated_count} records!")
                else:
                    st.error("Database manager not available")
        
        with col2:
            if st.button("🗑️ Clear All Records", width='stretch', type="secondary"):
                if hasattr(st.session_state, 'db_manager'):
                    if st.checkbox("I understand this will delete ALL records permanently"):
                        if st.button("CONFIRM DELETE ALL", type="primary", width='stretch'):
                            st.session_state.db_manager.clear_database()
                            st.success("✅ All records deleted!")
                            st.rerun()
        
        # System Information
        st.subheader("📊 System Info")
        if hasattr(st.session_state, 'db_manager'):
            stats = st.session_state.db_manager.get_database_stats()
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", stats['records_count'])
            with col2:
                st.metric("Users", stats['users_count'])
            with col3:
                st.metric("Database Path", stats['db_path'])

    def _get_store_fill_info(self):
        """Calculate store fill percentage based on total inventory and store capacity using API"""
        # Use cached value if available and store capacity hasn't changed
        if 'store_fill_info' in st.session_state and 'store_capacity_cache' in st.session_state:
            current_capacity = st.session_state.db_manager.get_config_value('STORE_CAPACITY', '1000')
            if st.session_state.store_capacity_cache == current_capacity:
                return st.session_state.store_fill_info
        
        # Get store capacity from config
        store_capacity = int(st.session_state.db_manager.get_config_value('STORE_CAPACITY', '1000'))
        
        # Get total inventory count using API
        records_df = st.session_state.db_manager.get_all_records()
        total_inventory = len(records_df)
        
        # Calculate fill percentage
        fill_percentage = (total_inventory / store_capacity) * 100 if store_capacity > 0 else 0
        
        store_fill_info = {
            'total_inventory': total_inventory,
            'store_capacity': store_capacity,
            'fill_percentage': fill_percentage
        }
        
        # Cache the result
        st.session_state.store_fill_info = store_fill_info
        st.session_state.store_capacity_cache = store_capacity
        
        return store_fill_info

    def _calculate_commission_rate(self, fill_percentage):
        """Calculate commission rate based on store fill percentage"""
        fill_fraction = fill_percentage / 100.0
        if fill_fraction < 0.60:
            return 0.10  # 10% when below 60%
        elif fill_fraction <= 1.10:
            # Linear increase from 10% to 40% between 60% and 110%
            # At 0.60: 0.10, at 1.10: 0.40
            slope = (0.40 - 0.10) / (1.10 - 0.60)
            return 0.10 + slope * (fill_fraction - 0.60)
        else:
            return 0.40  # 40% when above 110%