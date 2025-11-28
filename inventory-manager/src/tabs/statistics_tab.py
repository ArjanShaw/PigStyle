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
        
        try:
            # Get database statistics using API
            stats = st.session_state.db_manager.get_database_stats()
            
            # Display basic stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", stats['records_count'])
            with col2:
                st.metric("Latest Record", stats['latest_record'][:16] if stats['latest_record'] != "None" else "None")
            
            if stats['records_count'] > 0:
                # Use half width for both charts
                col1, col2 = st.columns(2)
                with col1:
                    self._render_genre_chart()
                with col2:
                    self._render_price_comparison_chart()
            else:
                st.info("No records available for analytics. Add some records first!")
                
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
            
            # Count records by genre
            genre_counts = records_df['genre'].value_counts().head(10).reset_index()
            genre_counts.columns = ['genre', 'record_count']
            
            if len(genre_counts) > 0:
                fig = px.bar(
                    genre_counts,
                    x='genre',
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
                st.plotly_chart(fig, width= 'stretch')
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
                    
                    st.plotly_chart(fig, width= 'stretch')
                    
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