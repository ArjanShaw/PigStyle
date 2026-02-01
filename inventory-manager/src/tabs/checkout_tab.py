import streamlit as st
import pandas as pd
from datetime import datetime as dt
import requests
import json
import uuid
import time

class CheckoutTab:
    def __init__(self):
        # Initialize API client
        self.api_client = APIClient()
    
    def render(self):
        st.header("💰 Checkout")
        
        user = st.session_state.get('user', {})
        user_role = user.get('role')
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info("👀 **Demo Mode**: In a real store, checkout would be handled by a store employee.")
            st.info("You can simulate the checkout process in demo mode.")
        
        # Only admin can view checkout
        if user_role != 'admin' and not is_demo:
            st.error("❌ Access denied. Administrator privileges required to view checkout.")
            return
        
        # Initialize checkout records in session state
        if 'checkout_records' not in st.session_state:
            st.session_state.checkout_records = []
        
        # Initialize Square payment status
        if 'square_checkout_status' not in st.session_state:
            st.session_state.square_checkout_status = None
        
        # Initialize polling status
        if 'last_poll_time' not in st.session_state:
            st.session_state.last_poll_time = 0
        
        # Two-column layout
        col1, col2 = st.columns([3, 1])
        
        with col1:
            self._render_search_section()
        
        with col2:
            self._render_checkout_cart()
        
        # Show current checkout list if any items
        if st.session_state.checkout_records:
            self._render_checkout_summary()
        
        # Show Square payment status if processing
        if st.session_state.square_checkout_status:
            self._render_payment_status()
    
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
                search_button = st.form_submit_button("🔍 Search", width='stretch')
            with col2:
                if st.form_submit_button("🗑️ Clear Results", type="secondary", width='stretch'):
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
            status_id = record.get('status_id')
            status_map = {
                1: "🆕 New",
                2: "✅ Active",
                3: "💰 Sold",
                4: "🗑️ Removed"
            }
            status_display = status_map.get(status_id, "❓ Unknown")
            st.write(f"**Status:** {status_display}")
        
        with col5:
            # Check status - only allow adding if not sold
            status_id = record.get('status_id')
            
            if status_id == 3:  # Sold
                st.button("💰 Sold", key=f"sold_{record['id']}", disabled=True, width='stretch')
            else:
                # Check if already in checkout
                already_in_checkout = any(r['id'] == record['id'] for r in st.session_state.checkout_records)
                
                if already_in_checkout:
                    st.button("✅ Added", key=f"added_{record['id']}", disabled=True, width='stretch')
                else:
                    if st.button("➕ Add", key=f"add_{record['id']}", width='stretch'):
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
        if st.button("🗑️ Clear All", type="secondary", width='stretch'):
            st.session_state.checkout_records = []
            st.session_state.square_checkout_status = None
            st.rerun()
    
    def _render_checkout_summary(self):
        """Render checkout summary and payment processing"""
        st.divider()
        st.subheader("💳 Process Payment")
        
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        # Calculate totals
        record_ids = [record['id'] for record in st.session_state.checkout_records]
        total_sales = sum(float(r.get('store_price', 0)) for r in st.session_state.checkout_records)
        record_titles = [f"{r.get('artist', '')} - {r.get('title', '')}" for r in st.session_state.checkout_records]
        
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
                        'records': 0,
                        'username': ''
                    }
                
                consignor_summary[consignor_id]['total_sales'] += price
                consignor_summary[consignor_id]['total_commission'] += commission
                consignor_summary[consignor_id]['total_payout'] += payout
                consignor_summary[consignor_id]['records'] += 1
                
                # Get consignor username
                if not consignor_summary[consignor_id]['username']:
                    user_info = self.api_client.get_user(consignor_id)
                    if user_info:
                        consignor_summary[consignor_id]['username'] = user_info.get('username', f'ID: {consignor_id}')
        
        # Display summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Items", len(record_ids))
        with col2:
            st.metric("Total Amount", f"${total_sales:.2f}")
        with col3:
            if consignor_summary:
                total_payout = sum(info['total_payout'] for info in consignor_summary.values())
                st.metric("Total Payout", f"${total_payout:.2f}")
        
        # Show consignor breakdown
        if consignor_summary:
            st.write("**Consignor Breakdown:**")
            for consignor_id, summary in consignor_summary.items():
                username = summary['username'] or f"ID: {consignor_id}"
                
                col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
                with col1:
                    st.write(f"**{username}**")
                with col2:
                    st.write(f"{summary['records']} items")
                with col3:
                    st.write(f"Sales: ${summary['total_sales']:.2f}")
                with col4:
                    st.write(f"Payout: ${summary['total_payout']:.2f}")
        
        # Payment method selection
        st.write("---")
        st.write("**Select Payment Method:**")
        
        col1, col2 = st.columns(2)
        with col1:
            use_square = st.checkbox("💳 Process with Square Terminal", value=True)
        with col2:
            use_cash = st.checkbox("💵 Mark as Cash/Check Payment", value=False)
        
        # Process payment buttons
        if use_square and not use_cash:
            # Square Terminal payment
            if st.button("💳 Process with Square Terminal", type="primary", width='stretch'):
                if is_demo:
                    st.success(f"✅ Demo: Would process ${total_sales:.2f} payment via Square Terminal")
                    st.info("💡 Demo: Customer would complete payment on the Square Terminal.")
                    
                    # Simulate successful payment
                    self._handle_successful_payment(record_ids, total_sales, "square")
                else:
                    # Call Square Terminal endpoint
                    with st.spinner("Initiating Square Terminal payment..."):
                        result = self._initiate_square_checkout(record_ids, total_sales, record_titles)
                        
                        if result.get('status') == 'success':
                            st.session_state.square_checkout_status = {
                                'status': 'processing',
                                'checkout_id': result.get('checkout_id'),
                                'amount': total_sales,
                                'record_ids': record_ids,
                                'start_time': time.time()
                            }
                            st.success("✅ Payment initiated on Square Terminal!")
                            st.info("💳 Please ask the customer to complete payment on the Square Terminal device.")
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to initiate payment: {result.get('error', 'Unknown error')}")
        
        elif use_cash and not use_square:
            # Cash/Check payment
            if st.button("💰 Mark as Cash/Check Paid", type="secondary", width='stretch'):
                if is_demo:
                    st.success(f"✅ Demo: Would mark ${total_sales:.2f} as cash/check payment")
                    self._handle_successful_payment(record_ids, total_sales, "cash")
                else:
                    success = self._mark_as_paid(record_ids, payment_method="cash")
                    if success:
                        st.success(f"✅ Successfully marked {len(record_ids)} items as paid!")
                        st.info("💡 Records updated and consignors credited.")
                        
                        # Clear checkout records
                        st.session_state.checkout_records = []
                        st.rerun()
                    else:
                        st.error("❌ Failed to process payment")
        
        else:
            st.warning("⚠️ Please select only one payment method")
    
    def _render_payment_status(self):
        """Render Square payment status and polling"""
        status = st.session_state.square_checkout_status
        
        if status and status['status'] == 'processing':
            st.divider()
            st.subheader("⏳ Payment Status")
            
            # Calculate time elapsed
            elapsed_time = time.time() - status.get('start_time', time.time())
            elapsed_minutes = int(elapsed_time // 60)
            elapsed_seconds = int(elapsed_time % 60)
            
            st.info(f"**Payment of ${status['amount']:.2f} pending on Square Terminal**")
            st.write(f"⏱️ Elapsed time: {elapsed_minutes}:{elapsed_seconds:02d}")
            st.write("Waiting for customer to complete payment...")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Check payment status button
                if st.button("🔄 Check Payment Status", key="check_payment_status"):
                    with st.spinner("Checking payment status..."):
                        result = self._check_square_payment_status(status['checkout_id'])
                        
                        if result.get('status') == 'success':
                            payment_status = result.get('payment_status', 'UNKNOWN')
                            
                            if payment_status == 'COMPLETED':
                                st.session_state.square_checkout_status['status'] = 'completed'
                                st.success("✅ Payment completed successfully!")
                                
                                # Update records and credit consignors
                                success = self._mark_as_paid(status['record_ids'], payment_method="square")
                                if success:
                                    st.success("✅ Records updated and consignors credited!")
                                    
                                    # Clear checkout records
                                    st.session_state.checkout_records = []
                                    st.session_state.square_checkout_status = None
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to update records after payment")
                            
                            elif payment_status == 'CANCELED':
                                st.session_state.square_checkout_status = None
                                st.warning("⚠️ Payment was cancelled")
                                st.rerun()
                            
                            else:
                                st.info(f"⏳ Payment status: {payment_status}")
                        else:
                            st.error(f"❌ Error checking status: {result.get('error', 'Unknown error')}")
            
            with col2:
                # NEW: Cancel transaction button
                if st.button("❌ Cancel Transaction", type="secondary", key="cancel_transaction"):
                    with st.spinner("Cancelling transaction..."):
                        result = self._cancel_square_checkout(status['checkout_id'])
                        
                        if result.get('status') == 'success':
                            st.session_state.square_checkout_status = None
                            st.success("✅ Transaction cancelled successfully!")
                            
                            # Optional: Revert record status if you want
                            # For now, just clear the checkout
                            st.session_state.checkout_records = []
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to cancel transaction: {result.get('error', 'Unknown error')}")
            
            with col3:
                # Clear status button (manual override)
                if st.button("🗑️ Clear Status", type="secondary", key="clear_status"):
                    if 'square_checkout_status' in st.session_state:
                        del st.session_state.square_checkout_status
                        st.rerun()
    
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
                    
                    # Filter out already sold items (status_id = 3)
                    available_results = []
                    for record in all_results:
                        status_id = record.get('status_id', 1)
                        
                        # Only include if not sold (status_id != 3)
                        if status_id != 3:
                            available_results.append(record)
                    
                    return available_results
            
            return []
            
        except Exception as e:
            st.error(f"Search error: {e}")
            return []
    
    def _initiate_square_checkout(self, record_ids, total_amount, record_titles):
        """Initiate Square Terminal checkout"""
        try:
            response = requests.post(
                f"{self.api_client.base_url}/api/square/terminal-checkout",
                json={
                    'record_ids': record_ids,
                    'total_amount': total_amount,
                    'record_titles': record_titles[:3]  # Send first 3 titles for note
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'status': 'error', 'error': f'API error: {response.status_code}'}
                
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _check_square_payment_status(self, checkout_id):
        """Check Square payment status"""
        try:
            response = requests.get(
                f"{self.api_client.base_url}/api/square/payment-status/{checkout_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'status': 'error', 'error': f'API error: {response.status_code}'}
                
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _cancel_square_checkout(self, checkout_id):
        """Cancel a Square Terminal checkout"""
        try:
            response = requests.post(
                f"{self.api_client.base_url}/api/square/cancel-checkout/{checkout_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'status': 'error', 'error': f'API error: {response.status_code}'}
                
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def _mark_as_paid(self, record_ids, payment_method="square"):
        """Mark items as paid - update status to sold and credit consignor"""
        if not record_ids:
            st.error("No items to process")
            return False
        
        success_count = 0
        failed_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, record_id in enumerate(record_ids):
            # Get record details
            record = self._get_record_details(record_id)
            if not record:
                failed_count += 1
                continue
            
            status_text.text(f"Processing {i+1}/{len(record_ids)}: {record.get('artist', '')} - {record.get('title', '')}")
            
            # Update record status to sold (status_id = 3)
            updates = {
                'status_id': 3
            }
            
            update_success = self.api_client.update_record(record_id, updates)
            
            if update_success:
                # Credit consignor if applicable
                consignor_id = record.get('consignor_id')
                if consignor_id:
                    store_price = float(record.get('store_price', 0))
                    commission_rate = float(record.get('commission_rate', 0.20))
                    payout = store_price * (1 - commission_rate)
                    
                    # Credit consignor
                    credit_success = self._credit_consignor(consignor_id, payout)
                    if credit_success:
                        success_count += 1
                    else:
                        failed_count += 1
                else:
                    # No consignor (store-owned), still count as success
                    success_count += 1
            else:
                failed_count += 1
            
            progress_bar.progress((i + 1) / len(record_ids))
        
        progress_bar.empty()
        status_text.empty()
        
        if success_count > 0:
            return True
        else:
            st.error(f"❌ Failed to process payment for {failed_count} items")
            return False
    
    def _handle_successful_payment(self, record_ids, total_amount, payment_method):
        """Handle successful payment in demo mode"""
        st.success(f"✅ Demo: Payment of ${total_amount:.2f} successful via {payment_method}")
        
        # Clear checkout records for demo
        st.session_state.checkout_records = []
        st.session_state.square_checkout_status = None
        st.rerun()
    
    def _get_record_details(self, record_id):
        """Get record details via API"""
        try:
            response = requests.get(f"{self.api_client.base_url}/records/{record_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"Error getting record details: {e}")
            return None
    
    def _credit_consignor(self, consignor_id, amount):
        """Credit consignor's store balance"""
        try:
            # Get current balance
            user = self.api_client.get_user(consignor_id)
            if not user:
                return False
            
            current_balance = float(user.get('store_credit_balance', 0))
            new_balance = current_balance + amount
            
            # Update user balance
            success = self.api_client.update_user(consignor_id, {'store_credit_balance': new_balance})
            return success
            
        except Exception as e:
            st.error(f"Error crediting consignor: {e}")
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
    
    def update_user(self, user_id, updates):
        """Update user via API"""
        try:
            response = requests.put(
                f"{self.base_url}/users/{user_id}",
                json=updates
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"API Error updating user: {e}")
            return False