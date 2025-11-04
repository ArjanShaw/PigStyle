import os
import streamlit as st
from pathlib import Path

class APIKeyHandler:
    """Handles loading and validation of API keys from .env file only"""
    
    def __init__(self, debug_tab=None):
        self.debug_tab = debug_tab
        self.env_vars = {}
        self.env_vars_loaded = False
    
    def get_environment_variables(self):
        """Get environment variables ONLY from .env file in project base directory"""
        if self.env_vars_loaded:
            return self.env_vars
            
        required_vars = [
            "IMAGEBB_API_KEY",
            "DISCOGS_USER_TOKEN", 
            "EBAY_CLIENT_ID",
            "EBAY_CLIENT_SECRET"
        ]
        
        # Get the project base directory and .env file path
        current_dir = os.getcwd()
        env_file_path = os.path.join(current_dir, '.env')
        
        # Check if .env file exists
        if not os.path.exists(env_file_path):
            error_msg = f"❌ .env file not found at {env_file_path}"
            self._log_debug("ERROR", error_msg)
            raise Exception(error_msg)
        
        # Load environment variables from .env file
        try:
            with open(env_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Remove quotes if present
                        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]
                        self.env_vars[key] = value
        except Exception as e:
            error_msg = f"❌ Error reading .env file: {str(e)}"
            self._log_debug("ERROR", error_msg)
            raise Exception(error_msg)
        
        # Validate all required variables are present
        missing_vars = []
        for var in required_vars:
            if var not in self.env_vars or not self.env_vars[var]:
                missing_vars.append(var)
        
        if missing_vars:
            error_msg = f"❌ Missing required variables in .env file: {', '.join(missing_vars)}"
            self._log_debug("ERROR", error_msg)
            raise Exception(error_msg)
        
        # Log successful loading
        for var in required_vars:
            self._log_debug("ENV", f"✅ {var} loaded from .env file", {"source": f".env file at {env_file_path}"})
        
        self.env_vars_loaded = True
        return self.env_vars
    
    def get_api_key(self, key_name, default=None):
        """Get a specific API key by name"""
        if not self.env_vars_loaded:
            self.get_environment_variables()
        return self.env_vars.get(key_name, default)
    
    def validate_required_keys(self, required_keys=None):
        """Validate that all required API keys are available"""
        if not self.env_vars_loaded:
            self.get_environment_variables()
            
        if required_keys is None:
            required_keys = ["DISCOGS_USER_TOKEN", "EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET"]
            
        missing_keys = []
        for key in required_keys:
            if not self.env_vars.get(key):
                missing_keys.append(key)
                
        if missing_keys:
            self._log_debug("ERROR", f"Missing required API keys: {', '.join(missing_keys)}")
            return False
            
        self._log_debug("SUCCESS", "All required API keys are available")
        return True
    
    def _log_debug(self, category, message, data=None):
        """Log to debug tab if available"""
        if self.debug_tab:
            self.debug_tab.add_log(category, message, data)
    
    def get_available_sources(self):
        """Get information about available API key sources"""
        current_dir = os.getcwd()
        env_file_path = os.path.join(current_dir, '.env')
        
        sources = {
            "env_file_exists": os.path.exists(env_file_path),
            "env_file_path": env_file_path,
            "current_directory": current_dir
        }
        return sources