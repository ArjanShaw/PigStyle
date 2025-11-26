import streamlit as st
from typing import Optional, Dict, Any

class SessionManager:
    """Manage user sessions in Streamlit"""
    
    def __init__(self, auth_manager):
        self.auth_manager = auth_manager
        
    def initialize_session_state(self):
        """Initialize session state variables"""
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'session_token' not in st.session_state:
            st.session_state.session_token = None
    
    def check_existing_session(self) -> bool:
        """Check for existing valid session"""
        self.initialize_session_state()
        
        if st.session_state.authenticated and st.session_state.session_token:
            # Validate existing session
            is_valid, user_info = self.auth_manager.validate_session(st.session_state.session_token)
            if is_valid:
                st.session_state.user = user_info
                return True
            else:
                # Session expired or invalid
                self.logout()
        
        # Check for session token in query params (for remember me functionality)
        query_params = st.experimental_get_query_params()
        if 'token' in query_params:
            token = query_params['token'][0]
            is_valid, user_info = self.auth_manager.validate_session(token)
            if is_valid:
                st.session_state.session_token = token
                st.session_state.user = user_info
                st.session_state.authenticated = True
                return True
        
        return False
    
    def login(self, username: str, password: str, remember_me: bool = False) -> tuple[bool, str]:
        """Authenticate user and create session"""
        # Get client info for logging
        try:
            import requests
            ip_address = requests.get('https://api.ipify.org').text
        except:
            ip_address = "unknown"
        
        user_agent = "Streamlit App"  # Simplified for Streamlit Cloud
        
        success, message, user_info = self.auth_manager.authenticate_user(
            username, password, ip_address, user_agent
        )
        
        if success and user_info:
            st.session_state.authenticated = True
            st.session_state.user = user_info
            st.session_state.session_token = user_info['session_token']
            
            # Set query param for "remember me" functionality
            if remember_me:
                st.experimental_set_query_params(token=user_info['session_token'])
            
            return True, message
        else:
            return False, message
    
    def logout(self):
        """Logout user and clear session"""
        if st.session_state.session_token:
            self.auth_manager.logout_user(st.session_state.session_token)
        
        # Clear session state
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.session_token = None
        
        # Clear query params
        st.experimental_set_query_params()
        
        # Force rerun to show login page
        st.rerun()
    
    def get_current_user(self) -> Optional[Dict]:
        """Get current user information"""
        return st.session_state.user if st.session_state.authenticated else None
    
    def change_password(self, current_password: str, new_password: str) -> tuple[bool, str]:
        """Change current user's password"""
        if not st.session_state.authenticated or not st.session_state.user:
            return False, "Not authenticated"
        
        user_id = st.session_state.user['id']
        return self.auth_manager.change_password(user_id, current_password, new_password)
    
    def require_auth(self):
        """Decorator to require authentication for functions"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                if not st.session_state.authenticated:
                    st.error("Please log in to access this feature")
                    return None
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_role(self, required_roles: list):
        """Decorator to require specific roles"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                if not st.session_state.authenticated:
                    st.error("Please log in to access this feature")
                    return None
                
                user_role = st.session_state.user.get('role', 'viewer')
                if user_role not in required_roles:
                    st.error(f"Access denied. Required roles: {', '.join(required_roles)}")
                    return None
                
                return func(*args, **kwargs)
            return wrapper
        return decorator