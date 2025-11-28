import streamlit as st
import pandas as pd
from datetime import datetime

class AdminConfigTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("⚙️ Admin Configuration")
        
        # Check if user is admin
        user = st.session_state.get('user', {})
        if user.get('role') != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view configuration.")
            return
        
        # Main configuration interface
        col1, col2 = st.columns([2, 1])
        
        with col1:
            self._render_config_editor()
        
        with col2:
            self._render_config_help()
            
        # User Management Section
        st.subheader("👥 User Management")
        self._render_user_management()
    
    def _render_config_editor(self):
        """Render the configuration editor"""
        st.subheader("Configuration Values")
        
        # Get all current configuration
        config_data = self._get_all_config_values()
        
        if not config_data:
            st.info("No configuration values found. Add some configuration values first.")
            
            # Quick add default configs
            if st.button("➕ Add Default Configuration", use_container_width=True):
                self._add_default_configurations()
                st.rerun()
            return
        
        # Create editable dataframe
        config_df = pd.DataFrame(config_data)
        
        # Display current values
        st.write("**Current Configuration:**")
        
        edited_df = st.data_editor(
            config_df,
            column_config={
                "config_key": st.column_config.TextColumn("Key", disabled=True),
                "config_value": st.column_config.TextColumn("Value"),
                "description": st.column_config.TextColumn("Description", disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key="config_editor"
        )
        
        # Save changes
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
        
        # Add new configuration key
        st.subheader("Add New Configuration")
        with st.form("add_config_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_key = st.text_input("Configuration Key", placeholder="e.g., NEW_SETTING")
            with col2:
                new_value = st.text_input("Configuration Value", placeholder="e.g., 100")
            
            new_description = st.text_area("Description", placeholder="What does this setting control?")
            
            if st.form_submit_button("➕ Add Configuration", use_container_width=True):
                if new_key and new_value:
                    success = st.session_state.db_manager.set_config_value(new_key, new_value)
                    if success:
                        st.success(f"✅ Added configuration key: {new_key}")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to add configuration key: {new_key}")
                else:
                    st.error("Please provide both key and value")
    
    def _render_config_help(self):
        """Render configuration help and descriptions"""
        st.subheader("Configuration Help")
        
        config_descriptions = {
            'SHIPPING_COST': 'Default shipping cost for eBay price calculations ($)',
            'MIN_STORE_PRICE': 'Minimum price for any record in the store ($)',
            'STORE_PRICE_LOWEST_MULTIPLIER': 'Multiplier for lowest price when calculating store price',
            'STORE_PRICE_ESTIMATED_MULTIPLIER': 'Multiplier for estimated price when calculating store price',
            'STORE_PRICE_MINIMUM': 'Absolute minimum store price regardless of calculations ($)',
            'DEFAULT_COMMISSION_RATE': 'Default commission rate for new consignment records (0.0-1.0)',
            'DEFAULT_STORE_RETURN_DAYS': 'Default number of days before unsold consignment records are returned',
            'CUSTOMER_RETURN_DAYS': 'Number of days before sold consignment records can be paid out',
            'CONSIGNOR_PICKUP_DAYS': 'Number of days consignors have to pick up returned records',
            'STORE_CAPACITY': 'Maximum number of records the store can hold'
        }
        
        for key, description in config_descriptions.items():
            with st.expander(f"**{key}**", expanded=False):
                st.write(description)
        
        st.subheader("Quick Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Reset to Defaults", use_container_width=True):
                self._reset_to_defaults()
        
        with col2:
            if st.button("🗑️ Clear All Config", use_container_width=True, type="secondary"):
                if st.checkbox("I understand this will delete ALL configuration"):
                    if st.button("CONFIRM DELETE ALL CONFIG", type="primary", use_container_width=True):
                        self._clear_all_config()
                        st.rerun()
    
    def _get_all_config_values(self):
        """Get all configuration values by checking each known config key individually"""
        try:
            config_data = []
            
            # List of known configuration keys to check
            known_config_keys = [
                'SHIPPING_COST', 'MIN_STORE_PRICE', 'STORE_PRICE_LOWEST_MULTIPLIER',
                'STORE_PRICE_ESTIMATED_MULTIPLIER', 'STORE_PRICE_MINIMUM', 
                'DEFAULT_COMMISSION_RATE', 'DEFAULT_STORE_RETURN_DAYS',
                'CUSTOMER_RETURN_DAYS', 'CONSIGNOR_PICKUP_DAYS', 'STORE_CAPACITY'
            ]
            
            # Check each config key individually
            for config_key in known_config_keys:
                config_value = st.session_state.db_manager.get_config_value(config_key)
                if config_value is not None:
                    config_data.append({
                        'config_key': config_key,
                        'config_value': config_value,
                        'description': self._get_config_description(config_key)
                    })
            
            return config_data
            
        except Exception as e:
            st.error(f"Error loading configuration: {e}")
            return []

    def _get_config_description(self, config_key):
        """Get description for configuration key"""
        config_descriptions = {
            'SHIPPING_COST': 'Default shipping cost for eBay price calculations ($)',
            'MIN_STORE_PRICE': 'Minimum price for any record in the store ($)',
            'STORE_PRICE_LOWEST_MULTIPLIER': 'Multiplier for lowest price when calculating store price',
            'STORE_PRICE_ESTIMATED_MULTIPLIER': 'Multiplier for estimated price when calculating store price',
            'STORE_PRICE_MINIMUM': 'Absolute minimum store price regardless of calculations ($)',
            'DEFAULT_COMMISSION_RATE': 'Default commission rate for new consignment records (0.0-1.0)',
            'DEFAULT_STORE_RETURN_DAYS': 'Default number of days before unsold consignment records are returned',
            'CUSTOMER_RETURN_DAYS': 'Number of days before sold consignment records can be paid out',
            'CONSIGNOR_PICKUP_DAYS': 'Number of days consignors have to pick up returned records',
            'STORE_CAPACITY': 'Maximum number of records the store can hold'
        }
        return config_descriptions.get(config_key, 'No description available')

    def _add_default_configurations(self):
        """Add default configuration values"""
        default_configs = [
            ('SHIPPING_COST', '5.72'),
            ('MIN_STORE_PRICE', '1.99'),
            ('STORE_PRICE_LOWEST_MULTIPLIER', '1.1'),
            ('STORE_PRICE_ESTIMATED_MULTIPLIER', '0.9'),
            ('STORE_PRICE_MINIMUM', '4.99'),
            ('DEFAULT_COMMISSION_RATE', '0.50'),
            ('DEFAULT_STORE_RETURN_DAYS', '90'),
            ('CUSTOMER_RETURN_DAYS', '30'),
            ('CONSIGNOR_PICKUP_DAYS', '30'),
            ('STORE_CAPACITY', '1000')
        ]
        
        added_count = 0
        for config_key, config_value in default_configs:
            success = st.session_state.db_manager.set_config_value(config_key, config_value)
            if success:
                added_count += 1
        
        if added_count > 0:
            st.success(f"✅ Added {added_count} default configuration values!")
        else:
            st.error("❌ Failed to add default configuration values")

    def _reset_to_defaults(self):
        """Reset configuration to default values using API"""
        default_configs = [
            ('SHIPPING_COST', '5.72'),
            ('MIN_STORE_PRICE', '1.99'),
            ('STORE_PRICE_LOWEST_MULTIPLIER', '1.1'),
            ('STORE_PRICE_ESTIMATED_MULTIPLIER', '0.9'),
            ('STORE_PRICE_MINIMUM', '4.99'),
            ('DEFAULT_COMMISSION_RATE', '0.50'),
            ('DEFAULT_STORE_RETURN_DAYS', '90'),
            ('CUSTOMER_RETURN_DAYS', '30'),
            ('CONSIGNOR_PICKUP_DAYS', '30'),
            ('STORE_CAPACITY', '1000')
        ]
        
        updated_count = 0
        for config_key, config_value in default_configs:
            success = st.session_state.db_manager.set_config_value(config_key, config_value)
            if success:
                updated_count += 1
        
        if updated_count > 0:
            st.success(f"✅ Reset {updated_count} configuration values to defaults!")
            st.rerun()
        else:
            st.error("❌ Failed to reset configuration values")

    def _clear_all_config(self):
        """Clear all configuration values"""
        # This would require a bulk delete endpoint which we don't have
        # For now, we'll reset to defaults
        st.info("Resetting all configuration to defaults...")
        self._reset_to_defaults()

    def _render_user_management(self):
        """Render user management section with password reset functionality"""
        # Get all users
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
                        if st.button("Reset Password", key=f"reset_btn_{user['id']}", use_container_width=True):
                            if new_password:
                                # Validate password strength
                                if len(new_password) < 8:
                                    st.error("Password must be at least 8 characters long")
                                elif not any(c.isupper() for c in new_password):
                                    st.error("Password must contain at least one uppercase letter")
                                elif not any(c.islower() for c in new_password):
                                    st.error("Password must contain at least one lowercase letter")
                                elif not any(c.isdigit() for c in new_password):
                                    st.error("Password must contain at least one number")
                                else:
                                    # Call API to reset password
                                    success = st.session_state.db_manager._make_request(
                                        'POST', 
                                        f"/users/{user['id']}/reset-password",
                                        json={'new_password': new_password}
                                    )
                                    
                                    if success and success.get('status') == 'success':
                                        st.success(f"✅ Password reset for {user['username']}")
                                        # Clear the password field
                                        st.rerun()
                                    else:
                                        error_msg = success.get('error', 'Unknown error') if success else 'API request failed'
                                        st.error(f"❌ Failed to reset password: {error_msg}")
                            else:
                                st.error("Please enter a new password")
        else:
            st.info("No users found")