import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import os

class AdminConfigTab:
    def __init__(self):
        self.base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
    
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
                    success = self._set_config_value(row['config_key'], row['config_value'])
                    if success:
                        changes_made = True
                        st.success(f"✅ Updated {row['config_key']}")
                        
                        # Clear config cache when a value changes
                        self._clear_config_cache()
                    else:
                        st.error(f"❌ Failed to update {row['config_key']}")
            
            if changes_made:
                st.rerun()

    def _get_all_config_values(self):
        """Get all config values via API - includes descriptions from database"""
        try:
            response = requests.get(f"{self.base_url}/config")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    configs = data.get('configs', {})
                    
                    # Convert to list for display
                    config_data = []
                    for key, config_info in configs.items():
                        # Handle both old format (string) and new format (dict with value/description)
                        if isinstance(config_info, dict):
                            config_value = config_info.get('value', '')
                            description = config_info.get('description', 'No description available')
                        else:
                            config_value = config_info
                            description = 'No description available'
                        
                        config_data.append({
                            'config_key': key,
                            'config_value': config_value,
                            'description': description
                        })
                    return config_data
            return []
        except Exception as e:
            st.error(f"Error getting config values: {e}")
            return []
    
    def _set_config_value(self, config_key, config_value):
        """Set config value via API"""
        try:
            response = requests.put(
                f"{self.base_url}/config/{config_key}",
                json={'config_value': config_value}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error setting config value: {e}")
            return False

    def _clear_config_cache(self):
        """Clear the config cache when values are updated"""
        if 'config_cache' in st.session_state:
            del st.session_state.config_cache
        
        # Also clear any other cached config-related data
        if hasattr(st, 'session_state'):
            # Clear commission calculator cache if exists
            if hasattr(st.session_state, 'commission_calculator'):
                # Force reload on next access
                pass

    def _render_email_config(self):
        """Render email configuration section"""
        st.write("**Email Service Settings**")
        
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

    def _render_user_creation(self):
        st.subheader("Create New User")
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                username = st.text_input("Username", placeholder="Enter username")
                email = st.text_input("Email*", placeholder="Enter email address")
                full_name = st.text_input("Full Name", placeholder="Enter full name")
                initials = st.text_input("Initials", placeholder="Enter user initials (e.g., AS)", max_chars=5)
            
            with col2:
                password = st.text_input("Password*", type="password", placeholder="Enter password")
                confirm_password = st.text_input("Confirm Password*", type="password", placeholder="Confirm password")
                role = st.selectbox("Role", options=["consignor", "admin"])
            
            st.caption("*Email is required for notifications. Password must be at least 8 characters.")
            st.caption("Initials: 2-3 characters recommended for labeling/tracking purposes")
            
            if st.form_submit_button("➕ Create User", width='stretch'):
                if not all([username, email, password, confirm_password]):
                    st.error("Please fill all required fields (*)")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif len(password) < 8:
                    st.error("Password must be at least 8 characters long")
                elif '@' not in email or '.' not in email:
                    st.error("Please enter a valid email address")
                elif initials and len(initials) > 5:
                    st.error("Initials should be 5 characters or less")
                else:
                    success = self._create_user_api(username, email, password, role, full_name, initials)
                    if success:
                        st.success(f"✅ User '{username}' created successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to create user")
    
    def _render_user_management(self):
        users = self._get_all_users()

        if users:
            st.write("**Manage Users:**")
            
            for user in users:
                with st.expander(f"User: {user['username']} ({user['full_name'] or 'No name'}) - {user['role']} | Email: {user['email']}", expanded=False):
                    # User details editor
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Basic info
                        new_username = st.text_input(
                            "Username",
                            value=user['username'],
                            key=f"username_{user['id']}"
                        )
                        
                        new_email = st.text_input(
                            "Email*",
                            value=user['email'],
                            key=f"email_{user['id']}"
                        )
                        
                        new_full_name = st.text_input(
                            "Full Name",
                            value=user.get('full_name', ''),
                            key=f"full_name_{user['id']}"
                        )
                        
                        new_initials = st.text_input(
                            "Initials*",
                            value=user.get('initials', ''),
                            placeholder="Enter initials (e.g., AS)",
                            max_chars=5,
                            key=f"initials_{user['id']}"
                        )
                        
                        new_role = st.selectbox(
                            "Role",
                            options=["consignor", "admin"],
                            index=0 if user.get('role') == 'consignor' else 1,
                            key=f"role_{user['id']}"
                        )
                    
                    with col2:
                        # Contact info
                        phone = st.text_input(
                            "Phone",
                            value=user.get('phone', ''),
                            key=f"phone_{user['id']}"
                        )
                        
                        address = st.text_area(
                            "Address",
                            value=user.get('address', ''),
                            height=100,
                            key=f"address_{user['id']}"
                        )
                        
                        # Password reset section
                        st.write("**Password Reset**")
                        new_password = st.text_input(
                            "New Password",
                            type="password",
                            placeholder="Enter new password (leave blank to keep current)",
                            key=f"new_password_{user['id']}"
                        )
                        
                        # Store credit
                        store_credit = st.number_input(
                            "Store Credit",
                            min_value=0.0,
                            value=float(user.get('store_credit_balance', 0)),
                            step=1.0,
                            key=f"store_credit_{user['id']}"
                        )
                    
                    # Action buttons
                    col_btn1, col_btn2, col_btn3 = st.columns(3)
                    
                    with col_btn1:
                        if st.button("💾 Update User Info", key=f"update_btn_{user['id']}", width='stretch'):
                            if not new_email:
                                st.error("Email is required")
                            elif new_initials and len(new_initials) > 5:
                                st.error("Initials should be 5 characters or less")
                            else:
                                # Prepare update data
                                update_data = {
                                    'username': new_username,
                                    'email': new_email,
                                    'full_name': new_full_name,
                                    'initials': new_initials,
                                    'role': new_role,
                                    'phone': phone,
                                    'address': address,
                                    'store_credit_balance': store_credit
                                }
                                
                                success = self._update_user_api(user['id'], update_data)
                                if success:
                                    st.success(f"✅ User information updated for {new_username}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Failed to update user information")
                    
                    with col_btn2:
                        if new_password and st.button("🔐 Reset Password", key=f"reset_btn_{user['id']}", width='stretch'):
                            if len(new_password) < 8:
                                st.error("Password must be at least 8 characters long")
                            elif not any(c.isupper() for c in new_password):
                                st.error("Password must contain at least one uppercase letter")
                            elif not any(c.islower() for c in new_password):
                                st.error("Password must contain at least one lowercase letter")
                            elif not any(c.isdigit() for c in new_password):
                                st.error("Password must contain at least one number")
                            else:
                                success = self._reset_password_api(user['id'], new_password)
                                if success:
                                    st.success(f"✅ Password reset for {user['username']}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Failed to reset password")
                        elif not new_password:
                            st.write("")  # Empty space for alignment
                    
                    with col_btn3:
                        if st.button("🚫 Deactivate User", key=f"deactivate_btn_{user['id']}", width='stretch'):
                            success = self._toggle_user_active_api(user['id'], not user.get('is_active', True))
                            if success:
                                status = "deactivated" if user.get('is_active', True) else "activated"
                                st.success(f"✅ User {status} successfully")
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to update user status")
                    
                    # User status info
                    status_col1, status_col2, status_col3 = st.columns(3)
                    with status_col1:
                        st.caption(f"**Status:** {'✅ Active' if user.get('is_active', True) else '❌ Inactive'}")
                    with status_col2:
                        created = user.get('created_at', '')
                        if created:
                            st.caption(f"**Created:** {created}")
                    with status_col3:
                        last_login = user.get('last_login', '')
                        if last_login:
                            st.caption(f"**Last Login:** {last_login}")
        else:
            st.info("No users found")
    
    def _get_all_users(self):
        """Get all users via API"""
        try:
            response = requests.get(f"{self.base_url}/users")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('users', [])
            return []
        except Exception as e:
            st.error(f"Error getting users: {e}")
            return []
    
    def _create_user_api(self, username, email, password, role, full_name, initials=None):
        """Create a new user via API"""
        try:
            user_data = {
                'username': username,
                'email': email,
                'password': password,
                'role': role,
                'full_name': full_name
            }
            
            if initials:
                user_data['initials'] = initials
            
            response = requests.post(
                f"{self.base_url}/users",
                json=user_data
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error creating user: {e}")
            return False
    
    def _reset_password_api(self, user_id, new_password):
        """Reset user password via API"""
        try:
            response = requests.post(
                f"{self.base_url}/users/{user_id}/reset-password",
                json={'new_password': new_password}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error resetting password: {e}")
            return False
    
    def _update_user_api(self, user_id, update_data):
        """Update user information via API"""
        try:
            response = requests.put(
                f"{self.base_url}/users/{user_id}",
                json=update_data
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error updating user: {e}")
            return False
    
    def _toggle_user_active_api(self, user_id, is_active):
        """Toggle user active status via API"""
        try:
            response = requests.put(
                f"{self.base_url}/users/{user_id}/status",
                json={'is_active': is_active}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error updating user status: {e}")
            return False