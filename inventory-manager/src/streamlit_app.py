import streamlit as st
import os
import sys  # ADD THIS IMPORT
from pathlib import Path
import pandas as pd
from datetime import datetime
import requests
import json
import numpy as np
from typing import Optional, Dict, Any, List
import time

# Add the current directory to the path to find local modules
sys.path.insert(0, os.path.dirname(__file__))

from auth.auth_manager import AuthManager
from auth.session_manager import SessionManager
from auth.permissions import PermissionManager

# Import existing modules
from handlers.discogs_handler import DiscogsHandler
from tabs.inventory_tab import InventoryTab
# REMOVED: from tabs.statistics_tab import StatisticsTab
# FIXED: Import EBayTab from ebay_handler
from tabs.ebay_tab import EBayTab
from tabs.consignment_tab import ConsignmentTab
from tabs.price_tag_tab import PriceTagTab
from tabs.admin_config_tab import AdminConfigTab
from tabs.votes_tab import VotesTab
from tabs.checkout_tab import CheckoutTab
# REMOVED: from handlers.ebay_handler import EbayHandler
from handlers.env_pars_handler import EnvParsHandler  # NEW: Centralized environment variable handler
from config import AppConfig
from handlers.youtube_handler import YouTubeHandler
from handlers.email_service import EmailService
from handlers.commission_calculator import CommissionCalculator
from handlers.pricing_validator import PricingValidator
from handlers.contract_handler import ContractHandler
from handlers.price_advise_handler import PriceAdviseHandler  # NEW IMPORT
from handlers.config_handler import ConfigHandler  # NEW IMPORT

# --- Configuration ---
IMAGE_FOLDER = Path("images")
IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
PAYLOADS_FOLDER = Path("payloads")
PAYLOADS_FOLDER.mkdir(parents=True, exist_ok=True)

