import os
import json
from pathlib import Path

class AppConfig:
    def __init__(self, config_file="app_config.json"):
        self.config_file = config_file
        self.required_keys = [
            "database_path",
            "label_width_mm", "label_height_mm", "left_margin_mm", 
            "gutter_spacing_mm", "top_margin_mm", "font_size",
            "price_font_size", "price_y_pos", "text_font_size",
            "barcode_y_pos", "barcode_height", "print_borders"
        ]
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file - throw error if file missing or values incomplete"""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)
        except Exception as e:
            raise ValueError(f"Error loading config file: {e}")
        
        # Validate all required keys exist
        missing_keys = []
        for key in self.required_keys:
            if key not in loaded_config:
                missing_keys.append(key)
        
        if missing_keys:
            raise ValueError(f"Missing required configuration keys: {', '.join(missing_keys)}")
        
        return loaded_config
    
    def _save_config(self, config):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            raise ValueError(f"Error saving config file: {e}")
    
    def get(self, key):
        """Get a configuration value - throws error if key doesn't exist"""
        if key not in self.config:
            raise KeyError(f"Configuration key '{key}' not found in config file")
        return self.config.get(key)
    
    def update(self, new_config):
        """Update configuration and save to file"""
        self.config.update(new_config)
        self._save_config(self.config)
    
    def get_all(self):
        """Get all configuration values"""
        return self.config.copy()
    
    def get_database_path(self):
        """Get the database path from config"""
        return self.get("database_path")
    
    def set_database_path(self, db_path):
        """Set the database path in config"""
        self.update({"database_path": db_path})