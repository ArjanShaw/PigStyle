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
                st.metric("Failed Searches", stats['failed_count'])
            with col3:
                st.metric("Latest Record", stats['latest_record'][:16] if stats['latest_record'] != "None" else "None")
            
            if stats['records_count'] > 0:
                self._render_genre_chart()
            else:
                st.info("No records available for analytics. Add some records first!")
                
        except Exception as e:
            st.error(f"Error loading statistics: {e}")

    def _render_genre_chart(self):
        """Render only the top 10 genre bar graph"""
        try:
            # Get all records
            records_df = st.session_state.db_manager.get_all_records()
            
            # Top 10 genres chart
            if 'genre' in records_df.columns and not records_df['genre'].empty:
                genre_counts = records_df['genre'].value_counts().head(10).reset_index()
                genre_counts.columns = ['genre', 'count']
                
                fig = px.bar(
                    genre_counts,
                    x='count',
                    y='genre',
                    orientation='h',
                    title='Top 10 Genres',
                    color='count',
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