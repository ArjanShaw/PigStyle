import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

class ConsignmentTab:
    def __init__(self):
        pass
    
    def render(self):
        user = st.session_state.get('user', {})
        user_role = user.get('role', 'consignor')
        user_id = user.get('id')
        
        if user_role == 'admin':
            self._render_admin_consignment()
        else:
            self._render_consignor_consignment(user_id)
    
    def _render_consignor_consignment(self, user_id):
        """Render consignment tab for individual users to check pickups/returns and request payment"""
        st.header("🤝 My Consignment")
        
        if not user_id:
            st.error("Unable to identify user. Please contact administrator.")
            return
        
        # Get user info
        user = st.session_state.db_manager.get_user_by_id(user_id)
        if user is None:
            st.error("User profile not found. Please contact administrator.")
            return
        
        st.write(f"**User:** {user['full_name'] or user['username']}")
        
        # Tab layout for user functions
        tab1, tab2 = st.tabs([
            "💰 Request Payment",
            "📦 Pickup & Returns"
        ])
        
        with tab1:
            self._render_consignor_payment_requests(user_id, user)
        
        with tab2:
            self._render_consignor_pickup_returns(user_id, user)
    
    def _render_admin_consignment(self):
        """Render consignment tab for admin to manage all users"""
        st.header("🤝 Consignment Management")
        
        # Tab layout for admin functions
        tab1, tab2 = st.tabs([
            "💰 Payment Processing", 
            "📦 Pickup & Returns"
        ])
        
        with tab1:
            self._render_admin_payment_processing()
        
        with tab2:
            self._render_admin_pickup_returns()
    
    def _render_consignor_payment_requests(self, user_id, user):
        """Render payment request section for users"""
        st.subheader("💰 Request Payment")
        
        # Get payment-ready records for this user
        payment_records = st.session_state.db_manager.get_user_consignment_records_ready_for_payment(user_id)
        
        if len(payment_records) == 0:
            st.info("No records ready for payment at this time.")
            return
        
        # Display payment summary
        total_sales = payment_records['store_price'].sum()
        commission_rate = payment_records.iloc[0]['commission_rate'] if len(payment_records) > 0 else 0
        store_commission = total_sales * commission_rate
        user_payout = total_sales - store_commission
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Records Ready", len(payment_records))
        with col2:
            st.metric("Total Sales", f"${total_sales:.2f}")
        with col3:
            st.metric("Store Commission", f"${store_commission:.2f}")
        with col4:
            st.metric("Your Payout", f"${user_payout:.2f}")
        
        # Display records table
        st.subheader("Records Ready for Payment")
        display_df = payment_records[['id', 'artist', 'title', 'store_price', 'date_sold']].copy()
        display_df['date_sold'] = pd.to_datetime(display_df['date_sold']).dt.date
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Payment request action
        if st.button("💳 Request Payment", type="primary", use_container_width=True):
            success = self._request_payment(payment_records, user_id)
            if success:
                st.success("Payment request submitted! The store will process your payment soon.")
                st.rerun()
    
    def _render_consignor_pickup_returns(self, user_id, user):
        """Render pickup and returns section for users"""
        st.subheader("📦 Pickup & Returns")
        
        # Get pickup-ready records for this user
        pickup_records = st.session_state.db_manager.get_user_consignment_records_ready_for_pickup(user_id)
        
        if len(pickup_records) == 0:
            st.info("No records ready for pickup at this time.")
            return
        
        # Display pickup summary
        st.metric("Records Ready for Pickup", len(pickup_records))
        
        # Display records table
        st.subheader("Records Ready for Pickup")
        display_df = pickup_records[['id', 'artist', 'title', 'store_price', 'date_returned']].copy()
        display_df['date_returned'] = pd.to_datetime(display_df['date_returned']).dt.date
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Pickup confirmation action
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Confirm Pickup", type="primary", use_container_width=True):
                success = self._confirm_pickup(pickup_records)
                if success:
                    st.success("Pickup confirmed! Please arrange to pick up your records.")
                    st.rerun()
        
        with col2:
            if st.button("📋 Generate Pickup List", use_container_width=True):
                self._generate_pickup_list(pickup_records)
    
    def _render_admin_payment_processing(self):
        """Render payment processing section for admin"""
        st.subheader("💰 User Payment Processing")
        
        # User selection
        user_id = self._render_user_selector("payment")
        if not user_id:
            st.info("Please select a user to process payments")
            return
        
        # Get payment-ready records for this user
        payment_records = st.session_state.db_manager.get_consignment_records_ready_for_payment(user_id)
        
        if len(payment_records) == 0:
            st.info("No records ready for payment for this user")
            return
        
        # Display payment summary
        total_sales = payment_records['store_price'].sum()
        commission_rate = payment_records.iloc[0]['commission_rate'] if len(payment_records) > 0 else 0
        store_commission = total_sales * commission_rate
        user_payout = total_sales - store_commission
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", len(payment_records))
        with col2:
            st.metric("Total Sales", f"${total_sales:.2f}")
        with col3:
            st.metric("Store Commission", f"${store_commission:.2f}")
        with col4:
            st.metric("User Payout", f"${user_payout:.2f}")
        
        # Display records table
        st.subheader("Records Ready for Payment")
        display_df = payment_records[['id', 'artist', 'title', 'store_price', 'date_sold']].copy()
        display_df['date_sold'] = pd.to_datetime(display_df['date_sold']).dt.date
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Payment actions
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💳 Process Payment", type="primary", use_container_width=True):
                self._process_payment(payment_records)
        with col2:
            if st.button("🧾 Generate Payment Report", use_container_width=True):
                self._generate_payment_report(payment_records, user_payout, store_commission)
    
    def _render_admin_pickup_returns(self):
        """Render pickup and returns section for admin"""
        st.subheader("📦 User Pickup & Returns")
        
        # User selection
        user_id = self._render_user_selector("pickup")
        if not user_id:
            st.info("Please select a user to process pickups")
            return
        
        # Get pickup-ready records for this user
        pickup_records = st.session_state.db_manager.get_consignment_records_ready_for_pickup(user_id)
        
        if len(pickup_records) == 0:
            st.info("No records ready for pickup for this user")
            return
        
        # Display pickup summary
        st.metric("Records Ready for Pickup", len(pickup_records))
        
        # Display records table
        st.subheader("Records Ready for Pickup")
        display_df = pickup_records[['id', 'artist', 'title', 'store_price', 'date_returned']].copy()
        display_df['date_returned'] = pd.to_datetime(display_df['date_returned']).dt.date
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Pickup actions
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 Process Pickup", type="primary", use_container_width=True):
                self._process_pickup(pickup_records)
        with col2:
            if st.button("📋 Generate Pickup List", use_container_width=True):
                self._generate_pickup_list(pickup_records)
        
        # Auto-return tools for admin only
        st.subheader("Auto-Return Tools")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Mark Records for Return", use_container_width=True):
                updated_count = st.session_state.db_manager.mark_records_for_return()
                if updated_count > 0:
                    st.success(f"✅ Marked {updated_count} records as ready for pickup!")
                    st.rerun()
                else:
                    st.info("No records needed to be marked for return")
        
        with col2:
            if st.button("🏪 Convert Abandoned Records", use_container_width=True):
                updated_count = st.session_state.db_manager.mark_abandoned_records_as_store_owned()
                if updated_count > 0:
                    st.success(f"✅ Converted {updated_count} abandoned records to store property!")
                    st.rerun()
                else:
                    st.info("No abandoned records found")
    
    def _render_user_selector(self, context):
        """Render user selector dropdown"""
        users = st.session_state.db_manager.get_all_users()
        
        if len(users) == 0:
            st.error("No users found. Please add users first.")
            return None
        
        # Create display names for dropdown
        user_options = ["Select User..."] + [
            f"{row['username']} ({row['full_name'] or 'No name'})" for _, row in users.iterrows()
        ]
        
        selected_user = st.selectbox(
            "Select User:",
            options=user_options,
            key=f"user_selector_{context}"
        )
        
        if selected_user == "Select User...":
            return None
        
        # Extract user ID from selection
        username = selected_user.split(" (")[0]
        user = users[users['username'] == username].iloc[0]
        return user['id']
    
    def _request_payment(self, payment_records, user_id):
        """Request payment for selected records (user action)"""
        try:
            # For users, this just marks them as payment requested
            # Admin will actually process the payment later
            for _, record in payment_records.iterrows():
                st.session_state.db_manager.update_record(record['id'], {
                    'payment_requested': datetime.now().date()
                })
            
            return True
            
        except Exception as e:
            st.error(f"❌ Error requesting payment: {e}")
            return False
    
    def _confirm_pickup(self, pickup_records):
        """Confirm pickup for selected records (user action)"""
        try:
            # For users, this confirms they will pick up
            for _, record in pickup_records.iterrows():
                st.session_state.db_manager.update_record(record['id'], {
                    'pickup_confirmed': datetime.now().date()
                })
            
            return True
            
        except Exception as e:
            st.error(f"❌ Error confirming pickup: {e}")
            return False
    
    def _process_payment(self, payment_records):
        """Process payment for selected records (admin action)"""
        try:
            # Mark records as paid
            for _, record in payment_records.iterrows():
                st.session_state.db_manager.update_record(record['id'], {
                    'date_paid': datetime.now().date()
                })
            
            st.success(f"✅ Payment processed for {len(payment_records)} records!")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error processing payment: {e}")
    
    def _process_pickup(self, pickup_records):
        """Process pickup for selected records (admin action)"""
        try:
            # Mark records as picked up
            for _, record in pickup_records.iterrows():
                st.session_state.db_manager.update_record(record['id'], {
                    'date_picked_up': datetime.now().date()
                })
            
            st.success(f"✅ Pickup processed for {len(pickup_records)} records!")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error processing pickup: {e}")
    
    def _generate_payment_report(self, payment_records, user_payout, store_commission):
        """Generate payment report CSV"""
        try:
            # Create detailed report
            report_data = []
            for _, record in payment_records.iterrows():
                report_data.append({
                    'Record ID': record['id'],
                    'Artist': record['artist'],
                    'Title': record['title'],
                    'Sale Price': record['store_price'],
                    'Date Sold': record['date_sold'],
                    'Commission Rate': f"{record['commission_rate']*100}%"
                })
            
            # Add summary row
            report_data.append({
                'Record ID': 'SUMMARY',
                'Artist': '',
                'Title': '',
                'Sale Price': f"Total: ${payment_records['store_price'].sum():.2f}",
                'Date Sold': f"Payout: ${user_payout:.2f}",
                'Commission Rate': f"Commission: ${store_commission:.2f}"
            })
            
            df = pd.DataFrame(report_data)
            csv_data = df.to_csv(index=False)
            
            # Create download button
            consignor_name = payment_records.iloc[0]['consignor_name'] if len(payment_records) > 0 else "Unknown"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"payment_report_{consignor_name}_{timestamp}.csv"
            
            st.download_button(
                label="📊 Download Payment Report",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"❌ Error generating report: {e}")
    
    def _generate_pickup_list(self, pickup_records):
        """Generate pickup list CSV"""
        try:
            df = pd.DataFrame({
                'Record ID': pickup_records['id'],
                'Artist': pickup_records['artist'],
                'Title': pickup_records['title'],
                'Store Price': pickup_records['store_price'],
                'Date Returned': pickup_records['date_returned']
            })
            
            csv_data = df.to_csv(index=False)
            
            # Create download button
            consignor_name = pickup_records.iloc[0]['consignor_name'] if len(pickup_records) > 0 else "Unknown"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pickup_list_{consignor_name}_{timestamp}.csv"
            
            st.download_button(
                label="📋 Download Pickup List",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                use_container_width=True
            )
            
        except Exception as e:
            st.error(f"❌ Error generating pickup list: {e}")