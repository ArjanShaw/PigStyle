import streamlit as st
import os
from datetime import datetime
import glob

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
        
        # Environment information
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Environment Info")
            st.write(f"**Python Executable:** `{os.sys.executable}`")
            st.write(f"**Working Directory:** `{os.getcwd()}`")
            st.write(f"**Streamlit Version:** `{st.__version__}`")
            
            # Check for .env file
            env_files = glob.glob("*.env") + glob.glob(".env")
            if env_files:
                st.success(f"✅ .env file found: {env_files}")
            else:
                st.warning("❌ No .env file found in current directory")
            
            # Check secrets availability
            try:
                if hasattr(st, 'secrets'):
                    secrets_count = len(st.secrets) if st.secrets else 0
                    st.write(f"**Streamlit Secrets:** {secrets_count} keys found")
                    if secrets_count > 0:
                        st.write("Available secrets:", list(st.secrets.keys()))
                else:
                    st.write("**Streamlit Secrets:** Not available")
            except Exception as e:
                st.error(f"Error checking secrets: {e}")
        
        with col2:
            st.subheader("Database Info")
            if hasattr(st.session_state, 'db_manager'):
                db_manager = st.session_state.db_manager
                st.write(f"**Database Path:** `{db_manager.db_path}`")
                st.write(f"**Database Exists:** `{os.path.exists(db_manager.db_path)}`")
                
                try:
                    conn = db_manager._get_connection()
                    cursor = conn.cursor()
                    
                    # Get table info
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    st.write(f"**Tables:** {[table[0] for table in tables]}")
                    
                    # Get record count
                    cursor.execute("SELECT COUNT(*) FROM records")
                    record_count = cursor.fetchone()[0]
                    st.write(f"**Total Records:** {record_count}")
                    
                    conn.close()
                except Exception as e:
                    st.error(f"Error querying database: {e}")
            else:
                st.error("Database manager not initialized")
        
        # Log entries
        st.subheader("Live Logs")
        
        # Clear logs button
        if st.button("Clear Logs"):
            self.log_entries = []
            st.rerun()
        
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