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
                
                st.write("---")
                st.write("**Record Details:**")
                st.write(f"**ID:** {record_id}")
                st.write(f"**Barcode:** {barcode}")
                st.write(f"**Catalog:** {catalog_number}" if catalog_number else "**Catalog:** N/A")
                st.write(f"**Genre:** {genre}" if genre else "**Genre:** N/A")
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
        
        if st.button("← Back to Results", key="back_to_results"):
            st.session_state.selected_record = None
            st.rerun()

    def render_edit_section(self, selected_record, add_callback, update_callback, discogs_handler=None, ebay_handler=None):
        """Render the edit properties section - SIMPLIFIED VERSION WITHOUT LOADING SCREEN"""
        
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
        
        # Add consignment dropdown for both new and existing records
        consignment_session_id = self._render_consignment_dropdown(record_data)
        if consignment_session_id:
            record_data['consignment_session_id'] = consignment_session_id
        else:
            # Clear consignment if "Store Owned" is selected
            record_data['consignment_session_id'] = None
        
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
        
        # Show genre dropdown (NOW VISIBLE AFTER ALL API CALLS COMPLETE)
        suggested_genre = self._get_suggested_genre(record_data)
        
        col1, col2 = st.columns(2)
        with col1:
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
        
        # Show ALL pricing information (now fully loaded after ALL API calls)
        self._render_pricing_information(record_data)
        
        # Show YouTube search results if available (now fully loaded)
        if self.youtube_handler and self.youtube_handler.is_enabled():
            st.subheader("🎵 YouTube Integration")
            
            # Show existing linked YouTube URL if any
            current_youtube_url = record_data.get('youtube_url', '')
            if current_youtube_url:
                st.success(f"✅ Currently linked: {current_youtube_url}")
                
                # Show option to remove link
                if st.button("❌ Remove YouTube Link", key="remove_youtube", width='stretch'):
                    record_data['youtube_url'] = ''
                    st.success("YouTube link removed!")
                    st.rerun()
            
            # Show YouTube search results if available
            if 'youtube_search_results' in st.session_state and st.session_state.youtube_search_results:
                st.info("Click on a video to link it to this record")
                
                # Group by track if available
                track_results = [r for r in st.session_state.youtube_search_results if r.get('type') == 'track']
                album_results = [r for r in st.session_state.youtube_search_results if r.get('type') == 'album']
                
                if track_results:
                    st.write("**🎵 Individual Track Recordings:**")
                    for i, video in enumerate(track_results):
                        self._render_youtube_video(video, i, record_data)
                
                if album_results:
                    st.write("**📀 Album Content:**")
                    for i, video in enumerate(album_results, start=len(track_results)):
                        self._render_youtube_video(video, i, record_data)
        
        # Single submit button - only enable if genre is selected
        if st.button("Add to Database", width='stretch', disabled=not genre, key="add_to_database"):
            # Get the file_at value for confirmation message
            file_at_value = self._calculate_file_at(record_data['artist'], genre)
            success, record_id = add_callback(genre)
            if success:
                # Show confirmation message with artist, title, and fileat
                st.success(f"✅ Record added successfully!\\n**Artist:** {record_data['artist']}\\n**Title:** {record_data['title']}\\n**File Location:** {file_at_value}")
                st.session_state.record_added = True

    def _render_youtube_video(self, video, index, record_data):
        """Render a single YouTube video result"""
        col1, col2 = st.columns([1, 3])
        with col1:
            if video.get('thumbnail'):
                st.image(video['thumbnail'], width=120)
            
            # Extract video ID for embedding
            video_id = self.youtube_handler.extract_youtube_id(video['url']) if self.youtube_handler else self._extract_youtube_id(video['url'])
            
            # Show play button that displays the actual video
            if st.button(f"▶️ Play", key=f"play_{index}", width='stretch'):
                # Store which video to play in session state
                st.session_state.playing_video_index = index
        
        with col2:
            st.write(f"**{video.get('title', 'No title')}**")
            st.write(f"Channel: {video.get('channel', 'Unknown')}")
            
            # Show track info if it's a track recording
            if video.get('type') == 'track' and video.get('track_title'):
                st.write(f"🎵 **Track:** {video['track_title']}")
            
            # Link this video to the record
            if st.button("🔗 Link This Video", key=f"link_{index}", width='stretch'):
                # Update the record with this YouTube URL
                record_data['youtube_url'] = video['url']
                st.success("✅ YouTube video will be linked when record is added!")
                # Clear search results
                st.session_state.youtube_search_results = []
                st.rerun()
        
        # Show embedded video if this is the one being played
        if st.session_state.get('playing_video_index') == index and video_id:
            st.components.v1.iframe(
                f"https://www.youtube.com/embed/{video_id}",
                width=400,
                height=225
            )
        
        st.divider()
    
    def _fetch_all_data_sync(self, record_data, discogs_handler, ebay_handler):
        """Fetch all required data synchronously (blocking calls) - ALL APIs must complete"""
        # Step 1: Fetch Discogs pricing (BLOCKING)
        release_id = record_data.get('discogs_id')
        if discogs_handler and release_id:
            pricing_data = discogs_handler.get_release_statistics_pricing(str(release_id))
            record_data['price_suggestions'] = pricing_data.get('price_suggestions', {})
            record_data['total_conditions'] = pricing_data.get('total_conditions', 0)
        
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
            track_titles = []
            if discogs_handler and release_id:
                track_titles = discogs_handler.get_release_tracklist(release_id)
            
            search_query = f"{artist} {title}"
            youtube_results = self.youtube_handler.search_youtube_videos(search_query, record_data, track_titles)
            st.session_state.youtube_search_results = youtube_results

    def _render_pricing_information(self, record_data):
        """Render ALL pricing information - ONLY called after ALL API calls complete"""
        
        # Check if we have the required data from ALL APIs
        has_discogs_data = 'price_suggestions' in record_data
        has_ebay_data = 'ebay_condition_pricing' in record_data
        has_youtube_data = 'youtube_search_results' in st.session_state
        
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
                        
                        # Try to find matching eBay condition
                        if selected_discogs_condition:
                            for i, ebay_condition in enumerate(ebay_condition_options):
                                if ebay_condition == selected_discogs_condition:
                                    default_ebay_index = i
                                    break
                        
                        selected_ebay_condition = st.selectbox(
                            "Choose eBay condition group:",
                            options=ebay_condition_options,
                            index=default_ebay_index,
                            key="ebay_condition_select"
                        )
                        
                        if selected_ebay_condition:
                            selected_pricing = ebay_condition_pricing[selected_ebay_condition]
                            # Calculate the suggested eBay sell price
                            if selected_pricing['lowest_shipping'] is None:  # CALC shipping
                                suggested_ebay_sell_at = selected_pricing['lowest_price']
                            else:
                                suggested_ebay_sell_at = self._calculate_ebay_sell_at(selected_pricing['lowest_price'], selected_pricing['lowest_shipping'])
                            
                            record_data['ebay_selected_condition'] = selected_ebay_condition
                            record_data['ebay_lowest_price'] = selected_pricing['lowest_price']
                            record_data['ebay_low_shipping'] = selected_pricing['lowest_shipping']
                            record_data['ebay_listings_count'] = selected_pricing['count']
                            record_data['ebay_low_url'] = selected_pricing['cheapest_item_url']
                            record_data['ebay_sell_at'] = suggested_ebay_sell_at  # Store calculated sell price
                            
                            st.success(f"✅ Selected eBay {selected_ebay_condition} condition group")
                            st.write(f"**Suggested eBay Sell At:** ${suggested_ebay_sell_at:.2f}")
                            
                            # Format shipping display for the calculation breakdown
                            if selected_pricing['lowest_shipping'] is None:
                                st.write(f"**Based on:** ${selected_pricing['lowest_price']:.2f} (lowest price only - CALC shipping)")
                            else:
                                st.write(f"**Based on:** ${selected_pricing['lowest_price']:.2f} (lowest) + ${selected_pricing['lowest_shipping']:.2f} shipping")
                
                st.write(f"**Total eBay items found:** {ebay_total_items_found}")
            else:
                st.write("No eBay pricing data available")
            
            st.divider()
        else:
            st.write("### 🛒 eBay Pricing")
            st.info("eBay pricing data loading...")
        
        # Store Price Calculation Section - ONLY show if we have Discogs data
        if has_discogs_data:
            st.write("### 🏪 Store Price Calculation")
            
            # Calculate store price using current configuration
            selected_price = record_data.get('selected_price')
            store_price = self._calculate_store_price(selected_price)
            
            # Get current configuration for display
            lowest_multiplier = float(st.session_state.db_manager.get_config_value('STORE_PRICE_LOWEST_MULTIPLIER', '1.1'))
            estimated_multiplier = float(st.session_state.db_manager.get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', '0.9'))
            minimum_price = float(st.session_state.db_manager.get_config_value('STORE_PRICE_MINIMUM', '4.99'))
            
            # Show calculation breakdown
            col1, col2 = st.columns(2)
            with col1:
                if selected_price:
                    suggested_calc = selected_price * estimated_multiplier
                    st.write(f"**Selected × {estimated_multiplier}:** ${selected_price:.2f} × {estimated_multiplier} = ${suggested_calc:.2f}")
                
                st.write(f"**Minimum Price:** ${minimum_price:.2f}")
            
            with col2:
                st.metric("Calculated Store Price", f"${store_price:.2f}", 
                         help="Based on highest of: (Selected × Multiplier) or Minimum Price")

    def _render_consignment_dropdown(self, record_data=None):
        """Render consignment session dropdown for record addition - UPDATED to handle existing assignments"""
        try:
            # Get all consignment sessions for dropdown
            sessions_df = st.session_state.db_manager.get_all_consignment_sessions()
            
            if len(sessions_df) == 0:
                return None
            
            # Create options for dropdown
            options = ["Store Owned"]  # Default option
            
            # Create mapping for session selection
            session_mapping = {}
            for _, session in sessions_df.iterrows():
                option_text = f"{session['consignor_name']} - {session['session_date']} ({session['commission_rate']*100}%, {session['store_return_days']} days)"
                options.append(option_text)
                session_mapping[option_text] = session['id']
            
            # Store mapping in session state for retrieval
            st.session_state.consignment_session_mapping = session_mapping
            
            # Determine default selection
            default_index = 0  # Default to "Store Owned"
            
            # If editing existing record with consignment, find the matching session
            if record_data and 'consignment_session_id' in record_data and record_data['consignment_session_id']:
                existing_session_id = record_data['consignment_session_id']
                # Find the session in the mapping
                for option_text, session_id in session_mapping.items():
                    if session_id == existing_session_id:
                        # Find the index of this option
                        default_index = options.index(option_text)
                        break
            
            # Render dropdown
            selected_option = st.selectbox(
                "Consignment Session:",
                options=options,
                index=default_index,
                key="consignment_session_select"
            )
            
            # Return session ID if consignment selected, None for store owned
            if selected_option == "Store Owned":
                return None
            else:
                return session_mapping.get(selected_option)
            
        except Exception as e:
            st.error(f"Error loading consignment sessions: {e}")
            return None

    def _calculate_ebay_sell_at(self, ebay_lowest_price, ebay_low_shipping):
        """Calculate eBay sell price from lowest eBay price and shipping"""
        # Get SHIPPING_COST from config
        shipping_cost = st.session_state.db_manager.get_config_value('SHIPPING_COST', '5.72')
        try:
            shipping_cost = float(shipping_cost)
        except (ValueError, TypeError):
            shipping_cost = 5.72
        
        if ebay_lowest_price is not None and ebay_low_shipping is not None:
            # Convert to float to ensure numeric operations
            ebay_lowest_price = float(ebay_lowest_price)
            ebay_low_shipping = float(ebay_low_shipping)
            
            # Calculate ebay_sell_at = ebay_lowest_price + ebay_low_shipping - SHIPPING_COST
            ebay_sell_at_raw = ebay_lowest_price + ebay_low_shipping - shipping_cost
            
            # Ensure ebay_sell_at is not negative - hardcoded minimum of 0.00
            ebay_sell_at_raw = max(ebay_sell_at_raw, 0.00)
            
            # Round down to nearest .49 or .99
            ebay_sell_at = self._round_down_to_49_or_99(ebay_sell_at_raw)
        else:
            # No eBay data available
            ebay_sell_at = 0.0
        
        return ebay_sell_at

    def _round_down_to_49_or_99(self, price):
        """Round down to nearest .49 or .99 that is less than or equal to original price"""
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

    def _get_condition_description(self, condition):
        """Get brief description for each Discogs condition"""
        condition_descriptions = {
            "Mint (M)": "Still sealed, perfect condition",
            "Near Mint (NM or M-)": "Like new, minimal signs of handling",
            "Very Good Plus (VG+)": "Light surface marks, plays perfectly",
            "Very Good (VG)": "Visible wear but plays well",
            "Good Plus (G+)": "Significant wear, some surface noise",
            "Good (G)": "Heavy wear, noticeable surface noise",
            "Fair (F)": "Poor condition, plays with difficulty",
            "Poor (P)": "Badly damaged, may be unplayable",
            "Generic": "Standard used condition",
            "Not Graded": "Condition not specified"
        }
        
        # Try exact match first
        if condition in condition_descriptions:
            return condition_descriptions[condition]
        
        # Try partial matches
        for key, description in condition_descriptions.items():
            if condition.lower() in key.lower() or key.lower() in condition.lower():
                return description
        
        # Default description
        return "Used record condition"

    def _calculate_store_price(self, selected_price):
        """Calculate store price using configurable parameters"""
        # Get current configuration
        lowest_multiplier = float(st.session_state.db_manager.get_config_value('STORE_PRICE_LOWEST_MULTIPLIER', '1.1'))
        estimated_multiplier = float(st.session_state.db_manager.get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', '0.9'))
        minimum_price = float(st.session_state.db_manager.get_config_value('STORE_PRICE_MINIMUM', '4.99'))
        
        candidates = []
        
        if selected_price and selected_price > 0:
            # Use the selected price with the estimated multiplier
            candidates.append(selected_price * estimated_multiplier)
        
        if candidates:
            raw_price = max(candidates)
            raw_price = max(raw_price, minimum_price)
        else:
            raw_price = minimum_price
        
        # Round to nearest .49 or .99
        store_price = self._round_to_49_or_99(raw_price)
        
        return store_price

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
        
        # Priority 1: Check if artist exists in database and get most common genre
        if artist:
            artist_genre = self._get_artist_most_common_genre(artist)
            if artist_genre:
                return artist_genre
        
        # Priority 2: Try to get genre from Discogs data if available
        if 'release_data' in record_data:
            discogs_genre = self._extract_discogs_genre(record_data['release_data'])
            if discogs_genre:
                return discogs_genre
        
        return ""

    def _extract_discogs_genre(self, release_data):
        """Extract genre from Discogs release data"""
        try:
            if not release_data:
                return ""
            
            # Discogs stores genres in a list under 'genres' key
            genres = release_data.get('genres', [])
            if genres and len(genres) > 0:
                # Return the first genre (primary genre)
                return genres[0]
            
            # Also check styles which are more specific sub-genres
            styles = release_data.get('styles', [])
            if styles and len(styles) > 0:
                return styles[0]
                
        except Exception as e:
            print(f"Error extracting Discogs genre: {e}")
        
        return ""

    def _get_suggestion_source(self, record_data, suggested_genre):
        """Get the source of the genre suggestion"""
        artist = record_data.get('artist', '')
        
        # Check if it came from artist history
        if artist:
            artist_genre = self._get_artist_most_common_genre(artist)
            if artist_genre == suggested_genre:
                return "artist history"
        
        # Check if it came from Discogs data
        if 'release_data' in record_data:
            discogs_genre = self._extract_discogs_genre(record_data['release_data'])
            if discogs_genre == suggested_genre:
                return "Discogs data"
        
        return "unknown"

    def _get_artist_most_common_genre(self, artist):
        """Get the most common genre for an artist from existing records"""
        conn = st.session_state.db_manager._get_connection()
        df = pd.read_sql('''
            SELECT g.genre_name as genre, COUNT(*) as count 
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.artist = ? AND g.genre_name IS NOT NULL AND g.genre_name != '' 
            GROUP BY g.genre_name 
            ORDER BY count DESC 
            LIMIT 1
        ''', conn, params=(artist,))
        conn.close()
        
        if len(df) > 0:
            return df.iloc[0]['genre']
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
            if st.button("📤 Export Genre CSV", width='stretch', help="Export ID, Artist, Title, and Genre for all inventory records", key="export_genre_csv"):
                self._export_genre_csv()

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

    def _get_all_genres(self):
        """Get all available genres"""
        try:
            genres_df = st.session_state.db_manager.get_all_genres()
            return genres_df['genre_name'].tolist()
        except Exception as e:
            st.error(f"Error loading genres: {e}")
            return []