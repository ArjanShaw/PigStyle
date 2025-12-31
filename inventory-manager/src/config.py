import os
import requests

class AppConfig:
    def __init__(self):
        """Initialize config with database-only approach"""
        self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
    
    def get(self, key, default=None):
        """Get a configuration value from API - throws error if key doesn't exist when no default provided"""
        if default is None:
            # If no default provided, we should raise an error if key not found
            try:
                response = requests.get(f"{self.base_url}/config/{key}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return data.get('config_value')
                else:
                    raise KeyError(f"Configuration key '{key}' not found in database")
            except Exception as e:
                raise KeyError(f"Error getting config '{key}' from API: {e}")
        else:
            # With default provided, return default if key not found
            try:
                response = requests.get(f"{self.base_url}/config/{key}", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return data.get('config_value', default)
                return default
            except:
                return default
    
    def get_all(self):
        """Get all configuration values"""
        try:
            response = requests.get(f"{self.base_url}/config", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    configs = data.get('configs', {})
                    
                    # Convert to flat dictionary
                    flat_configs = {}
                    for key, config_info in configs.items():
                        if isinstance(config_info, dict):
                            flat_configs[key] = config_info.get('value', '')
                        else:
                            flat_configs[key] = config_info
                    
                    return flat_configs
            return {}
        except Exception as e:
            print(f"Error getting all configs: {e}")
            return {}
    
    def get_database_path(self):
        """Get the database path (now hardcoded since using API)"""
        return "API-based"
    
    def set_database_path(self, db_path):
        """Set the database path (no-op for API-based config)"""
        pass  # No-op for API-based config