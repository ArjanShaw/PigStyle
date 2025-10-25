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
            
            # Create tabs for different functionality
            tab1, tab2 = st.tabs(["🎵 Artist Genre Mapping", "📊 Genre Statistics"])
            
            with tab1:
                self._render_artist_genre_mapping()
            
            with tab2:
                self._render_genre_statistics()
                
        except Exception as e:
            st.error(f"Error loading genre mappings: {e}")

    def _render_artist_genre_mapping(self):
        """Render artist to genre mapping interface"""
        st.subheader("Assign Genres to Artists")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Get artists without genres
            artists_without_genres = st.session_state.db_manager.get_artists_without_genres()
            
            if len(artists_without_genres) > 0:
                st.write(f"**Artists needing genre assignment:** {len(artists_without_genres)}")
                
                # Select artist to assign genre
                selected_artist = st.selectbox(
                    "Select artist to assign genre:",
                    options=artists_without_genres['artist_name'].tolist(),
                    key="artist_select"
                )
                
                # Get available genres
                all_genres = st.session_state.db_manager.get_all_genres()
                genre_options = all_genres['genre_name'].tolist()
                
                # Add new genre option
                genre_options.append("➕ Add new genre...")
                
                selected_genre = st.selectbox(
                    "Select genre:",
                    options=genre_options,
                    key="genre_select"
                )
                
                # Handle new genre creation
                if selected_genre == "➕ Add new genre...":
                    new_genre = st.text_input("Enter new genre name:", key="new_genre")
                    if st.button("Create Genre", key="create_genre"):
                        if new_genre and new_genre.strip():
                            success, genre_id = st.session_state.db_manager.add_genre(new_genre.strip())
                            if success:
                                st.success(f"✅ Created genre: {new_genre}")
                                st.rerun()
                            else:
                                st.error(f"❌ Genre '{new_genre}' already exists")
                        else:
                            st.error("Please enter a genre name")
                
                # Assign genre to artist
                elif selected_artist and selected_genre != "➕ Add new genre...":
                    if st.button("Assign Genre", key="assign_genre"):
                        # Find genre ID
                        genre_id = all_genres[all_genres['genre_name'] == selected_genre]['id'].iloc[0]
                        success = st.session_state.db_manager.assign_genre_to_artist(selected_artist, genre_id)
                        if success:
                            st.success(f"✅ Assigned '{selected_genre}' to {selected_artist}")
                            st.rerun()
                        else:
                            st.error("❌ Failed to assign genre")
            
            else:
                st.success("✅ All artists have genres assigned!")
        
        with col2:
            # Show current genre assignments
            st.subheader("Current Assignments")
            artists_with_genres = st.session_state.db_manager.get_artists_with_genres()
            
            if len(artists_with_genres) > 0:
                for _, row in artists_with_genres.iterrows():
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.write(f"**{row['artist_name']}**")
                        st.write(f"*{row['genre_name']}*")
                    with col_b:
                        if st.button("🗑️", key=f"remove_{row['mapping_id']}"):
                            success = st.session_state.db_manager.remove_genre_from_artist(
                                row['artist_name'], 
                                row['genre_id']
                            )
                            if success:
                                st.success(f"✅ Removed genre from {row['artist_name']}")
                                st.rerun()
                    st.divider()
            else:
                st.info("No genre assignments yet")

    def _render_genre_statistics(self):
        """Render genre statistics and management"""
        st.subheader("Genre Statistics & Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Genre management
            st.write("**Manage Genres**")
            all_genres = st.session_state.db_manager.get_all_genres()
            
            if len(all_genres) > 0:
                for _, genre in all_genres.iterrows():
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.write(genre['genre_name'])
                    with col_b:
                        if st.button("Delete", key=f"delete_genre_{genre['id']}"):
                            success = st.session_state.db_manager.delete_genre(genre['id'])
                            if success:
                                st.success(f"✅ Deleted genre: {genre['genre_name']}")
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to delete genre")
            
            # Add new genre
            new_genre_name = st.text_input("Add new genre:", key="new_genre_stats")
            if st.button("Add Genre", key="add_genre_stats"):
                if new_genre_name and new_genre_name.strip():
                    success, genre_id = st.session_state.db_manager.add_genre(new_genre_name.strip())
                    if success:
                        st.success(f"✅ Added genre: {new_genre_name}")
                        st.rerun()
                    else:
                        st.error(f"❌ Genre '{new_genre_name}' already exists")
                else:
                    st.error("Please enter a genre name")
        
        with col2:
            # Genre statistics
            st.write("**Genre Statistics**")
            try:
                genre_stats = st.session_state.db_manager.get_genre_statistics()
                
                if len(genre_stats) > 0:
                    for _, stat in genre_stats.iterrows():
                        st.write(f"**{stat['genre_name']}**")
                        st.write(f"Artists: {stat['artist_count']}")
                        st.write(f"Records: {stat['record_count']}")
                        st.divider()
                else:
                    st.info("No genre statistics available yet")
                    
            except Exception as e:
                st.error(f"Error loading genre statistics: {e}")
                st.info("Genre statistics will be available after creating some genres and assignments")

    def _render_genre_management(self):
        """Legacy method for backward compatibility"""
        self._render_genre_statistics()