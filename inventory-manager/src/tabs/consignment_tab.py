import streamlit as st
import pandas as pd
import requests

class CommissionCalculator:
    """Capacity-based commission calculator"""
    
    def __init__(self, api_client):
        self.api_client = api_client
    
    def get_current_commission_rate(self):
        """Get commission rate based ONLY on store capacity"""
        # Get required configuration values - will throw error if any missing
        max_capacity = self._get_config_value('COMMISSION_MAX_CAPACITY')
        min_capacity = self._get_config_value('COMMISSION_MIN_CAPACITY')
        max_rate = self._get_config_value('COMMISSION_MAX_RATE')
        min_rate = self._get_config_value('COMMISSION_MIN_RATE')
        
        # Get current store fill percentage
        store_fill_info = self._get_store_fill_info()
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
    
    def _get_config_value(self, config_key):
        """Get config value via API - throws error if not found"""
        value = self.api_client.get_config_value(config_key, None)
        if value is None:
            raise ValueError(f"Required configuration key '{config_key}' not found")
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Configuration key '{config_key}' has invalid value: '{value}'")
    
    def _get_store_fill_info(self):
        """Get store fill information"""
        store_capacity = self._get_config_value('STORE_CAPACITY')
        
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

class ConsignmentTab:
    def __init__(self):
        # Initialize API client
        self.api_client = APIClient()
        self.commission_calculator = CommissionCalculator(self.api_client)
    
    def render(self):
        st.title("🎵 Consignment Management")
        
        user = st.session_state.get('user', {})
        user_id = user.get('id')
        user_role = user.get('role', 'consignor')
        
        if not user_id:
            st.warning("Please log in to view consignment information.")
            return
        
        # Get consignment records
        if user_role == 'admin':
            response = requests.get(f"{self.api_client.base_url}/records?limit=1000")
        else:
            response = requests.get(f"{self.api_client.base_url}/records/user/{user_id}")
        
        if response.status_code != 200:
            st.error("Error fetching records")
            return
        
        data = response.json()
        if data.get('status') != 'success':
            st.error("Error fetching records")
            return
        
        records = data.get('records', [])
        if not records:
            st.info("No consignment records found.")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Filter only records with consignor_id (consignment items)
        consignment_df = df[df['consignor_id'].notna()].copy()
        
        if consignment_df.empty:
            st.info("No consignment records found (all records are store-owned).")
            return
        
        # Add consignor name for admin view
        if user_role == 'admin':
            consignor_names = {}
            for consignor_id in consignment_df['consignor_id'].unique():
                user_info = self.api_client.get_user(int(consignor_id))
                if user_info:
                    consignor_names[consignor_id] = user_info.get('username', f"ID: {consignor_id}")
            
            consignment_df['consignor'] = consignment_df['consignor_id'].map(consignor_names)
        
        # Get commission rate for each record (from database or calculate if missing)
        consignment_df['commission_rate'] = consignment_df['commission_rate'].fillna(0.0)
        
        # Calculate commission and payout for each record using individual commission rates
        consignment_df['commission'] = consignment_df['store_price'] * consignment_df['commission_rate']
        consignment_df['payout'] = consignment_df['store_price'] - consignment_df['commission']
        
        # Format display columns
        display_df = pd.DataFrame()
        
        if user_role == 'admin':
            display_df['Consignor'] = consignment_df['consignor']
        
        display_df['Artist'] = consignment_df['artist']
        display_df['Title'] = consignment_df['title']
        display_df['Price'] = consignment_df['store_price'].apply(lambda x: f"${x:.2f}")
        display_df['Comm Rate'] = consignment_df['commission_rate'].apply(lambda x: f"{x*100:.1f}%")
        display_df['Commission'] = consignment_df['commission'].apply(lambda x: f"${x:.2f}")
        display_df['Payout'] = consignment_df['payout'].apply(lambda x: f"${x:.2f}")
        
        if 'date_sold' in consignment_df.columns:
            display_df['Status'] = consignment_df['date_sold'].apply(
                lambda x: '✅ Sold' if pd.notna(x) else '🟢 Available'
            )
        
        # Calculate totals
        total_price = consignment_df['store_price'].sum()
        total_commission = consignment_df['commission'].sum()
        total_payout = consignment_df['payout'].sum()
        
        # Display totals
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Value", f"${total_price:.2f}")
        with col2:
            st.metric("Total Commission", f"${total_commission:.2f}")
        with col3:
            st.metric("Total Payout", f"${total_payout:.2f}")
        
        # Display the table
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Consignor': st.column_config.TextColumn('Consignor', width='medium'),
                'Artist': st.column_config.TextColumn('Artist', width='medium'),
                'Title': st.column_config.TextColumn('Title', width='large'),
                'Price': st.column_config.TextColumn('Price', width='small'),
                'Comm Rate': st.column_config.TextColumn('Comm Rate', width='small'),
                'Commission': st.column_config.TextColumn('Commission', width='small'),
                'Payout': st.column_config.TextColumn('Payout', width='small'),
                'Status': st.column_config.TextColumn('Status', width='small')
            }
        )

class APIClient:
    """API client for consignment operations"""
    
    def __init__(self, base_url="https://arjanshaw.pythonanywhere.com"):
        self.base_url = base_url
    
    def get_records_by_user(self, user_id):
        """Get records for specific user via API"""
        try:
            response = requests.get(f"{self.base_url}/records/user/{user_id}")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('records', [])
            return []
        except Exception as e:
            st.error(f"API Error getting user records: {e}")
            return []
    
    def get_config_value(self, config_key, default=None):
        """Get config value via API"""
        try:
            response = requests.get(f"{self.base_url}/config/{config_key}")
            if response.status_code == 200:
                data = response.json()
                return data.get('config_value', default)
            return default
        except Exception as e:
            st.error(f"API Error getting config: {e}")
            return default
    
    def get_user(self, user_id):
        """Get user by ID"""
        try:
            response = requests.get(f"{self.base_url}/users/{user_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"API Error getting user: {e}")
            return None