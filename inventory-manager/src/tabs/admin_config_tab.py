import streamlit as st
import pandas as pd
from datetime import datetime

class AdminConfigTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("⚙️ Admin Configuration")
        
        user = st.session_state.get('user', {})
        if user.get('role') != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view configuration.")
            return
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            self._render_config_editor()
        
        with col2:
            self._render_user_creation()
            
        st.subheader("👥 User Management")
        self._render_user_management()
    
    def _render_config_editor(self):
        st.subheader("Configuration Values")
        
        config_data = self._get_all_config_values()
        
        if not config_data:
            st.info("No configuration values found. Add some configuration values first.")
            return
        
        config_df = pd.DataFrame(config_data)
        
        st.write("**Current Configuration:**")
        
        edited_df = st.data_editor(
            config_df,
            column_config={
                "config_key": st.column_config.TextColumn("Key", disabled=True),
                "config_value": st.column_config.TextColumn("Value"),
                "description": st.column_config.TextColumn("Description", disabled=True)
            },
            hide_index=True,
            width='stretch',
            key="config_editor"
        )
        
        if not edited_df.equals(config_df):
            changes_made = False
            for _, row in edited_df.iterrows():
                original_row = config_df[config_df['config_key'] == row['config_key']].iloc[0]
                if original_row['config_value'] != row['config_value']:
                    success = st.session_state.db_manager.set_config_value(
                        row['config_key'], 
                        row['config_value']
                    )
                    if success:
                        changes_made = True
                        st.success(f"✅ Updated {row['config_key']}")
                    else:
                        st.error(f"❌ Failed to update {row['config_key']}")
            
            if changes_made:
                st.rerun()
    
    def _render_user_creation(self):
        st.subheader("Create New User")
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                username = st.text_input("Username", placeholder="Enter username")
                email = st.text_input("Email", placeholder="Enter email address")
                full_name = st.text_input("Full Name", placeholder="Enter full name")
            
            with col2:
                password = st.text_input("Password", type="password", placeholder="Enter password")
                confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm password")
                role = st.selectbox("Role", options=["consignor", "admin"])
            
            if st.form_submit_button("➕ Create User", width='stretch'):
                if not all([username, email, password, confirm_password]):
                    st.error("Please fill all required fields")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif len(password) < 8:
                    st.error("Password must be at least 8 characters long")
                else:
                    # Check if user already exists
                    users_df = st.session_state.db_manager.get_all_users()
                    if not users_df.empty:
                        existing_users = users_df[users_df['username'] == username]
                        if not existing_users.empty:
                            st.error(f"Username '{username}' already exists")
                            return
                    
                    # Create user via API
                    success = self._create_user_api(username, email, password, role, full_name)
                    if success:
                        st.success(f"✅ User '{username}' created successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to create user")
    
    def _create_user_api(self, username, email, password, role, full_name):
        """Create a new user via API"""
        try:
            result = st.session_state.db_manager._make_request(
                'POST', 
                '/users',
                json={
                    'username': username,
                    'email': email,
                    'password': password,
                    'role': role,
                    'full_name': full_name
                }
            )
            
            success = result is not None and result.get('status') == 'success'
            return success
        except Exception as e:
            st.error(f"Error creating user: {e}")
            return False

    def _get_all_config_values(self):
        config_data = []
        
        known_config_keys = [
            'SHIPPING_COST', 'MIN_STORE_PRICE',
            'STORE_PRICE_ESTIMATED_MULTIPLIER', 'STORE_PRICE_MINIMUM', 
            'DEFAULT_COMMISSION_RATE', 'DEFAULT_STORE_RETURN_DAYS',
            'CUSTOMER_RETURN_DAYS', 'CONSIGNOR_PICKUP_DAYS', 'STORE_CAPACITY'
        ]
        
        for config_key in known_config_keys:
            config_value = st.session_state.db_manager.get_config_value(config_key)
            if config_value is not None:
                config_data.append({
                    'config_key': config_key,
                    'config_value': config_value,
                    'description': self._get_config_description(config_key)
                })
        
        return config_data

    def _get_config_description(self, config_key):
        config_descriptions = {
            'SHIPPING_COST': 'Default shipping cost for eBay price calculations ($)',
            'MIN_STORE_PRICE': 'Minimum price for any record in the store ($)',
            'STORE_PRICE_ESTIMATED_MULTIPLIER': 'Multiplier for estimated price when calculating store price',
            'STORE_PRICE_MINIMUM': 'Absolute minimum store price regardless of calculations ($)',
            'DEFAULT_COMMISSION_RATE': 'Default commission rate for new consignment records (0.0-1.0)',
            'DEFAULT_STORE_RETURN_DAYS': 'Default number of days before unsold consignment records are returned',
            'CUSTOMER_RETURN_DAYS': 'Number of days before sold consignment records can be paid out',
            'CONSIGNOR_PICKUP_DAYS': 'Number of days consignors have to pick up returned records',
            'STORE_CAPACITY': 'Maximum number of records the store can hold'
        }
        return config_descriptions.get(config_key, 'No description available')

    def _render_user_management(self):
        users_df = st.session_state.db_manager.get_all_users()

        if not users_df.empty:
            st.write("**Reset User Passwords:**")
            
            for _, user in users_df.iterrows():
                with st.expander(f"User: {user['username']} ({user['full_name'] or 'No name'}) - {user['role']}", expanded=False):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        new_password = st.text_input(
                            "New Password",
                            type="password",
                            placeholder="Enter new password",
                            key=f"new_password_{user['id']}"
                        )
                    
                    with col2:
                        if st.button("Reset Password", key=f"reset_btn_{user['id']}", width='stretch'):
                            if new_password:
                                if len(new_password) < 8:
                                    st.error("Password must be at least 8 characters long")
                                elif not any(c.isupper() for c in new_password):
                                    st.error("Password must contain at least one uppercase letter")
                                elif not any(c.islower() for c in new_password):
                                    st.error("Password must contain at least one lowercase letter")
                                elif not any(c.isdigit() for c in new_password):
                                    st.error("Password must contain at least one number")
                                else:
                                    success = st.session_state.db_manager._make_request(
                                        'POST', 
                                        f"/users/{user['id']}/reset-password",
                                        json={'new_password': new_password}
                                    )
                                    
                                    if success and success.get('status') == 'success':
                                        st.success(f"✅ Password reset for {user['username']}")
                                        st.rerun()
                                    else:
                                        error_msg = success.get('error', 'Unknown error') if success else 'API request failed'
                                        st.error(f"❌ Failed to reset password: {error_msg}")
                            else:
                                st.error("Please enter a new password")
        else:
            st.info("No users found")