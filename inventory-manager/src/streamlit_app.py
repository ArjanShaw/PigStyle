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
from tabs.store_pricing_tab import StorePricingTab
from tabs.consignment_tab import ConsignmentTab
from tabs.price_tag_tab import PriceTagTab
from tabs.admin_config_tab import AdminConfigTab
from tabs.votes_tab import VotesTab
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

class DatabaseManager:
    """Unified API-based database manager that replaces all direct SQLite access"""
    
    def __init__(self, api_base_url: str = None):
        if api_base_url is None:
            api_base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
        
        self.api_base_url = api_base_url
        self.session = requests.Session()
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        url = f"{self.api_base_url}{endpoint}"
        
        response = self.session.request(method, url, **kwargs)
        
        if 200 <= response.status_code < 300:
            return response.json()
        else:
            st.error(f"API Error {response.status_code}: {response.text}")
            return None
    
    def _make_json_serializable(self, data):
        if isinstance(data, dict):
            return {k: self._make_json_serializable(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._make_json_serializable(v) for v in data]
        elif isinstance(data, np.integer):
            return int(data)
        elif isinstance(data, np.floating):
            return float(data)
        elif isinstance(data, np.ndarray):
            return data.tolist()
        elif pd.isna(data):
            return None
        elif isinstance(data, (int, float, str, bool)) or data is None:
            return data
        else:
            return str(data)

    def get_all_records(self) -> pd.DataFrame:
        result = self._make_request('GET', '/records?limit=1000')
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        return pd.DataFrame()
    
    def get_recent_records(self, limit: int = 100) -> pd.DataFrame:
        result = self._make_request('GET', f'/records?limit={limit}&order_by=created_at&order=desc')
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        
        return pd.DataFrame()
    
    def get_record_by_id(self, record_id: int) -> Optional[pd.Series]:
        result = self._make_request('GET', f'/records/{record_id}')
        if result:
            return pd.Series(result)
        return None
    
    def save_record(self, result_data: Dict) -> int:
        serializable_data = self._make_json_serializable(result_data)
        
        result = self._make_request('POST', '/records', json=serializable_data)
        
        if result and 'record_id' in result:
            return result['record_id']
        
        return None
    
    def update_record(self, record_id: int, updates: Dict) -> bool:
        serializable_updates = self._make_json_serializable(updates)
        
        result = self._make_request('PUT', f'/records/{record_id}', json=serializable_updates)
        
        success = result is not None and result.get('status') == 'success'
        return success
    
    def delete_record(self, record_id: int) -> bool:
        result = self._make_request('DELETE', f'/records/{record_id}')
        
        success = result is not None and result.get('status') == 'success'
        return success
    
    def search_records(self, search_term: str, consignor_id: str = None) -> pd.DataFrame:
        """Search records with optional consignor filtering"""
        endpoint = f'/search?q={search_term}'
        if consignor_id:
            endpoint += f'&consignor_id={consignor_id}'
        
        result = self._make_request('GET', endpoint)
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        return pd.DataFrame()
    
    def get_record_by_barcode(self, barcode: str) -> Optional[pd.Series]:
        result = self._make_request('GET', f'/records/barcode/{barcode}')
        if result:
            return pd.Series(result)
        return None

    def record_vote(self, record_id: int, voter_hash: str, vote_type: str) -> bool:
        result = self._make_request('POST', f'/vote/{record_id}/{voter_hash}/{vote_type}')
        
        success = result is not None and result.get('status') == 'success'
        return success
    
    def get_vote_counts(self, record_id: int = None):
        if record_id:
            result = self._make_request('GET', f'/votes/{record_id}')
            if result:
                return {record_id: {
                    'upvotes': result.get('upvotes', 0),
                    'downvotes': result.get('downvotes', 0)
                }}
        return {}
    
    def get_user_vote(self, record_id: int, voter_hash: str) -> Optional[str]:
        result = self._make_request('GET', f'/user-vote/{record_id}/{voter_hash}')
        if result:
            return result.get('vote_type')
        return None

    def get_all_genres(self) -> pd.DataFrame:
        result = self._make_request('GET', '/genres')
        if result and 'genres' in result:
            return pd.DataFrame(result['genres'])
        return pd.DataFrame(columns=['id', 'genre_name'])
    
    def add_genre(self, genre_name: str):
        result = self._make_request('POST', '/genres', json={'genre_name': genre_name})
        
        if result and 'genre_id' in result:
            genre_id = result['genre_id']
            return True, genre_id
        
        return False, None
    
    def assign_genre_to_artist(self, artist_name: str, genre_id: int) -> bool:
        result = self._make_request('POST', '/genre-assignments', json={
            'artist_name': artist_name,
            'genre_id': genre_id
        })
        
        success = result is not None and result.get('status') == 'success'
        return success
    
    def remove_genre_from_artist_by_name(self, artist_name: str) -> bool:
        result = self._make_request('DELETE', f'/genre-assignments/artist/{artist_name}')
        
        success = result is not None and result.get('status') == 'success'
        return success

    def get_all_users(self) -> pd.DataFrame:
        result = self._make_request('GET', '/users')
        if result and 'users' in result:
            return pd.DataFrame(result['users'])
        return pd.DataFrame()
    
    def get_user_by_id(self, user_id: int) -> Optional[pd.Series]:
        result = self._make_request('GET', f'/users/{user_id}')
        if result:
            return pd.Series(result)
        return None

    def get_config_value(self, config_key: str, default: Any = None) -> Any:
        result = self._make_request('GET', f'/config/{config_key}')
        if result and 'config_value' in result:
            return result['config_value']
        
        return default
    
    def set_config_value(self, config_key: str, config_value: str) -> bool:
        result = self._make_request('POST', '/config', json={
            'config_key': config_key,
            'config_value': config_value
        })
        
        success = result is not None and result.get('status') == 'success'
        return success

    def get_all_config(self):
        result = self._make_request('GET', '/config')
        if result and 'configs' in result:
            return result['configs']
        return []

    def reset_user_password(self, user_id: int, new_password: str) -> bool:
        result = self._make_request('POST', f'/users/{user_id}/reset-password', json={
            'new_password': new_password
        })
        
        success = result is not None and result.get('status') == 'success'
        return success

    def change_user_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        result = self._make_request('POST', f'/users/{user_id}/change-password', json={
            'current_password': current_password,
            'new_password': new_password
        })
        
        success = result is not None and result.get('status') == 'success'
        return success

    def get_database_stats(self) -> Dict:
        result = self._make_request('GET', '/stats')
        if result:
            return result
        
        return {
            'records_count': 0,
            'users_count': 0,
            'latest_record': 'N/A',
            'db_path': 'API-based'
        }
    
    def get_user_database_stats(self, user_id: int) -> Dict:
        result = self._make_request('GET', f'/stats/user/{user_id}')
        if result:
            return result
        
        return {
            'records_count': 0,
            'db_path': 'API-based'
        }

    def get_consignment_records_ready_for_payment(self, user_id: int = None) -> pd.DataFrame:
        endpoint = '/consignment/payment-ready'
        if user_id:
            endpoint += f'?user_id={user_id}'
        
        result = self._make_request('GET', endpoint)
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        
        return pd.DataFrame()
    
    def get_user_consignment_records_ready_for_payment(self, user_id: int) -> pd.DataFrame:
        return self.get_consignment_records_ready_for_payment(user_id)
    
    def get_consignment_records_ready_for_pickup(self, user_id: int = None) -> pd.DataFrame:
        endpoint = '/consignment/pickup-ready'
        if user_id:
            endpoint += f'?user_id={user_id}'
        
        result = self._make_request('GET', endpoint)
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        
        return pd.DataFrame()
    
    def get_user_consignment_records_ready_for_pickup(self, user_id: int) -> pd.DataFrame:
        return self.get_consignment_records_ready_for_pickup(user_id)
    
    def mark_records_for_return(self) -> int:
        result = self._make_request('POST', '/consignment/mark-for-return')
        
        if result and 'updated_count' in result:
            return result['updated_count']
        
        return 0
    
    def mark_abandoned_records_as_store_owned(self) -> int:
        result = self._make_request('POST', '/consignment/mark-abandoned')
        
        if result and 'updated_count' in result:
            return result['updated_count']
        
        return 0

    def get_records_without_barcodes(self) -> pd.DataFrame:
        result = self._make_request('GET', '/records/no-barcodes')
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        
        return pd.DataFrame()
    
    def assign_barcodes(self, record_ids: List[int]) -> Dict:
        serializable_ids = self._make_json_serializable(record_ids)
        
        result = self._make_request('POST', '/barcodes/assign', json={'record_ids': serializable_ids})
        
        if result and 'barcode_mapping' in result:
            return result['barcode_mapping']
        
        return {}

    def update_file_at_for_all_records(self) -> int:
        result = self._make_request('POST', '/records/update-file-locations')
        
        if result and 'updated_count' in result:
            return result['updated_count']
        
        return 0

    def clear_database(self):
        result = self._make_request('POST', '/database/clear')
        
        success = result is not None and result.get('status') == 'success'
        return success

    def get_artist_genre(self, artist_name: str) -> Optional[pd.Series]:
        result = self._make_request('GET', f'/genre-assignments/artist/{artist_name}')
        if result:
            return pd.Series(result)
        
        return None
    
    def get_genre_statistics(self) -> pd.DataFrame:
        result = self._make_request('GET', '/stats/genres')
        if result and 'genre_stats' in result:
            return pd.DataFrame(result['genre_stats'])
        
        return pd.DataFrame(columns=['genre_name', 'record_count'])

    def get_all_artists_with_genres(self, search_term: str = None) -> pd.DataFrame:
        endpoint = '/artists/with-genres'
        if search_term:
            endpoint += f'?search={search_term}'
        
        result = self._make_request('GET', endpoint)
        if result and 'artists' in result:
            return pd.DataFrame(result['artists'])
        
        return pd.DataFrame(columns=['artist_name', 'genre_name'])

    def _get_connection(self):
        raise Exception("Direct database connections are disabled. Use API methods instead.")
    
    def get_all_votes(self) -> pd.DataFrame:
        result = self._make_request('GET', '/votes/all')
        if result and 'votes' in result:
            return pd.DataFrame(result['votes'])
        return pd.DataFrame()
    
    def get_vote_statistics(self) -> pd.DataFrame:
        result = self._make_request('GET', '/votes/statistics')
        if result and 'statistics' in result:
            return pd.DataFrame(result['statistics'])
        return pd.DataFrame(columns=['record_id', 'artist', 'title', 'upvotes', 'downvotes', 'total_votes'])

    # NEW METHODS FOR DISCOGS GENRE MAPPINGS
    def get_discogs_genre_mapping(self, discogs_genre):
        result = self._make_request('GET', f'/discogs-genre-mappings/{discogs_genre}')
        
        if result and 'mapping' in result and result['mapping']:
            mapping_data = result['mapping']
            return {
                'mapping': {
                    'local_genre_name': mapping_data['local_genre_name'],
                    'discogs_genre': mapping_data['discogs_genre'],
                    'local_genre_id': mapping_data['local_genre_id']
                }
            }
        return {'mapping': None}
    def save_discogs_genre_mapping(self, discogs_genre, local_genre_id):
        """Save a mapping between Discogs genre and local genre"""
        # Ensure local_genre_id is a regular Python int, not numpy.int64
        local_genre_id = int(local_genre_id)
        
        result = self._make_request('POST', '/discogs-genre-mappings', 
                                  json={'discogs_genre': discogs_genre, 'local_genre_id': local_genre_id})
        success = result is not None and result.get('status') == 'success'
        return success

    def get_all_discogs_genre_mappings(self):
        """Get all Discogs genre mappings"""
        result = self._make_request('GET', '/discogs-genre-mappings')
        if result and 'mappings' in result:
            return result['mappings']
        return []
    

    def get_dropoff_records(self, user_id: int = None) -> pd.DataFrame:
        """Get consignment records ready for dropoff (records without barcodes)"""
        endpoint = '/consignment/dropoff-ready'
        if user_id:
            endpoint += f'?user_id={user_id}'
        
        result = self._make_request('GET', endpoint)
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        
        return pd.DataFrame()

    def get_records_by_ids(self, record_ids: List[int]) -> pd.DataFrame:
        """Get records by multiple IDs"""
        # For now, get all records and filter
        all_records = self.get_all_records()
        if not all_records.empty:
            return all_records[all_records['id'].isin(record_ids)]
        return pd.DataFrame()

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

    if "db_manager" not in st.session_state:
        api_base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
        st.session_state.db_manager = DatabaseManager(api_base_url)
        st.session_state.config = config
    
    # Initialize new services
    if "email_service" not in st.session_state:
        st.session_state.email_service = EmailService(st.session_state.db_manager)
    
    if "commission_calculator" not in st.session_state:
        st.session_state.commission_calculator = CommissionCalculator(st.session_state.db_manager)
    
    if "pricing_validator" not in st.session_state:
        st.session_state.pricing_validator = PricingValidator(
            st.session_state.db_manager, 
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

    discogs_handler = None
    if DISCOGS_USER_TOKEN:
        discogs_handler = DiscogsHandler(DISCOGS_USER_TOKEN)
        # Update pricing validator with discogs handler
        st.session_state.pricing_validator.discogs_handler = discogs_handler
    
    ebay_handler = None
    if EBAY_CLIENT_ID and EBAY_CLIENT_SECRET:
        ebay_handler = EbayHandler(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET)
        # Update pricing validator with ebay handler
        st.session_state.pricing_validator.ebay_handler = ebay_handler
    
    youtube_handler = None
    if YOUTUBE_API_KEY:
        youtube_handler = YouTubeHandler(YOUTUBE_API_KEY)
    else:
        st.warning("YouTube API key not found. YouTube integration will be disabled.")
 
    inventory_tab = InventoryTab(discogs_handler, ebay_handler, youtube_handler)
    statistics_tab = StatisticsTab()
    ebay_tab = EBayTab(ebay_handler)
    store_pricing_tab = StorePricingTab()
    consignment_tab = ConsignmentTab()
    price_tag_tab = PriceTagTab(st.session_state.db_manager)
    admin_config_tab = AdminConfigTab()
    votes_tab = VotesTab()

    render_header(user, session_manager)
    
    render_tabs_based_on_permissions(user, inventory_tab, price_tag_tab, store_pricing_tab, 
                                   ebay_tab, statistics_tab, consignment_tab, 
                                   admin_config_tab, votes_tab)

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
            user_info = st.session_state.db_manager.get_user_by_id(user['id'])
            if user_info is not None and not user_info.empty:
                store_credit = user_info.get('store_credit_balance', 0)
                if store_credit > 0:
                    st.metric("Store Credit", f"${store_credit:.2f}")
    
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

def render_tabs_based_on_permissions(user, inventory_tab, price_tag_tab, store_pricing_tab, 
                                   ebay_tab, statistics_tab, consignment_tab,  
                                   admin_config_tab, votes_tab):
    """Render tabs based on user permissions"""
    user_role = user['role']
    
    tab_configs = []
    
    if PermissionManager.has_permission(user_role, 'inventory', 'view'):
        tab_configs.append(("📦 Inventory", inventory_tab.render))
    
    if PermissionManager.has_permission(user_role, 'inventory', 'add'):
        tab_configs.append(("🏷️ Print Price Tags", price_tag_tab.render))
    
    if user_role == 'admin' and PermissionManager.has_permission(user_role, 'ebay', 'view'):
        tab_configs.append(("🛒 eBay", ebay_tab.render))
    
    if user_role == 'admin' and PermissionManager.has_permission(user_role, 'reports', 'view'):
        tab_configs.append(("📊 Statistics", statistics_tab.render))
    
    if user_role == 'admin' and PermissionManager.has_permission(user_role, 'reports', 'view'):
        tab_configs.append(("🗳️ Votes", votes_tab.render))
    
    if PermissionManager.has_permission(user_role, 'consignment', 'view'):
        tab_configs.append(("🤝 Consignment", consignment_tab.render))
    
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