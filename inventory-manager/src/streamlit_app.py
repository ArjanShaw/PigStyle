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
import time  # ADDED

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
from handlers.contract_handler import ContractHandler  # ADDED

# --- Configuration ---
IMAGE_FOLDER = Path("images")
IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
PAYLOADS_FOLDER = Path("payloads")
PAYLOADS_FOLDER.mkdir(parents=True, exist_ok=True)

class ConfigCache:
    """Centralized config cache management"""
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ConfigCache()
        return cls._instance
    
    def __init__(self):
        self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
        self._cache = None
        self._last_load_time = 0
        self._cache_ttl = 300  # 5 minutes cache TTL
    
    def load_all_configs(self, force_reload=False):
        """Load all config values in a single API call"""
        current_time = time.time()
        
        # Check if cache is still valid
        if (not force_reload and 
            self._cache is not None and 
            (current_time - self._last_load_time) < self._cache_ttl):
            return self._cache
        
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/config", timeout=5)
            duration = time.time() - start_time
            
            print(f"ConfigCache: Loaded all configs in {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    configs = data.get('configs', {})
                    
                    # Flatten config structure
                    flat_configs = {}
                    for key, config_info in configs.items():
                        if isinstance(config_info, dict):
                            flat_configs[key] = config_info.get('value', '')
                        else:
                            flat_configs[key] = config_info
                    
                    self._cache = flat_configs
                    self._last_load_time = current_time
                    
                    # Store in session state for backward compatibility
                    if 'config_cache' not in st.session_state:
                        st.session_state.config_cache = {}
                    st.session_state.config_cache = flat_configs.copy()
                    
                    return self._cache
            else:
                print(f"ConfigCache: Failed to load configs, status {response.status_code}")
                return {}
        except Exception as e:
            print(f"ConfigCache: Error loading configs: {e}")
            return {}
    
    def get(self, key, default=None):
        """Get a config value from cache"""
        if self._cache is None:
            self.load_all_configs()
        
        return self._cache.get(key, default) if self._cache else default
    
    def clear(self):
        """Clear the cache"""
        self._cache = None
        self._last_load_time = 0
        if 'config_cache' in st.session_state:
            del st.session_state.config_cache


class GenreCache:
    """Centralized genre cache management"""
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = GenreCache()
        return cls._instance
    
    def __init__(self):
        self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
        self._cache = None
        self._last_load_time = 0
        self._cache_ttl = 300  # 5 minutes cache TTL
    
    def load_all_genres(self, force_reload=False):
        """Load all genres in a single API call"""
        current_time = time.time()
        
        # Check if cache is still valid
        if (not force_reload and 
            self._cache is not None and 
            (current_time - self._last_load_time) < self._cache_ttl):
            return self._cache
        
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/genres", timeout=5)
            duration = time.time() - start_time
            
            print(f"GenreCache: Loaded all genres in {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    genres = data.get('genres', [])
                    
                    # Create a list of genre names for easy access
                    genre_list = []
                    for genre in genres:
                        if isinstance(genre, dict):
                            genre_list.append(genre.get('genre_name', ''))
                        else:
                            genre_list.append(genre)
                    
                    self._cache = {
                        'genres_list': genre_list,
                        'genres_data': genres,
                        'raw_response': data
                    }
                    self._last_load_time = current_time
                    
                    # Store in session state for backward compatibility
                    if 'genre_cache' not in st.session_state:
                        st.session_state.genre_cache = {}
                    st.session_state.genre_cache = self._cache.copy()
                    
                    return self._cache
            else:
                print(f"GenreCache: Failed to load genres, status {response.status_code}")
                return {'genres_list': [], 'genres_data': [], 'raw_response': {}}
        except Exception as e:
            print(f"GenreCache: Error loading genres: {e}")
            return {'genres_list': [], 'genres_data': [], 'raw_response': {}}
    
    def get_genres_list(self, force_reload=False):
        """Get list of genre names from cache"""
        cache_data = self.load_all_genres(force_reload)
        return cache_data.get('genres_list', []) if cache_data else []
    
    def get_genres_data(self, force_reload=False):
        """Get full genres data from cache"""
        cache_data = self.load_all_genres(force_reload)
        return cache_data.get('genres_data', []) if cache_data else []
    
    def clear(self):
        """Clear the cache"""
        self._cache = None
        self._last_load_time = 0
        if 'genre_cache' in st.session_state:
            del st.session_state.genre_cache
    
    def refresh(self):
        """Force refresh the cache"""
        self.clear()
        return self.load_all_genres(force_reload=True)


def main():
    """Main application entry point"""
    # Initialize session state for authentication
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'session_token' not in st.session_state:
        st.session_state.session_token = None
    
    # Initialize API timing storage
    if 'api_timings' not in st.session_state:
        st.session_state.api_timings = []
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        render_login_page()
    else:
        render_main_app()

def render_login_page():
    """Render login page"""
    st.set_page_config(page_title="PigStyle Login", page_icon="🎵", layout="centered")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎵 PigStyle Records")
        st.subheader("Inventory Manager")
        
        # Demo Mode button - SIMPLE AND DIRECT
        if st.button("👀 Demo Mode", key="demo_button", width='stretch', type="primary"):
            st.session_state.authenticated = True
            st.session_state.user = {
                'username': 'demo_user',
                'role': 'consignor',
                'full_name': 'Demo User',
                'id': 999,
                'email': 'demo@pigstyle.com'
            }
            st.session_state.session_token = None
            
            # Initialize demo last added record with real artist/title
            st.session_state.demo_last_added = {
                'artist': 'Radiohead',
                'title': 'OK Computer',
                'store_price': 27.99
            }
            
            # Initialize demo credit balance (calculated from sold records)
            # Pink Floyd sold at $39.99 - 20% commission = $31.99
            st.session_state.demo_credit_balance = 31.99
            
            st.rerun()
        
        st.markdown("---")
        st.write("**Regular Login**")
        
        with st.form("login_form"):
            username = st.text_input("Username or Email", placeholder="Enter your username or email")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            login_button = st.form_submit_button("🚀 Login", width='stretch')
        
        if login_button:
            if username and password:
                auth_manager = AuthManager()
                session_manager = SessionManager(auth_manager)
                success, message = session_manager.login(username, password, False)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please enter both username and password")
        
        st.markdown("---")
        st.caption("💡 Contact administrator for account creation")

def render_main_app():
    """Render the main application after authentication"""
    user = st.session_state.user
    
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
    
    # Initialize config cache singleton
    config_cache = ConfigCache.get_instance()
    
    # Pre-load all configs on app startup
    config_cache.load_all_configs()
    
    # Initialize genre cache singleton
    genre_cache = GenreCache.get_instance()
    
    # Pre-load all genres on app startup
    genre_cache.load_all_genres()
    
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
                self.config_cache = config_cache
            
            def get_config_value(self, key, default=None):
                # Use the centralized config cache
                return self.config_cache.get(key, default)
            
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
        # Create API client for pricing validator
        class SimpleAPIClient3:
            def __init__(self):
                self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
                self.config_cache = config_cache
                self.genre_cache = genre_cache
            
            def get_config_value(self, key, default=None):
                # Use the centralized config cache
                return self.config_cache.get(key, default)
                
            def search_records(self, query):
                try:
                    response = requests.get(f"{self.base_url}/search?q={query}", timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('status') == 'success':
                            return data.get('records', [])
                    return []
                except:
                    return []
        
        st.session_state.pricing_validator = PricingValidator(
            SimpleAPIClient3(),  # Now uses config cache
            None,  # Will be set if discogs_handler exists
            None   # Will be set if ebay_handler exists
        )

    # ADDED: Initialize contract handler
    if "contract_handler" not in st.session_state:
        # Create a simple API client for contract handler
        class SimpleAPIClientForContract:
            def __init__(self):
                self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
                self.config_cache = config_cache
            
            def get_config_value(self, key, default=None):
                # Use the centralized config cache
                return self.config_cache.get(key, default)
        
        st.session_state.contract_handler = ContractHandler(SimpleAPIClientForContract())

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
    
    # Create a proper API client for InventoryTab that uses both caches
    class InventoryTabAPIClient:
        def __init__(self, config_cache, genre_cache):
            self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
            self.config_cache = config_cache
            self.genre_cache = genre_cache
        
        # FIX: Add string representation methods to fix URL errors
        def __str__(self):
            return self.base_url
        
        def __repr__(self):
            return f"InventoryTabAPIClient(base_url='{self.base_url}')"
        
        def get_config_value(self, key, default=None):
            """Get config value from cache"""
            if self.config_cache:
                return self.config_cache.get(key, default)
            return default
        
        def get_all_genres(self):
            """Get all genres from cache"""
            if self.genre_cache:
                return self.genre_cache.get_genres_list()
            return []
        
        def add_genre(self, genre_name):
            """Add new genre via API"""
            try:
                response = requests.post(
                    f"{self.base_url}/genres",
                    json={'genre_name': genre_name}
                )
                if response.status_code == 200:
                    data = response.json()
                    # Refresh the genre cache after adding new genre
                    if self.genre_cache:
                        self.genre_cache.refresh()
                    return True, data.get('genre_id')
                return False, None
            except Exception as e:
                st.error(f"API Error adding genre: {e}")
                return False, None
        
        def get_discogs_genre_mapping(self, discogs_genre):
            """Get Discogs genre mapping via API"""
            try:
                response = requests.get(f"{self.base_url}/discogs-genre-mappings/{discogs_genre}")
                if response.status_code == 200:
                    return response.json()
                return {'mapping': None, 'status': 'error'}
            except Exception as e:
                st.error(f"API Error getting genre mapping: {e}")
                return {'mapping': None, 'status': 'error'}
        
        # Add other API methods that InventoryTab needs...
        def get_user(self, user_id):
            """Get user by ID via API"""
            try:
                response = requests.get(f"{self.base_url}/users/{user_id}")
                if response.status_code == 200:
                    return response.json()
                return None
            except Exception as e:
                st.error(f"API Error getting user: {e}")
                return None
        
        def search_records(self, query):
            """Search records via API"""
            try:
                response = requests.get(f"{self.base_url}/search?q={query}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        return data.get('records', [])
                return []
            except Exception as e:
                st.error(f"API Error searching records: {e}")
                return []
    
    # Pass the proper API client to InventoryTab
    inventory_api_client = InventoryTabAPIClient(config_cache, genre_cache)
    
    # Initialize InventoryTab with the proper API client structure
    inventory_tab = InventoryTab(
        discogs_handler, 
        ebay_handler, 
        youtube_handler, 
        config_cache, 
        genre_cache,
        inventory_api_client  # Pass the proper API client
    )
    
    statistics_tab = StatisticsTab()
    ebay_tab = EBayTab(ebay_handler)
    consignment_tab = ConsignmentTab()
    price_tag_tab = PriceTagTab(genre_cache)
    admin_config_tab = AdminConfigTab()
    votes_tab = VotesTab()
    checkout_tab = CheckoutTab()

    render_header(user)
    
    for timing in st.session_state.get("api_timings", [])[-10:]:
        print(f"{timing['endpoint']}: {timing['duration']:.2f}s")
    
    render_tabs_based_on_permissions(user, inventory_tab, price_tag_tab, 
                                   ebay_tab, statistics_tab, consignment_tab, 
                                   admin_config_tab, votes_tab, checkout_tab)

def render_header(user):
    """Render application header with user information"""
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
    
    with col1:
        st.write(f"**🎵 PigStyle Records**")
    
    with col2:
        role_display = "👑 Admin" if user['role'] == 'admin' else "🤝 Consignor"
        if user['username'] == 'demo_user':
            role_display = "👀 Demo User"
        st.write(f"**{user['full_name'] or user['username']}**")
        st.caption(role_display)
    
    with col3:
        # Store credit removed from header - now shown in consignment tab for consignors
        pass
    
    with col4:
        if st.button("🔐 PW", help="Change Password"):
            st.session_state.show_change_password = True
    
    with col5:
        if st.button("🚪", help="Logout"):
            # Clear authentication session state
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.session_token = None
            st.rerun()
    
    if st.session_state.get('show_change_password', False):
        render_change_password_form()

def render_change_password_form():
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
                    # For demo user, just show success
                    if st.session_state.user['username'] == 'demo_user':
                        st.success("Demo: Password change simulated")
                        st.session_state.show_change_password = False
                        st.rerun()
                    else:
                        auth_manager = AuthManager()
                        session_manager = SessionManager(auth_manager)
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
    is_demo = user['username'] == 'demo_user'
    
    tab_configs = []
    
    # Show inventory to all users with view permission
    if PermissionManager.has_permission(user_role, 'inventory', 'view') or is_demo:
        tab_configs.append(("📦 Inventory", inventory_tab.render))
    
    # Show consignment to users with consignment view permission
    if PermissionManager.has_permission(user_role, 'consignment', 'view') or is_demo:
        tab_configs.append(("🤝 Consignment", consignment_tab.render))
    
    # Show price tags to users with add permission - ONLY FOR ADMIN
    if user_role == 'admin':  # Only admin can print price tags
        tab_configs.append(("🏷️ Print Price Tags", price_tag_tab.render))
    
    # Show eBay to users with eBay view permission (admin only)
    if PermissionManager.has_permission(user_role, 'ebay', 'view'):
        tab_configs.append(("🛒 eBay", ebay_tab.render))
    
    # Show statistics to users with reports view permission (admin only)
    if PermissionManager.has_permission(user_role, 'reports', 'view'):
        tab_configs.append(("📊 Statistics", statistics_tab.render))
    
    # Show votes to users with reports view permission (admin only)
    if PermissionManager.has_permission(user_role, 'reports', 'view'):
        tab_configs.append(("🗳️ Votes", votes_tab.render))
    
    # Show checkout ONLY to admin users - NOT FOR DEMO OR CONSIGNOR
    if user_role == 'admin':
        tab_configs.append(("💰 Checkout", checkout_tab.render))
    
    # Show admin config to admin users
    if user_role == 'admin':
        tab_configs.append(("⚙️ Admin Config", admin_config_tab.render))
    
    if tab_configs:
        tab_names = [config[0] for config in tab_configs]
        tabs = st.tabs(tab_names)
        
        for i, (tab_name, render_function) in enumerate(tab_configs):
            with tabs[i]:
                render_function()

if __name__ == "__main__":
    main()