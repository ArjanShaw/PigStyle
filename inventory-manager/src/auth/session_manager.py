import streamlit as st
from typing import Optional, Dict, Any

class SessionManager:
    def __init__(self, auth_manager):
        self.auth_manager = auth_manager
        
    def initialize_session_state(self):
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'session_token' not in st.session_state:
            st.session_state.session_token = None
    
    def check_existing_session(self) -> bool:
        self.initialize_session_state()
        
        if st.session_state.authenticated and st.session_state.session_token:
            is_valid, user_info = self.auth_manager.validate_session(st.session_state.session_token)
            if is_valid:
                st.session_state.user = user_info
                return True
            else:
                self.logout()
        
        return False
    
    def login(self, username: str, password: str, remember_me: bool = False) -> tuple[bool, str]:
        success, message, user_info = self.auth_manager.authenticate_user(username, password)
        
        if success and user_info:
            st.session_state.authenticated = True
            st.session_state.user = user_info
            st.session_state.session_token = user_info['session_token']
            
            return True, message
        else:
            return False, message
    
    def logout(self):
        if hasattr(st.session_state, 'session_token') and st.session_state.session_token:
            self.auth_manager.logout_user(st.session_state.session_token)
        
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.session_token = None
        
        st.rerun()
    
    def get_current_user(self) -> Optional[Dict]:
        return st.session_state.user if hasattr(st.session_state, 'authenticated') and st.session_state.authenticated else None
    
    def change_password(self, current_password: str, new_password: str) -> tuple[bool, str]:
        if not hasattr(st.session_state, 'authenticated') or not st.session_state.authenticated or not st.session_state.user:
            return False, "Not authenticated"
        
        user_id = st.session_state.user['id']
        return self.auth_manager.change_password(user_id, current_password, new_password)
    
    def require_auth(self):
        def decorator(func):
            def wrapper(*args, **kwargs):
                if not hasattr(st.session_state, 'authenticated') or not st.session_state.authenticated:
                    st.error("Please log in to access this feature")
                    return None
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_role(self, required_roles: list):
        def decorator(func):
            def wrapper(*args, **kwargs):
                if not hasattr(st.session_state, 'authenticated') or not st.session_state.authenticated:
                    st.error("Please log in to access this feature")
                    return None
                
                user_role = st.session_state.user.get('role', 'viewer')
                if user_role not in required_roles:
                    st.error(f"Access denied. Required roles: {', '.join(required_roles)}")
                    return None
                
                return func(*args, **kwargs)
            return wrapper
        return decorator