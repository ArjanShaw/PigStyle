import streamlit as st
import pandas as pd
from datetime import datetime
import json

class DebugTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("🐛 Debug & System Info")
        
        # Check if user is admin
        user = st.session_state.get('user', {})
        if user.get('role') != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view debug information.")
            return
        
        # Tab layout for different debug information
        tab1, tab2, tab3, tab4 = st.tabs([
            "🚨 API Errors",
            "📊 Session State", 
            "🔧 System Info",
            "🔄 API Logs"
        ])
        
        with tab1:
            self._render_api_errors()
        
        with tab2:
            self._render_session_state()
        
        with tab3:
            self._render_system_info()
        
        with tab4:
            self._render_api_logs()
    
    def _render_api_errors(self):
        """Render API errors section"""
        st.subheader("🚨 Recent API Errors")
        
        if 'api_errors' not in st.session_state or not st.session_state.api_errors:
            st.info("No API errors recorded.")
            return
        
        # Show most recent errors first
        errors = st.session_state.api_errors[::-1]
        
        for i, error in enumerate(errors[:10]):  # Show last 10 errors
            with st.expander(f"Error {i+1} - {error['timestamp']}", expanded=i==0):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**URL:** `{error['url']}`")
                    st.write(f"**Method:** `{error['method']}`")
                with col2:
                    st.write(f"**Status Code:** `{error['status_code']}`")
                    st.write(f"**Time:** `{error['timestamp']}`")
                
                st.write("**Message:**")
                st.code(error['message'], language='text')
        
        # Clear errors button
        if st.button("🗑️ Clear All Error Logs", type="secondary"):
            st.session_state.api_errors = []
            st.rerun()
    
    def _render_session_state(self):
        """Render session state information"""
        st.subheader("📊 Session State")
        
        # Create a copy of session state without large objects
        session_data = {}
        for key, value in st.session_state.items():
            if key in ['db_manager', 'gallery_json_manager', 'github_sync_handler']:
                session_data[key] = f"<{type(value).__name__} object>"
            elif key == 'api_details':
                session_data[key] = f"API details: {len(value)} entries"
            elif key == 'api_logs':
                session_data[key] = f"API logs: {len(value)} entries"
            elif key == 'api_errors':
                session_data[key] = f"API errors: {len(value)} entries"
            elif key == 'user':
                session_data[key] = dict(value) if hasattr(value, 'items') else str(value)
            else:
                try:
                    # Try to convert to JSON-serializable format
                    json.dumps(value)
                    session_data[key] = value
                except:
                    session_data[key] = f"<{type(value).__name__} object>"
        
        # Display as JSON
        st.json(session_data)
        
        # Download session state
        if st.button("💾 Download Session State JSON"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"session_state_{timestamp}.json"
            
            # Convert to serializable format
            serializable_data = {}
            for key, value in session_data.items():
                if isinstance(value, (str, int, float, bool, type(None))):
                    serializable_data[key] = value
                else:
                    serializable_data[key] = str(value)
            
            json_data = json.dumps(serializable_data, indent=2)
            st.download_button(
                label="⬇️ Download JSON",
                data=json_data,
                file_name=filename,
                mime="application/json"
            )
    
    def _render_system_info(self):
        """Render system information"""
        st.subheader("🔧 System Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Python Environment:**")
            st.code(f"""
Python Version: {st.__version__}
Streamlit Version: {st.__version__}
Pandas Version: {pd.__version__}
            """)
            
            st.write("**Database Info:**")
            if hasattr(st.session_state, 'db_manager'):
                try:
                    stats = st.session_state.db_manager.get_database_stats()
                    st.code(f"""
Records: {stats.get('records_count', 'N/A')}
Users: {stats.get('users_count', 'N/A')}
Latest Record: {stats.get('latest_record', 'N/A')}
Database: {stats.get('db_path', 'N/A')}
                    """)
                except Exception as e:
                    st.error(f"Error getting database stats: {e}")
            else:
                st.warning("Database manager not available")
        
        with col2:
            st.write("**API Configuration:**")
            if hasattr(st.session_state, 'db_manager'):
                api_url = st.session_state.db_manager.api_base_url
                st.code(f"""
API Base URL: {api_url}
                    """)
            
            st.write("**Feature Status:**")
            status_items = []
            
            # Check various handlers
            handlers_to_check = [
                ('Discogs Handler', 'discogs_handler'),
                ('eBay Handler', 'ebay_handler'), 
                ('YouTube Handler', 'youtube_handler'),
                ('Gallery JSON Manager', 'gallery_json_manager'),
                ('GitHub Sync Handler', 'github_sync_handler')
            ]
            
            for name, attr in handlers_to_check:
                handler = getattr(st.session_state, attr, None)
                if handler:
                    status_items.append(f"✅ {name}: Available")
                else:
                    status_items.append(f"❌ {name}: Not available")
            
            st.code("\n".join(status_items))
        
        # System actions
        st.subheader("🛠️ System Actions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Test API Connection", use_container_width=True):
                self._test_api_connection()
        
        with col2:
            if st.button("🗑️ Clear All Caches", use_container_width=True):
                self._clear_caches()
        
        with col3:
            if st.button("📋 Export System Report", use_container_width=True):
                self._export_system_report()
    
    def _render_api_logs(self):
        """Render API logs from session state"""
        st.subheader("🔄 API Request Logs")
        
        if 'api_logs' not in st.session_state or not st.session_state.api_logs:
            st.info("No API requests logged.")
            return
        
        # Show most recent logs first
        logs = st.session_state.api_logs[::-1]
        
        for i, log_title in enumerate(logs[:20]):  # Show last 20 logs
            if log_title in st.session_state.api_details:
                details = st.session_state.api_details[log_title]
                duration = details.get('duration', 'N/A')
                
                with st.expander(f"{log_title} ({duration}s)", expanded=False):
                    # Request details
                    if 'request' in details:
                        st.write("**Request:**")
                        st.json(details['request'])
                    
                    # Response details  
                    if 'response' in details:
                        st.write("**Response:**")
                        st.json(details['response'])
        
        # Clear logs button
        if st.button("🗑️ Clear API Logs", key="clear_api_logs"):
            st.session_state.api_logs = []
            st.session_state.api_details = {}
            st.rerun()
    
    def _test_api_connection(self):
        """Test API connection"""
        if hasattr(st.session_state, 'db_manager'):
            with st.spinner("Testing API connection..."):
                try:
                    result = st.session_state.db_manager._make_request('GET', '/health')
                    if result:
                        st.success("✅ API connection successful!")
                    else:
                        st.error("❌ API connection failed")
                except Exception as e:
                    st.error(f"❌ API connection error: {e}")
        else:
            st.error("Database manager not available")
    
    def _clear_caches(self):
        """Clear various caches"""
        cache_keys = [
            'store_fill_info', 'store_capacity_cache',
            'selected_records', 'search_results', 'current_search'
        ]
        
        cleared = []
        for key in cache_keys:
            if key in st.session_state:
                del st.session_state[key]
                cleared.append(key)
        
        if cleared:
            st.success(f"✅ Cleared caches: {', '.join(cleared)}")
        else:
            st.info("No caches to clear")
    
    def _export_system_report(self):
        """Export system report"""
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'system_info': {}
        }
        
        # Collect system information
        if hasattr(st.session_state, 'db_manager'):
            try:
                stats = st.session_state.db_manager.get_database_stats()
                report_data['database_stats'] = stats
            except Exception as e:
                report_data['database_stats_error'] = str(e)
        
        # Add API errors
        if 'api_errors' in st.session_state:
            report_data['recent_errors'] = st.session_state.api_errors[-10:]  # Last 10 errors
        
        # Convert to JSON
        json_report = json.dumps(report_data, indent=2)
        
        # Download button
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"system_report_{timestamp}.json"
        
        st.download_button(
            label="📥 Download System Report",
            data=json_report,
            file_name=filename,
            mime="application/json"
        )