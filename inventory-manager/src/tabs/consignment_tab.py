import streamlit as st
import pandas as pd
import requests
from datetime import datetime

class ConsignmentTab:
    def __init__(self):
        self.api_client = APIClient()
        
        if 'selected_consignment_records' not in st.session_state:
            st.session_state.selected_consignment_records = []
        
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
            user_id = 999
        
        # ONLY SHOW CONTRACT/RECEIPT MANAGEMENT FOR ADMINS
        if user_role == 'admin' and not is_demo:
            with st.expander("📄 Contract & Receipt Management (Admin Only)", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📝 Generate New Contract", width='stretch', 
                               help="Generate a new consignment agreement contract"):
                        st.info("Contract generation is available when printing price tags in the '🏷️ Print Price Tags' tab.")
                        st.info("Go to Print Price Tags, select your records, and generate contract + receipt together.")
                
                with col2:
                    if st.button("📋 View Receipt History", width='stretch',
                               help="View past batch receipts and consignment records"):
                        st.info("Receipt history would show all past consignment batches")
        
        if user_role == 'consignor' or is_demo:
            if is_demo:
                demo_records = self._get_demo_consignment_records()
                sold_records = [r for r in demo_records if r.get('status_id') == 3]
                
                total_sales = sum(float(r.get('store_price', 0)) for r in sold_records)
                commission = total_sales * 0.20
                credit_balance = total_sales - commission
                
                st.session_state.demo_credit_balance = credit_balance
                
                st.success(f"💰 **Your Credit Balance: ${credit_balance:.2f}**")
                st.info("💡 **Demo**: This balance comes from sold consignment items (20% commission).")
                
                if credit_balance > 0:
                    if st.button("💰 Request Payout (Demo)", type="primary"):
                        st.success("✅ Demo: Payout request submitted! In real operation, this would notify store admin.")
                        st.info("💡 The store admin would confirm with an email and sent you a check.")
            else:
                user_info = self.api_client.get_user(user_id)
                if user_info:
                    credit_balance = user_info.get('store_credit_balance', 0)
                    payout_requested = user_info.get('payout_requested', False)
                    
                    if credit_balance > 0:
                        st.success(f"💰 **Your Credit Balance: ${credit_balance:.2f}**")
                    else:
                        st.info(f"💳 **Your Credit Balance: ${credit_balance:.2f}**")
                    
                    if credit_balance > 0 and not payout_requested:
                        if st.button("💰 Request Payout", type="primary"):
                            if self._request_payout(user_id):
                                st.success("✅ Payout request submitted! It will be processed by admin.")
                                st.info("💡 The store admin would confirm with an email and sent you a check.")
                                st.session_state.needs_refresh = True
                                st.stop()
                    elif payout_requested:
                        st.info("⏳ Payout request pending admin approval")
        
        if user_role == 'admin' and not is_demo:
            self._render_payout_requests()
        
        if is_demo:
            records = self._get_demo_consignment_records()
        else:
            if user_role == 'admin':
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
        
        df = pd.DataFrame(records)
        
        consignment_df = df[df['consignor_id'].notna()].copy()
        
        if consignment_df.empty:
            st.info("No consignment records found (all records are store-owned).")
            return
        
        if user_role == 'admin' and not is_demo:
            consignor_names = {}
            for consignor_id in consignment_df['consignor_id'].unique():
                user_info = self.api_client.get_user(int(consignor_id))
                if user_info:
                    consignor_names[consignor_id] = user_info.get('username', f"ID: {consignor_id}")
            
            consignment_df['consignor'] = consignment_df['consignor_id'].map(consignor_names)
        
        def determine_display_status(row):
            status_id = row.get('status_id', 1)
            
            # SIMPLIFIED LOGIC - only use status_id, not barcode
            if status_id == 1:
                return '🆕 Ready for Dropoff'
            elif status_id == 2:
                return '✅ Active (On Shelf)'
            elif status_id == 3:
                return '💰 Sold'
            elif status_id == 4:
                return '🗑️ Removed (Pickup Required)'
            else:
                return '❓ Unknown'
        
        consignment_df['display_status'] = consignment_df.apply(determine_display_status, axis=1)
        
        consignment_df['record_id'] = consignment_df['id']
        
        new_df = consignment_df[consignment_df['display_status'] == '🆕 Ready for Dropoff'].copy()
        active_df = consignment_df[consignment_df['display_status'] == '✅ Active (On Shelf)'].copy()
        sold_df = consignment_df[consignment_df['display_status'] == '💰 Sold'].copy()
        removed_df = consignment_df[consignment_df['display_status'] == '🗑️ Removed (Pickup Required)'].copy()
        
        if not new_df.empty:
            self._render_consignment_table("🆕 Ready for Dropoff", new_df, user_role, is_demo)
        
        if not active_df.empty:
            self._render_consignment_table("✅ Active (On Shelf)", active_df, user_role, is_demo)
        
        if not sold_df.empty:
            self._render_sold_table("💰 Sold Records", sold_df, user_role, is_demo)
        
        if not removed_df.empty:
            self._render_removed_table("🗑️ Removed Records - Pickup Required", removed_df, user_role, is_demo)
    
    def _render_consignment_table(self, title, df, user_role, is_demo):
        st.subheader(title)
        
        if user_role == 'consignor' and title in ['🆕 Ready for Dropoff', '✅ Active (On Shelf)']:
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button(f"✅ Select All {title.split()[0]}", key=f"select_all_{title}"):
                    st.session_state.select_all_consignment = True
                    st.session_state.selected_consignment_records = df['record_id'].tolist()
                    st.session_state.needs_refresh = True
                    st.stop()
            
            with col2:
                selected_count = len([r for r in st.session_state.selected_consignment_records if r in df['record_id'].tolist()])
                if selected_count > 0:
                    st.write(f"**{selected_count} records selected**")
        
        display_data = []
        
        for idx, record in df.iterrows():
            record_id = record['record_id']
            
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
            
            if record.get('receipt_number'):
                display_row['Receipt #'] = record['receipt_number']
            
            display_data.append(display_row)
        
        display_df = pd.DataFrame(display_data)
        
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
        
        if user_role == 'consignor' and title in ['🆕 Ready for Dropoff', '✅ Active (On Shelf)']:
            pass
        else:
            column_config["Select"] = st.column_config.CheckboxColumn("Select", default=False, disabled=True)
        
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            hide_index=True,
            width='stretch',
            key=f"consignment_table_{title}",
            disabled=[col for col in column_config.keys() if col != "Select"]
        )
        
        if user_role == 'consignor' and title in ['🆕 Ready for Dropoff', '✅ Active (On Shelf)']:
            new_selected_records = []
            for idx, row in edited_df.iterrows():
                if row['Select']:
                    record_id = row['ID']
                    new_selected_records.append(record_id)
            
            current_table_ids = df['record_id'].tolist()
            other_selected = [r for r in st.session_state.selected_consignment_records if r not in current_table_ids]
            st.session_state.selected_consignment_records = other_selected + new_selected_records
        
        table_selected_records = [r for r in st.session_state.selected_consignment_records if r in current_table_ids]
        
        if table_selected_records:
            selected_count = len(table_selected_records)
            
            if user_role == 'consignor' and title in ['🆕 Ready for Dropoff', '✅ Active (On Shelf)']:
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
                        st.session_state.needs_refresh = True
                        st.stop()
    
    def _render_sold_table(self, title, df, user_role, is_demo):
        st.subheader(title)
        
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
            
            if record.get('date_sold'):
                display_row['Date Sold'] = record['date_sold']
            
            if record.get('receipt_number'):
                display_row['Receipt #'] = record['receipt_number']
            
            display_data.append(display_row)
        
        display_df = pd.DataFrame(display_data)
        
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
            disabled=True
        )
    
    def _render_removed_table(self, title, df, user_role, is_demo):
        st.subheader(title)
        st.info("ℹ️ These records have been removed from consignment. Please pick up within 30 days.")
        
        display_data = []
        
        for idx, record in df.iterrows():
            record_id = record['record_id']
            
            display_row = {
                'ID': record_id,
                'Status': record['display_status']
            }
            
            if user_role == 'admin' and not is_demo:
                is_selected = record_id in st.session_state.selected_consignment_records
                display_row['Select'] = is_selected
            
            if user_role == 'admin' and not is_demo:
                display_row['Consignor'] = record.get('consignor', f"ID: {record.get('consignor_id')}")
            
            display_row['Artist'] = record['artist']
            display_row['Title'] = record['title']
            display_row['Price'] = f"${record['store_price']:.2f}"
            
            if record.get('receipt_number'):
                display_row['Receipt #'] = record['receipt_number']
            
            if record.get('date_removed'):
                display_row['Date Removed'] = record['date_removed']
            
            display_data.append(display_row)
        
        display_df = pd.DataFrame(display_data)
        
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
            
            disabled_columns = [col for col in column_config.keys() if col != "Select"]
        else:
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
            
            disabled_columns = list(column_config.keys())
        
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            hide_index=True,
            width='stretch',
            key=f"removed_table_{title}",
            disabled=disabled_columns
        )
        
        if user_role == 'admin' and not is_demo:
            new_selected_records = []
            for idx, row in edited_df.iterrows():
                if row['Select']:
                    record_id = row['ID']
                    new_selected_records.append(record_id)
            
            current_table_ids = df['record_id'].tolist()
            other_selected = [r for r in st.session_state.selected_consignment_records if r not in current_table_ids]
            st.session_state.selected_consignment_records = other_selected + new_selected_records
        
        table_selected_records = [r for r in st.session_state.selected_consignment_records if r in df['record_id'].tolist()]
        
        if table_selected_records and user_role == 'admin' and not is_demo:
            selected_count = len(table_selected_records)
            
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
                    st.session_state.needs_refresh = True
                    st.stop()
        elif user_role == 'consignor' and 'Select' in display_df.columns:
            st.session_state.selected_consignment_records = [
                r for r in st.session_state.selected_consignment_records 
                if r not in df['record_id'].tolist()
            ]
    
    def _get_demo_consignment_records(self):
        if 'demo_consignment_records' not in st.session_state or st.session_state.demo_consignment_records is None:
            demo_records = [
                {
                    'id': 1001,
                    'artist': 'The Beatles',
                    'title': 'Abbey Road',
                    'store_price': 34.99,
                    'consignor_id': 999,
                    'commission_rate': 0.20,
                    'status_id': 1,  # Ready for Dropoff
                    'barcode': '077774644121',
                    'display_status': '🆕 Ready for Dropoff',
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
                    'status_id': 2,  # Active (On Shelf)
                    'barcode': '074646300322',
                    'display_status': '✅ Active (On Shelf)',
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
                    'status_id': 3,  # Sold
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
                    'status_id': 4,  # Removed
                    'barcode': '072064244251',
                    'display_status': '🗑️ Removed (Pickup Required)',
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
                    'status_id': 4,  # Removed
                    'barcode': '724385467421',
                    'display_status': '🗑️ Removed (Pickup Required)',
                    'genre_name': 'Alternative Rock',
                    'catalog_number': '7243 8 55229 2 6',
                    'created_at': '2023-10-20',
                    'date_removed': '2023-12-15',
                    'receipt_number': 'PS20231020005'
                }
            ]
            
            st.session_state.demo_consignment_records = demo_records
        
        return st.session_state.demo_consignment_records
    
    def _update_demo_record_status(self, record_ids, new_status_id):
        if 'demo_consignment_records' not in st.session_state or st.session_state.demo_consignment_records is None:
            return False
        
        updated = False
        for record in st.session_state.demo_consignment_records:
            if record['id'] in record_ids:
                record['status_id'] = new_status_id
                
                if new_status_id == 1:
                    record['display_status'] = '🆕 Ready for Dropoff'
                elif new_status_id == 2:
                    record['display_status'] = '✅ Active (On Shelf)'
                elif new_status_id == 3:
                    record['display_status'] = '💰 Sold'
                elif new_status_id == 4:
                    record['display_status'] = '🗑️ Removed (Pickup Required)'
                    if 'date_removed' not in record:
                        record['date_removed'] = datetime.now().date().isoformat()
                
                updated = True
        
        return updated
    
    def _delete_demo_records(self, record_ids):
        if 'demo_consignment_records' not in st.session_state or st.session_state.demo_consignment_records is None:
            return False
        
        st.session_state.demo_consignment_records = [
            record for record in st.session_state.demo_consignment_records 
            if record['id'] not in record_ids
        ]
        
        return True
    
    def _render_payout_requests(self):
        st.subheader("💰 Payout Requests")
        
        users = self.api_client.get_all_users()
        
        payout_requests = []
        for user in users:
            if user.get('payout_requested') and user.get('store_credit_balance', 0) > 0:
                payout_requests.append(user)
        
        if not payout_requests:
            st.info("No pending payout requests.")
            return
        
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
                            st.session_state.needs_refresh = True
                            st.stop()
                        else:
                            st.error(f"❌ Failed to process payout")
    
    def _request_payout(self, user_id):
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
            if response.status_code == 200:
                st.session_state.needs_refresh = True
                return True
            return False
        except Exception as e:
            st.error(f"Error requesting payout: {e}")
            return False
    
    def _process_payout(self, user_id):
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would process payout for user {user_id}")
            return True
            
        try:
            user_info = self.api_client.get_user(user_id)
            if not user_info:
                return False
            
            credit_balance = user_info.get('store_credit_balance', 0)
            
            response = requests.put(
                f"{self.api_client.base_url}/users/{user_id}/process-payout",
                json={
                    'store_credit_balance': 0,
                    'payout_requested': False,
                    'original_payout_amount': credit_balance
                }
            )
            if response.status_code == 200:
                st.session_state.needs_refresh = True
                return True
            return False
        except Exception as e:
            st.error(f"Error processing payout: {e}")
            return False
    
    def _mark_as_removed(self, record_ids, is_demo=False):
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
                success = self._update_demo_record_status([record_id], 4)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            else:
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
        
        st.session_state.selected_consignment_records = [
            r for r in st.session_state.selected_consignment_records if r not in record_ids
        ]
        st.session_state.select_all_consignment = False
        
        st.session_state.needs_refresh = True
        st.session_state.records_updated = st.session_state.get('records_updated', 0) + 1
        st.stop()
    
    def _delete_selected_records(self, record_ids, is_demo=False):
        if not record_ids:
            st.error("No records selected")
            return
        
        user = st.session_state.get('user', {})
        user_role = user.get('role')
        is_demo = user.get('username') == 'demo_user'
        
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
                success = self._delete_demo_records([record_id])
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            else:
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
        
        st.session_state.selected_consignment_records = [
            r for r in st.session_state.selected_consignment_records if r not in record_ids
        ]
        st.session_state.select_all_consignment = False
        
        st.session_state.needs_refresh = True
        st.session_state.records_updated = st.session_state.get('records_updated', 0) + 1
        st.stop()

