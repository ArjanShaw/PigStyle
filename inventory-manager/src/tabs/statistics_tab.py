import streamlit as st
import pandas as pd
import plotly.express as px

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
                # Use half width for the chart
                col1, col2 = st.columns([1, 1])
                with col1:
                    self._render_genre_chart()
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