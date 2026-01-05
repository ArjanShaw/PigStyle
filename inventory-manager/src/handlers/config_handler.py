"""
Centralized configuration handler with caching.
Single source of truth for all config value retrieval and updates.
"""
import streamlit as st
import requests
import time
import os
from typing import Any, Optional, Dict, Union

class ConfigHandler:
    """Centralized configuration handler with intelligent caching"""
    
    _instance = None
    _cache = None
    _last_load_time = 0
    _cache_ttl = 300  # 5 minutes cache TTL
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigHandler, cls).__new__(cls)
            cls._instance._init_config_handler()
        return cls._instance
    
    def _init_config_handler(self):
        """Initialize the config handler"""
        self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
        self._cache = {}
        self._last_load_time = 0
    
    def _ensure_session_cache(self):
        """Ensure session state cache exists"""
        if 'config_cache' not in st.session_state:
            st.session_state.config_cache = {}
    
    def get(self, config_key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            config_key: The configuration key to retrieve
            default: Default value if key not found
            
        Returns:
            The configuration value or default if not found
        """
        # Ensure session state cache exists
        self._ensure_session_cache()
        
        # First check session state cache
        if config_key in st.session_state.config_cache:
            cached_value = st.session_state.config_cache[config_key]
            # Convert to appropriate type based on default or key pattern
            return self._convert_value(cached_value, default, config_key)
        
        # If not in session cache, check if we need to reload all configs
        current_time = time.time()
        needs_reload = (
            self._cache is None or 
            (current_time - self._last_load_time) >= self._cache_ttl
        )
        
        if needs_reload:
            success = self._load_all_configs()
            if not success and default is not None:
                return default
        
        # Check cache after potential reload
        if self._cache and config_key in self._cache:
            value = self._cache[config_key]
            # Also update session state cache
            st.session_state.config_cache[config_key] = value
            return self._convert_value(value, default, config_key)
        
        # If still not found and no default, try to fetch single value
        if default is None:
            value = self._fetch_single_config(config_key)
            if value is not None:
                # Cache the single value
                if self._cache is None:
                    self._cache = {}
                self._cache[config_key] = value
                st.session_state.config_cache[config_key] = value
                return self._convert_value(value, None, config_key)
        
        return default
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration values.
        
        Returns:
            Dictionary of all configuration values
        """
        # Ensure session state cache exists
        self._ensure_session_cache()
        
        current_time = time.time()
        needs_reload = (
            self._cache is None or 
            (current_time - self._last_load_time) >= self._cache_ttl
        )
        
        if needs_reload:
            success = self._load_all_configs()
            if not success:
                return {}
        
        return self._cache.copy() if self._cache else {}
    
    def set(self, config_key: str, config_value: Any) -> bool:
        """
        Set/update a configuration value.
        
        Args:
            config_key: The configuration key to update
            config_value: The new value to set
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.put(
                f"{self.base_url}/config/{config_key}",
                json={'config_value': str(config_value)},
                timeout=5
            )
            
            if response.status_code == 200:
                # Invalidate cache to force reload on next access
                self._cache = None
                self._last_load_time = 0
                # Clear session state cache
                if 'config_cache' in st.session_state:
                    st.session_state.config_cache = {}
                return True
            return False
        except Exception as e:
            print(f"ConfigHandler: Error setting config value: {e}")
            return False
    
    def clear_cache(self):
        """Clear all caches"""
        self._cache = None
        self._last_load_time = 0
        if 'config_cache' in st.session_state:
            st.session_state.config_cache = {}
    
    def _load_all_configs(self) -> bool:
        """Load all config values in a single API call"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/config", timeout=5)
            duration = time.time() - start_time
            
            print(f"ConfigHandler: Loaded all configs in {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    configs = data.get('configs', {})
                    
                    # Flatten the config structure
                    flat_configs = {}
                    for key, config_info in configs.items():
                        if isinstance(config_info, dict):
                            flat_configs[key] = config_info.get('value', '')
                        else:
                            flat_configs[key] = config_info
                    
                    self._cache = flat_configs
                    self._last_load_time = time.time()
                    
                    # Update session state cache
                    self._ensure_session_cache()
                    st.session_state.config_cache = flat_configs.copy()
                    
                    return True
            return False
        except Exception as e:
            print(f"ConfigHandler: Error loading all configs: {e}")
            return False
    
    def _fetch_single_config(self, config_key: str) -> Optional[str]:
        """Fetch a single config value directly from API"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/config/{config_key}", timeout=5)
            duration = time.time() - start_time
            
            print(f"ConfigHandler: Fetched single config '{config_key}' in {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                return data.get('config_value')
            return None
        except Exception as e:
            print(f"ConfigHandler: Error fetching single config: {e}")
            return None
    
    def _convert_value(self, value: Any, default: Any, config_key: str) -> Any:
        """
        Convert string value to appropriate type.
        
        Args:
            value: The value to convert
            default: Default value (used to infer type)
            config_key: Config key (used for special handling)
            
        Returns:
            Converted value
        """
        if value is None:
            return default
        
        # Try to infer type from default
        if default is not None:
            if isinstance(default, bool):
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ['true', 'yes', '1', 't', 'y']
                return bool(value)
            elif isinstance(default, int):
                try:
                    return int(float(value))
                except (ValueError, TypeError):
                    return default
            elif isinstance(default, float):
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
        
        # Special handling for known config keys
        if config_key in ['SHIPPING_COST', 'STORE_PRICE_ESTIMATED_MULTIPLIER', 
                         'STORE_PRICE_MINIMUM', 'EBAY_COND_TRESH', 
                         'MAX_PRICE_TO_ADV_RATIO', 'DEFAULT_COMMISSION_RATE',
                         'CONSIGNMENT_FULL_PRICE_DAYS', 'DEFAULT_STORE_RETURN_DAYS',
                         'STORE_CAPACITY', 'COMMISSION_MAX_CAPACITY',
                         'COMMISSION_MIN_CAPACITY', 'COMMISSION_MAX_RATE',
                         'COMMISSION_MIN_RATE']:
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        
        # For boolean configs
        if config_key in ['PRINT_BORDERS']:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ['true', 'yes', '1', 't', 'y']
            return bool(value)
        
        return value