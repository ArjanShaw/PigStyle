# inventory-manager/src/database_manager.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import requests

class DatabaseManager:
    """Unified API-based database manager that replaces all direct SQLite access"""
    
    def __init__(self, api_base_url: str = None):
        if api_base_url is None:
            # Get from environment or use default
            api_base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
        
        self.api_base_url = api_base_url
        self.session = requests.Session()
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make API request with error handling"""
        url = f"{self.api_base_url}{endpoint}"
    
        try:
            response = self.session.request(method, url, **kwargs)
        
            # Check for any successful status code (200-299)
            if 200 <= response.status_code < 300:
                return response.json()
            else:
                st.error(f"API Error {response.status_code}: {response.text}")
            return None
            
        except Exception as e:
            st.error(f"Network error: {str(e)}")
            return None
    # ==================== CORE RECORD OPERATIONS ====================

    def get_all_records(self) -> pd.DataFrame:
        """Get all records as DataFrame"""
        result = self._make_request('GET', '/records?limit=1000')
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        return pd.DataFrame()
    
    def get_record_by_id(self, record_id: int) -> Optional[pd.Series]:
        """Get record by ID"""
        result = self._make_request('GET', f'/records/{record_id}')
        if result:
            return pd.Series(result)
        return None
    
    def save_record(self, result_data: Dict) -> int:
        """Save record to database via API"""
        result = self._make_request('POST', '/records', json=result_data)
        if result and 'record_id' in result:
            return result['record_id']
        return None
    
    def update_record(self, record_id: int, updates: Dict) -> bool:
        """Update record via API"""
        result = self._make_request('PUT', f'/records/{record_id}', json=updates)
        return result is not None and result.get('status') == 'success'
    
    def delete_record(self, record_id: int) -> bool:
        """Delete record via API"""
        result = self._make_request('DELETE', f'/records/{record_id}')
        return result is not None and result.get('status') == 'success'
    
    def search_records(self, search_term: str) -> pd.DataFrame:
        """Search records via API"""
        result = self._make_request('GET', f'/search?q={search_term}')
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        return pd.DataFrame()
    
    def get_record_by_barcode(self, barcode: str) -> Optional[pd.Series]:
        """Get record by barcode"""
        result = self._make_request('GET', f'/records/barcode/{barcode}')
        if result:
            return pd.Series(result)
        return None

    # ==================== VOTE MANAGEMENT ====================

    def record_vote(self, record_id: int, voter_hash: str, vote_type: str) -> bool:
        """Record a vote via API"""
        result = self._make_request('POST', f'/vote/{record_id}/{voter_hash}/{vote_type}')
        return result is not None and result.get('status') == 'success'
    
    def get_vote_counts(self, record_id: int = None):
        """Get vote counts via API"""
        if record_id:
            result = self._make_request('GET', f'/votes/{record_id}')
            if result:
                return {record_id: {
                    'upvotes': result.get('upvotes', 0),
                    'downvotes': result.get('downvotes', 0)
                }}
        return {}
    
    def get_user_vote(self, record_id: int, voter_hash: str) -> Optional[str]:
        """Get user's vote via API"""
        result = self._make_request('GET', f'/user-vote/{record_id}/{voter_hash}')
        if result:
            return result.get('vote_type')
        return None

    # ==================== GENRE MANAGEMENT ====================

    def get_all_genres(self) -> pd.DataFrame:
        """Get all genres"""
        result = self._make_request('GET', '/genres')
        if result and 'genres' in result:
            return pd.DataFrame(result['genres'])
        return pd.DataFrame(columns=['id', 'genre_name'])
    
    def add_genre(self, genre_name: str):
        """Add genre"""
        result = self._make_request('POST', '/genres', json={'genre_name': genre_name})
        if result and 'genre_id' in result:
            return True, result['genre_id']
        return False, None
    
    def assign_genre_to_artist(self, artist_name: str, genre_id: int) -> bool:
        """Assign genre to artist"""
        result = self._make_request('POST', '/genre-assignments', json={
            'artist_name': artist_name,
            'genre_id': genre_id
        })
        return result is not None and result.get('status') == 'success'
    
    def remove_genre_from_artist_by_name(self, artist_name: str) -> bool:
        """Remove genre assignment from artist"""
        result = self._make_request('DELETE', f'/genre-assignments/artist/{artist_name}')
        return result is not None and result.get('status') == 'success'

    # ==================== USER MANAGEMENT ====================

    def get_all_users(self) -> pd.DataFrame:
        """Get all users"""
        result = self._make_request('GET', '/users')
        if result and 'users' in result:
            return pd.DataFrame(result['users'])
        return pd.DataFrame()
    
    def get_user_by_id(self, user_id: int) -> Optional[pd.Series]:
        """Get user by ID"""
        result = self._make_request('GET', f'/users/{user_id}')
        if result:
            return pd.Series(result)
        return None

    # ==================== CONFIGURATION MANAGEMENT ====================

    def get_config_value(self, config_key: str, default: Any = None) -> Any:
        """Get configuration value"""
        result = self._make_request('GET', f'/config/{config_key}')
        if result and 'config_value' in result:
            return result['config_value']
        return default
    
    def set_config_value(self, config_key: str, config_value: str) -> bool:
        """Set configuration value"""
        result = self._make_request('POST', '/config', json={
            'config_key': config_key,
            'config_value': config_value
        })
        return result is not None and result.get('status') == 'success'

    def get_all_config(self):
        """Get all configuration values"""
        result = self._make_request('GET', '/config')
        if result and 'configs' in result:
            return result['configs']
        return []

    # ==================== PASSWORD MANAGEMENT ====================

    def reset_user_password(self, user_id: int, new_password: str) -> bool:
        """Reset user password (admin only)"""
        result = self._make_request('POST', f'/users/{user_id}/reset-password', json={
            'new_password': new_password
        })
        return result is not None and result.get('status') == 'success'

    def change_user_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        """Change user password (requires current password)"""
        result = self._make_request('POST', f'/users/{user_id}/change-password', json={
            'current_password': current_password,
            'new_password': new_password
        })
        return result is not None and result.get('status') == 'success'

    # ==================== STATISTICS & REPORTING ====================

    def get_database_stats(self) -> Dict:
        """Get database statistics"""
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
        """Get user-specific database statistics"""
        result = self._make_request('GET', f'/stats/user/{user_id}')
        if result:
            return result
        return {
            'records_count': 0,
            'db_path': 'API-based'
        }

    # ==================== CONSIGNMENT OPERATIONS ====================

    def get_consignment_records_ready_for_payment(self, user_id: int = None) -> pd.DataFrame:
        """Get consignment records ready for payment"""
        endpoint = '/consignment/payment-ready'
        if user_id:
            endpoint += f'?user_id={user_id}'
        result = self._make_request('GET', endpoint)
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        return pd.DataFrame()
    
    def get_user_consignment_records_ready_for_payment(self, user_id: int) -> pd.DataFrame:
        """Get consignment records ready for payment for a specific user"""
        return self.get_consignment_records_ready_for_payment(user_id)
    
    def get_consignment_records_ready_for_pickup(self, user_id: int = None) -> pd.DataFrame:
        """Get consignment records ready for pickup"""
        endpoint = '/consignment/pickup-ready'
        if user_id:
            endpoint += f'?user_id={user_id}'
        result = self._make_request('GET', endpoint)
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        return pd.DataFrame()
    
    def get_user_consignment_records_ready_for_pickup(self, user_id: int) -> pd.DataFrame:
        """Get consignment records ready for pickup for a specific user"""
        return self.get_consignment_records_ready_for_pickup(user_id)
    
    def mark_records_for_return(self) -> int:
        """Mark consignment records as ready for pickup"""
        result = self._make_request('POST', '/consignment/mark-for-return')
        if result and 'updated_count' in result:
            return result['updated_count']
        return 0
    
    def mark_abandoned_records_as_store_owned(self) -> int:
        """Mark abandoned consignment records as store property"""
        result = self._make_request('POST', '/consignment/mark-abandoned')
        if result and 'updated_count' in result:
            return result['updated_count']
        return 0

    # ==================== PRICE TAG & BARCODE OPERATIONS ====================

    def get_records_without_barcodes(self) -> pd.DataFrame:
        """Get records without barcodes"""
        result = self._make_request('GET', '/records/no-barcodes')
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        return pd.DataFrame()
    
    def assign_barcodes(self, record_ids: List[int]) -> Dict:
        """Assign barcodes to records"""
        print(f"🔴 DEBUG: DatabaseManager.assign_barcodes called with record_ids: {record_ids}")
        result = self._make_request('POST', '/barcodes/assign', json={'record_ids': record_ids})
        print(f"🔴 DEBUG: DatabaseManager.assign_barcodes API response: {result}")
        if result and 'barcode_mapping' in result:
            return result['barcode_mapping']
        return {}

    # ==================== FILE LOCATION OPERATIONS ====================

    def update_file_at_for_all_records(self) -> int:
        """Update file_at column for all records"""
        result = self._make_request('POST', '/records/update-file-locations')
        if result and 'updated_count' in result:
            return result['updated_count']
        return 0

    # ==================== DATABASE MAINTENANCE ====================

    def clear_database(self):
        """Clear all data from database"""
        result = self._make_request('POST', '/database/clear')
        return result is not None and result.get('status') == 'success'

    # ==================== COMPATIBILITY METHODS ====================

    def get_recent_records(self, limit: int = 100) -> pd.DataFrame:
        """Get recent records"""
        result = self._make_request('GET', f'/records?limit={limit}')
        if result and 'records' in result:
            return pd.DataFrame(result['records'])
        return pd.DataFrame()

    def get_artist_genre(self, artist_name: str) -> Optional[pd.Series]:
        """Get the genre assigned to an artist"""
        result = self._make_request('GET', f'/genre-assignments/artist/{artist_name}')
        if result:
            return pd.Series(result)
        return None
    
    def get_genre_statistics(self) -> pd.DataFrame:
        """Get statistics about genres and records"""
        result = self._make_request('GET', '/stats/genres')
        if result and 'genre_stats' in result:
            return pd.DataFrame(result['genre_stats'])
        return pd.DataFrame(columns=['genre_name', 'record_count'])

    def get_all_artists_with_genres(self, search_term: str = None) -> pd.DataFrame:
        """Get all artists from records and their assigned genres"""
        endpoint = '/artists/with-genres'
        if search_term:
            endpoint += f'?search={search_term}'
        result = self._make_request('GET', endpoint)
        if result and 'artists' in result:
            return pd.DataFrame(result['artists'])
        return pd.DataFrame(columns=['artist_name', 'genre_name'])

    # ==================== LEGACY METHOD FOR COMPATIBILITY ====================

    def _get_connection(self):
        """Legacy method - raises error to prevent direct SQLite usage"""
        raise Exception("Direct database connections are disabled. Use API methods instead.")