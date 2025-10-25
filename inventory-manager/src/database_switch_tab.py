import streamlit as st
import os
import glob
import tempfile
from pathlib import Path

class DatabaseSwitchTab:
    def __init__(self):
        pass
    
    def get_available_databases(self):
        """Get all .db files in current directory and subdirectories"""
        db_files = []
        
        # Check current directory and subdirectories
        patterns = ["*.db", "*/*.db", "*/*/*.db"]
        for pattern in patterns:
            db_files.extend(glob.glob(pattern))
        
        return db_files
    
    def persist_database_path(self, db_path):
        """Persist the database path to file"""
        try:
            with open("current_database.txt", 'w') as f:
                f.write(db_path)
            return True
        except Exception as e:
            st.error(f"Error persisting database path: {e}")
            return False
    
    def render(self):
        st.header("🗃️ Database Manager")
        
        # Current database info
        if hasattr(st.session_state, 'db_manager'):
            current_db = st.session_state.db_manager.db_path
            st.write(f"**Current Database:** `{current_db}`")
            
            # Database statistics
            try:
                conn = st.session_state.db_manager._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM records")
                record_count = cursor.fetchone()[0]
                conn.close()
                st.write(f"**Records in database:** {record_count}")
            except Exception as e:
                st.error(f"Error getting database stats: {e}")
        else:
            st.error("No database manager found")
        
        st.divider()
        
        # Database selection
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Select Existing Database")
            available_dbs = self.get_available_databases()
            
            if available_dbs:
                selected_db = st.selectbox(
                    "Available databases:",
                    available_dbs,
                    index=available_dbs.index(current_db) if current_db in available_dbs else 0
                )
                
                if st.button("Switch to Selected Database", use_container_width=True):
                    try:
                        st.session_state.db_manager = st.session_state.db_manager.__class__(selected_db)
                        if self.persist_database_path(selected_db):
                            st.success(f"✅ Switched to: {selected_db}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error switching database: {e}")
            else:
                st.info("No .db files found in current directory")
        
        with col2:
            st.subheader("Create New")
            new_db_name = st.text_input("New database name:", value="new_inventory.db")
            if st.button("Create Database", use_container_width=True):
                try:
                    if not new_db_name.endswith('.db'):
                        new_db_name += '.db'
                    
                    st.session_state.db_manager = st.session_state.db_manager.__class__(new_db_name)
                    if self.persist_database_path(new_db_name):
                        st.success(f"✅ Created: {new_db_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating database: {e}")
        
        st.divider()
        
        # Database operations
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📤 Upload Database")
            uploaded_file = st.file_uploader(
                "Upload .db file",
                type=['db'],
                help="Upload a SQLite database file"
            )
            
            if uploaded_file is not None:
                try:
                    # Save uploaded file
                    upload_path = uploaded_file.name
                    with open(upload_path, 'wb') as f:
                        f.write(uploaded_file.getbuffer())
                    
                    st.session_state.db_manager = st.session_state.db_manager.__class__(upload_path)
                    if self.persist_database_path(upload_path):
                        st.success(f"✅ Uploaded and loaded: {upload_path}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error uploading database: {e}")
        
        with col2:
            st.subheader("📥 Download Database")
            if st.button("Download Current Database", use_container_width=True):
                try:
                    if os.path.exists(current_db):
                        with open(current_db, 'rb') as f:
                            db_data = f.read()
                        
                        st.download_button(
                            label="⬇️ Download Database File",
                            data=db_data,
                            file_name=os.path.basename(current_db),
                            mime="application/octet-stream",
                            key="download_db"
                        )
                    else:
                        st.error("Current database file not found")
                except Exception as e:
                    st.error(f"Error downloading database: {e}")
        
        st.divider()
        
        # Manual path input
        st.subheader("Manual Database Path")
        manual_path = st.text_input(
            "Enter full database path:",
            placeholder="/path/to/your/database.db"
        )
        
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("Load from Path", use_container_width=True):
                if manual_path and manual_path.endswith('.db'):
                    if os.path.exists(manual_path):
                        try:
                            st.session_state.db_manager = st.session_state.db_manager.__class__(manual_path)
                            if self.persist_database_path(manual_path):
                                st.success(f"✅ Loaded: {manual_path}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error loading database: {e}")
                    else:
                        st.error("Database file does not exist")
                else:
                    st.error("Please enter a valid .db file path")
        
        with col2:
            if st.button("Refresh List", use_container_width=True):
                st.rerun()