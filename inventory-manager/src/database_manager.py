import streamlit as st
import pandas as pd
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import requests
import json
import numpy as np

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