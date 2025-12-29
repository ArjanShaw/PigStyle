import streamlit as st

class CommissionCalculator:
    """Base class for commission calculations"""
    
    def __init__(self, api_client):
        """Initialize with API client"""
        self.api_client = api_client
    
    def get_current_commission_rate(self):
        """Get current commission rate from API"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def calculate_commission(self, store_price):
        """Calculate commission amount for given store price"""
        commission_rate = self.get_current_commission_rate()
        return store_price * commission_rate
    
    def calculate_payout(self, store_price):
        """Calculate consignor payout for given store price"""
        commission_rate = self.get_current_commission_rate()
        return store_price * (1 - commission_rate)