import streamlit as st
import os
import sys
from pathlib import Path

# Add the current directory to the path to find local modules
sys.path.insert(0, os.path.dirname(__file__))

from auth.auth_manager import AuthManager
from auth.session_manager import SessionManager
from auth.permissions import PermissionManager

# Import existing modules
from database_manager import DatabaseManager  # Changed from database_manager_api
from handlers.discogs_handler import DiscogsHandler
from tabs.inventory_tab import InventoryTab
from tabs.statistics_tab import StatisticsTab
from tabs.ebay_tab import EBayTab
from tabs.store_pricing_tab import StorePricingTab
from tabs.tools_sync_tab import ToolsSyncTab
from tabs.consignment_tab import ConsignmentTab
from tabs.price_tag_tab import PriceTagTab
from tabs.admin_config_tab import AdminConfigTab
from handlers.ebay_handler import EbayHandler
from handlers.api_key_handler import APIKeyHandler
from config import AppConfig
from handlers.youtube_handler import YouTubeHandler

# --- Configuration ---
IMAGE_FOLDER = Path("images")
IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
PAYLOADS_FOLDER = Path("payloads")
PAYLOADS_FOLDER.mkdir(parents=True, exist_ok=True)

def render_login_page(auth_manager, session_manager):
    """Render login page"""
    st.set_page_config(page_title="PigStyle Login", page_icon="🎵", layout="centered")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎵 PigStyle Records")
        st.subheader("Inventory Manager")
        
        with st.form("login_form"):
            username = st.text_input("Username or Email", placeholder="Enter your username or email")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            remember_me = st.checkbox("Remember me", value=True)
            
            col1, col2 = st.columns(2)
            with col1:
                login_button = st.form_submit_button("🚀 Login", width='stretch')
            with col2:
                demo_button = st.form_submit_button("👀 Demo Mode", width='stretch')
        
        if login_button:
            if username and password:
                success, message = session_manager.login(username, password, remember_me)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please enter both username and password")
        
        if demo_button:
            # Demo mode with viewer permissions
            st.session_state.authenticated = True
            st.session_state.user = {
                'username': 'demo_user',
                'role': 'consignor',
                'full_name': 'Demo User'
            }
            st.session_state.session_token = None
            st.success("Entering demo mode with read-only access")
            st.rerun()
        
        st.markdown("---")
        st.caption("💡 Contact administrator for account creation")

def render_main_app():
    """Render the main application after authentication"""
    # Initialize session manager and check existing session
    auth_manager = AuthManager()
    session_manager = SessionManager(auth_manager)
    
    if not session_manager.check_existing_session():
        render_login_page(auth_manager, session_manager)
        return
    
    # User is authenticated, render main app
    user = session_manager.get_current_user()
    
    # Set page config for main app
    st.set_page_config(
        page_title="PigStyle Inventory Manager",
        page_icon="🎵",
        layout="wide"
    )
    
    # Initialize configuration
    config = AppConfig()
    
    # Initialize API Key Handler
    api_key_handler = APIKeyHandler()
    
    # Get environment variables
    env_vars = api_key_handler.get_environment_variables()

    IMAGEBB_API_KEY = env_vars["IMAGEBB_API_KEY"]
    DISCOGS_USER_TOKEN = env_vars["DISCOGS_USER_TOKEN"]
    EBAY_CLIENT_ID = env_vars["EBAY_CLIENT_ID"]
    EBAY_CLIENT_SECRET = env_vars["EBAY_CLIENT_SECRET"]
    YOUTUBE_API_KEY = env_vars.get("YOUTUBE_API_KEY")

    # Initialize session state defaults with API-based database manager
    if "db_manager" not in st.session_state:
        api_base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
        st.session_state.db_manager = DatabaseManager(api_base_url)
        st.session_state.config = config

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
    inventory_tab = InventoryTab(discogs_handler, ebay_handler, youtube_handler)
    statistics_tab = StatisticsTab()
    ebay_tab = EBayTab(ebay_handler)
    store_pricing_tab = StorePricingTab()
    tools_sync_tab = ToolsSyncTab()  # Removed GitHubSyncHandler parameter
    consignment_tab = ConsignmentTab()
    price_tag_tab = PriceTagTab(st.session_state.db_manager)
    admin_config_tab = AdminConfigTab()

    # Render header with user info
    render_header(user, session_manager)
    
    # Create tabs based on user permissions
    render_tabs_based_on_permissions(user, inventory_tab, price_tag_tab, store_pricing_tab, 
                                   ebay_tab, statistics_tab, consignment_tab, tools_sync_tab, admin_config_tab)

