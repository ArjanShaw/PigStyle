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
import hashlib
from conditions import DiscogsConditions  # FIXED: Complete import statement

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

    def _perform_database_search(self, search_term, user):
        """Perform database search - calls the SearchHandler method"""
        return self.search_handler.perform_database_search(search_term, user)

    def _get_suggested_genre(self, record_data):
        """Get suggested genre from Discogs genre using cache mapping - FIXED to handle slashes"""
        discogs_genre = record_data.get('genre', '')
        if not discogs_genre:
            return None
        
        # FIX: Clean the discogs genre for API calls
        clean_discogs_genre = discogs_genre
        if '/' in discogs_genre:
            # Try multiple cleaning strategies
            clean_discogs_genre = discogs_genre.replace('/', ' ')
        
        mapping_data = self.get_discogs_genre_mapping(clean_discogs_genre)
        
        # If that fails, try the original with slash
        if (not mapping_data or mapping_data.get('status') != 'success') and '/' in discogs_genre:
            mapping_data = self.get_discogs_genre_mapping(discogs_genre)
        
        if mapping_data and mapping_data.get('status') == 'success':
            mapping = mapping_data.get('mapping')
            if mapping:
                return mapping.get('local_genre_name')
        
        # FIX: Fallback genre mapping for common slash genres
        slash_genre_mapping = {
            'Funk/Soul': 'Funk',
            'Rock/Pop': 'Rock',
            'Hip-Hop/Rap': 'Hip Hop',
            'Jazz/Blues': 'Jazz',
            'Electronic/Dance': 'Electronic',
            'Folk/Country': 'Folk',
            'Latin/World': 'World',
            'Classical/Opera': 'Classical'
        }
        
        if discogs_genre in slash_genre_mapping:
            return slash_genre_mapping[discogs_genre]
        
        # Try partial matching
        for slash_genre, mapped_genre in slash_genre_mapping.items():
            if slash_genre.startswith(discogs_genre.split('/')[0]):
                return mapped_genre
        
        return None

    def _render_ebay_listings_summary(self, price_research):
        """Render summarized eBay listings data with all evaluated listings"""
        ebay_prices = price_research.get('ebay_prices', {})
        
        if not ebay_prices:
            return
        
        search_query = ebay_prices.get('search_query', '')
        condition = ebay_prices.get('condition', '')
        generic_median = ebay_prices.get('generic_median', 0)
        condition_median = ebay_prices.get('condition_median', 0)
        
        st.write(f"**Search Query:** `{search_query}`")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Listings", ebay_prices.get('generic_count', 0))
        with col2:
            st.metric("Condition Listings", ebay_prices.get('condition_count', 0))
        with col3:
            st.metric("Condition Median", f"${condition_median:.2f}")
        
        all_listings = ebay_prices.get('all_listings', [])
        condition_listings = ebay_prices.get('condition_listings', [])
        
        if all_listings:
            with st.expander(f"📊 All eBay Listings ({len(all_listings)} listings) - Generic Median: ${generic_median:.2f}", expanded=False):
                self._render_listings_table(all_listings, "All Listings", generic_median)
        
        if condition_listings:
            with st.expander(f"🎯 Condition-Specific Listings: {condition} ({len(condition_listings)} listings) - Median: ${condition_median:.2f}", expanded=False):
                self._render_listings_table(condition_listings, f"{condition} Listings", condition_median)

    def _render_listings_table(self, listings, title, median_price):
        """Render listings in a table with median calculation info"""
        if not listings:
            st.info("No listings available")
            return
        
        sorted_listings = sorted(listings, key=lambda x: x.get('base_price', 0))
        
        st.write(f"**Median Calculation:** ${median_price:.2f}")
        st.write(f"**Number of Listings:** {len(listings)}")
        
        table_data = []
        for i, listing in enumerate(sorted_listings, 1):
            base_price = listing.get('base_price', 0)
            shipping_type = listing.get('shipping_type', 'UNKNOWN')
            shipping_cost = listing.get('shipping_cost', 0)
            title_text = listing.get('title', 'No title')[:80]
            condition = listing.get('condition', 'Unknown')
            url = listing.get('url', '#')
            
            used_in_calc = base_price > 0
            
            table_data.append({
                '#': i,
                'Price': f"${base_price:.2f}",
                'Shipping': f"${shipping_cost:.2f}" if shipping_type != 'CALC' else 'Calculated',
                'Total': f"${base_price + shipping_cost:.2f}",
                'Condition': condition,
                'Title': title_text,
                'Used in Median': '✓' if used_in_calc else '✗',
                'URL': url
            })
        
        df = pd.DataFrame(table_data)
        
        st.dataframe(
            df,
            column_config={
                '#': st.column_config.NumberColumn('#', width='small'),
                'Price': st.column_config.TextColumn('Price', width='medium'),
                'Shipping': st.column_config.TextColumn('Shipping', width='medium'),
                'Total': st.column_config.TextColumn('Total', width='medium'),
                'Condition': st.column_config.TextColumn('Condition', width='medium'),
                'Title': st.column_config.TextColumn('Title', width='large'),
                'Used in Median': st.column_config.TextColumn('In Calc', width='small'),
                'URL': st.column_config.LinkColumn('Link', width='small')
            },
            hide_index=True,
            width='stretch'
        )
        
        prices = [listing.get('base_price', 0) for listing in sorted_listings if listing.get('base_price', 0) > 0]
        if prices:
            st.write(f"**Price Range:** ${min(prices):.2f} - ${max(prices):.2f}")
            st.write(f"**Average Price:** ${sum(prices)/len(prices):.2f}")

    def _handle_add_record_direct(self, record_data, genre, user_price=None, consignor_id=None):
        """Handle adding a record directly to the database - FIXED VERSION"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        # FIX: Validate genre is provided
        if genre is None or genre == "Select genre...":
            st.error("❌ **Genre is required! Please select a genre.**")
            return False, None
        
        if is_demo:
            st.session_state.demo_last_added = {
                'artist': record_data.get('artist', 'Demo Artist'),
                'title': record_data.get('title', 'Demo Album'),
                'store_price': user_price or 19.99
            }
            
            success_container = st.empty()
            with success_container:
                st.success(f"✅ Demo: Record '{record_data.get('artist', '')} - {record_data.get('title', '')}' added")
                st.markdown(f"**📝 Last Added:** {record_data.get('artist', '')} - {record_data.get('title', '')} (${user_price or 19.99:.2f})")
            
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
            st.session_state.last_search_term = ""
            if 'search_results' in st.session_state:
                st.session_state.search_results = {}
            
            keys_to_clear = [key for key in st.session_state.keys() if key.startswith('discogs_result_')]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
                    
            st.session_state.record_added = True
            st.session_state.last_added_updated = True
            
            return True, 999
            
        if consignor_id:
            record_data['consignor_id'] = consignor_id
        
        if user_price is not None:
            record_data['selected_price'] = user_price
            record_data['original_consignor_price'] = user_price
            record_data['store_price'] = user_price
        
        success, record_id = self._add_inventory_record(
            record_data, 
            genre, 
            st.session_state.current_search,
            consignor_id
        )
        
        if success:
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
            st.session_state.last_search_term = ""
            if 'search_results' in st.session_state:
                st.session_state.search_results = {}
            
            keys_to_clear = [key for key in st.session_state.keys() if key.startswith('discogs_result_')]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            st.session_state.record_added = True
            st.session_state.last_added_updated = True
            
            cache_key = f"last_added_cache_{user.get('id') if user.get('id') else 'all'}"
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            
            success_container = st.empty()
            with success_container:
                st.success(f"✅ Record added successfully! ID: {record_id}")
                last_added_text = self._fetch_last_added_record(
                    user.get('role', 'consignor'),
                    user.get('id'),
                    is_demo
                )
                st.markdown(last_added_text)
        
        return success, record_id

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
            if hasattr(st.session_state, 'records_cache'):
                records = st.session_state.records_cache
                return pd.DataFrame(records) if isinstance(records, list) and records else pd.DataFrame()
            
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
                    sorted_records = sorted(records, key=lambda x: x.get('id', 0), reverse=True)
                    return pd.DataFrame(sorted_records[:limit]) if sorted_records else pd.DataFrame()
            
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
                if 'records_updated' not in st.session_state:
                    st.session_state.records_updated = 0
                st.session_state.records_updated += 1
                return True
            return False
        except Exception as e:
            st.error(f"API Error updating record: {e}")
            return False
        
    def search_records(self, search_term):
        """Search records via RecordsCache - FIXED to ensure dict format"""
        try:
            start_time = time.time()
            
            search_term = search_term.strip()
            if not search_term:
                return []
            
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
            
            response = requests.get(f"{self.base_url}/search?q={search_term}", timeout=10)
            
            duration = time.time() - start_time
            
            print(f"API Search: {search_term[:30]}... took {duration:.2f}s")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and data.get('status') == 'success':
                    records = data.get('records', [])
                    if records:
                        return [dict(r) if not isinstance(r, dict) else r for r in records]
                
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
            genres_data = self.genre_cache.load_all_genres()
            
            # Handle the return structure
            if isinstance(genres_data, dict):
                # Try to get genres_list
                genre_list = genres_data.get('genres_list', [])
                
                # If empty, try to extract from genres_data
                if not genre_list and 'genres_data' in genres_data:
                    genres_raw = genres_data['genres_data']
                    if isinstance(genres_raw, list):
                        # Extract genre names from dicts
                        genre_list = []
                        for item in genres_raw:
                            if isinstance(item, dict):
                                genre_list.append(item.get('genre_name', ''))
                            else:
                                genre_list.append(str(item))
                
                return genre_list if isinstance(genre_list, list) else []
        
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
        if st.session_state.get('needs_refresh'):
            st.session_state.needs_refresh = False
            st.session_state.search_triggered = False
            st.session_state.search_query = ""
            st.rerun()
        
        records_count = self.get_records_count()
        store_capacity = float(self.get_config_value('STORE_CAPACITY'))
        
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
        """Display the last record added to the database - UPDATED VERSION"""
        user = st.session_state.get('user', {})
        user_id = user.get('id')
        user_role = user.get('role')
        is_demo = user.get('username') == 'demo_user'
        
        cache_key = f"last_added_cache_{user_id if user_id else 'all'}"
        
        if st.session_state.get('last_added_updated'):
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            st.session_state.last_added_updated = False
        
        if cache_key not in st.session_state:
            last_record_text = self._fetch_last_added_record(user_role, user_id, is_demo)
            st.session_state[cache_key] = last_record_text
        
        last_record_text = st.session_state[cache_key]
        st.markdown(last_record_text)
        
        if is_demo and hasattr(st.session_state, 'demo_credit_balance'):
            credit_balance = st.session_state.demo_credit_balance
            st.caption(f"💡 Demo Credit Balance: ${credit_balance:.2f} (matches sold records)")

    def _fetch_last_added_record(self, user_role, user_id, is_demo):
        """Fetch the last added record text from API"""
        try:
            if is_demo:
                if 'demo_last_added' in st.session_state:
                    last_record = st.session_state.demo_last_added
                    artist = last_record.get('artist', 'Demo Artist')
                    title = last_record.get('title', 'Demo Album')
                    store_price = last_record.get('store_price', 19.99)
                    return f"**📝 Last Added:** {artist} - {title} (${store_price:.2f})"
                return "**📝 Last Added:** No records yet"
            
            base_url = "https://arjanshaw.pythonanywhere.com"
            
            if user_role == 'admin':
                response = requests.get(f"{base_url}/records?limit=1&order_by=id&order=desc")
            elif user_id:
                response = requests.get(f"{base_url}/records/user/{user_id}?limit=1&order_by=id&order=desc")
            else:
                return "**📝 Last Added:** Error loading"
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and data.get('status') == 'success':
                    records = data.get('records', [])
                    if records:
                        last_record = records[0]
                        artist = last_record.get('artist', 'Unknown Artist')
                        title = last_record.get('title', 'Unknown Title')
                        store_price = last_record.get('store_price', 0.0)
                        return f"**📝 Last Added:** {artist} - {title} (${store_price:.2f})"
                return "**📝 Last Added:** No records yet"
            return "**📝 Last Added:** Error loading"
            
        except Exception as e:
            print(f"Error loading last added record: {e}")
            return "**📝 Last Added:** Error loading"

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
                if key in st.session_state:
                    del st.session_state[key]
            
            st.session_state.selected_record = None
            st.session_state.record_added = None
            st.session_state.search_results = {}
            st.session_state.current_search = ""
            st.session_state.search_query = ""
            st.session_state.search_triggered = False
        
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
                    if key in st.session_state:
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
            
            clean_suggested_genre = suggested_genre
            if suggested_genre and '/' in suggested_genre:
                clean_suggested_genre = suggested_genre.replace('/', ' ')
                if clean_suggested_genre not in all_genres:
                    for genre in all_genres:
                        if suggested_genre.split('/')[0] in genre:
                            clean_suggested_genre = genre
                            break
            
            default_index = 0
            if suggested_genre and clean_suggested_genre in all_genres:
                default_index = all_genres.index(clean_suggested_genre) + 1
            elif stored_data.get('selected_genre') and stored_data['selected_genre'] in all_genres:
                default_index = all_genres.index(stored_data['selected_genre']) + 1
            
            genre_key = f"genre_select_{record_key}"
            selected_genre = st.selectbox(
                "Genre:",
                options=["Select genre..."] + all_genres,
                index=default_index,
                key=genre_key
            )
            
            if selected_genre == "Select genre...":
                st.error("⚠️ Please select a genre")
                stored_data['selected_genre'] = None
            else:
                stored_data['selected_genre'] = selected_genre
        
        with col3:
            user = st.session_state.get('user', {})
            user_role = user.get('role', 'consignor')
            
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
                        price_advice = self.price_advise_handler.get_price_advice(
                            artist,
                            title,
                            selected_condition,
                            stored_data['record_data']
                        )
                        
                        if price_advice['success']:
                            stored_data['advised_store_price'] = price_advice['advised_store_price']
                            stored_data['user_price'] = price_advice['advised_store_price']
                            
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
        
        with col4:
            if (stored_data['selected_condition'] and 
                stored_data['selected_condition'] != "Select condition..." and
                stored_data.get('price_research')):
                
                advised_store_price = stored_data.get('advised_store_price')
                
                if stored_data.get('user_price') is None and advised_store_price:
                    stored_data['user_price'] = advised_store_price
                    st.session_state[f"{record_key}_data"] = stored_data
                
                # REMOVED ALL MAX PRICE CALCULATIONS
                price_input_key = f"price_input_{record_key}"
                user_price = st.number_input(
                    "Price ($)",
                    min_value=0.0,
                    # COMPLETELY REMOVED: max_value parameter
                    value=float(advised_store_price) if advised_store_price else 0.0,
                    step=0.01,
                    format="%.2f",
                    key=price_input_key,
                    # SIMPLIFIED HELP TEXT
                    help="Enter store price" if advised_store_price and advised_store_price > 0 else "Enter price"
                )
                
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
                stored_data['selected_genre'] != "Select genre..." and
                stored_data['selected_genre'] is not None
            )
            
            add_button_key = f"add_{record_key}"
            
            disabled_reason = ""
            if not stored_data.get('selected_genre') or stored_data['selected_genre'] in [None, "Select genre..."]:
                disabled_reason = "Please select a genre"
            elif not stored_data.get('selected_condition') or stored_data['selected_condition'] == "Select condition...":
                disabled_reason = "Please select a condition"
            elif not stored_data.get('user_price') or stored_data.get('user_price', 0) <= 0:
                disabled_reason = "Please enter a price"
            
            if add_enabled:
                if st.button("➕ Add", key=add_button_key, type="primary", width='stretch'):
                    record_to_add = stored_data['record_data'].copy()
                    record_to_add['selected_condition'] = stored_data['selected_condition']
                    record_to_add['user_price'] = stored_data['user_price']
                    record_to_add['advised_store_price'] = stored_data.get('advised_store_price')
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
                        if f"{record_key}_data" in st.session_state:
                            del st.session_state[f"{record_key}_data"]
                        st.session_state.record_added = True
                        
                        if user.get('username') == 'demo_user':
                            st.session_state.demo_last_added = {
                                'artist': record_to_add['artist'],
                                'title': record_to_add['title'],
                                'store_price': stored_data['user_price']
                            }
                        
                        st.success(f"✅ Record added successfully! ID: {record_id}")
                    else:
                        st.error("Failed to add record to database")
            else:
                st.button("➕ Add", key=f"add_disabled_{record_key}", disabled=True, width='stretch',
                        help=disabled_reason)
        
        if (stored_data['selected_condition'] and 
            stored_data['selected_condition'] != "Select condition..." and
            stored_data.get('price_research')):
            
            with st.expander("📊 Price Details", expanded=False):
                self._render_price_calculation_details(stored_data['price_research'])
                
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
    
    def _add_inventory_record(self, record_data, genre, search_term, consignor_id=None):
        """Add inventory record to database via API - FIXED VERSION with genre validation"""
        # FIX: Validate genre is provided
        if genre is None or genre == "Select genre...":
            st.error("❌ **Genre is required! Please select a genre.**")
            return False, None
        
        # FIX: Get genre_id from database - CRITICAL FIX
        genre_id = None
        if genre:
            try:
                # Call API to get genre_id for genre name
                response = requests.get(
                    f"{self.base_url}/genres/by-name/{genre}",
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'success':
                        genre_id = data.get('genre_id')
                else:
                    # Try alternative endpoint if exists
                    response = requests.get(
                        f"{self.base_url}/genres",
                        timeout=5
                    )
                    if response.status_code == 200:
                        genres_data = response.json()
                        if genres_data.get('status') == 'success':
                            genres_list = genres_data.get('genres', [])
                            for g in genres_list:
                                if isinstance(g, dict):
                                    if g.get('genre_name') == genre:
                                        genre_id = g.get('id')
                                        break
                                elif g == genre:
                                    # Handle simple string list
                                    genre_id = 1  # Default or find better mapping
                                    break
            except Exception as e:
                st.error(f"Error getting genre ID: {e}")
                return False, None
        
        # Throw error if genre_id still not set
        if genre_id is None:
            st.error(f"❌ **Genre '{genre}' not found in database! Please check the genre exists.**")
            return False, None
        
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
        
        format_selected = st.session_state.get('format_select', 'Vinyl')
        
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
        
        discogs_genre = record_data.get('discogs_genre', '')
        
        # FIX: Clean discogs_genre for API calls
        discogs_genre_for_api = discogs_genre
        if '/' in discogs_genre:
            discogs_genre_for_api = discogs_genre.replace('/', ' ')
        
        store_price = user_price if user_price else 0.0
        
        consignment_start_date = None
        discount_eligible_date = None
        original_consignor_price = None
        
        if consignor_id:
            consignment_start_date = datetime.now().date()
            full_price_days = int(self.get_config_value('CONSIGNMENT_FULL_PRICE_DAYS'))
            discount_eligible_date = consignment_start_date + timedelta(days=full_price_days)
            original_consignor_price = store_price
        
        try:
            # GENERATE BARCODE BEFORE INSERTING RECORD
            # Use a combination of timestamp and record data to create a unique barcode
            import time
            import hashlib
            
            # Create a unique barcode using timestamp, artist, and title
            barcode_seed = f"{time.time()}_{artist}_{title}"
            barcode_hash = hashlib.md5(barcode_seed.encode()).hexdigest()[:12]
            # Ensure it's numeric for barcode standards
            barcode_number = ''.join(filter(str.isdigit, barcode_hash))
            if len(barcode_number) < 8:
                barcode_number = barcode_number.ljust(8, '0')[:8]
            else:
                barcode_number = barcode_number[:12]
            
            record_data_to_save = {
                'artist': artist,
                'title': title,
                'barcode': barcode_number,  # BARCODE ASSIGNED BEFORE INSERTION
                'genre_id': genre_id,  # NOW HAS VALID GENRE ID
                'image_url': image_url,
                'catalog_number': catalog_number,
                'format': format_selected,
                'condition': selected_condition,
                'store_price': float(store_price),
                'youtube_url': youtube_url,
                'compilation': bool(compilation),
                'advised_store_price': float(record_data.get('advised_store_price', store_price))
            }
            
            if consignor_id:
                record_data_to_save['consignor_id'] = int(consignor_id)
                record_data_to_save['commission_rate'] = float(commission_rate)
                record_data_to_save['store_return_days'] = int(store_return_days)
                record_data_to_save['store_credit_option'] = st.session_state.get('store_credit_option', False)
                record_data_to_save['consignment_start_date'] = consignment_start_date.isoformat() if consignment_start_date else None
                record_data_to_save['discount_eligible_date'] = discount_eligible_date.isoformat() if discount_eligible_date else None
                record_data_to_save['original_consignor_price'] = float(original_consignor_price) if original_consignor_price else None
            
            # DEBUG: Show what's being sent
            # st.write("Sending data:", record_data_to_save)
            
            response = requests.post(
                f"{self.base_url}/records",
                json=record_data_to_save,
                timeout=10
            )
            
            # DEBUG: Show response
            st.write("Response status:", response.status_code)
            if response.status_code != 200:
                st.write("Response body:", response.text)
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == 'success':
                    record_id = response_data.get('record_id')
                    
                    # Optional: Save genre mapping
                    if discogs_genre_for_api and genre_id:
                        mapping_data = {
                            'discogs_genre': discogs_genre_for_api,
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
    
    def update_database_record(self, record_data, genre, store_credit_option=None, user_price=None):
        """Update database record with enhanced consignment features via API - FIXED VERSION"""
        if genre is None:
            raise Exception("genre parameter is required but was None")
        
        record_id = record_data.get('id')
        
        if not record_id:
            st.error("No record ID provided")
            return False
        
        # First, get the genre_id for the genre name
        genre_id = None
        try:
            # Call API to get genre_id for genre name
            response = requests.get(
                f"{self.base_url}/genres/by-name/{genre}",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    genre_id = data.get('genre_id')
                else:
                    st.error(f"Genre '{genre}' not found")
                    return False
            else:
                st.error(f"Failed to get genre ID for '{genre}'")
                return False
        except Exception as e:
            st.error(f"Error getting genre ID: {e}")
            return False
        
        # Prepare updates
        updates = {
            'genre_id': genre_id
        }
        
        # Get compilation status from record_data
        compilation = record_data.get('compilation', False)
        updates['compilation'] = compilation
        
        # Get consignment info from record_data
        consignor_id = record_data.get('consignor_id')
        commission_rate = record_data.get('commission_rate')
        store_return_days = record_data.get('store_return_days')
        
        # Add consignor fields if provided
        if consignor_id is not None:
            updates['consignor_id'] = int(consignor_id) if consignor_id else None
        
        if commission_rate is not None:
            updates['commission_rate'] = float(commission_rate)
        
        if store_return_days is not None:
            updates['store_return_days'] = int(store_return_days)
        
        # Update store credit option if provided
        if store_credit_option is not None:
            updates['store_credit_option'] = bool(store_credit_option)
        
        # Update price if provided
        if user_price is not None:
            updates['store_price'] = float(user_price)
            updates['original_consignor_price'] = float(user_price)
        
        # If consignor is being added, set consignment dates
        if consignor_id and not record_data.get('consignment_start_date'):
            updates['consignment_start_date'] = datetime.now().date().isoformat()
            try:
                full_price_days = int(self.get_config_value('CONSIGNMENT_FULL_PRICE_DAYS', '90'))
            except:
                full_price_days = 90
            updates['discount_eligible_date'] = (datetime.now().date() + timedelta(days=full_price_days)).isoformat()
        
        # Call API to update record
        try:
            base_url = "https://arjanshaw.pythonanywhere.com"
            response = requests.put(
                f"{base_url}/records/{record_id}",
                json=updates,
                timeout=10
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('status') == 'success':
                    return True
                else:
                    error_msg = response_data.get('error', 'Unknown error')
                    st.error(f"API returned error: {error_msg}")
                    return False
            else:
                st.error(f"API request failed with status {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            st.error("API request timed out")
            return False
        except Exception as e:
            st.error(f"Error updating record: {str(e)}")
            return False

    def _render_database_results(self, results, search_type, user):
        """Render database search results - FIXED to filter for consignors"""
        if not results:
            st.warning("No matching records found in database")
            return
        
        # Filter results for consignors - only show their own records
        user_role = user.get('role', 'consignor')
        user_id = user.get('id')
        
        if user_role == 'consignor':
            filtered_results = []
            for record in results:
                # Check if record has consignor_id attribute
                record_consignor_id = None
                if hasattr(record, 'get'):
                    record_consignor_id = record.get('consignor_id')
                elif isinstance(record, dict):
                    record_consignor_id = record.get('consignor_id')
                
                # Include record if it belongs to this consignor
                if record_consignor_id == user_id:
                    filtered_results.append(record)
            
            results = filtered_results
        
        if not results:
            st.warning("No matching records found that belong to you")
            return
        
        st.write(f"**Found {len(results)} matching records**")
        
        for i, record in enumerate(results):
            self._render_database_result_item(record, i, user)

    def _render_database_result_item(self, record, index, user):
        """Render individual database result item - UPDATED to include created_at and delete button for consignors"""
        if hasattr(record, 'get'):
            record_id = record.get('id')
        elif hasattr(record, '__getitem__'):
            try:
                record_id = record['id']
            except (KeyError, TypeError):
                if hasattr(record, 'id'):
                    record_id = record.id
                elif 'id' in record:
                    record_id = record['id']
                else:
                    record_id = index
        else:
            record_id = index
        
        col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 1])
        
        with col1:
            image_url = record.get('image_url', '') if hasattr(record, 'get') else ''
            if image_url:
                st.image(image_url, width=80)
            else:
                st.write("No image")
        
        with col2:
            artist = record.get('artist', '') if hasattr(record, 'get') else ''
            title = record.get('title', '') if hasattr(record, 'get') else ''
            
            st.write(f"**{artist} - {title}**")
            
            catalog = record.get('catalog_number', '') if hasattr(record, 'get') else ''
            genre = record.get('genre', '') if hasattr(record, 'get') else ''
            barcode = record.get('barcode', '') if hasattr(record, 'get') else ''
            consignor_name = record.get('consignor_name', '') if hasattr(record, 'get') else ''
            
            info_lines = []
            if catalog:
                info_lines.append(f"**Catalog:** {catalog}")
            if genre:
                info_lines.append(f"**Genre:** {genre}")
            if barcode:
                info_lines.append(f"**Barcode:** {barcode}")
            if consignor_name:
                info_lines.append(f"**Consignor:** {consignor_name}")
            
            # NEW: Add created_at field if available
            created_at = record.get('created_at', '') if hasattr(record, 'get') else ''
            if created_at:
                # Format the date for display
                try:
                    if 'T' in created_at:
                        # Handle ISO format with T separator
                        date_part = created_at.split('T')[0]
                        info_lines.append(f"**Created:** {date_part}")
                    else:
                        info_lines.append(f"**Created:** {created_at}")
                except:
                    info_lines.append(f"**Created:** {created_at}")
            
            if info_lines:
                for line in info_lines:
                    st.write(line)
            
            # NEW: Genre editing field (just like YouTube URL)
            if hasattr(record, 'get'):
                current_genre = record.get('genre', '')
                genre_key = f"genre_edit_{record_id}"
                
                # Get all available genres
                all_genres = self.get_all_genres()
                
                # Find current genre index
                current_index = 0  # Default to first option
                if current_genre in all_genres:
                    current_index = all_genres.index(current_genre) + 1
                
                # Genre selection dropdown
                new_genre = st.selectbox(
                    "Genre:",
                    options=["Select genre..."] + all_genres,
                    index=current_index,
                    key=genre_key
                )
                
                # Show save button if genre changed
                if new_genre != "Select genre..." and new_genre != current_genre:
                    if st.button("💾 Save Genre", key=f"save_genre_{record_id}", type="secondary", width='stretch'):
                        # Add confirmation message
                        confirm_container = st.empty()
                        with confirm_container:
                            st.info(f"Updating genre from '{current_genre}' to '{new_genre}'...")
                        
                        # Update the record with new genre
                        success = self.update_database_record(
                            record,
                            new_genre,
                            store_credit_option=None,
                            user_price=None
                        )
                        
                        if success:
                            confirm_container.empty()
                            st.success(f"✅ Genre updated successfully from '{current_genre}' to '{new_genre}'!")
                            st.rerun()
                        else:
                            confirm_container.empty()
                            st.error("❌ Failed to update genre")
        
        with col3:
            store_price = record.get('store_price', 0.0) if hasattr(record, 'get') else 0.0
            
            st.write(f"**Store Price:** ${store_price:.2f}")
            
            condition = record.get('condition', '') if hasattr(record, 'get') else ''
            if condition:
                st.write(f"**Condition:** {condition}")
            
            # YouTube link editing field
            youtube_url = record.get('youtube_url', '') if hasattr(record, 'get') else ''
            youtube_key = f"youtube_edit_{record_id}"
            new_youtube_url = st.text_input(
                "YouTube URL:",
                value=youtube_url,
                placeholder="Enter YouTube URL...",
                key=youtube_key
            )
            
            # Save button for YouTube URL
            if new_youtube_url != youtube_url:
                if st.button("💾 Save YouTube Link", key=f"save_youtube_{record_id}", type="secondary", width='stretch'):
                    # Add confirmation message
                    confirm_container = st.empty()
                    with confirm_container:
                        st.info("Updating YouTube URL...")
                    
                    success = self.update_record(record_id, {'youtube_url': new_youtube_url})
                    if success:
                        confirm_container.empty()
                        st.success("✅ YouTube link saved!")
                        st.rerun()
                    else:
                        confirm_container.empty()
                        st.error("❌ Failed to save YouTube link")
        
        with col4:
            user_role = user.get('role', 'consignor')
            user_id = user.get('id')
            record_consignor_id = record.get('consignor_id') if hasattr(record, 'get') else None
            
            can_edit = (user_role == 'admin' or 
                       (user_role == 'consignor' and user_id and record_consignor_id == user_id))
            
            # Add "Set to Inactive" button (only for admin or record owner)
            status_id = record.get('status_id', 2) if hasattr(record, 'get') else 2
            
            # Show inactive button for active records (status_id = 2)
            if can_edit and status_id == 2:  # Only show for active records
                if st.button("⏸️ Inactive", key=f"inactive_{record_id}", type="secondary", width='stretch', 
                           help="Set record to inactive status (status_id = 1)"):
                    # Add confirmation message
                    confirm_container = st.empty()
                    with confirm_container:
                        st.info("Setting record to inactive...")
                    
                    if self._set_record_inactive(record_id):
                        confirm_container.empty()
                        st.success(f"✅ Record set to inactive!")
                        st.rerun()
                    else:
                        confirm_container.empty()
                        st.error("Failed to set record to inactive")
            # Show reactivate button for inactive records (status_id = 1)
            elif can_edit and status_id == 1:
                if st.button("▶️ Activate", key=f"activate_{record_id}", type="secondary", width='stretch',
                           help="Reactivate record (status_id = 2)"):
                    # Add confirmation message
                    confirm_container = st.empty()
                    with confirm_container:
                        st.info("Reactivating record...")
                    
                    if self._set_record_active(record_id):
                        confirm_container.empty()
                        st.success(f"✅ Record reactivated!")
                        st.rerun()
                    else:
                        confirm_container.empty()
                        st.error("Failed to reactivate record")
        
        with col5:
            # Display status with better icons based on actual status IDs
            status_id = record.get('status_id', 2) if hasattr(record, 'get') else 2
            date_sold = record.get('date_sold') if hasattr(record, 'get') else None
            date_removed = record.get('date_removed') if hasattr(record, 'get') else None
            
            # Correct status mapping:
            # status_id = 1: New/Inactive
            # status_id = 2: Active 
            # status_id = 3: Sold
            # status_id = 4: Removed
            
            if status_id == 1:
                status = "⏸️ Inactive"
            elif status_id == 2:
                status = "✅ Active"
            elif status_id == 3:
                status = "💰 Sold"
            elif status_id == 4:
                status = "🗑️ Removed"
            else:
                status = f"❓ Unknown ({status_id})"
            
            st.write(f"**Status:** {status}")
            
            # Delete button - FIXED to allow consignors to delete their own records
            user_role = user.get('role', 'consignor')
            user_id = user.get('id')
            record_consignor_id = record.get('consignor_id') if hasattr(record, 'get') else None
            
            # Allow deletion if:
            # 1. User is admin OR
            # 2. User is consignor and this is their record
            can_delete = (user_role == 'admin' or 
                         (user_role == 'consignor' and user_id and record_consignor_id == user_id))
            
            if can_delete:
                if st.button("🗑️ Delete", key=f"delete_{record_id}", type="secondary", width='stretch'):
                    # Add confirmation message
                    confirm_container = st.empty()
                    with confirm_container:
                        st.info("Deleting record...")
                    
                    if self.delete_record(record_id):
                        confirm_container.empty()
                        st.success(f"✅ Record deleted successfully!")
                        st.rerun()
                    else:
                        confirm_container.empty()
                        st.error("Failed to delete record")
        
        st.divider()
    
    def _set_record_inactive(self, record_id):
        """Set a record to inactive status (status_id = 1)"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would set record {record_id} to inactive")
            return True
            
        try:
            updates = {
                'status_id': 1  # Set to inactive
            }
            
            success = self.update_record(record_id, updates)
            if success:
                return True
            else:
                st.error("Failed to update record status")
                return False
        except Exception as e:
            st.error(f"Error setting record to inactive: {e}")
            return False
    
    def _set_record_active(self, record_id):
        """Reactivate a record (status_id = 2)"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would reactivate record {record_id}")
            return True
            
        try:
            updates = {
                'status_id': 2  # Set to active
            }
            
            success = self.update_record(record_id, updates)
            if success:
                return True
            else:
                st.error("Failed to update record status")
                return False
        except Exception as e:
            st.error(f"Error reactivating record: {e}")
            return False