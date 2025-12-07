# FILE: inventory-manager/src/tabs/votes_tab.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

class VotesTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("📊 Votes & Statistics")
        
        # Check if user is admin
        user = st.session_state.get('user', {})
        if user.get('role') != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view votes.")
            return
        
        # Tab layout for different vote statistics
        tab1, tab2 = st.tabs([
            "🗳️ All Votes",
            "📈 Vote Statistics"
        ])
        
        with tab1:
            self._render_all_votes()
        
        with tab2:
            self._render_vote_statistics()
    
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
    
    def _render_vote_statistics(self):
        """Render vote statistics and charts"""
        st.subheader("📈 Vote Statistics")
        
        try:
            # Get vote statistics using API
            result = st.session_state.db_manager._make_request('GET', '/votes/statistics')
            
            if result and 'statistics' in result:
                stats_df = pd.DataFrame(result['statistics'])
                
                if not stats_df.empty:
                    # Show top voted records
                    st.write("### 🏆 Most Voted Records")
                    
                    # Display top records by total votes
                    top_records = stats_df.sort_values('total_votes', ascending=False).head(20)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Bar chart for top voted records
                        fig = px.bar(
                            top_records,
                            x='total_votes',
                            y='title',
                            orientation='h',
                            title='Top 20 Most Voted Records',
                            color='total_votes',
                            color_continuous_scale='viridis'
                        )
                        fig.update_layout(
                            yaxis_title='Record Title',
                            xaxis_title='Total Votes',
                            height=500,
                            showlegend=False
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Display table with details
                        display_df = top_records[['artist', 'title', 'upvotes', 'downvotes', 'total_votes']].copy()
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                'artist': st.column_config.TextColumn('Artist'),
                                'title': st.column_config.TextColumn('Title'),
                                'upvotes': st.column_config.NumberColumn('👍 Upvotes'),
                                'downvotes': st.column_config.NumberColumn('👎 Downvotes'),
                                'total_votes': st.column_config.NumberColumn('📊 Total Votes')
                            }
                        )
                    
                    # Show vote distribution
                    st.write("### 📊 Vote Distribution")
                    
                    # Get overall vote counts
                    all_votes_result = st.session_state.db_manager._make_request('GET', '/votes/all')
                    if all_votes_result and 'votes' in all_votes_result:
                        all_votes_df = pd.DataFrame(all_votes_result['votes'])
                        
                        if not all_votes_df.empty:
                            vote_counts = all_votes_df['vote_type'].value_counts()
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # Pie chart for vote types
                                fig = px.pie(
                                    names=vote_counts.index,
                                    values=vote_counts.values,
                                    title='Vote Type Distribution',
                                    color_discrete_sequence=px.colors.qualitative.Set3
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            
                            with col2:
                                # Summary metrics
                                total_votes = len(all_votes_df)
                                upvote_percentage = (len(all_votes_df[all_votes_df['vote_type'] == 'upvote']) / total_votes * 100) if total_votes > 0 else 0
                                downvote_percentage = (len(all_votes_df[all_votes_df['vote_type'] == 'downvote']) / total_votes * 100) if total_votes > 0 else 0
                                
                                st.metric("Total Votes", total_votes)
                                st.metric("Upvote Rate", f"{upvote_percentage:.1f}%")
                                st.metric("Downvote Rate", f"{downvote_percentage:.1f}%")
                    
                    # Show records with highest upvote/downvote ratio
                    st.write("### ⭐ Best Rated Records")
                    
                    # Calculate ratio for records with at least 5 votes
                    qualified_records = stats_df[stats_df['total_votes'] >= 5].copy()
                    if not qualified_records.empty:
                        qualified_records['upvote_ratio'] = qualified_records['upvotes'] / qualified_records['total_votes'] * 100
                        best_rated = qualified_records.sort_values('upvote_ratio', ascending=False).head(10)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            fig = px.bar(
                                best_rated,
                                x='upvote_ratio',
                                y='title',
                                orientation='h',
                                title='Top 10 Best Rated Records (min 5 votes)',
                                color='upvote_ratio',
                                color_continuous_scale='greens'
                            )
                            fig.update_layout(
                                yaxis_title='Record Title',
                                xaxis_title='Upvote Ratio (%)',
                                height=400,
                                showlegend=False
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            display_df = best_rated[['artist', 'title', 'upvotes', 'total_votes', 'upvote_ratio']].copy()
                            display_df['upvote_ratio'] = display_df['upvote_ratio'].round(1)
                            st.dataframe(
                                display_df,
                                use_container_width=True,
                                hide_index=True,
                                column_config={
                                    'artist': st.column_config.TextColumn('Artist'),
                                    'title': st.column_config.TextColumn('Title'),
                                    'upvotes': st.column_config.NumberColumn('👍 Upvotes'),
                                    'total_votes': st.column_config.NumberColumn('📊 Total Votes'),
                                    'upvote_ratio': st.column_config.NumberColumn('⭐ Upvote Ratio (%)', format="%.1f")
                                }
                            )
                else:
                    st.info("No vote statistics available.")
            else:
                st.error("Unable to fetch vote statistics from API.")
                
        except Exception as e:
            st.error(f"Error loading vote statistics: {e}")