def render_header(user, session_manager):
    """Render application header with user information"""
    # Compact header in single row
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        # Removed "PigStyle Inventory Manager" header as requested
        pass
    
    with col2:
        role_display = "👑 Admin" if user['role'] == 'admin' else "🤝 Consignor"
        st.write(f"**{user['full_name'] or user['username']}**")
        st.caption(role_display)
    
    with col3:
        if st.button("🔐 PW", help="Change Password", width='stretch'):
            st.session_state.show_change_password = True
    
    with col4:
        if st.button("🚪", help="Logout", width='stretch'):
            session_manager.logout()
    
    # Show change password form if triggered
    if st.session_state.get('show_change_password', False):
        render_change_password_form(session_manager)

def render_change_password_form(session_manager):
    """Render password change form"""
    with st.expander("🔐 Change Password", expanded=True):
        with st.form("change_password_form"):
            st.write("### Change Your Password")
            
            current_password = st.text_input("Current Password", type="password", 
                                           placeholder="Enter your current password")
            new_password = st.text_input("New Password", type="password", 
                                       placeholder="Enter new password")
            confirm_password = st.text_input("Confirm New Password", type="password", 
                                           placeholder="Confirm new password")
            
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("💾 Update Password", width='stretch')
            with col2:
                cancel = st.form_submit_button("❌ Cancel", width='stretch')
            
            if cancel:
                st.session_state.show_change_password = False
                st.rerun()
            
            if submit:
                if not all([current_password, new_password, confirm_password]):
                    st.error("Please fill all fields")
                elif new_password != confirm_password:
                    st.error("New passwords do not match")
                else:
                    success, message = session_manager.change_password(current_password, new_password)
                    if success:
                        st.success(message)
                        st.session_state.show_change_password = False
                        st.rerun()
                    else:
                        st.error(message)

def render_tabs_based_on_permissions(user, inventory_tab, price_tag_tab, store_pricing_tab, 
                                   ebay_tab, statistics_tab, consignment_tab, tools_sync_tab, admin_config_tab):
    """Render tabs based on user permissions"""
    user_role = user['role']
    
    tab_configs = []
    
    # Always show these tabs for authenticated users with basic view permissions
    if PermissionManager.has_permission(user_role, 'inventory', 'view'):
        tab_configs.append(("📦 Inventory", inventory_tab.render))
    
    if PermissionManager.has_permission(user_role, 'inventory', 'add'):
        tab_configs.append(("🏷️ Print Price Tags", price_tag_tab.render))
    
    # Store Pricing tab removed for all users as requested
    # if PermissionManager.has_permission(user_role, 'pricing', 'view'):
    #     tab_configs.append(("🏪 Store Pricing", store_pricing_tab.render))
    
    # eBay tab only for admin
    if user_role == 'admin' and PermissionManager.has_permission(user_role, 'ebay', 'view'):
        tab_configs.append(("🛒 eBay", ebay_tab.render))
    
    # Statistics tab only for admin
    if user_role == 'admin' and PermissionManager.has_permission(user_role, 'reports', 'view'):
        tab_configs.append(("📊 Statistics", statistics_tab.render))
    
    if PermissionManager.has_permission(user_role, 'consignment', 'view'):
        tab_configs.append(("🤝 Consignment", consignment_tab.render))
    
    if PermissionManager.has_permission(user_role, 'system', 'view'):
        tab_configs.append(("🛠️ Tools & Sync", tools_sync_tab.render))
    
    # Admin-only tabs
    if user_role == 'admin':
        tab_configs.append(("⚙️ Admin Config", admin_config_tab.render))
    
    # Create tabs
    if tab_configs:
        tab_names = [config[0] for config in tab_configs]
        tabs = st.tabs(tab_names)
        
        for i, (tab_name, render_function) in enumerate(tab_configs):
            with tabs[i]:
                try:
                    render_function()
                except Exception as e:
                    st.error(f"Error loading {tab_name}: {str(e)}")

def main():
    """Main application entry point"""
    render_main_app()

if __name__ == "__main__":
    main()