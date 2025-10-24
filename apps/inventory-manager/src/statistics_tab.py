import streamlit as st
import pandas as pd
import plotly.express as px

class StatisticsTab:
    def __init__(self):
        pass
        
    def render(self):
        st.subheader("Statistics")
        
        # Database statistics
        stats = st.session_state.db_manager.get_database_stats()
        
        if stats['records_count'] > 0:
            # Get all records directly from the records table
            df_records = st.session_state.db_manager.get_all_records()
            
            # Get artist-genre mappings to create our own joined data
            artist_genres = st.session_state.db_manager.get_artists_with_genres()
            
            # Merge genres with records manually
            if len(artist_genres) > 0:
                # Create a mapping from artist to genre
                artist_to_genre = dict(zip(artist_genres['artist_name'], artist_genres['genre_name']))
                
                # Add genre_name column to records based on artist mapping
                df_records['genre_name'] = df_records['discogs_artist'].map(artist_to_genre)
                
                # Only show records with assigned genres in statistics
                records_with_genres = df_records[df_records['genre_name'].notna()]
                
                if len(records_with_genres) > 0:
                    # Create two columns for layout
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        # Genre bar chart
                        st.subheader("Records by Genre")
                        genre_counts = records_with_genres['genre_name'].value_counts().reset_index()
                        genre_counts.columns = ['Genre', 'Count']
                        
                        # Create bar chart with absolute numbers
                        fig_genre = px.bar(
                            genre_counts,
                            x='Genre',
                            y='Count',
                            title='Number of Records by Genre',
                            color='Genre',
                            color_discrete_sequence=px.colors.qualitative.Set3,
                            text='Count'  # Show count values on bars
                        )
                        
                        fig_genre.update_layout(
                            height=500,
                            showlegend=False,
                            margin=dict(l=20, r=20, t=40, b=20),
                            xaxis_tickangle=-45
                        )
                        
                        # Improve text display on bars
                        fig_genre.update_traces(texttemplate='%{text}', textposition='outside')
                        
                        st.plotly_chart(fig_genre, use_container_width=True)
                    
                    with col2:
                        # Database summary
                        st.subheader("Database Summary")
                        st.metric("Total Records", stats['records_count'])
                        st.metric("Records with Genres", len(records_with_genres))
                        st.metric("Unique Genres", len(genre_counts))
                        
                        # Artist statistics
                        unique_artists = df_records['discogs_artist'].nunique()
                        artists_with_genres = records_with_genres['discogs_artist'].nunique()
                        st.metric("Unique Artists", unique_artists)
                        st.metric("Artists with Genres", artists_with_genres)
                        
                        # Price statistics
                        if 'median_price' in records_with_genres.columns:
                            avg_price = records_with_genres['median_price'].mean()
                            total_value = records_with_genres['median_price'].sum()
                            st.metric("Average Price", f"${avg_price:.2f}")
                            st.metric("Total Value", f"${total_value:.2f}")
                    
                    # Show records without genres info
                    records_without_genres = len(df_records) - len(records_with_genres)
                    if records_without_genres > 0:
                        st.info(f"**Note:** {records_without_genres} records don't have genre assignments and are not shown in these statistics. "
                               f"Assign genres to artists in the Genre Mappings tab to include them.")
                    
                else:
                    st.warning("No records with genre assignments found. Please assign genres to artists in the Genre Mappings tab to see statistics.")
            
            else:
                st.warning("No genre assignments found. Please assign genres to artists in the Genre Mappings tab to see statistics.")
            
        else:
            st.info("No records in database yet. Start by searching and adding records in the Search & Add tab!")