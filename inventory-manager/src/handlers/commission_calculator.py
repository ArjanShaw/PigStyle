import streamlit as st
import requests

class CommissionCalculator:
    """Capacity-based commission calculator"""
    
    def __init__(self, api_client):
        """Initialize with API client"""
        self.api_client = api_client
    
    def get_current_commission_rate(self):
        """Get commission rate based ONLY on store capacity - throws error if config missing"""
        # Get required configuration values - will throw error if any missing
        max_capacity = self._get_config_value('COMMISSION_MAX_CAPACITY')
        min_capacity = self._get_config_value('COMMISSION_MIN_CAPACITY')
        max_rate = self._get_config_value('COMMISSION_MAX_RATE')
        min_rate = self._get_config_value('COMMISSION_MIN_RATE')
        store_capacity = self._get_config_value('STORE_CAPACITY')
        
        # Get current store fill percentage
        store_fill_info = self._get_store_fill_info(store_capacity)
        fill_percentage = store_fill_info['fill_percentage']
        
        # Calculate commission rate based on capacity
        if fill_percentage <= min_capacity:
            return min_rate / 100.0  # Convert from percentage to decimal
        elif fill_percentage >= max_capacity:
            return max_rate / 100.0  # Convert from percentage to decimal
        else:
            # Linear interpolation between min and max rates
            ratio = (fill_percentage - min_capacity) / (max_capacity - min_capacity)
            commission_rate = min_rate + (max_rate - min_rate) * ratio
            return commission_rate / 100.0  # Convert from percentage to decimal
    
    def calculate_commission(self, store_price):
        """Calculate commission amount for given store price"""
        commission_rate = self.get_current_commission_rate()
        return store_price * commission_rate
    
    def calculate_payout(self, store_price):
        """Calculate consignor payout for given store price"""
        commission_rate = self.get_current_commission_rate()
        return store_price * (1 - commission_rate)
    
    def _get_config_value(self, config_key):
        """Get config value via API - throws error if not found"""
        value = self.api_client.get_config_value(config_key, None)
        if value is None:
            raise ValueError(f"Required configuration key '{config_key}' not found")
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Configuration key '{config_key}' has invalid value: '{value}'")
    
    def _get_store_fill_info(self, store_capacity):
        """Get store fill information"""
        # Get all records via API
        response = requests.get(f"{self.api_client.base_url}/records?limit=1000")
        if response.status_code == 200:
            data = response.json()
            total_inventory = len(data.get('records', []))
        else:
            total_inventory = 0
        
        fill_fraction = total_inventory / store_capacity if store_capacity > 0 else 0
        fill_percentage = fill_fraction * 100
        
        return {
            'total_inventory': total_inventory,
            'store_capacity': store_capacity,
            'fill_fraction': fill_fraction,
            'fill_percentage': fill_percentage
        }