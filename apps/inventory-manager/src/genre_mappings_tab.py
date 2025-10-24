import streamlit as st
import pandas as pd
import io

class GenreMappingsTab:
    def __init__(self):
        pass
        
    def render(self):
        st.subheader("Genre Mappings by Artist")
        
        tab1, tab2, tab3 = st.tabs(["🎵 Artist-Genre Mappings", "⚙️ Genre Management", "📁 Import/Export"])
        
        with tab1:
            self._render_artist_genre_mappings()
        with tab2:
            self._render_genre_management()
        with tab3:
            self._render_import_export()
    
    # -------------------------
    # ARTIST-GENRE MAPPINGS TAB
    # -------------------------
    def _render_artist_genre_mappings(self):
        st.subheader("Assign Genres to Artists")
        
        all_artists = self._get_all_artists()
        if len(all_artists) == 0:
            st.info("No artists found in the database. Add some records first!")
            return
        
        available_genres = st.session_state.db_manager.get_all_genres()
        if len(available_genres) == 0:
            st.warning("Please add some genres first using the genre management section.")
            return
        
        current_assignments = st.session_state.db_manager.get_artists_with_genres()
        assignment_dict = {row['artist_name']: row['genre_id'] for _, row in current_assignments.iterrows()}
        
        genre_options = ["Select genre..."] + available_genres['genre_name'].tolist()
        genre_id_map = {row['genre_name']: row['id'] for _, row in available_genres.iterrows()}
        
        search_term = st.text_input("🔍 Search artists:", placeholder="Type to filter artists...", key="artist_search")
        if search_term:
            filtered_artists = [artist for artist in all_artists if search_term.lower() in artist.lower()]
        else:
            filtered_artists = all_artists
        
        st.write(f"Showing {len(filtered_artists)} artists")
        
        with st.form("artist_genre_form"):
            for artist in filtered_artists:
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.write(artist)
                with col2:
                    current_genre_id = assignment_dict.get(artist)
                    current_genre_name = None
                    if current_genre_id:
                        current_genre_row = available_genres[available_genres['id'] == current_genre_id]
                        if len(current_genre_row) > 0:
                            current_genre_name = current_genre_row.iloc[0]['genre_name']
                    
                    selected_genre = st.selectbox(
                        f"Genre for {artist}",
                        options=genre_options,
                        index=genre_options.index(current_genre_name) if current_genre_name else 0,
                        key=f"genre_select_{artist}",
                        label_visibility="collapsed"
                    )
            
            submitted = st.form_submit_button("💾 Save All Genre Assignments", use_container_width=True)
            if submitted:
                success_count = 0
                error_count = 0
                for artist in filtered_artists:
                    selected_genre = st.session_state.get(f"genre_select_{artist}", "Select genre...")
                    if selected_genre != "Select genre...":
                        genre_id = genre_id_map[selected_genre]
                        success = st.session_state.db_manager.assign_genre_to_artist(artist, genre_id)
                        success_count += int(success)
                        error_count += int(not success)
                    else:
                        current_genre_id = assignment_dict.get(artist)
                        if current_genre_id:
                            success = st.session_state.db_manager.remove_genre_from_artist(artist, current_genre_id)
                            success_count += int(success)
                            error_count += int(not success)
                
                if success_count > 0:
                    st.success(f"✅ Updated genre assignments for {success_count} artists!")
                if error_count > 0:
                    st.error(f"❌ Failed to update {error_count} artists")
        
        st.divider()
        assigned_count = len([a for a in all_artists if a in assignment_dict])
        unassigned_count = len(all_artists) - assigned_count
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Artists with Genre", assigned_count)
        with col2:
            st.metric("Artists without Genre", unassigned_count)
    
    def _get_all_artists(self):
        """Get all unique artists from the records table"""
        try:
            conn = st.session_state.db_manager._get_connection()
            df = pd.read_sql('SELECT DISTINCT discogs_artist FROM records ORDER BY discogs_artist', conn)
            conn.close()
            return df['discogs_artist'].tolist()
        except Exception as e:
            st.error(f"Error loading artists: {e}")
            return []
    
    # -------------------------
    # GENRE MANAGEMENT TAB
    # -------------------------
    def _render_genre_management(self):
        st.subheader("Manage Genres")
        
        available_genres = st.session_state.db_manager.get_all_genres()
        
        with st.form("add_genre_form", clear_on_submit=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                new_genre = st.text_input("Genre name:", placeholder="Enter new genre name...", label_visibility="collapsed")
            with col2:
                submitted = st.form_submit_button("➕ Add", use_container_width=True)
            
            if submitted:
                if new_genre and new_genre.strip():
                    success, genre_id = st.session_state.db_manager.add_genre(new_genre.strip())
                    if success:
                        st.success(f"Added genre: {new_genre}")
                    else:
                        st.error(f"Genre '{new_genre}' already exists!")
                else:
                    st.warning("Please enter a genre name")
        
        st.divider()
        st.write("**Existing Genres**")
        
        if len(available_genres) > 0:
            display_data = [
                {'ID': row['id'], 'Genre Name': row['genre_name'], 'Delete': False}
                for _, row in available_genres.iterrows()
            ]
            genres_df = pd.DataFrame(display_data)
            
            with st.form("genres_table_form"):
                edited_df = st.data_editor(
                    genres_df,
                    column_config={
                        "ID": st.column_config.NumberColumn("ID", disabled=True),
                        "Genre Name": st.column_config.TextColumn("Genre Name", disabled=True),
                        "Delete": st.column_config.CheckboxColumn("Delete")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                delete_submitted = st.form_submit_button("🗑️ Delete Selected Genres", use_container_width=True)
                if delete_submitted:
                    genres_to_delete = edited_df[edited_df['Delete']]
                    if len(genres_to_delete) > 0:
                        success_count = 0
                        error_count = 0
                        for _, row in genres_to_delete.iterrows():
                            genre_stats = st.session_state.db_manager.get_genre_statistics()
                            genre_usage = genre_stats[genre_stats['genre_name'] == row['Genre Name']]
                            if len(genre_usage) > 0 and genre_usage.iloc[0]['record_count'] > 0:
                                st.error(f"Cannot delete '{row['Genre Name']}' - it's assigned to {genre_usage.iloc[0]['record_count']} records")
                                error_count += 1
                            else:
                                success = st.session_state.db_manager.delete_genre(row['ID'])
                                success_count += int(success)
                                error_count += int(not success)
                        if success_count > 0:
                            st.success(f"✅ Deleted {success_count} genres!")
                        if error_count > 0:
                            st.error(f"❌ Failed to delete {error_count} genres")
                    else:
                        st.info("No genres selected for deletion.")
        else:
            st.info("No genres added yet.")
        
        st.divider()
        st.write("**Genre Statistics**")
        genre_stats = st.session_state.db_manager.get_genre_statistics()
        
        if len(genre_stats) > 0:
            display_stats = [
                {'Genre': row['genre_name'], 'Records': row['record_count'], 'Artists': row['artist_count']}
                for _, row in genre_stats.iterrows()
            ]
            stats_df = pd.DataFrame(display_stats)
            st.dataframe(stats_df, use_container_width=True, hide_index=True)
        else:
            st.info("No genre statistics available.")
    
    # -------------------------
    # IMPORT / EXPORT TAB
    # -------------------------
    def _render_import_export(self):
        st.subheader("Import/Export Genre Mappings")
        col1, col2 = st.columns(2)
        with col1:
            self._render_export_section()
        with col2:
            self._render_import_section()
    
    def _render_export_section(self):
        """Export all artists and their genres (Unassigned if missing)"""
        st.write("**Export Genre Mappings**")
        st.write("Download all artists and their assigned genres (shows 'Unassigned' if none).")
        
        all_artists = pd.DataFrame(self._get_all_artists(), columns=['artist_name'])
        mappings = st.session_state.db_manager.get_artists_with_genres()
        genres = st.session_state.db_manager.get_all_genres()
        
        # Normalize column names
        mappings.columns = [c.lower() for c in mappings.columns]
        genres.columns = [c.lower() for c in genres.columns]
        
        # Merge artist → mapping → genres
        df = all_artists.merge(mappings, on='artist_name', how='left') \
                        .merge(genres, left_on='genre_id', right_on='id', how='left', suffixes=('_mapping', '_genre'))
        
        # Determine which genre name column exists
        genre_col = None
        for c in ['genre_name_genre', 'genre_name_y', 'genre_name']:
            if c in df.columns:
                genre_col = c
                break
        
        df['Genre'] = df[genre_col].fillna('Unassigned')
        export_df = df[['artist_name', 'Genre']].rename(columns={'artist_name': 'Artist'})
        export_df = export_df.sort_values('Artist')
        
        csv = export_df.to_csv(index=False)
        st.download_button(
            label="📥 Download All Artists + Genres CSV",
            data=csv,
            file_name="all_artist_genre_mappings.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.write("**Preview:**")
        st.dataframe(export_df.head(10), use_container_width=True, hide_index=True)
        if len(export_df) > 10:
            st.caption(f"Showing first 10 of {len(export_df)} rows")
    
    def _render_import_section(self):
        """Import artist-genre mappings from CSV"""
        st.write("**Import Genre Mappings**")
        st.write("Upload a CSV file to update artist-genre mappings.")
        
        uploaded_file = st.file_uploader("Choose CSV file", type=['csv'], help="CSV should have columns: 'Artist' and 'Genre'")
        if uploaded_file is not None:
            try:
                import_df = pd.read_csv(uploaded_file)
                if not all(col in import_df.columns for col in ['Artist', 'Genre']):
                    st.error("CSV must contain 'Artist' and 'Genre' columns")
                    return
                
                st.write("**Preview:**")
                st.dataframe(import_df.head(10), use_container_width=True, hide_index=True)
                
                available_genres = st.session_state.db_manager.get_all_genres()
                valid_genres = set(available_genres['genre_name'].tolist())
                invalid_genres = set(import_df['Genre'].dropna().unique()) - valid_genres - {"Unassigned"}
                
                if invalid_genres:
                    st.warning(f"⚠️ Unknown genres found: {', '.join(invalid_genres)}")
                    st.info("Please add these genres in the Genre Management tab before importing.")
                    return
                
                if st.button("🚀 Import Genre Mappings", use_container_width=True):
                    genre_id_map = {row['genre_name']: row['id'] for _, row in available_genres.iterrows()}
                    success_count = 0
                    error_count = 0
                    for _, row in import_df.iterrows():
                        artist = row['Artist']
                        genre_name = row['Genre']
                        if genre_name == "Unassigned" or pd.isna(genre_name):
                            success = st.session_state.db_manager.remove_all_genres_from_artist(artist)
                        elif genre_name in genre_id_map:
                            success = st.session_state.db_manager.assign_genre_to_artist(artist, genre_id_map[genre_name])
                        else:
                            success = False
                        success_count += int(success)
                        error_count += int(not success)
                    
                    if success_count > 0:
                        st.success(f"✅ Imported {success_count} mappings successfully!")
                    if error_count > 0:
                        st.error(f"❌ Failed to import {error_count} mappings")
            
            except Exception as e:
                st.error(f"Error reading CSV file: {e}")
        
        with st.expander("📋 Import Instructions"):
            st.markdown("""
            **CSV Format Requirements:**
            - Must have columns: `Artist` and `Genre`
            - Artist names must match exactly with those in your database
            - Genre names must exist in your genre list
            - Use `Unassigned` to clear an artist’s genre
            
            **Example CSV:**
            ```csv
            Artist,Genre
            The Beatles,Rock
            Miles Davis,Jazz
            Unknown Artist,Unassigned
            ```
            """)
