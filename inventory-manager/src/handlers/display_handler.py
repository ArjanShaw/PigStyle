# FILE: inventory-manager/src/handlers/display_handler.py

import streamlit as st
import pandas as pd
from datetime import datetime
import re
import math
import threading
import time

class DisplayHandler:
    def __init__(self, youtube_handler=None):
        self.youtube_handler = youtube_handler

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
            # Use columns for layout
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
                    store_price = record.get('store_price')
                    ebay_sell_at = record.get('ebay_sell_at')
                    discogs_suggested_price = record.get('discogs_suggested_price')
                    compilation = record.get('compilation', False)
                    consignor_name = record.get('consignor_name', '')
                    commission_rate = record.get('commission_rate')
                    
                    # SHOW THE REQUESTED FIELDS when selecting from inventory
                    record_id = record.get('id', '')
                    barcode = record.get('barcode', '')
                    file_at = record.get('file_at', '')
                    youtube_url = record.get('youtube_url', '')
                    catalog_number = record.get('catalog_number', '')
                    genre = record.get('genre', '')
                    
                    # Format the display with requested fields
                    st.write(f"**ID:** {record_id} | **Barcode:** {barcode}")
                    st.write(f"**Catalog:** {catalog_number}" if catalog_number else "**Catalog:** N/A")
                    st.write(f"**Genre:** {genre}" if genre else "**Genre:** N/A")
                    st.write(f"**Compilation:** {'✅ Yes' if compilation else '❌ No'}")
                    if consignor_name:
                        st.write(f"**Consignor:** {consignor_name} ({commission_rate*100 if commission_rate else 0}%)")
                    st.write(f"**Store Price:** ${store_price:.2f}" if store_price is not None else "**Store Price:** N/A")
                    st.write(f"**Discogs Price:** ${discogs_suggested_price:.2f}" if discogs_suggested_price and discogs_suggested_price > 0 else "**Discogs Price:** N/A")
                    st.write(f"**eBay Sell At:** ${ebay_sell_at:.2f}" if ebay_sell_at and ebay_sell_at > 0 else "**eBay Sell At:** N/A")
                    st.write(f"**File Location:** {file_at}")
                    if youtube_url:
                        st.write(f"🎵 **YouTube:** {youtube_url}")
                else:  # discogs
                    catalog = record.get('catalog_number', '')
                    year = record.get('year', '')
                    format_info = record.get('format', '')
                    label_info = record.get('label', '')
                    country = record.get('country', '')
                    genre = record.get('genre', '')
                    
                    # Show distinguishing information for Discogs results
                    info_lines = []
                    if catalog:
                        info_lines.append(f"**Catalog:** {catalog}")
                    if year:
                        info_lines.append(f"**Year:** {year}")
                    if format_info:
                        info_lines.append(f"**Format:** {format_info}")
                    if label_info:
                        info_lines.append(f"**Label:** {label_info}")
                    if country:
                        info_lines.append(f"**Country:** {country}")
                    if genre:
                        info_lines.append(f"**Genre:** {genre}")
                    
                    if info_lines:
                        st.write(" | ".join(info_lines))
                    else:
                        st.write("*No additional info*")
                
            with col3:
                if st.button("Select", key=f"select_{result_type}_{i}", width='stretch'):
                    st.session_state.selected_record = {
                        'type': 'discogs' if result_type == "Add item" else 'database',
                        'data': record,
                        'index': i
                    }
                    # Clear any previous loading state
                    if 'loading_complete' in st.session_state:
                        del st.session_state.loading_complete
                    if 'loading_progress' in st.session_state:
                        del st.session_state.loading_progress
                    if 'loading_error' in st.session_state:
                        del st.session_state.loading_error
                    
                    st.rerun()
            
            with col4:
                # DELETE BUTTON for each item in search results
                if result_type == "Edit or Delete item":
                    if st.button("🗑️ Delete", key=f"delete_{result_type}_{i}", width='stretch', type="secondary"):
                        record_id = record.get('id')
                        if self._delete_record(record_id):
                            st.success("Record deleted successfully!")
                            st.rerun()
            
            st.divider()

    def render_selected_record_only(self, selected_record):
        """Render only the selected record - SHOW REQUESTED FIELDS"""
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
                # SHOW THE REQUESTED FIELDS prominently
                record_id = record.get('id', '')
                barcode = record.get('barcode', '')
                file_at = record.get('file_at', '')
                store_price = record.get('store_price', '')
                ebay_sell_at = record.get('ebay_sell_at', '')
                youtube_url = record.get('youtube_url', '')
                catalog_number = record.get('catalog_number', '')
                genre = record.get('genre', '')
                discogs_suggested_price = record.get('discogs_suggested_price', '')
                compilation = record.get('compilation', False)
                consignor_name = record.get('consignor_name', '')
                commission_rate = record.get('commission_rate')
                store_return_days = record.get('store_return_days')
                
                st.write("---")
                st.write("**Record Details:**")
                st.write(f"**ID:** {record_id}")
                st.write(f"**Barcode:** {barcode}")
                st.write(f"**Catalog:** {catalog_number}" if catalog_number else "**Catalog:** N/A")
                st.write(f"**Genre:** {genre}" if genre else "**Genre:** N/A")
                st.write(f"**Compilation:** {'✅ Yes' if compilation else '❌ No'}")
                if consignor_name:
                    st.write(f"**Consignor:** {consignor_name}")
                    st.write(f"**Commission Rate:** {commission_rate*100 if commission_rate else 0}%")
                    st.write(f"**Store Return Days:** {store_return_days if store_return_days else 'N/A'}")
                st.write(f"**Store Price:** ${store_price:.2f}" if store_price and store_price > 0 else "**Store Price:** N/A")
                st.write(f"**Discogs Price:** ${discogs_suggested_price:.2f}" if discogs_suggested_price and discogs_suggested_price > 0 else "**Discogs Price:** N/A")
                st.write(f"**eBay Sell At:** ${ebay_sell_at:.2f}" if ebay_sell_at and ebay_sell_at > 0 else "**eBay Sell At:** N/A")
                st.write(f"**File Location:** {file_at}")
                if youtube_url:
                    st.write(f"🎵 **YouTube:** {youtube_url}")
                st.write("---")
            else:
                catalog = record.get('catalog_number', '')
                year = record.get('year', '')
                format_info = record.get('format', '')
                label_info = record.get('label', '')
                country = record.get('country', '')
                genre = record.get('genre', '')
                
                # Show distinguishing information for Discogs results
                info_lines = []
                if catalog:
                    info_lines.append(f"**Catalog:** {catalog}")
                if year:
                    info_lines.append(f"**Year:** {year}")
                if format_info:
                    info_lines.append(f"**Format:** {format_info}")
                if label_info:
                    info_lines.append(f"**Label:** {label_info}")
                if country:
                    info_lines.append(f"**Country:** {country}")
                if genre:
                    info_lines.append(f"**Genre:** {genre}")
                
                if info_lines:
                    for line in info_lines:
                        st.write(line)
        
        # Show tracklist for Discogs records
        if selected_record['type'] == 'discogs' and 'tracklist' in record:
            st.subheader("🎵 Album Tracklist")
            for i, track in enumerate(record['tracklist'], 1):
                st.write(f"{i}. {track}")
        
        if st.button("← Back to Results", key="back_to_results"):
            st.session_state.selected_record = None
            st.rerun()

    def render_edit_section(self, selected_record, add_callback, update_callback, discogs_handler=None, ebay_handler=None):
        """Render the edit properties section - WITH COMPILATION AND DIRECT CONSIGNMENT SUPPORT"""
        
        record_data = selected_record['data']
        
        # For Discogs records, fetch all data before showing ANY UI
        if selected_record['type'] == 'discogs' and not record_data.get('pricing_fetched'):
            # Show spinner while fetching ALL data
            with st.spinner("🔄 Fetching pricing data from Discogs, eBay, and YouTube..."):
                # Fetch all required data sequentially
                self._fetch_all_data_sync(record_data, discogs_handler, ebay_handler)
            
            # Mark as fetched and rerun to show the complete UI
            record_data['pricing_fetched'] = True
            st.rerun()
            return
        
        # Once ALL data is loaded, show the complete UI
        st.subheader("Edit Properties")
        
        # Add consignment dropdown for both new and existing records - NOW DIRECT CONSIGNOR SELECTION
        consignor_id, commission_rate, store_return_days = self._render_consignment_section(record_data)
        if consignor_id:
            record_data['consignor_id'] = consignor_id
            record_data['commission_rate'] = commission_rate
            record_data['store_return_days'] = store_return_days
        else:
            # Clear consignment if "Store Owned" is selected
            record_data['consignor_id'] = None
            record_data['commission_rate'] = None
            record_data['store_return_days'] = None
        
        # Show editable artist field with cleaned version
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
        
        # Show compilation checkbox - auto-detect for Various artists
        compilation_default = self._should_be_compilation(edited_artist, record_data)
        compilation = st.checkbox(
            "This is a compilation",
            value=compilation_default,
            key="compilation_checkbox",
            help="Auto-detected for Various artists. Check if this is a compilation album."
        )
        record_data['compilation'] = compilation
        
        # Show genre dropdown
        suggested_genre = self._get_suggested_genre(record_data)
        
        col1, col2 = st.columns(2)
        with col1:
            all_genres = self._get_all_genres()
            
            # Set default index based on suggested genre
            default_index = 0
            if suggested_genre and suggested_genre in all_genres:
                default_index = all_genres.index(suggested_genre) + 1
            
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
        
        # Show ALL pricing information (now fully loaded after ALL API calls)
        self._render_pricing_information(record_data)
        
        # Show YouTube integration (merged search and manual input)
        self._render_youtube_integration(record_data)
        
        # Single submit button - only enable if genre is selected
        button_label = "Add to Database" if selected_record['type'] == 'discogs' else "Update Record"
        if st.button(button_label, width='stretch', disabled=not genre, key="add_to_database"):
            # Get the file_at value for confirmation message
            file_at_value = self._calculate_file_at(record_data['artist'], genre, compilation)
            if selected_record['type'] == 'discogs':
                success, record_id = add_callback(genre)
                if success:
                    # Show confirmation message with artist, title, and fileat
                    st.success(f"✅ Record added successfully!\\n**Artist:** {record_data['artist']}\\n**Title:** {record_data['title']}\\n**File Location:** {file_at_value}")
                    st.session_state.record_added = True
            else:
                success = update_callback(genre)
                if success:
                    st.success(f"✅ Record updated successfully!\\n**File Location:** {file_at_value}")

    def _render_consignment_section(self, record_data=None):
        """Render consignment section with direct consignor selection and individual rates"""
        try:
            # Get all consignors for dropdown
            consignors_df = st.session_state.db_manager.get_all_consignors()
            
            if len(consignors_df) == 0:
                st.info("No consignors available. Add consignors in the Consignment tab first.")
                return None, None, None
            
            # Create options for dropdown
            options = ["Store Owned"]  # Default option
            
            # Create mapping for consignor selection
            consignor_mapping = {}
            for _, consignor in consignors_df.iterrows():
                option_text = f"{consignor['name']}"
                options.append(option_text)
                consignor_mapping[option_text] = consignor['id']
            
            # Determine default selection
            default_index = 0  # Default to "Store Owned"
            
            # If editing existing record with consignment, find the matching consignor
            current_consignor_name = record_data.get('consignor_name', '')
            if current_consignor_name:
                for option_text in consignor_mapping.keys():
                    if current_consignor_name in option_text:
                        default_index = options.index(option_text)
                        break
            
            # Render consignor dropdown
            selected_option = st.selectbox(
                "Consignor:",
                options=options,
                index=default_index,
                key="consignor_select"
            )
            
            # If Store Owned selected, return None for all values
            if selected_option == "Store Owned":
                return None, None, None
            
            # Get the selected consignor ID
            consignor_id = consignor_mapping.get(selected_option)
            
            # Show commission rate input
            current_commission_rate = record_data.get('commission_rate')
            if current_commission_rate is None:
                current_commission_rate = float(st.session_state.db_manager.get_config_value('DEFAULT_COMMISSION_RATE', '0.50'))
            
            commission_rate = st.number_input(
                "Commission Rate:",
                min_value=0.0,
                max_value=1.0,
                value=current_commission_rate,
                step=0.05,
                format="%.2f",
                key="commission_rate_input"
            )
            
            # Show store return days input
            current_store_return_days = record_data.get('store_return_days')
            if current_store_return_days is None:
                current_store_return_days = int(st.session_state.db_manager.get_config_value('DEFAULT_STORE_RETURN_DAYS', '90'))
            
            store_return_days = st.number_input(
                "Store Return Days:",
                min_value=1,
                max_value=365,
                value=current_store_return_days,
                step=1,
                key="store_return_days_input"
            )
            
            return consignor_id, commission_rate, store_return_days
            
        except Exception as e:
            st.error(f"Error loading consignment section: {e}")
            return None, None, None

    def _should_be_compilation(self, artist, record_data):
        """Determine if record should be marked as compilation based on artist name and artist history"""
        if not artist:
            return False
        
        artist_lower = artist.lower()
        compilation_indicators = [
            'various',
            'various artists',
            'va',
            'v.a.',
            'compilation',
            'various artits',  # Common typo
            'various artiists'  # Another common typo
        ]
        
        # Check for compilation indicators in artist name
        for indicator in compilation_indicators:
            if indicator in artist_lower:
                return True
        
        # Check artist history in database
        if self._is_artist_mostly_compilation(artist):
            return True
        
        # Also check if it's already marked as compilation in database record
        if record_data.get('compilation'):
            return True
            
        return False

    def _is_artist_mostly_compilation(self, artist):
        """Check if this artist's records are mostly marked as compilations in the database"""
        try:
            conn = st.session_state.db_manager._get_connection()
            
            # Count how many records by this artist are marked as compilations
            df = pd.read_sql('''
                SELECT compilation, COUNT(*) as count 
                FROM records 
                WHERE artist = ? 
                GROUP BY compilation
            ''', conn, params=(artist,))
            conn.close()
            
            if len(df) == 0:
                return False
            
            # Calculate compilation ratio
            total_records = df['count'].sum()
            compilation_count = df[df['compilation'] == True]['count'].sum() if True in df['compilation'].values else 0
            
            # If more than 50% of this artist's records are compilations, suggest compilation
            if total_records > 0 and (compilation_count / total_records) > 0.5:
                return True
                
            return False
            
        except Exception as e:
            print(f"Error checking artist compilation history: {e}")
            return False

    def _calculate_file_at(self, artist, genre, compilation):
        """Calculate file_at value for display in confirmation message"""
        if not artist or not genre:
            return "?"
        
        if compilation:
            # For compilations: Comp(first_letter_of_genre)
            genre_first_char = genre[0].upper() if genre and genre[0].isalpha() else "?"
            return f"Comp({genre_first_char})"
        else:
            # For regular records: genre(first_letter_of_artist)
            artist_clean = artist.strip().lower()
            
            if artist_clean.startswith('the '):
                artist_clean = artist_clean[4:]
            
            if artist_clean and artist_clean[0].isdigit():
                number_words = {
                    '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
                    '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
                }
                first_char = artist_clean[0]
                file_at_letter = number_words.get(first_char, '?')[0].upper()
            elif artist_clean and artist_clean[0].isalpha():
                file_at_letter = artist_clean[0].upper()
            else:
                file_at_letter = "?"
            
            return f"{genre}({file_at_letter})"

    def _fetch_all_data_sync(self, record_data, discogs_handler, ebay_handler):
        """Fetch all required data synchronously (blocking calls) - ALL APIs must complete"""
        # Step 1: Fetch Discogs pricing (BLOCKING)
        release_id = record_data.get('discogs_id')
        if discogs_handler and release_id:
            pricing_data = discogs_handler.get_release_statistics_pricing(str(release_id))
            record_data['price_suggestions'] = pricing_data.get('price_suggestions', {})
            record_data['total_conditions'] = pricing_data.get('total_conditions', 0)
            
            # Fetch tracklist from Discogs
            tracklist = discogs_handler.get_release_tracklist(release_id)
            if tracklist:
                record_data['tracklist'] = tracklist
        
        # Step 2: Fetch eBay pricing (BLOCKING)
        artist = record_data.get('artist', '')
        title = record_data.get('title', '')
        if ebay_handler and artist and title:
            ebay_pricing = ebay_handler.get_ebay_pricing(artist, title)
            if ebay_pricing:
                record_data['ebay_condition_pricing'] = ebay_pricing.get('condition_pricing', {})
                record_data['ebay_total_items_found'] = ebay_pricing.get('total_items_found', 0)
                record_data['ebay_search_url'] = ebay_pricing.get('search_url', '')
        
        # Step 3: Fetch YouTube results (BLOCKING) - NOW WITH TRACKLIST
        if self.youtube_handler and self.youtube_handler.is_enabled():
            # Get tracklist from Discogs for better YouTube matching
            track_titles = record_data.get('tracklist', [])
            
            search_query = f"{artist} {title}"
            record_data['youtube_search_query'] = search_query
            youtube_results = self.youtube_handler.search_youtube_videos(search_query, record_data, track_titles)
            st.session_state.youtube_search_results = youtube_results

    def _get_suggested_genre(self, record_data):
        """Get suggested genre for a record based on artist history - ONLY suggest if artist exists in database"""
        try:
            # Priority 1: Check artist history in database - ONLY if artist has existing records
            artist = record_data.get('artist', '')
            if artist:
                artist_genre = self._get_genre_from_artist_history(artist)
                if artist_genre:
                    return artist_genre
            
            # No suggestion available if artist doesn't exist in database
            return ""
            
        except Exception as e:
            print(f"Error getting suggested genre: {e}")
            return ""

    def _get_genre_from_artist_history(self, artist):
        """Get the most common genre for this artist from existing records - ONLY if artist exists"""
        try:
            conn = st.session_state.db_manager._get_connection()
            
            # First check if artist exists in database
            artist_exists = pd.read_sql('''
                SELECT COUNT(*) as count FROM records WHERE artist = ?
            ''', conn, params=(artist,)).iloc[0]['count'] > 0
            
            if not artist_exists:
                return ""
            
            # Find the most common genre for this artist
            df = pd.read_sql('''
                SELECT g.genre_name, COUNT(*) as count
                FROM records r
                JOIN genres g ON r.genre_id = g.id
                WHERE r.artist = ? AND g.genre_name IS NOT NULL
                GROUP BY g.genre_name
                ORDER BY count DESC
                LIMIT 1
            ''', conn, params=(artist,))
            conn.close()
            
            if len(df) > 0:
                return df.iloc[0]['genre_name']
            return ""
            
        except Exception as e:
            print(f"Error getting genre from artist history: {e}")
            return ""

    def _get_suggestion_source(self, record_data, suggested_genre):
        """Explain where the genre suggestion came from"""
        artist = record_data.get('artist', '')
        if artist and suggested_genre == self._get_genre_from_artist_history(artist):
            return "Artist history"
        
        return "Unknown"

    def _get_all_genres(self):
        """Get all available genres from database"""
        try:
            genres_df = st.session_state.db_manager.get_all_genres()
            return genres_df['genre_name'].tolist()
        except Exception as e:
            print(f"Error getting genres: {e}")
            return []

    def _get_condition_description(self, condition):
        """Map condition codes to readable descriptions"""
        condition_descriptions = {
            'Mint (M)': 'Perfect condition, still sealed or like new',
            'Near Mint (NM or M-)': 'Almost perfect, very minor signs of handling',
            'Very Good Plus (VG+)': 'Excellent condition with minor wear',
            'Very Good (VG)': 'Good condition with some visible wear',
            'Good Plus (G+)': 'Playable condition with noticeable wear',
            'Good (G)': 'Heavy wear but still playable',
            'Fair (F)': 'Significant wear, may have skips',
            'Poor (P)': 'Poor condition, may not play properly',
            'Generic': 'No specific condition information'
        }
        return condition_descriptions.get(condition, 'Unknown condition')

    def _render_youtube_integration(self, record_data):
        """Render merged YouTube integration with search results and manual input"""
        st.subheader("🎵 YouTube Integration")
        
        # Show current linked YouTube URL
        current_youtube_url = record_data.get('youtube_url', '')
        if current_youtube_url:
            st.success(f"✅ Currently linked: {current_youtube_url}")
            
            # Show option to remove link
            if st.button("❌ Remove YouTube Link", key="remove_youtube", width='stretch'):
                record_data['youtube_url'] = ''
                st.success("YouTube link removed!")
                st.rerun()
        
        # Manual YouTube URL input
        st.write("**Manual YouTube Link**")
        manual_url = st.text_input(
            "Paste YouTube URL:",
            value="",
            placeholder="https://www.youtube.com/watch?v=...",
            key="manual_youtube_url"
        )
        
        if manual_url and "youtube.com" in manual_url:
            if st.button("🔗 Use This YouTube URL", key="use_manual_url", width='stretch'):
                record_data['youtube_url'] = manual_url
                st.success("✅ YouTube URL linked!")
                st.rerun()
        
        # Show YouTube search results if available
        if 'youtube_search_results' in st.session_state and st.session_state.youtube_search_results:
            search_query = record_data.get('youtube_search_query', 'Unknown search')
            st.info(f"YouTube search '{search_query}' completed - {len(st.session_state.youtube_search_results)} results found")
            
            st.write("**Search Results:**")
            
            # Group by track if available
            track_results = [r for r in st.session_state.youtube_search_results if r.get('type') == 'track']
            album_results = [r for r in st.session_state.youtube_search_results if r.get('type') == 'album']
            
            if track_results:
                st.write("**🎵 Individual Track Recordings:**")
                for i, video in enumerate(track_results):
                    self._render_youtube_video_option(video, i, record_data)
            
            if album_results:
                st.write("**📀 Album Content:**")
                for i, video in enumerate(album_results, start=len(track_results)):
                    self._render_youtube_video_option(video, i, record_data)
        else:
            st.info("No YouTube search results available")

    def _render_youtube_video_option(self, video, index, record_data):
        """Display a YouTube video option with link button"""
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            if video.get('thumbnail'):
                st.image(video['thumbnail'], width=80)
        with col2:
            st.write(f"**{video['title']}**")
            st.write(f"Channel: {video['channel']}")
            if video.get('track_title'):
                st.write(f"Track: {video['track_title']}")
        with col3:
            if st.button("🔗 Link", key=f"youtube_link_{index}", width='stretch'):
                record_data['youtube_url'] = video['url']
                st.success(f"✅ Linked to: {video['title']}")
                st.rerun()

    def _render_pricing_information(self, record_data):
        """Render ALL pricing information - ONLY called after ALL API calls complete"""
        
        # Check if we have the required data from ALL APIs
        has_discogs_data = 'price_suggestions' in record_data
        has_ebay_data = 'ebay_condition_pricing' in record_data
        
        # Discogs Pricing Section - ONLY show if data is available
        if has_discogs_data:
            st.write("### 📀 Discogs Pricing")
            
            price_suggestions = record_data.get('price_suggestions', {})
            total_conditions = record_data.get('total_conditions', 0)
            
            if price_suggestions:
                # Display all conditions in a table for user selection
                st.write("**Select a condition:**")
                
                # Create a list of conditions with prices and descriptions
                conditions_data = []
                for condition, price in price_suggestions.items():
                    description = self._get_condition_description(condition)
                    conditions_data.append({
                        'Condition': condition,
                        'Description': description,
                        'Price': f"${price:.2f}"
                    })
                
                # Display as a table
                if conditions_data:
                    df = pd.DataFrame(conditions_data)
                    st.dataframe(df, width='stretch', hide_index=True)
                    
                    # Let user select a condition - default to Good Plus
                    condition_options = list(price_suggestions.keys())
                    default_condition = "Good Plus (G+)"
                    if default_condition not in condition_options and condition_options:
                        default_condition = condition_options[0]
                    
                    selected_condition = st.selectbox(
                        "Choose Discogs condition:",
                        options=condition_options,
                        index=condition_options.index(default_condition) if default_condition in condition_options else 0,
                        key="discogs_condition_select"
                    )
                    
                    # Store the selected condition and price in record_data
                    if selected_condition:
                        record_data['selected_condition'] = selected_condition
                        record_data['selected_price'] = price_suggestions[selected_condition]
                        st.success(f"✅ Selected: {selected_condition} - ${price_suggestions[selected_condition]:.2f}")
            else:
                st.write("No Discogs pricing data available")
            
            st.divider()
        else:
            st.write("### 📀 Discogs Pricing")
            st.info("Discogs pricing data loading...")
        
        # eBay Pricing Section - ONLY show if data is available
        if has_ebay_data:
            st.write("### 🛒 eBay Pricing")
            
            ebay_condition_pricing = record_data.get('ebay_condition_pricing', {})
            ebay_total_items_found = record_data.get('ebay_total_items_found', 0)
            
            if ebay_condition_pricing:
                # Create a table showing eBay pricing grouped by Discogs condition
                ebay_data = []
                for condition, pricing in ebay_condition_pricing.items():
                    # Calculate suggested eBay sell price - use lowest price only for CALC shipping
                    if pricing['lowest_shipping'] is None:  # CALC shipping
                        suggested_ebay_sell_at = pricing['lowest_price']
                    else:
                        suggested_ebay_sell_at = self._calculate_ebay_sell_at(pricing['lowest_price'], pricing['lowest_shipping'])
                    
                    # Format shipping cost display - show "CALC" for calculated shipping
                    shipping_display = "CALC" if pricing['lowest_shipping'] is None else f"${pricing['lowest_shipping']:.2f}"
                    
                    # Format total display - show N/A for CALC shipping
                    total_display = "N/A" if pricing['lowest_shipping'] is None else f"${pricing['lowest_price'] + pricing['lowest_shipping']:.2f}"
                    
                    # Create hyperlink for the listing - FIXED URL FORMAT
                    listing_url = pricing.get('cheapest_item_url', '')
                    if listing_url:
                        ebay_data.append({
                            'Condition': condition,
                            'Listings': pricing['count'],
                            'Lowest Price': f"${pricing['lowest_price']:.2f}",
                            'Lowest Shipping': shipping_display,
                            'Lowest Total': total_display,
                            'Suggested eBay Sell At': f"${suggested_ebay_sell_at:.2f}",
                            'Listing': listing_url
                        })
                    else:
                        ebay_data.append({
                            'Condition': condition,
                            'Listings': pricing['count'],
                            'Lowest Price': f"${pricing['lowest_price']:.2f}",
                            'Lowest Shipping': shipping_display,
                            'Lowest Total': total_display,
                            'Suggested eBay Sell At': f"${suggested_ebay_sell_at:.2f}",
                            'Listing': 'No URL'
                        })
                
                # Sort by condition from Mint to Poor, with Generic at bottom
                condition_order = [
                    'Mint (M)',
                    'Near Mint (NM or M-)', 
                    'Very Good Plus (VG+)',
                    'Very Good (VG)',
                    'Good Plus (G+)',
                    'Good (G)',
                    'Fair (F)',
                    'Poor (P)',
                    'Generic'
                ]
                
                # Sort the data
                sorted_ebay_data = []
                for condition in condition_order:
                    for item in ebay_data:
                        if item['Condition'] == condition:
                            sorted_ebay_data.append(item)
                            break
                
                if sorted_ebay_data:
                    ebay_df = pd.DataFrame(sorted_ebay_data)
                    
                    # Display the dataframe with clickable links - FIXED URL FORMAT
                    st.dataframe(
                        ebay_df,
                        width='stretch',
                        hide_index=True,
                        column_config={
                            "Listing": st.column_config.LinkColumn(
                                "Listing",
                                help="Click to view the eBay listing"
                            )
                        }
                    )
                    
                    # Let user select which eBay condition group to use for pricing
                    ebay_condition_options = list(ebay_condition_pricing.keys())
                    if ebay_condition_options:
                        # Auto-select eBay condition that matches the selected Discogs condition
                        selected_discogs_condition = record_data.get('selected_condition')
                        default_ebay_index = 0
                        if selected_discogs_condition and selected_discogs_condition in ebay_condition_options:
                            default_ebay_index = ebay_condition_options.index(selected_discogs_condition)
                        
                        selected_ebay_condition = st.selectbox(
                            "Choose eBay condition group:",
                            options=ebay_condition_options,
                            index=default_ebay_index,
                            key="ebay_condition_select"
                        )
                        
                        # Store eBay pricing data
                        if selected_ebay_condition:
                            ebay_pricing = ebay_condition_pricing[selected_ebay_condition]
                            record_data['ebay_lowest_price'] = ebay_pricing['lowest_price']
                            record_data['ebay_low_shipping'] = ebay_pricing['lowest_shipping']
                            record_data['ebay_sell_at'] = self._calculate_ebay_sell_at(
                                ebay_pricing['lowest_price'], 
                                ebay_pricing['lowest_shipping']
                            )
            else:
                st.write("No eBay pricing data available")
            
            st.divider()
        else:
            st.write("### 🛒 eBay Pricing")
            st.info("eBay pricing data loading...")

    def _calculate_ebay_sell_at(self, ebay_lowest_price, ebay_low_shipping):
        """Calculate eBay sell price from lowest price and shipping"""
        # Get SHIPPING_COST from config
        shipping_cost = st.session_state.db_manager.get_config_value('SHIPPING_COST', '5.72')
        try:
            shipping_cost = float(shipping_cost)
        except (ValueError, TypeError):
            shipping_cost = 5.72
        
        if ebay_lowest_price is not None:
            ebay_lowest_price = float(ebay_lowest_price)
            
            # For CALC shipping, use just the base price
            if ebay_low_shipping is None:
                ebay_sell_at_raw = ebay_lowest_price
            else:
                ebay_low_shipping = float(ebay_low_shipping)
                ebay_sell_at_raw = ebay_lowest_price + ebay_low_shipping - shipping_cost
            
            # Ensure not negative
            ebay_sell_at_raw = max(ebay_sell_at_raw, 0.00)
            
            # Round to nearest .49 or .99
            return self._round_to_49_or_99(ebay_sell_at_raw)
        
        return 0.0

    def _round_to_49_or_99(self, price):
        """Round to nearest .49 or .99"""
        if price <= 0:
            return 0.0
        
        base_price = math.floor(price)
        decimal_part = price - base_price
        
        if decimal_part < 0.25:
            return base_price + 0.49
        elif decimal_part < 0.75:
            return base_price + 0.49
        else:
            return base_price + 0.99

    def _delete_record(self, record_id):
        """Delete a record from the database"""
        try:
            success = st.session_state.db_manager.delete_record(record_id)
            if success:
                st.success("Record deleted successfully!")
                return True
            else:
                st.error("Failed to delete record")
                return False
        except Exception as e:
            st.error(f"Error deleting record: {e}")
            return False