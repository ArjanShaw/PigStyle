import streamlit as st
import subprocess
import os
from pathlib import Path
from datetime import datetime

class ToolsSyncTab:
    def __init__(self, gallery_json_manager=None, github_sync_handler=None):
        self.gallery_json_manager = gallery_json_manager
        self.github_sync_handler = github_sync_handler
    
    def render(self):
        st.header("🛠️ Tools & Sync")
        
        col1, col2 = st.columns(2)
        
        # Gallery JSON Management
        with col1:
            st.subheader("🔄 Gallery JSON")
            if st.button("🔄 Manual JSON Rebuild", use_container_width=True):
                if self.gallery_json_manager:
                    with st.spinner("Rebuilding gallery JSON..."):
                        success = self.gallery_json_manager.trigger_rebuild(async_mode=False)
                    if success:
                        st.success("✅ Gallery JSON rebuilt successfully!")
                    else:
                        st.error("❌ Gallery JSON rebuild failed")
                else:
                    st.error("Gallery JSON manager not initialized")
            
            if self.gallery_json_manager:
                status = self.gallery_json_manager.get_rebuild_status()
                st.write(f"**Status:** {'Rebuilding...' if status['in_progress'] else 'Ready'}")
                json_path = self.gallery_json_manager.get_json_path()
                st.write(f"**JSON Path:** `{json_path}`")
        
        # GitHub Sync Section
        with col2:
            st.subheader("🔄 GitHub Sync")
            if st.button("🔄 Manual GitHub Sync", use_container_width=True):
                if self.github_sync_handler:
                    with st.spinner("Syncing with GitHub..."):
                        success, message = self.github_sync_handler.trigger_sync()
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")
                else:
                    st.error("GitHub sync handler not initialized")
            
            if self.github_sync_handler:
                status = self.github_sync_handler.get_sync_status()
                st.write(f"**Repo:** `{status['repo_path']}`")
                st.write(f"**Script:** {'✅ Found' if status['script_exists'] else '❌ Missing'}")
                st.write(f"**Changes pending:** {'✅ Yes' if status['has_changes'] else '❌ No'}")
                st.write(f"**Last commit:** {status['last_commit']}")
        
        # Database Management
        st.subheader("🗃️ Database Tools")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Update File Locations", use_container_width=True):
                if hasattr(st.session_state, 'db_manager'):
                    updated_count = st.session_state.db_manager.update_file_at_for_all_records()
                    st.success(f"✅ Updated file locations for {updated_count} records!")
                else:
                    st.error("Database manager not available")
        
        with col2:
            if st.button("🗑️ Clear All Records", use_container_width=True, type="secondary"):
                if hasattr(st.session_state, 'db_manager'):
                    if st.checkbox("I understand this will delete ALL records permanently"):
                        if st.button("CONFIRM DELETE ALL", type="primary"):
                            st.session_state.db_manager.clear_database()
                            st.success("✅ All records deleted!")
                            st.rerun()
        
        # System Information
        st.subheader("📊 System Info")
        if hasattr(st.session_state, 'db_manager'):
            stats = st.session_state.db_manager.get_database_stats()
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", stats['records_count'])
            with col2:
                st.metric("Failed Searches", stats['failed_count'])
            with col3:
                st.metric("Database Path", stats['db_path'])