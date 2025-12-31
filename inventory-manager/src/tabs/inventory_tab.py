import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from handlers.search_handler import SearchHandler
from handlers.commission_calculator import CommissionCalculator
from handlers.pricing_validator import PricingValidator
from handlers.price_advise_handler import PriceAdviseHandler
import requests
import os

class InventoryTab:
    def __init__(self, discogs_handler, ebay_handler=None, youtube_handler=None, config_cache=None, genre_cache=None, price_advise_handler=None, base_url="https://arjanshaw.pythonanywhere.com"):
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
        self.youtube_handler = youtube_handler
        self.base_url = base_url
        self.config_cache = config_cache
        self.genre_cache = genre_cache
        self.price_advise_handler = price_advise_handler 
        
        self.search_handler = SearchHandler(discogs_handler, self.base_url)
        self.commission_calculator = CommissionCalculator(self)
        self.pricing_validator = PricingValidator(self, discogs_handler, ebay_handler)
        self.price_advise_handler = PriceAdviseHandler(discogs_handler, ebay_handler)

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
            # Use cache first via api_client
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
        
        # Get store capacity from config
        store_capacity = float(self.get_config_value('STORE_CAPACITY'))
        
        # Calculate store fill info
        store_fill_info = self._calculate_store_fill_info(store_capacity)
        current_commission_rate = st.session_state.commission_calculator.get_current_commission_rate()
        
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
                
        self._render_last_added_record_simple()
        
        store_fill_fraction = store_fill_info['fill_fraction']
        
        self._render_unified_operations(store_fill_fraction)

    def _calculate_store_fill_info(self, store_capacity):
        """Calculate store fill information"""
        total_inventory = self.get_records_count()
        
        fill_fraction = total_inventory / store_capacity if store_capacity > 0 else 0
        fill_percentage = fill_fraction * 100
        
        return {
            'total_inventory': total_inventory,
            'store_capacity': store_capacity,
            'fill_fraction': fill_fraction,
            'fill_percentage': fill_percentage
        }

    def _render_last_added_record_simple(self):
        """Display the last record added to the database - FIXED VERSION"""
        user = st.session_state.get('user', {})
        user_id = user.get('id')
        user_role = user.get('role')
        is_demo = user.get('username') == 'demo_user'
        is_admin = user_role == 'admin'
        
        # Clear any cached last added if we have a new record
        if st.session_state.get('record_added'):
            # Force refresh on next load
            st.session_state['last_added_refresh'] = True
        
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
            try:
                if is_admin:
                    # For admin, get most recent record from ALL records
                    response = requests.get(f"{self.base_url}/records?limit=1&order_by=id&order=desc")
                    if response.status_code == 200:
                        data = response.json()
                        records = data.get('records', [])
                        if records:
                            last_record = records[0]
                            artist = last_record.get('artist', 'Unknown Artist')
                            title = last_record.get('title', 'Unknown Title')
                            store_price = last_record.get('store_price', 0.0)
                            
                            display_text = f"**📝 Last Added:** {artist} - {title} (${store_price:.2f})"
                            st.markdown(display_text)
                        else:
                            st.markdown("**📝 Last Added:** No records yet")
                    else:
                        st.markdown("**📝 Last Added:** Error loading")
                else:
                    # For consignor, get their most recent record
                    if user_id:
                        response = requests.get(f"{self.base_url}/records/user/{user_id}?limit=1&order_by=id&order=desc")
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('status') == 'success':
                                records = data.get('records', [])
                                if records:
                                    last_record = records[0]
                                    artist = last_record.get('artist', 'Unknown Artist')
                                    title = last_record.get('title', 'Unknown Title')
                                    store_price = last_record.get('store_price', 0.0)
                                    
                                    display_text = f"**📝 Last Added:** {artist} - {title} (${store_price:.2f})"
                                    st.markdown(display_text)
                                else:
                                    st.markdown("**📝 Last Added:** No records yet")
                            else:
                                st.markdown("**📝 Last Added:** No records yet")
                        else:
                            st.markdown("**📝 Last Added:** Error loading")
                    else:
                        st.markdown("**📝 Last Added:** No records yet")
            except Exception as e:
                print(f"Error loading last added record: {e}")
                st.markdown("**📝 Last Added:** Error loading")

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
        
        # Check if we need to clear search state after adding a record
        if st.session_state.get('record_added'):
            keys_to_clear = [key for key in st.session_state.keys() if key.startswith('discogs_result_')]
            for key in keys_to_clear:
                if key in st.session_state:  # FIX: Check if key exists before deleting
                    del st.session_state[key]
            
            st.session_state.selected_record = None
            st.session_state.record_added = None
            st.session_state.search_results = {}
            st.session_state.current_search = ""
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
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
                    if key in st.session_state:  # FIX: Check if key exists before deleting
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
                'advised_store_price': None,
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
            country = stored_data['record_data'].get('country', '')
            discogs_genre = stored_data['record_data'].get('genre', '')
            
            info_lines = []
            if catalog:
                info_lines.append(f"**Catalog:** {catalog}")
            if year:
                info_lines.append(f"**Year:** {year}")
            if format_info:
                info_lines.append(f"**Format:** {format_info}")
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
            
            # Use centralized condition list based on user role
            from conditions import DiscogsConditions
            available_conditions = DiscogsConditions.get_available_conditions(user_role)
            
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
                        # Use PriceAdviseHandler to get comprehensive price advice
                        price_advice = self.price_advise_handler.get_price_advice(
                            artist,
                            title,
                            selected_condition,
                            stored_data['record_data']
                        )
                        
                        if price_advice['success']:
                            # FIXED: Set the price field to the advised store price
                            stored_data['advised_store_price'] = price_advice['advised_store_price']
                            stored_data['user_price'] = price_advice['advised_store_price']  # This ensures price field shows correct value
                            
                            stored_data['price_research'] = {
                                'discogs_price': price_advice['discogs_price'],
                                'ebay_prices': price_advice['ebay_prices'],
                                'advised_store_price': price_advice['advised_store_price'],
                                'selected_condition': selected_condition,
                                'calculation_lines': price_advice['calculation_lines'],
                                'ebay_listings': price_advice['ebay_listings']
                            }
                            stored_data['last_researched_condition'] = selected_condition
                            
                            st.session_state[f"{record_key}_data"] = stored_data
                            
                            st.rerun()
        
        with col4:
            if (stored_data['selected_condition'] and 
                stored_data['selected_condition'] != "Select condition..." and
                stored_data.get('price_research')):
                
                advised_store_price = stored_data.get('advised_store_price')
                
                # Set the user_price to advised_store_price if not already set
                if stored_data.get('user_price') is None and advised_store_price:
                    stored_data['user_price'] = advised_store_price
                    st.session_state[f"{record_key}_data"] = stored_data
                
                max_ratio_value = self.get_config_value('MAX_PRICE_TO_ADV_RATIO', '1.3')
                max_ratio = float(max_ratio_value) if max_ratio_value else 1.3
                
                max_allowed = advised_store_price * max_ratio if advised_store_price and advised_store_price > 0 else 0
                
                price_input_key = f"price_input_{record_key}"
                user_price = st.number_input(
                    "Price ($)",
                    min_value=0.0,
                    max_value=float(max_allowed * 1.5),
                    value=float(advised_store_price),
                    step=0.01,
                    format="%.2f",
                    key=price_input_key,
                    help=f"Advised: ${advised_store_price:.2f} | Max: ${max_allowed:.2f}" if advised_store_price and max_allowed > 0 else "Enter price"
                )
                
                # FIXED: Always update user_price when user changes it
                if user_price != stored_data.get('user_price'):
                    stored_data['user_price'] = user_price
                    st.session_state[f"{record_key}_data"] = stored_data
                    
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
                    record_to_add['user_price'] = stored_data['user_price']  # Use the user_price, NOT advised price
                    record_to_add['advised_store_price'] = stored_data.get('advised_store_price')
                    record_to_add['price_research'] = stored_data.get('price_research')
                    record_to_add['genre'] = stored_data['selected_genre']
                    record_to_add['discogs_genre'] = record_to_add.get('genre', '')
                    
                    user = st.session_state.get('user', {})
                    consignor_id = user.get('id')
                    
                    success, record_id = self._handle_add_record_direct(
                        record_to_add, 
                        stored_data['selected_genre'], 
                        stored_data['user_price'],  # Use user_price here
                        consignor_id
                    )
                    
                    if success:
                        if f"{record_key}_data" in st.session_state:  # FIX: Check if key exists before deleting
                            del st.session_state[f"{record_key}_data"]
                        st.session_state.record_added = True
                        
                        if user.get('username') == 'demo_user':
                            st.session_state.demo_last_added = {
                                'artist': record_to_add['artist'],
                                'title': record_to_add['title'],
                                'store_price': stored_data['user_price']  # Use user_price
                            }
                        
                        st.success(f"✅ Record added successfully! ID: {record_id}")
                        st.rerun()
                    else:
                        st.error("Failed to add record to database")
            else:
                st.button("➕ Add", key=f"add_disabled_{record_key}", disabled=True, width='stretch')
        
        # Show price details in an expanded section below the main row
        if (stored_data['selected_condition'] and 
            stored_data['selected_condition'] != "Select condition..." and
            stored_data.get('price_research')):
            
            with st.expander("📊 Price Details", expanded=False):
                self._render_price_calculation_details(stored_data['price_research'])
                
                # Show eBay listings summary
                ebay_prices = stored_data['price_research'].get('ebay_prices')
                if ebay_prices and stored_data['price_research'].get('ebay_listings'):
                    with st.expander("🛒 eBay Listings Summary", expanded=False):
                        self._render_ebay_listings_summary(stored_data['price_research'])
        
        st.divider()
        
        st.session_state[f"{record_key}_data"] = stored_data
    
    def _render_price_calculation_details(self, price_research):
        """Render price calculation details from stored calculation_lines"""
        if not price_research:
            st.info("No price research data available")
            return
        
        calculation_lines = price_research.get('calculation_lines', [])
        advised_store_price = price_research.get('advised_store_price', 0.0)
        
        if not calculation_lines:
            st.info("No calculation details available")
            return
        
        st.write("**🧮 Price Calculation:**")
        for line in calculation_lines:
            st.write(line)
        
        st.write(f"**Final advised price: ${advised_store_price:.2f}**")
    
    def _render_ebay_listings_summary(self, price_research):
        """Render summarized eBay listings data"""
        ebay_listings = price_research.get('ebay_listings', [])
        ebay_prices = price_research.get('ebay_prices', {})
        
        if not ebay_listings:
            return
        
        search_query = ebay_prices.get('search_query', '')
        
        st.write(f"**Search Query:** `{search_query}`")
        
        # Show summary counts
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Listings", len(ebay_listings))
        with col2:
            if ebay_prices.get('condition_count'):
                st.metric("Condition Listings", ebay_prices['condition_count'])
        with col3:
            if ebay_prices.get('condition_median'):
                st.metric("Condition Median", f"${ebay_prices['condition_median']:.2f}")
        
        # Show top 5 listings
        st.write("**Top 5 Listings (by total cost):**")
        
        # Sort listings by total cost for ranking
        sorted_listings = sorted(ebay_listings, key=lambda x: x.get('total_cost_for_ranking', 9999))
        
        for i, listing in enumerate(sorted_listings[:5]):
            base_price = listing.get('base_price', 0)
            shipping_type = listing.get('shipping_type', 'UNKNOWN')
            shipping_cost = listing.get('shipping_cost')
            item_url = listing.get('item_url', '#')
            item_data = listing.get('item_data', {})
            title = item_data.get('title', 'No title')[:60] + '...' if len(item_data.get('title', '')) > 60 else item_data.get('title', 'No title')
            
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                st.write(f"**{i+1}.** [{title}]({item_url})")
            
            with col2:
                st.write(f"${base_price:.2f}")
            
            with col3:
                if shipping_type == 'FREE':
                    st.write("Free")
                elif shipping_type == 'FIXED' and shipping_cost is not None:
                    st.write(f"${shipping_cost:.2f}")
                elif shipping_type == 'CALC':
                    st.write("Calculated")
                else:
                    st.write("Unknown")
            
            with col4:
                total_cost = listing.get('total_cost_for_ranking', base_price)
                st.write(f"**${total_cost:.2f}**")
            
            st.divider()
    
    def _handle_add_record_direct(self, record_data, genre, user_price=None, consignor_id=None):
        """Handle adding a record directly to the database - FIXED VERSION"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            # Store demo record for display
            st.session_state.demo_last_added = {
                'artist': record_data.get('artist', 'Demo Artist'),
                'title': record_data.get('title', 'Demo Album'),
                'store_price': user_price or 19.99
            }
            
            st.success(f"✅ Demo: Record '{record_data.get('artist', '')} - {record_data.get('title', '')}' added")
            
            # Clear search state for demo
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
            st.session_state.last_search_term = ""
            if 'search_results' in st.session_state:
                st.session_state.search_results = {}
            
            # Clear any discogs result data
            keys_to_clear = [key for key in st.session_state.keys() if key.startswith('discogs_result_')]
            for key in keys_to_clear:
                if key in st.session_state:  # FIX: Check if key exists before deleting
                    del st.session_state[key]
                    
            # Mark record as added to trigger refresh
            st.session_state.record_added = True
            
            return True, 999
            
        if consignor_id:
            record_data['consignor_id'] = consignor_id
        
        # FIXED: Always use user_price if provided
        if user_price is not None:
            # Store the user price as store_price
            record_data['selected_price'] = user_price
            record_data['original_consignor_price'] = user_price
            record_data['store_price'] = user_price  # This is the key fix
        
        success, record_id = self._add_inventory_record(
            record_data, 
            genre, 
            st.session_state.current_search,
            consignor_id
        )
        
        if success:
            # CLEAR SEARCH STATE AFTER SUCCESSFUL ADD
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
            st.session_state.last_search_term = ""
            if 'search_results' in st.session_state:
                st.session_state.search_results = {}
            # Clear any discogs result data
            keys_to_clear = [key for key in st.session_state.keys() if key.startswith('discogs_result_')]
            for key in keys_to_clear:
                if key in st.session_state:  # FIX: Check if key exists before deleting
                    del st.session_state[key]
            
            # Mark record as added to trigger refresh
            st.session_state.record_added = True
        
        return success, record_id

    def _add_inventory_record(self, record_data, genre, search_term, consignor_id=None):
        """Add inventory record to database via API - FIXED VERSION"""
        if genre is None:
            raise Exception("genre parameter is required but was None")
        
        duplicates_found = st.session_state.pricing_validator.check_for_duplicates(record_data)

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
        
        # Get format from session state or default
        format_selected = st.session_state.get('format_select', 'Vinyl')
        
        # Get Discogs pricing information
        pricing_data = None
        
        if self.discogs_handler:
            with st.spinner("Fetching Discogs price suggestions..."):
                pricing_data = self.discogs_handler.get_release_statistics_pricing(str(release_id))
        else:
            st.error("Discogs handler not available")
            return False, None
        
        # Extract result information
        artist = record_data.get('artist', '')
        title = record_data.get('title', '')
        image_url = record_data.get('image_url', '')
        catalog_number = record_data.get('catalog_number', '')
        youtube_url = record_data.get('youtube_url', '')
        
        # Get selected condition and price from record_data
        selected_condition = record_data.get('selected_condition')
        user_price = record_data.get('user_price')  # This is the user-entered price
        
        # Get compilation status from record_data
        compilation = record_data.get('compilation', False)
        
        # Get consignor_id
        if consignor_id is None:
            consignor_id = record_data.get('consignor_id')
        
        # Get commission info
        commission_rate = None
        store_return_days = None
        
        if consignor_id:
            user_data = self.get_user(consignor_id)
            if user_data and user_data.get('agreement_details'):
                commission_rate = user_data['agreement_details'].get('commission_rate')
                store_return_days = user_data['agreement_details'].get('store_return_days')
        
        if commission_rate is None:
            commission_rate = float(self.get_config_value('DEFAULT_COMMISSION_RATE'))
        
        if store_return_days is None:
            store_return_days = int(self.get_config_value('DEFAULT_STORE_RETURN_DAYS'))
        
        # Get discogs_genre for mapping
        discogs_genre = record_data.get('discogs_genre', '')
        
        # Get genre_id
        genre_id = None
        if genre:
            genres = self.get_all_genres()
            if genre in genres:
                pass
        
        # Store pricing data
        if pricing_data:
            record_data['price_suggestions'] = pricing_data.get('price_suggestions', {})
        
        # FIXED: Use user_price as store_price
        store_price = user_price if user_price else 0.0
        
        # Get eBay sell price from record_data if available
        ebay_sell_at = record_data.get('ebay_sell_at', 0.0)
        
        # Set consignment dates if consigning
        consignment_start_date = None
        discount_eligible_date = None
        original_consignor_price = None
        
        if consignor_id:
            consignment_start_date = datetime.now().date()
            full_price_days = int(self.get_config_value('CONSIGNMENT_FULL_PRICE_DAYS'))
            discount_eligible_date = consignment_start_date + timedelta(days=full_price_days)
            original_consignor_price = store_price
        
        # Save to database via API
        try:
            # Prepare data for API - USE USER_PRICE AS STORE_PRICE
            record_data_to_save = {
                'artist': artist,
                'title': title,
                'barcode': '',
                'genre_id': genre_id,
                'image_url': image_url,
                'catalog_number': catalog_number,
                'format': format_selected,
                'condition': selected_condition,
                'store_price': float(store_price),  # This uses user_price
                'ebay_sell_at': float(ebay_sell_at) if ebay_sell_at else 0.0,
                'youtube_url': youtube_url,
                'compilation': bool(compilation),
                'advised_store_price': float(record_data.get('advised_store_price', store_price))  # Store advised for reference
            }
            
            # Add consignor fields only if consignor_id exists
            if consignor_id:
                record_data_to_save['consignor_id'] = int(consignor_id)
                record_data_to_save['commission_rate'] = float(commission_rate)
                record_data_to_save['store_return_days'] = int(store_return_days)
                record_data_to_save['store_credit_option'] = st.session_state.get('store_credit_option', False)
                record_data_to_save['consignment_start_date'] = consignment_start_date.isoformat() if consignment_start_date else None
                record_data_to_save['discount_eligible_date'] = discount_eligible_date.isoformat() if discount_eligible_date else None
                record_data_to_save['original_consignor_price'] = float(original_consignor_price) if original_consignor_price else None
            
            # Call API to create record
            response = requests.post(
                f"{self.base_url}/records",
                json=record_data_to_save,
                timeout=10
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == 'success':
                    record_id = response_data.get('record_id')
                    
                    # Save Discogs genre mapping if available
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

    def _perform_database_search(self, search_term, user):
        """Perform database search"""
        user_id = user.get('id') if user else None
        user_role = user.get('role', 'consignor') if user else 'consignor'
        
        if user_role == 'admin':
            results = self.search_records(search_term)
        else:
            if user_id:
                # For consignors, only search their own records
                user_records = self.get_records_by_user(user_id)
                search_lower = search_term.lower()
                results = []
                
                for record in user_records:
                    artist = str(record.get('artist', '')).lower()
                    title = str(record.get('title', '')).lower()
                    catalog = str(record.get('catalog_number', '')).lower()
                    barcode = str(record.get('barcode', '')).lower()
                    
                    if (search_lower in artist or 
                        search_lower in title or 
                        search_lower in catalog or 
                        search_lower in barcode):
                        results.append(record)
            else:
                results = []
        
        # Format results for display
        formatted_results = []
        for record in results:
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
                'compilation': record.get('compilation', False)
            }
            
            formatted_results.append(formatted_result)
        
        return formatted_results

    def _render_database_results(self, results, search_type, user):
        """Render database search results"""
        if not results:
            st.warning("No matching records found in database")
            return
        
        st.write(f"**Found {len(results)} matching records**")
        
        for i, record in enumerate(results):
            self._render_database_result_item(record, i, user)

    def _render_database_result_item(self, record, index, user):
        """Render individual database result item"""
        col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 1])
        
        with col1:
            image_url = record.get('image_url', '')
            if image_url:
                st.image(image_url, width=80)
            else:
                st.write("No image")
        
        with col2:
            artist = record.get('artist', '')
            title = record.get('title', '')
            
            st.write(f"**{artist} - {title}**")
            
            catalog = record.get('catalog_number', '')
            genre = record.get('genre', '')
            barcode = record.get('barcode', '')
            consignor_name = record.get('consignor_name', '')
            
            info_lines = []
            if catalog:
                info_lines.append(f"**Catalog:** {catalog}")
            if genre:
                info_lines.append(f"**Genre:** {genre}")
            if barcode:
                info_lines.append(f"**Barcode:** {barcode}")
            if consignor_name:
                info_lines.append(f"**Consignor:** {consignor_name}")
            
            if info_lines:
                for line in info_lines:
                    st.write(line)
        
        with col3:
            store_price = record.get('store_price', 0.0)
            ebay_sell_at = record.get('ebay_sell_at', 0.0)
            
            st.write(f"**Store Price:** ${store_price:.2f}")
            st.write(f"**eBay Price:** ${ebay_sell_at:.2f}")
            
            condition = record.get('condition', '')
            if condition:
                st.write(f"**Condition:** {condition}")
        
        with col4:
            # Show edit button for admins or record owners
            user_role = user.get('role', 'consignor')
            user_id = user.get('id')
            record_consignor_id = record.get('consignor_id')
            
            can_edit = (user_role == 'admin' or 
                       (user_role == 'consignor' and user_id and record_consignor_id == user_id))
            
            if can_edit:
                if st.button("✏️ Edit", key=f"edit_{record['id']}", width='stretch'):
                    st.session_state.selected_record = record
                    st.session_state.editing_record = True
                    st.rerun()
            else:
                st.button("✏️ Edit", key=f"edit_disabled_{record['id']}", disabled=True, width='stretch')
            
            # Show delete button for admins only
            if user_role == 'admin':
                if st.button("🗑️ Delete", key=f"delete_{record['id']}", type="secondary", width='stretch'):
                    if self.delete_record(record['id']):
                        st.success(f"✅ Record deleted successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to delete record")
        
        with col5:
            # Show status or other info
            status = "Active"
            if record.get('date_sold'):
                status = "Sold"
            elif record.get('date_removed'):
                status = "Removed"
            
            st.write(f"**Status:** {status}")
        
        st.divider()

    def _get_suggested_genre(self, record_data):
        """Get suggested genre from Discogs genre using cache mapping"""
        discogs_genre = record_data.get('genre', '')
        if not discogs_genre:
            return None
        
        # Get mapping from genre cache
        mapping_data = self.get_discogs_genre_mapping(discogs_genre)
        
        if mapping_data and mapping_data.get('status') == 'success':
            mapping = mapping_data.get('mapping')
            if mapping:
                # Get the local genre name from mapping
                return mapping.get('local_genre_name')
        
        return None