import streamlit as st
import os
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
import requests
import json
import numpy as np
from typing import Optional, Dict, Any, List

# Add the current directory to the path to find local modules
sys.path.insert(0, os.path.dirname(__file__))

from auth.auth_manager import AuthManager
from auth.session_manager import SessionManager
from auth.permissions import PermissionManager

# Import existing modules
from handlers.discogs_handler import DiscogsHandler
from tabs.inventory_tab import InventoryTab
from tabs.statistics_tab import StatisticsTab
from tabs.ebay_tab import EBayTab
from tabs.consignment_tab import ConsignmentTab
from tabs.price_tag_tab import PriceTagTab
from tabs.admin_config_tab import AdminConfigTab
from tabs.votes_tab import VotesTab
from tabs.checkout_tab import CheckoutTab
from handlers.ebay_handler import EbayHandler
from handlers.api_key_handler import APIKeyHandler
from config import AppConfig
from handlers.youtube_handler import YouTubeHandler
from handlers.email_service import EmailService
from handlers.commission_calculator import CommissionCalculator
from handlers.pricing_validator import PricingValidator

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
                login_button = st.form_submit_button("🚀 Login")
            with col2:
                demo_button = st.form_submit_button("👀 Demo Mode")
        
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
            st.session_state.authenticated = True
            st.session_state.user = {
                'username': 'demo_user',
                'role': 'consignor',
                'full_name': 'Demo User',
                'id': 999,
                'email': 'demo@pigstyle.com'
            }
            st.session_state.session_token = None
            st.success("Entering demo mode with read-only access")
            st.rerun()
        
        st.markdown("---")
        st.caption("💡 Contact administrator for account creation")

