import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
from handlers.commission_calculator import CommissionCalculator
from handlers.pricing_validator import PricingValidator
from handlers.email_service import EmailService

class ConsignmentTab:
    def __init__(self):
        self.commission_calculator = CommissionCalculator(st.session_state.db_manager)
        self.pricing_validator = PricingValidator(st.session_state.db_manager)
        self.email_service = EmailService(st.session_state.db_manager)
    
    def render(self):
        user = st.session_state.get('user', {})
        user_role = user.get('role', 'consignor')
        user_id = user.get('id')
        
        st.header("🤝 Consignment Management")
        
        if user_role == 'admin':
            self._render_admin_view()
        else:
            self._render_consignor_view(user_id)
    
    def _render_admin_view(self):
        """Render consignment management for admin"""
        
        # User selection at the top
        st.subheader("👤 Select User")
        user_id = self._render_user_selector("admin")
        
        if user_id:
            # Show user's consignment stats
            user_stats = self._get_user_consignment_stats(user_id)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Active Items", user_stats['active_count'])
            with col2:
                st.metric("Ready for Payment", user_stats['payment_ready_count'])
            with col3:
                st.metric("Ready for Pickup", user_stats['pickup_ready_count'])
        
        # Show merged consignment table
        st.divider()
        st.subheader("📋 All Consignment Records")
        self._render_merged_consignment_table(user_id if user_id else None)
    
    def _render_consignor_view(self, user_id):
        """Render consignment management for consignor"""
        if not user_id:
            st.error("Unable to identify user. Please contact administrator.")
            return
        
        # Get user info
        user = st.session_state.db_manager.get_user_by_id(user_id)
        if user is None or user.empty:
            st.error("User profile not found. Please contact administrator.")
            return
        
        # Show consignor dashboard WITHOUT commission rate and store credit
        user_stats = self._get_user_consignment_stats(user_id)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Active Items", user_stats['active_count'])
        
        with col2:
            st.metric("Ready for Payment", user_stats['payment_ready_count'])
        
        with col3:
            st.metric("Ready for Pickup", user_stats['pickup_ready_count'])
        
        # REMOVED: Store credit payout option section
        
        # Show merged consignment table
        st.divider()
        st.subheader("📋 Your Consignment Records")
        self._render_merged_consignment_table(user_id)
    
    def _render_merged_consignment_table(self, user_id=None):
        """Render merged consignment table with all statuses"""
        try:
            # Get all records for the user
            records_df = st.session_state.db_manager.get_all_records()
            
            if records_df.empty:
                st.info("No consignment records found.")
                return
            
            # Filter by user if specified
            if user_id:
                user_records = records_df[records_df['consignor_id'] == user_id]
            else:
                user_records = records_df[records_df['consignor_id'].notna()]
            
            if user_records.empty:
                st.info("No consignment records found.")
                return
            
            # Determine status for each record
            status_data = []
            for _, record in user_records.iterrows():
                record_id = record.get('id')
                artist = record.get('artist', '')
                title = record.get('title', '')
                store_price = record.get('store_price', 0)
                created_at = record.get('created_at', '')
                date_sold = record.get('date_sold', '')
                date_returned = record.get('date_returned', '')
                date_picked_up = record.get('date_picked_up', '')
                date_paid = record.get('date_paid', '')
                consignor_name = record.get('consignor_name', '')
                barcode = record.get('barcode', '')
                commission_rate = record.get('commission_rate', 0)
                
                # Determine status
                status = "Active"
                status_icon = "🟢"
                
                if pd.notna(date_sold):
                    if pd.notna(date_paid):
                        status = "Paid"
                        status_icon = "💰"
                    else:
                        status = "Ready for Payment"
                        status_icon = "💳"
                elif pd.notna(date_returned):
                    if pd.notna(date_picked_up):
                        status = "Picked Up"
                        status_icon = "📦✅"
                    else:
                        status = "Ready for Pickup"
                        status_icon = "📦"
                elif pd.isna(barcode) or barcode == '' or barcode == 'None':
                    status = "Ready for Dropoff"
                    status_icon = "📤"
                
                # Format commission rate
                commission_display = f"{commission_rate*100:.1f}%" if commission_rate and commission_rate > 0 else "0%"
                
                status_data.append({
                    'ID': record_id,
                    'Artist': artist,
                    'Title': title,
                    'Price': f"${store_price:.2f}" if store_price else "$0.00",
                    'Status': f"{status_icon} {status}",
                    'Added Date': created_at,
                    'Consignor': consignor_name if user_id is None else '',
                    'Barcode': barcode if barcode and barcode != 'None' else 'No barcode',
                    'Commission': commission_display  # ADDED: Commission rate
                })
            
            # Create dataframe
            status_df = pd.DataFrame(status_data)
            
            # Display the table
            if not status_df.empty:
                # Add action buttons for each row
                for i, (_, row) in enumerate(status_df.iterrows()):
                    status_text = row['Status']
                    record_id = row['ID']
                    
                    # Determine column layout based on view
                    if user_id is None:  # Admin view
                        col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns([1, 3, 2, 2, 2, 2, 2, 2, 1])
                    else:  # Consignor view
                        col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1, 3, 2, 2, 2, 2, 2, 1])
                    
                    with col1:
                        st.write(row['ID'])
                    
                    with col2:
                        st.write(f"{row['Artist']} - {row['Title']}")
                    
                    with col3:
                        st.write(row['Price'])
                    
                    with col4:
                        st.write(row['Status'])
                    
                    with col5:
                        st.write(row['Added Date'][:10] if len(row['Added Date']) > 10 else row['Added Date'])
                    
                    with col6:
                        if user_id is None:  # Admin view
                            st.write(row['Consignor'])
                        else:
                            st.write(row['Barcode'])
                    
                    with col7:
                        st.write(row['Commission'])
                    
                    with col8:
                        # Action buttons based on status
                        if "Active" in status_text:
                            if st.button("Remove", key=f"remove_{record_id}_{i}", help="Remove record"):
                                if self._delete_record(record_id):
                                    st.success(f"Record {record_id} removed!")
                                    st.rerun()
                        elif "Ready for Dropoff" in status_text:
                            if st.button("Remove", key=f"delete_dropoff_{record_id}_{i}", help="Remove record"):
                                if self._delete_record(record_id):
                                    st.success(f"Record {record_id} removed!")
                                    st.rerun()
                        elif "Ready for Pickup" in status_text:
                            if st.button("Remove", key=f"delete_pickup_{record_id}_{i}", help="Remove record"):
                                if self._delete_record(record_id):
                                    st.success(f"Record {record_id} removed!")
                                    st.rerun()
                    
                    # Only show delete button for admin view
                    if user_id is None:  # Admin view
                        with col9:
                            if st.button("Delete", key=f"admin_delete_{record_id}_{i}", help="Delete record permanently"):
                                if self._delete_record(record_id):
                                    st.success(f"Record {record_id} deleted!")
                                    st.rerun()
            
        except Exception as e:
            st.error(f"Error loading consignment records: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    def _delete_record(self, record_id):
        """Delete a record from the database"""
        try:
            success = st.session_state.db_manager.delete_record(record_id)
            return success
        except Exception as e:
            st.error(f"Error deleting record: {e}")
            return False
    
    def _render_payment_section(self, user_id):
        """Render payment section with enhanced validation"""
        
        try:
            payment_records = st.session_state.db_manager.get_consignment_records_ready_for_payment(user_id)
            
            if payment_records is None or len(payment_records) == 0:
                st.info("No records ready for payment.")
                return
            
            # Convert to DataFrame if needed
            if not isinstance(payment_records, pd.DataFrame):
                payment_records = pd.DataFrame(payment_records)
            
            if payment_records.empty:
                st.info("No records ready for payment.")
                return
            
            # Calculate totals with commission
            if 'store_price' in payment_records.columns and 'commission_rate' in payment_records.columns:
                payment_records['store_price'] = pd.to_numeric(payment_records['store_price'], errors='coerce').fillna(0)
                payment_records['commission_rate'] = pd.to_numeric(payment_records['commission_rate'], errors='coerce').fillna(0)
                
                total_sales = payment_records['store_price'].sum()
                commission_rate = payment_records['commission_rate'].iloc[0] if len(payment_records) > 0 else 0
                
                # Check for store credit option
                store_credit_records = payment_records[payment_records['store_credit_option'] == True]
                store_credit_sales = store_credit_records['store_price'].sum() if not store_credit_records.empty else 0
                
                # Apply store credit bonus
                commission_calc = CommissionCalculator(st.session_state.db_manager)
                payout_info = commission_calc.calculate_consignor_payout(
                    total_sales, 
                    commission_rate,
                    store_credit_option=(store_credit_sales > 0)
                )
                
                st.metric("Records Ready", len(payment_records))
                st.metric("Total Payout", f"${payout_info['consignor_payout']:.2f}")
                
                if store_credit_sales > 0:
                    st.success(f"💰 Store credit bonus applied! (+{commission_calc._get_config_int('COMMISSION_STORE_CREDIT_BONUS')}%)")
            else:
                st.metric("Records Ready", len(payment_records))
                st.metric("Total Payout", "N/A")
            
            # Check payout eligibility
            payout_amount = payout_info['consignor_payout'] if 'payout_info' in locals() else total_sales
            is_eligible, message = self.commission_calculator.check_payout_eligibility(user_id, payout_amount)
            
            if not is_eligible:
                st.warning(f"⚠️ {message}")
            
            # Display records
            display_cols = []
            for col in ['id', 'artist', 'title', 'store_price', 'date_sold', 'store_credit_option']:
                if col in payment_records.columns:
                    display_cols.append(col)
            
            display_df = payment_records[display_cols].copy()
            
            # Format price column
            if 'store_price' in display_df.columns:
                def format_price(x):
                    try:
                        if pd.isna(x) or str(x).strip() == '':
                            return "$0.00"
                        return f"${float(x):.2f}"
                    except:
                        return "$0.00"
                
                display_df['store_price'] = display_df['store_price'].apply(format_price)
            
            # Format store credit option
            if 'store_credit_option' in display_df.columns:
                display_df['store_credit_option'] = display_df['store_credit_option'].apply(
                    lambda x: "✅ Yes" if x else "❌ No"
                )
            
            # Create column configuration
            column_config = {}
            if 'id' in display_df.columns:
                column_config['id'] = st.column_config.NumberColumn('ID')
            if 'artist' in display_df.columns:
                column_config['artist'] = st.column_config.TextColumn('Artist')
            if 'title' in display_df.columns:
                column_config['title'] = st.column_config.TextColumn('Title')
            if 'store_price' in display_df.columns:
                column_config['store_price'] = st.column_config.TextColumn('Price')
            if 'date_sold' in display_df.columns:
                display_df['date_sold'] = pd.to_datetime(display_df['date_sold'], errors='coerce').dt.date
                column_config['date_sold'] = st.column_config.DateColumn('Date Sold')
            if 'store_credit_option' in display_df.columns:
                column_config['store_credit_option'] = st.column_config.TextColumn('Store Credit')
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            # Actions
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💳 Process Payment", key="admin_process_payment", use_container_width=True, disabled=not is_eligible):
                    self._process_payment(payment_records, user_id)
            
            with col2:
                if st.button("🧾 Generate Report", key="admin_payment_report", use_container_width=True):
                    self._generate_payment_report(payment_records, user_id)
            
            with col3:
                store_credit_only = st.checkbox("Store Credit Only", value=False)
                if st.button("💰 Convert to Store Credit", key="admin_store_credit", use_container_width=True):
                    self._convert_to_store_credit(payment_records, user_id)
        except Exception as e:
            st.error(f"Error loading payment records: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    def _process_payment(self, payment_records, user_id):
        """Process payment with enhanced tracking"""
        try:
            # Update user's last payout date
            today = datetime.now().date()
            user_update = {'last_payout_date': today}
            
            # Calculate store credit if any
            store_credit_records = payment_records[payment_records['store_credit_option'] == True]
            if not store_credit_records.empty:
                store_credit_amount = store_credit_records['store_price'].sum()
                user_info = st.session_state.db_manager.get_user_by_id(user_id)
                current_credit = user_info.get('store_credit_balance', 0)
                user_update['store_credit_balance'] = current_credit + store_credit_amount
            
            # Update user
            result = st.session_state.db_manager._make_request(
                'PUT', 
                f'/users/{user_id}',
                json=user_update
            )
            
            # Mark records as paid
            for _, record in payment_records.iterrows():
                st.session_state.db_manager.update_record(record['id'], {
                    'date_paid': today
                })
            
            # Send email notification
            total_amount = payment_records['store_price'].sum()
            self.email_service.send_payment_notification(user_id, total_amount, len(payment_records))
            
            st.success(f"✅ Payment processed for {len(payment_records)} records!")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error processing payment: {e}")
    
    def _convert_to_store_credit(self, payment_records, user_id):
        """Convert cash payment to store credit"""
        try:
            for _, record in payment_records.iterrows():
                st.session_state.db_manager.update_record(record['id'], {
                    'store_credit_option': True
                })
            
            st.success(f"✅ {len(payment_records)} records converted to store credit!")
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Error converting to store credit: {e}")
    
    def _generate_payment_report(self, payment_records, user_id):
        """Generate detailed payment report"""
        try:
            # Calculate commission and payout
            total_sales = payment_records['store_price'].sum()
            commission_rate = payment_records['commission_rate'].iloc[0] if len(payment_records) > 0 else 0
            
            commission_calc = CommissionCalculator(st.session_state.db_manager)
            payout_info = commission_calc.calculate_consignor_payout(
                total_sales, 
                commission_rate,
                store_credit_option=False
            )
            
            # Create detailed report
            report_data = []
            for _, record in payment_records.iterrows():
                sale_price = record.get('store_price', 0)
                date_sold = record.get('date_sold', '')
                commission_rate = record.get('commission_rate', 0)
                store_credit = record.get('store_credit_option', False)
                
                report_data.append({
                    'Record ID': record['id'],
                    'Artist': record.get('artist', ''),
                    'Title': record.get('title', ''),
                    'Sale Price': f"${float(sale_price):.2f}" if sale_price else "$0.00",
                    'Date Sold': date_sold,
                    'Commission Rate': f"{float(commission_rate)*100:.1f}%" if commission_rate else "0%",
                    'Store Credit': 'Yes' if store_credit else 'No'
                })
            
            # Add summary rows
            report_data.append({
                'Record ID': '---',
                'Artist': '',
                'Title': '',
                'Sale Price': '',
                'Date Sold': '',
                'Commission Rate': '',
                'Store Credit': ''
            })
            
            report_data.append({
                'Record ID': 'SUMMARY',
                'Artist': '',
                'Title': '',
                'Sale Price': f"Total Sales: ${float(total_sales):.2f}",
                'Date Sold': f"Consignor Payout: ${payout_info['consignor_payout']:.2f}",
                'Commission Rate': f"Commission: ${payout_info['store_commission']:.2f} ({payout_info['commission_rate']*100:.1f}%)",
                'Store Credit': f"Records: {len(payment_records)}"
            })
            
            df = pd.DataFrame(report_data)
            csv_data = df.to_csv(index=False)
            
            # Create download button
            consignor_name = payment_records.iloc[0].get('consignor_name', 'Unknown') if len(payment_records) > 0 else "Unknown"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"payment_report_{consignor_name}_{timestamp}.csv"
            
            st.download_button(
                label="📊 Download Payment Report",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                use_container_width=True,
                key=f"download_payment_{timestamp}"
            )
            
        except Exception as e:
            st.error(f"❌ Error generating report: {e}")
    
    def _check_user_price_validity(self, user_id):
        """Check price validity for user's records"""
        try:
            # Get user's active consignment records
            records_df = st.session_state.db_manager.get_all_records()
            user_records = records_df[records_df['consignor_id'] == user_id]
            
            if user_records.empty:
                st.info("No consignment records found")
                return
            
            invalid_records = []
            for _, record in user_records.iterrows():
                user_price = record.get('store_price', 0)
                original_price = record.get('original_consignor_price', user_price)
                
                # Check if price exceeds maximum allowed
                validation = self.pricing_validator.validate_user_price(
                    user_price,
                    record.to_dict()
                )
                
                if not validation['is_valid']:
                    invalid_records.append({
                        'id': record['id'],
                        'artist': record.get('artist', ''),
                        'title': record.get('title', ''),
                        'current_price': user_price,
                        'max_allowed': validation['max_allowed'],
                        'advised_price': validation['advised_price']
                    })
            
            if invalid_records:
                st.warning(f"⚠️ Found {len(invalid_records)} records with prices exceeding maximum allowed:")
                
                df = pd.DataFrame(invalid_records)
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'id': st.column_config.NumberColumn('ID'),
                        'artist': st.column_config.TextColumn('Artist'),
                        'title': st.column_config.TextColumn('Title'),
                        'current_price': st.column_config.NumberColumn('Current Price', format='$%.2f'),
                        'max_allowed': st.column_config.NumberColumn('Max Allowed', format='$%.2f'),
                        'advised_price': st.column_config.NumberColumn('Advised Price', format='$%.2f')
                    }
                )
                
                if st.button("📧 Request Price Review", use_container_width=True):
                    self._request_price_review(invalid_records, user_id)
            else:
                st.success("✅ All your prices are within allowed limits!")
                
        except Exception as e:
            st.error(f"Error checking price validity: {e}")
    
    def _request_price_review(self, invalid_records, user_id):
        """Request admin review for price overrides"""
        try:
            for record in invalid_records:
                st.session_state.db_manager.update_record(record['id'], {
                    'price_override_requested': True
                })
            
            # Send notification to admin
            message = f"Consignor {user_id} has requested price override for {len(invalid_records)} records."
            # This would send to admin email in production
            
            st.success(f"✅ Price review requested for {len(invalid_records)} records!")
            st.info("An administrator will review your request and contact you.")
            
        except Exception as e:
            st.error(f"Error requesting price review: {e}")
    
    def _get_store_fill_info(self):
        """Get store fill information"""
        store_capacity = int(st.session_state.db_manager.get_config_value('STORE_CAPACITY', '12000'))
        
        records_df = st.session_state.db_manager.get_all_records()
        total_inventory = len(records_df) if not records_df.empty else 0
        
        fill_fraction = total_inventory / store_capacity if store_capacity > 0 else 0
        fill_percentage = fill_fraction * 100
        
        return {
            'total_inventory': total_inventory,
            'store_capacity': store_capacity,
            'fill_fraction': fill_fraction,
            'fill_percentage': fill_percentage
        }
    
    def _get_user_consignment_stats(self, user_id):
        """Get consignment statistics for a user"""
        records_df = st.session_state.db_manager.get_all_records()
        
        if records_df.empty:
            return {'active_count': 0, 'payment_ready_count': 0, 'pickup_ready_count': 0}
        
        user_records = records_df[records_df['consignor_id'] == user_id]
        
        # Active records (not sold, not returned)
        active_records = user_records[
            (user_records['date_sold'].isna()) & 
            (user_records['date_returned'].isna())
        ]
        
        # Records ready for payment
        payment_records = user_records[
            (user_records['date_sold'].notna()) & 
            (user_records['date_paid'].isna())
        ]
        
        # Records ready for pickup
        pickup_records = user_records[
            (user_records['date_returned'].notna()) & 
            (user_records['date_picked_up'].isna())
        ]
        
        return {
            'active_count': len(active_records),
            'payment_ready_count': len(payment_records),
            'pickup_ready_count': len(pickup_records)
        }
    
    def _render_user_selector(self, context):
        """Render user selection dropdown"""
        users_df = st.session_state.db_manager.get_all_users()
        
        if users_df.empty:
            st.info("No users found")
            return None
        
        # Create selection options
        options = ["Select a user..."] + [f"{row['username']} ({row['full_name'] or 'No name'})" for _, row in users_df.iterrows()]
        
        selected_option = st.selectbox(
            "Choose user:",
            options=options,
            key=f"user_selector_{context}"
        )
        
        if selected_option == "Select a user...":
            return None
        
        # Extract user ID from selection
        username = selected_option.split(" (")[0]
        selected_user = users_df[users_df['username'] == username]
        
        if not selected_user.empty:
            return int(selected_user.iloc[0]['id'])
        
        return None
    
    def _generate_consignor_report(self, user_id):
        """Generate consignor sales report"""
        try:
            records_df = st.session_state.db_manager.get_all_records()
            user_records = records_df[records_df['consignor_id'] == user_id]
            
            if user_records.empty:
                st.info("No consignment records found")
                return
            
            # Calculate statistics
            total_records = len(user_records)
            sold_records = user_records[user_records['date_sold'].notna()]
            active_records = user_records[user_records['date_sold'].isna()]
            
            total_sales = sold_records['store_price'].sum()
            avg_sale_price = sold_records['store_price'].mean() if not sold_records.empty else 0
            
            # Create report
            report_data = []
            for _, record in user_records.iterrows():
                report_data.append({
                    'ID': record['id'],
                    'Artist': record.get('artist', ''),
                    'Title': record.get('title', ''),
                    'Price': f"${record.get('store_price', 0):.2f}",
                    'Status': 'Sold' if pd.notna(record.get('date_sold')) else 'Active',
                    'Date Added': record.get('created_at', ''),
                    'Date Sold': record.get('date_sold', ''),
                    'Commission': f"{record.get('commission_rate', 0)*100:.1f}%"
                })
            
            df = pd.DataFrame(report_data)
            csv_data = df.to_csv(index=False)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"consignor_report_{user_id}_{timestamp}.csv"
            
            st.download_button(
                label="📊 Download Your Report",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                use_container_width=True,
                key=f"download_report_{timestamp}"
            )
            
            # Show summary
            st.info(f"""
            **Your Consignment Summary:**
            - Total Records: {total_records}
            - Sold: {len(sold_records)}
            - Active: {len(active_records)}
            - Total Sales: ${total_sales:.2f}
            - Average Sale Price: ${avg_sale_price:.2f}
            """)
            
        except Exception as e:
            st.error(f"Error generating report: {e}")

    # MOVED FROM display_handler.py
    def render_checkout_section(self, checkout_records, process_checkout_callback):
        """Render checkout section for selected records"""
        if not checkout_records:
            return
        
        st.subheader("Checkout")
        
        total_amount = 0
        for record in checkout_records:
            store_price = record.get('store_price', 0)
            total_amount += store_price
        
        st.write(f"**Total Amount:** ${total_amount:.2f}")
        
        if st.button("Process Checkout", key="process_checkout"):
            amount_collected = process_checkout_callback()
            if amount_collected > 0:
                st.success(f"✅ Checkout processed successfully! Amount collected: ${amount_collected:.2f}")
                st.session_state.checkout_records = []
                st.rerun()