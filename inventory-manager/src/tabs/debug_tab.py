import streamlit as st
from datetime import datetime

class DebugTab:
    def __init__(self):
        # Initialize session state for logs if not exists
        if 'debug_logs' not in st.session_state:
            st.session_state.debug_logs = []
        
    def add_log(self, category, message, data=None):
        """Add a log entry to the debug tab"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = {
            'timestamp': timestamp,
            'category': category,
            'message': message,
            'data': data
        }
        st.session_state.debug_logs.append(log_entry)
        # Keep only last 100 entries to prevent memory issues
        if len(st.session_state.debug_logs) > 100:
            st.session_state.debug_logs.pop(0)
    
    def render(self):
        st.header("🔧 Debug Logs")
        
        if not st.session_state.debug_logs:
            st.info("No debug logs yet. Actions will appear here as they happen.")
            return
        
        # Display logs in reverse chronological order
        for log in reversed(st.session_state.debug_logs):
            with st.container():
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.code(log['timestamp'])
                with col2:
                    st.write(f"**{log['category']}**: {log['message']}")
                
                # Show data in expander if available
                if log['data']:
                    with st.expander("View Request/Response Details"):
                        st.json(log['data'])
                
                st.divider()
        
        # Clear logs button
        if st.button("Clear Logs"):
            st.session_state.debug_logs = []
            st.rerun()