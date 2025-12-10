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
            user_info = st.session_state.db_manager.get_user_by_id(user_id)
            if user_info is not None and not user_info.empty:
                # Convert Series to dict for display
                user_info_dict = user_info.to_dict()
                st.info(f"**Selected User:** {user_info_dict.get('full_name') or user_info_dict.get('username')}")
        
        # Show sections vertically
        st.divider()
        
        # Dropoff Section
        with st.container():
            st.subheader("📤 Dropoff")
            self._render_dropoff_section(user_id if user_id else None)
        
        st.divider()
        
        # Payment Section
        with st.container():
            st.subheader("💰 Payment")
            if user_id:
                self._render_payment_section(user_id)
            else:
                st.info("👆 Select a user to view payment section")
        
        st.divider()
        
        # Pickup Section
        with st.container():
            st.subheader("📦 Pickup")
            if user_id:
                self._render_pickup_section(user_id)
            else:
                st.info("👆 Select a user to view pickup section")
        
        # Admin tools at the bottom
        st.divider()
        st.subheader("🛠️ Admin Tools")
        
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
        
        # Convert Series to dict for display
        user_dict = user.to_dict() if hasattr(user, 'to_dict') else dict(user)
        st.write(f"**User:** {user_dict.get('full_name') or user_dict.get('username')}")
        
        # Show sections vertically
        st.divider()
        
        # Dropoff Section
        with st.container():
            st.subheader("📤 Dropoff")
            self._render_consignor_dropoff(user_id)
        
        st.divider()
        
        # Payment Section
        with st.container():
            st.subheader("💰 Payment")
            self._render_consignor_payment_requests(user_id)
        
        st.divider()
        
        # Pickup Section
        with st.container():
            st.subheader("📦 Pickup")
            self._render_consignor_pickup_returns(user_id)
    
    def _render_dropoff_section(self, selected_user_id=None):
        """Render dropoff section showing records ready for dropoff (no barcodes yet)"""
        
        try:
            # FIXED: Use the correct method for dropoff records
            if selected_user_id:
                # Get dropoff records for this specific user
                all_records = st.session_state.db_manager.get_dropoff_records(selected_user_id)
            else:
                # For admin view, get all records without barcodes
                all_records = st.session_state.db_manager.get_records_without_barcodes()
            
            # Check if we got valid data
            if all_records is None:
                st.info("No records found.")
                return
            
            # Check if it's empty
            if isinstance(all_records, pd.DataFrame):
                if all_records.empty:
                    st.info("No records ready for dropoff.")
                    return
            elif len(all_records) == 0:
                st.info("No records ready for dropoff.")
                return
            
            if selected_user_id:
                # Convert to DataFrame if needed
                if not isinstance(all_records, pd.DataFrame):
                    all_records = pd.DataFrame(all_records)
                
                # Filter for this user's records
                # First check if 'consignor_id' column exists
                if 'consignor_id' in all_records.columns:
                    # Filter using .loc to avoid chained assignment warnings
                    user_records = all_records.loc[all_records['consignor_id'].astype(str) == str(selected_user_id)].copy()
                    
                    if user_records.empty:
                        st.info("No records ready for dropoff.")
                        return
                    
                    st.metric("Ready for Dropoff", len(user_records))
                    
                    # Prepare display columns
                    display_cols = []
                    for col in ['id', 'artist', 'title', 'store_price', 'genre_name', 'created_at']:
                        if col in user_records.columns:
                            display_cols.append(col)
                    
                    display_data = user_records[display_cols].copy()
                    
                    # Format price column
                    if 'store_price' in display_data.columns:
                        def format_price(x):
                            try:
                                if pd.isna(x) or str(x).strip() == '':
                                    return "$0.00"
                                return f"${float(x):.2f}"
                            except:
                                return "$0.00"
                        
                        display_data['store_price'] = display_data['store_price'].apply(format_price)
                    
                    # Create column configuration
                    column_config = {}
                    if 'id' in display_data.columns:
                        column_config['id'] = st.column_config.NumberColumn('ID')
                    if 'artist' in display_data.columns:
                        column_config['artist'] = st.column_config.TextColumn('Artist')
                    if 'title' in display_data.columns:
                        column_config['title'] = st.column_config.TextColumn('Title')
                    if 'store_price' in display_data.columns:
                        column_config['store_price'] = st.column_config.TextColumn('Price')
                    if 'genre_name' in display_data.columns:
                        column_config['genre_name'] = st.column_config.TextColumn('Genre')
                    if 'created_at' in display_data.columns:
                        column_config['created_at'] = st.column_config.DatetimeColumn('Added')
                    
                    st.dataframe(
                        display_data,
                        use_container_width=True,
                        hide_index=True,
                        column_config=column_config
                    )
                    
                    # Generate dropoff list button
                    if st.button("📋 Generate Dropoff List", key="admin_dropoff_list", use_container_width=True):
                        user_info = st.session_state.db_manager.get_user_by_id(selected_user_id)
                        if user_info is not None and not user_info.empty:
                            # Convert Series to dict
                            user_info_dict = user_info.to_dict()
                            consignor_name = user_info_dict.get('full_name') or user_info_dict.get('username') or "Unknown"
                        else:
                            consignor_name = "Unknown"
                        
                        # Convert to list of dicts for the download
                        records_list = user_records.to_dict('records')
                        self._generate_dropoff_list(records_list, consignor_name)
                else:
                    st.info("No consignment records found.")
            else:
                # Show summary for all users
                if not isinstance(all_records, pd.DataFrame):
                    all_records = pd.DataFrame(all_records)
                
                if 'consignor_id' in all_records.columns:
                    # Remove rows where consignor_id is null
                    consignment_records = all_records[all_records['consignor_id'].notna()].copy()
                    
                    if consignment_records.empty:
                        st.info("No consignment records ready for dropoff.")
                        return
                    
                    # Count records by consignor
                    consignor_counts = consignment_records['consignor_id'].value_counts()
                    
                    if len(consignor_counts) > 0:
                        st.write("**Summary by Consignor:**")
                        for consignor_id, count in consignor_counts.items():
                            # Try to get consignor name
                            try:
                                consignor_info = st.session_state.db_manager.get_user_by_id(int(consignor_id))
                                if consignor_info is not None and not consignor_info.empty:
                                    # Convert Series to dict
                                    consignor_info_dict = consignor_info.to_dict()
                                    consignor_name = consignor_info_dict.get('full_name') or consignor_info_dict.get('username') or f"ID {consignor_id}"
                                else:
                                    consignor_name = f"ID {consignor_id}"
                            except:
                                consignor_name = f"ID {consignor_id}"
                            st.write(f"- {consignor_name}: {count} records")
                    else:
                        st.info("No consignment records ready for dropoff.")
                else:
                    st.info("No consignment records ready for dropoff.")
        except Exception as e:
            st.error(f"Error loading dropoff records: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    def _render_consignor_dropoff(self, user_id):
        """Render dropoff section for individual consignors"""
        
        try:
            # FIXED: Use the dropoff_records method which filters by user
            user_records = st.session_state.db_manager.get_dropoff_records(user_id)
            
            # Check if we got valid data
            if user_records is None:
                st.info("All your records have been printed with price tags.")
                return
            
            # Check if it's empty
            if isinstance(user_records, pd.DataFrame):
                if user_records.empty:
                    st.info("All your records have been printed with price tags.")
                    return
            elif len(user_records) == 0:
                st.info("All your records have been printed with price tags.")
                return
            
            st.metric("Ready for Dropoff", len(user_records))
            
            # Convert to DataFrame if needed
            if not isinstance(user_records, pd.DataFrame):
                user_records = pd.DataFrame(user_records)
            
            # Prepare display columns
            display_cols = []
            for col in ['id', 'artist', 'title', 'store_price', 'genre_name', 'created_at']:
                if col in user_records.columns:
                    display_cols.append(col)
            
            display_data = user_records[display_cols].copy()
            
            # Format price column
            if 'store_price' in display_data.columns:
                def format_price(x):
                    try:
                        if pd.isna(x) or str(x).strip() == '':
                            return "$0.00"
                        return f"${float(x):.2f}"
                    except:
                        return "$0.00"
                
                display_data['store_price'] = display_data['store_price'].apply(format_price)
            
            # Create column configuration
            column_config = {}
            if 'id' in display_data.columns:
                column_config['id'] = st.column_config.NumberColumn('ID')
            if 'artist' in display_data.columns:
                column_config['artist'] = st.column_config.TextColumn('Artist')
            if 'title' in display_data.columns:
                column_config['title'] = st.column_config.TextColumn('Title')
            if 'store_price' in display_data.columns:
                column_config['store_price'] = st.column_config.TextColumn('Price')
            if 'genre_name' in display_data.columns:
                column_config['genre_name'] = st.column_config.TextColumn('Genre')
            if 'created_at' in display_data.columns:
                column_config['created_at'] = st.column_config.DatetimeColumn('Added')
            
            st.dataframe(
                display_data,
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            # Generate dropoff list button
            user_info = st.session_state.db_manager.get_user_by_id(user_id)
            # FIXED: Check if user_info is not None and not empty
            if user_info is not None and not user_info.empty:
                # Convert Series to dict
                user_info_dict = user_info.to_dict()
                consignor_name = user_info_dict.get('full_name') or user_info_dict.get('username') or "Unknown"
            else:
                consignor_name = "Unknown"
            
            if st.button("📋 Generate Dropoff List", key="consignor_dropoff_list", use_container_width=True):
                # Convert to list of dicts for the download
                records_list = user_records.to_dict('records')
                self._generate_dropoff_list(records_list, consignor_name)
        except Exception as e:
            st.error(f"Error loading dropoff records: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    def _render_payment_section(self, user_id):
        """Render payment section"""
        
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
            
            # Calculate totals
            if 'store_price' in payment_records.columns and 'commission_rate' in payment_records.columns:
                # Handle NaN values
                payment_records['store_price'] = pd.to_numeric(payment_records['store_price'], errors='coerce').fillna(0)
                payment_records['commission_rate'] = pd.to_numeric(payment_records['commission_rate'], errors='coerce').fillna(0)
                
                total_sales = payment_records['store_price'].sum()
                commission_rate = payment_records['commission_rate'].iloc[0] if len(payment_records) > 0 else 0
                store_commission = total_sales * commission_rate
                user_payout = total_sales - store_commission
                
                st.metric("Records Ready", len(payment_records))
                st.metric("Total Payout", f"${user_payout:.2f}")
            else:
                st.metric("Records Ready", len(payment_records))
                st.metric("Total Payout", "N/A")
            
            # Display records
            display_cols = []
            for col in ['id', 'artist', 'title', 'store_price', 'date_sold']:
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
                # Convert date column
                display_df['date_sold'] = pd.to_datetime(display_df['date_sold'], errors='coerce').dt.date
                column_config['date_sold'] = st.column_config.DateColumn('Date Sold')
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            # Actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💳 Process Payment", key="admin_process_payment", use_container_width=True):
                    self._process_payment(payment_records)
            
            with col2:
                if st.button("🧾 Generate Report", key="admin_payment_report", use_container_width=True):
                    if 'store_price' in payment_records.columns and 'commission_rate' in payment_records.columns:
                        total_sales = payment_records['store_price'].sum()
                        commission_rate = payment_records['commission_rate'].iloc[0] if len(payment_records) > 0 else 0
                        store_commission = total_sales * commission_rate
                        user_payout = total_sales - store_commission
                        self._generate_payment_report(payment_records, user_payout, store_commission)
                    else:
                        st.error("Cannot generate report: missing price or commission data")
        except Exception as e:
            st.error(f"Error loading payment records: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    def _render_consignor_payment_requests(self, user_id):
        """Render payment request section for users"""
        
        try:
            payment_records = st.session_state.db_manager.get_user_consignment_records_ready_for_payment(user_id)
            
            if payment_records is None or len(payment_records) == 0:
                st.info("No records ready for payment.")
                return
            
            # Convert to DataFrame if needed
            if not isinstance(payment_records, pd.DataFrame):
                payment_records = pd.DataFrame(payment_records)
            
            if payment_records.empty:
                st.info("No records ready for payment.")
                return
            
            # Calculate totals
            if 'store_price' in payment_records.columns and 'commission_rate' in payment_records.columns:
                # Handle NaN values
                payment_records['store_price'] = pd.to_numeric(payment_records['store_price'], errors='coerce').fillna(0)
                payment_records['commission_rate'] = pd.to_numeric(payment_records['commission_rate'], errors='coerce').fillna(0)
                
                total_sales = payment_records['store_price'].sum()
                commission_rate = payment_records['commission_rate'].iloc[0] if len(payment_records) > 0 else 0
                store_commission = total_sales * commission_rate
                user_payout = total_sales - store_commission
                
                st.metric("Records Ready", len(payment_records))
                st.metric("Your Payout", f"${user_payout:.2f}")
            else:
                st.metric("Records Ready", len(payment_records))
                st.metric("Your Payout", "N/A")
            
            # Display records
            display_cols = []
            for col in ['id', 'artist', 'title', 'store_price', 'date_sold']:
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
                # Convert date column
                display_df['date_sold'] = pd.to_datetime(display_df['date_sold'], errors='coerce').dt.date
                column_config['date_sold'] = st.column_config.DateColumn('Date Sold')
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            # Request payment button
            if st.button("💳 Request Payment", key="consignor_request_payment", use_container_width=True):
                success = self._request_payment(payment_records, user_id)
                if success:
                    st.success("Payment request submitted!")
                    st.rerun()
        except Exception as e:
            st.error(f"Error loading payment records: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    def _render_pickup_section(self, user_id):
        """Render pickup section"""
        
        try:
            pickup_records = st.session_state.db_manager.get_consignment_records_ready_for_pickup(user_id)
            
            if pickup_records is None or len(pickup_records) == 0:
                st.info("No records ready for pickup.")
                return
            
            # Convert to DataFrame if needed
            if not isinstance(pickup_records, pd.DataFrame):
                pickup_records = pd.DataFrame(pickup_records)
            
            if pickup_records.empty:
                st.info("No records ready for pickup.")
                return
            
            st.metric("Records Ready", len(pickup_records))
            
            # Display records
            display_cols = []
            for col in ['id', 'artist', 'title', 'store_price', 'date_returned']:
                if col in pickup_records.columns:
                    display_cols.append(col)
            
            display_df = pickup_records[display_cols].copy()
            
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
            if 'date_returned' in display_df.columns:
                # Convert date column
                display_df['date_returned'] = pd.to_datetime(display_df['date_returned'], errors='coerce').dt.date
                column_config['date_returned'] = st.column_config.DateColumn('Date Returned')
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            # Actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📤 Process Pickup", key="admin_process_pickup", use_container_width=True):
                    self._process_pickup(pickup_records)
            
            with col2:
                if st.button("📋 Generate List", key="admin_pickup_list", use_container_width=True):
                    self._generate_pickup_list(pickup_records)
        except Exception as e:
            st.error(f"Error loading pickup records: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    def _render_consignor_pickup_returns(self, user_id):
        """Render pickup and returns section for users"""
        
        try:
            pickup_records = st.session_state.db_manager.get_user_consignment_records_ready_for_pickup(user_id)
            
            if pickup_records is None or len(pickup_records) == 0:
                st.info("No records ready for pickup.")
                return
            
            # Convert to DataFrame if needed
            if not isinstance(pickup_records, pd.DataFrame):
                pickup_records = pd.DataFrame(pickup_records)
            
            if pickup_records.empty:
                st.info("No records ready for pickup.")
                return
            
            st.metric("Records Ready", len(pickup_records))
            
            # Display records
            display_cols = []
            for col in ['id', 'artist', 'title', 'store_price', 'date_returned']:
                if col in pickup_records.columns:
                    display_cols.append(col)
            
            display_df = pickup_records[display_cols].copy()
            
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
            if 'date_returned' in display_df.columns:
                # Convert date column
                display_df['date_returned'] = pd.to_datetime(display_df['date_returned'], errors='coerce').dt.date
                column_config['date_returned'] = st.column_config.DateColumn('Date Returned')
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
            
            # Actions
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📤 Confirm Pickup", key="consignor_confirm_pickup", use_container_width=True):
                    success = self._confirm_pickup(pickup_records)
                    if success:
                        st.success("Pickup confirmed!")
                        st.rerun()
            
            with col2:
                if st.button("📋 Generate List", key="consignor_pickup_list", use_container_width=True):
                    self._generate_pickup_list(pickup_records)
        except Exception as e:
            st.error(f"Error loading pickup records: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    def _render_user_selector(self, context):
        """Render user selector dropdown"""
        users = st.session_state.db_manager.get_all_users()
        
        if users is None or len(users) == 0:
            st.error("No users found.")
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
    
    def _generate_dropoff_list(self, records, consignor_name):
        """Generate dropoff list CSV"""
        try:
            # Create DataFrame from records
            df_data = []
            for record in records:
                row = {
                    'Record ID': record.get('id', ''),
                    'Artist': record.get('artist', 'Unknown'),
                    'Title': record.get('title', 'Unknown'),
                    'Price': f"${record.get('store_price', 0):.2f}",
                    'Genre': record.get('genre_name', 'Unknown'),
                    'Catalog': record.get('catalog_number', ''),
                    'Added Date': record.get('created_at', '')
                }
                df_data.append(row)
            
            df = pd.DataFrame(df_data)
            csv_data = df.to_csv(index=False)
            
            # Create download button
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dropoff_list_{consignor_name}_{timestamp}.csv"
            
            st.download_button(
                label="📋 Download Dropoff List",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                use_container_width=True,
                key=f"download_dropoff_{timestamp}"
            )
            
        except Exception as e:
            st.error(f"❌ Error generating dropoff list: {e}")
    
    def _request_payment(self, payment_records, user_id):
        """Request payment for selected records (user action)"""
        try:
            # For users, this just marks them as payment requested
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
                sale_price = record.get('store_price', 0)
                date_sold = record.get('date_sold', '')
                commission_rate = record.get('commission_rate', 0)
                
                report_data.append({
                    'Record ID': record['id'],
                    'Artist': record.get('artist', ''),
                    'Title': record.get('title', ''),
                    'Sale Price': f"${float(sale_price):.2f}" if sale_price else "$0.00",
                    'Date Sold': date_sold,
                    'Commission Rate': f"{float(commission_rate)*100}%" if commission_rate else "0%"
                })
            
            # Add summary row
            total_sales = payment_records['store_price'].sum() if 'store_price' in payment_records.columns else 0
            
            report_data.append({
                'Record ID': 'SUMMARY',
                'Artist': '',
                'Title': '',
                'Sale Price': f"Total: ${float(total_sales):.2f}",
                'Date Sold': f"Payout: ${float(user_payout):.2f}",
                'Commission Rate': f"Commission: ${float(store_commission):.2f}"
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
    
    def _generate_pickup_list(self, pickup_records):
        """Generate pickup list CSV"""
        try:
            # Format price column
            def format_price(x):
                try:
                    if pd.isna(x) or str(x).strip() == '':
                        return "$0.00"
                    return f"${float(x):.2f}"
                except:
                    return "$0.00"
            
            pickup_records['formatted_price'] = pickup_records['store_price'].apply(format_price)
            
            df = pd.DataFrame({
                'Record ID': pickup_records['id'],
                'Artist': pickup_records['artist'],
                'Title': pickup_records['title'],
                'Price': pickup_records['formatted_price'],
                'Date Returned': pickup_records['date_returned']
            })
            
            csv_data = df.to_csv(index=False)
            
            # Create download button
            consignor_name = pickup_records.iloc[0].get('consignor_name', 'Unknown') if len(pickup_records) > 0 else "Unknown"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pickup_list_{consignor_name}_{timestamp}.csv"
            
            st.download_button(
                label="📋 Download Pickup List",
                data=csv_data,
                file_name=filename,
                mime="text/csv",
                use_container_width=True,
                key=f"download_pickup_{timestamp}"
            )
            
        except Exception as e:
            st.error(f"❌ Error generating pickup list: {e}")