class APIClient:
    
    def __init__(self, base_url="https://arjanshaw.pythonanywhere.com"):
        self.base_url = base_url
    
    def get_user(self, user_id):
        try:
            response = requests.get(f"{self.base_url}/users/{user_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"API Error getting user: {e}")
            return None
    
    def get_all_users(self):
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
            if response.status_code == 200:
                # Mark records as updated
                if 'records_updated' not in st.session_state:
                    st.session_state.records_updated = 0
                st.session_state.records_updated += 1
                return True
            return False
        except Exception as e:
            st.error(f"API Error updating record status: {e}")
            return False
    
    def delete_record(self, record_id):
        user = st.session_state.get('user', {})
        is_demo = user.get('username') == 'demo_user'
        
        if is_demo:
            st.info(f"Demo: Would delete record {record_id}")
            return True
            
        try:
            response = requests.delete(f"{self.base_url}/records/{record_id}")
            if response.status_code == 200:
                # Mark records as updated
                if 'records_updated' not in st.session_state:
                    st.session_state.records_updated = 0
                st.session_state.records_updated += 1
                return True
            return False
        except Exception as e:
            st.error(f"API Error deleting record: {e}")
            return False
    
    def update_record(self, record_id, updates):
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
            if response.status_code == 200:
                # Mark records as updated
                if 'records_updated' not in st.session_state:
                    st.session_state.records_updated = 0
                st.session_state.records_updated += 1
                return True
            return False
        except Exception as e:
            st.error(f"API Error updating record: {e}")
            return False