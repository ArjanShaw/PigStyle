import streamlit as st
import pandas as pd
from datetime import datetime
import re

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
            # Use 3 columns for both types
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
                    discogs_median = record.get('discogs_median_price')
                    ebay_low = record.get('ebay_lowest_price')
                    ebay_low_shipping = record.get('ebay_low_shipping')  # ADDED eBay low shipping
                    
                    # SHOW THE REQUESTED FIELDS when selecting from inventory
                    record_id = record.get('id', '')
                    barcode = record.get('barcode', '')
                    file_at = record.get('file_at', '')
                    youtube_url = record.get('youtube_url', '')
                    
                    # Format the display with requested fields - INCLUDING EBAY LOW SHIPPING
                    st.write(f"**ID:** {record_id} | **Barcode:** {barcode}")
                    st.write(f"**Store Price:** ${store_price:.2f}" if store_price is not None else "**Store Price:** N/A")
                    st.write(f"**eBay Sell At:** ${ebay_sell_at:.2f}" if ebay_sell_at and ebay_sell_at > 0 else "**eBay Sell At:** N/A")
                    st.write(f"**Discogs Median:** ${discogs_median:.2f}" if discogs_median and discogs_median > 0 else "**Discogs Median:** N/A")
                    st.write(f"**eBay Low:** ${ebay_low:.2f}" if ebay_low and ebay_low > 0 else "**eBay Low:** N/A")
                    st.write(f"**eBay Low Shipping:** ${ebay_low_shipping:.2f}" if ebay_low_shipping and ebay_low_shipping > 0 else "**eBay Low Shipping:** N/A")  # ADDED
                    st.write(f"**File:** {file_at}")
                    if youtube_url:
                        st.write(f"🎵 **YouTube:** {youtube_url}")
                else:  # discogs
                    catalog = record.get('catalog_number', '')
                    st.write(f"Catalog: {catalog}")
                
            with col3:
                if st.button("Select", key=f"select_{result_type}_{i}", use_container_width=True):
                    st.session_state.selected_record = {
                        'type': 'discogs' if result_type == "Add item" else 'database',
                        'data': record,
                        'index': i
                    }
                    # Auto-trigger YouTube search when record is selected
                    if result_type == "Add item" and self.youtube_handler and self.youtube_handler.is_enabled():
                        artist = record.get('artist', '')
                        title = record.get('title', '')
                        if artist and title:
                            search_query = f"{artist} {title}"
                            youtube_results = self.youtube_handler.search_youtube_videos(search_query, record)
                            st.session_state.youtube_search_results = youtube_results
                    st.rerun()
            
            with col4:
                # DELETE BUTTON for each item in search results
                if result_type == "Edit or Delete item":
                    if st.button("🗑️ Delete", key=f"delete_{result_type}_{i}", use_container_width=True, type="secondary"):
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
                # SHOW THE REQUESTED FIELDS prominently - INCLUDING EBAY LOW SHIPPING
                record_id = record.get('id', '')
                barcode = record.get('barcode', '')
                file_at = record.get('file_at', '')
                store_price = record.get('store_price', '')
                ebay_sell_at = record.get('ebay_sell_at', '')
                discogs_median = record.get('discogs_median_price', '')
                ebay_low = record.get('ebay_lowest_price', '')
                ebay_low_shipping = record.get('ebay_low_shipping', '')  # ADDED
                youtube_url = record.get('youtube_url', '')
                
                st.write("---")
                st.write("**Record Details:**")
                st.write(f"**ID:** {record_id}")
                st.write(f"**Barcode:** {barcode}")
                st.write(f"**Store Price:** ${store_price:.2f}" if store_price and store_price > 0 else "**Store Price:** N/A")
                st.write(f"**eBay Sell At:** ${ebay_sell_at:.2f}" if ebay_sell_at and ebay_sell_at > 0 else "**eBay Sell At:** N/A")
                st.write(f"**Discogs Median:** ${discogs_median:.2f}" if discogs_median and discogs_median > 0 else "**Discogs Median:** N/A")
                st.write(f"**eBay Low:** ${ebay_low:.2f}" if ebay_low and ebay_low > 0 else "**eBay Low:** N/A")
                st.write(f"**eBay Low Shipping:** ${ebay_low_shipping:.2f}" if ebay_low_shipping and ebay_low_shipping > 0 else "**eBay Low Shipping:** N/A")  # ADDED
                st.write(f"**File Location:** {file_at}")
                if youtube_url:
                    st.write(f"🎵 **YouTube:** {youtube_url}")
                st.write("---")
            else:
                catalog = record.get('catalog_number', '')
                st.write(f"Catalog: {catalog}")
        
        if st.button("← Back to Results", key="back_to_results"):
            st.session_state.selected_record = None
            st.rerun()

    def render_edit_section(self, selected_record, add_callback, update_callback, last_condition="5", discogs_handler=None, ebay_handler=None):
        """Render the edit properties section with YouTube URL functionality"""
        st.subheader("Edit Properties")
        
        record_data = selected_record['data']
        
        # For Discogs records, fetch pricing data when the record is selected
        if selected_record['type'] == 'discogs' and not record_data.get('pricing_fetched'):
            with st.spinner("Fetching pricing data..."):
                # Fetch Discogs pricing
                release_id = record_data.get('discogs_id')
                if release_id and discogs_handler:
                    search_term = f"{record_data.get('artist', '')} {record_data.get('title', '')}"
                    pricing_data = discogs_handler.get_release_pricing(str(release_id), search_term, f"release_{release_id}")
                    
                    if pricing_data and pricing_data.get('success'):
                        record_data['discogs_lowest_price'] = pricing_data.get('lowest_price')
                        record_data['discogs_median_price'] = pricing_data.get('median_price')
                        record_data['discogs_highest_price'] = pricing_data.get('highest_price')
                
                # Fetch eBay pricing
                artist = record_data.get('artist', '')
                title = record_data.get('title', '')
                if artist and title and ebay_handler:
                    ebay_pricing = ebay_handler.get_ebay_pricing(artist, title)
                    if ebay_pricing:
                        record_data['ebay_lowest_price'] = ebay_pricing.get('ebay_lowest_price')
                        record_data['ebay_median_price'] = ebay_pricing.get('ebay_median_price')
                        record_data['ebay_highest_price'] = ebay_pricing.get('ebay_highest_price')
                        record_data['ebay_low_shipping'] = ebay_pricing.get('ebay_low_shipping')
                        record_data['ebay_low_total'] = ebay_pricing.get('ebay_low_total')
                        record_data['ebay_search_url'] = ebay_pricing.get('ebay_search_url')
                
                record_data['pricing_fetched'] = True
        
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
        
        # Show pricing information for Discogs records
        if selected_record['type'] == 'discogs':
            self._render_pricing_information(record_data)
        
        # Show YouTube search results if available (auto-triggered when record was selected)
        if selected_record['type'] == 'discogs' and self.youtube_handler and self.youtube_handler.is_enabled():
            st.subheader("🎵 YouTube Integration")
            
            # Show existing linked YouTube URL if any
            current_youtube_url = record_data.get('youtube_url', '')
            if current_youtube_url:
                st.success(f"✅ Currently linked: {current_youtube_url}")
                
                # Show option to remove link
                if st.button("❌ Remove YouTube Link", key="remove_youtube"):
                    record_data['youtube_url'] = ''
                    st.success("YouTube link removed!")
                    st.rerun()
            
            # Show YouTube search results if available
            if 'youtube_search_results' in st.session_state and st.session_state.youtube_search_results:
                st.info("Click on a video to link it to this record")
                
                for i, video in enumerate(st.session_state.youtube_search_results):
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if video.get('thumbnail'):
                            st.image(video['thumbnail'], width=120)
                        
                        # Extract video ID for embedding
                        video_id = self.youtube_handler.extract_youtube_id(video['url']) if self.youtube_handler else self._extract_youtube_id(video['url'])
                        
                        # Show play button that displays the actual video
                        if st.button(f"▶️ Play", key=f"play_{i}", use_container_width=True):
                            # Store which video to play in session state
                            st.session_state.playing_video_index = i
                    
                    with col2:
                        st.write(f"**{video.get('title', 'No title')}**")
                        st.write(f"Channel: {video.get('channel', 'Unknown')}")
                        
                        # Link this video to the record
                        if st.button("🔗 Link This Video", key=f"link_{i}", use_container_width=True):
                            # Update the record with this YouTube URL
                            record_data['youtube_url'] = video['url']
                            st.success("✅ YouTube video will be linked when record is added!")
                            # Clear search results
                            st.session_state.youtube_search_results = []
                            st.rerun()
                    
                    # Show embedded video if this is the one being played
                    if st.session_state.get('playing_video_index') == i and video_id:
                        st.components.v1.iframe(
                            f"https://www.youtube.com/embed/{video_id}",
                            width=400,
                            height=225
                        )
                    
                    st.divider()
        
        # Single submit button - only enable if genre is selected
        if selected_record['type'] == 'discogs':
            if st.button("Add to Database", use_container_width=True, disabled=not genre, key="add_to_database"):
                # Get the file_at value for confirmation message
                file_at_value = self._calculate_file_at(record_data['artist'], genre)
                success, record_id = add_callback(condition, genre)
                if success:
                    # Show confirmation message with artist, title, and fileat
                    st.success(f"✅ Record added successfully!\\n**Artist:** {record_data['artist']}\\n**Title:** {record_data['title']}\\n**File Location:** {file_at_value}")
                    st.session_state.record_added = True
        else:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Update Record", use_container_width=True, disabled=not genre, key="update_record"):
                    # Include YouTube URL in updates
                    updates = {
                        'condition': condition,
                        'genre_id': self._get_genre_id(genre),
                        'youtube_url': record_data.get('youtube_url', '')
                    }
                    success = st.session_state.db_manager.update_record(record_data['id'], updates)
                    if success:
                        st.success("✅ Record updated successfully!")
                        st.session_state.records_updated += 1
                        st.session_state.selected_record = None
                        st.rerun()
                    else:
                        st.error("❌ Failed to update record")

    def _render_pricing_information(self, record_data):
        """Render pricing information for Discogs records"""
        st.subheader("💰 Pricing Information")
        
        # Get pricing data from record
        discogs_min = record_data.get('discogs_lowest_price')
        discogs_median = record_data.get('discogs_median_price')
        discogs_max = record_data.get('discogs_highest_price')
        
        ebay_min = record_data.get('ebay_lowest_price')
        ebay_median = record_data.get('ebay_median_price')
        ebay_max = record_data.get('ebay_highest_price')
        ebay_low_shipping = record_data.get('ebay_low_shipping')
        ebay_low_total = record_data.get('ebay_low_total')
        ebay_search_url = record_data.get('ebay_search_url')
        
        # Calculate suggested prices using existing logic
        suggested_store_price = self._calculate_suggested_store_price(discogs_median)
        suggested_ebay_price = self._calculate_suggested_ebay_price(ebay_min, ebay_low_shipping, discogs_median)
        
        # Display pricing in two columns
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Discogs Pricing**")
            st.write(f"Min: ${discogs_min:.2f}" if discogs_min is not None else "Min: N/A")
            st.write(f"Median: ${discogs_median:.2f}" if discogs_median is not None else "Median: N/A")
            st.write(f"Max: ${discogs_max:.2f}" if discogs_max is not None else "Max: N/A")
            st.write(f"**Suggested Store Price: ${suggested_store_price:.2f}**")
        
        with col2:
            st.write("**eBay Pricing**")
            
            # Show Min as base + shipping total with link
            if ebay_min is not None and ebay_low_shipping is not None:
                min_total = ebay_min + ebay_low_shipping
                shipping_display = f" (shipping ${ebay_low_shipping:.2f})" if ebay_low_shipping > 0 else " (free shipping)"
                if ebay_search_url:
                    st.markdown(f"Min: [${min_total:.2f}{shipping_display}*]({ebay_search_url})")
                else:
                    st.write(f"Min: ${min_total:.2f}{shipping_display}")
            else:
                st.write("Min: N/A")
            
            st.write(f"Median: ${ebay_median:.2f}" if ebay_median is not None else "Median: N/A")
            st.write(f"Max: ${ebay_max:.2f}" if ebay_max is not None else "Max: N/A")
            st.write(f"**Suggested eBay Price: ${suggested_ebay_price:.2f}**")
            
            # Add footnote for eBay link
            if ebay_search_url:
                st.caption(f"*[Click to verify on eBay]({ebay_search_url})")

    def _calculate_suggested_store_price(self, discogs_median_price):
        """Calculate suggested store price using existing logic"""
        if not discogs_median_price or discogs_median_price <= 0:
            return 0.0
        
        # Get MIN_STORE_PRICE from config
        min_store_price = st.session_state.db_manager.get_config_value('MIN_STORE_PRICE', '1.99')
        min_store_price = float(min_store_price)
        
        # Use the same rounding function as eBay sell prices
        store_price = self._round_down_to_49_or_99(float(discogs_median_price))
        
        # Apply MIN_STORE_PRICE minimum
        store_price = max(store_price, min_store_price)
        
        return store_price

    def _calculate_suggested_ebay_price(self, ebay_lowest_price, ebay_low_shipping, discogs_median_price):
        """Calculate suggested eBay price using existing logic"""
        # Get SHIPPING_COST from config
        shipping_cost = st.session_state.db_manager.get_config_value('SHIPPING_COST', '5.72')
        shipping_cost = float(shipping_cost)
        
        if ebay_lowest_price is not None and ebay_low_shipping is not None:
            # Convert to float to ensure numeric operations
            ebay_lowest_price = float(ebay_lowest_price)
            ebay_low_shipping = float(ebay_low_shipping)
            
            # Calculate ebay_sell_at = ebay_lowest_price + ebay_low_shipping - SHIPPING_COST
            ebay_sell_at_raw = ebay_lowest_price + ebay_low_shipping - shipping_cost
            
            # Ensure ebay_sell_at is not negative - hardcoded minimum of 0.00
            ebay_sell_at_raw = max(ebay_sell_at_raw, 0.00)
            
            # Cap ebay_sell_at at discogs_median_price if available
            if discogs_median_price is not None and discogs_median_price > 0:
                discogs_median = float(discogs_median_price)
                if ebay_sell_at_raw > discogs_median:
                    # If calculated price exceeds Discogs median, use Discogs median rounded down
                    ebay_sell_at = self._round_down_to_49_or_99(discogs_median)
                else:
                    # Use calculated price rounded down
                    ebay_sell_at = self._round_down_to_49_or_99(ebay_sell_at_raw)
            else:
                # No Discogs price, use calculated price rounded down
                ebay_sell_at = self._round_down_to_49_or_99(ebay_sell_at_raw)
        else:
            # No eBay data - use Discogs median price
            if discogs_median_price is not None and discogs_median_price > 0:
                # Round down Discogs median price for eBay
                ebay_sell_at = self._round_down_to_49_or_99(float(discogs_median_price))
            else:
                # No pricing data available
                ebay_sell_at = 0.0
        
        # Apply hardcoded minimum for eBay sell price
        return max(ebay_sell_at, 0.00)

    def _round_down_to_49_or_99(self, price):
        """Round down to nearest .49 or .99 that is less than or equal to original price"""
        import math
        
        if price <= 0:
            return 0.0
        
        # Check if price already ends with .49 or .99
        if abs(price % 1 - 0.49) < 0.001 or abs(price % 1 - 0.99) < 0.001:
            return price
        
        base_price = math.floor(price)
        
        # Calculate candidate prices
        candidate_99 = base_price + 0.99
        candidate_49 = base_price + 0.49
        
        # Return the highest candidate that is <= original price
        if candidate_99 <= price:
            return candidate_99
        elif candidate_49 <= price:
            return candidate_49
        else:
            # If both are too high, go down one dollar and use .99
            return (base_price - 1) + 0.99

    def _calculate_file_at(self, artist, genre):
        """Calculate file_at value for an artist and genre"""
        if not artist:
            return "?"
        
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

    def _extract_youtube_id(self, url):
        """Extract YouTube video ID from URL (fallback method)"""
        # Handle various YouTube URL formats
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?]+)',
            r'youtube\.com\/embed\/([^&\n?]+)',
            r'youtube\.com\/v\/([^&\n?]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _get_genre_id(self, genre_name):
        """Get genre ID for a genre name"""
        if not genre_name:
            return None
        conn = st.session_state.db_manager._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM genres WHERE genre_name = ?', (genre_name,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

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

    def _map_discogs_genre(self, discogs_genre):
        """Map Discogs genre to existing genres in database"""
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

    def render_checkout_section(self, checkout_records, checkout_callback):
        """Render checkout section"""
        if not checkout_records:
            return
        
        st.subheader("Checkout")
        st.info("Checkout functionality is not available. The status column has been removed from the database.")

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
                            st.session_state.records_updated = st.session_state.get('records_updated', 0) + 1
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
        success = st.session_state.db_manager.delete_record(record_id)
        if success:
            st.session_state.records_updated = st.session_state.get('records_updated', 0) + 1
            return True
        else:
            st.error("Failed to delete record")
            return False

    def _get_all_genres(self):
        """Get all available genres from database"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('SELECT genre_name FROM genres ORDER BY genre_name', conn)
        conn.close()
        return df['genre_name'].tolist()

    def _get_unique_genres(self):
        """Get unique genres from inventory"""
        conn = st.session_state.db_manager._get_connection()
        genres_df = pd.read_sql(
            "SELECT DISTINCT genre FROM records_with_genres WHERE genre IS NOT NULL AND genre != '' ORDER BY genre",
            conn
        )
        conn.close()
        
        if len(genres_df) > 0:
            return genres_df['genre'].tolist()
        else:
            return ["ROCK", "JAZZ", "HIP-HOP", "ELECTRONIC", "POP", "METAL", "FOLK", "SOUL"]

    def _export_genre_csv(self):
        """Export ID, Artist, Title, and Genre for all inventory records"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql(
            "SELECT id, artist, title, genre FROM records_with_genres ORDER BY artist, title",
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