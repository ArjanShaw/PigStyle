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
        st.title("🎵 Consignment Management")
        
        user = st.session_state.get('user', {})
        user_id = user.get('id')
        user_role = user.get('role', 'consignor')
        
        if not user_id:
            st.warning("Please log in to view consignment information.")
            return
        
        # Get consignment records
        if user_role == 'admin':
            response = requests.get(f"{self.api_client.base_url}/records?limit=1000")
        else:
            response = requests.get(f"{self.api_client.base_url}/records/user/{user_id}")
        
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
        
        # Add status column based on barcode and deactivated values
        def determine_status(row):
            barcode = row.get('barcode')
            deactivated = row.get('deactivated', 0)
            
            # Check if barcode is null, empty, or 'None'
            if pd.isna(barcode) or barcode in [None, '', 'None']:
                return '🆕 New'
            elif deactivated == 1:
                return '🗑️ Removed'
            else:
                return '✅ Active'
        
        consignment_df['status'] = consignment_df.apply(determine_status, axis=1)
        
        # Add record ID to session state for selection
        consignment_df['record_id'] = consignment_df['id']
        
        # Filter options
        st.subheader("Consignment Records")
        
        filter_cols = st.columns(3)
        with filter_cols[0]:
            show_new = st.checkbox("🆕 New", value=True, key="show_new")
        with filter_cols[1]:
            show_active = st.checkbox("✅ Active", value=True, key="show_active")
        with filter_cols[2]:
            show_removed = st.checkbox("🗑️ Removed", value=True, key="show_removed")
        
        # Apply filters
        selected_statuses = []
        if show_new:
            selected_statuses.append('🆕 New')
        if show_active:
            selected_statuses.append('✅ Active')
        if show_removed:
            selected_statuses.append('🗑️ Removed')
        
        filtered_df = consignment_df[consignment_df['status'].isin(selected_statuses)] if selected_statuses else consignment_df
        
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
                st.write(f"**{selected_count} records selected**")
        
        # Create editable DataFrame with checkboxes
        display_data = []
        
        for idx, record in filtered_df.iterrows():
            record_id = record['record_id']
            
            # Determine if this record should be selected
            is_selected = record_id in st.session_state.selected_consignment_records
            
            display_row = {
                'Select': is_selected,
                'ID': record_id,
                'Status': record['status']
            }
            
            if user_role == 'admin':
                display_row['Consignor'] = record.get('consignor', f"ID: {record.get('consignor_id')}")
            
            display_row['Artist'] = record['artist']
            display_row['Title'] = record['title']
            display_row['Price'] = f"${record['store_price']:.2f}"
            
            # Store original row data for reference
            display_row['_original_row'] = record
            
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
        
        # Update session state if selection changed
        if set(new_selected_records) != set(st.session_state.selected_consignment_records):
            st.session_state.selected_consignment_records = new_selected_records
            st.rerun()
        
        # Bulk deactivate button
        if st.session_state.selected_consignment_records:
            selected_count = len(st.session_state.selected_consignment_records)
            st.warning(f"You are about to deactivate {selected_count} record(s). This will mark them as 'Removed'.")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Deactivate", type="primary", use_container_width=True):
                    self._deactivate_selected_records(st.session_state.selected_consignment_records)
            
            with col2:
                if st.button("❌ Cancel", type="secondary", use_container_width=True):
                    st.session_state.selected_consignment_records = []
                    st.rerun()
    
    def _deactivate_selected_records(self, record_ids):
        """Deactivate selected records by setting deactivated = 1"""
        if not record_ids:
            st.error("No records selected")
            return
        
        success_count = 0
        failed_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, record_id in enumerate(record_ids):
            status_text.text(f"Deactivating record {i+1}/{len(record_ids)} (ID: {record_id})...")
            
            # Make API call to update record
            success = self.api_client.update_record(record_id, {'deactivated': 1})
            
            if success:
                success_count += 1
            else:
                failed_count += 1
            
            progress_bar.progress((i + 1) / len(record_ids))
        
        progress_bar.empty()
        status_text.empty()
        
        if success_count > 0:
            st.success(f"✅ Successfully deactivated {success_count} record(s)!")
        
        if failed_count > 0:
            st.error(f"❌ Failed to deactivate {failed_count} record(s)")
        
        # Clear selection
        st.session_state.selected_consignment_records = []
        st.session_state.select_all_consignment = False
        
        # Rerun to refresh data
        st.rerun()

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