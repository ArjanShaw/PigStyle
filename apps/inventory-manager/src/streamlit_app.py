import streamlit as st
from pathlib import Path
import os
from dotenv import load_dotenv
from database_manager import DatabaseManager
from discogs_handler import DiscogsHandler
from search_tab import SearchTab
from records_tab import RecordsTab
from statistics_tab import StatisticsTab
from genre_mappings_tab import GenreMappingsTab
from print_tab import PrintTab

# --- Load environment variables ---
try:
    load_dotenv()
except:
    pass

# --- Configuration ---
st.set_page_config(layout="wide")
IMAGE_FOLDER = Path("images")
IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
PAYLOADS_FOLDER = Path("payloads")
PAYLOADS_FOLDER.mkdir(parents=True, exist_ok=True)

# Database persistence file
DB_PERSISTENCE_FILE = "current_database.txt"

CATEGORY_MAP = {
    "Vinyl": "176985",
    "CDs": "176984", 
    "Cassettes": "176983"
}

def get_environment_variables():
    """Get environment variables from either .env file or Streamlit secrets"""
    env_vars = {}
    
    required_vars = [
        "IMAGEBB_API_KEY",
        "DISCOGS_USER_TOKEN", 
        "EBAY_CLIENT_ID",
        "EBAY_CLIENT_SECRET"
    ]
    
    # Debug: Check if secrets are available
    st.sidebar.write("### Secrets Debug")
    try:
        if hasattr(st, 'secrets'):
            st.sidebar.write("✅ Streamlit secrets available")
            secrets_keys = list(st.secrets.keys())
            st.sidebar.write(f"Secrets keys: {secrets_keys}")
        else:
            st.sidebar.write("❌ Streamlit secrets not available")
    except Exception as e:
        st.sidebar.write(f"❌ Secrets error: {e}")
    
    for var in required_vars:
        try:
            if hasattr(st, 'secrets') and var in st.secrets:
                env_vars[var] = st.secrets[var]
                st.sidebar.write(f"✅ {var} loaded from secrets")
                continue
            else:
                st.sidebar.write(f"❌ {var} not in secrets")
        except Exception as e:
            st.sidebar.write(f"❌ {var} secrets error: {e}")
            
        env_value = os.getenv(var)
        if env_value:
            env_vars[var] = env_value
            st.sidebar.write(f"✅ {var} loaded from environment")
        else:
            env_vars[var] = None
            st.sidebar.write(f"❌ {var} not in environment")
                
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

# Get environment variables
env_vars = get_environment_variables()

IMAGEBB_API_KEY = env_vars["IMAGEBB_API_KEY"]
DISCOGS_USER_TOKEN = env_vars["DISCOGS_USER_TOKEN"]
EBAY_CLIENT_ID = env_vars["EBAY_CLIENT_ID"]
EBAY_CLIENT_SECRET = env_vars["EBAY_CLIENT_SECRET"]

# Debug: Show what we got
st.sidebar.write("### Final Values")
st.sidebar.write(f"DISCOGS_USER_TOKEN: {'✅ Set' if DISCOGS_USER_TOKEN else '❌ None'}")
st.sidebar.write(f"IMAGEBB_API_KEY: {'✅ Set' if IMAGEBB_API_KEY else '❌ None'}")
st.sidebar.write(f"EBAY_CLIENT_ID: {'✅ Set' if EBAY_CLIENT_ID else '❌ None'}")
st.sidebar.write(f"EBAY_CLIENT_SECRET: {'✅ Set' if EBAY_CLIENT_SECRET else '❌ None'}")

# Initialize session state defaults
if "db_manager" not in st.session_state:
    persisted_path = get_persisted_database_path()
    if persisted_path:
        st.session_state.db_manager = DatabaseManager(persisted_path)
    else:
        st.session_state.db_manager = DatabaseManager()

if "search_results" not in st.session_state:
    st.session_state.search_results = {}

if "current_search" not in st.session_state:
    st.session_state.current_search = ""

if "last_added" not in st.session_state:
    st.session_state.last_added = None

if "records_updated" not in st.session_state:
    st.session_state.records_updated = 0

