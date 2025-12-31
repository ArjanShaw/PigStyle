import streamlit as st
import pandas as pd
from datetime import datetime
import time
from handlers.search_handler import SearchHandler
from handlers.commission_calculator import CommissionCalculator
from handlers.pricing_validator import PricingValidator
import re
import math
import requests
from datetime import datetime as dt
import os

class InventoryTab:
    def __init__(self, discogs_handler, ebay_handler=None, youtube_handler=None, config_cache=None, genre_cache=None, base_url="https://arjanshaw.pythonanywhere.com"):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
        self.youtube_handler = youtube_handler
        self.base_url = base_url
        self.config_cache = config_cache
        self.genre_cache = genre_cache
        
        self.search_handler = SearchHandler(discogs_handler, self.base_url)
        self.commission_calculator = CommissionCalculator(self)
        self.pricing_validator = PricingValidator(self, discogs_handler, ebay_handler)

    # API Client methods - now use RecordsCache
    
    def delete_record(self, record_id):
        """Delete a record via API - updates cache"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would delete record {record_id}")
            return True
            
        try:
            start_time = time.time()
            response = requests.delete(f"{self.base_url}/records/{record_id}")
            duration = time.time() - start_time
            
            print(f"API Delete Record ({record_id}) took {duration:.2f}s")
            
            if response.status_code == 200:
                # Mark records as updated
                if 'records_updated' not in st.session_state:
                    st.session_state.records_updated = 0
                st.session_state.records_updated += 1
                return True
            return False
        except Exception as e:
            st.error(f"API Error deleting record: {e}")
            return False
    
    def get_all_records(self):
        """Get all records via RecordsCache"""
        try:
            # Get records cache from session state
            if hasattr(st.session_state, 'records_cache'):
                records = st.session_state.records_cache
                # Convert to DataFrame for compatibility
                return pd.DataFrame(records) if isinstance(records, list) and records else pd.DataFrame()
            
            # Fallback: direct API call
            start_time = time.time()
            response = requests.get(f"{self.base_url}/records")
            duration = time.time() - start_time
            
            print(f"API Get All Records took {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])
                return pd.DataFrame(records) if records else pd.DataFrame()
            return pd.DataFrame()
        except Exception as e:
            st.error(f"API Error getting records: {e}")
            return pd.DataFrame()
    
    def get_recent_records(self, limit=10):
        """Get recent records via RecordsCache"""
        try:
            if hasattr(st.session_state, 'records_cache'):
                records = st.session_state.records_cache
                if isinstance(records, list) and records:
                    # Sort by ID descending
                    sorted_records = sorted(records, key=lambda x: x.get('id', 0), reverse=True)
                    return pd.DataFrame(sorted_records[:limit]) if sorted_records else pd.DataFrame()
            
            # Fallback: direct API call
            start_time = time.time()
            response = requests.get(f"{self.base_url}/records?limit={limit}&order_by=id&order=desc")
            duration = time.time() - start_time
            
            print(f"API Get Recent Records ({limit}) took {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])
                return pd.DataFrame(records) if records else pd.DataFrame()
            return pd.DataFrame()
        except Exception as e:
            st.error(f"API Error getting recent records: {e}")
            return pd.DataFrame()
    
    def get_record(self, record_id):
        """Get single record via RecordsCache"""
        try:
            if hasattr(st.session_state, 'records_cache'):
                records = st.session_state.records_cache
                if isinstance(records, list) and records:
                    for record in records:
                        if record.get('id') == record_id:
                            return record
            
            # Fallback: direct API call
            start_time = time.time()
            response = requests.get(f"{self.base_url}/records/{record_id}")
            duration = time.time() - start_time
            
            print(f"API Get Record ({record_id}) took {duration:.2f}s")
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"API Error getting record: {e}")
            return None
    
    def update_record(self, record_id, updates):
        """Update a record via API - updates cache"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would update record {record_id} with {updates}")
            return True
            
        try:
            start_time = time.time()
            response = requests.put(
                f"{self.base_url}/records/{record_id}",
                json=updates
            )
            duration = time.time() - start_time
            
            print(f"API Update Record ({record_id}) took {duration:.2f}s")
            
            if response.status_code == 200:
                # Mark records as updated
                if 'records_updated' not in st.session_state:
                    st.session_state.records_updated = 0
                st.session_state.records_updated += 1
                return True
            return False
        except Exception as e:
            st.error(f"API Error updating record: {e}")
            return False
    
    def search_records(self, search_term):
        """Search records via RecordsCache"""
        try:
            start_time = time.time()
            
            search_term = search_term.strip()
            if not search_term:
                return []
            
            # First try to use cache
            if hasattr(st.session_state, 'records_cache'):
                records = st.session_state.records_cache
                if isinstance(records, list) and records:
                    search_lower = search_term.lower()
                    filtered = []
                    
                    for record in records:
                        artist = str(record.get('artist', '')).lower()
                        title = str(record.get('title', '')).lower()
                        catalog = str(record.get('catalog_number', '')).lower()
                        barcode = str(record.get('barcode', '')).lower()
                        
                        if (search_lower in artist or 
                            search_lower in title or 
                            search_lower in catalog or 
                            search_lower in barcode):
                            filtered.append(record)
                    
                    duration = time.time() - start_time
                    print(f"Cached Search: {search_term[:30]}... took {duration:.2f}s")
                    return filtered
            
            # Fallback to API
            response = requests.get(f"{self.base_url}/search?q={search_term}", timeout=10)
            
            duration = time.time() - start_time
            
            print(f"API Search: {search_term[:30]}... took {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and data.get('status') == 'success':
                    records = data.get('records', [])
                    if records:
                        return records
                
                return []
            else:
                return []
                
        except requests.exceptions.Timeout:
            st.warning("Search timeout")
            return []
        except Exception as e:
            st.error(f"API Error searching records: {e}")
            return []
    
    def get_records_by_user(self, user_id):
        """Get records for specific user via RecordsCache"""
        try:
            if hasattr(st.session_state, 'records_cache'):
                records = st.session_state.records_cache
                if isinstance(records, list) and records:
                    user_records = [r for r in records if r.get('consignor_id') == user_id]
                    return user_records
            
            # Fallback: direct API call
            start_time = time.time()
            response = requests.get(f"{self.base_url}/records/user/{user_id}")
            duration = time.time() - start_time
            
            print(f"API Get User Records ({user_id}) took {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('records', [])
            return []
        except Exception as e:
            st.error(f"API Error getting user records: {e}")
            return []
    
    def get_config_value(self, config_key, default=None):
        """Get config value from cache"""
        if self.config_cache:
            return self.config_cache.get(config_key, default)
        return default
    
    def get_all_config(self):
        """Get all config values via API"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/config")
            duration = time.time() - start_time
            
            print(f"API Get All Config took {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                return data.get('configs', {})
            return {}
        except Exception as e:
            st.error(f"API Error getting all config: {e}")
            return {}
    
    def get_all_genres(self):
        """Get all genres via cache"""
        if self.genre_cache:
            return self.genre_cache.get_genres_list()
        return []
    
    def add_genre(self, genre_name):
        """Add new genre via API"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would add genre '{genre_name}'")
            return True, 999
            
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/genres",
                json={'genre_name': genre_name}
            )
            duration = time.time() - start_time
            
            print(f"API Add Genre: {genre_name} took {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                if self.genre_cache:
                    self.genre_cache.refresh()
                return True, data.get('genre_id')
            return False, None
        except Exception as e:
            st.error(f"API Error adding genre: {e}")
            return False, None
    
    def get_discogs_genre_mapping(self, discogs_genre):
        """Get Discogs genre mapping via cache"""
        if self.genre_cache:
            return self.genre_cache.get_discogs_genre_mapping(discogs_genre)
        return {'mapping': None, 'status': 'error'}
    
    def get_records_count(self):
        """Get records count from cache (efficient)"""
        try:
            if hasattr(st.session_state, 'records_cache'):
                records = st.session_state.records_cache
                if isinstance(records, list):
                    return len(records)
                
            return 0
        except Exception as e:
            print(f"Error getting records count: {e}")
            return 0
    
    def get_user(self, user_id):
        """Get user by ID"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/users/{user_id}")
            duration = time.time() - start_time
            
            print(f"API Get User ({user_id}) took {duration:.2f}s")            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"API Error getting user: {e}")
            return None

    # Main InventoryTab methods
    
    def _get_config_value(self, config_key):
        """Get config value using config cache"""
        value = self.get_config_value(config_key, None)
        if value is not None:
            if config_key == 'STORE_CAPACITY':
                return int(value)
            else:
                return float(value)
        return None

    def render(self):
        # Get records count from cache (efficient)
        records_count = self.get_records_count()
        
        try:
            store_fill_info = self._get_store_fill_info()
            current_commission_rate = self.commission_calculator.get_current_commission_rate()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Inventory Records", records_count)
            with col2:
                st.metric("Store Fill", f"{store_fill_info['fill_percentage']:.1f}%")
            with col3:
                st.metric("Commission Rate", f"{current_commission_rate*100:.1f}%")
            
            if store_fill_info['fill_fraction'] > 1.10:
                st.error("🚨 Store is over capacity! Cannot add new items.")
            elif store_fill_info['fill_fraction'] > 0.90:
                st.warning("⚠️ Store is near capacity ({:.1f}%)".format(store_fill_info['fill_percentage']))
                
        except ValueError as e:
            st.error(f"Configuration error 2: {e}")
            st.info("Please check configuration values for commission calculation")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Inventory Records", records_count)
            with col2:
                st.info("Store fill: N/A")
            with col3:
                st.info("Commission: N/A")
        
        self._render_last_added_record_simple()
        
        try:
            store_fill_info = self._get_store_fill_info()
            store_fill_fraction = store_fill_info['fill_fraction']
        except:
            store_fill_fraction = 0
            
        self._render_unified_operations(store_fill_fraction)

    def _render_last_added_record_simple(self):
        """Display the last record added to the database"""
        user = st.session_state.get('user', {})
        user_id = user.get('id')
        user_role = user.get('role')
        is_demo = user.get('username') == 'demo_user'
        is_admin = user_role == 'admin'
        
        if is_demo:
            if 'demo_last_added' in st.session_state:
                last_record = st.session_state.demo_last_added
                artist = last_record.get('artist', 'Demo Artist')
                title = last_record.get('title', 'Demo Album')
                store_price = last_record.get('store_price', 19.99)
                
                display_text = f"**📝 Last Added:** {artist} - {title} (${store_price:.2f})"
                st.markdown(display_text)
            else:
                st.markdown("**📝 Last Added:** No records yet")
            
            if hasattr(st.session_state, 'demo_credit_balance'):
                credit_balance = st.session_state.demo_credit_balance
                st.caption(f"💡 Demo Credit Balance: ${credit_balance:.2f} (matches sold records)")
        else:
            if is_admin:
                recent_records = self.get_recent_records(limit=1)
            else:
                if user_id:
                    user_records = self.get_records_by_user(user_id)
                    if user_records:
                        user_records.sort(key=lambda x: x.get('id', 0), reverse=True)
                        recent_records = pd.DataFrame(user_records[:1]) if user_records else pd.DataFrame()
                    else:
                        recent_records = pd.DataFrame()
                else:
                    recent_records = pd.DataFrame()
            
            if not recent_records.empty:
                last_record = recent_records.iloc[0]
                
                artist = last_record.get('artist', 'Unknown Artist')
                title = last_record.get('title', 'Unknown Title')
                store_price = last_record.get('store_price', 0.0)
                
                display_text = f"**📝 Last Added:** {artist} - {title} (${store_price:.2f})"
                
                st.markdown(display_text)
            else:
                st.markdown("**📝 Last Added:** No records yet")

    def _render_unified_operations(self, store_fill_fraction):
        if 'search_type' not in st.session_state:
            st.session_state.search_type = "Edit or Delete item"
        if 'current_search' not in st.session_state:
            st.session_state.current_search = ""
        if 'search_results' not in st.session_state:
            st.session_state.search_results = {}
        if 'selected_record' not in st.session_state:
            st.session_state.selected_record = None
        if 'record_added' not in st.session_state:
            st.session_state.record_added = None
        if 'search_triggered' not in st.session_state:
            st.session_state.search_triggered = False
        if 'search_query' not in st.session_state:
            st.session_state.search_query = ""
        if 'last_search_term' not in st.session_state:
            st.session_state.last_search_term = ""
        
        if st.session_state.get('record_added'):
            keys_to_clear = [key for key in st.session_state.keys() if key.startswith('discogs_result_')]
            for key in keys_to_clear:
                del st.session_state[key]
            
            st.session_state.selected_record = None
            st.session_state.record_added = None
            st.session_state.search_results = {}
            st.session_state.current_search = ""
            st.session_state.search_query = ""
            st.rerun()
        
        col1, col2 = st.columns([1, 3])
        with col1:
            search_type = st.radio(
                "Action:",
                ["Add item", "Edit or Delete item"],
                key="search_type_radio",
                disabled=(store_fill_fraction > 1.10 and "Add item" in ["Add item"])
            )
        
        search_disabled = (store_fill_fraction > 1.10 and search_type == "Add item")
        
        with st.form(key="search_form", clear_on_submit=False):
            search_input = st.text_input(
                "Search:",
                value=st.session_state.get('search_query', ''),
                placeholder="Enter barcode, artist, or title...",
                key="unified_search_input",
                disabled=search_disabled
            )
            
            col1, col2 = st.columns([3, 1])
            with col1:
                search_submitted = st.form_submit_button("🔍 Search", width='stretch', disabled=search_disabled)
        
        if search_submitted:
            if search_input != st.session_state.get('last_search_term', ''):
                keys_to_clear = [key for key in st.session_state.keys() if key.startswith('discogs_result_')]
                for key in keys_to_clear:
                    del st.session_state[key]
                
                st.session_state.search_results = {}
                st.session_state.current_search = ""
                st.session_state.selected_record = None
                st.session_state.record_added = None
                
                st.session_state.search_query = search_input
                st.session_state.search_triggered = True
                st.session_state.last_search_term = search_input
        
        if (st.session_state.search_triggered and 
            st.session_state.search_query and 
            st.session_state.search_query.strip()):
            
            search_term = st.session_state.search_query.strip()
            st.session_state.current_search = search_term
            st.session_state.selected_record = None
            st.session_state.record_added = None
            
            if search_type == "Add item":
                results = self.search_handler.perform_discogs_search(search_term)
                st.session_state[f"discogs_search_{search_term}"] = results
                st.session_state.search_results[search_term] = results
                
                self._render_discogs_results(results, search_type)
                
            else:
                user = st.session_state.get('user', {})
                results = self._perform_database_search(search_term, user)
                st.session_state.search_results[search_term] = results
                
                self._render_database_results(results, search_type, st.session_state.get('user', {}))
            
            st.session_state.search_triggered = False
            st.session_state.last_search = search_term
        
        elif search_type == "Add item" and st.session_state.get('last_search_term'):
            search_term = st.session_state.get('last_search_term', '')
            results = st.session_state.get(f"discogs_search_{search_term}", [])
            if results:
                self._render_discogs_results(results, search_type)
        
        elif search_type == "Edit or Delete item" and st.session_state.get('last_search_term'):
            search_term = st.session_state.get('last_search_term', '')
            results = st.session_state.get('search_results', {}).get(search_term, [])
            if results:
                user = st.session_state.get('user', {})
                self._render_database_results(results, search_type, user)
    
    def _render_discogs_results(self, results, search_type):
        if not results:
            st.warning("No results found on Discogs")
            return
        
        st.write(f"**Found {len(results)} results**")
        
        for i, record in enumerate(results):
            self._render_discogs_result_item(record, i)

    def _render_discogs_result_item(self, record, index):
        record_key = f"discogs_result_{record.get('discogs_id', '')}_{record.get('artist', '')}_{record.get('title', '')}"
        
        if f"{record_key}_data" not in st.session_state:
            st.session_state[f"{record_key}_data"] = {
                'record_data': record.copy(),
                'selected_condition': None,
                'price_research': None,
                'advised_price': None,
                'user_price': None,
                'last_researched_condition': None,
                'selected_genre': None
            }
        
        stored_data = st.session_state[f"{record_key}_data"]
        
        col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 1])
        
        with col1:
            image_url = stored_data['record_data'].get('image_url', '')
            if image_url:
                st.image(image_url, width=80)
            else:
                st.write("No image")
        
        with col2:
            artist = stored_data['record_data'].get('artist', '')
            title = stored_data['record_data'].get('title', '')
            
            st.write(f"**{artist} - {title}**")
            
            catalog = stored_data['record_data'].get('catalog_number', '')
            year = stored_data['record_data'].get('year', '')
            format_info = stored_data['record_data'].get('format', '')
            label_info = stored_data['record_data'].get('label', '')
            country = stored_data['record_data'].get('country', '')
            discogs_genre = stored_data['record_data'].get('genre', '')
            
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
            if discogs_genre:
                info_lines.append(f"**Discogs Genre:** {discogs_genre}")
            
            if info_lines:
                for line in info_lines:
                    st.write(line)
            else:
                st.write("*No additional info*")
            
            all_genres = self.get_all_genres()
            
            suggested_genre = self._get_suggested_genre(stored_data['record_data'])
            
            default_index = 0
            if suggested_genre and suggested_genre in all_genres:
                default_index = all_genres.index(suggested_genre) + 1
            elif stored_data.get('selected_genre') and stored_data['selected_genre'] in all_genres:
                default_index = all_genres.index(stored_data['selected_genre']) + 1
            
            genre_key = f"genre_select_{record_key}"
            selected_genre = st.selectbox(
                "Genre:",
                options=["Select genre..."] + all_genres,
                index=default_index,
                key=genre_key
            )
            
            if selected_genre != "Select genre...":
                stored_data['selected_genre'] = selected_genre
            else:
                stored_data['selected_genre'] = None
        
        with col3:
            user = st.session_state.get('user', {})
            user_role = user.get('role', 'consignor')
            
            discogs_conditions = [
                "Mint (M)",
                "Near Mint (NM or M-)", 
                "Very Good Plus (VG+)",
                "Very Good (VG)",
                "Good Plus (G+)",
                "Good (G)",
                "Fair (F)",
                "Poor (P)"
            ]
            
            if user_role == 'consignor':
                available_conditions = ["Mint (M)", "Near Mint (NM or M-)", "Very Good Plus (VG+)", "Very Good (VG)"]
            else:
                available_conditions = discogs_conditions
            
            previous_selection = stored_data['selected_condition']
            
            options = ["Select condition..."] + available_conditions
            
            default_index = 0
            if previous_selection and previous_selection in available_conditions:
                default_index = available_conditions.index(previous_selection) + 1
            
            selectbox_key = f"condition_select_{record_key}"
            
            selected_condition = st.selectbox(
                "Condition",
                options=options,
                index=default_index,
                key=selectbox_key
            )
            
            if selected_condition != "Select condition...":
                if selected_condition != stored_data['selected_condition']:
                    stored_data['selected_condition'] = selected_condition
                    stored_data['last_researched_condition'] = None
                    
                    with st.spinner(f"Researching {selected_condition} prices..."):
                        discogs_price = self._get_discogs_price_for_condition(
                            stored_data['record_data'], 
                            selected_condition
                        )
                        
                        ebay_prices = self._get_ebay_prices_for_condition(
                            stored_data['record_data'].get('artist', ''), 
                            stored_data['record_data'].get('title', ''),
                            selected_condition
                        )
                        
                        advised_price = self._calculate_advised_price(discogs_price, ebay_prices, selected_condition)
                        
                        stored_data['price_research'] = {
                            'discogs_price': discogs_price,
                            'ebay_prices': ebay_prices,
                            'advised_price': advised_price,
                            'selected_condition': selected_condition
                        }
                        stored_data['advised_price'] = advised_price
                        stored_data['last_researched_condition'] = selected_condition
                        
                        if advised_price and advised_price > 0:
                            stored_data['user_price'] = advised_price
                        
                        st.session_state[f"{record_key}_data"] = stored_data
                        
                        st.rerun()
        
        with col4:
            if (stored_data['selected_condition'] and 
                stored_data['selected_condition'] != "Select condition..." and
                stored_data.get('price_research')):
                
                advised_price = stored_data.get('advised_price')
                
                max_ratio_value = self.get_config_value('MAX_PRICE_TO_ADV_RATIO', '1.3')
                max_ratio = float(max_ratio_value) if max_ratio_value else 1.3
                
                max_allowed = advised_price * max_ratio if advised_price and advised_price > 0 else 0
                
                current_price = stored_data.get('user_price')
                if current_price is None and advised_price:
                    current_price = advised_price
                elif current_price is None:
                    current_price = 0.0
                
                price_input_key = f"price_input_{record_key}"
                user_price = st.number_input(
                    "Price ($)",
                    min_value=0.0,
                    max_value=float(max_allowed * 1.5),
                    value=float(current_price),
                    step=0.01,
                    format="%.2f",
                    key=price_input_key,
                    help=f"Max: ${max_allowed:.2f}" if max_allowed > 0 else "Enter price"
                )
                
                if user_price != stored_data.get('user_price'):
                    stored_data['user_price'] = user_price
                    st.session_state[f"{record_key}_data"] = stored_data
                
                if stored_data.get('price_research'):
                    with st.expander("📊 Price Details", expanded=False):
                        self._render_price_research_details(stored_data['price_research'], stored_data['record_data'])
            elif stored_data['selected_condition'] and stored_data['selected_condition'] != "Select condition...":
                st.info("Researching prices...")
            else:
                st.info("Select condition first")
        
        with col5:
            add_enabled = (
                stored_data['selected_condition'] and 
                stored_data['selected_condition'] != "Select condition..." and
                stored_data.get('user_price') and 
                stored_data.get('user_price', 0) > 0 and
                stored_data.get('selected_genre') and
                stored_data['selected_genre'] != "Select genre..."
            )
            
            add_button_key = f"add_{record_key}"
            if add_enabled:
                if st.button("➕ Add", key=add_button_key, type="primary", width='stretch'):
                    record_to_add = stored_data['record_data'].copy()
                    record_to_add['selected_condition'] = stored_data['selected_condition']
                    record_to_add['user_price'] = stored_data['user_price']
                    record_to_add['advised_price'] = stored_data.get('advised_price')
                    record_to_add['price_research'] = stored_data.get('price_research')
                    record_to_add['genre'] = stored_data['selected_genre']
                    record_to_add['discogs_genre'] = record_to_add.get('genre', '')
                    
                    user = st.session_state.get('user', {})
                    consignor_id = user.get('id')
                    
                    success, record_id = self._handle_add_record_direct(
                        record_to_add, 
                        stored_data['selected_genre'], 
                        stored_data['user_price'],
                        consignor_id
                    )
                    
                    if success:
                        del st.session_state[f"{record_key}_data"]
                        st.session_state.record_added = True
                        
                        if user.get('username') == 'demo_user':
                            st.session_state.demo_last_added = {
                                'artist': record_to_add['artist'],
                                'title': record_to_add['title'],
                                'store_price': stored_data['user_price']
                            }
                        
                        st.success(f"✅ Record added successfully! ID: {record_id}")
                        st.rerun()
                    else:
                        st.error("Failed to add record to database")
            else:
                st.button("➕ Add", key=f"add_disabled_{record_key}", disabled=True, width='stretch')
        
        st.divider()
        
        st.session_state[f"{record_key}_data"] = stored_data

    def _handle_add_record_direct(self, record_data, genre, user_price=None, consignor_id=None):
        """Handle adding a record directly to the database"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.success(f"✅ Demo: Record '{record_data.get('artist', '')} - {record_data.get('title', '')}' would be added")
            st.info("💡 In a real session, this would be saved to the database.")
            return True, 999
            
        if consignor_id:
            record_data['consignor_id'] = consignor_id
        
        if user_price is not None:
            validation = self.pricing_validator.validate_user_price(user_price, record_data)
            if not validation['is_valid']:
                st.error(f"❌ Price validation failed: {validation['reason']}")
                st.info(f"Maximum allowed price: ${validation['max_allowed']:.2f} (based on advised price: ${validation['advised_price']:.2f})")
                return False, None
            
            record_data['selected_price'] = user_price
            record_data['original_consignor_price'] = user_price
        
        success, record_id = self._add_inventory_record(
            record_data, 
            genre, 
            st.session_state.current_search,
            consignor_id
        )
        
        return success, record_id

    def _add_inventory_record(self, record_data, genre, search_term, consignor_id=None):
        """Add inventory record to database via API"""
        if genre is None:
            raise Exception("genre parameter is required but was None")
        
        from handlers.pricing_validator import PricingValidator
        pricing_validator = PricingValidator(self, self.discogs_handler, self.ebay_handler)
        duplicates_found = pricing_validator.check_for_duplicates(record_data)
        
        if duplicates_found:
            user = st.session_state.get('user', {})
            user_role = user.get('role', 'consignor')
            
            if user_role != 'admin':
                st.error("❌ **Cannot add duplicate record!**")
                return False, None
            else:
                st.warning("⚠️ **Duplicate detected - you may proceed as admin**")
        
        release_id = record_data.get('discogs_id')
        
        if not release_id:
            st.error("No release ID found")
            return False, None
        
        format_selected = st.session_state.get('format_select', 'Vinyl')
        
        pricing_data = None
        
        if self.discogs_handler:
            with st.spinner("Fetching Discogs price suggestions..."):
                pricing_data = self.discogs_handler.get_release_statistics_pricing(str(release_id))
        else:
            st.error("Discogs handler not available")
            return False, None
        
        artist = record_data.get('artist', '')
        title = record_data.get('title', '')
        image_url = record_data.get('image_url', '')
        catalog_number = record_data.get('catalog_number', '')
        youtube_url = record_data.get('youtube_url', '')
        
        selected_condition = record_data.get('selected_condition')
        user_price = record_data.get('user_price')
        
        compilation = record_data.get('compilation', False)
        
        if consignor_id is None:
            consignor_id = record_data.get('consignor_id')
        
        try:
            commission_rate = self.commission_calculator.get_current_commission_rate()
        except ValueError as e:
            st.error(f"Cannot determine commission rate: {e}")
            return False, None
        
        discogs_genre = record_data.get('discogs_genre', '')
        
        genre_id = None
        if genre and self.genre_cache:
            genre_data = self.genre_cache.get_genres_data()
            if genre_data:
                for genre_item in genre_data:
                    if genre_item.get('genre_name') == genre:
                        genre_id = genre_item.get('id')
                        break
        
        if genre and not genre_id:
            success, new_genre_id = self.add_genre(genre)
            if success:
                genre_id = int(new_genre_id)
            else:
                st.error(f"Failed to create new genre: {genre}")
                return False, None
        
        if pricing_data:
            record_data['price_suggestions'] = pricing_data.get('price_suggestions', {})
        
        advised_price = record_data.get('advised_price')
        
        if user_price is not None and user_price > 0:
            store_price = user_price
        elif advised_price is not None and advised_price > 0:
            store_price = self._calculate_store_price(advised_price)
        else:
            store_price = self._calculate_store_price_from_suggestions(record_data, selected_condition)
        
        ebay_sell_at = record_data.get('ebay_sell_at', 0.0)
        
        consignment_start_date = None
        discount_eligible_date = None
        original_consignor_price = None
        
        if consignor_id:
            consignment_start_date = dt.now().date()
            try:
                full_price_days = int(self.get_config_value('CONSIGNMENT_FULL_PRICE_DAYS', '90'))
            except:
                full_price_days = 90
            discount_eligible_date = consignment_start_date + pd.Timedelta(days=full_price_days)
            original_consignor_price = store_price
        
        try:
            record_data_to_save = {
                'artist': artist,
                'title': title,
                'barcode': '',
                'genre_id': genre_id,
                'image_url': image_url,
                'catalog_number': catalog_number,
                'format': format_selected,
                'condition': selected_condition,
                'store_price': float(store_price),
                'ebay_sell_at': float(ebay_sell_at) if ebay_sell_at else 0.0,
                'youtube_url': youtube_url,
                'compilation': bool(compilation)
            }
            
            if consignor_id:
                record_data_to_save['consignor_id'] = int(consignor_id)
                record_data_to_save['commission_rate'] = float(commission_rate)
                record_data_to_save['consignment_start_date'] = consignment_start_date.isoformat() if consignment_start_date else None
                record_data_to_save['discount_eligible_date'] = discount_eligible_date.isoformat() if discount_eligible_date else None
                record_data_to_save['original_consignor_price'] = float(original_consignor_price) if original_consignor_price else None
            
            start_time = time.time()
            
            response = requests.post(
                f"{self.base_url}/records",
                json=record_data_to_save,
                timeout=10
            )
            
            duration = time.time() - start_time
            
            print(f"API Add Record: {artist[:15]} - {title[:15]}... took {duration:.2f}s")

            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == 'success':
                    record_id = response_data.get('record_id')
                    
                    if discogs_genre and genre_id:
                        mapping_data = {
                            'discogs_genre': discogs_genre,
                            'local_genre_id': genre_id
                        }
                        mapping_response = requests.post(
                            f"{self.base_url}/discogs-genre-mappings",
                            json=mapping_data,
                            timeout=5
                        )
                        if mapping_response.status_code == 200:
                            mapping_data = mapping_response.json()
                            if mapping_data.get('status') == 'success':
                                pass
                    
                    # Mark records as updated
                    if 'records_updated' not in st.session_state:
                        st.session_state.records_updated = 0
                    st.session_state.records_updated += 1
                    
                    return True, record_id
                else:
                    error_msg = response_data.get('error', 'Unknown error from API')
                    st.error(f"Failed to save record: {error_msg}")
                    return False, None
            else:
                st.error(f"API request failed with status {response.status_code}")
                return False, None
                
        except requests.exceptions.Timeout:
            st.error("API request timed out. Please try again.")
            return False, None
        except Exception as e:
            st.error(f"Error saving record: {str(e)}")
            return False, None

    def _calculate_store_price_from_suggestions(self, record_data, selected_condition):
        price_suggestions = record_data.get('price_suggestions', {})
        
        if not price_suggestions:
            return 0.0
        
        condition_map = {
            'Mint (M)': ['Mint (M)', 'M', 'Mint'],
            'Near Mint (NM or M-)': ['Near Mint (NM or M-)', 'NM', 'M-', 'Near Mint'],
            'Very Good Plus (VG+)': ['Very Good Plus (VG+)', 'VG+'],
            'Very Good (VG)': ['Very Good (VG)', 'VG'],
            'Good Plus (G+)': ['Good Plus (G+)', 'G+'],
            'Good (G)': ['Good (G)', 'G'],
            'Fair (F)': ['Fair (F)', 'F'],
            'Poor (P)': ['Poor (P)', 'P']
        }
        
        for discogs_condition, price in price_suggestions.items():
            if price and price > 0:
                for pattern in condition_map.get(selected_condition, []):
                    if pattern.lower() in discogs_condition.lower():
                        return self._calculate_store_price(float(price))
        
        valid_prices = [float(p) for p in price_suggestions.values() if p]
        if valid_prices:
            lowest_price = min(valid_prices)
            return self._calculate_store_price(lowest_price)
        
        return 0.0

    def _calculate_store_price(self, discogs_suggested_price):
        try:
            estimated_multiplier = self.get_config_value('STORE_PRICE_ESTIMATED_MULTIPLIER', '2.0')
            minimum_price = self.get_config_value('STORE_PRICE_MINIMUM', '5.0')
            
            estimated_multiplier = float(estimated_multiplier)
            minimum_price = float(minimum_price)
            
            candidates = []
            
            if discogs_suggested_price and discogs_suggested_price > 0:
                candidates.append(discogs_suggested_price * estimated_multiplier)
            
            if candidates:
                raw_price = max(candidates)
                raw_price = max(raw_price, minimum_price)
            else:
                raw_price = minimum_price
            
            store_price = self._round_to_49_or_99(raw_price)
            
            return store_price
            
        except Exception as e:
            try:
                minimum_price = float(self.get_config_value('STORE_PRICE_MINIMUM', '5.0'))
                return minimum_price
            except:
                return 5.0

    def _round_to_49_or_99(self, price):
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

    def _get_discogs_price_for_condition(self, record, selected_condition):
        try:
            if not self.discogs_handler or 'discogs_id' not in record:
                return None
            
            release_id = record.get('discogs_id')
            if not release_id:
                return None
            
            pricing_data = self.discogs_handler.get_release_statistics_pricing(str(release_id))
            if not pricing_data or 'price_suggestions' not in pricing_data:
                return None
            
            price_suggestions = pricing_data.get('price_suggestions', {})
            
            condition_map = {
                'Mint (M)': ['Mint (M)', 'M', 'Mint'],
                'Near Mint (NM or M-)': ['Near Mint (NM or M-)', 'NM', 'M-', 'Near Mint'],
                'Very Good Plus (VG+)': ['Very Good Plus (VG+)', 'VG+'],
                'Very Good (VG)': ['Very Good (VG)', 'VG'],
                'Good Plus (G+)': ['Good Plus (G+)', 'G+'],
                'Good (G)': ['Good (G)', 'G'],
                'Fair (F)': ['Fair (F)', 'F'],
                'Poor (P)': ['Poor (P)', 'P']
            }
            
            for discogs_condition, price in price_suggestions.items():
                if price and price > 0:
                    for pattern in condition_map.get(selected_condition, []):
                        if pattern.lower() in discogs_condition.lower():
                            return float(price)
            
            for discogs_condition, price in price_suggestions.items():
                if price and price > 0:
                    return float(price)
            
            return None
            
        except Exception as e:
            st.error(f"Error getting Discogs price: {e}")
            return None

    def _get_ebay_prices_for_condition(self, artist, title, selected_condition):
        try:
            if not self.ebay_handler:
                return None
            
            ebay_data = self.ebay_handler.get_ebay_pricing(artist, title)
            if not ebay_data:
                return None
            
            all_listings = []
            for condition_group in ebay_data.get('condition_pricing', {}).values():
                all_listings.extend(condition_group.get('listings', []))
            
            all_prices = [listing.get('base_price', 0) for listing in all_listings if listing.get('base_price', 0) > 0]
            generic_median = self._calculate_median(all_prices) if all_prices else 0
            
            condition_patterns = {
                'Mint (M)': [r'\bmint\b', r'\bm\b', r'\bstill sealed\b'],
                'Near Mint (NM or M-)': [r'\bnear mint\b', r'\bnm\b', r'\bm-\b'],
                'Very Good Plus (VG+)': [r'\bvery good plus\b', r'\bvg\+\b', r'\bvg\s*\+\s*'],
                'Very Good (VG)': [r'\bvery good\b', r'\bvg\b'],
                'Good Plus (G+)': [r'\bgood plus\b', r'\bg\+\b', r'\bg\s*\+\s*'],
                'Good (G)': ['Good (G)', 'G'],
                'Fair (F)': ['Fair (F)', 'F'],
                'Poor (P)': ['Poor (P)', 'P']
            }
            
            condition_listings = []
            patterns = condition_patterns.get(selected_condition, [])
            
            for listing in all_listings:
                item_data = listing.get('item_data', {})
                title_text = item_data.get('title', '').lower()
                
                for pattern in patterns:
                    if re.search(pattern, title_text, re.IGNORECASE):
                        condition_listings.append(listing)
                        break
            
            condition_prices = [listing.get('base_price', 0) for listing in condition_listings if listing.get('base_price', 0) > 0]
            condition_median = self._calculate_median(condition_prices) if condition_prices else 0
            
            return {
                'generic_median': generic_median,
                'condition_median': condition_median,
                'generic_count': len(all_prices),
                'condition_count': len(condition_prices),
                'all_listings': all_listings,
                'condition_listings': condition_listings,
                'search_query': f"{artist} {title}",
                'condition': selected_condition,
                'raw_data': ebay_data
            }
            
        except Exception as e:
            st.error(f"Error getting eBay prices: {e}")
            return None

    def _calculate_advised_price(self, discogs_price, ebay_prices, selected_condition):
        candidates = []
        
        if discogs_price and discogs_price > 0:
            candidates.append(discogs_price)
        
        if ebay_prices:
            if ebay_prices['condition_count'] >= 3 and ebay_prices['condition_median'] > 0:
                candidates.append(ebay_prices['condition_median'])
            elif ebay_prices['generic_median'] > 0:
                candidates.append(ebay_prices['generic_median'])
        
        return min(candidates) if candidates else 0.0

    def _calculate_median(self, prices):
        if not prices:
            return 0.0
        
        valid_prices = [p for p in prices if p is not None and p > 0]
        if not valid_prices:
            return 0.0
        
        sorted_prices = sorted(valid_prices)
        n = len(sorted_prices)
        
        if n % 2 == 1:
            return float(sorted_prices[n // 2])
        else:
            return float((sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) / 2)

    def _render_price_research_details(self, research, record):
        st.write(f"**Research for:** {record.get('artist', '')} - {record.get('title', '')}")
        st.write(f"**Selected Condition:** {research['selected_condition']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Discogs Price Research:**")
            if research.get('discogs_price'):
                st.write(f"Price found: ${research['discogs_price']:.2f}")
            else:
                st.write("No price found for this condition")
                
            with st.expander("Discogs Debug Info", expanded=False):
                st.write(f"Artist: {record.get('artist')}")
                st.write(f"Title: {record.get('title')}")
                st.write(f"Discogs ID: {record.get('discogs_id')}")
                st.write(f"Condition searched: {research['selected_condition']}")
                if 'discogs_id' in record:
                    st.write(f"API URL: https://api.discogs.com/releases/{record['discogs_id']}")
        
        with col2:
            st.write("**eBay Research:**")
            if research.get('ebay_prices'):
                ebay = research['ebay_prices']
                st.write(f"Generic median: ${ebay['generic_median']:.2f} ({ebay['generic_count']} listings)")
                st.write(f"Condition median: ${ebay['condition_median']:.2f} ({ebay['condition_count']} listings)")
                
                with st.expander("eBay Debug Info", expanded=False):
                    st.write(f"Search query: {ebay.get('search_query', 'N/A')}")
                    st.write(f"Raw listings found: {len(ebay.get('all_listings', []))}")
                    st.write(f"Condition listings: {ebay.get('condition_count', 0)}")
                    if ebay.get('raw_data'):
                        st.write(f"Raw eBay data keys: {list(ebay['raw_data'].keys())}")
                        if 'search_stats' in ebay['raw_data']:
                            st.write(f"Search stats: {ebay['raw_data']['search_stats']}")
            else:
                st.write("No eBay data found")
        
        st.write(f"**Advised Price:** ${research['advised_price']:.2f}")

    def _render_database_results(self, results, search_type, user=None):
        if not results:
            st.warning("No records found in database")
            return
        
        filtered_results = results
        if user and user.get('role') == 'consignor' and search_type == "Edit or Delete item":
            user_id = user.get('id')
            filtered_results = [r for r in results if r.get('consignor_id') == user_id]
            
            if not filtered_results:
                st.info("You don't have any records that match your search.")
                st.info("Only your own consignment records are shown in edit/delete mode.")
                return
        
        self._render_editable_database_results(filtered_results, search_type, user)

    def _render_editable_database_results(self, results, search_type, user=None):
        for i, record in enumerate(results):
            expander_title = f"{record.get('artist', '')} - {record.get('title', '')}"
            user_role = user.get('role', 'consignor') if user else 'consignor'
            user_id = user.get('id') if user else None
            
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
            user_id = user.get('id') if user else None
            
            if user_role == 'admin' and record.get('consignor_id'):
                consignor_id = record.get('consignor_id')
                if consignor_id:
                    user_info = self.get_user(consignor_id)
                    if user_info:
                        consignor_name = user_info.get('username', f"ID: {consignor_id}")
                        st.write(f"**👤 Consignor:** {consignor_name} (ID: {consignor_id}")
                    else:
                        st.write(f"**👤 Consignor ID:** {consignor_id}")
            
            st.write(f"**ID:** {record.get('id', '')}")
            st.write(f"**Barcode:** {record.get('barcode', '')}")
            st.write(f"**Catalog:** {record.get('catalog_number', '')}")
            st.write(f"**Genre:** {record.get('genre', '')}")
            
            if record.get('consignment_start_date'):
                st.write(f"**Consigned:** {record.get('consignment_start_date')}")
            
            if record.get('discount_eligible_date'):
                st.write(f"**Discount Eligible:** {record.get('discount_eligible_date')}")
            
            can_edit = False
            if user_role == 'admin':
                can_edit = True
            elif user_role == 'consignor' and record.get('consignor_id') == user_id:
                can_edit = True
            
            artist = st.text_input("Artist", value=record.get('artist', ''), key=f"artist_edit_{index}", disabled=not can_edit)
            title = st.text_input("Title", value=record.get('title', ''), key=f"title_edit_{index}", disabled=not can_edit)
            
            all_genres = self.get_all_genres()
            
            current_genre = record.get('genre', '')
            genre_index = all_genres.index(current_genre) + 1 if current_genre in all_genres else 0
            genre = st.selectbox("Genre", options=[""] + all_genres, index=genre_index, key=f"genre_edit_{index}", disabled=not can_edit)
            
            compilation = st.checkbox("Compilation", value=record.get('compilation', False), key=f"compilation_{index}", disabled=not can_edit)
            
            store_price = record.get('store_price', 0.0)
            st.write(f"**Current Store Price:** ${store_price:.2f}")
            
            if record.get('price_override_requested'):
                st.warning("⚠️ Price override requested")
            
            youtube_url = st.text_input("YouTube URL", value=record.get('youtube_url', ''), key=f"youtube_{index}", disabled=not can_edit)
            
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            with col_btn1:
                if can_edit:
                    if st.button("💾 Save", key=f"save_{index}", width='stretch'):
                        updates = {
                            'artist': artist,
                            'title': title,
                            'genre': genre,
                            'compilation': compilation,
                            'youtube_url': youtube_url
                        }
                        
                        self._save_record_changes(record, updates)
                else:
                    st.button("💾 Save", key=f"save_{index}_disabled", width='stretch', disabled=True)
            
            with col_btn2:
                can_delete = False
                if user_role == 'admin':
                    can_delete = True
                elif user_role == 'consignor' and record.get('consignor_id') == user_id:
                    if record.get('status_id') == 1:
                        can_delete = True
                
                if can_delete:
                    if st.button("🗑️ Delete", key=f"delete_{index}", width='stretch', type="secondary"):
                        if self._delete_record(record.get('id')):
                            st.success("Record deleted successfully!")
                            st.rerun()
                else:
                    st.button("🗑️ Delete", key=f"delete_{index}_disabled", width='stretch', type="secondary", disabled=True)
            
            with col_btn3:
                if record.get('barcode'):
                    if user_role == 'admin':
                        if st.button("🗑️ Clear Barcode", key=f"clear_barcode_{index}", width='stretch', type="secondary"):
                            if self._clear_barcode(record.get('id')):
                                st.success("Barcode cleared!")
                                st.rerun()
                    else:
                        st.button("🗑️ Clear Barcode", key=f"clear_barcode_{index}_disabled", width='stretch', type="secondary", disabled=True)

    def _save_record_changes(self, original_record, updates):
        """Save record changes via API - updates cache"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would update record {original_record['id']} with {updates}")
            st.success("Demo: Record updated successfully!")
            st.rerun()
            return
        
        if 'genre' in updates:
            genre = updates.pop('genre')
            if genre:
                genre_id = None
                if self.genre_cache:
                    genre_data = self.genre_cache.get_genres_data()
                    if genre_data:
                        for genre_item in genre_data:
                            if genre_item.get('genre_name') == genre:
                                genre_id = genre_item.get('id')
                                break
                
                if not genre_id:
                    success, new_genre_id = self.add_genre(genre)
                    if success:
                        genre_id = new_genre_id
                
                if genre_id:
                    updates['genre_id'] = genre_id
        
        success = self.update_record(original_record['id'], updates)
        if success:
            st.success("Record updated successfully!")
            st.rerun()
        else:
            st.error("Failed to update record")

    def _clear_barcode(self, record_id):
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would clear barcode for record {record_id}")
            st.success("Demo: Barcode cleared!")
            return True
            
        updates = {'barcode': None}
        success = self.update_record(record_id, updates)
        return success

    def _delete_record(self, record_id):
        """Delete a record from the database via API - updates cache"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would delete record {record_id}")
            st.success("Demo: Record deleted successfully!")
            return True
            
        try:
            success = self.delete_record(record_id)
            return success
        except Exception as e:
            st.error(f"Error deleting record: {e}")
            return False

    def _perform_database_search(self, search_term, user=None):
        """Perform database search using cache"""
        try:
            user_role = user.get('role', 'consignor') if user else 'consignor'
            user_id = user.get('id') if user else None
            
            # Use cache first
            if hasattr(st.session_state, 'records_cache'):
                records = st.session_state.records_cache
                if isinstance(records, list) and records:
                    search_lower = search_term.lower()
                    filtered_records = []
                    
                    for record in records:
                        # Filter by user if needed
                        if user_role == 'consignor' and user_id and record.get('consignor_id') != user_id:
                            continue
                        
                        artist = str(record.get('artist', '')).lower()
                        title = str(record.get('title', '')).lower()
                        catalog = str(record.get('catalog_number', '')).lower()
                        barcode = str(record.get('barcode', '')).lower()
                        
                        if (search_lower in artist or 
                            search_lower in title or 
                            search_lower in catalog or 
                            search_lower in barcode):
                            filtered_records.append(record)
                    
                    # Convert to expected format
                    formatted_results = []
                    for record in filtered_records:
                        formatted_result = {
                            'type': 'database',
                            'id': record.get('id', ''),
                            'artist': record.get('artist', ''),
                            'title': record.get('title', ''),
                            'image_url': record.get('image_url', ''),
                            'barcode': record.get('barcode', ''),
                            'catalog_number': record.get('catalog_number', ''),
                            'file_at': record.get('file_at', ''),
                            'store_price': record.get('store_price', ''),
                            'ebay_sell_at': record.get('ebay_sell_at', ''),
                            'discogs_suggested_price': record.get('discogs_suggested_price', ''),
                            'ebay_lowest_price': record.get('ebay_lowest_price', ''),
                            'condition': record.get('condition', ''),
                            'genre': record.get('genre_name', record.get('genre', '')),
                            'youtube_url': record.get('youtube_url', ''),
                            'consignor_id': record.get('consignor_id', ''),
                            'consignor_name': record.get('consignor_name', ''),
                            'commission_rate': record.get('commission_rate', ''),
                            'compilation': record.get('compilation', False),
                            'status_id': record.get('status_id', 1)
                        }
                        
                        formatted_results.append(formatted_result)
                    
                    return formatted_results
            
            # Fallback to API
            if user_role == 'consignor' and user_id:
                response = requests.get(
                    f"{self.base_url}/records/user/{user_id}?search={search_term}",
                    timeout=10
                )
            else:
                response = requests.get(f"{self.base_url}/search?q={search_term}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    records = data.get('records', [])
                    
                    if user_role == 'consignor' and user_id:
                        filtered_records = []
                        search_lower = search_term.lower()
                        for record in records:
                            artist = str(record.get('artist', '')).lower()
                            title = str(record.get('title', '')).lower()
                            catalog = str(record.get('catalog_number', '')).lower()
                            barcode = str(record.get('barcode', '')).lower()
                            
                            if (search_lower in artist or 
                                search_lower in title or 
                                search_lower in catalog or 
                                search_lower in barcode):
                                filtered_records.append(record)
                        records = filtered_records
                    
                    df = pd.DataFrame(records) if records else pd.DataFrame()
                else:
                    return []
            else:
                return []
            
            formatted_results = []
            for _, record in df.iterrows():
                formatted_result = {
                    'type': 'database',
                    'id': record.get('id', ''),
                    'artist': record.get('artist', ''),
                    'title': record.get('title', ''),
                    'image_url': record.get('image_url', ''),
                    'barcode': record.get('barcode', ''),
                    'catalog_number': record.get('catalog_number', ''),
                    'file_at': record.get('file_at', ''),
                    'store_price': record.get('store_price', ''),
                    'ebay_sell_at': record.get('ebay_sell_at', ''),
                    'discogs_suggested_price': record.get('discogs_suggested_price', ''),
                    'ebay_lowest_price': record.get('ebay_lowest_price', ''),
                    'condition': record.get('condition', ''),
                    'genre': record.get('genre_name', record.get('genre', '')),
                    'youtube_url': record.get('youtube_url', ''),
                    'consignor_id': record.get('consignor_id', ''),
                    'consignor_name': record.get('consignor_name', ''),
                    'commission_rate': record.get('commission_rate', ''),
                    'compilation': record.get('compilation', False),
                    'status_id': record.get('status_id', 1)
                }
                
                formatted_results.append(formatted_result)
            
            return formatted_results
            
        except Exception as e:
            st.error(f"Error searching database: {str(e)}")
            return []

    def _get_all_genres(self):
        if self.genre_cache:
            return self.genre_cache.get_genres_list()
        return []

    def _get_suggested_genre(self, record_data):
        discogs_genre = record_data.get('genre', '')
        if not discogs_genre:
            return None
        
        mapping_result = self.get_discogs_genre_mapping(discogs_genre)
        if mapping_result and mapping_result.get('mapping'):
            return mapping_result['mapping'].get('local_genre_name')
        
        return None

    def _get_store_fill_info(self):
        try:
            store_capacity = self._get_config_value('STORE_CAPACITY')
        except ValueError as e:
            raise ValueError(f"Cannot calculate store fill: {e}")
        
        # Get records count from cache (efficient)
        total_inventory = self.get_records_count()
        
        fill_fraction = total_inventory / store_capacity if store_capacity > 0 else 0
        fill_percentage = fill_fraction * 100
        
        return {
            'total_inventory': total_inventory,
            'store_capacity': store_capacity,
            'fill_fraction': fill_fraction,
            'fill_percentage': fill_percentage
        }