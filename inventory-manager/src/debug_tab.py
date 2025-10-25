import streamlit as st
from datetime import datetime

class DebugTab:
    def __init__(self):
        self.log_entries = []
        
    def add_log(self, category, message, data=None):
        """Add a log entry to the debug tab"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'category': category,
            'message': message,
            'data': data
        }
        self.log_entries.append(log_entry)
        # Keep only last 100 entries to prevent memory issues
        if len(self.log_entries) > 100:
            self.log_entries.pop(0)
    
    def render(self):
        st.header("🔧 Debug & Logs")
        
        # Display logs in reverse chronological order
        for log in reversed(self.log_entries):
            with st.container():
                col1, col2, col3 = st.columns([1, 2, 3])
                with col1:
                    st.code(log['timestamp'])
                with col2:
                    st.write(f"**{log['category']}**")
                with col3:
                    st.write(log['message'])
                    if log['data']:
                        with st.expander("View Data"):
                            st.json(log['data'])
                st.divider()