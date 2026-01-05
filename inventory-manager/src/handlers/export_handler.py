import streamlit as st
import pandas as pd
from datetime import datetime
import time
from handlers.draft_csv_handler import DraftCSVHandler
import requests
from handlers.rounding_handler import RoundingHandler
from handlers.config_handler import ConfigHandler  # NEW IMPORT

class ExportHandler:
    def __init__(self, price_handler, base_url="https://arjanshaw.pythonanywhere.com"):
        self.price_handler = price_handler
        self.base_url = base_url
        self.config_handler = ConfigHandler()  # NEW: ConfigHandler instance
 
    def export_ebay_list(self):
        """Export selected records as eBay draft listings"""
        if not st.session_state.selected_records:
            st.warning("Please select records first using the checkboxes in the table.")
            return
        
        # Get selected records data using API
        selected_ids = st.session_state.selected_records
        records = self._get_records_by_ids(selected_ids)
        
        if not records:
            st.warning("No records found for the selected IDs")
            return
        
        # Generate eBay formatted TXT
        draft_handler = DraftCSVHandler()
        ebay_content = draft_handler.generate_ebay_txt_from_records(records, self.price_handler)
        
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
        
        st.success(f"✅ eBay draft file ready! {len(records)} records formatted for eBay import.")

    def _calculate_ebay_sell_at(self, ebay_lowest_price, ebay_low_shipping, discogs_median_price):
        """Calculate eBay sell price with all rules applied"""
        # Get SHIPPING_COST from config via ConfigHandler
        shipping_cost = self.config_handler.get('SHIPPING_COST', 5.72)
        
        return RoundingHandler.calculate_ebay_sell_at(
            ebay_lowest_price, 
            ebay_low_shipping, 
            discogs_median_price, 
            shipping_cost
        )

    def update_all_ebay_prices(self, ebay_handler):
        """Update eBay prices for all inventory records - DO NOT update ebay_sell_at here"""
        if not ebay_handler:
            st.error("eBay handler not available. Check your eBay API credentials.")
            return 0
        
        # Get all records using API
        records = self._get_all_records()
        
        if not records:
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