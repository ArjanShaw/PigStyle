import streamlit as st
import pandas as pd

class GenreMappingsTab:
    def __init__(self):
        pass
        
    def render(self):
        st.subheader("Genre Mappings by Artist")
        
        # Create two columns for layout
        col1, col2 = st.columns([2, 1])
        
        with col1:
            self._render_artist_genre_mappings()
        
        with col2:
            self._render_genre_management()
    
    def _render_artist_genre_mappings(self):
        """Render the main artist-genre mapping interface"""
        st.subheader("Assign Genres to Artists")
        
        # Get all unique artists from records
        all_artists = self._get_all_artists()
        
        if len(all_artists) == 0:
            st.info("No artists found in the database. Add some records first!")
            return
        
        # Get available genres
        available_genres = st.session_state.db_manager.get_all_genres()
        
        if len(available_genres) == 0:
            st.warning("Please add some genres first using the genre management section.")
            return
        
        # Get current artist-genre assignments
        current_assignments = st.session_state.db_manager.get_artists_with_genres()
        assignment_dict = {}
        for _, row in current_assignments.iterrows():
            assignment_dict[row['artist_name']] = row['genre_id']
        
        # Create genre options for dropdown
        genre_options = ["Select genre..."] + available_genres['genre_name'].tolist()
        genre_id_map = {}
        for _, row in available_genres.iterrows():
            genre_id_map[row['genre_name']] = row['id']
        
        st.write(f"**Artists ({len(all_artists)} total):**")
        
        # Process in batches to avoid performance issues
        batch_size = 50
        total_artists = len(all_artists)
        
        # Add search/filter for artists
        search_term = st.text_input("🔍 Search artists:", placeholder="Type to filter artists...")
        
        if search_term:
            filtered_artists = [artist for artist in all_artists if search_term.lower() in artist.lower()]
        else:
            filtered_artists = all_artists
        
        st.write(f"Showing {len(filtered_artists)} artists")
        
        # Create a form for bulk updates
        with st.form("artist_genre_form"):
            updates_made = False
            
            for artist in filtered_artists:
                col1, col2 = st.columns([3, 2])
                
                with col1:
                    st.write(artist)
                
                with col2:
                    # Get current genre for this artist
                    current_genre_id = assignment_dict.get(artist)
                    current_genre_name = None
                    if current_genre_id:
                        current_genre_row = available_genres[available_genres['id'] == current_genre_id]
                        if len(current_genre_row) > 0:
                            current_genre_name = current_genre_row.iloc[0]['genre_name']
                    
                    # Create dropdown with current selection
                    selected_genre = st.selectbox(
                        f"Genre for {artist}",
                        options=genre_options,
                        index=genre_options.index(current_genre_name) if current_genre_name else 0,
                        key=f"genre_select_{artist}",
                        label_visibility="collapsed"
                    )
            
            # Submit button for the form
            if st.form_submit_button("💾 Save All Genre Assignments", use_container_width=True):
                success_count = 0
                error_count = 0
                
                for artist in filtered_artists:
                    selected_genre = st.session_state.get(f"genre_select_{artist}", "Select genre...")
                    
                    if selected_genre != "Select genre...":
                        # Assign genre to artist
                        genre_id = genre_id_map[selected_genre]
                        success = st.session_state.db_manager.assign_genre_to_artist(artist, genre_id)
                        if success:
                            success_count += 1
                        else:
                            error_count += 1
                    else:
                        # Remove genre assignment if "Select genre..." is chosen
                        current_genre_id = assignment_dict.get(artist)
                        if current_genre_id:
                            success = st.session_state.db_manager.remove_genre_from_artist(artist, current_genre_id)
                            if success:
                                success_count += 1
                            else:
                                error_count += 1
                
                if success_count > 0:
                    st.success(f"✅ Updated genre assignments for {success_count} artists!")
                if error_count > 0:
                    st.error(f"❌ Failed to update {error_count} artists")
                
                st.rerun()
        
        # Show summary statistics
        st.divider()
        assigned_count = len([a for a in all_artists if a in assignment_dict])
        unassigned_count = len(all_artists) - assigned_count
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Artists with Genre", assigned_count)
        with col2:
            st.metric("Artists without Genre", unassigned_count)
    
    def _get_all_artists(self):
        """Get all unique artists from records"""
        try:
            conn = st.session_state.db_manager._get_connection()
            df = pd.read_sql('SELECT DISTINCT discogs_artist FROM records ORDER BY discogs_artist', conn)
            conn.close()
            return df['discogs_artist'].tolist()
        except Exception as e:
            st.error(f"Error loading artists: {e}")
            return []
    
    def _render_genre_management(self):
        """Render genre management interface"""
        st.subheader("Manage Genres")
        
        # Add new genre
        st.write("**Add New Genre**")
        new_genre = st.text_input("Genre name:", key="new_genre_name")
        
        if st.button("Add Genre", use_container_width=True):
            if new_genre and new_genre.strip():
                success, genre_id = st.session_state.db_manager.add_genre(new_genre.strip())
                if success:
                    st.success(f"Added genre: {new_genre}")
                    st.rerun()
                else:
                    st.error(f"Genre '{new_genre}' already exists!")
            else:
                st.warning("Please enter a genre name")
        
        st.divider()
        
        # List existing genres
        st.write("**Existing Genres**")
        available_genres = st.session_state.db_manager.get_all_genres()
        
        if len(available_genres) > 0:
            for _, genre_row in available_genres.iterrows():
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(genre_row['genre_name'])
                
                with col2:
                    if st.button("Delete", key=f"delete_genre_{genre_row['id']}"):
                        # Check if genre is in use
                        genre_stats = st.session_state.db_manager.get_genre_statistics()
                        genre_usage = genre_stats[genre_stats['genre_name'] == genre_row['genre_name']]
                        
                        if len(genre_usage) > 0 and genre_usage.iloc[0]['record_count'] > 0:
                            st.error(f"Cannot delete '{genre_row['genre_name']}' - it's assigned to {genre_usage.iloc[0]['record_count']} records")
                        else:
                            success = st.session_state.db_manager.delete_genre(genre_row['id'])
                            if success:
                                st.success(f"Deleted genre: {genre_row['genre_name']}")
                                st.rerun()
                            else:
                                st.error(f"Failed to delete genre: {genre_row['genre_name']}")
        else:
            st.info("No genres added yet.")
        
        st.divider()
        
        # Genre statistics
        st.write("**Genre Statistics**")
        genre_stats = st.session_state.db_manager.get_genre_statistics()
        
        if len(genre_stats) > 0:
            for _, stat_row in genre_stats.iterrows():
                st.write(f"**{stat_row['genre_name']}:** {stat_row['record_count']} records, {stat_row['artist_count']} artists")
        else:
            st.info("No genre statistics available.")