import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import random
import time
import traceback

class YouTubeLinkerTab:
    def __init__(self, youtube_handler):
        self.youtube_handler = youtube_handler
        self.base_url = "https://www.pigstylemusic.com"
        
        # Initialize session state for dropdown
        if 'youtube_dropdown_state' not in st.session_state:
            st.session_state.youtube_dropdown_state = {
                'records_without_links': [],
                'current_search_results': None,
                'current_search_query': None,  # Track what was actually searched
                'selected_record': None,
                'dropdown_options': [],
                'filtered_options': [],
                'last_saved_record': None,
                'force_refresh': False,
                'reset_dropdown': False,
                'force_search': True,  # Start with True to force initial search
                'search_query': '',
                'dropdown_index': 0,
                'selected_genre': 'All Genres',
                'search_cache': {},  # Cache results by record ID
            }
    
    def render(self):
        st.header("🎬 YouTube Linker")
        
        user = st.session_state.get('user', {})
        if user.get('role') != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view YouTube Linker.")
            return
        
        # Check if YouTube handler is enabled
        if not self.youtube_handler or not self.youtube_handler.is_enabled():
            st.error("❌ YouTube API not configured. Please set YOUTUBE_API_KEY in your environment variables.")
            return
         
        # Initialize dropdown state
        self._initialize_dropdown()
        
        # Render dropdown and content
        self._render_dropdown_interface()
    
    def _initialize_dropdown(self):
        dropdown_state = st.session_state.youtube_dropdown_state
        
        # Reset logic
        if dropdown_state.get('reset_dropdown', False):
            dropdown_state['reset_dropdown'] = False
            dropdown_state['current_search_results'] = None
            dropdown_state['selected_record'] = None
            dropdown_state['force_search'] = True
        
        if dropdown_state.get('force_refresh', False):
            dropdown_state['records_without_links'] = []
            dropdown_state['dropdown_options'] = []
            dropdown_state['filtered_options'] = []
            dropdown_state['current_search_results'] = None
            dropdown_state['current_search_query'] = None
            dropdown_state['selected_record'] = None
            dropdown_state['force_refresh'] = False
            dropdown_state['force_search'] = True
            dropdown_state['search_query'] = ''
            dropdown_state['dropdown_index'] = 0
            dropdown_state['selected_genre'] = 'All Genres'
            dropdown_state['search_cache'] = {}  # Clear cache
        
        # Load records without YouTube links if needed
        if not dropdown_state['records_without_links']:
            with st.spinner("Loading records without YouTube links..."):
                records = self._get_records_without_youtube()
                dropdown_state['records_without_links'] = records
                
                options = []
                all_genres = set(['All Genres'])
                
                for record in records:
                    artist = record.get('artist', 'Unknown Artist')
                    title = record.get('title', 'Unknown Title')
                    catalog = record.get('catalog_number', '')
                    genre = record.get('genre_name', record.get('genre', 'Unknown'))
                    
                    if genre:
                        all_genres.add(genre)
                    
                    display_text = f"{artist} - {title}"
                    if catalog:
                        display_text += f" [{catalog}]"
                    
                    options.append({
                        'display': display_text,
                        'record': record,
                        'value': f"{record.get('id')}_{artist}_{title}",
                        'search_text': f"{artist.lower()} {title.lower()} {catalog.lower()}" if catalog else f"{artist.lower()} {title.lower()}",
                        'genre': genre,
                        'record_id': record.get('id')  # Store record ID for cache lookup
                    })
                
                dropdown_state['dropdown_options'] = options
                dropdown_state['filtered_options'] = options[:]
                dropdown_state['available_genres'] = sorted(list(all_genres))
                dropdown_state['search_cache'] = {}  # Clear cache when reloading records
                
                # Auto-select first record if there are options
                if options:
                    dropdown_state['selected_record'] = options[0]['record']
                    dropdown_state['dropdown_index'] = 0
                else:
                    dropdown_state['selected_record'] = None
                    dropdown_state['dropdown_index'] = 0
                
                st.session_state.youtube_dropdown_state = dropdown_state
    
    def _get_records_without_youtube(self):
        try:
            response = requests.get(f"{self.base_url}/records")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') == 'success':
                    records = data.get('records', [])
                    
                    records_without_links = []
                    for record in records:
                        youtube_url = record.get('youtube_url', '')
                        if not youtube_url or youtube_url == '' or youtube_url == 'None':
                            records_without_links.append(record)
                    
                    return records_without_links
            
            return []
        except Exception as e:
            st.error(f"Error getting records: {e}")
            return []
    
    def _render_dropdown_interface(self):
        dropdown_state = st.session_state.youtube_dropdown_state
        
        if not dropdown_state['dropdown_options']:
            st.success("✅ All records already have YouTube links!")
            if st.button("🔄 Check for new records"):
                dropdown_state['force_refresh'] = True
                st.session_state.youtube_dropdown_state = dropdown_state
                st.rerun()
            return
        
        # FILTER CONTROLS
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            # SEARCH INPUT
            search_query = st.text_input(
                "🔍 Search records (artist, title, or catalog number):",
                value=dropdown_state.get('search_query', ''),
                key="youtube_search_input",
                placeholder="Type to filter records..."
            )
        
        with col2:
            # GENRE DROPDOWN FILTER
            available_genres = dropdown_state.get('available_genres', ['All Genres'])
            selected_genre = st.selectbox(
                "🎵 Filter by Genre:",
                options=available_genres,
                index=available_genres.index(dropdown_state.get('selected_genre', 'All Genres')) 
                if dropdown_state.get('selected_genre', 'All Genres') in available_genres else 0,
                key="genre_filter_dropdown"
            )
        
        with col3:
            st.metric("Total", len(dropdown_state['dropdown_options']))
        
        # Apply filters
        filters_changed = False
        
        if search_query != dropdown_state.get('search_query', ''):
            dropdown_state['search_query'] = search_query
            filters_changed = True
        
        if selected_genre != dropdown_state.get('selected_genre', 'All Genres'):
            dropdown_state['selected_genre'] = selected_genre
            filters_changed = True
        
        # Apply filters if they changed
        if filters_changed:
            filtered = dropdown_state['dropdown_options']
            
            # Apply genre filter
            if selected_genre != 'All Genres':
                filtered = [option for option in filtered if option.get('genre') == selected_genre]
            
            # Apply search filter
            if search_query:
                search_lower = search_query.lower()
                filtered = [option for option in filtered if search_lower in option['search_text']]
            
            dropdown_state['filtered_options'] = filtered
            
            # Reset to first item when filters change
            dropdown_state['dropdown_index'] = 0
            if filtered:
                dropdown_state['selected_record'] = filtered[0]['record']
            else:
                dropdown_state['selected_record'] = None
            
            # Force new search when filters change (new selection)
            dropdown_state['force_search'] = True
            
            st.session_state.youtube_dropdown_state = dropdown_state
        
        filtered_options = dropdown_state['filtered_options']
        
        if not filtered_options:
            st.warning(f"No records found matching your filters.")
            
            if search_query or selected_genre != 'All Genres':
                if st.button("🗑️ Clear All Filters", type="secondary"):
                    dropdown_state['search_query'] = ''
                    dropdown_state['selected_genre'] = 'All Genres'
                    dropdown_state['filtered_options'] = dropdown_state['dropdown_options'][:]
                    dropdown_state['dropdown_index'] = 0
                    if dropdown_state['dropdown_options']:
                        dropdown_state['selected_record'] = dropdown_state['dropdown_options'][0]['record']
                    st.session_state.youtube_dropdown_state = dropdown_state
                    st.rerun()
            return
        
        # DROPDOWN SELECTION
        dropdown_choices = [option['display'] for option in filtered_options]
        
        selected_index = dropdown_state['dropdown_index']
        
        selected_display = st.selectbox(
            "Select record to add YouTube link:",
            options=dropdown_choices,
            index=selected_index,
            key="youtube_record_dropdown"
        )
        
        # Update index when user selects a different option
        current_index = dropdown_choices.index(selected_display) if selected_display in dropdown_choices else 0
        if current_index != dropdown_state['dropdown_index']:
            dropdown_state['dropdown_index'] = current_index
            # Force new search when dropdown selection changes
            dropdown_state['force_search'] = True
            st.session_state.youtube_dropdown_state = dropdown_state
        
        # Show filter metrics
        if selected_genre != 'All Genres' or search_query:
            st.caption(f"Showing {len(filtered_options)} records (filtered by {selected_genre}{' + search' if search_query else ''})")
        
        # Always show results for the selected record
        if selected_display:
            selected_option = None
            for option in filtered_options:
                if option['display'] == selected_display:
                    selected_option = option
                    break
            
            if selected_option:
                record = selected_option['record']
                record_id = record.get('id')
                
                # Clear session state for previous selection
                prev_selected_record = dropdown_state.get('selected_record')
                if prev_selected_record:
                    prev_selected_id = prev_selected_record.get('id')
                    if prev_selected_id and prev_selected_id != record_id:
                        # Clear the saved session state for previous record
                        prev_session_key = f"saved_session_{prev_selected_id}"
                        if prev_session_key in st.session_state:
                            del st.session_state[prev_session_key]
                
                # Update the selected record
                if dropdown_state.get('selected_record') != record:
                    dropdown_state['selected_record'] = record
                
                # Check if we need to perform a new search
                should_search = False
                
                # Condition 1: Force search flag is set
                if dropdown_state.get('force_search', False):
                    should_search = True
                    dropdown_state['force_search'] = False
                # Condition 2: No search results cached
                elif dropdown_state['current_search_results'] is None:
                    should_search = True
                # Condition 3: Cached results are for a different record
                elif prev_selected_record and prev_selected_record.get('id') != record_id:
                    should_search = True
                # Condition 4: Check if we have cached results for this record
                elif record_id in dropdown_state.get('search_cache', {}):
                    # Use cached results
                    cached = dropdown_state['search_cache'][record_id]
                    dropdown_state['current_search_results'] = cached['results']
                    dropdown_state['current_search_query'] = cached['query']
                    should_search = False
                
                if should_search:
                    with st.spinner(f"Searching YouTube for {record.get('artist', '')}..."):
                        artist = record.get('artist', '')
                        title = record.get('title', '')
                        search_query = f"{artist} - {title}"
                        
                        # Store the actual search query
                        dropdown_state['current_search_query'] = search_query
                        
                        youtube_results = self._search_youtube_for_record(record, search_query)
                        dropdown_state['current_search_results'] = youtube_results
                        
                        # Cache the results
                        if record_id:
                            dropdown_state['search_cache'][record_id] = {
                                'results': youtube_results,
                                'query': search_query
                            }
                        
                        st.session_state.youtube_dropdown_state = dropdown_state
                
                self._display_record_and_results(record)
    
    def _search_youtube_for_record(self, record, search_query):
        artist = record.get('artist', '')
        title = record.get('title', '')
        
        # Use the provided search query
        track_titles = []
        if 'discogs_handler' in st.session_state and record.get('discogs_id'):
            try:
                track_titles = st.session_state.discogs_handler.get_release_tracklist(
                    str(record.get('discogs_id'))
                )
            except:
                pass
        
        results = self.youtube_handler.search_youtube_videos(
            search_query,
            record,
            track_titles
        )
        
        return results
    
    def _display_record_and_results(self, record):
        dropdown_state = st.session_state.youtube_dropdown_state
        
        with st.container():
            col1, col2 = st.columns([1, 3])
            
            with col1:
                image_url = record.get('image_url', '')
                if image_url:
                    st.image(image_url, width=150)
                else:
                    st.write("No image")
            
            with col2:
                st.markdown(f"### {record.get('artist', '')} - {record.get('title', '')}")
                
                catalog = record.get('catalog_number', '')
                genre = record.get('genre_name', record.get('genre', ''))
                price = record.get('store_price', 0)
                
                if catalog:
                    st.write(f"**Catalog:** {catalog}")
                if genre:
                    st.write(f"**Genre:** {genre}")
                if price:
                    st.write(f"**Price:** ${price:.2f}")
        
        st.divider()
        
        if dropdown_state['current_search_results']:
            youtube_results = dropdown_state['current_search_results']
            search_query = dropdown_state.get('current_search_query', 'Unknown search')
            
            # Display the actual search query used
            st.subheader(f"🎬 YouTube Results for: '{search_query}' ({len(youtube_results)} found)")
            
            # Show a button to re-search if results seem irrelevant
            if len(youtube_results) == 0 or len(youtube_results) < 3:
                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button("🔄 Re-search YouTube", type="secondary"):
                        dropdown_state['force_search'] = True
                        # Clear cache for this record
                        record_id = record.get('id')
                        if record_id in dropdown_state.get('search_cache', {}):
                            del dropdown_state['search_cache'][record_id]
                        st.session_state.youtube_dropdown_state = dropdown_state
                        st.rerun()
            
            cols_per_row = 3
            max_rows = 3
            num_results = min(len(youtube_results), cols_per_row * max_rows)
            
            for row_start in range(0, num_results, cols_per_row):
                row_results = youtube_results[row_start:row_start + cols_per_row]
                cols = st.columns(cols_per_row)
                
                for col_idx, result in enumerate(row_results):
                    with cols[col_idx]:
                        result_idx = row_start + col_idx
                        self._display_youtube_result_card(result, record, result_idx)
        else:
            st.info("No YouTube results found for this record.")
            if st.button("🔄 Try Search Again"):
                dropdown_state['force_search'] = True
                st.session_state.youtube_dropdown_state = dropdown_state
                st.rerun()
    
    def _display_youtube_result_card(self, result, record, index):
        record_id = record.get('id')
        
        title = result.get('title', '')
        channel = result.get('channel', '')
        url = result.get('url', '')
        duration = result.get('duration', '')
        
        if not duration:
            duration = self._extract_video_duration(title)
        
        display_title = title[:40] + '...' if len(title) > 40 else title
        
        st.markdown(f"**{display_title}**")
        
        if channel:
            st.caption(f"👤 {channel[:20]}{'...' if len(channel) > 20 else ''}")
        if duration:
            st.caption(f"⏱️ {duration}")
        
        video_id = self._extract_youtube_video_id(url)
        if video_id:
            st.markdown(f"""
            <div style="position: relative; padding-bottom: 75%; height: 0; overflow: hidden; max-width: 100%; margin: 5px 0;">
                <iframe src="https://www.youtube.com/embed/{video_id}" 
                        style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;" 
                        allowfullscreen>
                </iframe>
            </div>
            """, unsafe_allow_html=True)
        
        # 🔒 STABLE BUTTON KEY (FIXED)
        button_key = f"save_btn_{record_id}_{index}"
        
        session_save_key = f"saved_session_{record_id}"
        if session_save_key not in st.session_state:
            st.session_state[session_save_key] = False
        
        if not st.session_state[session_save_key]:
            button_clicked = st.button(
                "💾 Save This Clip",
                key=button_key,
                type="primary",
                use_container_width=True
            )
            
            if button_clicked:
                print(f"\n{'='*60}")
                print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] ====== SAVE BUTTON CLICKED! ======")
                print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Record ID: {record_id}")
                print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] YouTube URL: {url}")
                print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Title: {title}")
                
                success = self._add_youtube_link(record_id, url)
                
                if success:
                    st.session_state[session_save_key] = True
                    
                    st.success(f"✅ YouTube link saved to record: {record.get('artist')} - {record.get('title')}")
                    
                    dropdown_state = st.session_state.youtube_dropdown_state
                    self._remove_record_from_dropdown(record_id)
                    
                    # Clear the search results cache
                    dropdown_state['current_search_results'] = None
                    dropdown_state['current_search_query'] = None
                    dropdown_state['selected_record'] = None
                    dropdown_state['reset_dropdown'] = True
                    dropdown_state['force_refresh'] = True
                    dropdown_state['force_search'] = True
                    dropdown_state['last_saved_record'] = record_id
                    
                    # Remove from search cache
                    if record_id in dropdown_state.get('search_cache', {}):
                        del dropdown_state['search_cache'][record_id]
                    
                    st.session_state.youtube_dropdown_state = dropdown_state
                    
                    # Clear any session save states
                    for key in list(st.session_state.keys()):
                        if key.startswith("saved_session_"):
                            del st.session_state[key]
                    
                    st.rerun()
                else:
                    st.error(f"❌ FAILED to save YouTube link for record {record_id}")
        else:
            st.info("✅ Already saved!")
        
        st.divider()
    
    def _remove_record_from_dropdown(self, record_id):
        dropdown_state = st.session_state.youtube_dropdown_state
        
        new_options = []
        new_records = []
        
        for option in dropdown_state['dropdown_options']:
            if option['record'].get('id') != record_id:
                new_options.append(option)
        
        for record in dropdown_state['records_without_links']:
            if record.get('id') != record_id:
                new_records.append(record)
        
        dropdown_state['dropdown_options'] = new_options
        dropdown_state['records_without_links'] = new_records
        
        # Rebuild available genres
        all_genres = set(['All Genres'])
        for option in new_options:
            genre = option.get('genre')
            if genre:
                all_genres.add(genre)
        dropdown_state['available_genres'] = sorted(list(all_genres))
        
        # Re-filter the options based on current filters
        filtered = new_options
        
        if dropdown_state.get('selected_genre', 'All Genres') != 'All Genres':
            filtered = [option for option in filtered if option.get('genre') == dropdown_state['selected_genre']]
        
        if dropdown_state.get('search_query', ''):
            search_lower = dropdown_state['search_query'].lower()
            filtered = [option for option in filtered if search_lower in option['search_text']]
        
        dropdown_state['filtered_options'] = filtered
        
        # Update dropdown index
        dropdown_state['dropdown_index'] = 0
        if dropdown_state['filtered_options']:
            dropdown_state['selected_record'] = dropdown_state['filtered_options'][0]['record']
        else:
            dropdown_state['selected_record'] = None
        
        # Remove from search cache
        if record_id in dropdown_state.get('search_cache', {}):
            del dropdown_state['search_cache'][record_id]
        
        st.session_state.youtube_dropdown_state = dropdown_state
        return True
    
    def _extract_youtube_video_id(self, url):
        import re
        
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_video_duration(self, title):
        import re
        
        patterns = [
            r'\((\d+:\d+)\)',
            r'\[(\d+:\d+)\]',
            r'(\d+:\d+:\d+)',
            r'(\d+:\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return match.group(1)
        
        return None
    
    def _add_youtube_link(self, record_id, youtube_url):
        print(f"\n{'='*60}")
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] ====== _ADD_YOUTUBE_LINK CALLED ======")
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] record_id={record_id}")
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] youtube_url={youtube_url}")
        
        try:
            api_url = f"{self.base_url}/records/{record_id}"
            
            response = requests.put(
                api_url, 
                json={'youtube_url': youtube_url},
                timeout=10
            )
            
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] Response status: {response.status_code}")
            
            if response.status_code == 200:
                if 'records_updated' not in st.session_state:
                    st.session_state.records_updated = 0
                st.session_state.records_updated += 1
                return True
            else:
                print(f"ERROR RESPONSE: {response.text[:500]}")
                return False
                
        except requests.exceptions.Timeout:
            st.error("Request timed out. The server might be down or slow.")
            return False
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to server. Check your internet connection.")
            return False
        except Exception as e:
            print(traceback.format_exc())
            st.error(f"Error adding YouTube link: {e}")
            return False
    
    def clear_youtube_cache(self):
        """Clear cached YouTube search results"""
        dropdown_state = st.session_state.youtube_dropdown_state
        dropdown_state['current_search_results'] = None
        dropdown_state['current_search_query'] = None
        dropdown_state['search_cache'] = {}
        dropdown_state['force_search'] = True
        st.session_state.youtube_dropdown_state = dropdown_state