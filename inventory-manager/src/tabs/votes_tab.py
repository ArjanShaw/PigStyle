# FILE: inventory-manager/src/tabs/votes_tab.py
import streamlit as st
import pandas as pd

class VotesTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("🗳️ All Votes")
        
        # Check if user is admin
        user = st.session_state.get('user', {})
        if user.get('role') != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view votes.")
            return
        
        self._render_all_votes()
    
    def _render_all_votes(self):
        """Render all votes in a table"""
        st.subheader("🗳️ All Votes")
        
        try:
            # Get votes data using API
            result = st.session_state.db_manager._make_request('GET', '/votes/all')
            
            if result and 'votes' in result:
                votes_df = pd.DataFrame(result['votes'])
                
                if not votes_df.empty:
                    # Display the votes table
                    st.dataframe(
                        votes_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            'id': st.column_config.NumberColumn('Vote ID'),
                            'record_id': st.column_config.NumberColumn('Record ID'),
                            'artist': st.column_config.TextColumn('Artist'),
                            'title': st.column_config.TextColumn('Title'),
                            'voter_hash': st.column_config.TextColumn('Voter Hash'),
                            'vote_type': st.column_config.TextColumn('Vote Type'),
                            'vote_type_name': st.column_config.TextColumn('Vote Type Name'),
                            'created_at': st.column_config.DatetimeColumn('Voted At')
                        }
                    )
                    
                    # Show summary statistics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Votes", len(votes_df))
                    with col2:
                        upvotes = len(votes_df[votes_df['vote_type'] == 'upvote'])
                        st.metric("Upvotes", upvotes)
                    with col3:
                        downvotes = len(votes_df[votes_df['vote_type'] == 'downvote'])
                        st.metric("Downvotes", downvotes)
                else:
                    st.info("No votes found in the database.")
            else:
                st.error("Unable to fetch votes data from API.")
                
        except Exception as e:
            st.error(f"Error loading votes: {e}")