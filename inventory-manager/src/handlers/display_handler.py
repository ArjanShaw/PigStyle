import streamlit as st
import pandas as pd
from datetime import datetime
import re
import math

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
                    discogs_lowest = record.get('discogs_lowest_price')
                    discogs_estimated = record.get('discogs_estimated_price')
                    ebay_low = record.get('ebay_lowest_price')
                    ebay_low_shipping = record.get('ebay_low_shipping')
                    
                    # SHOW THE REQUESTED FIELDS when selecting from inventory
                    record_id = record.get('id', '')
                    barcode = record.get('barcode', '')
                    file_at = record.get('file_at', '')
                    youtube_url = record.get('youtube_url', '')
                    
                    # Format the display with requested fields
                    st.write(f"**ID:** {record_id} | **Barcode:** {barcode}")
                    st.write(f"**Store Price:** ${store_price:.2f}" if store_price is not None else "**Store Price:** N/A")
                    st.write(f"**eBay Sell At:** ${ebay_sell_at:.2f}" if ebay_sell_at and ebay_sell_at > 0 else "**eBay Sell At:** N/A")
                    st.write(f"**Discogs Lowest:** ${discogs_lowest:.2f}" if discogs_lowest and discogs_lowest > 0 else "**Discogs Lowest:** N/A")
                    st.write(f"**Discogs Estimated:** ${discogs_estimated:.2f}" if discogs_estimated and discogs_estimated > 0 else "**Discogs Estimated:** N/A")
                    st.write(f"**eBay Low:** ${ebay_low:.2f}" if ebay_low and ebay_low > 0 else "**eBay Low:** N/A")
                    st.write(f"**eBay Low Shipping:** ${ebay_low_shipping:.2f}" if ebay_low_shipping and ebay_low_shipping > 0 else "**eBay Low Shipping:** N/A")
                    st.write(f"**File Location:** {file_at}")
                    if youtube_url:
                        st.write(f"🎵 **YouTube:** {youtube_url}")
                else:  # discogs
                    catalog = record.get('catalog_number', '')
                    year = record.get('year', '')
                    format_info = record.get('format', '')
                    label_info = record.get('label', '')
                    country = record.get('country', '')
                    
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
                    
                    if info_lines:
                        st.write(" | ".join(info_lines))
                    else:
                        st.write("*No additional info*")
                    
                    st.write("*Pricing data will be loaded when you select this record*")
                
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
                # SHOW THE REQUESTED FIELDS prominently
                record_id = record.get('id', '')
                barcode = record.get('barcode', '')
                file_at = record.get('file_at', '')
                store_price = record.get('store_price', '')
                ebay_sell_at = record.get('ebay_sell_at', '')
                discogs_lowest = record.get('discogs_lowest_price', '')
                discogs_estimated = record.get('discogs_estimated_price', '')
                ebay_low = record.get('ebay_lowest_price', '')
                ebay_low_shipping = record.get('ebay_low_shipping', '')
                youtube_url = record.get('youtube_url', '')
                
                st.write("---")
                st.write("**Record Details:**")
                st.write(f"**ID:** {record_id}")
                st.write(f"**Barcode:** {barcode}")
                st.write(f"**Store Price:** ${store_price:.2f}" if store_price and store_price > 0 else "**Store Price:** N/A")
                st.write(f"**eBay Sell At:** ${ebay_sell_at:.2f}" if ebay_sell_at and ebay_sell_at > 0 else "**eBay Sell At:** N/A")
                st.write(f"**Discogs Lowest:** ${discogs_lowest:.2f}" if discogs_lowest and discogs_lowest > 0 else "**Discogs Lowest:** N/A")
                st.write(f"**Discogs Estimated:** ${discogs_estimated:.2f}" if discogs_estimated and discogs_estimated > 0 else "**Discogs Estimated:** N/A")
                st.write(f"**eBay Low:** ${ebay_low:.2f}" if ebay_low and ebay_low > 0 else "**eBay Low:** N/A")
                st.write(f"**eBay Low Shipping:** ${ebay_low_shipping:.2f}" if ebay_low_shipping and ebay_low_shipping > 0 else "**eBay Low Shipping:** N/A")
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
                
                if info_lines:
                    for line in info_lines:
                        st.write(line)
        
        if st.button("← Back to Results", key="back_to_results"):
            st.session_state.selected_record = None
            st.rerun()

    def render_edit_section(self, selected_record, add_callback, update_callback, discogs_handler=None, ebay_handler=None):
        """Render the edit properties section with YouTube URL functionality - NO CONDITION DROPDOWN"""
        
        st.subheader("Edit Properties")
        
        record_data = selected_record['data']
        
        # For Discogs records, fetch pricing data ONLY when user selects the record (single API call)
        if selected_record['type'] == 'discogs' and not record_data.get('pricing_fetched'):
            release_id = record_data.get('discogs_id')
            if release_id and discogs_handler:
                with st.spinner("Fetching pricing data..."):
                    # GET ALL PRICE SUGGESTIONS
                    pricing_data = discogs_handler.get_release_statistics_pricing(str(release_id))
                    if pricing_data:
                        record_data['price_suggestions'] = pricing_data.get('price_suggestions', {})
                        record_data['total_conditions'] = pricing_data.get('total_conditions', 0)
                    else:
                        # Fallback to get_release_data if no marketplace data found
                        pricing_data = discogs_handler.get_release_data(str(release_id), "selected_record")
                        if pricing_data and pricing_data.get('success'):
                            record_data['price_suggestions'] = pricing_data.get('price_suggestions', {})
                            record_data['image_url'] = pricing_data.get('image_url') or record_data.get('image_url', '')
                            record_data['total_conditions'] = pricing_data.get('total_conditions', 0)
            
            # Fetch eBay pricing separately
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
                    record_data['ebay_listings_count'] = ebay_pricing.get('ebay_listings_count', 0)
                    record_data['ebay_total_items_found'] = ebay_pricing.get('ebay_total_items_found', 0)
                    record_data['ebay_lowest_item_details'] = ebay_pricing.get('ebay_lowest_item_details')
                    record_data['ebay_lowest_item_url'] = ebay_pricing.get('ebay_lowest_item_url')
            
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
        
        # Show pricing information for Discogs records - BOTH Discogs and eBay pricing
        if selected_record['type'] == 'discogs':
            self._render_pricing_information(record_data, discogs_handler, ebay_handler)
        
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
                success, record_id = add_callback(genre)
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

    def _render_pricing_information(self, record_data, discogs_handler=None, ebay_handler=None):
        """Render BOTH Discogs and eBay pricing information in edit section"""
        st.subheader("💰 Pricing Information")
        
        # Discogs Pricing Section
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
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Let user select a condition
                condition_options = list(price_suggestions.keys())
                selected_condition = st.selectbox(
                    "Choose condition for this record:",
                    options=condition_options,
                    key="condition_select"
                )
                
                # Store the selected condition and price in record_data
                if selected_condition:
                    record_data['selected_condition'] = selected_condition
                    record_data['selected_price'] = price_suggestions[selected_condition]
                    st.success(f"✅ Selected: {selected_condition} - ${price_suggestions[selected_condition]:.2f}")
        else:
            st.write("No Discogs pricing data available")
        
        # DISCOGS API LOGS - RIGHT AFTER DISCOGS PRICING
        if 'api_details' in st.session_state:
            discogs_apis = [title for title in st.session_state.api_details.keys() if 'Discogs' in title]
            if discogs_apis:
                with st.expander("📡 Discogs API Requests & Responses", expanded=False):
                    for api_title in discogs_apis:
                        if api_title in st.session_state.api_details:
                            details = st.session_state.api_details[api_title]
                            duration = details.get('duration', 'N/A')
                            display_title = f"{api_title} ({duration}s)" if duration != 'N/A' else api_title
                            with st.expander(display_title, expanded=False):
                                request_data = details.get('raw_request', details.get('request', {}))
                                st.write("**Request:**")
                                st.json(request_data)
                                
                                response_data = details.get('raw_response', details.get('response', {}))
                                if response_data:
                                    st.write("**Response:**")
                                    st.json(response_data)
        
        st.divider()
        
        # eBay Pricing Section
        st.write("### 🛒 eBay Pricing")
        
        # Get eBay pricing data from record
        ebay_min = record_data.get('ebay_lowest_price')
        ebay_median = record_data.get('ebay_median_price')
        ebay_max = record_data.get('ebay_highest_price')
        ebay_low_shipping = record_data.get('ebay_low_shipping')
        ebay_low_total = record_data.get('ebay_low_total')
        ebay_listings_count = record_data.get('ebay_listings_count', 0)
        ebay_total_items_found = record_data.get('ebay_total_items_found', 0)
        ebay_lowest_item_details = record_data.get('ebay_lowest_item_details')
        ebay_lowest_item_url = record_data.get('ebay_lowest_item_url')
        
        # Show eBay pricing metrics
        if ebay_median is not None:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Lowest Price", f"${ebay_min:.2f}" if ebay_min else "N/A")
            with col2:
                st.metric("Median Price", f"${ebay_median:.2f}")
            with col3:
                st.metric("Highest Price", f"${ebay_max:.2f}" if ebay_max else "N/A")
            
            st.write(f"**Listings with prices:** {ebay_listings_count}")
            st.write(f"**Total items found:** {ebay_total_items_found}")
            
            # Show eBay API requests/responses IMMEDIATELY after eBay pricing section
            if 'api_details' in st.session_state:
                ebay_apis = [title for title in st.session_state.api_details.keys() if 'eBay' in title or 'eBay' in title]
                if ebay_apis:
                    with st.expander("📡 eBay API Requests & Responses", expanded=False):
                        for api_title in ebay_apis:
                            if api_title in st.session_state.api_details:
                                details = st.session_state.api_details[api_title]
                                duration = details.get('duration', 'N/A')
                                display_title = f"{api_title} ({duration}s)" if duration != 'N/A' else api_title
                                with st.expander(display_title, expanded=False):
                                    request_data = details.get('raw_request', details.get('request', {}))
                                    st.write("**Request:**")
                                    st.json(request_data)
                                    
                                    response_data = details.get('raw_response', details.get('response', {}))
                                    if response_data:
                                        st.write("**Response:**")
                                        st.json(response_data)
            
            # Show cheapest listing details in expandable section
            if ebay_lowest_item_details:
                with st.expander("📋 Cheapest eBay Listing Details", expanded=False):
                    self._render_ebay_listing_details(ebay_lowest_item_details, ebay_lowest_item_url)
        
        else:
            st.write("No eBay pricing data available")
        
        # Store Price Calculation Section
        st.divider()
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

    def _render_ebay_listing_details(self, item_details, item_url):
        """Render detailed information about the cheapest eBay listing"""
        if not item_details:
            st.write("No detailed listing information available")
            return
        
        # Display the listing URL
        if item_url:
            st.write(f"**Listing URL:** [View on eBay]({item_url})")
            st.divider()
        
        # Extract item specifics
        item_specifics = item_details.get('itemSpecifics', {}).get('nameValuePairs', [])
        
        # Extract condition information
        condition = item_details.get('condition', '')
        condition_id = item_details.get('conditionId', '')
        
        # Extract description/short description
        short_description = item_details.get('shortDescription', '')
        description = item_details.get('description', '')
        
        # Extract shipping information
        shipping_options = item_details.get('shippingOptions', [])
        
        # Display item specifics
        st.write("**Item Specifics:**")
        if item_specifics:
            for specific in item_specifics:
                name = specific.get('name', '')
                value = specific.get('value', '')
                if name and value:
                    st.write(f"- **{name}:** {value}")
        else:
            st.write("No item specifics available")
        
        st.divider()
        
        # Display condition information
        st.write("**Condition Information:**")
        if condition:
            st.write(f"- **Condition:** {condition}")
        if condition_id:
            st.write(f"- **Condition ID:** {condition_id}")
        
        # Look for grading information in item specifics or description
        grading_found = False
        for specific in item_specifics:
            name = specific.get('name', '').lower()
            value = specific.get('value', '')
            if 'grade' in name or 'condition' in name:
                st.write(f"- **{specific.get('name', '')}:** {value}")
                grading_found = True
        
        if not grading_found:
            st.write("No specific grading information available")
        
        st.divider()
        
        # Display description
        st.write("**Description:**")
        if short_description:
            # Clean HTML tags if present
            clean_desc = re.sub('<[^<]+?>', '', short_description)
            st.write(clean_desc[:500] + "..." if len(clean_desc) > 500 else clean_desc)
        elif description:
            # Clean HTML tags if present
            clean_desc = re.sub('<[^<]+?>', '', description)
            st.write(clean_desc[:500] + "..." if len(clean_desc) > 500 else clean_desc)
        else:
            st.write("No description available")
        
        st.divider()
        
        # Display shipping information
        st.write("**Shipping Options:**")
        if shipping_options:
            for option in shipping_options[:3]:  # Show first 3 options
                cost_type = option.get('shippingCostType', '')
                cost = option.get('shippingCost', {}).get('value', 'N/A')
                service = option.get('shippingServiceCode', '')
                st.write(f"- **{service}:** {cost_type} - ${cost}" if cost != 'N/A' else f"- **{service}:** {cost_type}")
        else:
            st.write("No shipping information available")

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