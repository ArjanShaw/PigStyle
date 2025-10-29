import streamlit as st
from datetime import datetime
import json
from pathlib import Path

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
        
        # Add manual JSON rebuild test
        st.subheader("🔄 Gallery JSON Test")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Manual JSON Rebuild", use_container_width=True):
                if st.session_state.get('gallery_json_manager'):
                    try:
                        with st.spinner("Rebuilding gallery JSON..."):
                            success = st.session_state.gallery_json_manager.trigger_rebuild(async_mode=False)
                        if success:
                            st.success("✅ Gallery JSON rebuilt successfully!")
                        else:
                            st.error("❌ Gallery JSON rebuild failed")
                    except Exception as e:
                        st.error(f"❌ Gallery JSON rebuild error: {str(e)}")
                        # Show full traceback in expander
                        import traceback
                        with st.expander("View full error details"):
                            st.code(traceback.format_exc())
                else:
                    st.error("Gallery JSON manager not initialized")
        
        with col2:
            if st.session_state.get('gallery_json_manager'):
                status = st.session_state.gallery_json_manager.get_rebuild_status()
                st.write(f"**Status:** {'Rebuilding...' if status['in_progress'] else 'Ready'}")
                json_path = st.session_state.gallery_json_manager.get_json_path()
                st.write(f"**JSON Path:** `{json_path}`")
        
        # GitHub Sync Section
        st.subheader("🔄 GitHub Sync")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Manual GitHub Sync", use_container_width=True):
                if hasattr(st.session_state, 'github_sync_handler'):
                    with st.spinner("Syncing with GitHub..."):
                        success, message = st.session_state.github_sync_handler.trigger_sync()
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
                else:
                    st.error("GitHub sync handler not initialized")
        
        with col2:
            if hasattr(st.session_state, 'github_sync_handler'):
                status = st.session_state.github_sync_handler.get_sync_status()
                st.write(f"**Repo:** `{status['repo_path']}`")
                st.write(f"**Script:** {'✅ Found' if status['script_exists'] else '❌ Missing'}")
                st.write(f"**Changes pending:** {'✅ Yes' if status['has_changes'] else '❌ No'}")
                st.write(f"**Last commit:** {status['last_commit']}")
        
        # Check if JSON file exists using the manager's path
        if st.session_state.get('gallery_json_manager'):
            json_path = Path(st.session_state.gallery_json_manager.get_json_path())
            if json_path.exists():
                try:
                    with open(json_path, 'r') as f:
                        data = json.load(f)
                        st.success(f"✅ JSON file exists: {data['meta']['total_records']} records")
                        st.write(f"Last updated: {data['meta']['last_updated']}")
                except Exception as e:
                    st.error(f"❌ Error reading JSON: {e}")
            else:
                st.warning("⚠️ JSON file not found yet")
        
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