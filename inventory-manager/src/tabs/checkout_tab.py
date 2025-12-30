import streamlit as st
import pandas as pd
from datetime import datetime as dt
import requests

class CheckoutTab:
    def __init__(self):
        # Initialize API client
        self.api_client = APIClient()
    
    def render(self):
        st.header("💰 Checkout")
        
        user = st.session_state.get('user', {})
        user_role = user.get('role')
        
        # Only admin can view checkout
        if user_role != 'admin':
            st.error("❌ Access denied. Administrator privileges required to view checkout.")
            return
        
        # Initialize checkout records in session state
        if 'checkout_records' not in st.session_state:
            st.session_state.checkout_records = []
        
        # Two-column layout
        col1, col2 = st.columns([3, 1])
        
        with col1:
            self._render_search_section()
        
        with col2:
            self._render_checkout_cart()
        
        # Show current checkout list if any items
        if st.session_state.checkout_records:
            self._render_checkout_summary()
    
    def _render_search_section(self):
        """Render search section for adding items to checkout"""
        st.subheader("🔍 Search Items to Checkout")
        
        with st.form(key="checkout_search_form"):
            search_input = st.text_input(
                "Search by artist, title, barcode, or catalog number:",
                placeholder="Enter search term...",
                key="checkout_search_input"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                search_button = st.form_submit_button("🔍 Search", use_container_width=True)
            with col2:
                if st.form_submit_button("🗑️ Clear Results", type="secondary", use_container_width=True):
                    st.session_state.search_results_checkout = []
                    st.rerun()
        
        if search_button and search_input:
            with st.spinner("Searching records..."):
                results = self._search_records_for_checkout(search_input)
                st.session_state.search_results_checkout = results
        
        # Display search results
        if st.session_state.get('search_results_checkout'):
            st.write(f"**Found {len(st.session_state.search_results_checkout)} records:**")
            
            for record in st.session_state.search_results_checkout:
                self._render_checkout_search_result(record)
    
    def _render_checkout_search_result(self, record):
        """Render individual search result for checkout"""
        col1, col2, col3, col4, col5 = st.columns([1, 3, 2, 2, 1])
        
        with col1:
            image_url = record.get('image_url', '')
            if image_url:
                st.image(image_url, width=80)
            else:
                st.write("📷")
        
        with col2:
            artist = record.get('artist', '')
            title = record.get('title', '')
            
            st.write(f"**{artist} - {title}**")
            
            catalog = record.get('catalog_number', '')
            genre = record.get('genre_name', record.get('genre', 'Unknown'))
            barcode = record.get('barcode', '')
            
            info_lines = []
            if catalog:
                info_lines.append(f"**Catalog:** {catalog}")
            if genre:
                info_lines.append(f"**Genre:** {genre}")
            if barcode:
                info_lines.append(f"**Barcode:** {barcode}")
            
            if info_lines:
                for line in info_lines:
                    st.write(line)
        
        with col3:
            store_price = record.get('store_price', 0.0)
            st.write(f"**Price:** ${store_price:.2f}")
            
            # Show consignor info if available
            consignor_id = record.get('consignor_id')
            if consignor_id:
                user_info = self.api_client.get_user(consignor_id)
                if user_info:
                    st.write(f"**Consignor:** {user_info.get('username', f'ID: {consignor_id}')}")
        
        with col4:
            # Show sale status
            date_sold = record.get('date_sold')
            date_paid = record.get('date_paid')
            
            if date_sold:
                if date_paid:
                    st.write("**Status:** ✅ Paid")
                else:
                    st.write("**Status:** 💳 Sold (unpaid)")
            else:
                st.write("**Status:** 🟢 Available")
        
        with col5:
            # Check if already sold or paid
            date_sold = record.get('date_sold')
            date_paid = record.get('date_paid')
            
            if date_sold and not date_paid:
                st.button("✅ In Checkout", key=f"sold_{record['id']}", disabled=True, use_container_width=True)
            elif date_sold and date_paid:
                st.button("💰 Paid", key=f"paid_{record['id']}", disabled=True, use_container_width=True)
            else:
                # Check if already in checkout
                already_in_checkout = any(r['id'] == record['id'] for r in st.session_state.checkout_records)
                
                if already_in_checkout:
                    st.button("✅ Added", key=f"added_{record['id']}", disabled=True, use_container_width=True)
                else:
                    if st.button("➕ Add to Checkout", key=f"add_{record['id']}", use_container_width=True):
                        st.session_state.checkout_records.append(record)
                        st.success(f"Added {record.get('artist', '')} - {record.get('title', '')} to checkout")
                        st.rerun()
        
        st.divider()
    
    def _render_checkout_cart(self):
        """Render the checkout cart sidebar"""
        st.subheader("🛒 Checkout Cart")
        
        selected_count = len(st.session_state.checkout_records)
        
        if selected_count == 0:
            st.info("No items in checkout cart.")
            return
        
        st.success(f"**{selected_count} items selected**")
        
        # Calculate total value
        total_value = sum(float(r.get('store_price', 0)) for r in st.session_state.checkout_records)
        st.write(f"**Total Value:** ${total_value:.2f}")
        
        # Show selected items with remove option
        for i, record in enumerate(st.session_state.checkout_records):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"{record.get('artist', 'Unknown')}")
                st.write(f"*{record.get('title', 'Unknown')[:20]}...*")
            
            with col2:
                st.write(f"${record.get('store_price', 0):.2f}")
            
            with col3:
                if st.button("❌", key=f"remove_{record['id']}", help="Remove"):
                    st.session_state.checkout_records.pop(i)
                    st.rerun()
        
        # Clear all button
        if st.button("🗑️ Clear All", type="secondary", use_container_width=True):
            st.session_state.checkout_records = []
            st.rerun()
    
    def _render_checkout_summary(self):
        """Render checkout summary and payment processing"""
        st.divider()
        st.subheader("💳 Process Payment")
        
        # Calculate totals
        record_ids = [record['id'] for record in st.session_state.checkout_records]
        total_sales = sum(float(r.get('store_price', 0)) for r in st.session_state.checkout_records)
        
        # Group by consignor for summary
        consignor_summary = {}
        for record in st.session_state.checkout_records:
            consignor_id = record.get('consignor_id')
            if consignor_id:
                price = float(record.get('store_price', 0))
                commission_rate = float(record.get('commission_rate', 0.20))
                commission = price * commission_rate
                payout = price - commission
                
                if consignor_id not in consignor_summary:
                    consignor_summary[consignor_id] = {
                        'total_sales': 0,
                        'total_commission': 0,
                        'total_payout': 0,
                        'records': 0
                    }
                
                consignor_summary[consignor_id]['total_sales'] += price
                consignor_summary[consignor_id]['total_commission'] += commission
                consignor_summary[consignor_id]['total_payout'] += payout
                consignor_summary[consignor_id]['records'] += 1
        
        # Display summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Items", len(record_ids))
        with col2:
            st.metric("Total Sales", f"${total_sales:.2f}")
        with col3:
            if consignor_summary:
                total_payout = sum(info['total_payout'] for info in consignor_summary.values())
                st.metric("Total Payout", f"${total_payout:.2f}")
        
        # Show consignor breakdown
        if consignor_summary:
            st.write("**Consignor Breakdown:**")
            for consignor_id, summary in consignor_summary.items():
                user = self.api_client.get_user(consignor_id)
                username = user.get('username', f"ID: {consignor_id}") if user else f"ID: {consignor_id}"
                
                col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
                with col1:
                    st.write(f"**{username}**")
                with col2:
                    st.write(f"{summary['records']} items")
                with col3:
                    st.write(f"Sales: ${summary['total_sales']:.2f}")
                with col4:
                    st.write(f"Payout: ${summary['total_payout']:.2f}")
        
        # Payment button
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💳 Process Payment", type="primary", use_container_width=True):
                self._process_checkout_payment(record_ids)
        with col2:
            if st.button("🔁 Mark as Sold Only", type="secondary", use_container_width=True):
                self._mark_as_sold_only(record_ids)
    
    def _search_records_for_checkout(self, search_term):
        """Search records for checkout - only shows unsold items"""
        try:
            # Search via API
            response = requests.get(
                f"{self.api_client.base_url}/search?q={search_term}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    all_results = data.get('records', [])
                    
                    # Filter out already sold items
                    available_results = []
                    for record in all_results:
                        date_sold = record.get('date_sold')
                        date_paid = record.get('date_paid')
                        
                        # Only include if not sold OR sold but not paid
                        if not date_sold or (date_sold and not date_paid):
                            available_results.append(record)
                    
                    return available_results
            
            return []
            
        except Exception as e:
            st.error(f"Search error: {e}")
            return []
    
    def _process_checkout_payment(self, record_ids):
        """Process payment for checked out items"""
        if not record_ids:
            st.error("No items to process")
            return
        
        # First mark as sold
        success_sold = self._mark_as_sold_only(record_ids)
        if not success_sold:
            st.error("Failed to mark items as sold")
            return
        
        # Then process payment
        success_payment = self.api_client.process_checkout_payment(record_ids)
        
        if success_payment:
            st.success(f"✅ Payment processed for {len(record_ids)} items!")
            
            # Calculate totals for display
            total_sales = sum(float(r.get('store_price', 0)) for r in st.session_state.checkout_records)
            
            # Group by consignor for summary
            consignor_summary = {}
            for record in st.session_state.checkout_records:
                consignor_id = record.get('consignor_id')
                if consignor_id:
                    price = float(record.get('store_price', 0))
                    commission_rate = float(record.get('commission_rate', 0.20))
                    commission = price * commission_rate
                    payout = price - commission
                    
                    if consignor_id not in consignor_summary:
                        consignor_summary[consignor_id] = {
                            'total_sales': 0,
                            'total_commission': 0,
                            'total_payout': 0,
                            'records': 0
                        }
                    
                    consignor_summary[consignor_id]['total_sales'] += price
                    consignor_summary[consignor_id]['total_commission'] += commission
                    consignor_summary[consignor_id]['total_payout'] += payout
                    consignor_summary[consignor_id]['records'] += 1
            
            # Display summary
            st.write("**Payment Summary:**")
            st.write(f"Total Sales: ${total_sales:.2f}")
            
            for consignor_id, summary in consignor_summary.items():
                user = self.api_client.get_user(consignor_id)
                username = user.get('username', f"ID: {consignor_id}") if user else f"ID: {consignor_id}"
                st.write(f"**{username}:** {summary['records']} items, Payout: ${summary['total_payout']:.2f}")
            
            # Clear checkout records
            st.session_state.checkout_records = []
            st.rerun()
        else:
            st.error("❌ Failed to process payment")
    
    def _mark_as_sold_only(self, record_ids):
        """Mark items as sold without processing payment"""
        success_count = 0
        
        for record_id in record_ids:
            today = dt.now().date().isoformat()
            updates = {'date_sold': today}
            
            success = self.api_client.update_record(record_id, updates)
            if success:
                success_count += 1
        
        if success_count == len(record_ids):
            st.success(f"✅ Marked {success_count} items as sold")
            return True
        else:
            st.warning(f"⚠️ Marked {success_count} of {len(record_ids)} items as sold")
            return False

class APIClient:
    """API client for checkout operations"""
    
    def __init__(self, base_url="https://arjanshaw.pythonanywhere.com"):
        self.base_url = base_url
    
    def get_user(self, user_id):
        """Get user by ID"""
        try:
            response = requests.get(f"{self.base_url}/users/{user_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"API Error getting user: {e}")
            return None
    
    def update_record(self, record_id, updates):
        """Update a record via API"""
        try:
            response = requests.put(
                f"{self.base_url}/records/{record_id}",
                json=updates
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"API Error updating record: {e}")
            return False
    
    def process_checkout_payment(self, record_ids):
        """Process payment for checked out records"""
        try:
            # This endpoint should be implemented in the API
            response = requests.post(
                f"{self.base_url}/checkout/process-payment",
                json={'record_ids': record_ids}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error processing payment: {e}")
            return False