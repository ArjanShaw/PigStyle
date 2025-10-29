import streamlit as st
import pandas as pd
from datetime import datetime

class DisplayHandler:
    def render_discogs_results(self, results, search_type):
        """Render Discogs search results"""
        if not results:
            st.warning("No results found on Discogs")
            return
        
        self._render_unified_results(results, search_type)

    def render_database_results(self, results, search_type):
        """Render database search results"""
        if not results:
            st.warning("No records found in database")
            return
        
        self._render_unified_results(results, search_type)

    def _render_unified_results(self, results, result_type):
        """Render unified results component for both Discogs and Database searches"""
        for i, record in enumerate(results):
            if result_type == "Add item":
                # For Discogs results, use 3 columns (no delete button)
                col1, col2, col3 = st.columns([1, 3, 1])
            else:
                # For database results, use 4 columns to include delete button
                col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
                
            with col1:
                image_url = record.get('image_url', '')
                if image_url:
                    st.image(image_url, width=80)
                else:
                    st.write("No image")
            with col2:
                artist = record.get('artist', '')
                title = record.get('title', '')
                
                # Common fields
                st.write(f"**{artist} - {title}**")
                
                # Type-specific fields
                if result_type == "Edit or Delete item":
                    barcode = record.get('barcode', '')
                    file_at = record.get('file_at', '')
                    price = record.get('price', '')
                    st.write(f"Barcode: {barcode} | File: {file_at} | Price: {price}")
                else:  # discogs
                    year = record.get('year', 'Unknown')
                    genre = record.get('genre', 'Unknown')
                    catalog = record.get('catalog_number', '')
                    st.write(f"Year: {year} | Genre: {genre} | Catalog: {catalog}")
                
            with col3:
                if st.button("Select", key=f"select_{result_type}_{i}", use_container_width=True):
                    st.session_state.selected_record = {
                        'type': 'discogs' if result_type == "Add item" else 'database',
                        'data': record,
                        'index': i
                    }
                    st.rerun()
            
            # Add delete button only for database results
            if result_type == "Edit or Delete item":
                with col4:
                    if st.button("🗑️ Delete", key=f"delete_{i}", use_container_width=True, type="secondary"):
                        record_id = record.get('id')
                        if record_id and self._delete_record(record_id):
                            st.success("Record deleted successfully!")
                            # Remove from current results
                            results.pop(i)
                            st.rerun()
            
            st.divider()
        
        # Checkout option only for database search
        if (result_type == "Edit or Delete item" and 
            st.session_state.selected_record and 
            st.session_state.selected_record['type'] == 'database'):
            
            checkout_checked = st.checkbox(
                "Check out selected record",
                key="checkout_checkbox"
            )
            
            if checkout_checked:
                record_data = st.session_state.selected_record['data']
                if 'id' in record_data and record_data['id'] not in [r.get('id') for r in st.session_state.checkout_records]:
                    st.session_state.checkout_records.append(record_data)

    def render_selected_record_only(self, selected_record):
        """Render only the selected record"""
        record = selected_record['data']
        result_type = "Database" if selected_record['type'] == 'database' else "Discogs"
        
        st.write(f"**Selected {result_type} Record:**")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            image_url = record.get('image_url', '')
            if image_url:
                st.image(image_url, width=100)
            else:
                st.write("No image")
        with col2:
            artist = record.get('artist', '')
            title = record.get('title', '')
            
            st.write(f"**{artist} - {title}**")
            
            if selected_record['type'] == 'database':
                barcode = record.get('barcode', '')
                file_at = record.get('file_at', '')
                price = record.get('price', '')
                st.write(f"Barcode: {barcode} | File: {file_at} | Price: {price}")
                
                # Add delete button for database records
                if st.button("🗑️ Delete Record", type="secondary", use_container_width=True, key="delete_record_view"):
                    if self._delete_record(record['id']):
                        st.success("Record deleted successfully!")
                        st.session_state.selected_record = None
                        st.rerun()
            else:
                year = record.get('year', 'Unknown')
                genre = record.get('genre', 'Unknown')
                catalog = record.get('catalog_number', '')
                st.write(f"Year: {year} | Genre: {genre} | Catalog: {catalog}")
        
        if st.button("← Back to Results", key="back_to_results"):
            st.session_state.selected_record = None
            st.rerun()

    def render_edit_section(self, selected_record, add_callback, update_callback, last_condition="5"):
        """Render the edit properties section"""
        st.subheader("Edit Properties")
        
        record_data = selected_record['data']
        
        # For Discogs records, show editable artist field with cleaned version
        if selected_record['type'] == 'discogs':
            raw_artist = record_data.get('artist', '')
            cleaned_artist = record_data.get('cleaned_artist', raw_artist)
            
            col1, col2 = st.columns(2)
            with col1:
                # Editable artist field pre-populated with cleaned version
                edited_artist = st.text_input(
                    "Artist:",
                    value=cleaned_artist,
                    key="artist_edit"
                )
            with col2:
                title = st.text_input(
                    "Title:",
                    value=record_data.get('title', ''),
                    key="title_edit"
                )
            
            # Update the record data with edited values
            record_data['artist'] = edited_artist
            record_data['title'] = title
            
            st.write(f"*Original artist from Discogs: {raw_artist}*")
        
        # Get suggested genre based on artist and Discogs genre
        suggested_genre = self._get_suggested_genre(record_data)
        
        col1, col2 = st.columns(2)
        with col1:
            # Use the last condition as default, or condition 5 if no last condition
            condition_index = ["1", "2", "3", "4", "5"].index(last_condition) if last_condition in ["1", "2", "3", "4", "5"] else 4
            condition = st.selectbox(
                "Condition:",
                options=["1", "2", "3", "4", "5"],
                index=condition_index,
                key="condition_edit"
            )
        with col2:
            all_genres = self._get_all_genres()
            
            # Set default index based on suggested genre
            default_index = 0
            if suggested_genre and suggested_genre in all_genres:
                default_index = all_genres.index(suggested_genre) + 1
            else:
                # Genre is mandatory, show warning if no genre selected
                st.warning("Genre is required")
            
            genre = st.selectbox(
                "Genre:",
                options=[""] + all_genres,
                index=default_index,
                key="genre_edit"
            )
            
            # Show where the suggestion came from
            if suggested_genre:
                suggestion_source = self._get_suggestion_source(record_data, suggested_genre)
                st.caption(f"Suggested: {suggested_genre} ({suggestion_source})")
        
        # Single submit button - only enable if genre is selected
        if selected_record['type'] == 'discogs':
            if st.button("Add to Database", use_container_width=True, disabled=not genre, key="add_to_database"):
                add_callback(condition, genre)
        else:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Update Record", use_container_width=True, disabled=not genre, key="update_record"):
                    update_callback(condition, genre)
            with col2:
                # Add delete button in edit section for database records
                if st.button("🗑️ Delete Record", type="secondary", use_container_width=True, key="delete_record_edit"):
                    record_id = selected_record['data']['id']
                    if self._delete_record(record_id):
                        st.success("Record deleted successfully!")
                        st.session_state.selected_record = None
                        st.rerun()

    def _get_suggested_genre(self, record_data):
        """Get suggested genre based on artist history and Discogs genre"""
        artist = record_data.get('artist', '')
        discogs_genre = record_data.get('genre', '')
        
        # Priority 1: Check if artist exists in database and get most common genre
        if artist:
            artist_genre = self._get_artist_most_common_genre(artist)
            if artist_genre:
                return artist_genre
        
        # Priority 2: Check Discogs genre and map to existing genres
        if discogs_genre:
            mapped_genre = self._map_discogs_genre(discogs_genre)
            if mapped_genre:
                return mapped_genre
        
        return ""

    def _get_suggestion_source(self, record_data, suggested_genre):
        """Get the source of the genre suggestion"""
        artist = record_data.get('artist', '')
        discogs_genre = record_data.get('genre', '')
        
        # Check if it came from artist history
        if artist:
            artist_genre = self._get_artist_most_common_genre(artist)
            if artist_genre == suggested_genre:
                return "artist history"
        
        # Check if it came from Discogs genre mapping
        if discogs_genre:
            mapped_genre = self._map_discogs_genre(discogs_genre)
            if mapped_genre == suggested_genre:
                return "Discogs genre mapping"
        
        return "unknown"

    def _get_artist_most_common_genre(self, artist):
        """Get the most common genre for an artist from existing records"""
        try:
            conn = st.session_state.db_manager._get_connection()
            df = pd.read_sql('''
                SELECT genre, COUNT(*) as count 
                FROM records_with_genres 
                WHERE artist = ? AND genre IS NOT NULL AND genre != '' 
                GROUP BY genre 
                ORDER BY count DESC 
                LIMIT 1
            ''', conn, params=(artist,))
            conn.close()
            
            if len(df) > 0:
                return df.iloc[0]['genre']
            return ""
        except Exception as e:
            return ""

    def _map_discogs_genre(self, discogs_genre):
        """Map Discogs genre to existing genres in database"""
        try:
            # Clean the Discogs genre (remove "Folk, World, & Country" type formatting)
            clean_genre = discogs_genre.split(',')[0].strip()
            
            # Check if this exact genre exists
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT genre_name FROM genres WHERE genre_name = ?', (clean_genre,))
            result = cursor.fetchone()
            if result:
                conn.close()
                return result[0]
            
            # Check for partial matches or common mappings
            common_mappings = {
                'Rock': ['Rock', 'Alternative Rock', 'Classic Rock'],
                'Jazz': ['Jazz'],
                'Hip Hop': ['Hip-Hop', 'Rap'],
                'Electronic': ['Electronic', 'Techno', 'House'],
                'Pop': ['Pop'],
                'Folk': ['Folk'],
                'Country': ['Country'],
                'Blues': ['Blues'],
                'Classical': ['Classical'],
                'Reggae': ['Reggae'],
                'Soul': ['Soul', 'Funk'],
                'Metal': ['Metal', 'Heavy Metal']
            }
            
            for main_genre, variants in common_mappings.items():
                for variant in variants:
                    if variant.lower() in clean_genre.lower():
                        # Check if main genre exists
                        cursor.execute('SELECT genre_name FROM genres WHERE genre_name = ?', (main_genre,))
                        result = cursor.fetchone()
                        if result:
                            conn.close()
                            return main_genre
            
            conn.close()
            return ""
        except Exception as e:
            return ""

    def render_checkout_section(self, checkout_records, checkout_callback):
        """Render checkout section"""
        if not checkout_records:
            return
        
        st.subheader("Checkout")
        st.write(f"**Items to checkout:** {len(checkout_records)}")
        
        # Display checkout items
        for record in checkout_records:
            st.write(f"- {record.get('artist', '')} - {record.get('title', '')} (${record.get('store_price', 0) or 0:.2f})")
        
        if st.button("🧾 Print Receipt & Mark as Sold", use_container_width=True, key="checkout_button"):
            checkout_callback()

    def render_genre_management(self):
        """Render genre management, import/export, and printing"""
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📤 Export Genre CSV", use_container_width=True, help="Export ID, Artist, Title, and Genre for all inventory records", key="export_genre_csv"):
                self._export_genre_csv()
            
        with col2:
            uploaded_file = st.file_uploader(
                "Upload genre CSV to update genres",
                type=['csv'],
                help="Upload CSV with id and genre columns to update genres",
                key="genre_import_uploader"
            )
                
            if uploaded_file is not None:
                import_df = pd.read_csv(uploaded_file)
                        
                if 'id' not in import_df.columns or 'genre' not in import_df.columns:
                    st.error("CSV must contain 'id' and 'genre' columns")
                else:
                    if st.button("🔄 Update Genres", use_container_width=True, key="update_genres"):
                        updated_count = self._update_genres_from_csv(import_df)
                        if updated_count > 0:
                            st.success(f"✅ Updated genres for {updated_count} records!")
                            st.session_state.records_updated += 1
                            st.rerun()
                        else:
                            st.warning("No genres were updated.")
        
        # Genre Signs Printing
        st.subheader("Genre Signs Printing")
        print_option = st.radio(
            "Print option:",
            ["Single Genre", "All Genres"],
            key="print_option"
        )
        
        if print_option == "Single Genre":
            genre_options = self._get_unique_genres()
            genre_text = st.selectbox("Select genre:", options=genre_options, key="genre_select")
        else:
            genre_text = "ALL_GENRES"
        
        font_size = st.slider("Font Size", min_value=24, max_value=96, value=48, key="genre_font_size")
        
        if st.button("🖨️ Generate Genre Sign PDF", use_container_width=True, key="generate_genre_sign"):
            self._generate_genre_sign_pdf(print_option, genre_text, font_size)

    def render_price_tag_management(self):
        """Render price tag management section"""
        if st.button("🖨️ Print Selected", use_container_width=True, help="Print selected records", key="print_selected"):
            self._generate_price_tags_pdf()

    def _delete_record(self, record_id):
        """Delete a record from the database"""
        try:
            success = st.session_state.db_manager.delete_record(record_id)
            if success:
                st.session_state.records_updated += 1
                return True
            else:
                st.error("Failed to delete record")
                return False
        except Exception as e:
            st.error(f"Error deleting record: {e}")
            return False

    def _get_all_genres(self):
        """Get all available genres from database"""
        try:
            conn = st.session_state.db_manager._get_connection()
            df = pd.read_sql('SELECT genre_name FROM genres ORDER BY genre_name', conn)
            conn.close()
            return df['genre_name'].tolist()
        except Exception as e:
            st.error(f"Error loading genres: {e}")
            return []

    def _get_unique_genres(self):
        """Get unique genres from inventory"""
        try:
            conn = st.session_state.db_manager._get_connection()
            genres_df = pd.read_sql(
                "SELECT DISTINCT genre FROM records WHERE genre IS NOT NULL AND genre != '' AND status = 'inventory' ORDER BY genre",
                conn
            )
            conn.close()
            
            if len(genres_df) > 0:
                return genres_df['genre'].tolist()
            else:
                return ["ROCK", "JAZZ", "HIP-HOP", "ELECTRONIC", "POP", "METAL", "FOLK", "SOUL"]
        except Exception as e:
            return ["ROCK", "JAZZ", "HIP-HOP", "ELECTRONIC", "POP", "METAL", "FOLK", "SOUL"]

    def _export_genre_csv(self):
        """Export ID, Artist, Title, and Genre for all inventory records"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql(
            "SELECT id, artist, title, genre FROM records_with_genres WHERE status = 'inventory' ORDER BY artist, title",
            conn
        )
        conn.close()
        
        if len(df) > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"genre_export_{timestamp}.csv"
            
            csv_data = df.to_csv(index=False)
            
            st.download_button(
                label="⬇️ Download Genre CSV",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                key=f"download_genre_{timestamp}"
            )
            
            st.success(f"✅ Export ready! {len(df)} inventory records.")
        else:
            st.warning("No inventory records to export.")

    def _update_genres_from_csv(self, import_df):
        """Update genres from CSV data (only id and genre columns are used)"""
        updated_count = 0
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        
        for _, row in import_df.iterrows():
            record_id = row.get('id')
            new_genre = row.get('genre')
            
            if record_id and pd.notna(new_genre):
                # Find genre_id for the genre name
                cursor.execute('SELECT id FROM genres WHERE genre_name = ?', (new_genre,))
                genre_result = cursor.fetchone()
                if genre_result:
                    genre_id = genre_result[0]
                    success = st.session_state.db_manager.update_record(record_id, {'genre_id': genre_id})
                    if success:
                        updated_count += 1
        
        conn.close()
        return updated_count

    def _generate_genre_sign_pdf(self, print_option, genre_text, font_size):
        """Generate genre sign PDF"""
        # This would call the genre handler - simplified for now
        st.info("Genre sign PDF generation would be implemented here")

    def _generate_price_tags_pdf(self):
        """Generate price tags PDF for selected records"""
        # This would call the export handler - simplified for now
        st.info("Price tags PDF generation would be implemented here")