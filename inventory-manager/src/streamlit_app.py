import streamlit as st
import os
import sys
from pathlib import Path

# Add auth module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from auth.auth_manager import AuthManager
from auth.session_manager import SessionManager
from auth.permissions import PermissionManager

# Import existing modules
from database_manager import DatabaseManager
from handlers.discogs_handler import DiscogsHandler
from tabs.inventory_tab import InventoryTab
from tabs.statistics_tab import StatisticsTab
from tabs.ebay_tab import EBayTab
from tabs.store_pricing_tab import StorePricingTab
from tabs.tools_sync_tab import ToolsSyncTab
from tabs.consignment_tab import ConsignmentTab
from tabs.price_tag_tab import PriceTagTab
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
                login_button = st.form_submit_button("🚀 Login", use_container_width=True)
            with col2:
                demo_button = st.form_submit_button("👀 Demo Mode", use_container_width=True)
        
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
                'role': 'viewer',
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
    price_tag_tab = PriceTagTab(st.session_state.db_manager)

    # Render header with user info
    render_header(user, session_manager)
    
    # Create tabs based on user permissions
    render_tabs_based_on_permissions(user, inventory_tab, price_tag_tab, store_pricing_tab, 
                                   ebay_tab, statistics_tab, consignment_tab, tools_sync_tab)

def render_header(user, session_manager):
    """Render application header with user information"""
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    
    with col1:
        st.title("🎵 PigStyle Inventory Manager")
    
    with col2:
        role_display = user['role'].title()
        st.write(f"**Welcome, {user['full_name'] or user['username']}**")
        st.caption(f"Role: {role_display}")
    
    with col3:
        if st.button("🔐 Change Password", use_container_width=True):
            st.session_state.show_change_password = True
    
    with col4:
        if st.button("🚪 Logout", use_container_width=True):
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
                submit = st.form_submit_button("💾 Update Password", use_container_width=True)
            with col2:
                cancel = st.form_submit_button("❌ Cancel", use_container_width=True)
            
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
                                   ebay_tab, statistics_tab, consignment_tab, tools_sync_tab):
    """Render tabs based on user permissions"""
    user_role = user['role']
    accessible_modules = PermissionManager.get_accessible_modules(user_role)
    
    tab_configs = []
    
    # Define tab configurations with required permissions
    if 'inventory' in accessible_modules:
        tab_configs.append(("📦 Inventory", inventory_tab.render, ['view']))
    
    if PermissionManager.has_permission(user_role, 'inventory', 'add'):
        tab_configs.append(("🏷️ Print Price Tags", price_tag_tab.render, ['view']))
    
    if 'pricing' in accessible_modules:
        tab_configs.append(("🏪 Store Pricing", store_pricing_tab.render, ['view']))
    
    if 'ebay' in accessible_modules:
        tab_configs.append(("🛒 eBay", ebay_tab.render, ['view']))
    
    if 'reports' in accessible_modules:
        tab_configs.append(("📊 Statistics", statistics_tab.render, ['view']))
    
    if 'consignment' in accessible_modules:
        tab_configs.append(("🤝 Consignment", consignment_tab.render, ['view']))
    
    if PermissionManager.has_permission(user_role, 'system', 'view'):
        tab_configs.append(("🛠️ Tools & Sync", tools_sync_tab.render, ['view']))
    
    # Admin-only tabs
    if user_role == 'admin':
        tab_configs.append(("👥 User Management", render_user_management, ['view']))
    
    # Create tabs
    if tab_configs:
        tab_names = [config[0] for config in tab_configs]
        tabs = st.tabs(tab_names)
        
        for i, (tab_name, render_function, required_perms) in enumerate(tab_configs):
            with tabs[i]:
                # Check permissions before rendering
                module = tab_name.split(' ')[1].lower() if ' ' in tab_name else tab_name.lower()
                has_access = all(PermissionManager.has_permission(user_role, module, perm) for perm in required_perms)
                
                if has_access:
                    render_function()
                else:
                    st.warning(f"You don't have permission to access {tab_name}")

def render_user_management():
    """Render user management interface (admin only)"""
    st.header("👥 User Management")
    
    auth_manager = AuthManager()
    session_manager = SessionManager(auth_manager)
    current_user = session_manager.get_current_user()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Users", "Create User", "Reset Passwords", "Audit Log"])
    
    with tab1:
        st.subheader("User Accounts")
        users = auth_manager.get_all_users()
        
        if users:
            for user in users:
                user_id, username, email, role, full_name, is_active, created_at, last_login = user
                
                with st.expander(f"{username} ({role}) - {full_name or 'No name'}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Email:** {email}")
                        st.write(f"**Created:** {created_at.split(' ')[0]}")
                        if last_login:
                            st.write(f"**Last Login:** {last_login.split(' ')[0]}")
                    
                    with col2:
                        new_role = st.selectbox(
                            "Role",
                            options=['admin', 'manager', 'clerk', 'viewer'],
                            index=['admin', 'manager', 'clerk', 'viewer'].index(role),
                            key=f"role_{user_id}"
                        )
                        
                        if new_role != role:
                            if st.button("Update Role", key=f"update_{user_id}"):
                                success, message = auth_manager.update_user_role(user_id, new_role, current_user['id'])
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
        
        else:
            st.info("No users found")
    
    with tab2:
        st.subheader("Create New User")
        
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                username = st.text_input("Username*", placeholder="Enter username")
                email = st.text_input("Email*", placeholder="user@example.com")
                full_name = st.text_input("Full Name", placeholder="Optional full name")
            
            with col2:
                password = st.text_input("Password*", type="password", placeholder="Enter password")
                confirm_password = st.text_input("Confirm Password*", type="password", placeholder="Confirm password")
                role = st.selectbox("Role*", options=['viewer', 'clerk', 'manager', 'admin'])
            
            if st.form_submit_button("Create User", use_container_width=True):
                if not all([username, email, password, confirm_password]):
                    st.error("Please fill all required fields (*)")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    success, message = auth_manager.create_user(username, email, password, role, full_name)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
    
    with tab3:
        st.subheader("Reset User Passwords")
        users = auth_manager.get_all_users()
        
        if users:
            for user in users:
                user_id, username, email, role, full_name, is_active, created_at, last_login = user
                
                with st.expander(f"Reset password for {username}"):
                    new_password = st.text_input("New Password", type="password", 
                                               placeholder="Enter new password",
                                               key=f"new_pass_{user_id}")
                    confirm_password = st.text_input("Confirm Password", type="password",
                                                   placeholder="Confirm new password",
                                                   key=f"confirm_pass_{user_id}")
                    
                    if st.button("Reset Password", key=f"reset_{user_id}"):
                        if not new_password or not confirm_password:
                            st.error("Please enter both password fields")
                        elif new_password != confirm_password:
                            st.error("Passwords do not match")
                        else:
                            success, message = auth_manager.reset_password(current_user['id'], user_id, new_password)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
        else:
            st.info("No users found")
    
    with tab4:
        st.subheader("Audit Log")
        logs = auth_manager.get_audit_log(limit=50)
        
        if logs:
            for log in logs:
                timestamp, username, action, description, ip_address = log
                st.write(f"**{timestamp}** - {username or 'System'} - {action}")
                st.caption(f"{description} | IP: {ip_address or 'Unknown'}")
        else:
            st.info("No audit logs found")

def main():
    """Main application entry point"""
    render_main_app()

if __name__ == "__main__":
    main()