class ConfigCache:
    """Centralized config cache management - DEPRECATED: Use ConfigHandler instead"""
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
        self._cache_ttl = 300
    
    def load_all_configs(self, force_reload=False):
        """Load all config values in a single API call - DEPRECATED"""
        # Use ConfigHandler instead
        config_handler = ConfigHandler()
        configs = config_handler.get_all()
        
        # Maintain backward compatibility with session state
        st.session_state.config_cache = configs.copy()
        
        return configs
    
    def get(self, key, default=None):
        """Get a config value from cache - DEPRECATED"""
        # Use ConfigHandler instead
        config_handler = ConfigHandler()
        return config_handler.get(key, default)
    
    def clear(self):
        """Clear the cache - DEPRECATED"""
        config_handler = ConfigHandler()
        config_handler.clear_cache()


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
        self._cache_ttl = 300
        
        # Initialize genre mapping cache from session state if available
        self._genre_mapping_cache = st.session_state.get('genre_mapping_cache', {})
    
    def load_all_genres(self, force_reload=False):
        """Load all genres in a single API call"""
        current_time = time.time()
        
        # Check cache conditions
        cache_valid = (
            not force_reload and 
            self._cache is not None and 
            (current_time - self._last_load_time) < self._cache_ttl
        )
        
        if cache_valid:
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
                    st.session_state.genre_cache = self._cache.copy()
                    
                    return self._cache
            else:
                print(f"GenreCache: Failed to load genres, status {response.status_code}")
                return {'genres_list': [], 'genres_data': [], 'raw_response': {}}
        except Exception as e:
            print(f"GenreCache: Error loading genres: {e}")
            return {'genres_list': [], 'genres_data': [], 'raw_response': {}}
    
    def get_discogs_genre_mapping(self, discogs_genre):
        """Get Discogs genre mapping from cache or API - FIXED to handle slashes"""
        # FIX: Clean the discogs_genre to handle special characters
        if discogs_genre and '/' in discogs_genre:
            # Try multiple formats
            clean_genres = [
                discogs_genre,  # Original
                discogs_genre.replace('/', ' '),  # Space instead of slash
                discogs_genre.split('/')[0],  # First part before slash
            ]
            
            # Check cache for any variant
            for clean_genre in clean_genres:
                if clean_genre in self._genre_mapping_cache:
                    cached_result = self._genre_mapping_cache[clean_genre]
                    if cached_result.get('status') == 'success' and cached_result.get('mapping'):
                        print(f"GenreCache: Using cached mapping for variant '{clean_genre}' of '{discogs_genre}'")
                        return cached_result
        else:
            # Original logic for non-slash genres
            if discogs_genre in self._genre_mapping_cache:
                cached_result = self._genre_mapping_cache[discogs_genre]
                if cached_result.get('status') == 'success' and cached_result.get('mapping'):
                    print(f"GenreCache: Using cached mapping for '{discogs_genre}'")
                    return cached_result
        
        # If not in cache, make API call with cleaned genre
        api_genre = discogs_genre
        if '/' in discogs_genre:
            api_genre = discogs_genre.replace('/', '%2F')  # URL encode slash
        
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/discogs-genre-mappings/{api_genre}")
            duration = time.time() - start_time
            
            print(f"GenreCache: Get Discogs mapping '{discogs_genre}' took {duration:.2f}s")
            
            if response.status_code == 200:
                mapping_data = response.json()
                # Cache the result for all variants
                self._genre_mapping_cache[discogs_genre] = mapping_data
                
                # Also cache variants for future use
                if '/' in discogs_genre:
                    clean_variant = discogs_genre.replace('/', ' ')
                    self._genre_mapping_cache[clean_variant] = mapping_data
                    first_part = discogs_genre.split('/')[0]
                    self._genre_mapping_cache[first_part] = mapping_data
                
                # Persist in session state
                st.session_state.genre_mapping_cache = self._genre_mapping_cache
                return mapping_data
            else:
                # Try alternative API endpoint with cleaned genre
                if '/' in discogs_genre:
                    clean_genre = discogs_genre.replace('/', ' ')
                    alt_response = requests.get(f"{self.base_url}/discogs-genre-mappings/{clean_genre}")
                    if alt_response.status_code == 200:
                        mapping_data = alt_response.json()
                        self._genre_mapping_cache[discogs_genre] = mapping_data
                        st.session_state.genre_mapping_cache = self._genre_mapping_cache
                        return mapping_data
                
                # Cache the error response
                error_response = {'mapping': None, 'status': 'error'}
                self._genre_mapping_cache[discogs_genre] = error_response
                st.session_state.genre_mapping_cache = self._genre_mapping_cache
                return error_response
        except Exception as e:
            print(f"GenreCache: Error getting genre mapping: {e}")
            error_response = {'mapping': None, 'status': 'error'}
            self._genre_mapping_cache[discogs_genre] = error_response
            st.session_state.genre_mapping_cache = self._genre_mapping_cache
            return error_response
    
    def clear(self):
        """Clear the cache"""
        self._cache = None
        self._genre_mapping_cache = {}
        self._last_load_time = 0
        # Clear from session state
        if 'genre_cache' in st.session_state:
            del st.session_state.genre_cache
        if 'genre_mapping_cache' in st.session_state:
            del st.session_state.genre_mapping_cache
    
    def refresh(self):
        """Force refresh the cache"""
        self.clear()
        return self.load_all_genres(force_reload=True)


