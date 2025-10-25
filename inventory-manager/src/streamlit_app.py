import sys
import os

# Add the correct path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/inventory-manager/src'))

# Now import all modules
import streamlit as st
from pathlib import Path
import glob
from dotenv import load_dotenv
from database_manager import DatabaseManager
from discogs_handler import DiscogsHandler
from search_tab import SearchTab
from records_tab import RecordsTab
from statistics_tab import StatisticsTab
from genre_mappings_tab import GenreMappingsTab
from print_tab import PrintTab
from debug_tab import DebugTab
from database_switch_tab import DatabaseSwitchTab

# --- Load environment variables ---
try:
    load_dotenv()
except:
    pass

# --- Configuration ---
IMAGE_FOLDER = Path("images")
IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
PAYLOADS_FOLDER = Path("payloads")
PAYLOADS_FOLDER.mkdir(parents=True, exist_ok=True)

CATEGORY_MAP = {
    "Vinyl": "176985",
    "CDs": "176984", 
    "Cassettes": "176983"
}

def get_environment_variables(debug_tab):
    """Get environment variables from either .env file or Streamlit secrets"""
    env_vars = {}
    
    required_vars = [
        "IMAGEBB_API_KEY",
        "DISCOGS_USER_TOKEN", 
        "EBAY_CLIENT_ID",
        "EBAY_CLIENT_SECRET"
    ]
    
    for var in required_vars:
        try:
            if hasattr(st, 'secrets') and var in st.secrets:
                env_vars[var] = st.secrets[var]
                debug_tab.add_log("SECRETS", f"✅ {var} loaded from secrets", {"source": "secrets"})
            else:
                env_value = os.getenv(var)
                if env_value:
                    env_vars[var] = env_value
                    debug_tab.add_log("ENV", f"✅ {var} loaded from environment", {"source": ".env"})
                else:
                    env_vars[var] = None
                    debug_tab.add_log("ERROR", f"❌ {var} not found in secrets or environment")
        except Exception as e:
            env_vars[var] = None
            debug_tab.add_log("ERROR", f"❌ Error loading {var}: {e}")
                
    return env_vars

def initialize_database_manager():
    """Initialize database manager"""
    return DatabaseManager()

def main():
    """Main function to run the Streamlit app"""
    # Set page config - this must be the first Streamlit command
    st.set_page_config(
        page_title="PigStyle Inventory Manager",
        page_icon="🎵",
        layout="wide"
    )
    
    # Initialize debug tab first
    debug_tab = DebugTab()
    
    # Get environment variables
    env_vars = get_environment_variables(debug_tab)

    IMAGEBB_API_KEY = env_vars["IMAGEBB_API_KEY"]
    DISCOGS_USER_TOKEN = env_vars["DISCOGS_USER_TOKEN"]
    EBAY_CLIENT_ID = env_vars["EBAY_CLIENT_ID"]
    EBAY_CLIENT_SECRET = env_vars["EBAY_CLIENT_SECRET"]

    # Initialize session state defaults
    if "db_manager" not in st.session_state:
        st.session_state.db_manager = initialize_database_manager()
        debug_tab.add_log("DATABASE", "Database manager initialized")

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
        try:
            discogs_handler = DiscogsHandler(DISCOGS_USER_TOKEN, debug_tab)
            debug_tab.add_log("DISCOGS", "Discogs handler initialized successfully")
        except Exception as e:
            debug_tab.add_log("ERROR", f"Failed to initialize Discogs: {e}")
            discogs_handler = None
    else:
        debug_tab.add_log("ERROR", "DISCOGS_USER_TOKEN not found")
 
    # Initialize all tabs
    search_tab = SearchTab(discogs_handler, debug_tab)
    records_tab = RecordsTab()
    statistics_tab = StatisticsTab()
    genre_mappings_tab = GenreMappingsTab()
    print_tab = PrintTab()
    database_switch_tab = DatabaseSwitchTab()

    # Main app header
    st.title("🎵 PigStyle Inventory Manager")
    
    # Create tabs - now including Debug and Database Switch
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📥 Search & Add", 
        "📚 Records", 
        "📊 Statistics", 
        "🏷️ Genre Mappings", 
        "🖨️ Print",
        "🗃️ Database",
        "🔧 Debug"
    ])
    
    with tab1:
        search_tab.render()
    
    with tab2:
        records_tab.render()
    
    with tab3:
        statistics_tab.render()
    
    with tab4:
        genre_mappings_tab.render()
    
    with tab5:
        print_tab.render()
        
    with tab6:
        database_switch_tab.render()
        
    with tab7:
        debug_tab.render()


if __name__ == "__main__":
    main()