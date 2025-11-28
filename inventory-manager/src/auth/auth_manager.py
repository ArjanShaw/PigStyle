# FILE: inventory-manager/src/auth/auth_manager.py
import streamlit as st
import hashlib
import secrets
import time
from datetime import datetime, timedelta
import re
from typing import Optional, Dict, Any
import os
import requests

class AuthManager:
    def __init__(self, api_base_url: str = None):
        if api_base_url is None:
            # Get from environment or use default
            api_base_url = os.getenv('PYTHONANYWHERE_API_URL', 'https://arjanshaw.pythonanywhere.com')
        
        self.api_base_url = api_base_url
        self.session = requests.Session()
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make API request with error handling"""
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            if 200 <= response.status_code < 300:
                return response.json()
            else:
                print(f"API Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            print(f"Network error: {str(e)}")
            return None
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256 with salt - FOR LOCAL USE ONLY"""
        salt = secrets.token_hex(16)
        return f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash - FOR LOCAL USE ONLY"""
        try:
            if not password_hash or '$' not in password_hash:
                return False
                
            salt, hash_value = password_hash.split('$')
            return hashlib.sha256((salt + password).encode()).hexdigest() == hash_value
        except:
            return False
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _validate_password_strength(self, password: str) -> tuple[bool, str]:
        """Validate password strength"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r'[0-9]', password):
            return False, "Password must contain at least one number"
        return True, "Password is strong"
    
    def authenticate_user(self, username: str, password: str, ip_address: str = "", user_agent: str = "") -> tuple[bool, str, Optional[Dict]]:
        """Authenticate user via API"""
        # Use the debug endpoint to verify login
        # First, get user by username/email to find user_id
        users_result = self._make_request('GET', '/users')
        if not users_result or 'users' not in users_result:
            return False, "Unable to access user database", None
        
        # Find user by username or email
        user_data = None
        user_id = None
        
        for user in users_result['users']:
            if user['username'] == username or user['email'] == username:
                user_data = user
                user_id = user['id']
                break
        
        if not user_data:
            return False, "Invalid username or password", None
        
        # Now verify the password using the debug endpoint
        verify_result = self._make_request(
            'POST', 
            f'/debug/verify-login/{user_id}',
            json={'password': password}
        )
        
        if not verify_result:
            return False, "Authentication service unavailable", None
        
        if verify_result.get('login_valid'):
            # Successful login - create session info
            user_info = {
                'id': user_id,
                'username': user_data['username'],
                'email': user_data['email'],
                'role': user_data['role'],
                'full_name': user_data.get('full_name', ''),
                'session_token': secrets.token_urlsafe(32)  # Generate local session token
            }
            
            return True, "Login successful", user_info
        else:
            return False, "Invalid password", None
    
    def validate_session(self, session_token: str) -> tuple[bool, Optional[Dict]]:
        """Validate session token - for now, just check if user exists in session state"""
        # This is a simplified session validation for Streamlit
        # In a production app, you'd want more robust session management
        if hasattr(st.session_state, 'user') and st.session_state.user:
            return True, st.session_state.user
        return False, None
    
    def logout_user(self, session_token: str):
        """Invalidate user session - clear session state"""
        # Clear session state
        if hasattr(st.session_state, 'user'):
            st.session_state.user = None
        if hasattr(st.session_state, 'authenticated'):
            st.session_state.authenticated = False
        if hasattr(st.session_state, 'session_token'):
            st.session_state.session_token = None
    
    def change_password(self, user_id: int, current_password: str, new_password: str) -> tuple[bool, str]:
        """Change user password via API"""
        # Validate new password strength
        is_strong, message = self._validate_password_strength(new_password)
        if not is_strong:
            return False, f"New password is weak: {message}"
        
        # Use API to change password
        result = self._make_request(
            'POST', 
            f'/users/{user_id}/change-password',
            json={
                'current_password': current_password,
                'new_password': new_password
            }
        )
        
        if result and result.get('status') == 'success':
            return True, "Password changed successfully"
        else:
            error_msg = result.get('error', 'Unknown error') if result else 'API request failed'
            return False, f"Error changing password: {error_msg}"
    
    def reset_password(self, admin_user_id: int, target_user_id: int, new_password: str) -> tuple[bool, str]:
        """Admin reset user password via API"""
        # Validate new password strength
        is_strong, message = self._validate_password_strength(new_password)
        if not is_strong:
            return False, f"New password is weak: {message}"
        
        # Use API to reset password
        result = self._make_request(
            'POST', 
            f'/users/{target_user_id}/reset-password',
            json={'new_password': new_password}
        )
        
        if result and result.get('status') == 'success':
            return True, "Password reset successfully"
        else:
            error_msg = result.get('error', 'Unknown error') if result else 'API request failed'
            return False, f"Error resetting password: {error_msg}"
    
    def get_all_users(self):
        """Get all users via API"""
        result = self._make_request('GET', '/users')
        if result and 'users' in result:
            return result['users']
        return []
    
    def create_user(self, username: str, email: str, password: str, role: str = "consignor", full_name: str = "", phone: str = "", address: str = "") -> tuple[bool, str]:
        """Create a new user account - NOT IMPLEMENTED IN API YET"""
        # This would require a new API endpoint for user creation
        return False, "User creation not available via API"
    
    def update_user_role(self, user_id: int, new_role: str, admin_id: int) -> tuple[bool, str]:
        """Update user role - NOT IMPLEMENTED IN API YET"""
        # This would require a new API endpoint for role updates
        return False, "Role updates not available via API"