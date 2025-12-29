import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

class StatisticsTab:
    def __init__(self, base_url="https://arjanshaw.pythonanywhere.com"):
        self.base_url = base_url
    
    def render(self):
        st.header("📊 Statistics")
        
        user = st.session_state.get('user', {})
        if user.get('role') != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view statistics.")
            return
        
        self._render_combined_stats()
    
    def _get_database_stats(self):
        """Get database statistics via API"""
        try:
            response = requests.get(f"{self.base_url}/stats")
            if response.status_code == 200:
                data = response.json()
                return {
                    'records_count': data.get('records_count', 0),
                    'users_count': data.get('users_count', 0),
                    'votes_count': data.get('votes_count', 0),
                    'latest_record': data.get('latest_record'),
                    'db_path': data.get('db_path', 'API-based')
                }
            return {'records_count': 0, 'users_count': 0, 'votes_count': 0, 'latest_record': 'N/A', 'db_path': 'API-based'}
        except Exception as e:
            st.error(f"API Error getting stats: {e}")
            return {'records_count': 0, 'users_count': 0, 'votes_count': 0, 'latest_record': 'N/A', 'db_path': 'API-based'}
    
    def _get_vote_statistics(self):
        """Get vote statistics via API"""
        try:
            response = requests.get(f"{self.base_url}/votes/statistics")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return pd.DataFrame(data.get('statistics', []))
            return pd.DataFrame()
        except Exception as e:
            st.error(f"API Error getting vote statistics: {e}")
            return pd.DataFrame()
    
    def _get_all_records(self):
        """Get all records via API"""
        try:
            response = requests.get(f"{self.base_url}/records?limit=1000")
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])
                return pd.DataFrame(records) if records else pd.DataFrame()
            return pd.DataFrame()
        except Exception as e:
            st.error(f"API Error getting records: {e}")
            return pd.DataFrame()
    
    def _render_combined_stats(self):
        # Get database stats
        stats = self._get_database_stats()
        
        # Display metrics in columns
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Records", stats['records_count'])
        with col2:
            latest = stats['latest_record']
            if latest and latest != "N/A":
                st.metric("Latest Record", latest[:16])
            else:
                st.metric("Latest Record", "None")
        with col3:
            st.metric("Users", stats['users_count'])
        
        # Get vote statistics
        vote_stats = self._get_vote_statistics()
        
        if not vote_stats.empty:
            st.subheader("🗳️ Vote Statistics")
            
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
            
            # Top 5 most voted records
            st.write("**🏆 Top 5 Most Voted Records**")
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
        
        # Genre statistics
        st.subheader("🎵 Genre Distribution")
        self._render_genre_chart()
        
        # Price statistics
        st.subheader("💰 Price Statistics")
        self._render_price_comparison_chart()
        
        # All votes table
        if not vote_stats.empty:
            st.subheader("📋 All Votes Summary")
            
            display_df = vote_stats[['artist', 'title', 'upvotes', 'downvotes', 'total_votes']].copy()
            st.dataframe(
                display_df,
                width='stretch',
                hide_index=True,
                column_config={
                    'artist': st.column_config.TextColumn('Artist'),
                    'title': st.column_config.TextColumn('Title'),
                    'upvotes': st.column_config.NumberColumn('👍 Upvotes'),
                    'downvotes': st.column_config.NumberColumn('👎 Downvotes'),
                    'total_votes': st.column_config.NumberColumn('📊 Total Votes')
                }
            )

    def _render_genre_chart(self):
        records_df = self._get_all_records()
        
        if records_df.empty:
            st.info("No records available for genre chart.")
            return
        
        if 'genre_name' in records_df.columns:
            genre_counts = records_df['genre_name'].value_counts().head(10).reset_index()
            genre_counts.columns = ['genre_name', 'record_count']
        elif 'genre' in records_df.columns:
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

    def _render_price_comparison_chart(self):
        records_df = self._get_all_records()
        
        if records_df.empty:
            st.info("No price data available for comparison charts. Update prices using the Pricing section.")
            return
        
        # Get price columns that actually exist in the database
        available_price_columns = []
        for col in ['ebay_sell_at', 'store_price']:
            if col in records_df.columns:
                available_price_columns.append(col)
        
        if not available_price_columns:
            st.info("No price columns found in database.")
            return
        
        # Filter records with valid prices
        filter_conditions = []
        for col in available_price_columns:
            filter_conditions.append(f"(records_df['{col}'].notna() & (records_df['{col}'] > 0))")
        
        filter_str = " | ".join(filter_conditions)
        valid_price_records = records_df[eval(filter_str)]
        
        if len(valid_price_records) > 0:
            avg_prices = {}
            
            if 'ebay_sell_at' in available_price_columns:
                ebay_avg = valid_price_records['ebay_sell_at'].mean() 
                if ebay_avg > 0:
                    avg_prices['eBay'] = ebay_avg
            
            if 'store_price' in available_price_columns:
                store_avg = valid_price_records['store_price'].mean()
                if store_avg > 0:
                    avg_prices['Store'] = store_avg
            
            if avg_prices:
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
                
                fig.update_yaxes(tickprefix='$', tickformat='.2f')
                
                st.plotly_chart(fig, width='stretch')
                
                # Display metrics
                cols = st.columns(len(avg_prices))
                for i, (price_type, price_value) in enumerate(avg_prices.items()):
                    with cols[i]:
                        st.metric(f"Avg {price_type} Price", f"${price_value:.2f}")
                        
            else:
                st.info("No valid price data available for comparison chart.")
                        
        else:
            st.info("No price data available for comparison charts. Update prices using the Pricing section.")