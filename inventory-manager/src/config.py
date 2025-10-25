import os
import json
from pathlib import Path

class PrintConfig:
    def __init__(self, config_file="print_config.json"):
        self.config_file = config_file
        self.defaults = {
            "label_width_mm": 45.0,
            "label_height_mm": 16.80,
            "left_margin_mm": 6.50,
            "gutter_spacing_mm": 6.50,
            "top_margin_mm": 14.00,
            "font_size": 7,
            "last_genre": "",
            "genre_font_size": 48
        }
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file or use defaults"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    config = self.defaults.copy()
                    config.update(loaded_config)
                    return config
            except Exception as e:
                print(f"Error loading config file: {e}. Using defaults.")
                return self.defaults.copy()
        else:
            # Create default config file
            self._save_config(self.defaults)
            return self.defaults.copy()
    
    def _save_config(self, config):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config file: {e}")
    
    def get(self, key, default=None):
        """Get a configuration value with optional default"""
        return self.config.get(key, default if default is not None else self.defaults.get(key))
    
    def update(self, new_config):
        """Update configuration and save to file"""
        self.config.update(new_config)
        self._save_config(self.config)
    
    def get_all(self):
        """Get all configuration values"""
        return self.config.copy()