"""
Centralized environment variable parsing handler.
Loads all required environment variables from .env file or Streamlit secrets.
Throws hard errors if required variables are missing.
"""
import os
import streamlit as st
from pathlib import Path

class EnvParsHandler:
    """Centralized handler for parsing environment variables"""
    
    def __init__(self):
        self.env_vars = {}
        self.env_vars_loaded = False
        
    def get_environment_variables(self):
        """Load all environment variables from .env or Streamlit secrets"""
        if self.env_vars_loaded:
            return self.env_vars
            
        required_vars = [
            "IMAGEBB_API_KEY",
            "DISCOGS_USER_TOKEN", 
            "EBAY_CLIENT_ID",
            "EBAY_CLIENT_SECRET",
            "YOUTUBE_API_KEY"
        ]
        
        # First try Streamlit secrets
        if hasattr(st, 'secrets'):
            secrets_available = all(var in st.secrets for var in required_vars)
            if secrets_available:
                for var in required_vars:
                    self.env_vars[var] = st.secrets[var]
                self.env_vars_loaded = True
                return self.env_vars
        
        # Then try .env file in current directory
        current_dir = os.getcwd()
        env_file_path = os.path.join(current_dir, '.env')
        
        if not os.path.exists(env_file_path):
            error_msg = f"""
            ❌ Environment variables not found!
            
            For local development:
            - Create a .env file at {env_file_path} with:
              IMAGEBB_API_KEY=your_key
              DISCOGS_USER_TOKEN=your_token
              EBAY_CLIENT_ID=your_id
              EBAY_CLIENT_SECRET=your_secret
              YOUTUBE_API_KEY=your_key
            
            For Streamlit Cloud:
            - Add these secrets in app settings under 'Secrets'
            """
            raise Exception(error_msg)
        
        # Load from .env file
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
        
        # Check for missing variables
        missing_vars = []
        for var in required_vars:
            if var not in self.env_vars or not self.env_vars[var]:
                missing_vars.append(var)
        
        if missing_vars:
            error_msg = f"""
            ❌ Missing required environment variables!
            
            Missing: {', '.join(missing_vars)}
            
            Please add these to your .env file or Streamlit Cloud secrets.
            """
            raise Exception(error_msg)
        
        self.env_vars_loaded = True
        return self.env_vars
    
    def get_api_key(self, key_name, default=None):
        """Get a specific API key"""
        if not self.env_vars_loaded:
            self.get_environment_variables()
        return self.env_vars.get(key_name, default)
    
    def validate_required_keys(self, required_keys=None):
        """Validate that required keys are present"""
        if not self.env_vars_loaded:
            self.get_environment_variables()
            
        if required_keys is None:
            required_keys = ["DISCOGS_USER_TOKEN", "EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET"]
            
        missing_keys = []
        for key in required_keys:
            if not self.env_vars.get(key):
                missing_keys.append(key)
                
        if missing_keys:
            return False, missing_keys
            
        return True, []
    
    def get_available_sources(self):
        """Get information about available environment variable sources"""
        current_dir = os.getcwd()
        env_file_path = os.path.join(current_dir, '.env')
        
        sources = {
            "env_file_exists": os.path.exists(env_file_path),
            "env_file_path": env_file_path,
            "current_directory": current_dir,
            "streamlit_secrets_available": hasattr(st, 'secrets')
        }
        return sources