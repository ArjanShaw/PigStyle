import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests

class CommissionCalculator:
    """Simplified capacity-based commission calculator"""
    
    def __init__(self, api_client):
        self.api_client = api_client
    
    def get_current_commission_rate(self):
        """Get commission rate based ONLY on store capacity"""
        # Get required configuration values - will throw error if any missing
        max_capacity = self._get_config_value('COMMISSION_MAX_CAPACITY')
        min_capacity = self._get_config_value('COMMISSION_MIN_CAPACITY')
        max_rate = self._get_config_value('COMMISSION_MAX_RATE')
        min_rate = self._get_config_value('COMMISSION_MIN_RATE')
        
        # Get current store fill percentage
        store_fill_info = self._get_store_fill_info()
        fill_percentage = store_fill_info['fill_percentage']
        
        # Calculate commission rate based on capacity
        if fill_percentage <= min_capacity:
            return min_rate / 100.0  # Convert from percentage to decimal
        elif fill_percentage >= max_capacity:
            return max_rate / 100.0  # Convert from percentage to decimal
        else:
            # Linear interpolation between min and max rates
            ratio = (fill_percentage - min_capacity) / (max_capacity - min_capacity)
            commission_rate = min_rate + (max_rate - min_rate) * ratio
            return commission_rate / 100.0  # Convert from percentage to decimal
    
    def _get_config_value(self, config_key):
        """Get config value via API - throws error if not found"""
        value = self.api_client.get_config_value(config_key, None)
        if value is None:
            raise ValueError(f"Required configuration key '{config_key}' not found")
        try:
            return float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Configuration key '{config_key}' has invalid value: '{value}'")
    
    def _get_store_fill_info(self):
        """Get store fill information"""
        store_capacity = self._get_config_value('STORE_CAPACITY')
        
        # Get all records via API
        response = requests.get(f"{self.api_client.base_url}/records?limit=1000")
        if response.status_code == 200:
            data = response.json()
            total_inventory = len(data.get('records', []))
        else:
            total_inventory = 0
        
        fill_fraction = total_inventory / store_capacity if store_capacity > 0 else 0
        fill_percentage = fill_fraction * 100
        
        return {
            'total_inventory': total_inventory,
            'store_capacity': store_capacity,
            'fill_fraction': fill_fraction,
            'fill_percentage': fill_percentage
        }

