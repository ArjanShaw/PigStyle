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
        
        self._render_config_editor()
            
        st.subheader("👥 User Management")
        self._render_user_creation()
        self._render_user_management()
        
        st.subheader("📧 Email Configuration")
        self._render_email_config()
    
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

    def _render_email_config(self):
        """Render email configuration section"""
        st.write("**Email Service Settings**")
        
        # Note: In production, these would be stored in app_config or secrets
        # For now, show environment variables status
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Required Environment Variables:**")
            st.code("""
            SMTP_SERVER=smtp.gmail.com
            SMTP_PORT=587
            SMTP_USERNAME=your-email@gmail.com
            SMTP_PASSWORD=your-app-password
            FROM_EMAIL=noreply@pigstylerecords.com
            """)
        
        with col2:
            st.write("**Current Status:**")
            
            import os
            env_vars = {
                'SMTP_SERVER': os.getenv('SMTP_SERVER'),
                'SMTP_PORT': os.getenv('SMTP_PORT'),
                'SMTP_USERNAME': os.getenv('SMTP_USERNAME'),
                'SMTP_PASSWORD': '✓ Set' if os.getenv('SMTP_PASSWORD') else '✗ Missing',
                'FROM_EMAIL': os.getenv('FROM_EMAIL', 'noreply@pigstylerecords.com')
            }
            
            for key, value in env_vars.items():
                status = "✅" if value and 'Missing' not in str(value) else "❌"
                st.write(f"{status} {key}: {value or 'Not set'}")
            
            if all(v and 'Missing' not in str(v) for v in env_vars.values()):
                st.success("✅ Email service is configured!")
            else:
                st.warning("⚠️ Email service requires configuration")

    def _get_all_config_values(self):
        config_data = []
        
        # Get all config from database
        all_config = st.session_state.db_manager.get_all_config()
        
        # Check what type of data we got back
        if isinstance(all_config, list):
            # It's a list of dictionaries
            for config in all_config:
                if isinstance(config, dict):
                    config_data.append({
                        'config_key': config.get('config_key'),
                        'config_value': config.get('config_value'),
                        'description': config.get('description', 'No description available')
                    })
                elif isinstance(config, str):
                    # It might be a string representation, try to parse it
                    try:
                        # Try to extract key-value pairs from string
                        if '=' in config:
                            parts = config.split('=', 1)
                            config_data.append({
                                'config_key': parts[0].strip(),
                                'config_value': parts[1].strip(),
                                'description': 'Parsed from string'
                            })
                    except:
                        continue
        elif isinstance(all_config, dict):
            # It's a dictionary
            for key, value in all_config.items():
                config_data.append({
                    'config_key': key,
                    'config_value': str(value),
                    'description': 'From dictionary'
                })
        else:
            # Fallback to known config keys
            known_config_keys = [
                'SHIPPING_COST', 'MIN_STORE_PRICE',
                'STORE_PRICE_ESTIMATED_MULTIPLIER', 'STORE_PRICE_MINIMUM', 
                'DEFAULT_COMMISSION_RATE', 'DEFAULT_STORE_RETURN_DAYS',
                'CUSTOMER_RETURN_DAYS', 'CONSIGNOR_PICKUP_DAYS', 'STORE_CAPACITY',
                'MAX_PRICE_TO_ADV_RATIO', 'COMMISSION_MIN_RATE', 'COMMISSION_MIN_CAPACITY',
                'COMMISSION_MAX_RATE', 'COMMISSION_MAX_CAPACITY', 'COMMISSION_STORE_CREDIT_BONUS',
                'PAYOUT_MINIMUM_AMOUNT', 'CONSIGNMENT_TOTAL_DAYS', 'CONSIGNMENT_FULL_PRICE_DAYS',
                'CONSIGNMENT_DISCOUNT_DAYS', 'DISCOUNT_PERCENTAGE', 'EMAIL_NOTIFICATION_DAYS',
                'PAYOUT_FREQUENCY_DAYS'
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
            'STORE_CAPACITY': 'Maximum number of records the store can hold',
            'MAX_PRICE_TO_ADV_RATIO': 'Maximum allowed price multiplier (user can enter up to this ratio times advised price)',
            'COMMISSION_MIN_RATE': 'Minimum commission rate (percentage) at low capacity',
            'COMMISSION_MIN_CAPACITY': 'Capacity threshold (percentage) for minimum commission rate',
            'COMMISSION_MAX_RATE': 'Maximum commission rate (percentage) at high capacity',
            'COMMISSION_MAX_CAPACITY': 'Capacity threshold (percentage) for maximum commission rate',
            'COMMISSION_STORE_CREDIT_BONUS': 'Additional commission bonus (percentage) for choosing store credit',
            'PAYOUT_MINIMUM_AMOUNT': 'Minimum balance required to request a payout ($)',
            'CONSIGNMENT_TOTAL_DAYS': 'Total consignment period in days',
            'CONSIGNMENT_FULL_PRICE_DAYS': 'Days items remain at consignor\'s set price',
            'CONSIGNMENT_DISCOUNT_DAYS': 'Days items may be subject to discount after initial period',
            'DISCOUNT_PERCENTAGE': 'Maximum discount percentage after full price period',
            'EMAIL_NOTIFICATION_DAYS': 'Days between email reminders for pickup',
            'PAYOUT_FREQUENCY_DAYS': 'Minimum days between payout requests'
        }
        return config_descriptions.get(config_key, 'No description available')

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

    def _render_user_creation(self):
        st.subheader("Create New User")
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                username = st.text_input("Username", placeholder="Enter username")
                email = st.text_input("Email*", placeholder="Enter email address")
                full_name = st.text_input("Full Name", placeholder="Enter full name")
            
            with col2:
                password = st.text_input("Password*", type="password", placeholder="Enter password")
                confirm_password = st.text_input("Confirm Password*", type="password", placeholder="Confirm password")
                role = st.selectbox("Role", options=["consignor", "admin"])
            
            st.caption("*Email is required for notifications. Password must be at least 8 characters.")
            
            if st.form_submit_button("➕ Create User", width='stretch'):
                if not all([username, email, password, confirm_password]):
                    st.error("Please fill all required fields (*)")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif len(password) < 8:
                    st.error("Password must be at least 8 characters long")
                elif '@' not in email or '.' not in email:
                    st.error("Please enter a valid email address")
                else:
                    # Create user via API
                    success = self._create_user_api(username, email, password, role, full_name)
                    if success:
                        st.success(f"✅ User '{username}' created successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to create user")
    
    def _render_user_management(self):
        users_df = st.session_state.db_manager.get_all_users()

        if not users_df.empty:
            st.write("**Reset User Passwords:**")
            
            for _, user in users_df.iterrows():
                with st.expander(f"User: {user['username']} ({user['full_name'] or 'No name'}) - {user['role']} | Email: {user['email']}", expanded=False):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
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
                    
                    with col3:
                        store_credit = st.number_input(
                            "Store Credit",
                            min_value=0.0,
                            value=float(user.get('store_credit_balance', 0)),
                            step=1.0,
                            key=f"store_credit_{user['id']}"
                        )
                        
                        if st.button("Update Credit", key=f"credit_btn_{user['id']}", width='stretch'):
                            success = st.session_state.db_manager._make_request(
                                'PUT',
                                f"/users/{user['id']}",
                                json={'store_credit_balance': store_credit}
                            )
                            
                            if success and success.get('status') == 'success':
                                st.success(f"✅ Store credit updated for {user['username']}")
                                st.rerun()
        else:
            st.info("No users found")