class BatchProcessorUI:
    def __init__(self, discogs_handler):
        self.discogs_handler = discogs_handler
        self.search_tab = SearchTab(discogs_handler)
        self.records_tab = RecordsTab()
        self.statistics_tab = StatisticsTab()
        self.genre_mappings_tab = GenreMappingsTab()
        self.print_tab = PrintTab()
        
    def render(self):
        if not self.discogs_handler or not getattr(self.discogs_handler, "user_token", None):
            self._render_error_message()
            return

        # Database file browser
        self._render_database_selector()

        # Create tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📥 Search & Add", "📚 Records", "📊 Statistics", "🏷️ Genre Mappings", "🖨️ Print"])
        
        with tab1:
            self.search_tab.render()
        
        with tab2:
            self.records_tab.render()
        
        with tab3:
            self.statistics_tab.render()
        
        with tab4:
            self.genre_mappings_tab.render()
        
        with tab5:
            self.print_tab.render()

    def _render_database_selector(self):
        """Allow user to select a different database file"""
        st.sidebar.subheader("Database")
        
        # Current database info
        current_db = st.session_state.db_manager.db_path
        st.sidebar.write(f"**Current DB:** {os.path.basename(current_db)}")
        
        # File uploader for new database
        uploaded_db = st.sidebar.file_uploader(
            "Load different database", 
            type=['db'],
            help="Select a SQLite database file to load",
            key="db_uploader"
        )
        
        if uploaded_db is not None:
            try:
                # Save uploaded file temporarily
                temp_db_path = f"temp_{uploaded_db.name}"
                with open(temp_db_path, "wb") as f:
                    f.write(uploaded_db.getvalue())
                
                # Reinitialize database manager with new path
                st.session_state.db_manager = DatabaseManager(temp_db_path)
                
                # Persist the new database path
                if persist_database_path(temp_db_path):
                    st.sidebar.success(f"Loaded and persisted database: {uploaded_db.name}")
                else:
                    st.sidebar.warning(f"Loaded database but failed to persist path: {uploaded_db.name}")
                
                # Force rerun to refresh the entire app with new database
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error loading database: {e}")
        
        # Also allow creating new empty database
        if st.sidebar.button("Create New Database", use_container_width=True):
            new_db_name = st.sidebar.text_input("New database name:", value="new_database.db")
            if st.sidebar.button("Create Database", key="create_db"):
                try:
                    new_db_path = new_db_name if new_db_name.endswith('.db') else f"{new_db_name}.db"
                    st.session_state.db_manager = DatabaseManager(new_db_path)
                    
                    # Persist the new database path
                    if persist_database_path(new_db_path):
                        st.sidebar.success(f"Created and persisted new database: {new_db_path}")
                    else:
                        st.sidebar.warning(f"Created database but failed to persist path: {new_db_path}")
                    
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Error creating database: {e}")

    def _render_error_message(self):
        st.error("🚫 Discogs integration not available")
        
        missing_vars = []
        for var_name, var_value in env_vars.items():
            if not var_value:
                missing_vars.append(var_name)
        
        if missing_vars:
            st.error(f"Missing environment variables: {', '.join(missing_vars)}")
        
        st.info("""
        **To fix this issue:**
        
        **For Streamlit Cloud:**
        1. Go to your app dashboard at https://share.streamlit.io/
        2. Click on your app
        3. Click the "⋮" (three dots) menu and select "Settings"
        4. Go to the "Secrets" tab
        5. Add your secrets in this format:
        ```
        DISCOGS_USER_TOKEN = "your_discogs_token_here"
        IMAGEBB_API_KEY = "your_imgbb_api_key_here"
        EBAY_CLIENT_ID = "your_ebay_client_id_here" 
        EBAY_CLIENT_SECRET = "your_ebay_client_secret_here"
        ```
        6. Click "Save" and redeploy your app
        
        **For local development:**
        Make sure you have a `.env` file in your project root with the same variables.
        """)


# Initialize Discogs handler
discogs_handler = None
if DISCOGS_USER_TOKEN:
    try:
        discogs_handler = DiscogsHandler(DISCOGS_USER_TOKEN)
        st.sidebar.success("✅ Discogs handler initialized!")
    except Exception as e:
        st.error(f"❌ Failed to initialize Discogs: {e}")
        discogs_handler = None
else:
    st.error("❌ DISCOGS_USER_TOKEN not found")

# Initialize the UI
batch_ui = BatchProcessorUI(discogs_handler) if discogs_handler else None

# Render the interface
if batch_ui:
    batch_ui.render()
else:
    st.error("Discogs integration not available. Please check your Discogs API token.")