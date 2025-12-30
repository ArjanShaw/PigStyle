import streamlit as st
import pandas as pd
import requests

class ConsignmentTab:
    def __init__(self):
        # Initialize API client
        self.api_client = APIClient()
        
        # Initialize session state for selected records
        if 'selected_consignment_records' not in st.session_state:
            st.session_state.selected_consignment_records = []
        
        # Initialize session state for select all
        if 'select_all_consignment' not in st.session_state:
            st.session_state.select_all_consignment = False
    
    def render(self):
        user = st.session_state.get('user', {})
        user_id = user.get('id')
        user_role = user.get('role', 'consignor')
        
        if not user_id:
            st.warning("Please log in to view consignment information.")
            return
        
        # Show consignor's credit balance at the top
        if user_role == 'consignor':
            user_info = self.api_client.get_user(user_id)
            if user_info:
                credit_balance = user_info.get('store_credit_balance', 0)
                payout_requested = user_info.get('payout_requested', False)
                
                # Display credit balance
                if credit_balance > 0:
                    st.success(f"💰 **Your Credit Balance: ${credit_balance:.2f}**")
                else:
                    st.info(f"💳 **Your Credit Balance: ${credit_balance:.2f}**")
                
                # Request payout button for consignors with positive balance
                if credit_balance > 0 and not payout_requested:
                    if st.button("💰 Request Payout", type="primary"):
                        if self._request_payout(user_id):
                            st.success("✅ Payout request submitted! It will be processed by admin.")
                            st.rerun()
                elif payout_requested:
                    st.info("⏳ Payout request pending admin approval")
        
        # Show payout requests table for admin
        if user_role == 'admin':
            self._render_payout_requests()
        
        # Get consignment records
        if user_role == 'admin':
            # Use the new endpoint for consignment records
            response = requests.get(f"{self.api_client.base_url}/consignment/records")
        else:
            response = requests.get(f"{self.api_client.base_url}/consignment/records?user_id={user_id}")
        
        if response.status_code != 200:
            st.error("Error fetching records")
            return
        
        data = response.json()
        if data.get('status') != 'success':
            st.error("Error fetching records")
            return
        
        records = data.get('records', [])
        if not records:
            st.info("No consignment records found.")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(records)
        
        # Filter only records with consignor_id (consignment items)
        consignment_df = df[df['consignor_id'].notna()].copy()
        
        if consignment_df.empty:
            st.info("No consignment records found (all records are store-owned).")
            return
        
        # Add consignor name for admin view
        if user_role == 'admin':
            consignor_names = {}
            for consignor_id in consignment_df['consignor_id'].unique():
                user_info = self.api_client.get_user(int(consignor_id))
                if user_info:
                    consignor_names[consignor_id] = user_info.get('username', f"ID: {consignor_id}")
            
            consignment_df['consignor'] = consignment_df['consignor_id'].map(consignor_names)
        
        # Use display_status from API response
        if 'display_status' not in consignment_df.columns:
            # Fallback: determine status based on status_id and barcode
            def determine_display_status(row):
                status_id = row.get('status_id', 1)
                barcode = row.get('barcode')
                
                if status_id == 1:  # new
                    if pd.isna(barcode) or barcode in [None, '', 'None']:
                        return '🆕 New'
                    else:
                        return '✅ Active'
                elif status_id == 2:  # active
                    return '✅ Active'
                elif status_id == 3:  # sold
                    return '💰 Sold'
                elif status_id == 4:  # removed
                    return '🗑️ Removed'
                else:
                    return '❓ Unknown'
            
            consignment_df['display_status'] = consignment_df.apply(determine_display_status, axis=1)
        
        # Add record ID to session state for selection
        consignment_df['record_id'] = consignment_df['id']
        
        # Filter options
        st.subheader("Consignment Records")
        
        filter_cols = st.columns(4)
        with filter_cols[0]:
            show_new = st.checkbox("🆕 New", value=True, key="show_new")
        with filter_cols[1]:
            show_active = st.checkbox("✅ Active", value=True, key="show_active")
        with filter_cols[2]:
            show_sold = st.checkbox("💰 Sold", value=False, key="show_sold")
        with filter_cols[3]:
            show_removed = st.checkbox("🗑️ Removed", value=True, key="show_removed")
        
        # Apply filters
        selected_statuses = []
        if show_new:
            selected_statuses.append('🆕 New')
        if show_active:
            selected_statuses.append('✅ Active')
        if show_sold:
            selected_statuses.append('💰 Sold')
        if show_removed:
            selected_statuses.append('🗑️ Removed')
        
        filtered_df = consignment_df[consignment_df['display_status'].isin(selected_statuses)] if selected_statuses else consignment_df
        
        st.info(f"Showing {len(filtered_df)} of {len(consignment_df)} records")
        
        if filtered_df.empty:
            st.warning("No records match the selected filters.")
            return
        
        # Selection controls
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("✅ Select All", key="select_all_btn"):
                st.session_state.select_all_consignment = True
                st.session_state.selected_consignment_records = filtered_df['record_id'].tolist()
                st.rerun()
        
        with col2:
            if st.button("❌ Deselect All", key="deselect_all_btn"):
                st.session_state.select_all_consignment = False
                st.session_state.selected_consignment_records = []
                st.rerun()
        
        with col3:
            selected_count = len(st.session_state.selected_consignment_records)
            if selected_count > 0:
                # Check if selected records have mixed statuses
                selected_records_data = filtered_df[filtered_df['record_id'].isin(st.session_state.selected_consignment_records)]
                selected_statuses_set = set(selected_records_data['display_status'].unique())
                
                if len(selected_statuses_set) > 1:
                    st.error(f"❌ {selected_count} records selected - Cannot select records with mixed statuses!")
                else:
                    status = list(selected_statuses_set)[0] if selected_statuses_set else None
                    st.write(f"**{selected_count} {status} records selected**")
        
        # Create editable DataFrame with checkboxes
        display_data = []
        
        for idx, record in filtered_df.iterrows():
            record_id = record['record_id']
            
            # Determine if this record should be selected
            is_selected = record_id in st.session_state.selected_consignment_records
            
            display_row = {
                'Select': is_selected,
                'ID': record_id,
                'Status': record['display_status']
            }
            
            if user_role == 'admin':
                display_row['Consignor'] = record.get('consignor', f"ID: {record.get('consignor_id')}")
            
            display_row['Artist'] = record['artist']
            display_row['Title'] = record['title']
            display_row['Price'] = f"${record['store_price']:.2f}"
            
            display_data.append(display_row)
        
        # Create DataFrame for display
        display_df = pd.DataFrame(display_data)
        
        # Display the editable table
        column_config = {
            "Select": st.column_config.CheckboxColumn("Select", default=False),
            "ID": st.column_config.NumberColumn("ID", disabled=True),
            "Status": st.column_config.TextColumn("Status", disabled=True),
            "Artist": st.column_config.TextColumn("Artist", disabled=True),
            "Title": st.column_config.TextColumn("Title", disabled=True),
            "Price": st.column_config.TextColumn("Price", disabled=True),
        }
        
        if user_role == 'admin':
            column_config["Consignor"] = st.column_config.TextColumn("Consignor", disabled=True)
        
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            hide_index=True,
            width='stretch',
            key="consignment_table_editor",
            disabled=["ID", "Status", "Artist", "Title", "Price", "Consignor"]
        )
        
        # Update selected records based on user selection
        new_selected_records = []
        for idx, row in edited_df.iterrows():
            if row['Select']:
                record_id = row['ID']
                new_selected_records.append(record_id)
        
        # Check if newly selected records would create mixed statuses
        if new_selected_records:
            new_selected_data = filtered_df[filtered_df['record_id'].isin(new_selected_records)]
            new_statuses_set = set(new_selected_data['display_status'].unique())
            
            if len(new_statuses_set) > 1:
                st.error("❌ Cannot select records with mixed statuses. Please select records with the same status only.")
                # Revert to previous selection
                new_selected_records = st.session_state.selected_consignment_records.copy()
        
        # Update session state if selection changed
        if set(new_selected_records) != set(st.session_state.selected_consignment_records):
            st.session_state.selected_consignment_records = new_selected_records
            st.rerun()
        
        # Check if we have selected records
        if st.session_state.selected_consignment_records:
            # Get status of selected records
            selected_records_data = filtered_df[filtered_df['record_id'].isin(st.session_state.selected_consignment_records)]
            selected_status = selected_records_data['display_status'].iloc[0] if not selected_records_data.empty else None
            
            if selected_status:
                selected_count = len(st.session_state.selected_consignment_records)
                
                if selected_status == '🗑️ Removed':
                    # Show delete option for removed records
                    st.warning(f"You are about to permanently delete {selected_count} record(s) marked as 'Removed'.")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Delete", type="primary", use_container_width=True):
                            self._delete_selected_records(st.session_state.selected_consignment_records)
                    
                    with col2:
                        if st.button("❌ Cancel", type="secondary", use_container_width=True):
                            st.session_state.selected_consignment_records = []
                            st.rerun()
                
                elif selected_status == '✅ Active' or selected_status == '🆕 New':
                    # Show mark as removed option for active/new records
                    action = "deactivate" if selected_status == '✅ Active' else "mark as removed"
                    st.warning(f"You are about to {action} {selected_count} record(s). This will mark them as 'Removed'.")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Mark as Removed", type="primary", use_container_width=True):
                            self._mark_as_removed(st.session_state.selected_consignment_records)
                    
                    with col2:
                        if st.button("❌ Cancel", type="secondary", use_container_width=True):
                            st.session_state.selected_consignment_records = []
                            st.rerun()
                
                elif selected_status == '💰 Sold':
                    st.info("Sold records cannot be modified.")
                    if st.button("❌ Clear Selection", type="secondary", use_container_width=True):
                        st.session_state.selected_consignment_records = []
                        st.rerun()
    
    def _render_payout_requests(self):
        """Render payout requests table for admin"""
        st.subheader("💰 Payout Requests")
        
        # Get all users with payout requested
        users = self.api_client.get_all_users()
        
        payout_requests = []
        for user in users:
            if user.get('payout_requested') and user.get('store_credit_balance', 0) > 0:
                payout_requests.append(user)
        
        if not payout_requests:
            st.info("No pending payout requests.")
            return
        
        # Create table
        st.write(f"**Pending Payouts:** {len(payout_requests)}")
        
        for user in payout_requests:
            with st.expander(f"{user.get('username')} - ${user.get('store_credit_balance', 0):.2f}", expanded=True):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**Name:** {user.get('full_name', 'Not provided')}")
                    st.write(f"**Email:** {user.get('email', 'Not provided')}")
                    st.write(f"**Phone:** {user.get('phone', 'Not provided')}")
                
                with col2:
                    st.write(f"**Address:**")
                    address = user.get('address', 'Not provided')
                    if address and address != 'Not provided':
                        st.text(address)
                    else:
                        st.write("Not provided")
                    st.write(f"**Credit Balance:** ${user.get('store_credit_balance', 0):.2f}")
                
                with col3:
                    if st.button("✅ Process Payout", key=f"process_{user['id']}", use_container_width=True):
                        if self._process_payout(user['id']):
                            st.success(f"✅ Payout processed for {user.get('username')}")
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to process payout")
    
    def _request_payout(self, user_id):
        """Request payout for a user"""
        try:
            response = requests.put(
                f"{self.api_client.base_url}/users/{user_id}/request-payout",
                json={'payout_requested': True}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error requesting payout: {e}")
            return False
    
    def _process_payout(self, user_id):
        """Process payout and clear user's credit balance"""
        try:
            # Get user info to get current balance
            user_info = self.api_client.get_user(user_id)
            if not user_info:
                return False
            
            credit_balance = user_info.get('store_credit_balance', 0)
            
            # Update user - clear balance and remove payout request
            response = requests.put(
                f"{self.api_client.base_url}/users/{user_id}/process-payout",
                json={
                    'store_credit_balance': 0,
                    'payout_requested': False,
                    'original_payout_amount': credit_balance
                }
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error processing payout: {e}")
            return False
    
    def _mark_as_removed(self, record_ids):
        """Mark selected records as removed (status_id = 4)"""
        if not record_ids:
            st.error("No records selected")
            return
        
        success_count = 0
        failed_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, record_id in enumerate(record_ids):
            status_text.text(f"Marking record {i+1}/{len(record_ids)} (ID: {record_id}) as removed...")
            
            # Make API call to update record status to removed (4)
            success = self.api_client.update_record_status(record_id, 4)
            
            if success:
                success_count += 1
            else:
                failed_count += 1
            
            progress_bar.progress((i + 1) / len(record_ids))
        
        progress_bar.empty()
        status_text.empty()
        
        if success_count > 0:
            st.success(f"✅ Successfully marked {success_count} record(s) as removed!")
        
        if failed_count > 0:
            st.error(f"❌ Failed to mark {failed_count} record(s) as removed")
        
        # Clear selection
        st.session_state.selected_consignment_records = []
        st.session_state.select_all_consignment = False
        
        # Rerun to refresh data
        st.rerun()
    
    def _delete_selected_records(self, record_ids):
        """Permanently delete selected records from database"""
        if not record_ids:
            st.error("No records selected")
            return
        
        success_count = 0
        failed_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, record_id in enumerate(record_ids):
            status_text.text(f"Deleting record {i+1}/{len(record_ids)} (ID: {record_id})...")
            
            # Make API call to delete record
            success = self.api_client.delete_record(record_id)
            
            if success:
                success_count += 1
            else:
                failed_count += 1
            
            progress_bar.progress((i + 1) / len(record_ids))
        
        progress_bar.empty()
        status_text.empty()
        
        if success_count > 0:
            st.success(f"✅ Successfully deleted {success_count} record(s)!")
        
        if failed_count > 0:
            st.error(f"❌ Failed to delete {failed_count} record(s)")
        
        # Clear selection
        st.session_state.selected_consignment_records = []
        st.session_state.select_all_consignment = False
        
        # Rerun to refresh data
        st.rerun()

class APIClient:
    """API client for consignment operations"""
    
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
    
    def get_all_users(self):
        """Get all users"""
        try:
            response = requests.get(f"{self.base_url}/users")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('users', [])
            return []
        except Exception as e:
            st.error(f"API Error getting users: {e}")
            return []
    
    def update_record_status(self, record_id, status_id):
        """Update a record's status via API"""
        try:
            response = requests.put(
                f"{self.base_url}/records/{record_id}",
                json={'status_id': status_id}
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"API Error updating record status: {e}")
            return False
    
    def delete_record(self, record_id):
        """Delete a record via API"""
        try:
            response = requests.delete(f"{self.base_url}/records/{record_id}")
            return response.status_code == 200
        except Exception as e:
            st.error(f"API Error deleting record: {e}")
            return False
    
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