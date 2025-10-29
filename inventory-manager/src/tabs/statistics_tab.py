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
            # Get database statistics
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
                    self._render_price_distribution_chart()
            else:
                st.info("No records available for analytics. Add some records first!")
                
        except Exception as e:
            st.error(f"Error loading statistics: {e}")

    def _render_genre_chart(self):
        """Render only the top 10 genre bar graph using records_with_genres view"""
        try:
            # Get genre statistics from records_with_genres view
            conn = st.session_state.db_manager._get_connection()
            
            # Count records by genre using the view
            df = pd.read_sql('''
                SELECT 
                    genre,
                    COUNT(*) as record_count
                FROM records_with_genres 
                WHERE genre IS NOT NULL AND genre != ''
                GROUP BY genre
                ORDER BY record_count DESC
                LIMIT 10
            ''', conn)
            conn.close()
            
            if len(df) > 0:
                fig = px.bar(
                    df,
                    x='record_count',
                    y='genre',
                    orientation='h',
                    title='Top 10 Genres',
                    color='record_count',
                    color_continuous_scale='blues'
                )
                fig.update_layout(
                    xaxis_title='Number of Records',
                    yaxis_title='Genre',
                    height=400,
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No genre data available for chart.")
                
        except Exception as e:
            st.error(f"Error rendering genre chart: {e}")

    def _render_price_distribution_chart(self):
        """Render price distribution for eBay and store prices"""
        try:
            # Get price data from records
            conn = st.session_state.db_manager._get_connection()
            
            # Get records with eBay and store prices - using available price columns
            df = pd.read_sql('''
                SELECT 
                    ebay_median_price,
                    ebay_lowest_price,
                    ebay_highest_price,
                    store_price,
                    discogs_median_price
                FROM records_with_genres 
                WHERE (ebay_median_price IS NOT NULL AND ebay_median_price > 0)
                   OR (store_price IS NOT NULL AND store_price > 0)
                   OR (discogs_median_price IS NOT NULL AND discogs_median_price > 0)
            ''', conn)
            conn.close()
            
            if len(df) > 0:
                # Create subplots for price distributions
                fig = make_subplots(
                    rows=2, cols=1,
                    subplot_titles=('eBay Price Distribution', 'Store & Discogs Price Distribution'),
                    vertical_spacing=0.15
                )
                
                # eBay Median Price distribution
                ebay_prices = df[df['ebay_median_price'].notna() & (df['ebay_median_price'] > 0)]['ebay_median_price']
                if len(ebay_prices) > 0:
                    fig.add_trace(
                        go.Histogram(
                            x=ebay_prices,
                            name='eBay Median Price',
                            nbinsx=20,
                            marker_color='#1f77b4',
                            opacity=0.7
                        ),
                        row=1, col=1
                    )
                
                # Store Price distribution
                store_prices = df[df['store_price'].notna() & (df['store_price'] > 0)]['store_price']
                if len(store_prices) > 0:
                    fig.add_trace(
                        go.Histogram(
                            x=store_prices,
                            name='Store Price',
                            nbinsx=20,
                            marker_color='#ff7f0e',
                            opacity=0.7
                        ),
                        row=2, col=1
                    )
                
                # Discogs Median Price distribution (overlay on store prices)
                discogs_prices = df[df['discogs_median_price'].notna() & (df['discogs_median_price'] > 0)]['discogs_median_price']
                if len(discogs_prices) > 0:
                    fig.add_trace(
                        go.Histogram(
                            x=discogs_prices,
                            name='Discogs Median Price',
                            nbinsx=20,
                            marker_color='#2ca02c',
                            opacity=0.7
                        ),
                        row=2, col=1
                    )
                
                # Update layout
                fig.update_layout(
                    height=500,
                    showlegend=True,
                    title_text="Price Distributions",
                    title_x=0.5,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )
                
                # Update axes
                fig.update_xaxes(title_text="Price ($)", row=1, col=1)
                fig.update_xaxes(title_text="Price ($)", row=2, col=1)
                fig.update_yaxes(title_text="Count", row=1, col=1)
                fig.update_yaxes(title_text="Count", row=2, col=1)
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Add some statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    if len(ebay_prices) > 0:
                        st.metric("eBay Median Records", len(ebay_prices))
                        st.metric("Avg eBay Price", f"${ebay_prices.mean():.2f}")
                with col2:
                    if len(store_prices) > 0:
                        st.metric("Store Price Records", len(store_prices))
                        st.metric("Avg Store Price", f"${store_prices.mean():.2f}")
                with col3:
                    if len(discogs_prices) > 0:
                        st.metric("Discogs Records", len(discogs_prices))
                        st.metric("Avg Discogs Price", f"${discogs_prices.mean():.2f}")
                        
            else:
                st.info("No price data available for distribution charts. Update prices using the Pricing section.")
                
        except Exception as e:
            st.error(f"Error rendering price distribution chart: {e}")