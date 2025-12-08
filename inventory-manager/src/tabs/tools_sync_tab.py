# FILE: inventory-manager/src/tabs/tools_sync_tab.py
import streamlit as st
import subprocess
import os
from pathlib import Path
from datetime import datetime

class ToolsSyncTab:
    def __init__(self):
        pass  # Removed GitHubSyncHandler parameter
    
    def _get_config_value(self, config_key):
        """Get config value and throw exception if not found"""
        value = st.session_state.db_manager.get_config_value(config_key, None)
        if value is None:
            raise ValueError(f"Configuration key '{config_key}' not found in app_config table")
        try:
            if config_key == 'STORE_CAPACITY':
                return int(value)
            else:
                return float(value)
        except ValueError:
            raise ValueError(f"Configuration key '{config_key}' has invalid value: '{value}'. Must be a number.")
    
    def render(self):
        st.header("🛠️ Tools & Sync")
        
        col1, col2 = st.columns(2)
        
        # GitHub Sync Section - REMOVED GITHUB SYNC FUNCTIONALITY
        with col2:
            st.subheader("🔄 GitHub Sync")
            st.warning("GitHub sync functionality is currently disabled")
            
            # Show placeholder status
            st.write("**Repo:** `GitHub sync disabled`")
            st.write("**Status:** ❌ Disabled")
        
        # Store Capacity Configuration
        st.subheader("🏪 Store Capacity Configuration")
        col1, col2 = st.columns(2)
        
        with col1:
            try:
                current_capacity = self._get_config_value('STORE_CAPACITY')
                store_capacity = st.number_input(
                    "Store Capacity (total records):",
                    min_value=100,
                    max_value=10000,
                    value=current_capacity,
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
            except ValueError as e:
                st.error(f"❌ Configuration Error: {e}")
                st.warning("Please go to Admin Config tab to set up configuration values.")
        
        with col2:
            # Show store fill information
            try:
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
            except ValueError as e:
                st.error(f"❌ Cannot calculate store fill: {e}")

    def _get_store_fill_info(self):
        """Calculate store fill percentage based on total inventory and store capacity using API"""
        # Get store capacity from config
        store_capacity = self._get_config_value('STORE_CAPACITY')
        
        # Get total inventory count using API
        records_df = st.session_state.db_manager.get_all_records()
        total_inventory = len(records_df)
        
        # Calculate fill fraction and percentage
        fill_fraction = total_inventory / store_capacity if store_capacity > 0 else 0
        fill_percentage = fill_fraction * 100
        
        store_fill_info = {
            'total_inventory': total_inventory,
            'store_capacity': store_capacity,
            'fill_fraction': fill_fraction,
            'fill_percentage': fill_percentage
        }
        
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