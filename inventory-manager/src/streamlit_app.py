import streamlit as st
import os
import time
from pathlib import Path
from database_manager import DatabaseManager
from handlers.discogs_handler import DiscogsHandler
from tabs.inventory_tab import InventoryTab
from tabs.statistics_tab import StatisticsTab
from tabs.ebay_tab import EBayTab
from tabs.store_pricing_tab import StorePricingTab
from tabs.tools_sync_tab import ToolsSyncTab
from tabs.consignment_tab import ConsignmentTab
from handlers.ebay_handler import EbayHandler
from gallery.generator import GalleryJSONManager
from handlers.github_sync_handler import GitHubSyncHandler
from handlers.api_key_handler import APIKeyHandler
from config import AppConfig
from handlers.youtube_handler import YouTubeHandler

# --- Configuration ---
IMAGE_FOLDER = Path("images")
IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
PAYLOADS_FOLDER = Path("payloads")
PAYLOADS_FOLDER.mkdir(parents=True, exist_ok=True)

def main():
    """Main function to run the Streamlit app"""
    # Set page config - this must be the first Streamlit command
    st.set_page_config(
        page_title="PigStyle Inventory Manager",
        page_icon="🎵",
        layout="wide"
    )
    
    # Initialize configuration
    config = AppConfig()
    
    # Initialize API Key Handler
    api_key_handler = APIKeyHandler()
    
    # Get environment variables - this will validate the .env file
    env_vars = api_key_handler.get_environment_variables()

    IMAGEBB_API_KEY = env_vars["IMAGEBB_API_KEY"]
    DISCOGS_USER_TOKEN = env_vars["DISCOGS_USER_TOKEN"]
    EBAY_CLIENT_ID = env_vars["EBAY_CLIENT_ID"]
    EBAY_CLIENT_SECRET = env_vars["EBAY_CLIENT_SECRET"]
    YOUTUBE_API_KEY = env_vars.get("YOUTUBE_API_KEY")

    # Initialize session state defaults
    if "db_manager" not in st.session_state:
        db_path = config.get_database_path()
        st.session_state.db_manager = DatabaseManager(db_path)
        st.session_state.config = config

    # Initialize Gallery JSON Manager AFTER db_manager is set
    if "gallery_json_manager" not in st.session_state:
        st.session_state.gallery_json_manager = GalleryJSONManager(st.session_state.db_manager)

    # Initialize GitHub Sync Handler
    if "github_sync_handler" not in st.session_state:
        st.session_state.github_sync_handler = GitHubSyncHandler(
            repo_path="/home/arjan-ubuntu/Documents/PigStyle",
            gallery_json_manager=st.session_state.gallery_json_manager
        )

    if "search_results" not in st.session_state:
        st.session_state.search_results = {}

    if "current_search" not in st.session_state:
        st.session_state.current_search = ""

    if "last_added" not in st.session_state:
        st.session_state.last_added = None

    if "records_updated" not in st.session_state:
        st.session_state.records_updated = 0

    if "selected_records" not in st.session_state:
        st.session_state.selected_records = []

    # Initialize Discogs handler
    discogs_handler = None
    if DISCOGS_USER_TOKEN:
        discogs_handler = DiscogsHandler(DISCOGS_USER_TOKEN)
    
    # Initialize eBay handler
    ebay_handler = None
    if EBAY_CLIENT_ID and EBAY_CLIENT_SECRET:
        ebay_handler = EbayHandler(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET)
    
    # Initialize YouTube handler
    youtube_handler = None
    if YOUTUBE_API_KEY:
        youtube_handler = YouTubeHandler(YOUTUBE_API_KEY)
    else:
        st.warning("YouTube API key not found. YouTube integration will be disabled.")
 
    # Initialize all tabs
    inventory_tab = InventoryTab(discogs_handler, ebay_handler, st.session_state.gallery_json_manager, youtube_handler)
    statistics_tab = StatisticsTab()
    ebay_tab = EBayTab(ebay_handler, st.session_state.gallery_json_manager)
    store_pricing_tab = StorePricingTab()
    tools_sync_tab = ToolsSyncTab(st.session_state.gallery_json_manager, st.session_state.github_sync_handler)
    consignment_tab = ConsignmentTab()

    # Create tabs
    tabs = st.tabs([
        "📦 Inventory",
        "🏪 Store Pricing",
        "🛒 eBay", 
        "📊 Statistics",
        "🤝 Consignment",
        "🛠️ Tools & Sync"
    ])
    
    with tabs[0]:
        inventory_tab.render()
    
    with tabs[1]:
        store_pricing_tab.render()
    
    with tabs[2]:
        ebay_tab.render()
    
    with tabs[3]:
        statistics_tab.render()
    
    with tabs[4]:
        consignment_tab.render()
    
    with tabs[5]:
        tools_sync_tab.render()

if __name__ == "__main__":
    main()