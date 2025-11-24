import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

class ConsignmentTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("🤝 Consignment Services")
        
        # Initialize session state for selected consignor
        if 'selected_consignor_id' not in st.session_state:
            st.session_state.selected_consignor_id = None
        if 'selected_session_id' not in st.session_state:
            st.session_state.selected_session_id = None
        
        # Tab layout for different consignment functions
        tab1, tab2, tab3 = st.tabs([
            "💰 Payment Processing",
            "📦 Pickup & Returns", 
            "👥 Consignor Management"
        ])
        
        with tab1:
            self._render_payment_processing()
        
        with tab2:
            self._render_pickup_returns()
        
        with tab3:
            self._render_consignor_management()
    
    def _render_payment_processing(self):
        """Render payment processing section"""
        st.subheader("💰 Consignor Payment Processing")
        
        # Consignor selection
        consignor_id = self._render_consignor_selector("payment")
        if not consignor_id:
            st.info("Please select a consignor to process payments")
            return
        
        # Get payment-ready records for this consignor
        payment_records = st.session_state.db_manager.get_consignment_records_ready_for_payment(consignor_id)
        
        if len(payment_records) == 0:
            st.info("No records ready for payment for this consignor")
            return
        
        # Display payment summary
        total_sales = payment_records['store_price'].sum()
        commission_rate = payment_records.iloc[0]['commission_rate'] if len(payment_records) > 0 else 0
        store_commission = total_sales * commission_rate
        consignor_payout = total_sales - store_commission
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Records", len(payment_records))
        with col2:
            st.metric("Total Sales", f"${total_sales:.2f}")
        with col3:
            st.metric("Store Commission", f"${store_commission:.2f}")
        with col4:
            st.metric("Consignor Payout", f"${consignor_payout:.2f}")
        
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
                self._generate_payment_report(payment_records, consignor_payout, store_commission)
    
    def _render_pickup_returns(self):
        """Render pickup and returns section"""
        st.subheader("📦 Consignor Pickup & Returns")
        
        # Consignor selection
        consignor_id = self._render_consignor_selector("pickup")
        if not consignor_id:
            st.info("Please select a consignor to process pickups")
            return
        
        # Get pickup-ready records for this consignor
        pickup_records = st.session_state.db_manager.get_consignment_records_ready_for_pickup(consignor_id)
        
        if len(pickup_records) == 0:
            st.info("No records ready for pickup for this consignor")
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
        
        # Auto-return tools
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
    
    def _render_consignor_management(self):
        """Render consignor management section"""
        st.subheader("👥 Consignor Management")
        
        # Add new consignor
        with st.expander("➕ Add New Consignor", expanded=False):
            self._render_add_consignor_form()
        
        # Add new consignment session
        with st.expander("📅 Add New Consignment Session", expanded=False):
            self._render_add_session_form()
        
        # Consignor list
        st.subheader("Consignors")
        consignors = st.session_state.db_manager.get_all_consignors()
        
        if len(consignors) == 0:
            st.info("No consignors found. Add a new consignor to get started.")
            return
        
        # Display consignors with their stats
        for _, consignor in consignors.iterrows():
            with st.expander(f"👤 {consignor['name']}", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Email:** {consignor['email'] or 'N/A'}")
                    st.write(f"**Phone:** {consignor['phone'] or 'N/A'}")
                with col2:
                    st.write(f"**Address:** {consignor['address'] or 'N/A'}")
                with col3:
                    st.write(f"**Notes:** {consignor['notes'] or 'N/A'}")
                
                # Show consignor sessions
                sessions = st.session_state.db_manager.get_sessions_by_consignor(consignor['id'])
                if len(sessions) > 0:
                    st.write("**Sessions:**")
                    for _, session in sessions.iterrows():
                        st.write(f"- {session['session_date']}: {session['commission_rate']*100}% commission, {session['store_return_days']} days")
    
    def _render_consignor_selector(self, context):
        """Render consignor selector dropdown"""
        consignors = st.session_state.db_manager.get_all_consignors()
        
        if len(consignors) == 0:
            st.error("No consignors found. Please add consignors first.")
            return None
        
        # Create display names for dropdown
        consignor_options = ["Select Consignor..."] + [
            f"{row['name']} (ID: {row['id']})" for _, row in consignors.iterrows()
        ]
        
        selected_consignor = st.selectbox(
            "Select Consignor:",
            options=consignor_options,
            key=f"consignor_selector_{context}"
        )
        
        if selected_consignor == "Select Consignor...":
            return None
        
        # Extract consignor ID from selection
        consignor_id = int(selected_consignor.split("(ID: ")[1].rstrip(")"))
        return consignor_id
    
    def _render_add_consignor_form(self):
        """Render form to add new consignor"""
        with st.form("add_consignor_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Name *", placeholder="Consignor full name")
                email = st.text_input("Email", placeholder="email@example.com")
                phone = st.text_input("Phone", placeholder="(555) 123-4567")
            with col2:
                address = st.text_area("Address", placeholder="Street address")
                notes = st.text_area("Notes", placeholder="Additional notes")
            
            if st.form_submit_button("Add Consignor", use_container_width=True):
                if not name:
                    st.error("Name is required")
                    return
                
                consignor_id = st.session_state.db_manager.add_consignor(
                    name=name,
                    email=email or None,
                    phone=phone or None,
                    address=address or None,
                    notes=notes or None
                )
                
                if consignor_id:
                    st.success(f"✅ Consignor '{name}' added successfully!")
                    st.rerun()
    
    def _render_add_session_form(self):
        """Render form to add new consignment session"""
        consignors = st.session_state.db_manager.get_all_consignors()
        
        if len(consignors) == 0:
            st.info("Please add consignors first before creating sessions")
            return
        
        with st.form("add_session_form"):
            col1, col2 = st.columns(2)
            with col1:
                consignor_id = st.selectbox(
                    "Consignor *",
                    options=consignors['id'].tolist(),
                    format_func=lambda x: consignors[consignors['id'] == x]['name'].iloc[0]
                )
                session_date = st.date_input("Session Date", value=datetime.now().date())
                commission_rate = st.number_input(
                    "Commission Rate *",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(st.session_state.db_manager.get_config_value('DEFAULT_COMMISSION_RATE', '0.50')),
                    step=0.05,
                    format="%.2f"
                )
            with col2:
                store_return_days = st.number_input(
                    "Store Return Days *",
                    min_value=1,
                    max_value=365,
                    value=int(st.session_state.db_manager.get_config_value('DEFAULT_STORE_RETURN_DAYS', '90')),
                    step=1
                )
                session_notes = st.text_area("Session Notes", placeholder="Special terms, collection type, etc.")
            
            if st.form_submit_button("Add Consignment Session", use_container_width=True):
                session_id = st.session_state.db_manager.add_consignment_session(
                    consignor_id=consignor_id,
                    session_date=session_date,
                    commission_rate=commission_rate,
                    store_return_days=store_return_days,
                    session_notes=session_notes or None
                )
                
                if session_id:
                    consignor_name = consignors[consignors['id'] == consignor_id]['name'].iloc[0]
                    st.success(f"✅ Consignment session for '{consignor_name}' added successfully!")
                    st.rerun()
    
    def _process_payment(self, payment_records):
        """Process payment for selected records"""
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
        """Process pickup for selected records"""
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
    
    def _generate_payment_report(self, payment_records, consignor_payout, store_commission):
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
                'Date Sold': f"Payout: ${consignor_payout:.2f}",
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