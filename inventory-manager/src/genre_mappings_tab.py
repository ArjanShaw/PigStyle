import streamlit as st
import pandas as pd

class GenreMappingsTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("🏷️ Genre Mappings")
        
        try:
            # Check if database manager is available
            if not hasattr(st.session_state, 'db_manager'):
                st.error("Database manager not initialized")
                return
            
            col1, col2 = st.columns(2)
            
            with col1:
                self._render_genre_management()
            
            with col2:
                self._render_artist_genre_table()
                
        except Exception as e:
            st.error(f"Error loading genre mappings: {e}")

    def _render_genre_management(self):
        """Render genre management section"""
        st.subheader("Manage Genres")
        
        # Get all genres
        all_genres = st.session_state.db_manager.get_all_genres()
        
        # Display current genres with delete buttons
        if len(all_genres) > 0:
            st.write("**Current Genres:**")
            for _, genre in all_genres.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(genre['genre_name'])
                with col2:
                    if st.button("Delete", key=f"delete_{genre['id']}"):
                        success = st.session_state.db_manager.delete_genre(genre['id'])
                        if success:
                            st.success(f"Deleted genre: {genre['genre_name']}")
                            st.rerun()
                        else:
                            st.error("Failed to delete genre")
        
        # Add new genre
        st.write("**Add New Genre:**")
        new_genre = st.text_input("Genre name:", key="new_genre")
        if st.button("Add Genre"):
            if new_genre and new_genre.strip():
                success, genre_id = st.session_state.db_manager.add_genre(new_genre.strip())
                if success:
                    st.success(f"Added genre: {new_genre}")
                    st.rerun()
                else:
                    st.error(f"Genre '{new_genre}' already exists")
            else:
                st.error("Please enter a genre name")

    def _render_artist_genre_table(self):
        """Render artist-genre assignment table"""
        st.subheader("Artist Genre Assignments")
        
        # Get artists with genres
        artists_with_genres = st.session_state.db_manager.get_artists_with_genres()
        
        if len(artists_with_genres) > 0:
            # Display as a simple table
            display_data = []
            for _, row in artists_with_genres.iterrows():
                display_data.append({
                    'Artist': row['artist_name'],
                    'Genre': row['genre_name']
                })
            
            df = pd.DataFrame(display_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No genre assignments yet. Use the genre management to assign genres to artists.")