class ConsignmentTab:
    def __init__(self):
        # Initialize API client
        self.api_client = APIClient()
        self.commission_calculator = CommissionCalculator(self.api_client)
    
    def render(self):
        st.title("🎵 Consignment Management")
        
        user = st.session_state.get('user', {})
        user_id = user.get('id')
        user_role = user.get('role', 'consignor')
        
        if not user_id:
            st.warning("Please log in to view consignment information.")
            return
        
        # Show current commission rate
        try:
            commission_rate = self.commission_calculator.get_current_commission_rate()
            store_fill_info = self.commission_calculator._get_store_fill_info()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"Current commission rate: **{commission_rate*100:.1f}%**")
            with col2:
                st.info(f"Store fill: **{store_fill_info['fill_percentage']:.1f}%**")
            with col3:
                st.info(f"Store capacity: **{store_fill_info['store_capacity']}**")
        except ValueError as e:
            st.error(f"Configuration error: {e}")
            return
        
        # Tabs for different consignment views
        tab1, tab2, tab3, tab4 = st.tabs([
            "📦 My Consignments", 
            "💰 Payment Ready", 
            "📤 Pickup Ready",
            "🏪 Store Drop-off"
        ])
        
        with tab1:
            self._render_my_consignments(user_id, user_role)
        
        with tab2:
            self._render_payment_ready(user_id, user_role)
        
        with tab3:
            self._render_pickup_ready(user_id, user_role)
        
        with tab4:
            self._render_store_dropoff(user_id, user_role)

    def _render_my_consignments(self, user_id, user_role):
        """Render user's consignment records"""
        st.subheader("My Consignment Records")
        
        # Get user's records or all records if admin
        if user_role == 'admin':
            response = requests.get(f"{self.api_client.base_url}/records?limit=1000")
        else:
            response = requests.get(f"{self.api_client.base_url}/records/user/{user_id}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                records = data.get('records', [])
            else:
                records = []
        else:
            records = []
        
        if not records:
            st.info("No consignment records found.")
            return
        
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(records)
        
        # Calculate totals
        total_records = len(df)
        unsold_records = df[df['date_sold'].isna()].shape[0]
        sold_records = df[~df['date_sold'].isna()].shape[0]
        
        # Display summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Records", total_records)
        with col2:
            st.metric("Unsold", unsold_records)
        with col3:
            st.metric("Sold", sold_records)
        
        # Show detailed records
        st.write("### Detailed Records")
        
        for idx, record in df.iterrows():
            expander_title = f"{record['artist']} - {record['title']} (${record['store_price']:.2f})"
            if user_role == 'admin' and record.get('consignor_id'):
                user_info = self.api_client.get_user(record['consignor_id'])
                if user_info:
                    expander_title += f" 👤 {user_info.get('username', f'ID: {record['consignor_id']}')}"
            
            with st.expander(expander_title):
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    if record.get('image_url'):
                        st.image(record['image_url'], width=100)
                
                with col2:
                    st.write(f"**Catalog:** {record.get('catalog_number', 'N/A')}")
                    st.write(f"**Genre:** {record.get('genre_name', record.get('genre', 'Unknown'))}")
                    st.write(f"**Condition:** {record.get('condition', 'N/A')}")
                    st.write(f"**Price:** ${record['store_price']:.2f}")
                    
                    # Show consignor info for admin
                    if user_role == 'admin' and record.get('consignor_id'):
                        user_info = self.api_client.get_user(record['consignor_id'])
                        if user_info:
                            st.write(f"**Consignor:** {user_info.get('username')}")
                    
                    # Show current commission rate (same for all records)
                    try:
                        commission_rate = self.commission_calculator.get_current_commission_rate()
                        st.write(f"**Commission Rate:** {commission_rate*100:.1f}%")
                    except ValueError as e:
                        st.write(f"**Commission Rate:** Error: {e}")
                    
                    # Show dates
                    if record.get('consignment_start_date'):
                        st.write(f"**Consigned:** {record['consignment_start_date']}")
                    
                    if record.get('date_sold'):
                        st.success(f"✅ Sold on: {record['date_sold']}")
                        if record.get('date_paid'):
                            st.success(f"💰 Paid on: {record['date_paid']}")
                        else:
                            st.warning("⏳ Payment pending")
                    
                    if record.get('date_returned'):
                        st.info(f"📦 Returned on: {record['date_returned']}")
                        if record.get('date_picked_up'):
                            st.info(f"✅ Picked up on: {record['date_picked_up']}")
                        else:
                            st.warning("📦 Ready for pickup")

    def _render_payment_ready(self, user_id, user_role):
        """Render records ready for payment"""
        st.subheader("Payment Ready Records")
        
        # Get payment ready records
        if user_role == 'admin':
            response = requests.get(f"{self.api_client.base_url}/consignment/payment-ready")
        else:
            response = requests.get(f"{self.api_client.base_url}/consignment/payment-ready?user_id={user_id}")
        
        if response.status_code == 200:
            data = response.json()
            records = data.get('records', [])
            
            if not records:
                st.info("No records ready for payment.")
                return
            
            df = pd.DataFrame(records)
            
            # Get current commission rate
            try:
                commission_rate = self.commission_calculator.get_current_commission_rate()
            except ValueError as e:
                st.error(f"Cannot calculate payments: {e}")
                return
            
            # Calculate totals
            total_sales = df['store_price'].sum()
            total_commission = total_sales * commission_rate
            total_payout = total_sales - total_commission
            
            # Group by consignor for admin view
            if user_role == 'admin':
                consignor_summary = {}
                for _, record in df.iterrows():
                    consignor_id = record.get('consignor_id')
                    if consignor_id:
                        user_info = self.api_client.get_user(consignor_id)
                        consignor_name = user_info.get('username', f"ID: {consignor_id}") if user_info else f"ID: {consignor_id}"
                        
                        if consignor_id not in consignor_summary:
                            consignor_summary[consignor_id] = {
                                'name': consignor_name,
                                'total_sales': 0,
                                'total_commission': 0,
                                'total_payout': 0,
                                'records': 0
                            }
                        
                        price = float(record['store_price'])
                        commission = price * commission_rate
                        payout = price - commission
                        
                        consignor_summary[consignor_id]['total_sales'] += price
                        consignor_summary[consignor_id]['total_commission'] += commission
                        consignor_summary[consignor_id]['total_payout'] += payout
                        consignor_summary[consignor_id]['records'] += 1
            
            # Display summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Records", len(df))
            with col2:
                st.metric("Total Sales", f"${total_sales:.2f}")
            with col3:
                st.metric("Total Payout", f"${total_payout:.2f}")
            
            st.write(f"**Current Commission Rate:** {commission_rate*100:.1f}%")
            
            # Show consignor breakdown for admin
            if user_role == 'admin' and consignor_summary:
                st.write("**Consignor Breakdown:**")
                for consignor_id, summary in consignor_summary.items():
                    col1, col2, col3, col4 = st.columns([2, 1, 2, 2])
                    with col1:
                        st.write(f"**{summary['name']}**")
                    with col2:
                        st.write(f"{summary['records']} items")
                    with col3:
                        st.write(f"Sales: ${summary['total_sales']:.2f}")
                    with col4:
                        st.write(f"Payout: ${summary['total_payout']:.2f}")
            
            # Show records
            st.write("### Records awaiting payment")
            for idx, record in df.iterrows():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                
                with col1:
                    st.write(f"**{record['artist']} - {record['title']}**")
                    st.write(f"Sold: {record['date_sold']}")
                    if user_role == 'admin' and record.get('consignor_id'):
                        user_info = self.api_client.get_user(record['consignor_id'])
                        if user_info:
                            st.write(f"Consignor: {user_info.get('username')}")
                
                with col2:
                    price = float(record['store_price'])
                    commission = price * commission_rate
                    payout = price - commission
                    
                    st.write(f"Price: ${price:.2f}")
                    st.write(f"Commission: ${commission:.2f} ({commission_rate*100:.1f}%)")
                    st.write(f"**Payout: ${payout:.2f}**")
                
                with col4:
                    if user_role == 'admin':
                        if st.button("✅ Mark Paid", key=f"pay_{record['id']}"):
                            success = self._mark_as_paid(record['id'])
                            if success:
                                st.success(f"Record {record['id']} marked as paid")
                                st.rerun()
            
            # Bulk payment button for admin
            if user_role == 'admin' and len(df) > 0:
                st.divider()
                if st.button("💳 Process All Payments", type="primary"):
                    success = self._process_all_payments(df['id'].tolist())
                    if success:
                        st.success(f"Processed payments for {len(df)} records")
                        st.rerun()
        else:
            st.error(f"Error fetching payment ready records: {response.status_code}")

    def _render_pickup_ready(self, user_id, user_role):
        """Render records ready for pickup"""
        st.subheader("Pickup Ready Records")
        
        # Get pickup ready records
        if user_role == 'admin':
            response = requests.get(f"{self.api_client.base_url}/consignment/pickup-ready")
        else:
            response = requests.get(f"{self.api_client.base_url}/consignment/pickup-ready?user_id={user_id}")
        
        if response.status_code == 200:
            data = response.json()
            records = data.get('records', [])
            
            if not records:
                st.info("No records ready for pickup.")
                return
            
            df = pd.DataFrame(records)
            
            # Display summary
            st.metric("Records Ready for Pickup", len(df))
            
            # Show records
            for idx, record in df.iterrows():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                
                with col1:
                    st.write(f"**{record['artist']} - {record['title']}**")
                    st.write(f"Returned: {record['date_returned']}")
                    if user_role == 'admin' and record.get('consignor_id'):
                        user_info = self.api_client.get_user(record['consignor_id'])
                        if user_info:
                            st.write(f"Consignor: {user_info.get('username')}")
                
                with col2:
                    st.write(f"Price: ${record['store_price']:.2f}")
                    st.write(f"Status: Returned, awaiting pickup")
                
                with col4:
                    if st.button("✅ Mark Picked Up", key=f"pickup_{record['id']}"):
                        success = self._mark_as_picked_up(record['id'])
                        if success:
                            st.success(f"Record {record['id']} marked as picked up")
                            st.rerun()
        else:
            st.error(f"Error fetching pickup ready records: {response.status_code}")

    def _render_store_dropoff(self, user_id, user_role):
        """Render store drop-off functionality"""
        st.subheader("Store Drop-off")
        
        if user_role == 'admin':
            st.info("Admin view: All records without barcodes")
            response = requests.get(f"{self.api_client.base_url}/consignment/dropoff-ready")
        else:
            st.info("Your records that need barcodes for store drop-off")
            response = requests.get(f"{self.api_client.base_url}/consignment/dropoff-ready?user_id={user_id}")
        
        if response.status_code == 200:
            data = response.json()
            records = data.get('records', [])
            
            if not records:
                st.success("🎉 All your records have barcodes assigned!")
                return
            
            df = pd.DataFrame(records)
            
            st.metric("Records Needing Barcodes", len(df))
            st.info("These records need barcodes assigned before they can be placed in the store.")
            
            # Show records
            for idx, record in df.iterrows():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.write(f"**{record['artist']} - {record['title']}**")
                    st.write(f"Added: {record.get('created_at', 'Unknown')}")
                    if user_role == 'admin' and record.get('consignor_id'):
                        user_info = self.api_client.get_user(record['consignor_id'])
                        if user_info:
                            st.write(f"Consignor: {user_info.get('username')}")
                
                with col2:
                    st.write(f"Price: ${record['store_price']:.2f}")
                
                with col3:
                    if user_role == 'admin':
                        if st.button("🔢 Assign Barcode", key=f"barcode_{record['id']}"):
                            success = self._assign_single_barcode(record['id'])
                            if success:
                                st.success(f"Barcode assigned to record {record['id']}")
                                st.rerun()
            
            # Bulk assignment for admin
            if user_role == 'admin' and len(df) > 0:
                st.divider()
                if st.button("🔢 Assign Barcodes to All", type="primary"):
                    record_ids = df['id'].tolist()
                    success = self._assign_barcodes_bulk(record_ids)
                    if success:
                        st.success(f"Assigned barcodes to {len(record_ids)} records")
                        st.rerun()
        else:
            st.error(f"Error fetching drop-off records: {response.status_code}")

    def _mark_as_paid(self, record_id):
        """Mark a record as paid"""
        try:
            today = datetime.now().date().isoformat()
            updates = {'date_paid': today}
            return self.api_client.update_record(record_id, updates)
        except Exception as e:
            st.error(f"Error marking as paid: {e}")
            return False

    def _process_all_payments(self, record_ids):
        """Process payments for multiple records"""
        try:
            return self.api_client.process_checkout_payment(record_ids)
        except Exception as e:
            st.error(f"Error processing payments: {e}")
            return False

    def _mark_as_picked_up(self, record_id):
        """Mark a record as picked up"""
        try:
            today = datetime.now().date().isoformat()
            updates = {'date_picked_up': today}
            return self.api_client.update_record(record_id, updates)
        except Exception as e:
            st.error(f"Error marking as picked up: {e}")
            return False

    def _assign_single_barcode(self, record_id):
        """Assign a barcode to a single record"""
        try:
            response = requests.post(
                f"{self.api_client.base_url}/barcodes/assign",
                json={'record_ids': [record_id]}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error assigning barcode: {e}")
            return False

    def _assign_barcodes_bulk(self, record_ids):
        """Assign barcodes to multiple records"""
        try:
            response = requests.post(
                f"{self.api_client.base_url}/barcodes/assign",
                json={'record_ids': record_ids}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error assigning barcodes: {e}")
            return False

class APIClient:
    """API client for consignment operations"""
    
    def __init__(self, base_url="https://arjanshaw.pythonanywhere.com"):
        self.base_url = base_url
    
    def get_records_by_user(self, user_id):
        """Get records for specific user via API"""
        try:
            response = requests.get(f"{self.base_url}/records/user/{user_id}")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('records', [])
            return []
        except Exception as e:
            st.error(f"API Error getting user records: {e}")
            return []
    
    def get_config_value(self, config_key, default=None):
        """Get config value via API"""
        try:
            response = requests.get(f"{self.base_url}/config/{config_key}")
            if response.status_code == 200:
                data = response.json()
                return data.get('config_value', default)
            return default
        except Exception as e:
            st.error(f"API Error getting config: {e}")
            return default
    
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
            response = requests.post(
                f"{self.base_url}/checkout/process-payment",
                json={'record_ids': record_ids}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error processing payment: {e}")
            return False