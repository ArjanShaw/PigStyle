# FILE: inventory-manager/src/handlers/display_handler.py
import streamlit as st
import pandas as pd
from datetime import datetime
import re
import math
import threading
import subprocess
from pathlib import Path
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
        """Render database search results - NOW WITH DIRECT EDITING"""
        if not results:
            st.warning("No records found in database")
            return
        
        # For database results, render editable fields directly
        self._render_editable_database_results(results)

    def _render_editable_database_results(self, results):
        """Render database results with direct editing (no Select button)"""
        for i, record in enumerate(results):
            # Create an expander for each record with editing capabilities
            with st.expander(f"{record.get('artist', '')} - {record.get('title', '')}", expanded=False):
                self._render_editable_record(record, i)

    def _render_editable_record(self, record, index):
        """Render a single record with editable fields"""
        col1, col2 = st.columns([1, 3])
        
        with col1:
            image_url = record.get('image_url', '')
            if image_url:
                st.image(image_url, width=80)
            else:
                st.write("No image")
        
        with col2:
            # Show record details
            st.write(f"**ID:** {record.get('id', '')}")
            st.write(f"**Barcode:** {record.get('barcode', '')}")
            st.write(f"**Catalog:** {record.get('catalog_number', '')}")
            st.write(f"**Genre:** {record.get('genre', '')}")
            
            # Editable fields
            artist = st.text_input("Artist", value=record.get('artist', ''), key=f"artist_edit_{index}")
            title = st.text_input("Title", value=record.get('title', ''), key=f"title_edit_{index}")
            
            # Genre selection
            all_genres = self._get_all_genres()
            current_genre = record.get('genre', '')
            genre_index = all_genres.index(current_genre) + 1 if current_genre in all_genres else 0
            genre = st.selectbox("Genre", options=[""] + all_genres, index=genre_index, key=f"genre_edit_{index}")
            
            # Compilation checkbox
            compilation = st.checkbox("Compilation", value=record.get('compilation', False), key=f"compilation_{index}")
            
            # Store price
            store_price = st.number_input("Store Price", value=float(record.get('store_price', 0.0)), min_value=0.0, step=0.5, key=f"store_price_{index}")
            
            # YouTube URL
            youtube_url = st.text_input("YouTube URL", value=record.get('youtube_url', ''), key=f"youtube_{index}")
            
            # Barcode clearing option
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("💾 Save", key=f"save_{index}", use_container_width=True):
                    self._save_record_changes(record, artist, title, genre, compilation, store_price, youtube_url)
            
            with col_btn2:
                if st.button("🗑️ Delete", key=f"delete_{index}", use_container_width=True, type="secondary"):
                    if self._delete_record(record.get('id')):
                        st.success("Record deleted successfully!")
                        st.rerun()
            
            with col_btn3:
                if record.get('barcode'):
                    if st.button("🗑️ Clear Barcode", key=f"clear_barcode_{index}", use_container_width=True, type="secondary"):
                        if self._clear_barcode(record.get('id')):
                            st.success("Barcode cleared!")
                            st.rerun()

    def _save_record_changes(self, original_record, artist, title, genre, compilation, store_price, youtube_url):
        """Save changes to a record"""
        try:
            # Get genre_id for the genre
            genre_id = None
            if genre:
                genres_df = st.session_state.db_manager.get_all_genres()
                genre_row = genres_df[genres_df['genre_name'] == genre]
                if not genre_row.empty:
                    genre_id = genre_row.iloc[0]['id']
                else:
                    # Create new genre
                    success, new_genre_id = st.session_state.db_manager.add_genre(genre)
                    if success:
                        genre_id = new_genre_id
            
            # Prepare updates
            updates = {
                'artist': artist,
                'title': title,
                'genre_id': genre_id,
                'compilation': compilation,
                'store_price': store_price,
                'youtube_url': youtube_url
            }
            
            # Update the record
            success = st.session_state.db_manager.update_record(original_record['id'], updates)
            if success:
                st.success("Record updated successfully!")
                st.rerun()
            else:
                st.error("Failed to update record")
                
        except Exception as e:
            st.error(f"Error updating record: {str(e)}")

    def _clear_barcode(self, record_id):
        """Clear barcode from a record"""
        try:
            success = st.session_state.db_manager.update_record(record_id, {'barcode': None})
            return success
        except Exception as e:
            st.error(f"Error clearing barcode: {str(e)}")
            return False

    def _render_unified_results(self, results, result_type):
        """Render unified results component for Discogs searches (keeps Select button)"""
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
                    discogs_suggested_price = record.get('discogs_suggested_price')
                    compilation = record.get('compilation', False)
                    consignor_name = record.get('consignor_name', '')
                    commission_rate = record.get('commission_rate')
                    
                    # SHOW THE REQUESTED FIELDS when selecting from inventory
                    record_id = record.get('id', '')
                    barcode = record.get('barcode', '')
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
                if st.button("Select", key=f"select_{result_type}_{i}", use_container_width=True):
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
                store_price = record.get('store_price', '')
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
        
        if st.button("← Back to Results", key="back_to_results", use_container_width=True):
            st.session_state.selected_record = None
            st.rerun()

    def render_edit_section(self, selected_record, add_callback, update_callback, discogs_handler=None, ebay_handler=None, store_fill_fraction=0.0):
        """Render the edit properties section - WITH COMPILATION AND DIRECT CONSIGNMENT SUPPORT"""
        
        record_data = selected_record['data']
        
        # For Discogs records, fetch all data before showing ANY UI
        if selected_record['type'] == 'discogs' and not record_data.get('pricing_fetched'):
            # Show spinner while fetching ALL data
            with st.spinner("🔄 Fetching pricing data from Discogs and YouTube..."):
                # Fetch all required data sequentially
                self._fetch_all_data_sync(record_data, discogs_handler, ebay_handler)
            
            # Mark as fetched and rerun to show the complete UI
            record_data['pricing_fetched'] = True
            st.rerun()
            return
        
        # Once ALL data is loaded, show the complete UI
        st.subheader("Edit Properties")
        
        # Calculate current consignment rate based on store fill
        current_consignment_rate = self._calculate_consignment_rate(store_fill_fraction)
        
        # Show current store fill status and consignment rate
        st.info(f"**Store Fill:** {store_fill_fraction*100:.1f}% | **Current Consignment Rate:** {current_consignment_rate:.1%}")
        
        # Disable add button if store is over capacity
        add_disabled = store_fill_fraction > 1.10
        
        if add_disabled:
            st.error("❌ Cannot add new items - store is over capacity!")
        
        # Check for duplicates
        duplicates_found = self._check_for_duplicate_simple(record_data)
        
        if duplicates_found:
            user = st.session_state.get('user', {})
            user_role = user.get('role', 'consignor')
            
            if user_role != 'admin':
                st.error("❌ **Cannot add duplicate record!**")
                return
            else:
                st.warning("⚠️ **Duplicate detected - you may proceed as admin**")
        
        # Add consignment dropdown for both new and existing records - NOW WITH USER ROLE CHECK
        user_id, commission_rate, store_return_days = self._render_consignment_section(record_data, current_consignment_rate)
        if user_id:
            record_data['consignor_id'] = user_id
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
        
        # Show YouTube integration in a collapsible component (collapsed by default)
        with st.expander("🎵 YouTube Integration", expanded=False):
            self._render_youtube_integration(record_data)
        
        # Single submit button - only enable if genre is selected and not over capacity
        button_label = "Add to Database" if selected_record['type'] == 'discogs' else "Update Record"
        
        # Check user role for duplicate restrictions
        user_role = st.session_state.get('user', {}).get('role', 'consignor')
        is_admin = (user_role == 'admin')
        
        # Disable button for non-admin users with duplicates
        disabled_condition = not genre or (selected_record['type'] == 'discogs' and add_disabled) or (duplicates_found and not is_admin)
        
        if st.button(button_label, use_container_width=True, disabled=disabled_condition, key="add_to_database"):
            if selected_record['type'] == 'discogs':
                success, record_id = add_callback(genre)
                if success:
                    # Clear duplicate warning if successful
                    if 'last_duplicate_check' in st.session_state:
                        del st.session_state.last_duplicate_check
                    
                    # Show confirmation message with artist and title
                    st.success(f"✅ Record added successfully!\\n**Artist:** {record_data['artist']}\\n**Title:** {record_data['title']}")
                    st.session_state.record_added = True
            else:
                success = update_callback(genre)
                if success:
                    st.success(f"✅ Record updated successfully!")

    def _check_for_duplicate_simple(self, record_data):
        """Simple duplicate check using ONLY artist, title, and catalog number"""
        # Get the data to check
        artist = record_data.get('artist', '')
        title = record_data.get('title', '')
        catalog_number = record_data.get('catalog_number', '')
        
        # Get all records from database
        all_records = st.session_state.db_manager.get_all_records()
        
        if all_records.empty:
            return False
        
        # Check artist/title combination
        if artist and title:
            artist_title_match = all_records[
                (all_records['artist'].str.lower() == artist.lower()) & 
                (all_records['title'].str.lower() == title.lower())
            ]
            if not artist_title_match.empty:
                return True
        
        # Check catalog number
        if catalog_number:
            catalog_match = all_records[
                (all_records['catalog_number'].str.lower() == catalog_number.lower())
            ]
            if not catalog_match.empty:
                return True
        
        return False

    def _calculate_consignment_rate(self, fill_fraction):
        """Calculate consignment rate based on store fill fraction"""
        if fill_fraction < 0.60:
            return 0.10  # 10% when below 60%
        elif fill_fraction <= 1.10:
            # Linear increase from 10% to 40% between 60% and 110%
            # At 0.60: 0.10, at 1.10: 0.40
            slope = (0.40 - 0.10) / (1.10 - 0.60)
            return 0.10 + slope * (fill_fraction - 0.60)
        else:
            return 0.40  # 40% when above 110%

    def _render_consignment_section(self, record_data=None, current_consignment_rate=0.10):
        """Render consignment section with direct user selection and individual rates - NOW WITH USER ROLE CHECK"""
        # Get current user info
        current_user = st.session_state.get('user', {})
        user_role = current_user.get('role', 'consignor')
        current_user_id = current_user.get('id')
        
        # If user is consignor, automatically set to themselves and make it unchangeable
        if user_role == 'consignor' and current_user_id:
            # Auto-select current user as consignor
            user_id = current_user_id
            
            # Use current calculated consignment rate as default
            current_commission_rate = record_data.get('commission_rate')
            if current_commission_rate is None:
                current_commission_rate = current_consignment_rate
            
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
            
            st.info(f"🔒 Consignor automatically set to: {current_user.get('username', 'You')} (Consignor account)")
            
            return user_id, commission_rate, store_return_days
        
        # For admin users, show the full dropdown selection
        # Get all users for dropdown - using API approach
        users_df = st.session_state.db_manager.get_all_users()
        
        if len(users_df) == 0:
            st.info("No users available. Add users in the Consignment tab first.")
            return None, None, None
        
        # Create options for dropdown
        options = ["Store Owned"]  # Default option
        
        # Create mapping for user selection
        user_mapping = {}
        for _, user in users_df.iterrows():
            option_text = f"{user['username']} ({user['full_name'] or 'No name'})"
            options.append(option_text)
            user_mapping[option_text] = user['id']
        
        # Determine default selection
        default_index = 0  # Default to "Store Owned"
        
        # If editing existing record with consignment, find the matching user
        current_consignor_name = record_data.get('consignor_name', '')
        if current_consignor_name:
            for option_text in user_mapping.keys():
                if current_consignor_name in option_text:
                    default_index = options.index(option_text)
                    break
        
        # Render user dropdown
        selected_option = st.selectbox(
            "Consignor:",
            options=options,
            index=default_index,
            key="consignor_select"
        )
        
        # If Store Owned selected, return None for all values
        if selected_option == "Store Owned":
            return None, None, None
        
        # Get the selected user ID
        user_id = user_mapping.get(selected_option)
        
        # Use current calculated consignment rate as default
        current_commission_rate = record_data.get('commission_rate')
        if current_commission_rate is None:
            current_commission_rate = current_consignment_rate
        
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
        
        return user_id, commission_rate, store_return_days

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
        
        # Check artist history in database - using API approach
        if self._is_artist_mostly_compilation(artist):
            return True
        
        # Also check if it's already marked as compilation in database record
        if record_data.get('compilation'):
            return True
            
        return False

    def _is_artist_mostly_compilation(self, artist):
        """Check if this artist's records are mostly marked as compilations in the database using API"""
        # Use API approach instead of SQL connection
        all_records = st.session_state.db_manager.get_all_records()
        if all_records.empty:
            return False
        
        # Filter records by this artist
        artist_records = all_records[all_records['artist'] == artist]
        if artist_records.empty:
            return False
        
        # Calculate compilation ratio
        total_records = len(artist_records)
        compilation_count = len(artist_records[artist_records['compilation'] == True])
        
        # If more than 50% of this artist's records are compilations, suggest compilation
        if total_records > 0 and (compilation_count / total_records) > 0.5:
            return True
            
        return False

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
        
        # Step 3: Fetch YouTube results (BLOCKING) - NOW WITH TRACKLIST
        if self.youtube_handler and self.youtube_handler.is_enabled():
            # Get tracklist from Discogs for better YouTube matching
            track_titles = record_data.get('tracklist', [])
            
            search_query = f"{record_data.get('artist', '')} {record_data.get('title', '')}"
            record_data['youtube_search_query'] = search_query
            youtube_results = self.youtube_handler.search_youtube_videos(search_query, record_data, track_titles)
            st.session_state.youtube_search_results = youtube_results

    def _get_suggested_genre(self, record_data):
        """Get suggested genre for a record based on artist history - ONLY suggest if artist exists in database"""
        # Priority 1: Check artist history in database - ONLY if artist has existing records
        artist = record_data.get('artist', '')
        if artist:
            artist_genre = self._get_genre_from_artist_history(artist)
            if artist_genre:
                return artist_genre
        
        # No suggestion available if artist doesn't exist in database
        return ""

    def _get_genre_from_artist_history(self, artist):
        """Get the most common genre for this artist from existing records - ONLY if artist exists using API"""
        # Use API approach instead of SQL connection
        all_records = st.session_state.db_manager.get_all_records()
        if all_records.empty:
            return ""
        
        # Check if artist exists in database
        artist_exists = len(all_records[all_records['artist'] == artist]) > 0
        if not artist_exists:
            return ""
        
        # Find the most common genre for this artist
        artist_records = all_records[all_records['artist'] == artist]
        if not artist_records.empty:
            genre_counts = artist_records['genre_name'].value_counts()
            if not genre_counts.empty:
                return genre_counts.index[0]
        return ""

    def _get_suggestion_source(self, record_data, suggested_genre):
        """Explain where the genre suggestion came from"""
        artist = record_data.get('artist', '')
        if artist and suggested_genre == self._get_genre_from_artist_history(artist):
            return "Artist history"
        
        return "Unknown"

    def _get_all_genres(self):
        """Get all available genres from database using API"""
        genres_df = st.session_state.db_manager.get_all_genres()
        return genres_df['genre_name'].tolist()

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
        # Show current linked YouTube URL
        current_youtube_url = record_data.get('youtube_url', '')
        if current_youtube_url:
            st.success(f"✅ Currently linked: {current_youtube_url}")
            
            # Add clickable link to view the video
            st.markdown(f"[📺 Click here to view the video]({current_youtube_url})", unsafe_allow_html=True)
            
            # Show option to remove link
            if st.button("❌ Remove YouTube Link", key="remove_youtube", use_container_width=True):
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
            if st.button("🔗 Use This YouTube URL", key="use_manual_url", use_container_width=True):
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
            other_results = [r for r in st.session_state.youtube_search_results if r.get('type') == 'other']
            
            if track_results:
                st.write("**🎵 Individual Track Recordings:**")
                for i, video in enumerate(track_results):
                    self._render_youtube_video_option(video, i, record_data)
            
            if album_results:
                st.write("**📀 Album Content:**")
                for i, video in enumerate(album_results, start=len(track_results)):
                    self._render_youtube_video_option(video, i, record_data)
                    
            if other_results:
                st.write("**🎥 Other Related Videos:**")
                for i, video in enumerate(other_results, start=len(track_results) + len(album_results)):
                    self._render_youtube_video_option(video, i, record_data)
                    
            # If no results were categorized, show all results
            if not track_results and not album_results and not other_results and st.session_state.youtube_search_results:
                st.write("**🎥 All Search Results:**")
                for i, video in enumerate(st.session_state.youtube_search_results):
                    self._render_youtube_video_option(video, i, record_data)
        else:
            st.info("No YouTube search results available")

    def _render_youtube_video_option(self, video, index, record_data):
        """Display a YouTube video option with link button and clickable link"""
        col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
        with col1:
            if video.get('thumbnail'):
                st.image(video['thumbnail'], width=80)
            else:
                st.write("No thumbnail")
        with col2:
            st.write(f"**{video['title']}**")
            st.write(f"Channel: {video['channel']}")
            if video.get('track_title'):
                st.write(f"Track: {video['track_title']}")
            if video.get('type'):
                st.write(f"Type: {video['type']}")
            
            # Add clickable link to view the video
            st.markdown(f"[📺 Watch this video]({video['url']})", unsafe_allow_html=True)
            
        with col3:
            if st.button("🔗 Link", key=f"youtube_link_{index}", use_container_width=True):
                record_data['youtube_url'] = video['url']
                st.success(f"✅ Linked to: {video['title']}")
                st.rerun()
        
        with col4:
            # Add a direct view button
            st.markdown(f'<a href="{video["url"]}" target="_blank"><button style="width: 100%;">👀 View</button></a>', unsafe_allow_html=True)

    def _render_pricing_information(self, record_data):
        """Render ALL pricing information - ONLY called after ALL API calls complete"""
        
        # Check if we have the required data from ALL APIs
        has_discogs_data = 'price_suggestions' in record_data
        
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
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
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

    def _delete_record(self, record_id):
        """Delete a record from the database using API"""
        success = st.session_state.db_manager.delete_record(record_id)
        if success:
            st.success("Record deleted successfully!")
            return True
        else:
            st.error("Failed to delete record")
            return False