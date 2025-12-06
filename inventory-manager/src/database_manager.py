# inventory-manager/src/database_manager.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import requests
import json
import traceback

class DatabaseManager:
    """Unified API-based database manager that replaces all direct SQLite access"""
    
    def __init__(self, api_base_url: str = None):
        if api_base_url is None:
            # Get from environment or use default
            api_base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
        
        self.api_base_url = api_base_url
        self.session = requests.Session()
        print(f"🔴 DEBUG: DatabaseManager initialized with API URL: {api_base_url}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make API request with error handling"""
        url = f"{self.api_base_url}{endpoint}"
        
        print(f"🔴 DEBUG: _make_request - URL: {url}")
        print(f"🔴 DEBUG: _make_request - Method: {method}")
        print(f"🔴 DEBUG: _make_request - Endpoint: {endpoint}")
        
        try:
            # Log the JSON data being sent
            if 'json' in kwargs:
                print(f"🔴 DEBUG: _make_request - Request data (raw): {kwargs['json']}")
                try:
                    print(f"🔴 DEBUG: _make_request - Request data (JSON): {json.dumps(kwargs['json'], indent=2)}")
                except Exception as json_err:
                    print(f"🔴 DEBUG: _make_request - Could not serialize JSON: {json_err}")
            
            response = self.session.request(method, url, **kwargs)
            
            print(f"🔴 DEBUG: _make_request - Response status: {response.status_code}")
            print(f"🔴 DEBUG: _make_request - Response headers: {dict(response.headers)}")
            
            # Check for any successful status code (200-299)
            if 200 <= response.status_code < 300:
                try:
                    result = response.json()
                    print(f"🔴 DEBUG: _make_request - Response JSON: {json.dumps(result, indent=2)}")
                    return result
                except Exception as json_err:
                    print(f"🔴 DEBUG: _make_request - Failed to parse JSON: {json_err}")
                    print(f"🔴 DEBUG: _make_request - Raw response: {response.text[:500]}")
                    return None
            else:
                print(f"🔴 DEBUG: _make_request - API Error {response.status_code}: {response.text}")
                st.error(f"API Error {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.ConnectionError as e:
            print(f"🔴 DEBUG: _make_request - Connection error: {str(e)}")
            st.error(f"Connection error: {str(e)}")
            return None
        except requests.exceptions.Timeout as e:
            print(f"🔴 DEBUG: _make_request - Timeout error: {str(e)}")
            st.error(f"Timeout error: {str(e)}")
            return None
        except Exception as e:
            print(f"🔴 DEBUG: _make_request - Unexpected error: {str(e)}")
            print(f"🔴 DEBUG: _make_request - Traceback: {traceback.format_exc()}")
            st.error(f"Network error: {str(e)}")
            return None
    
    def _make_json_serializable(self, data):
        """Convert NumPy/Pandas types to native Python types for JSON serialization"""
        import pandas as pd
        import numpy as np
        
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
    
    # ==================== CORE RECORD OPERATIONS ====================

    def get_all_records(self) -> pd.DataFrame:
        """Get all records as DataFrame"""
        print(f"🔴 DEBUG: get_all_records called")
        result = self._make_request('GET', '/records?limit=1000')
        if result and 'records' in result:
            df = pd.DataFrame(result['records'])
            print(f"🔴 DEBUG: get_all_records returned {len(df)} records")
            return df
        print(f"🔴 DEBUG: get_all_records returned empty DataFrame")
        return pd.DataFrame()
    
    def get_record_by_id(self, record_id: int) -> Optional[pd.Series]:
        """Get record by ID"""
        print(f"🔴 DEBUG: get_record_by_id called with ID: {record_id}")
        result = self._make_request('GET', f'/records/{record_id}')
        if result:
            print(f"🔴 DEBUG: get_record_by_id found record")
            return pd.Series(result)
        print(f"🔴 DEBUG: get_record_by_id returned None")
        return None
    
    def save_record(self, result_data: Dict) -> int:
        """Save record to database via API"""
        print(f"🔴 DEBUG: save_record called")
        print(f"🔴 DEBUG: save_record - Input data type: {type(result_data)}")
        print(f"🔴 DEBUG: save_record - Input data keys: {list(result_data.keys())}")
        
        # Make data JSON serializable
        serializable_data = self._make_json_serializable(result_data)
        print(f"🔴 DEBUG: save_record - Serializable data: {serializable_data}")
        
        result = self._make_request('POST', '/records', json=serializable_data)
        print(f"🔴 DEBUG: save_record - API result: {result}")
        
        if result and 'record_id' in result:
            record_id = result['record_id']
            print(f"🔴 DEBUG: save_record - Success! Record ID: {record_id}")
            return record_id
        
        print(f"🔴 DEBUG: save_record - Failed! Returning None")
        return None
    
    def update_record(self, record_id: int, updates: Dict) -> bool:
        """Update record via API"""
        print(f"🔴 DEBUG: update_record called for ID: {record_id}")
        print(f"🔴 DEBUG: update_record - Updates: {updates}")
        
        # Make data JSON serializable
        serializable_updates = self._make_json_serializable(updates)
        
        result = self._make_request('PUT', f'/records/{record_id}', json=serializable_updates)
        print(f"🔴 DEBUG: update_record - API result: {result}")
        
        success = result is not None and result.get('status') == 'success'
        print(f"🔴 DEBUG: update_record - Success: {success}")
        return success
    
    def delete_record(self, record_id: int) -> bool:
        """Delete record via API"""
        print(f"🔴 DEBUG: delete_record called for ID: {record_id}")
        result = self._make_request('DELETE', f'/records/{record_id}')
        print(f"🔴 DEBUG: delete_record - API result: {result}")
        
        success = result is not None and result.get('status') == 'success'
        print(f"🔴 DEBUG: delete_record - Success: {success}")
        return success
    
    def search_records(self, search_term: str) -> pd.DataFrame:
        """Search records via API"""
        print(f"🔴 DEBUG: search_records called for: {search_term}")
        result = self._make_request('GET', f'/search?q={search_term}')
        if result and 'records' in result:
            df = pd.DataFrame(result['records'])
            print(f"🔴 DEBUG: search_records returned {len(df)} records")
            return df
        print(f"🔴 DEBUG: search_records returned empty DataFrame")
        return pd.DataFrame()
    
    def get_record_by_barcode(self, barcode: str) -> Optional[pd.Series]:
        """Get record by barcode"""
        print(f"🔴 DEBUG: get_record_by_barcode called for: {barcode}")
        result = self._make_request('GET', f'/records/barcode/{barcode}')
        if result:
            print(f"🔴 DEBUG: get_record_by_barcode found record")
            return pd.Series(result)
        print(f"🔴 DEBUG: get_record_by_barcode returned None")
        return None

    # ==================== VOTE MANAGEMENT ====================

    def record_vote(self, record_id: int, voter_hash: str, vote_type: str) -> bool:
        """Record a vote via API"""
        print(f"🔴 DEBUG: record_vote called")
        result = self._make_request('POST', f'/vote/{record_id}/{voter_hash}/{vote_type}')
        print(f"🔴 DEBUG: record_vote - API result: {result}")
        
        success = result is not None and result.get('status') == 'success'
        print(f"🔴 DEBUG: record_vote - Success: {success}")
        return success
    
    def get_vote_counts(self, record_id: int = None):
        """Get vote counts via API"""
        print(f"🔴 DEBUG: get_vote_counts called for record_id: {record_id}")
        if record_id:
            result = self._make_request('GET', f'/votes/{record_id}')
            if result:
                print(f"🔴 DEBUG: get_vote_counts found data")
                return {record_id: {
                    'upvotes': result.get('upvotes', 0),
                    'downvotes': result.get('downvotes', 0)
                }}
        print(f"🔴 DEBUG: get_vote_counts returned empty dict")
        return {}
    
    def get_user_vote(self, record_id: int, voter_hash: str) -> Optional[str]:
        """Get user's vote via API"""
        print(f"🔴 DEBUG: get_user_vote called")
        result = self._make_request('GET', f'/user-vote/{record_id}/{voter_hash}')
        if result:
            vote_type = result.get('vote_type')
            print(f"🔴 DEBUG: get_user_vote - Vote type: {vote_type}")
            return vote_type
        print(f"🔴 DEBUG: get_user_vote returned None")
        return None

    # ==================== GENRE MANAGEMENT ====================

    def get_all_genres(self) -> pd.DataFrame:
        """Get all genres"""
        print(f"🔴 DEBUG: get_all_genres called")
        result = self._make_request('GET', '/genres')
        if result and 'genres' in result:
            df = pd.DataFrame(result['genres'])
            print(f"🔴 DEBUG: get_all_genres returned {len(df)} genres")
            return df
        print(f"🔴 DEBUG: get_all_genres returned empty DataFrame")
        return pd.DataFrame(columns=['id', 'genre_name'])
    
    def add_genre(self, genre_name: str):
        """Add genre"""
        print(f"🔴 DEBUG: add_genre called for: {genre_name}")
        result = self._make_request('POST', '/genres', json={'genre_name': genre_name})
        print(f"🔴 DEBUG: add_genre - API result: {result}")
        
        if result and 'genre_id' in result:
            genre_id = result['genre_id']
            print(f"🔴 DEBUG: add_genre - Success! Genre ID: {genre_id}")
            return True, genre_id
        
        print(f"🔴 DEBUG: add_genre - Failed!")
        return False, None
    
    def assign_genre_to_artist(self, artist_name: str, genre_id: int) -> bool:
        """Assign genre to artist"""
        print(f"🔴 DEBUG: assign_genre_to_artist called for artist: {artist_name}, genre_id: {genre_id}")
        result = self._make_request('POST', '/genre-assignments', json={
            'artist_name': artist_name,
            'genre_id': genre_id
        })
        print(f"🔴 DEBUG: assign_genre_to_artist - API result: {result}")
        
        success = result is not None and result.get('status') == 'success'
        print(f"🔴 DEBUG: assign_genre_to_artist - Success: {success}")
        return success
    
    def remove_genre_from_artist_by_name(self, artist_name: str) -> bool:
        """Remove genre assignment from artist"""
        print(f"🔴 DEBUG: remove_genre_from_artist_by_name called for artist: {artist_name}")
        result = self._make_request('DELETE', f'/genre-assignments/artist/{artist_name}')
        print(f"🔴 DEBUG: remove_genre_from_artist_by_name - API result: {result}")
        
        success = result is not None and result.get('status') == 'success'
        print(f"🔴 DEBUG: remove_genre_from_artist_by_name - Success: {success}")
        return success

    # ==================== USER MANAGEMENT ====================

    def get_all_users(self) -> pd.DataFrame:
        """Get all users"""
        print(f"🔴 DEBUG: get_all_users called")
        result = self._make_request('GET', '/users')
        if result and 'users' in result:
            df = pd.DataFrame(result['users'])
            print(f"🔴 DEBUG: get_all_users returned {len(df)} users")
            return df
        print(f"🔴 DEBUG: get_all_users returned empty DataFrame")
        return pd.DataFrame()
    
    def get_user_by_id(self, user_id: int) -> Optional[pd.Series]:
        """Get user by ID"""
        print(f"🔴 DEBUG: get_user_by_id called for ID: {user_id}")
        result = self._make_request('GET', f'/users/{user_id}')
        if result:
            print(f"🔴 DEBUG: get_user_by_id found user")
            return pd.Series(result)
        print(f"🔴 DEBUG: get_user_by_id returned None")
        return None

    # ==================== CONFIGURATION MANAGEMENT ====================

    def get_config_value(self, config_key: str, default: Any = None) -> Any:
        """Get configuration value"""
        print(f"🔴 DEBUG: get_config_value called for key: {config_key}")
        result = self._make_request('GET', f'/config/{config_key}')
        if result and 'config_value' in result:
            value = result['config_value']
            print(f"🔴 DEBUG: get_config_value - Value: {value}")
            return value
        
        print(f"🔴 DEBUG: get_config_value - Using default: {default}")
        return default
    
    def set_config_value(self, config_key: str, config_value: str) -> bool:
        """Set configuration value"""
        print(f"🔴 DEBUG: set_config_value called for key: {config_key}, value: {config_value}")
        result = self._make_request('POST', '/config', json={
            'config_key': config_key,
            'config_value': config_value
        })
        print(f"🔴 DEBUG: set_config_value - API result: {result}")
        
        success = result is not None and result.get('status') == 'success'
        print(f"🔴 DEBUG: set_config_value - Success: {success}")
        return success

    def get_all_config(self):
        """Get all configuration values"""
        print(f"🔴 DEBUG: get_all_config called")
        result = self._make_request('GET', '/config')
        if result and 'configs' in result:
            configs = result['configs']
            print(f"🔴 DEBUG: get_all_config returned {len(configs)} configs")
            return configs
        print(f"🔴 DEBUG: get_all_config returned empty list")
        return []

    # ==================== PASSWORD MANAGEMENT ====================

    def reset_user_password(self, user_id: int, new_password: str) -> bool:
        """Reset user password (admin only)"""
        print(f"🔴 DEBUG: reset_user_password called for user_id: {user_id}")
        result = self._make_request('POST', f'/users/{user_id}/reset-password', json={
            'new_password': new_password
        })
        print(f"🔴 DEBUG: reset_user_password - API result: {result}")
        
        success = result is not None and result.get('status') == 'success'
        print(f"🔴 DEBUG: reset_user_password - Success: {success}")
        return success

    def change_user_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        """Change user password (requires current password)"""
        print(f"🔴 DEBUG: change_user_password called for user_id: {user_id}")
        result = self._make_request('POST', f'/users/{user_id}/change-password', json={
            'current_password': current_password,
            'new_password': new_password
        })
        print(f"🔴 DEBUG: change_user_password - API result: {result}")
        
        success = result is not None and result.get('status') == 'success'
        print(f"🔴 DEBUG: change_user_password - Success: {success}")
        return success

    # ==================== STATISTICS & REPORTING ====================

    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        print(f"🔴 DEBUG: get_database_stats called")
        result = self._make_request('GET', '/stats')
        if result:
            print(f"🔴 DEBUG: get_database_stats - Result: {result}")
            return result
        
        print(f"🔴 DEBUG: get_database_stats - Using default stats")
        return {
            'records_count': 0,
            'users_count': 0,
            'latest_record': 'N/A',
            'db_path': 'API-based'
        }
    
    def get_user_database_stats(self, user_id: int) -> Dict:
        """Get user-specific database statistics"""
        print(f"🔴 DEBUG: get_user_database_stats called for user_id: {user_id}")
        result = self._make_request('GET', f'/stats/user/{user_id}')
        if result:
            print(f"🔴 DEBUG: get_user_database_stats - Result: {result}")
            return result
        
        print(f"🔴 DEBUG: get_user_database_stats - Using default stats")
        return {
            'records_count': 0,
            'db_path': 'API-based'
        }

    # ==================== CONSIGNMENT OPERATIONS ====================

    def get_consignment_records_ready_for_payment(self, user_id: int = None) -> pd.DataFrame:
        """Get consignment records ready for payment"""
        print(f"🔴 DEBUG: get_consignment_records_ready_for_payment called for user_id: {user_id}")
        endpoint = '/consignment/payment-ready'
        if user_id:
            endpoint += f'?user_id={user_id}'
        
        result = self._make_request('GET', endpoint)
        if result and 'records' in result:
            df = pd.DataFrame(result['records'])
            print(f"🔴 DEBUG: get_consignment_records_ready_for_payment returned {len(df)} records")
            return df
        
        print(f"🔴 DEBUG: get_consignment_records_ready_for_payment returned empty DataFrame")
        return pd.DataFrame()
    
    def get_user_consignment_records_ready_for_payment(self, user_id: int) -> pd.DataFrame:
        """Get consignment records ready for payment for a specific user"""
        print(f"🔴 DEBUG: get_user_consignment_records_ready_for_payment called for user_id: {user_id}")
        return self.get_consignment_records_ready_for_payment(user_id)
    
    def get_consignment_records_ready_for_pickup(self, user_id: int = None) -> pd.DataFrame:
        """Get consignment records ready for pickup"""
        print(f"🔴 DEBUG: get_consignment_records_ready_for_pickup called for user_id: {user_id}")
        endpoint = '/consignment/pickup-ready'
        if user_id:
            endpoint += f'?user_id={user_id}'
        
        result = self._make_request('GET', endpoint)
        if result and 'records' in result:
            df = pd.DataFrame(result['records'])
            print(f"🔴 DEBUG: get_consignment_records_ready_for_pickup returned {len(df)} records")
            return df
        
        print(f"🔴 DEBUG: get_consignment_records_ready_for_pickup returned empty DataFrame")
        return pd.DataFrame()
    
    def get_user_consignment_records_ready_for_pickup(self, user_id: int) -> pd.DataFrame:
        """Get consignment records ready for pickup for a specific user"""
        print(f"🔴 DEBUG: get_user_consignment_records_ready_for_pickup called for user_id: {user_id}")
        return self.get_consignment_records_ready_for_pickup(user_id)
    
    def mark_records_for_return(self) -> int:
        """Mark consignment records as ready for pickup"""
        print(f"🔴 DEBUG: mark_records_for_return called")
        result = self._make_request('POST', '/consignment/mark-for-return')
        print(f"🔴 DEBUG: mark_records_for_return - API result: {result}")
        
        if result and 'updated_count' in result:
            updated_count = result['updated_count']
            print(f"🔴 DEBUG: mark_records_for_return - Updated count: {updated_count}")
            return updated_count
        
        print(f"🔴 DEBUG: mark_records_for_return - No records updated")
        return 0
    
    def mark_abandoned_records_as_store_owned(self) -> int:
        """Mark abandoned consignment records as store property"""
        print(f"🔴 DEBUG: mark_abandoned_records_as_store_owned called")
        result = self._make_request('POST', '/consignment/mark-abandoned')
        print(f"🔴 DEBUG: mark_abandoned_records_as_store_owned - API result: {result}")
        
        if result and 'updated_count' in result:
            updated_count = result['updated_count']
            print(f"🔴 DEBUG: mark_abandoned_records_as_store_owned - Updated count: {updated_count}")
            return updated_count
        
        print(f"🔴 DEBUG: mark_abandoned_records_as_store_owned - No records updated")
        return 0

    # ==================== PRICE TAG & BARCODE OPERATIONS ====================

    def get_records_without_barcodes(self) -> pd.DataFrame:
        """Get records without barcodes"""
        print(f"🔴 DEBUG: get_records_without_barcodes called")
        result = self._make_request('GET', '/records/no-barcodes')
        if result and 'records' in result:
            df = pd.DataFrame(result['records'])
            print(f"🔴 DEBUG: get_records_without_barcodes returned {len(df)} records")
            return df
        
        print(f"🔴 DEBUG: get_records_without_barcodes returned empty DataFrame")
        return pd.DataFrame()
    
    def assign_barcodes(self, record_ids: List[int]) -> Dict:
        """Assign barcodes to records"""
        print(f"🔴 DEBUG: DatabaseManager.assign_barcodes called with record_ids: {record_ids}")
        
        # Make data JSON serializable
        serializable_ids = self._make_json_serializable(record_ids)
        
        result = self._make_request('POST', '/barcodes/assign', json={'record_ids': serializable_ids})
        print(f"🔴 DEBUG: DatabaseManager.assign_barcodes API response: {result}")
        
        if result and 'barcode_mapping' in result:
            mapping = result['barcode_mapping']
            print(f"🔴 DEBUG: DatabaseManager.assign_barcodes - Mapping: {mapping}")
            return mapping
        
        print(f"🔴 DEBUG: DatabaseManager.assign_barcodes - No mapping returned")
        return {}

    # ==================== FILE LOCATION OPERATIONS ====================

    def update_file_at_for_all_records(self) -> int:
        """Update file_at column for all records"""
        print(f"🔴 DEBUG: update_file_at_for_all_records called")
        result = self._make_request('POST', '/records/update-file-locations')
        print(f"🔴 DEBUG: update_file_at_for_all_records - API result: {result}")
        
        if result and 'updated_count' in result:
            updated_count = result['updated_count']
            print(f"🔴 DEBUG: update_file_at_for_all_records - Updated count: {updated_count}")
            return updated_count
        
        print(f"🔴 DEBUG: update_file_at_for_all_records - No records updated")
        return 0

    # ==================== DATABASE MAINTENANCE ====================

    def clear_database(self):
        """Clear all data from database"""
        print(f"🔴 DEBUG: clear_database called")
        result = self._make_request('POST', '/database/clear')
        print(f"🔴 DEBUG: clear_database - API result: {result}")
        
        success = result is not None and result.get('status') == 'success'
        print(f"🔴 DEBUG: clear_database - Success: {success}")
        return success

    # ==================== COMPATIBILITY METHODS ====================

    def get_recent_records(self, limit: int = 100) -> pd.DataFrame:
        """Get recent records"""
        print(f"🔴 DEBUG: get_recent_records called with limit: {limit}")
        result = self._make_request('GET', f'/records?limit={limit}')
        if result and 'records' in result:
            df = pd.DataFrame(result['records'])
            print(f"🔴 DEBUG: get_recent_records returned {len(df)} records")
            return df
        
        print(f"🔴 DEBUG: get_recent_records returned empty DataFrame")
        return pd.DataFrame()

    def get_artist_genre(self, artist_name: str) -> Optional[pd.Series]:
        """Get the genre assigned to an artist"""
        print(f"🔴 DEBUG: get_artist_genre called for artist: {artist_name}")
        result = self._make_request('GET', f'/genre-assignments/artist/{artist_name}')
        if result:
            print(f"🔴 DEBUG: get_artist_genre found genre")
            return pd.Series(result)
        
        print(f"🔴 DEBUG: get_artist_genre returned None")
        return None
    
    def get_genre_statistics(self) -> pd.DataFrame:
        """Get statistics about genres and records"""
        print(f"🔴 DEBUG: get_genre_statistics called")
        result = self._make_request('GET', '/stats/genres')
        if result and 'genre_stats' in result:
            df = pd.DataFrame(result['genre_stats'])
            print(f"🔴 DEBUG: get_genre_statistics returned {len(df)} genre stats")
            return df
        
        print(f"🔴 DEBUG: get_genre_statistics returned empty DataFrame")
        return pd.DataFrame(columns=['genre_name', 'record_count'])

    def get_all_artists_with_genres(self, search_term: str = None) -> pd.DataFrame:
        """Get all artists from records and their assigned genres"""
        print(f"🔴 DEBUG: get_all_artists_with_genres called with search_term: {search_term}")
        endpoint = '/artists/with-genres'
        if search_term:
            endpoint += f'?search={search_term}'
        
        result = self._make_request('GET', endpoint)
        if result and 'artists' in result:
            df = pd.DataFrame(result['artists'])
            print(f"🔴 DEBUG: get_all_artists_with_genres returned {len(df)} artists")
            return df
        
        print(f"🔴 DEBUG: get_all_artists_with_genres returned empty DataFrame")
        return pd.DataFrame(columns=['artist_name', 'genre_name'])

    # ==================== LEGACY METHOD FOR COMPATIBILITY ====================

    def _get_connection(self):
        """Legacy method - raises error to prevent direct SQLite usage"""
        raise Exception("Direct database connections are disabled. Use API methods instead.")