class RecordsCache:
    """Centralized records cache management with automatic refresh on updates"""
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = RecordsCache()
        return cls._instance
    
    def __init__(self):
        self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
        self._cache = None
        self._last_load_time = 0
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._last_update_time = 0  # Track when records were last updated
    
    def get_all_records(self, force_reload=False):
        """Get all records from cache or API"""
        current_time = time.time()
        
        # Check if we need to reload - FIXED: Better logic to prevent unnecessary reloads
        needs_reload = (
            force_reload or 
            self._cache is None or
            (current_time - self._last_load_time) >= self._cache_ttl or
            st.session_state.get('records_updated', 0) > self._last_update_time or
            not hasattr(st.session_state, 'records_cache') or
            st.session_state.get('records_cache') is None
        )
        
        if not needs_reload:
            return self._cache
        
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/records", timeout=10)
            duration = time.time() - start_time
            
            print(f"RecordsCache: Loaded all records in {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])
                
                self._cache = records
                self._last_load_time = current_time
                self._last_update_time = st.session_state.get('records_updated', 0)
                
                # Store in session state for backward compatibility
                st.session_state.records_cache = records.copy()
                
                return records
            else:
                print(f"RecordsCache: Failed to load records, status {response.status_code}")
                return []
        except Exception as e:
            print(f"RecordsCache: Error loading records: {e}")
            return []
    
    def get_recent_records(self, limit=10, force_reload=False):
        """Get recent records from cache"""
        records = self.get_all_records(force_reload)
        
        if not records:
            return []
        
        # Sort by ID descending to get most recent
        sorted_records = sorted(records, key=lambda x: x.get('id', 0), reverse=True)
        return sorted_records[:limit]
    
    def get_records_by_user(self, user_id, force_reload=False):
        """Get records for specific user from cache"""
        records = self.get_all_records(force_reload)
        
        if not records:
            return []
        
        user_records = [r for r in records if r.get('consignor_id') == user_id]
        return user_records
    
    def search_records(self, search_term, user_id=None, force_reload=False):
        """Search records in cache"""
        records = self.get_all_records(force_reload)
        
        if not records:
            return []
        
        search_lower = search_term.lower()
        results = []
        
        for record in records:
            # Skip if user_id is specified and record doesn't belong to user
            if user_id and record.get('consignor_id') != user_id:
                continue
            
            artist = str(record.get('artist', '')).lower()
            title = str(record.get('title', '')).lower()
            catalog = str(record.get('catalog_number', '')).lower()
            barcode = str(record.get('barcode', '')).lower()
            
            if (search_lower in artist or 
                search_lower in title or 
                search_lower in catalog or 
                search_lower in barcode):
                results.append(record)
        
        return results
    
    def get_record_by_id(self, record_id, force_reload=False):
        """Get single record by ID from cache"""
        records = self.get_all_records(force_reload)
        
        if not records:
            return None
        
        for record in records:
            if record.get('id') == record_id:
                return record
        
        return None
    
    def get_records_count(self):
        """Get count of records from cache (efficient)"""
        records = self.get_all_records()
        return len(records) if records else 0
    
    def clear(self):
        """Clear the cache"""
        self._cache = None
        self._last_load_time = 0
        self._last_update_time = 0
        if 'records_cache' in st.session_state:
            del st.session_state.records_cache
    
    def refresh(self):
        """Force refresh the cache"""
        self.clear()
        return self.get_all_records(force_reload=True)
    
    def mark_updated(self):
        """Mark that records have been updated (call after add/edit/delete)"""
        if 'records_updated' not in st.session_state:
            st.session_state.records_updated = 0
        st.session_state.records_updated += 1


def main():
    """Main application entry point"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'session_token' not in st.session_state:
        st.session_state.session_token = None
    
    if 'api_timings' not in st.session_state:
        st.session_state.api_timings = []
    
    # Initialize records update counter
    if 'records_updated' not in st.session_state:
        st.session_state.records_updated = 0
    
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
            
            st.session_state.demo_last_added = {
                'artist': 'Radiohead',
                'title': 'OK Computer',
                'store_price': 27.99
            }
            
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
    
    # Initialize caches
    config_handler = ConfigHandler()  # NEW: Use ConfigHandler
    genre_cache = GenreCache.get_instance()
    records_cache = RecordsCache.get_instance()
    
    # Load initial data using ConfigHandler
    config_handler.get_all()  # This will load all configs into cache
    genre_cache.load_all_genres()
    records_cache.get_all_records()
    
    # NEW: Use EnvParsHandler for all environment variables
    env_handler = EnvParsHandler()
    env_vars = env_handler.get_environment_variables()
    
    IMAGEBB_API_KEY = env_vars["IMAGEBB_API_KEY"]
    DISCOGS_USER_TOKEN = env_vars["DISCOGS_USER_TOKEN"]
    EBAY_CLIENT_ID = env_vars["EBAY_CLIENT_ID"]
    EBAY_CLIENT_SECRET = env_vars["EBAY_CLIENT_SECRET"]
    YOUTUBE_API_KEY = env_vars.get("YOUTUBE_API_KEY")
    
    if "email_service" not in st.session_state:
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
        class SimpleAPIClient2:
            def __init__(self):
                self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
                self.config_handler = config_handler  # Use ConfigHandler
            
            def get_config_value(self, key, default=None):
                return self.config_handler.get(key, default)
            
            def get_all_records(self):
                # Use records cache instead of API call
                return records_cache.get_all_records()
            
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
        class SimpleAPIClient3:
            def __init__(self):
                self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
                self.config_handler = config_handler  # Use ConfigHandler
                self.genre_cache = genre_cache
            
            def get_config_value(self, key, default=None):
                return self.config_handler.get(key, default)
                
            def search_records(self, query):
                # Use records cache instead of API call
                return records_cache.search_records(query)
        
        st.session_state.pricing_validator = PricingValidator(
            SimpleAPIClient3(),
            None,
            None
        )

    if "contract_handler" not in st.session_state:
        class SimpleAPIClientForContract:
            def __init__(self):
                self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
                self.config_handler = config_handler  # Use ConfigHandler
            
            def get_config_value(self, key, default=None):
                return self.config_handler.get(key, default)
        
        st.session_state.contract_handler = ContractHandler(SimpleAPIClientForContract())

    if "search_results" not in st.session_state:
        st.session_state.search_results = {}

    if "current_search" not in st.session_state:
        st.session_state.current_search = ""

    if "last_added" not in st.session_state:
        st.session_state.last_added = None

    if "selected_records" not in st.session_state:
        st.session_state.selected_records = []

    if "checkout_records" not in st.session_state:
        st.session_state.checkout_records = []

    discogs_handler = None
    if DISCOGS_USER_TOKEN:
        discogs_handler = DiscogsHandler(DISCOGS_USER_TOKEN)
    
    ebay_handler = None
    if EBAY_CLIENT_ID and EBAY_CLIENT_SECRET:
        ebay_handler = EBayTab(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET)  # Now EBayTab contains handler functionality
    
    youtube_handler = None
    if YOUTUBE_API_KEY:
        youtube_handler = YouTubeHandler(YOUTUBE_API_KEY)
    
    # Initialize PriceAdviseHandler with env variables loaded from EnvParsHandler
    price_advise_handler = PriceAdviseHandler(discogs_handler, ebay_handler)
    
    # Create API client for InventoryTab that uses caches
    class InventoryTabAPIClient:
        def __init__(self, config_handler, genre_cache, records_cache):
            self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
            self.config_handler = config_handler  # Use ConfigHandler
            self.genre_cache = genre_cache
            self.records_cache = records_cache
        
        def __str__(self):
            return self.base_url
        
        def __repr__(self):
            return f"InventoryTabAPIClient(base_url='{self.base_url}')"
        
        def get_config_value(self, key, default=None):
            return self.config_handler.get(key, default)
        
        def get_all_genres(self):
            if self.genre_cache:
                return self.genre_cache.get_genres_list()
            return []
        
        def add_genre(self, genre_name):
            try:
                response = requests.post(
                    f"{self.base_url}/genres",
                    json={'genre_name': genre_name}
                )
                if response.status_code == 200:
                    data = response.json()
                    if self.genre_cache:
                        self.genre_cache.refresh()
                    return True, data.get('genre_id')
                return False, None
            except Exception as e:
                st.error(f"API Error adding genre: {e}")
                return False, None
        
        def get_discogs_genre_mapping(self, discogs_genre):
            if self.genre_cache:
                return self.genre_cache.get_discogs_genre_mapping(discogs_genre)
            return {'mapping': None, 'status': 'error'}
        
        def get_user(self, user_id):
            try:
                response = requests.get(f"{self.base_url}/users/{user_id}")
                if response.status_code == 200:
                    return response.json()
                return None
            except Exception as e:
                st.error(f"API Error getting user: {e}")
                return None
        
        def search_records(self, query):
            return self.records_cache.search_records(query)
        
        # Add record operation methods that will update cache
        def add_record(self, record_data):
            try:
                response = requests.post(
                    f"{self.base_url}/records",
                    json=record_data,
                    timeout=10
                )
                if response.status_code == 200:
                    # Mark records as updated to trigger cache refresh
                    self.records_cache.mark_updated()
                    return True, response.json().get('record_id')
                return False, None
            except Exception as e:
                st.error(f"API Error adding record: {e}")
                return False
        
        def update_record(self, record_id, updates):
            try:
                response = requests.put(
                    f"{self.base_url}/records/{record_id}",
                    json=updates
                )
                if response.status_code == 200:
                    # Mark records as updated to trigger cache refresh
                    self.records_cache.mark_updated()
                    return True
                return False
            except Exception as e:
                st.error(f"API Error updating record: {e}")
                return False
        
        def delete_record(self, record_id):
            try:
                response = requests.delete(f"{self.base_url}/records/{record_id}")
                if response.status_code == 200:
                    # Mark records as updated to trigger cache refresh
                    self.records_cache.mark_updated()
                    return True
                return False
            except Exception as e:
                st.error(f"API Error deleting record: {e}")
                return False
        
        # Methods that use cache
        def get_all_records(self):
            return self.records_cache.get_all_records()
        
        def get_recent_records(self, limit=10):
            return self.records_cache.get_recent_records(limit)
        
        def get_records_by_user(self, user_id):
            return self.records_cache.get_records_by_user(user_id)
        
        def get_record_by_id(self, record_id):
            return self.records_cache.get_record_by_id(record_id)
        
        def get_records_count(self):
            """Get records count from cache (efficient)"""
            return self.records_cache.get_records_count()
    
    # Pass the proper API client to InventoryTab
    inventory_api_client = InventoryTabAPIClient(config_handler, genre_cache, records_cache)
    
    # Pass price_advise_handler to InventoryTab
    inventory_tab = InventoryTab(
        discogs_handler, 
        ebay_handler,  # This is now an EBayTab instance with handler functionality
        youtube_handler, 
        config_handler,  # Use ConfigHandler instead of config_cache
        genre_cache,
        price_advise_handler,  # NEW: Pass price_advise_handler
        inventory_api_client
    )
    
    # REMOVED: statistics_tab initialization since StatisticsTab no longer exists
    ebay_tab = ebay_handler  # ebay_handler is already an EBayTab instance
    consignment_tab = ConsignmentTab()
    price_tag_tab = PriceTagTab(genre_cache)
    admin_config_tab = AdminConfigTab()
    votes_tab = VotesTab()
    checkout_tab = CheckoutTab()

    render_header(user)
    
    # Print recent API timings for debugging
    if st.session_state.get("api_timings"):
        print("\n=== Recent API Timings ===")
        for timing in st.session_state.get("api_timings", [])[-5:]:
            print(f"{timing['endpoint']}: {timing['duration']:.2f}s")
        print("=========================\n")
        
    render_tabs_based_on_permissions(user, inventory_tab, price_tag_tab, 
                                   ebay_tab, consignment_tab, 
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
        pass
    
    with col4:
        if st.button("🔐 PW", help="Change Password"):
            st.session_state.show_change_password = True
    
    with col5:
        if st.button("🚪", help="Logout"):
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
                                   ebay_tab, consignment_tab,  
                                   admin_config_tab, votes_tab, checkout_tab):
    """Render tabs based on user permissions"""
    user_role = user['role']
    is_demo = user['username'] == 'demo_user'
    
    tab_configs = []
    
    if PermissionManager.has_permission(user_role, 'inventory', 'view') or is_demo:
        tab_configs.append(("📦 Inventory", inventory_tab.render))
    
    if PermissionManager.has_permission(user_role, 'consignment', 'view') or is_demo:
        tab_configs.append(("🤝 Consignment", consignment_tab.render))
    
    if user_role == 'admin':
        tab_configs.append(("🏷️ Print Price Tags", price_tag_tab.render))
    
    if PermissionManager.has_permission(user_role, 'ebay', 'view'):
        tab_configs.append(("🛒 eBay", ebay_tab.render))
    
    # REMOVED: Statistics tab
    
    if PermissionManager.has_permission(user_role, 'reports', 'view'):
        tab_configs.append(("🗳️ Votes", votes_tab.render))
    
    if user_role == 'admin':
        tab_configs.append(("💰 Checkout", checkout_tab.render))
    
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