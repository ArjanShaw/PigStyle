import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class StatisticsTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("📊 Statistics & Analytics")
        
        try:
            # Get database statistics
            stats = st.session_state.db_manager.get_database_stats()
            
            # Display basic stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Records", stats['records_count'])
            with col2:
                st.metric("Failed Searches", stats['failed_count'])
            with col3:
                st.metric("Latest Record", stats['latest_record'][:16] if stats['latest_record'] != "None" else "None")
            with col4:
                st.metric("Database", stats['db_path'])
            
            if stats['records_count'] > 0:
                self._render_analytics()
            else:
                st.info("No records available for analytics. Add some records first!")
                
        except Exception as e:
            st.error(f"Error loading statistics: {e}")

    def _render_analytics(self):
        """Render analytics charts and insights"""
        try:
            # Get all records
            records_df = st.session_state.db_manager.get_all_records()
            
            # Basic data cleaning
            records_df = records_df.fillna({
                'discogs_median_price': 0,
                'discogs_lowest_price': 0,
                'discogs_highest_price': 0
            })
            
            # Create tabs for different analytics views
            tab1, tab2, tab3, tab4 = st.tabs(["📈 Price Analysis", "🎵 Format & Genre", "📅 Timeline", "🔍 Insights"])
            
            with tab1:
                self._render_price_analysis(records_df)
            
            with tab2:
                self._render_format_genre_analysis(records_df)
            
            with tab3:
                self._render_timeline_analysis(records_df)
            
            with tab4:
                self._render_insights(records_df)
                
        except Exception as e:
            st.error(f"Error rendering analytics: {e}")

    def _render_price_analysis(self, df):
        """Render price distribution analysis"""
        st.subheader("Price Distribution")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Median price distribution
            fig = px.histogram(
                df[df['discogs_median_price'] > 0], 
                x='discogs_median_price',
                title='Distribution of Median Prices',
                nbins=20
            )
            fig.update_layout(xaxis_title='Median Price ($)', yaxis_title='Count')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Price by format
            if 'format' in df.columns:
                format_prices = df[df['discogs_median_price'] > 0].groupby('format')['discogs_median_price'].mean().reset_index()
                fig = px.bar(
                    format_prices,
                    x='format',
                    y='discogs_median_price',
                    title='Average Price by Format'
                )
                fig.update_layout(xaxis_title='Format', yaxis_title='Average Price ($)')
                st.plotly_chart(fig, use_container_width=True)
        
        # Top 10 most valuable records
        st.subheader("Top 10 Most Valuable Records")
        valuable_records = df[df['discogs_median_price'] > 0].nlargest(10, 'discogs_median_price')[['artist', 'title', 'discogs_median_price', 'format']]
        st.dataframe(valuable_records, use_container_width=True)

    def _render_format_genre_analysis(self, df):
        """Render format and genre analysis"""
        col1, col2 = st.columns(2)
        
        with col1:
            # Records by format
            if 'format' in df.columns:
                format_counts = df['format'].value_counts().reset_index()
                format_counts.columns = ['format', 'count']
                fig = px.pie(
                    format_counts,
                    values='count',
                    names='format',
                    title='Records by Format'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Records by genre
            if 'genre' in df.columns:
                genre_counts = df['genre'].value_counts().head(10).reset_index()
                genre_counts.columns = ['genre', 'count']
                fig = px.bar(
                    genre_counts,
                    x='count',
                    y='genre',
                    orientation='h',
                    title='Top 10 Genres'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Artist frequency
        st.subheader("Top 10 Artists by Record Count")
        artist_counts = df['artist'].value_counts().head(10).reset_index()
        artist_counts.columns = ['artist', 'count']
        st.dataframe(artist_counts, use_container_width=True)

    def _render_timeline_analysis(self, df):
        """Render timeline analysis"""
        # Convert created_at to datetime
        df['created_date'] = pd.to_datetime(df['created_at']).dt.date
        
        # Records added over time
        daily_additions = df.groupby('created_date').size().reset_index()
        daily_additions.columns = ['date', 'records_added']
        
        fig = px.line(
            daily_additions,
            x='date',
            y='records_added',
            title='Records Added Over Time'
        )
        fig.update_layout(xaxis_title='Date', yaxis_title='Records Added')
        st.plotly_chart(fig, use_container_width=True)
        
        # Cumulative records
        daily_additions['cumulative_records'] = daily_additions['records_added'].cumsum()
        fig = px.line(
            daily_additions,
            x='date',
            y='cumulative_records',
            title='Cumulative Records Over Time'
        )
        fig.update_layout(xaxis_title='Date', yaxis_title='Cumulative Records')
        st.plotly_chart(fig, use_container_width=True)

    def _render_insights(self, df):
        """Render key insights"""
        st.subheader("Key Insights")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Basic insights
            total_records = len(df)
            records_with_prices = len(df[df['discogs_median_price'] > 0])
            avg_price = df['discogs_median_price'].mean()
            max_price = df['discogs_median_price'].max()
            
            st.metric("Total Records", total_records)
            st.metric("Records with Prices", records_with_prices)
            st.metric("Average Price", f"${avg_price:.2f}" if avg_price > 0 else "N/A")
            st.metric("Highest Price", f"${max_price:.2f}" if max_price > 0 else "N/A")
        
        with col2:
            # Format insights
            if 'format' in df.columns:
                most_common_format = df['format'].mode()[0] if not df['format'].mode().empty else "N/A"
                format_count = df['format'].value_counts().iloc[0] if not df['format'].value_counts().empty else 0
                
                st.metric("Most Common Format", most_common_format)
                st.metric("Records in Most Common Format", format_count)
            
            # Condition insights
            if 'condition' in df.columns:
                avg_condition = df['condition'].apply(lambda x: float(x) if x and x.replace('.','').isdigit() else 0).mean()
                st.metric("Average Condition", f"{avg_condition:.1f}/5" if avg_condition > 0 else "N/A")
        
        # Data quality insights
        st.subheader("Data Quality")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            missing_barcodes = len(df[df['barcode'].isna() | (df['barcode'] == '')])
            st.metric("Missing Barcodes", missing_barcodes)
        
        with col2:
            missing_images = len(df[df['image_url'].isna() | (df['image_url'] == '')])
            st.metric("Missing Images", missing_images)
        
        with col3:
            missing_genres = len(df[df['genre'].isna() | (df['genre'] == '')])
            st.metric("Missing Genres", missing_genres)