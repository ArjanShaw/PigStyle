import streamlit as st
import pandas as pd
import requests
from datetime import datetime

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
        is_demo = user.get('username') == 'demo_user'
        
        if not user_id and not is_demo:
            st.warning("Please log in to view consignment information.")
            return
        
        if is_demo:
            st.info("👀 **Demo Mode**: You can simulate consignment operations in demo mode.")
            # Use demo user ID
            user_id = 999
        
        # NEW: Contract management section
        if user_role == 'consignor' or is_demo:
            with st.expander("📄 Contract & Receipt Management", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📝 Generate New Contract", width='stretch', 
                               help="Generate a new consignment agreement contract"):
                        if is_demo:
                            st.success("✅ Demo: Contract generated!")
                            st.info("💡 In real mode, this would generate a downloadable PDF contract with your terms.")
                            st.info("Contract includes: 180-day term, commission rates, pricing rules, and liability terms.")
                        else:
                            # In real mode, this would generate contract
                            st.info("Contract generation is available when printing price tags in the '🏷️ Print Price Tags' tab.")
                            st.info("Go to Print Price Tags, select your records, and generate contract + receipt together.")
                
                with col2:
                    if st.button("📋 View Receipt History", width='stretch',
                               help="View past batch receipts and consignment records"):
                        if is_demo:
                            # Show demo receipt history
                            with st.expander("📋 Demo Receipt History", expanded=True):
                                st.write("**Sample Receipts:**")
                                demo_receipts = [
                                    {"Date": "2024-01-15", "Receipt #": "PS20240115001", "Items": 5, "Value": "$174.95", "Status": "Active"},
                                    {"Date": "2023-12-10", "Receipt #": "PS20231210003", "Items": 3, "Value": "$89.97", "Status": "Paid"},
                                    {"Date": "2023-11-05", "Receipt #": "PS20231105002", "Items": 2, "Value": "$49.98", "Status": "Expired"}
                                ]
                                st.dataframe(pd.DataFrame(demo_receipts), hide_index=True)
                        else:
                            st.info("Receipt history would show your past consignment batches")
        
        # Show consignor's credit balance at the top
        if user_role == 'consignor' or is_demo:
            if is_demo:
                # Demo user balance - CALCULATE FROM SOLD RECORDS
                demo_records = self._get_demo_consignment_records()
                sold_records = [r for r in demo_records if r.get('status_id') == 3]
                
                # Calculate total from sold records
                total_sales = sum(float(r.get('store_price', 0)) for r in sold_records)
                commission = total_sales * 0.20  # 20% commission
                credit_balance = total_sales - commission
                
                # Store for use in Last Added display
                st.session_state.demo_credit_balance = credit_balance
                
                st.success(f"💰 **Your Credit Balance: ${credit_balance:.2f}**")
                st.info("💡 **Demo**: This balance comes from sold consignment items (20% commission).")
                
                # Request payout button for demo
                if credit_balance > 0:
                    if st.button("💰 Request Payout (Demo)", type="primary"):
                        st.success("✅ Demo: Payout request submitted! In real operation, this would notify store admin.")
                        st.info("💡 The store admin would confirm with an email and sent you a check.")
            else:
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
                                st.info("💡 The store admin would confirm with an email and sent you a check.")
                                st.rerun()
                    elif payout_requested:
                        st.info("⏳ Payout request pending admin approval")
        
        # Show payout requests table for admin
        if user_role == 'admin' and not is_demo:
            self._render_payout_requests()
        
        # Get consignment records
        if is_demo:
            records = self._get_demo_consignment_records()
        else:
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
        if user_role == 'admin' and not is_demo:
            consignor_names = {}
            for consignor_id in consignment_df['consignor_id'].unique():
                user_info = self.api_client.get_user(int(consignor_id))
                if user_info:
                    consignor_names[consignor_id] = user_info.get('username', f"ID: {consignor_id}")
            
            consignment_df['consignor'] = consignment_df['consignor_id'].map(consignor_names)
        
        # Determine display status based on status_id
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
        
        # Split into separate tables
        new_df = consignment_df[consignment_df['display_status'] == '🆕 New'].copy()
        active_df = consignment_df[consignment_df['display_status'] == '✅ Active'].copy()
        sold_df = consignment_df[consignment_df['display_status'] == '💰 Sold'].copy()
        removed_df = consignment_df[consignment_df['display_status'] == '🗑️ Removed'].copy()
        
        # Display tables in order, only if they have records
        if not new_df.empty:
            self._render_consignment_table("🆕 New Records", new_df, user_role, is_demo)
        
        if not active_df.empty:
            self._render_consignment_table("✅ Active Records", active_df, user_role, is_demo)
        
        if not sold_df.empty:
            self._render_sold_table("💰 Sold Records", sold_df, user_role, is_demo)
        
        if not removed_df.empty:
            self._render_removed_table("🗑️ Removed Records - Ready for Pickup", removed_df, user_role, is_demo)
    
    def _render_consignment_table(self, title, df, user_role, is_demo):
        """Render a consignment table with selection and actions"""
        st.subheader(title)
        
        # Only show selection controls for active/new records (not for removed records)
        # Consignors can remove their own active/new records
        if user_role == 'consignor' and title in ['🆕 New Records', '✅ Active Records']:
            # Selection controls
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button(f"✅ Select All {title.split()[0]}", key=f"select_all_{title}"):
                    st.session_state.select_all_consignment = True
                    st.session_state.selected_consignment_records = df['record_id'].tolist()
                    st.rerun()
            
            with col2:
                selected_count = len([r for r in st.session_state.selected_consignment_records if r in df['record_id'].tolist()])
                if selected_count > 0:
                    st.write(f"**{selected_count} records selected**")
        
        # Create editable DataFrame with checkboxes
        display_data = []
        
        for idx, record in df.iterrows():
            record_id = record['record_id']
            
            # Determine if this record should be selected
            is_selected = record_id in st.session_state.selected_consignment_records
            
            display_row = {
                'Select': is_selected,
                'ID': record_id,
                'Status': record['display_status']
            }
            
            if user_role == 'admin' and not is_demo:
                display_row['Consignor'] = record.get('consignor', f"ID: {record.get('consignor_id')}")
            
            display_row['Artist'] = record['artist']
            display_row['Title'] = record['title']
            display_row['Price'] = f"${record['store_price']:.2f}"
            
            # Show receipt number if available
            if record.get('receipt_number'):
                display_row['Receipt #'] = record['receipt_number']
            
            display_data.append(display_row)
        
        # Create DataFrame for display
        display_df = pd.DataFrame(display_data)
        
        # Configure columns - disable select column for admin viewing other users' records
        column_config = {
            "Select": st.column_config.CheckboxColumn("Select", default=False),
            "ID": st.column_config.NumberColumn("ID", disabled=True),
            "Status": st.column_config.TextColumn("Status", disabled=True),
            "Artist": st.column_config.TextColumn("Artist", disabled=True),
            "Title": st.column_config.TextColumn("Title", disabled=True),
            "Price": st.column_config.TextColumn("Price", disabled=True),
        }
        
        if user_role == 'admin' and not is_demo:
            column_config["Consignor"] = st.column_config.TextColumn("Consignor", disabled=True)
        
        if 'Receipt #' in display_df.columns:
            column_config["Receipt #"] = st.column_config.TextColumn("Receipt #", disabled=True)
        
        # Determine if select column should be disabled
        disabled_columns = [col for col in column_config.keys() if col != "Select"]
        
        # If user is consignor and this is active/new records table, allow selection
        if user_role == 'consignor' and title in ['🆕 New Records', '✅ Active Records']:
            # Keep select column enabled for consignors
            pass
        else:
            # Disable select column for all other cases
            disabled_columns.append("Select")
        
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            hide_index=True,
            width='stretch',
            key=f"consignment_table_{title}",
            disabled=disabled_columns
        )
        
        # Update selected records based on user selection (only for consignors on active/new records)
        if user_role == 'consignor' and title in ['🆕 New Records', '✅ Active Records']:
            new_selected_records = []
            for idx, row in edited_df.iterrows():
                if row['Select']:
                    record_id = row['ID']
                    new_selected_records.append(record_id)
            
            # Update session state for records in this table
            current_table_ids = df['record_id'].tolist()
            other_selected = [r for r in st.session_state.selected_consignment_records if r not in current_table_ids]
            st.session_state.selected_consignment_records = other_selected + new_selected_records
        
        # Check if we have selected records in this table
        table_selected_records = [r for r in st.session_state.selected_consignment_records if r in current_table_ids]
        
        if table_selected_records:
            selected_count = len(table_selected_records)
            
            # Show remove from consignment option for active/new records (only for consignors)
            if user_role == 'consignor' and title in ['🆕 New Records', '✅ Active Records']:
                st.warning(f"You are about to remove {selected_count} record(s) from consignment.")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🗑️ Remove from Consignment", type="primary", width='stretch'):
                        self._mark_as_removed(table_selected_records, is_demo)
                with col2:
                    if st.button("❌ Clear Selection", type="secondary", width='stretch'):
                        st.session_state.selected_consignment_records = [
                            r for r in st.session_state.selected_consignment_records 
                            if r not in table_selected_records
                        ]
                        st.rerun()
    
    def _render_sold_table(self, title, df, user_role, is_demo):
        """Render sold records table WITHOUT checkboxes"""
        st.subheader(title)
        
        # Create display data WITHOUT select column
        display_data = []
        
        for idx, record in df.iterrows():
            display_row = {
                'ID': record['record_id'],
                'Status': record['display_status']
            }
            
            if user_role == 'admin' and not is_demo:
                display_row['Consignor'] = record.get('consignor', f"ID: {record.get('consignor_id')}")
            
            display_row['Artist'] = record['artist']
            display_row['Title'] = record['title']
            display_row['Price'] = f"${record['store_price']:.2f}"
            
            # Add date sold if available
            if record.get('date_sold'):
                display_row['Date Sold'] = record['date_sold']
            
            # Show receipt number if available
            if record.get('receipt_number'):
                display_row['Receipt #'] = record['receipt_number']
            
            display_data.append(display_row)
        
        # Create DataFrame for display
        display_df = pd.DataFrame(display_data)
        
        # Configure columns (NO SELECT COLUMN)
        column_config = {
            "ID": st.column_config.NumberColumn("ID", disabled=True),
            "Status": st.column_config.TextColumn("Status", disabled=True),
            "Artist": st.column_config.TextColumn("Artist", disabled=True),
            "Title": st.column_config.TextColumn("Title", disabled=True),
            "Price": st.column_config.TextColumn("Price", disabled=True),
        }
        
        if user_role == 'admin' and not is_demo:
            column_config["Consignor"] = st.column_config.TextColumn("Consignor", disabled=True)
        
        if 'Date Sold' in display_df.columns:
            column_config["Date Sold"] = st.column_config.DateColumn("Date Sold", disabled=True)
        
        if 'Receipt #' in display_df.columns:
            column_config["Receipt #"] = st.column_config.TextColumn("Receipt #", disabled=True)
        
        st.data_editor(
            display_df,
            column_config=column_config,
            hide_index=True,
            width='stretch',
            key=f"sold_table_{title}",
            disabled=True  # Entire table is disabled
        )
    
    def _render_removed_table(self, title, df, user_role, is_demo):
        """Render removed records table with special header - NO SELECT COLUMN FOR CONSIGNORS"""
        st.subheader(title)
        st.info("ℹ️ These records have been removed from consignment. Please pick up within 30 days.")
        
        # Create display data WITHOUT select column for consignors
        # Only include select column for admin users
        display_data = []
        
        for idx, record in df.iterrows():
            record_id = record['record_id']
            
            # Initialize display row
            display_row = {
                'ID': record_id,
                'Status': record['display_status']
            }
            
            # Only add select column for admin users
            if user_role == 'admin' and not is_demo:
                # Determine if this record should be selected
                is_selected = record_id in st.session_state.selected_consignment_records
                display_row['Select'] = is_selected
            
            if user_role == 'admin' and not is_demo:
                display_row['Consignor'] = record.get('consignor', f"ID: {record.get('consignor_id')}")
            
            display_row['Artist'] = record['artist']
            display_row['Title'] = record['title']
            display_row['Price'] = f"${record['store_price']:.2f}"
            
            # Add receipt number if available
            if record.get('receipt_number'):
                display_row['Receipt #'] = record['receipt_number']
            
            # Add date removed if available
            if record.get('date_removed'):
                display_row['Date Removed'] = record['date_removed']
            
            display_data.append(display_row)
        
        # Create DataFrame for display
        display_df = pd.DataFrame(display_data)
        
        # Configure columns based on user role
        if user_role == 'admin' and not is_demo:
            column_config = {
                "Select": st.column_config.CheckboxColumn("Select", default=False),
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "Status": st.column_config.TextColumn("Status", disabled=True),
                "Artist": st.column_config.TextColumn("Artist", disabled=True),
                "Title": st.column_config.TextColumn("Title", disabled=True),
                "Price": st.column_config.TextColumn("Price", disabled=True),
            }
            
            if 'Consignor' in display_df.columns:
                column_config["Consignor"] = st.column_config.TextColumn("Consignor", disabled=True)
            
            if 'Receipt #' in display_df.columns:
                column_config["Receipt #"] = st.column_config.TextColumn("Receipt #", disabled=True)
            
            if 'Date Removed' in display_df.columns:
                column_config["Date Removed"] = st.column_config.DateColumn("Date Removed", disabled=True)
            
            # Only disable non-select columns for admin
            disabled_columns = [col for col in column_config.keys() if col != "Select"]
        else:
            # For consignors, don't include select column at all
            column_config = {
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "Status": st.column_config.TextColumn("Status", disabled=True),
                "Artist": st.column_config.TextColumn("Artist", disabled=True),
                "Title": st.column_config.TextColumn("Title", disabled=True),
                "Price": st.column_config.TextColumn("Price", disabled=True),
            }
            
            if 'Receipt #' in display_df.columns:
                column_config["Receipt #"] = st.column_config.TextColumn("Receipt #", disabled=True)
            
            if 'Date Removed' in display_df.columns:
                column_config["Date Removed"] = st.column_config.DateColumn("Date Removed", disabled=True)
            
            # Disable all columns for consignors
            disabled_columns = list(column_config.keys())
        
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            hide_index=True,
            width='stretch',
            key=f"removed_table_{title}",
            disabled=disabled_columns
        )
        
        # Update selected records based on user selection (only for admin)
        if user_role == 'admin' and not is_demo:
            new_selected_records = []
            for idx, row in edited_df.iterrows():
                if row['Select']:
                    record_id = row['ID']
                    new_selected_records.append(record_id)
            
            # Update session state for records in this table
            current_table_ids = df['record_id'].tolist()
            other_selected = [r for r in st.session_state.selected_consignment_records if r not in current_table_ids]
            st.session_state.selected_consignment_records = other_selected + new_selected_records
        
        # Check if we have selected records in this table (only for admin)
        table_selected_records = [r for r in st.session_state.selected_consignment_records if r in df['record_id'].tolist()]
        
        if table_selected_records and user_role == 'admin' and not is_demo:
            selected_count = len(table_selected_records)
            
            # Show delete option for removed records (only for admin)
            st.warning(f"You are about to permanently delete {selected_count} record(s) marked as 'Removed'.")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Delete", type="primary", width='stretch'):
                    self._delete_selected_records(table_selected_records, is_demo)
            with col2:
                if st.button("❌ Clear Selection", type="secondary", width='stretch'):
                    st.session_state.selected_consignment_records = [
                        r for r in st.session_state.selected_consignment_records 
                        if r not in table_selected_records
                    ]
                    st.rerun()
        elif user_role == 'consignor' and 'Select' in display_df.columns:
            # Clear any accidental selection by consignors
            st.session_state.selected_consignment_records = [
                r for r in st.session_state.selected_consignment_records 
                if r not in df['record_id'].tolist()
            ]
    
    def _get_demo_consignment_records(self):
        """Create demo consignment records with real artist/title combinations"""
        # Use session state to persist demo records
        if 'demo_consignment_records' not in st.session_state or st.session_state.demo_consignment_records is None:
            # Initial demo records
            demo_records = [
                {
                    'id': 1001,
                    'artist': 'The Beatles',
                    'title': 'Abbey Road',
                    'store_price': 34.99,
                    'consignor_id': 999,
                    'commission_rate': 0.20,
                    'status_id': 1,
                    'barcode': '077774644121',
                    'display_status': '✅ Active',
                    'genre_name': 'Rock',
                    'catalog_number': 'PCS 7088',
                    'created_at': '2024-01-15',
                    'receipt_number': 'PS20240115001'
                },
                {
                    'id': 1002,
                    'artist': 'Miles Davis',
                    'title': 'Kind of Blue',
                    'store_price': 29.99,
                    'consignor_id': 999,
                    'commission_rate': 0.20,
                    'status_id': 1,
                    'barcode': '074646300322',
                    'display_status': '✅ Active',
                    'genre_name': 'Jazz',
                    'catalog_number': 'CL 1355',
                    'created_at': '2024-01-10',
                    'receipt_number': 'PS20240110002'
                },
                {
                    'id': 1003,
                    'artist': 'Pink Floyd',
                    'title': 'The Dark Side of the Moon',
                    'store_price': 39.99,
                    'consignor_id': 999,
                    'commission_rate': 0.20,
                    'status_id': 3,  # Sold status
                    'barcode': '077774644421',
                    'display_status': '💰 Sold',
                    'genre_name': 'Progressive Rock',
                    'catalog_number': 'SHVL 804',
                    'created_at': '2023-12-20',
                    'date_sold': '2024-01-05',
                    'receipt_number': 'PS20231220003'
                },
                {
                    'id': 1004,
                    'artist': 'Nirvana',
                    'title': 'Nevermind',
                    'store_price': 24.99,
                    'consignor_id': 999,
                    'commission_rate': 0.20,
                    'status_id': 4,  # Removed status
                    'barcode': '072064244251',
                    'display_status': '🗑️ Removed',
                    'genre_name': 'Grunge',
                    'catalog_number': 'GEF 24425',
                    'created_at': '2023-11-15',
                    'date_removed': '2024-01-01',
                    'receipt_number': 'PS20231115004'
                },
                {
                    'id': 1005,
                    'artist': 'Radiohead',
                    'title': 'OK Computer',
                    'store_price': 27.99,
                    'consignor_id': 999,
                    'commission_rate': 0.20,
                    'status_id': 4,  # Removed status
                    'barcode': '724385467421',
                    'display_status': '🗑️ Removed',
                    'genre_name': 'Alternative Rock',
                    'catalog_number': '7243 8 55229 2 6',
                    'created_at': '2023-10-20',
                    'date_removed': '2023-12-15',
                    'receipt_number': 'PS20231020005'
                }
            ]
            
            # Store in session state
            st.session_state.demo_consignment_records = demo_records
        
        return st.session_state.demo_consignment_records
    
    def _update_demo_record_status(self, record_ids, new_status_id):
        """Update status of demo records"""
        if 'demo_consignment_records' not in st.session_state or st.session_state.demo_consignment_records is None:
            return False
        
        updated = False
        for record in st.session_state.demo_consignment_records:
            if record['id'] in record_ids:
                # Update status
                record['status_id'] = new_status_id
                
                # Update display status
                if new_status_id == 1:
                    record['display_status'] = '🆕 New'
                elif new_status_id == 2:
                    record['display_status'] = '✅ Active'
                elif new_status_id == 3:
                    record['display_status'] = '💰 Sold'
                elif new_status_id == 4:
                    record['display_status'] = '🗑️ Removed'
                    # Add removal date if not present
                    if 'date_removed' not in record:
                        record['date_removed'] = datetime.now().date().isoformat()
                
                updated = True
        
        return updated
    
    def _delete_demo_records(self, record_ids):
        """Delete demo records"""
        if 'demo_consignment_records' not in st.session_state or st.session_state.demo_consignment_records is None:
            return False
        
        # Filter out records to delete
        st.session_state.demo_consignment_records = [
            record for record in st.session_state.demo_consignment_records 
            if record['id'] not in record_ids
        ]
        
        return True
    
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
                    if st.button("✅ Process Payout", key=f"process_{user['id']}", width='stretch'):
                        if self._process_payout(user['id']):
                            st.success(f"✅ Payout processed for {user.get('username')}")
                            st.info("💡 Email confirmation sent and check mailed to consignor.")
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to process payout")
    
    def _request_payout(self, user_id):
        """Request payout for a user"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would request payout for user {user_id}")
            return True
            
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
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would process payout for user {user_id}")
            return True
            
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
    
    def _mark_as_removed(self, record_ids, is_demo=False):
        """Mark selected records as removed (status_id = 4)"""
        if not record_ids:
            st.error("No records selected")
            return
        
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        success_count = 0
        failed_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, record_id in enumerate(record_ids):
            status_text.text(f"Removing record {i+1}/{len(record_ids)} (ID: {record_id}) from consignment...")
            
            if is_demo:
                # Demo mode - update demo record status
                success = self._update_demo_record_status([record_id], 4)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            else:
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
            st.success(f"✅ Successfully removed {success_count} record(s) from consignment!")
            st.info("📝 Removed from consignment, please pick up item(s) within 30 days")
        
        if failed_count > 0:
            st.error(f"❌ Failed to remove {failed_count} record(s) from consignment")
        
        # Clear selection
        st.session_state.selected_consignment_records = [
            r for r in st.session_state.selected_consignment_records if r not in record_ids
        ]
        st.session_state.select_all_consignment = False
        
        # Rerun to refresh data
        st.rerun()
    
    def _delete_selected_records(self, record_ids, is_demo=False):
        """Permanently delete selected records from database"""
        if not record_ids:
            st.error("No records selected")
            return
        
        user = st.session_state.get('user', {})
        user_role = user.get('role')
        is_demo = user.get('username') == 'demo_user'
        
        # Only admin can delete records
        if user_role != 'admin' and not is_demo:
            st.error("❌ Only administrators can delete records.")
            return
        
        success_count = 0
        failed_count = 0
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, record_id in enumerate(record_ids):
            status_text.text(f"Deleting record {i+1}/{len(record_ids)} (ID: {record_id})...")
            
            if is_demo:
                # Demo mode - delete from demo records
                success = self._delete_demo_records([record_id])
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            else:
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
        st.session_state.selected_consignment_records = [
            r for r in st.session_state.selected_consignment_records if r not in record_ids
        ]
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
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would update record {record_id} status to {status_id}")
            return True
            
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
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would delete record {record_id}")
            return True
            
        try:
            response = requests.delete(f"{self.base_url}/records/{record_id}")
            return response.status_code == 200
        except Exception as e:
            st.error(f"API Error deleting record: {e}")
            return False
    
    def update_record(self, record_id, updates):
        """Update a record via API"""
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would update record {record_id} with {updates}")
            return True
            
        try:
            response = requests.put(
                f"{self.base_url}/records/{record_id}",
                json=updates
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"API Error updating record: {e}")
            return False