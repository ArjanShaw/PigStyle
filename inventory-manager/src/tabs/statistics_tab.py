# FILE: inventory-manager/src/tabs/statistics_tab.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class StatisticsTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("📊 Statistics")
        
        # Check if user is admin
        user = st.session_state.get('user', {})
        if user.get('role') != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view statistics.")
            return
        
        # Tab layout for different statistics
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Overview",
            "🎵 Genres",
            "💰 Pricing",
            "🗳️ Votes"  # Added Votes tab here
        ])
        
        with tab1:
            self._render_overview_stats()
        
        with tab2:
            self._render_genre_chart()
        
        with tab3:
            self._render_price_comparison_chart()
        
        with tab4:
            self._render_vote_statistics()  # Moved from separate VotesTab

    def _render_overview_stats(self):
        """Render overview statistics"""
        try:
            # Get database statistics using API
            stats = st.session_state.db_manager.get_database_stats()
            
            # Display basic stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Records", stats['records_count'])
            with col2:
                st.metric("Latest Record", stats['latest_record'][:16] if stats['latest_record'] != "None" else "None")
            with col3:
                st.metric("Users", stats['users_count'])
            with col4:
                st.metric("Database", stats['db_path'])
            
            # Try to get vote statistics
            try:
                vote_stats = st.session_state.db_manager.get_vote_statistics()
                if not vote_stats.empty:
                    # Calculate vote statistics
                    total_votes = vote_stats['total_votes'].sum()
                    avg_votes_per_record = vote_stats['total_votes'].mean()
                    most_voted = vote_stats.sort_values('total_votes', ascending=False).head(1)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Votes", int(total_votes))
                    with col2:
                        st.metric("Avg Votes/Record", f"{avg_votes_per_record:.1f}")
                    with col3:
                        if not most_voted.empty:
                            record = most_voted.iloc[0]
                            st.metric("Most Voted", f"{record['total_votes']} votes")
                    
                    # Show top 5 most voted records
                    st.subheader("🏆 Top 5 Most Voted Records")
                    top_records = vote_stats.sort_values('total_votes', ascending=False).head(5)
                    
                    for i, (_, record) in enumerate(top_records.iterrows()):
                        with st.expander(f"{i+1}. {record['artist']} - {record['title']}", expanded=(i==0)):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("👍 Upvotes", record['upvotes'])
                            with col2:
                                st.metric("👎 Downvotes", record['downvotes'])
                            with col3:
                                st.metric("📊 Total", record['total_votes'])
            except Exception as e:
                st.info("Vote statistics not available")
            
        except Exception as e:
            st.error(f"Error loading statistics: {e}")

    def _render_genre_chart(self):
        """Render vertical bar chart for top 10 genres using API data"""
        try:
            # Get genre statistics from records using API
            records_df = st.session_state.db_manager.get_all_records()
            
            if records_df.empty:
                st.info("No records available for genre chart.")
                return
            
            # Count records by genre_name
            if 'genre_name' in records_df.columns:
                genre_counts = records_df['genre_name'].value_counts().head(10).reset_index()
                genre_counts.columns = ['genre_name', 'record_count']
            elif 'genre' in records_df.columns:
                # Fallback to 'genre' column if 'genre_name' doesn't exist
                genre_counts = records_df['genre'].value_counts().head(10).reset_index()
                genre_counts.columns = ['genre_name', 'record_count']
            else:
                st.info("No genre data available for chart.")
                return
            
            if len(genre_counts) > 0:
                fig = px.bar(
                    genre_counts,
                    x='genre_name',
                    y='record_count',
                    title='Top 10 Genres',
                    color='record_count',
                    color_continuous_scale='blues'
                )
                fig.update_layout(
                    xaxis_title='Genre',
                    yaxis_title='Number of Records',
                    height=400,
                    showlegend=False,
                    xaxis_tickangle=-45
                )
                st.plotly_chart(fig, width='stretch')
            else:
                st.info("No genre data available for chart.")
                
        except Exception as e:
            st.error(f"Error rendering genre chart: {e}")

    def _render_price_comparison_chart(self):
        """Render price comparison chart between eBay, Discogs, and Store prices using API data"""
        try:
            # Get price data from records using API
            records_df = st.session_state.db_manager.get_all_records()
            
            if records_df.empty:
                st.info("No price data available for comparison charts. Update prices using the Pricing section.")
                return
            
            # Filter records with valid prices
            price_columns = ['ebay_sell_at', 'store_price', 'discogs_suggested_price']
            valid_price_records = records_df[
                (records_df['ebay_sell_at'].notna() & (records_df['ebay_sell_at'] > 0)) |
                (records_df['store_price'].notna() & (records_df['store_price'] > 0)) |
                (records_df['discogs_suggested_price'].notna() & (records_df['discogs_suggested_price'] > 0))
            ]
            
            if len(valid_price_records) > 0:
                # Calculate average prices
                avg_prices = {
                    'eBay': valid_price_records['ebay_sell_at'].mean() if 'ebay_sell_at' in valid_price_records.columns and valid_price_records['ebay_sell_at'].notna().any() else 0,
                    'Store': valid_price_records['store_price'].mean() if 'store_price' in valid_price_records.columns and valid_price_records['store_price'].notna().any() else 0,
                    'Discogs': valid_price_records['discogs_suggested_price'].mean() if 'discogs_suggested_price' in valid_price_records.columns and valid_price_records['discogs_suggested_price'].notna().any() else 0
                }
                
                # Remove zero values
                avg_prices = {k: v for k, v in avg_prices.items() if v > 0}
                
                if avg_prices:
                    # Create comparison bar chart
                    fig = px.bar(
                        x=list(avg_prices.keys()),
                        y=list(avg_prices.values()),
                        title='Average Price Comparison',
                        color=list(avg_prices.keys()),
                        color_discrete_sequence=['#1f77b4', '#ff7f0e', '#2ca02c']
                    )
                    
                    fig.update_layout(
                        xaxis_title='Price Type',
                        yaxis_title='Average Price ($)',
                        height=400,
                        showlegend=False
                    )
                    
                    # Format y-axis as currency
                    fig.update_yaxes(tickprefix='$', tickformat='.2f')
                    
                    st.plotly_chart(fig, width='stretch')
                    
                    # Add some statistics
                    col1, col2, col3 = st.columns(3)
                    
                    if 'eBay' in avg_prices:
                        with col1:
                            st.metric("Avg eBay Price", f"${avg_prices['eBay']:.2f}")
                    
                    if 'Store' in avg_prices:
                        with col2:
                            st.metric("Avg Store Price", f"${avg_prices['Store']:.2f}")
                    
                    if 'Discogs' in avg_prices:
                        with col3:
                            st.metric("Avg Discogs Price", f"${avg_prices['Discogs']:.2f}")
                            
                else:
                    st.info("No valid price data available for comparison chart.")
                        
            else:
                st.info("No price data available for comparison charts. Update prices using the Pricing section.")
                
        except Exception as e:
            st.error(f"Error rendering price comparison chart: {e}")

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