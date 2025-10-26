import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import os
import json
from datetime import datetime

class PrintConfig:
    def __init__(self, config_file="print_config.json"):
        self.config_file = config_file
        self.defaults = {
            "last_genre": "",
            "genre_font_size": 48
        }
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file or use defaults"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    config = self.defaults.copy()
                    config.update(loaded_config)
                    return config
            except Exception as e:
                print(f"Error loading config file: {e}. Using defaults.")
                return self.defaults.copy()
        else:
            # Create default config file
            self._save_config(self.defaults)
            return self.defaults.copy()
    
    def _save_config(self, config):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config file: {e}")
    
    def get(self, key, default=None):
        """Get a configuration value with optional default"""
        return self.config.get(key, default if default is not None else self.defaults.get(key))
    
    def update(self, new_config):
        """Update configuration and save to file"""
        self.config.update(new_config)
        self._save_config(self.config)
    
    def get_all(self):
        """Get all configuration values"""
        return self.config.copy()

class GenreMappingsTab:
    def __init__(self):
        self.config = PrintConfig()
    
    def render(self):
        st.header("🎵 Genres")
        
        try:
            # Check if database manager is available
            if not hasattr(st.session_state, 'db_manager'):
                st.error("Database manager not initialized")
                return
            
            # Initialize session state for tracking processed files
            if 'last_processed_file' not in st.session_state:
                st.session_state.last_processed_file = None
            
            # Get all artists from records and their assigned genres
            all_artists_with_genres = st.session_state.db_manager.get_all_artists_with_genres()
            
            # Get all genres for dropdown
            all_genres = st.session_state.db_manager.get_all_genres()
            genre_options = {row['genre_name']: row['id'] for _, row in all_genres.iterrows()}
            
            if len(all_artists_with_genres) > 0:
                st.subheader("Artist-Genre Assignments")
                
                # Add filters
                col1, col2 = st.columns(2)
                with col1:
                    artist_filter = st.text_input(
                        "Filter by artist:",
                        placeholder="Enter artist name...",
                        key="artist_filter"
                    )
                with col2:
                    genre_filter = st.selectbox(
                        "Filter by genre:",
                        options=["All Genres"] + list(genre_options.keys()),
                        key="genre_filter"
                    )
                
                # Apply filters
                filtered_artists = all_artists_with_genres.copy()
                if artist_filter:
                    filtered_artists = filtered_artists[filtered_artists['artist_name'].str.contains(artist_filter, case=False, na=False)]
                if genre_filter != "All Genres":
                    filtered_artists = filtered_artists[filtered_artists['genre_name'] == genre_filter]
                
                # Create editable dataframe
                display_data = []
                for _, row in filtered_artists.iterrows():
                    display_data.append({
                        'Artist': row['artist_name'],
                        'Genre': row['genre_name'] if row['genre_name'] else "Unknown"
                    })
                
                df = pd.DataFrame(display_data)
                
                # Create editable dataframe with selectbox for genre
                edited_df = st.data_editor(
                    df,
                    column_config={
                        'Artist': st.column_config.TextColumn('Artist', disabled=True),
                        'Genre': st.column_config.SelectboxColumn(
                            'Genre',
                            options=[""] + list(genre_options.keys()),
                            required=False
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
                        if original_row['Genre'] != edited_row['Genre']:
                            artist_name = original_row['Artist']
                            if edited_row['Genre']:  # Only update if a genre is selected
                                new_genre_name = edited_row['Genre']
                                # Check if genre exists, if not create it
                                if new_genre_name not in genre_options:
                                    success, new_genre_id = st.session_state.db_manager.add_genre(new_genre_name)
                                    if success:
                                        genre_options[new_genre_name] = new_genre_id
                                    else:
                                        st.error(f"Failed to create new genre: {new_genre_name}")
                                        continue
                                else:
                                    new_genre_id = genre_options[new_genre_name]
                                
                                success = st.session_state.db_manager.assign_genre_to_artist(artist_name, new_genre_id)
                                if success:
                                    changes_made = True
                            else:
                                # Remove genre assignment if empty string selected
                                success = st.session_state.db_manager.remove_genre_from_artist_by_name(artist_name)
                                if success:
                                    changes_made = True
                    
                    if changes_made:
                        st.success("Genre assignments updated!")
                        st.rerun()
                
                # Export/Import functionality
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📤 Export Genre Data", use_container_width=True):
                        # Export only artist mappings
                        export_data = self._prepare_export_data(edited_df)
                        csv_data = export_data.to_csv(index=False)
                        
                        st.download_button(
                            label="⬇️ Download Genre CSV",
                            data=csv_data,
                            file_name="genre_data_export.csv",
                            mime="text/csv",
                            key="download_genre_data"
                        )
                
                with col2:
                    uploaded_file = st.file_uploader(
                        "Import genre data CSV",
                        type=['csv'],
                        help="Upload CSV with artist-genre mappings",
                        key="genre_import_uploader"
                    )
                    
                    # Only process if we have a new uploaded file and haven't processed it yet
                    if (uploaded_file is not None and 
                        st.session_state.last_processed_file != uploaded_file.file_id):
                        
                        try:
                            # Store that we're processing this file
                            st.session_state.last_processed_file = uploaded_file.file_id
                            
                            import_df = pd.read_csv(uploaded_file)
                            updates_made = self._process_import_data_fast(import_df)
                            
                            if updates_made > 0:
                                st.success(f"✅ Imported {updates_made} genre updates!")
                                # Clear the uploader by resetting the session state
                                if 'genre_import_uploader' in st.session_state:
                                    del st.session_state.genre_import_uploader
                                st.rerun()
                            else:
                                st.warning("No valid genre updates found in file")
                                # Clear the uploader
                                if 'genre_import_uploader' in st.session_state:
                                    del st.session_state.genre_import_uploader
                        except Exception as e:
                            st.error(f"Error importing CSV: {e}")
                            # Clear the uploader on error too
                            if 'genre_import_uploader' in st.session_state:
                                del st.session_state.genre_import_uploader
            
            else:
                st.info("No artists found in records.")
            
            # Clean up unused genres
            st.subheader("Clean Up Genres")
            if st.button("🗑️ Remove Unused Genres", help="Delete genres that are not assigned to any artists"):
                unused_genres_removed = self._remove_unused_genres()
                if unused_genres_removed > 0:
                    st.success(f"✅ Removed {unused_genres_removed} unused genres!")
                    st.rerun()
                else:
                    st.info("No unused genres found.")
            
            # Genre Signs Printing
            st.subheader("Genre Signs Printing")
            
            if len(all_genres) > 0:
                genre_options_list = all_genres['genre_name'].tolist()
            else:
                genre_options_list = ["ROCK", "JAZZ", "HIP-HOP", "ELECTRONIC", "POP", "METAL", "FOLK", "SOUL"]
            
            col1, col2 = st.columns(2)
            with col1:
                print_option = st.radio(
                    "Print option:",
                    ["Single Genre", "All Genres"],
                    key="print_option"
                )
                
                if print_option == "Single Genre":
                    genre_text = st.selectbox("Select genre:", options=genre_options_list, key="genre_select")
                else:
                    genre_text = "ALL_GENRES"
            
            with col2:
                font_size = st.slider("Font Size", min_value=24, max_value=96, value=48, key="genre_font_size")
            
            if st.button("🖨️ Generate Genre Sign PDF"):
                try:
                    if print_option == "All Genres":
                        pdf_buffer = self._generate_all_genre_signs_pdf(genre_options_list, font_size)
                        filename = f"all_genre_signs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    else:
                        pdf_buffer = self._generate_genre_sign_pdf(genre_text, font_size)
                        filename = f"genre_sign_{genre_text.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    
                    st.download_button(
                        label="⬇️ Download Genre Sign PDF",
                        data=pdf_buffer.getvalue(),
                        file_name=filename,
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"Error generating genre sign: {e}")
                
        except Exception as e:
            st.error(f"Error loading genres: {e}")

    def _prepare_export_data(self, artist_mappings_df):
        """Prepare export data with only artist mappings"""
        # Prepare artist mapping data (include unknown genres)
        artist_mapping_data = []
        for _, row in artist_mappings_df.iterrows():
            artist_mapping_data.append({
                'Artist': row['Artist'],
                'Genre': row['Genre'] if row['Genre'] else 'Unknown'
            })
        
        # Combine both datasets
        export_df = pd.DataFrame(artist_mapping_data)
        return export_df

    def _process_import_data_fast(self, import_df):
        """Process imported genre data with bulk operations and progress bar"""
        # Normalize column names to handle case differences
        column_mapping = {}
        for col in import_df.columns:
            col_lower = col.lower()
            if col_lower == 'artist':
                column_mapping[col] = 'artist'
            elif col_lower == 'genre':
                column_mapping[col] = 'genre'
        
        # Rename columns to standardize
        import_df_standardized = import_df.rename(columns=column_mapping)
        
        # Check if we have the required columns
        if 'artist' not in import_df_standardized.columns or 'genre' not in import_df_standardized.columns:
            st.error("CSV must contain 'Artist' and 'Genre' columns")
            return 0
        
        # Filter valid rows
        valid_rows = []
        for _, row in import_df_standardized.iterrows():
            artist = row['artist']
            genre_name = row['genre']
            if artist and genre_name and pd.notna(artist) and pd.notna(genre_name) and genre_name != 'Unknown':
                valid_rows.append((artist, genre_name))
        
        if not valid_rows:
            st.warning("No valid artist-genre pairs found in file")
            return 0
        
        # Setup progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        total_rows = len(valid_rows)
        
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            
            # Step 1: Get all existing genres
            cursor.execute('SELECT id, genre_name FROM genres')
            existing_genres = {row[1]: row[0] for row in cursor.fetchall()}
            
            # Step 2: Find genres that need to be created
            unique_genres = set(genre for _, genre in valid_rows)
            genres_to_create = unique_genres - set(existing_genres.keys())
            
            # Step 3: Bulk create new genres
            if genres_to_create:
                status_text.text("Creating new genres...")
                for i, genre_name in enumerate(genres_to_create):
                    cursor.execute('INSERT INTO genres (genre_name) VALUES (?)', (genre_name,))
                    existing_genres[genre_name] = cursor.lastrowid
                    progress_bar.progress((i + 1) / (len(genres_to_create) + total_rows) * 0.3)
            
            # Step 4: Bulk assign genres to artists
            status_text.text("Assigning genres to artists...")
            assignments_made = 0
            
            for i, (artist, genre_name) in enumerate(valid_rows):
                genre_id = existing_genres[genre_name]
                
                # Use INSERT OR REPLACE to handle existing assignments
                cursor.execute('''
                    INSERT OR REPLACE INTO genre_by_artist (artist_name, genre_id)
                    VALUES (?, ?)
                ''', (artist, genre_id))
                
                assignments_made += 1
                
                # Update progress
                progress = 0.3 + ((i + 1) / total_rows * 0.7)
                progress_bar.progress(progress)
                status_text.text(f"Processing {i+1}/{total_rows}: {artist} → {genre_name}")
            
            conn.commit()
            conn.close()
            
            status_text.text(f"✅ Completed! Processed {assignments_made} assignments")
            progress_bar.progress(1.0)
            
            return assignments_made
            
        except Exception as e:
            st.error(f"Error during import: {e}")
            return 0
        finally:
            # Clean up progress indicators after a delay
            import time
            time.sleep(2)
            progress_bar.empty()
            status_text.empty()

    def _process_import_data(self, import_df):
        """Legacy slow import method - kept for compatibility"""
        return self._process_import_data_fast(import_df)

    def _remove_unused_genres(self):
        """Remove genres that are not assigned to any artists"""
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            
            # Find genres with no artist assignments
            cursor.execute('''
                SELECT g.id, g.genre_name 
                FROM genres g 
                LEFT JOIN genre_by_artist gba ON g.id = gba.genre_id 
                WHERE gba.genre_id IS NULL
            ''')
            
            unused_genres = cursor.fetchall()
            removed_count = 0
            
            # Delete unused genres
            for genre_id, genre_name in unused_genres:
                cursor.execute('DELETE FROM genres WHERE id = ?', (genre_id,))
                removed_count += 1
            
            conn.commit()
            conn.close()
            
            return removed_count
            
        except Exception as e:
            st.error(f"Error removing unused genres: {e}")
            return 0

    def _generate_genre_sign_pdf(self, genre, font_size):
        """Generate PDF with genre sign"""
        buffer = io.BytesIO()
        page_width, page_height = letter
        c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
        
        text = genre.upper()
        font_name = "Helvetica-Bold"
        
        c.setFont(font_name, font_size)
        text_width = c.stringWidth(text, font_name, font_size)
        text_height = font_size
        
        x_center = page_width / 2
        y_center = page_height / 2
        
        border_padding = 12
        border_width = text_height + (2 * border_padding)
        border_height = text_width + (2 * border_padding)
        border_x = x_center - (border_width / 2)
        border_y = y_center - (border_height / 2)
        
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(2)
        c.rect(border_x, border_y, border_width, border_height)
        
        c.saveState()
        c.translate(x_center, y_center)
        c.rotate(-90)
        c.setFont(font_name, font_size)
        c.drawString(-text_width/2, -text_height/2, text)
        c.restoreState()
        
        c.save()
        buffer.seek(0)
        return buffer

    def _generate_all_genre_signs_pdf(self, genres, font_size):
        """Generate PDF with all genre signs, one per page"""
        buffer = io.BytesIO()
        page_width, page_height = letter
        c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
        font_name = "Helvetica-Bold"
        
        for i, genre in enumerate(genres):
            if i > 0:  # Start new page for each genre after the first one
                c.showPage()
            
            text = genre.upper()
            
            c.setFont(font_name, font_size)
            text_width = c.stringWidth(text, font_name, font_size)
            text_height = font_size
            
            x_center = page_width / 2
            y_center = page_height / 2
            
            border_padding = 12
            border_width = text_height + (2 * border_padding)
            border_height = text_width + (2 * border_padding)
            border_x = x_center - (border_width / 2)
            border_y = y_center - (border_height / 2)
            
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(2)
            c.rect(border_x, border_y, border_width, border_height)
            
            c.saveState()
            c.translate(x_center, y_center)
            c.rotate(-90)
            c.setFont(font_name, font_size)
            c.drawString(-text_width/2, -text_height/2, text)
            c.restoreState()
        
        c.save()
        buffer.seek(0)
        return buffer