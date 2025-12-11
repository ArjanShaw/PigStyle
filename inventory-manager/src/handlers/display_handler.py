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
        if not results:
            st.warning("No results found on Discogs")
            return
        
        self._render_unified_results(results, search_type, None)

    def render_database_results(self, results, search_type, user=None):
        if not results:
            st.warning("No records found in database")
            return
        
        self._render_editable_database_results(results, search_type, user)

    def _render_editable_database_results(self, results, search_type, user=None):
        for i, record in enumerate(results):
            # Show consignor name in the expander title for admin users
            expander_title = f"{record.get('artist', '')} - {record.get('title', '')}"
            user_role = user.get('role', 'consignor') if user else 'consignor'
            
            if user_role == 'admin' and record.get('consignor_name'):
                expander_title += f" 👤 {record.get('consignor_name')}"
            
            with st.expander(expander_title, expanded=False):
                self._render_editable_record(record, i, search_type, user)

    def _render_editable_record(self, record, index, search_type, user=None):
        col1, col2 = st.columns([1, 3])
        
        with col1:
            image_url = record.get('image_url', '')
            if image_url:
                st.image(image_url, width=80)
            else:
                st.write("No image")
        
        with col2:
            user_role = user.get('role', 'consignor') if user else 'consignor'
            
            # Show consignor info for admin users
            if user_role == 'admin' and record.get('consignor_name'):
                st.write(f"**👤 Consignor:** {record.get('consignor_name', '')}")
            
            st.write(f"**ID:** {record.get('id', '')}")
            st.write(f"**Barcode:** {record.get('barcode', '')}")
            st.write(f"**Catalog:** {record.get('catalog_number', '')}")
            st.write(f"**Genre:** {record.get('genre', '')}")
            
            artist = st.text_input("Artist", value=record.get('artist', ''), key=f"artist_edit_{index}")
            title = st.text_input("Title", value=record.get('title', ''), key=f"title_edit_{index}")
            
            all_genres = self._get_all_genres()
            current_genre = record.get('genre', '')
            genre_index = all_genres.index(current_genre) + 1 if current_genre in all_genres else 0
            genre = st.selectbox("Genre", options=[""] + all_genres, index=genre_index, key=f"genre_edit_{index}")
            
            compilation = st.checkbox("Compilation", value=record.get('compilation', False), key=f"compilation_{index}")
            
            # REMOVED: Store price editable field - users should not be able to edit store price here
            store_price = record.get('store_price', 0.0)
            st.write(f"**Store Price:** ${store_price:.2f}")
            
            youtube_url = st.text_input("YouTube URL", value=record.get('youtube_url', ''), key=f"youtube_{index}")
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if st.button("💾 Save", key=f"save_{index}", width='stretch'):
                    self._save_record_changes(record, artist, title, genre, compilation, store_price, youtube_url)
            
            with col_btn2:
                if st.button("🗑️ Delete", key=f"delete_{index}", width='stretch', type="secondary"):
                    if self._delete_record(record.get('id')):
                        st.success("Record deleted successfully!")
                        st.rerun()
            
            with col_btn3:
                if record.get('barcode'):
                    if st.button("🗑️ Clear Barcode", key=f"clear_barcode_{index}", width='stretch', type="secondary"):
                        if self._clear_barcode(record.get('id')):
                            st.success("Barcode cleared!")
                            st.rerun()

    def _save_record_changes(self, original_record, artist, title, genre, compilation, store_price, youtube_url):
        genre_id = None
        if genre:
            genres_df = st.session_state.db_manager.get_all_genres()
            genre_row = genres_df[genres_df['genre_name'] == genre]
            if not genre_row.empty:
                genre_id = genre_row.iloc[0]['id']
            else:
                success, new_genre_id = st.session_state.db_manager.add_genre(genre)
                if success:
                    genre_id = new_genre_id
        
        updates = {
            'artist': artist,
            'title': title,
            'genre_id': genre_id,
            'compilation': compilation,
            'youtube_url': youtube_url
            # REMOVED: store_price from updates - users should not be able to edit store price here
        }
        
        success = st.session_state.db_manager.update_record(original_record['id'], updates)
        if success:
            st.success("Record updated successfully!")
            st.rerun()
        else:
            st.error("Failed to update record")

    def _clear_barcode(self, record_id):
        success = st.session_state.db_manager.update_record(record_id, {'barcode': None})
        return success

    def _render_unified_results(self, results, result_type, user=None):
        for i, record in enumerate(results):
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
                
                # Show consignor name for admin users - ALWAYS SHOW IN SEARCH RESULTS FOR ADMINS
                user_role = user.get('role', 'consignor') if user else 'consignor'
                consignor_info = ""
                if user_role == 'admin' and record.get('consignor_name'):
                    consignor_info = f" 👤 {record.get('consignor_name')}"
                
                st.write(f"**{artist} - {title}{consignor_info}**")
                
                if result_type == "Edit or Delete item":
                    store_price = record.get('store_price')
                    discogs_suggested_price = record.get('discogs_suggested_price')
                    compilation = record.get('compilation', False)
                    consignor_name = record.get('consignor_name', '')
                    commission_rate = record.get('commission_rate')
                    
                    record_id = record.get('id', '')
                    barcode = record.get('barcode', '')
                    youtube_url = record.get('youtube_url', '')
                    catalog_number = record.get('catalog_number', '')
                    genre = record.get('genre', '')
                    
                    # FIXED: Always show consignor information for admin, show only for own records for consignor
                    user_role = user.get('role', 'consignor') if user else 'consignor'
                    user_id = user.get('id') if user else None
                    record_consignor_id = record.get('consignor_id')
                    
                    # Determine if we should show consignor info
                    show_consignor_info = False
                    if user_role == 'admin':
                        show_consignor_info = True  # Admin sees all consignor info
                    elif user_role == 'consignor' and user_id and record_consignor_id and str(user_id) == str(record_consignor_id):
                        show_consignor_info = True  # Consignor sees their own info
                    
                    st.write(f"**ID:** {record_id} | **Barcode:** {barcode}")
                    st.write(f"**Catalog:** {catalog_number}" if catalog_number else "**Catalog:** N/A")
                    st.write(f"**Genre:** {genre}" if genre else "**Genre:** N/A")
                    st.write(f"**Compilation:** {'✅ Yes' if compilation else '❌ No'}")
                    if show_consignor_info and consignor_name:
                        st.write(f"**Consignor:** {consignor_name} ({commission_rate*100 if commission_rate else 0}%)")
                    st.write(f"**Store Price:** ${store_price:.2f}" if store_price is not None else "**Store Price:** N/A")
                    st.write(f"**Discogs Price:** ${discogs_suggested_price:.2f}" if discogs_suggested_price and discogs_suggested_price > 0 else "**Discogs Price:** N/A")
                    if youtube_url:
                        st.write(f"🎵 **YouTube:** {youtube_url}")
                else:
                    catalog = record.get('catalog_number', '')
                    year = record.get('year', '')
                    format_info = record.get('format', '')
                    label_info = record.get('label', '')
                    country = record.get('country', '')
                    genre = record.get('genre', '')
                    
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
                    if 'loading_complete' in st.session_state:
                        del st.session_state.loading_complete
                    if 'loading_progress' in st.session_state:
                        del st.session_state.loading_progress
                    if 'loading_error' in st.session_state:
                        del st.session_state.loading_error
                    
                    st.rerun()
            
            with col4:
                if result_type == "Edit or Delete item":
                    # Only show delete button for admin or if user owns the record
                    user_role = user.get('role', 'consignor') if user else 'consignor'
                    user_id = user.get('id') if user else None
                    record_consignor_id = record.get('consignor_id')
                    
                    # Allow delete if: user is admin OR record has no consignor OR user is the consignor
                    show_delete = (user_role == 'admin') or (not record_consignor_id) or (user_id and str(record_consignor_id) == str(user_id))
                    
                    if show_delete:
                        if st.button("🗑️ Delete", key=f"delete_{result_type}_{i}", width='stretch', type="secondary"):
                            record_id = record.get('id')
                            if self._delete_record(record_id):
                                st.success("Record deleted successfully!")
                                st.rerun()
            
            st.divider()

    def render_selected_record_only(self, selected_record):
        # Don't render if record_added flag is set
        if st.session_state.get('record_added'):
            return
            
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
        
        if selected_record['type'] == 'discogs' and 'tracklist' in record:
            st.subheader("🎵 Album Tracklist")
            for i, track in enumerate(record['tracklist'], 1):
                st.write(f"{i}. {track}")
        
        if st.button("← Back to Results", key="back_to_results", width='stretch'):
            st.session_state.selected_record = None
            st.rerun()

    def render_edit_section(self, selected_record, add_callback, update_callback, discogs_handler=None, ebay_handler=None, store_fill_fraction=0.0):
        # Don't render if record_added flag is set
        if st.session_state.get('record_added'):
            return
            
        record_data = selected_record['data']
        
        if selected_record['type'] == 'discogs' and not record_data.get('pricing_fetched'):
            with st.spinner("🔄 Fetching pricing data from Discogs and YouTube..."):
                self._fetch_all_data_sync(record_data, discogs_handler, ebay_handler)
            
            record_data['pricing_fetched'] = True
            st.rerun()
            return
        
        st.subheader("Edit Properties")
        
        current_consignment_rate = self._calculate_consignment_rate(store_fill_fraction)
        
        st.info(f"**Store Fill:** {store_fill_fraction*100:.1f}% | **Current Consignment Rate:** {current_consignment_rate:.1%}")
        
        add_disabled = store_fill_fraction > 1.10
        
        if add_disabled:
            st.error("❌ Cannot add new items - store is over capacity!")
        
        duplicates_found = self._check_for_duplicate_simple(record_data)
        
        if duplicates_found:
            user = st.session_state.get('user', {})
            user_role = user.get('role', 'consignor')
            
            if user_role != 'admin':
                st.error("❌ **Cannot add duplicate record!**")
                return
            else:
                st.warning("⚠️ **Duplicate detected - you may proceed as admin**")
        
        user_id, commission_rate, store_return_days = self._render_consignment_section(record_data, current_consignment_rate)
        if user_id:
            record_data['consignor_id'] = user_id
            record_data['commission_rate'] = commission_rate
            record_data['store_return_days'] = store_return_days
        else:
            record_data['consignor_id'] = None
            record_data['commission_rate'] = None
            record_data['store_return_days'] = None
        
        raw_artist = record_data.get('artist', '')
        cleaned_artist = record_data.get('cleaned_artist', raw_artist)
        
        col1, col2 = st.columns(2)
        with col1:
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
        
        record_data['artist'] = edited_artist
        record_data['title'] = title
        
        st.write(f"*Original artist from Discogs: {raw_artist}*")
        
        compilation_default = self._should_be_compilation(edited_artist, record_data)
        compilation = st.checkbox(
            "This is a compilation",
            value=compilation_default,
            key="compilation_checkbox",
            help="Auto-detected for Various artists. Check if this is a compilation album."
        )
        record_data['compilation'] = compilation
        
        # Get Discogs genre from the record
        discogs_genre = record_data.get('genre', '')
        
        # Get suggested genre from mapping
        suggested_genre = self._get_suggested_genre(record_data)
        
        col1, col2 = st.columns(2)
        with col1:
            all_genres = self._get_all_genres()
            
            default_index = 0
            if suggested_genre and suggested_genre in all_genres:
                default_index = all_genres.index(suggested_genre) + 1
            
            genre = st.selectbox(
                "Genre:",
                options=[""] + all_genres,
                index=default_index,
                key="genre_edit"
            )
            
            # Show Discogs genre information
            if discogs_genre:
                suggestion_source = self._get_suggestion_source(record_data, suggested_genre)
                st.caption(f"Discogs Genre: {discogs_genre}")
                if suggested_genre:
                    st.caption(f"Suggested: {suggested_genre} ({suggestion_source})")
        
        # Store discogs_genre for later use in mapping
        record_data['discogs_genre'] = discogs_genre
        
        self._render_consolidated_pricing_information(record_data)
        
        with st.expander("🎵 YouTube Integration", expanded=False):
            self._render_youtube_integration(record_data)
        
        button_label = "Add to Database" if selected_record['type'] == 'discogs' else "Update Record"
        
        user_role = st.session_state.get('user', {}).get('role', 'consignor')
        is_admin = (user_role == 'admin')
        
        disabled_condition = not genre or (selected_record['type'] == 'discogs' and add_disabled) or (duplicates_found and not is_admin)
        
        if st.button(button_label, width='stretch', disabled=disabled_condition, key="add_to_database"):
            if selected_record['type'] == 'discogs':
                success, record_id = add_callback(genre)
                if success:
                    # The success handling is now in the callback
                    pass
            else:
                success = update_callback(genre)
                if success:
                    st.success(f"✅ Record updated successfully!")

    def _render_consolidated_pricing_information(self, record_data):
        """Simplified Discogs pricing section - just a dropdown"""
        has_discogs_data = 'price_suggestions' in record_data
        
        if has_discogs_data:
            st.write("### 📀 Discogs Pricing")
            
            price_suggestions = record_data.get('price_suggestions', {})
            
            if price_suggestions:
                # Create dropdown options with condition and price
                condition_options = []
                condition_descriptions = {}
                
                for condition, price in price_suggestions.items():
                    description = self._get_condition_description(condition)
                    condition_options.append(f"{condition} - ${price:.2f}")
                    condition_descriptions[condition] = description
                
                # Default selection
                default_condition = "Good Plus (G+)"
                default_index = 0
                for i, option in enumerate(condition_options):
                    if default_condition in option:
                        default_index = i
                        break
                
                # Simple dropdown
                selected_option = st.selectbox(
                    "Select Discogs condition:",
                    options=condition_options,
                    index=default_index,
                    key="discogs_condition_select"
                )
                
                # Extract selected condition and price
                for condition, price in price_suggestions.items():
                    if f"{condition} - ${price:.2f}" == selected_option:
                        record_data['selected_condition'] = condition
                        record_data['selected_price'] = price
                        
                        # Show description below dropdown
                        description = self._get_condition_description(condition)
                        st.caption(f"{description}")
                        break
            else:
                st.write("No Discogs pricing data available")
            
            st.divider()
        else:
            st.write("### 📀 Discogs Pricing")
            st.info("Discogs pricing data loading...")

    def _calculate_consignment_rate(self, fill_fraction):
        """Calculate consignment rate based on store fill fraction"""
        if fill_fraction < 0.60:
            return 0.10
        elif fill_fraction <= 1.10:
            slope = (0.40 - 0.10) / (1.10 - 0.60)
            return 0.10 + slope * (fill_fraction - 0.60)
        else:
            return 0.40

    def _check_for_duplicate_simple(self, record_data):
        """Check for duplicates using ONLY artist, title, and catalog number"""
        artist = record_data.get('artist', '')
        title = record_data.get('title', '')
        catalog_number = record_data.get('catalog_number', '')
        
        all_records = st.session_state.db_manager.get_all_records()
        
        if all_records.empty:
            return False
        
        if artist and title:
            artist_title_match = all_records[
                (all_records['artist'].str.lower() == artist.lower()) & 
                (all_records['title'].str.lower() == title.lower())
            ]
            if not artist_title_match.empty:
                return True
        
        if catalog_number:
            catalog_match = all_records[
                (all_records['catalog_number'].str.lower() == catalog_number.lower())
            ]
            if not catalog_match.empty:
                return True
        
        return False

    def _render_consignment_section(self, record_data=None, current_consignment_rate=0.10):
        current_user = st.session_state.get('user', {})
        user_role = current_user.get('role', 'consignor')
        current_user_id = current_user.get('id')
        
        # If user is consignor, they should NOT see commission rate or store return days fields
        # They should only be able to select that they are consigning
        if user_role == 'consignor' and current_user_id:
            user_id = current_user_id
            
            # Consignors get the current consignment rate automatically
            commission_rate = current_consignment_rate
            
            # Consignors get default store return days from config
            current_store_return_days = record_data.get('store_return_days')
            if current_store_return_days is None:
                current_store_return_days = int(st.session_state.db_manager.get_config_value('DEFAULT_STORE_RETURN_DAYS', '90'))
            
            store_return_days = current_store_return_days
            
            # Show info to consignor but NOT editable fields
            st.info(f"🔒 Consignor: {current_user.get('username', 'You')} (Consignor account)")
            st.info(f"📊 Commission Rate: {commission_rate:.1%} (auto-applied based on store fill)")
            st.info(f"📅 Store Return Days: {store_return_days} days (default)")
            
            # Consignor should have a simple checkbox to consign or not
            wants_to_consign = st.checkbox(
                "I want to consign this record",
                value=(record_data.get('consignor_id') == current_user_id),
                key="consignor_checkbox"
            )
            
            if wants_to_consign:
                return user_id, commission_rate, store_return_days
            else:
                return None, None, None
        
        # Admin flow - show all options
        users_df = st.session_state.db_manager.get_all_users()
        
        if len(users_df) == 0:
            st.info("No users available. Add users in the Consignment tab first.")
            return None, None, None
        
        options = ["Store Owned"]
        
        user_mapping = {}
        for _, user in users_df.iterrows():
            option_text = f"{user['username']} ({user['full_name'] or 'No name'})"
            options.append(option_text)
            user_mapping[option_text] = user['id']
        
        default_index = 0
        
        current_consignor_name = record_data.get('consignor_name', '')
        if current_consignor_name:
            for option_text in user_mapping.keys():
                if current_consignor_name in option_text:
                    default_index = options.index(option_text)
                    break
        
        selected_option = st.selectbox(
            "Consignor:",
            options=options,
            index=default_index,
            key="consignor_select"
        )
        
        if selected_option == "Store Owned":
            return None, None, None
        
        user_id = user_mapping.get(selected_option)
        
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
        if not artist:
            return False
        
        artist_lower = artist.lower()
        compilation_indicators = [
            'various',
            'various artists',
            'va',
            'v.a.',
            'compilation',
            'various artits',
            'various artiists'
        ]
        
        for indicator in compilation_indicators:
            if indicator in artist_lower:
                return True
        
        if record_data.get('compilation'):
            return True
            
        return False

    def _fetch_all_data_sync(self, record_data, discogs_handler, ebay_handler):
        release_id = record_data.get('discogs_id')
        if discogs_handler and release_id:
            pricing_data = discogs_handler.get_release_statistics_pricing(str(release_id))
            record_data['price_suggestions'] = pricing_data.get('price_suggestions', {})
            record_data['total_conditions'] = pricing_data.get('total_conditions', 0)
            
            tracklist = discogs_handler.get_release_tracklist(release_id)
            if tracklist:
                record_data['tracklist'] = tracklist
        
        if self.youtube_handler and self.youtube_handler.is_enabled():
            track_titles = record_data.get('tracklist', [])
            
            search_query = f"{record_data.get('artist', '')} {record_data.get('title', '')}"
            record_data['youtube_search_query'] = search_query
            youtube_results = self.youtube_handler.search_youtube_videos(search_query, record_data, track_titles)
            st.session_state.youtube_search_results = youtube_results

    def _get_suggested_genre(self, record_data):
        """Get suggested genre from Discogs genre mapping ONLY"""
        discogs_genre = record_data.get('genre', '')
        
        if discogs_genre:
            # Check if we have a mapping for this Discogs genre
            result = st.session_state.db_manager.get_discogs_genre_mapping(discogs_genre)
            
            if result and result.get('mapping'):
                local_genre_name = result['mapping']['local_genre_name']
                return local_genre_name
        
        # NO FALLBACK TO ARTIST HISTORY
        return ""

    def _get_suggestion_source(self, record_data, suggested_genre):
        discogs_genre = record_data.get('genre', '')
        
        # Only check if suggestion came from Discogs genre mapping
        if discogs_genre and suggested_genre:
            result = st.session_state.db_manager.get_discogs_genre_mapping(discogs_genre)
            if result and result.get('mapping'):
                return "Discogs genre mapping"
        
        return "No mapping found"

    def _get_all_genres(self):
        genres_df = st.session_state.db_manager.get_all_genres()
        return genres_df['genre_name'].tolist()

    def _get_condition_description(self, condition):
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
        current_youtube_url = record_data.get('youtube_url', '')
        if current_youtube_url:
            st.success(f"✅ Currently linked: {current_youtube_url}")
            
            st.markdown(f"[📺 Click here to view the video]({current_youtube_url})", unsafe_allow_html=True)
            
            if st.button("❌ Remove YouTube Link", key="remove_youtube", width='stretch'):
                record_data['youtube_url'] = ''
                st.success("YouTube link removed!")
                st.rerun()
        
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
        
        if 'youtube_search_results' in st.session_state and st.session_state.youtube_search_results:
            search_query = record_data.get('youtube_search_query', 'Unknown search')
            st.info(f"YouTube search '{search_query}' completed - {len(st.session_state.youtube_search_results)} results found")
            
            st.write("**Search Results:**")
            
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
                    
            if not track_results and not album_results and not other_results and st.session_state.youtube_search_results:
                st.write("**🎥 All Search Results:**")
                for i, video in enumerate(st.session_state.youtube_search_results):
                    self._render_youtube_video_option(video, i, record_data)
        else:
            st.info("No YouTube search results available")

    def _render_youtube_video_option(self, video, index, record_data):
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
            
            st.markdown(f"[📺 Watch this video]({video['url']})", unsafe_allow_html=True)
            
        with col3:
            if st.button("🔗 Link", key=f"youtube_link_{index}", width='stretch'):
                record_data['youtube_url'] = video['url']
                st.success(f"✅ Linked to: {video['title']}")
                st.rerun()
        
        with col4:
            st.markdown(f'<a href="{video["url"]}" target="_blank"><button style="width: 100%;">👀 View</button></a>', unsafe_allow_html=True)

    def _delete_record(self, record_id):
        success = st.session_state.db_manager.delete_record(record_id)
        if success:
            st.success("Record deleted successfully!")
            return True
        else:
            st.error("Failed to delete record")
            return False