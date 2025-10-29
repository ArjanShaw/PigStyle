import sys
import os
import time

# Add the correct path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/inventory-manager/src'))

# Now import all modules
import streamlit as st
from pathlib import Path
import glob
from dotenv import load_dotenv
from database_manager import DatabaseManager
from handlers.discogs_handler import DiscogsHandler
from tabs.inventory_tab import InventoryTab
from tabs.statistics_tab import StatisticsTab
from tabs.debug_tab import DebugTab
from tabs.database_switch_tab import DatabaseSwitchTab
from tabs.expenses_tab import ExpensesTab
from handlers.ebay_handler import EbayHandler

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

# Database persistence file
DB_PERSISTENCE_FILE = "current_database.txt"

def get_environment_variables(debug_tab):
    """Get environment variables from either .env file or Streamlit secrets"""
    env_vars = {}
    
    required_vars = [
        "IMAGEBB_API_KEY",
        "DISCOGS_USER_TOKEN", 
        "EBAY_CLIENT_ID",
        "EBAY_CLIENT_SECRET"
    ]
    
    # Only log environment variable status once per session
    if 'env_vars_loaded' not in st.session_state:
        st.session_state.env_vars_loaded = False
    
    for var in required_vars:
        try:
            if hasattr(st, 'secrets') and var in st.secrets:
                env_vars[var] = st.secrets[var]
                if not st.session_state.env_vars_loaded:
                    debug_tab.add_log("SECRETS", f"✅ {var} loaded from secrets", {"source": "secrets"})
            else:
                env_value = os.getenv(var)
                if env_value:
                    env_vars[var] = env_value
                    if not st.session_state.env_vars_loaded:
                        debug_tab.add_log("ENV", f"✅ {var} loaded from environment", {"source": ".env"})
                else:
                    env_vars[var] = None
                    if not st.session_state.env_vars_loaded:
                        debug_tab.add_log("ERROR", f"❌ {var} not found in secrets or environment")
        except Exception as e:
            env_vars[var] = None
            if not st.session_state.env_vars_loaded:
                debug_tab.add_log("ERROR", f"❌ Error loading {var}: {e}")
    
    # Mark environment variables as loaded for this session
    st.session_state.env_vars_loaded = True
    return env_vars

def get_persisted_database_path():
    """Get the persisted database path from file"""
    try:
        if os.path.exists(DB_PERSISTENCE_FILE):
            with open(DB_PERSISTENCE_FILE, 'r') as f:
                db_path = f.read().strip()
                if db_path and os.path.exists(db_path):
                    return db_path
    except Exception as e:
        st.error(f"Error reading persisted database path: {e}")
    return None

def persist_database_path(db_path):
    """Persist the database path to file"""
    try:
        with open(DB_PERSISTENCE_FILE, 'w') as f:
            f.write(db_path)
        return True
    except Exception as e:
        st.error(f"Error persisting database path: {e}")
        return False

def initialize_database_manager():
    """Initialize database manager with persisted path or default"""
    persisted_path = get_persisted_database_path()
    if persisted_path:
        return DatabaseManager(persisted_path)
    
    # Default database
    return DatabaseManager()

def main():
    """Main function to run the Streamlit app"""
    # Set page config - this must be the first Streamlit command
    st.set_page_config(
        page_title="PigStyle Inventory Manager",
        page_icon="🎵",
        layout="wide"
    )
    
    # Initialize debug tab FIRST and use the SAME instance everywhere
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
        debug_tab.add_log("DATABASE", f"Database manager initialized with: {st.session_state.db_manager.db_path}")

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
        except Exception as e:
            debug_tab.add_log("ERROR", f"Failed to initialize Discogs: {e}")
            discogs_handler = None
    
    # Initialize eBay handler
    ebay_handler = None
    if EBAY_CLIENT_ID and EBAY_CLIENT_SECRET:
        try:
            ebay_handler = EbayHandler(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, debug_tab)
        except Exception as e:
            debug_tab.add_log("ERROR", f"Failed to initialize eBay: {e}")
            ebay_handler = None
 
    # Initialize all tabs - pass the SAME debug_tab instance to all
    inventory_tab = InventoryTab(discogs_handler, debug_tab, ebay_handler)
    statistics_tab = StatisticsTab()
    database_switch_tab = DatabaseSwitchTab()
    expenses_tab = ExpensesTab()
    # Use the SAME debug_tab instance for rendering

    # Create tabs with new order (REMOVED CHECKOUT TAB)
    tabs = st.tabs([
        "🗃️ Database",
        "📦 Inventory",  # Now includes both inventory, check-in, and checkout functionality
        "💰 Income",
        "💰 Expenses",
        "📊 Statistics",
        "🔧 Debug"
    ])
    
    with tabs[0]:
        database_switch_tab.render()
    
    with tabs[1]:
        inventory_tab.render()  # Now includes inventory, check-in, and checkout functionality
    
    with tabs[2]:
        inventory_tab.render_sold_tab()
    
    with tabs[3]:
        expenses_tab.render()
        
    with tabs[4]:
        statistics_tab.render()
        
    with tabs[5]:
        debug_tab.render()  # Use the SAME instance


if __name__ == "__main__":
    main()