def render_main_app():
    """Render the main application after authentication"""
    auth_manager = AuthManager()
    session_manager = SessionManager(auth_manager)
    
    if not session_manager.check_existing_session():
        render_login_page(auth_manager, session_manager)
        return
    
    user = session_manager.get_current_user()
    
    st.set_page_config(
        page_title="PigStyle Inventory Manager",
        page_icon="🎵",
        layout="wide"
    )
    
    # Initialize config - this will throw error if config file is missing or incomplete
    try:
        config = AppConfig()
    except Exception as e:
        st.error(f"Configuration error: {e}")
        st.info("Please ensure app_config.json exists with all required values")
        st.stop()
    
    api_key_handler = APIKeyHandler()
    
    env_vars = api_key_handler.get_environment_variables()

    IMAGEBB_API_KEY = env_vars["IMAGEBB_API_KEY"]
    DISCOGS_USER_TOKEN = env_vars["DISCOGS_USER_TOKEN"]
    EBAY_CLIENT_ID = env_vars["EBAY_CLIENT_ID"]
    EBAY_CLIENT_SECRET = env_vars["EBAY_CLIENT_SECRET"]
    YOUTUBE_API_KEY = env_vars.get("YOUTUBE_API_KEY")

    if "config" not in st.session_state:
        st.session_state.config = config
    
    # Initialize new services
    if "email_service" not in st.session_state:
        # Create a simple API client for email service
        class SimpleAPIClient:
            def __init__(self):
                self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
            
            def get_user_by_id(self, user_id):
                try:
                    response = requests.get(f"{self.base_url}/users/{user_id}")
                    if response.status_code == 200:
                        return response.json()
                    return None
                except:
                    return None
                    
            def update_record(self, record_id, updates):
                try:
                    response = requests.put(f"{self.base_url}/records/{record_id}", json=updates)
                    return response.status_code == 200
                except:
                    return False
        
        st.session_state.email_service = EmailService(SimpleAPIClient())
    
    if "commission_calculator" not in st.session_state:
        # Create a simple API client for commission calculator
        class SimpleAPIClient2:
            def __init__(self):
                self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
            
            def get_config_value(self, key, default=None):
                try:
                    response = requests.get(f"{self.base_url}/config/{key}")
                    if response.status_code == 200:
                        data = response.json()
                        return data.get('config_value', default)
                    return default
                except:
                    return default
            
            def get_all_records(self):
                try:
                    response = requests.get(f"{self.base_url}/records?limit=1000")
                    if response.status_code == 200:
                        data = response.json()
                        return pd.DataFrame(data.get('records', []))
                    return pd.DataFrame()
                except:
                    return pd.DataFrame()
            
            def get_user_by_id(self, user_id):
                try:
                    response = requests.get(f"{self.base_url}/users/{user_id}")
                    if response.status_code == 200:
                        return response.json()
                    return None
                except:
                    return None
        
        st.session_state.commission_calculator = CommissionCalculator(SimpleAPIClient2())
    
    if "pricing_validator" not in st.session_state:
        st.session_state.pricing_validator = PricingValidator(
            None,  # Will be set if needed
            None,  # Will be set if discogs_handler exists
            None   # Will be set if ebay_handler exists
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

    if "checkout_records" not in st.session_state:
        st.session_state.checkout_records = []

    discogs_handler = None
    if DISCOGS_USER_TOKEN:
        discogs_handler = DiscogsHandler(DISCOGS_USER_TOKEN)
    
    ebay_handler = None
    if EBAY_CLIENT_ID and EBAY_CLIENT_SECRET:
        ebay_handler = EbayHandler(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET)
    
    youtube_handler = None
    if YOUTUBE_API_KEY:
        youtube_handler = YouTubeHandler(YOUTUBE_API_KEY)
    else:
        st.warning("YouTube API key not found. YouTube integration will be disabled.")
 
    inventory_tab = InventoryTab(discogs_handler, ebay_handler, youtube_handler)
    statistics_tab = StatisticsTab()
    ebay_tab = EBayTab(ebay_handler)
    consignment_tab = ConsignmentTab()
    price_tag_tab = PriceTagTab()
    admin_config_tab = AdminConfigTab()
    votes_tab = VotesTab()
    checkout_tab = CheckoutTab()

    render_header(user, session_manager)
    
    render_tabs_based_on_permissions(user, inventory_tab, price_tag_tab, 
                                   ebay_tab, statistics_tab, consignment_tab, 
                                   admin_config_tab, votes_tab, checkout_tab)

def render_header(user, session_manager):
    """Render application header with user information"""
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    
    with col1:
        st.write(f"**🎵 PigStyle Records**")
    
    with col2:
        role_display = "👑 Admin" if user['role'] == 'admin' else "🤝 Consignor"
        st.write(f"**{user['full_name'] or user['username']}**")
        st.caption(role_display)
    
    with col3:
        # Show store credit balance for consignors
        if user['role'] == 'consignor':
            try:
                base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
                response = requests.get(f"{base_url}/users/{user['id']}")
                if response.status_code == 200:
                    user_info = response.json()
                    store_credit = user_info.get('store_credit_balance', 0)
                    if store_credit > 0:
                        st.metric("Store Credit", f"${store_credit:.2f}")
            except:
                pass
    
    with col4:
        if st.button("🔐 PW", help="Change Password"):
            st.session_state.show_change_password = True
    
    with col5:
        if st.button("🚪", help="Logout"):
            session_manager.logout()
    
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
                submit = st.form_submit_button("💾 Update Password")
            with col2:
                cancel = st.form_submit_button("❌ Cancel")
            
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

def render_tabs_based_on_permissions(user, inventory_tab, price_tag_tab, 
                                   ebay_tab, statistics_tab, consignment_tab,  
                                   admin_config_tab, votes_tab, checkout_tab):
    """Render tabs based on user permissions"""
    user_role = user['role']
    
    tab_configs = []
    
    # Show checkout to users with checkout view permission - FIRST TAB
    if PermissionManager.has_permission(user_role, 'checkout', 'view'):
        tab_configs.append(("💰 Checkout", checkout_tab.render))
    # Fallback: if permission system doesn't have checkout defined, show for admin
    elif user_role == 'admin':
        tab_configs.append(("💰 Checkout", checkout_tab.render))
    
    # Show inventory to all users with view permission
    if PermissionManager.has_permission(user_role, 'inventory', 'view'):
        tab_configs.append(("📦 Inventory", inventory_tab.render))
    
    # Show price tags to users with add permission
    if PermissionManager.has_permission(user_role, 'inventory', 'add'):
        tab_configs.append(("🏷️ Print Price Tags", price_tag_tab.render))
    
    # Show eBay to users with eBay view permission
    if PermissionManager.has_permission(user_role, 'ebay', 'view'):
        tab_configs.append(("🛒 eBay", ebay_tab.render))
    
    # Show statistics to users with reports view permission
    if PermissionManager.has_permission(user_role, 'reports', 'view'):
        tab_configs.append(("📊 Statistics", statistics_tab.render))
    
    # Show votes to users with reports view permission
    if PermissionManager.has_permission(user_role, 'reports', 'view'):
        tab_configs.append(("🗳️ Votes", votes_tab.render))
    
    # Show consignment to users with consignment view permission
    if PermissionManager.has_permission(user_role, 'consignment', 'view'):
        tab_configs.append(("🤝 Consignment", consignment_tab.render))
    
    # Show admin config to admin users
    if user_role == 'admin':
        tab_configs.append(("⚙️ Admin Config", admin_config_tab.render))
    
    if tab_configs:
        tab_names = [config[0] for config in tab_configs]
        tabs = st.tabs(tab_names)
        
        for i, (tab_name, render_function) in enumerate(tab_configs):
            with tabs[i]:
                render_function()

def main():
    """Main application entry point"""
    render_main_app()

if __name__ == "__main__":
    main()