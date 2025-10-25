import streamlit as st
import pandas as pd
import io

class GenreMappingsTab:
    def __init__(self):
        pass
    
    def render(self):
        try:
            # Check if database manager is available
            if not hasattr(st.session_state, 'db_manager'):
                st.error("Database manager not initialized")
                return
            
            # Get artists with genres
            artists_with_genres = st.session_state.db_manager.get_artists_with_genres()
            
            # Get all genres for dropdown
            all_genres = st.session_state.db_manager.get_all_genres()
            genre_options = {row['genre_name']: row['id'] for _, row in all_genres.iterrows()}
            
            if len(artists_with_genres) > 0:
                # Create editable dataframe
                display_data = []
                for _, row in artists_with_genres.iterrows():
                    display_data.append({
                        'Artist': row['artist_name'],
                        'Current Genre': row['genre_name'],
                        'New Genre': row['genre_name']  # For editing
                    })
                
                df = pd.DataFrame(display_data)
                
                # Create editable dataframe
                edited_df = st.data_editor(
                    df,
                    column_config={
                        'Artist': st.column_config.TextColumn('Artist', disabled=True),
                        'Current Genre': st.column_config.TextColumn('Current Genre', disabled=True),
                        'New Genre': st.column_config.SelectboxColumn(
                            'New Genre',
                            options=list(genre_options.keys())
                        )
                    },
                    use_container_width=True,
                    hide_index=True,
                    key="genre_mappings_editor"
                )
                
                # Update genre assignments if changes were made
                if not edited_df.equals(df):
                    changes_made = False
                    for i, (original_row, edited_row) in enumerate(zip(df.to_dict('records'), edited_df.to_dict('records'))):
                        if original_row['New Genre'] != edited_row['New Genre']:
                            artist_name = original_row['Artist']
                            new_genre_id = genre_options[edited_row['New Genre']]
                            success = st.session_state.db_manager.assign_genre_to_artist(artist_name, new_genre_id)
                            if success:
                                changes_made = True
                    
                    if changes_made:
                        st.success("Genre assignments updated!")
                        st.rerun()
                
                # Export/Import functionality
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📤 Export Mappings", use_container_width=True):
                        export_data = edited_df[['Artist', 'New Genre']].copy()
                        export_data.columns = ['artist', 'genre']
                        csv_data = export_data.to_csv(index=False)
                        
                        st.download_button(
                            label="⬇️ Download CSV",
                            data=csv_data,
                            file_name="genre_mappings_export.csv",
                            mime="text/csv",
                            key="download_mappings"
                        )
                
                with col2:
                    uploaded_file = st.file_uploader(
                        "Import mappings CSV",
                        type=['csv'],
                        help="Upload CSV with columns: artist, genre"
                    )
                    
                    if uploaded_file is not None:
                        try:
                            import_df = pd.read_csv(uploaded_file)
                            if 'artist' in import_df.columns and 'genre' in import_df.columns:
                                updates_made = 0
                                for _, row in import_df.iterrows():
                                    artist = row['artist']
                                    genre_name = row['genre']
                                    if genre_name in genre_options:
                                        genre_id = genre_options[genre_name]
                                        success = st.session_state.db_manager.assign_genre_to_artist(artist, genre_id)
                                        if success:
                                            updates_made += 1
                                
                                if updates_made > 0:
                                    st.success(f"✅ Imported {updates_made} genre assignments!")
                                    st.rerun()
                                else:
                                    st.warning("No valid genre assignments found in file")
                            else:
                                st.error("CSV must contain 'artist' and 'genre' columns")
                        except Exception as e:
                            st.error(f"Error importing CSV: {e}")
            
            else:
                st.info("No genre assignments yet. Use the Genres tab to assign genres to artists.")
                
        except Exception as e:
            st.error(f"Error loading genre mappings: {e}")