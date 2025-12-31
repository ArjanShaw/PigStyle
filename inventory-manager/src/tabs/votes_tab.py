import streamlit as st
import pandas as pd
import requests

class VotesTab:
    def __init__(self, base_url="https://arjanshaw.pythonanywhere.com"):
        # FIX: Ensure base_url is a string, not an object
        if hasattr(base_url, '__str__'):
            self.base_url = str(base_url)
        else:
            self.base_url = base_url
    
    def render(self):
        st.header("🗳️ All Votes")
        
        user = st.session_state.get('user', {})
        user_role = user.get('role')
        
        # Only admin can view votes tab
        if user_role != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view votes.")
            return
        
        self._render_all_votes()
    
    def _render_all_votes(self):
        st.subheader("🗳️ All Votes")
        
        # Make direct API call
        result = self._make_request('GET', '/votes/all')
        
        if result and 'votes' in result:
            votes_df = pd.DataFrame(result['votes'])
            
            if not votes_df.empty:
                st.dataframe(
                    votes_df,
                    width='stretch',
                    hide_index=True,
                    column_config={
                        'id': st.column_config.NumberColumn('Vote ID'),
                        'record_id': st.column_config.NumberColumn('Record ID'),
                        'artist': st.column_config.TextColumn('Artist'),
                        'title': st.column_config.TextColumn('Title'),
                        'voter_ip': st.column_config.TextColumn('Voter IP'),
                        'vote_type': st.column_config.TextColumn('Vote Type'),
                        'vote_type_name': st.column_config.TextColumn('Vote Type Name'),
                        'voted_at': st.column_config.DatetimeColumn('Voted At')
                    }
                )
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Votes", len(votes_df))
                with col2:
                    upvotes = len(votes_df[votes_df['vote_type'] == 'up'])
                    st.metric("Upvotes", upvotes)
                with col3:
                    downvotes = len(votes_df[votes_df['vote_type'] == 'down'])
                    st.metric("Downvotes", downvotes)
            else:
                st.info("No votes found in the database.")
        else:
            st.error("Unable to fetch votes data from API.")
    
    def _make_request(self, method, endpoint, **kwargs):
        """Make API request with error handling"""
        # FIX: Ensure base_url is a string
        base_url_str = str(self.base_url) if hasattr(self.base_url, '__str__') else self.base_url
        url = f"{base_url_str}{endpoint}"
        
        try:
            response = requests.request(method, url, **kwargs)
            
            if 200 <= response.status_code < 300:
                return response.json()
            else:
                st.error(f"API Error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            st.error(f"Network error: {str(e)}")
            return None