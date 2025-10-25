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

# --- Password Protection ---
def check_password():
    """Simple password protection for the app"""
    # Return True if already authenticated
    if st.session_state.get("password_correct", False):
        return True
    
    # Show password input
    st.title("🔒 PigStyle Inventory Manager")
    st.write("Please enter the password to access the inventory system.")
    
    password = st.text_input("Password", type="password", key="password_input")
    
    if password:
        # Check against secret (for Streamlit Cloud) or environment variable (local)
        correct_password = (
            st.secrets.get("APP_PASSWORD") if hasattr(st, 'secrets') 
            else os.getenv("APP_PASSWORD")
        )
        
        if password == correct_password:
            st.session_state.password_correct = True
            st.rerun()
        else:
            st.error("❌ Incorrect password")
            st.stop()
    else:
        st.stop()
    
    return False

# Check password before loading the rest of the app
if not check_password():
    st.stop()

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

def get_available_databases():
    """Get all .db files in current directory and src directory"""
    db_files = []
    
    # Check current directory
    current_dir_dbs = glob.glob("*.db")
    db_files.extend(current_dir_dbs)
    
    # Check src directory
    src_dir_dbs = glob.glob("src/*.db")
    db_files.extend([f"src/{os.path.basename(db)}" for db in src_dir_dbs])
    
    # Also check parent directory
    parent_dir_dbs = glob.glob("../*.db")
    db_files.extend([f"../{os.path.basename(db)}" for db in parent_dir_dbs])
    
    return db_files

def initialize_database_manager(db_path=None):
    """Initialize database manager with the given path or persisted path"""
    if db_path:
        return DatabaseManager(db_path)
    
    persisted_path = get_persisted_database_path()
    if persisted_path:
        return DatabaseManager(persisted_path)
    
    # Default database
    return DatabaseManager()

class DatabaseSwitcher:
    def __init__(self):
        self.available_dbs = get_available_databases()
    
    def render(self):
        """Render database switcher in sidebar"""
        st.sidebar.header("📁 Database Manager")
        
        # Show current database with full path
        current_db = st.session_state.db_manager.db_path
        current_db_name = os.path.basename(current_db)
        
        st.sidebar.write(f"**Current:** `{current_db}`")
        
        # Database selector with browse icon
        col1, col2 = st.sidebar.columns([3, 1])
        
        with col1:
            selected_db = st.selectbox(
                "📂 Select Database",
                self.available_dbs,
                index=self.available_dbs.index(current_db) if current_db in self.available_dbs else 0,
                format_func=lambda x: os.path.basename(x)
            )
        
        with col2:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("🔍", help="Browse for database files"):
                st.session_state.show_file_browser = True
        
        # File browser modal
        if st.session_state.get('show_file_browser', False):
            with st.sidebar.expander("📁 File Browser", expanded=True):
                st.write("Navigate to select a database file:")
                
                # Current directory info
                current_dir = os.getcwd()
                st.write(f"**Current directory:** `{current_dir}`")
                
                # Show .db files in current directory
                db_files = glob.glob("*.db")
                if db_files:
                    st.write("**Database files in current directory:**")
                    for db_file in db_files:
                        if st.button(f"📄 {db_file}", key=f"select_{db_file}"):
                            st.session_state.db_manager = DatabaseManager(db_file)
                            persist_database_path(db_file)
                            st.session_state.show_file_browser = False
                            st.rerun()
                else:
                    st.info("No .db files found in current directory")
                
                # Manual path input
                st.write("**Or enter full path:**")
                manual_path = st.text_input("Database path:", placeholder="/path/to/database.db")
                if st.button("Load Database", key="load_manual"):
                    if manual_path and os.path.exists(manual_path) and manual_path.endswith('.db'):
                        st.session_state.db_manager = DatabaseManager(manual_path)
                        persist_database_path(manual_path)
                        st.session_state.show_file_browser = False
                        st.rerun()
                    else:
                        st.error("Invalid database path")
                
                if st.button("Close Browser"):
                    st.session_state.show_file_browser = False
        
        # Switch database if selection changed
        if selected_db != current_db:
            try:
                st.session_state.db_manager = DatabaseManager(selected_db)
                if persist_database_path(selected_db):
                    st.sidebar.success(f"Switched to: {os.path.basename(selected_db)}")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error loading database: {e}")
        
        # Database upload section
        st.sidebar.subheader("📤 Upload Database")
        uploaded_file = st.sidebar.file_uploader(
            "Upload .db file", 
            type=['db'],
            key="db_uploader",
            label_visibility="collapsed"
        )
        
        if uploaded_file is not None:
            try:
                # Save uploaded file
                upload_path = uploaded_file.name
                with open(upload_path, 'wb') as f:
                    f.write(uploaded_file.getbuffer())
                
                st.session_state.db_manager = DatabaseManager(upload_path)
                if persist_database_path(upload_path):
                    st.sidebar.success(f"📥 Uploaded and loaded: {upload_path}")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error uploading database: {e}")
        
        # Create new database
        st.sidebar.subheader("🆕 Create New Database")
        new_db_name = st.sidebar.text_input("New database name:", value="new_inventory.db")
        if st.sidebar.button("Create Database", use_container_width=True):
            try:
                if not new_db_name.endswith('.db'):
                    new_db_name += '.db'
                
                st.session_state.db_manager = DatabaseManager(new_db_name)
                if persist_database_path(new_db_name):
                    st.sidebar.success(f"✅ Created: {new_db_name}")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error creating database: {e}")

class BatchProcessorUI:
    def __init__(self, discogs_handler):
        self.discogs_handler = discogs_handler
        self.search_tab = SearchTab(discogs_handler)
        self.records_tab = RecordsTab()
        self.statistics_tab = StatisticsTab()
        self.genre_mappings_tab = GenreMappingsTab()
        self.print_tab = PrintTab()
        self.db_switcher = DatabaseSwitcher()
        
    def render(self):
        if not self.discogs_handler or not getattr(self.discogs_handler, "user_token", None):
            self._render_error_message()
            return

        # Database switcher
        self.db_switcher.render()

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
        APP_PASSWORD = "your_app_password_here"
        ```
        6. Click "Save" and redeploy your app
        
        **For local development:**
        Make sure you have a `.env` file in your project root with the same variables.
        """)


def main():
    """Main function to run the Streamlit app"""
    # Set page config - this must be the first Streamlit command
    st.set_page_config(layout="wide")
    
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
        st.session_state.db_manager = initialize_database_manager()

    if "search_results" not in st.session_state:
        st.session_state.search_results = {}

    if "current_search" not in st.session_state:
        st.session_state.current_search = ""

    if "last_added" not in st.session_state:
        st.session_state.last_added = None

    if "records_updated" not in st.session_state:
        st.session_state.records_updated = 0

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


if __name__ == "__main__":
    main()