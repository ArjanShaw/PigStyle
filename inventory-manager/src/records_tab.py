import streamlit as st
import pandas as pd
from datetime import datetime
import os
import sqlite3
from typing import Dict, List, Optional, Tuple

class RecordsTab:
    def __init__(self):
        self.page_size = 50  # Records per page
        self.current_page = 1
        
    def render(self):
        st.subheader("Records")
        
        try:
            # Database statistics - direct count from records table
            stats = self._get_database_stats_direct()
            
            # Header with stats and actions
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Records", stats['records_count'])
            with col2:
                if st.button("🔄 Refresh", use_container_width=True, help="Refresh data"):
                    st.rerun()
            with col3:
                if st.button("📊 Export CSV", use_container_width=True, help="Export all records to CSV"):
                    self._export_all_records()
            with col4:
                if st.button("🔢 Gen Barcodes", use_container_width=True, help="Generate missing barcodes"):
                    self._generate_barcodes_for_existing_records()
            with col5:
                if st.button("🖨️ Print Selected", use_container_width=True, help="Print selected records"):
                    self._send_to_print_tab()
            
            if stats['records_count'] > 0:
                self._render_search_and_filters()
                self._render_records_table()
            else:
                st.info("No records in database yet. Start by searching and adding records above!")
                
        except Exception as e:
            st.error(f"Error loading records: {e}")

    def _get_database_stats_direct(self) -> Dict:
        """Get database statistics directly from records table"""
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM records')
            records_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM records WHERE barcode IS NULL OR barcode = ""')
            no_barcode_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'records_count': records_count,
                'no_barcode_count': no_barcode_count
            }
        except Exception as e:
            st.error(f"Error getting stats: {e}")
            return {'records_count': 0, 'no_barcode_count': 0}

    def _render_search_and_filters(self):
        """Render search and filter controls"""
        st.subheader("Search & Filter")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            search_term = st.text_input(
                "Search by artist, title, or barcode:",
                key="search_records",
                placeholder="Enter search term..."
            )
        
        with col2:
            # Quick filters
            filter_option = st.selectbox(
                "Filter by",
                options=["All Records", "No Barcode", "No Price Data", "No Genre"],
                key="quick_filter"
            )
        
        with col3:
            if st.button("🔄 Clear Filters", use_container_width=True):
                st.session_state.pop('search_records', None)
                st.session_state.pop('quick_filter', None)
                st.session_state.current_page = 1
                st.rerun()

    def _get_paginated_records_direct(self, offset: int, limit: int, search_term: str = None, filter_option: str = None) -> pd.DataFrame:
        """Get paginated records directly from records table with optional filtering"""
        try:
            conn = st.session_state.db_manager._get_connection()
            
            # Simple query - only from records table with correct column names
            base_query = """
            SELECT 
                id, artist, title, 
                discogs_median_price, discogs_lowest_price, discogs_highest_price, 
                image_url, barcode, format, condition, created_at
            FROM records 
            WHERE 1=1
            """
            
            params = []
            
            # Apply search filter
            if search_term:
                base_query += """
                AND (artist LIKE ? 
                    OR title LIKE ? 
                    OR barcode LIKE ?)
                """
                search_pattern = f"%{search_term}%"
                params.extend([search_pattern, search_pattern, search_pattern])
            
            # Apply quick filters
            if filter_option == "No Barcode":
                base_query += " AND (barcode IS NULL OR barcode = '')"
            elif filter_option == "No Price Data":
                base_query += " AND (discogs_median_price IS NULL OR discogs_median_price = 0)"
            elif filter_option == "No Genre":
                base_query += " AND (genre IS NULL OR genre = '')"
            
            # Add ordering and pagination
            base_query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            df = pd.read_sql_query(base_query, conn, params=params)
            conn.close()
            return df
            
        except Exception as e:
            st.error(f"Error loading records: {e}")
            return pd.DataFrame()

    def _get_total_filtered_count(self, search_term: str = None, filter_option: str = None) -> int:
        """Get total count of records after applying filters"""
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            
            base_query = "SELECT COUNT(*) FROM records WHERE 1=1"
            params = []
            
            if search_term:
                base_query += """
                AND (artist LIKE ? 
                    OR title LIKE ? 
                    OR barcode LIKE ?)
                """
                search_pattern = f"%{search_term}%"
                params.extend([search_pattern, search_pattern, search_pattern])
            
            if filter_option == "No Barcode":
                base_query += " AND (barcode IS NULL OR barcode = '')"
            elif filter_option == "No Price Data":
                base_query += " AND (discogs_median_price IS NULL OR discogs_median_price = 0)"
            elif filter_option == "No Genre":
                base_query += " AND (genre IS NULL OR genre = '')"
            
            cursor.execute(base_query, params)
            count = cursor.fetchone()[0]
            conn.close()
            return count
            
        except Exception as e:
            st.error(f"Error counting records: {e}")
            return 0

    def _render_records_table(self):
        """Render records with pagination"""
        
        # Get current filter state
        search_term = st.session_state.get('search_records', '')
        filter_option = st.session_state.get('quick_filter', 'All Records')
        
        # Initialize pagination
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 1
        
        # Get total count for pagination
        total_records = self._get_total_filtered_count(search_term, filter_option)
        
        if total_records == 0:
            st.info("No records found matching your criteria.")
            return
        
        # Calculate pagination
        total_pages = max(1, (total_records + self.page_size - 1) // self.page_size)
        current_page = min(st.session_state.current_page, total_pages)
        offset = (current_page - 1) * self.page_size
        
        # Load only the current page of records
        records = self._get_paginated_records_direct(offset, self.page_size, search_term, filter_option)
        
        if len(records) == 0 and current_page > 1:
            # If no records on current page but we're not on page 1, go to page 1
            st.session_state.current_page = 1
            st.rerun()
            return
        
        # Display record count and pagination info
        self._render_pagination_info(total_records, current_page, total_pages, search_term, filter_option)
        
        # Render the records table with selection
        self._render_records_dataframe(records)
        
        # Pagination controls
        if total_pages > 1:
            self._render_pagination_controls(current_page, total_pages)

    def _render_pagination_info(self, total_records: int, current_page: int, total_pages: int, search_term: str, filter_option: str):
        """Render pagination information and filters"""
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            start_record = (current_page - 1) * self.page_size + 1
            end_record = min(current_page * self.page_size, total_records)
            
            if search_term:
                st.write(f"**Showing {start_record}-{end_record} of {total_records} records matching '{search_term}'**")
            elif filter_option != "All Records":
                st.write(f"**Showing {start_record}-{end_record} of {total_records} {filter_option.lower()}**")
            else:
                st.write(f"**Showing {start_record}-{end_record} of {total_records} records**")
        
        with col2:
            # Page size selector
            new_page_size = st.selectbox(
                "Records per page:",
                options=[25, 50, 100],
                index=1,  # Default to 50
                key="page_size_selector"
            )
            if new_page_size != self.page_size:
                self.page_size = new_page_size
                st.session_state.current_page = 1
                st.rerun()
        
        with col3:
            st.write(f"**Page {current_page} of {total_pages}**")

    def _render_records_dataframe(self, records: pd.DataFrame):
        """Render records in an optimized dataframe with selection"""
        if len(records) == 0:
            return
        
        # Add selection column to the dataframe
        records_with_selection = records.copy()
        records_with_selection['Select'] = False
        
        # Initialize selection state
        if 'selected_records' not in st.session_state:
            st.session_state.selected_records = []
        
        # Prepare display data with selection
        display_data = []
        for _, record in records.iterrows():
            is_selected = record['id'] in st.session_state.selected_records
            display_data.append({
                'Select': is_selected,
                'Cover': record.get('image_url', ''),
                'Artist': record.get('artist', ''),
                'Title': record.get('title', ''),
                'Barcode': record.get('barcode', ''),
                'Condition': f"{record.get('condition', '')}/5",
                'Format': record.get('format', ''),
                'Median Price': self._format_currency(record.get('discogs_median_price')),
                'Lowest Price': self._format_currency(record.get('discogs_lowest_price')),
                'Highest Price': self._format_currency(record.get('discogs_highest_price')),
                'Added': record.get('created_at', '')[:16] if record.get('created_at') else ''
            })
        
        display_df = pd.DataFrame(display_data)
        
        # Configure columns for better display
        column_config = {
            'Select': st.column_config.CheckboxColumn('Select', width='small'),
            'Cover': st.column_config.ImageColumn('Cover', width='small'),
            'Artist': st.column_config.TextColumn('Artist', width='medium'),
            'Title': st.column_config.TextColumn('Title', width='large'),
            'Barcode': st.column_config.TextColumn('Barcode', width='small'),
            'Condition': st.column_config.TextColumn('Condition', width='small'),
            'Format': st.column_config.TextColumn('Format', width='small'),
            'Median Price': st.column_config.TextColumn('Median Price', width='small'),
            'Lowest Price': st.column_config.TextColumn('Low Price', width='small'),
            'Highest Price': st.column_config.TextColumn('High Price', width='small'),
            'Added': st.column_config.TextColumn('Added', width='small'),
        }
        
        # Display editable dataframe with selection
        edited_df = st.data_editor(
            display_df,
            column_config=column_config,
            use_container_width=True,
            height=min(600, 35 * len(display_df) + 40),
            hide_index=True,
            key="records_editor"
        )
        
        # Update selection state based on editor changes
        if edited_df is not None:
            selected_ids = []
            for i, (_, original_record) in enumerate(records.iterrows()):
                if i < len(edited_df) and edited_df.iloc[i]['Select']:
                    selected_ids.append(original_record['id'])
            
            st.session_state.selected_records = selected_ids
        
        # Show actions for selected records
        if st.session_state.selected_records:
            selected_records = records[records['id'].isin(st.session_state.selected_records)]
            self._render_record_actions(selected_records)

    def _render_record_actions(self, records):
        """Render actions for selected records"""
        st.divider()
        st.write(f"**Actions for {len(records)} selected records:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🗑️ Delete Selected", use_container_width=True):
                if self._delete_records(records['id'].tolist()):
                    st.success(f"Deleted {len(records)} records!")
                    # Clear selection after deletion
                    st.session_state.selected_records = []
                    st.session_state.records_updated += 1
                    st.rerun()
        
        with col2:
            if st.button("🖨️ Print Selected", use_container_width=True):
                records_list = records.to_dict('records')
                st.session_state.records_to_print = records_list
                st.success(f"Sent {len(records_list)} records to Print tab!")
                # Clear selection after sending to print
                st.session_state.selected_records = []
        
        with col3:
            if st.button("📋 Copy Barcodes", use_container_width=True):
                barcodes = ", ".join([str(b) for b in records['barcode'].tolist() if b])
                st.session_state.clipboard = barcodes
                st.success("Barcodes copied to clipboard!")

    def _render_pagination_controls(self, current_page: int, total_pages: int):
        """Render pagination controls"""
        st.divider()
        
        col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
        
        with col1:
            if st.button("⏮️ First", disabled=current_page == 1, use_container_width=True):
                st.session_state.current_page = 1
                st.rerun()
        
        with col2:
            if st.button("◀️ Previous", disabled=current_page == 1, use_container_width=True):
                st.session_state.current_page = current_page - 1
                st.rerun()
        
        with col3:
            # Page jumper
            new_page = st.number_input(
                "Go to page:",
                min_value=1,
                max_value=total_pages,
                value=current_page,
                key="page_jumper"
            )
            if new_page != current_page:
                st.session_state.current_page = new_page
                st.rerun()
        
        with col4:
            if st.button("Next ▶️", disabled=current_page == total_pages, use_container_width=True):
                st.session_state.current_page = current_page + 1
                st.rerun()
        
        with col5:
            if st.button("Last ⏭️", disabled=current_page == total_pages, use_container_width=True):
                st.session_state.current_page = total_pages
                st.rerun()

    def _format_currency(self, value):
        """Format currency values"""
        if not value:
            return ""
        try:
            return f"${float(value):.2f}"
        except (ValueError, TypeError):
            return ""

    def _delete_records(self, record_ids):
        """Delete records from the database"""
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            cursor.executemany('DELETE FROM records WHERE id = ?', [(id,) for id in record_ids])
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error deleting records: {e}")
            return False

    def _export_all_records(self):
        """Export all records to CSV directly from table"""
        try:
            # Get all records in chunks to avoid memory issues
            all_records = []
            limit = 1000
            offset = 0
            
            while True:
                chunk = self._get_paginated_records_direct(offset, limit)
                if len(chunk) == 0:
                    break
                all_records.append(chunk)
                offset += limit
            
            if all_records:
                export_df = pd.concat(all_records, ignore_index=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"vinyl_records_export_{timestamp}.csv"
                
                csv_data = export_df.to_csv(index=False)
                
                st.download_button(
                    label="⬇️ Download CSV File",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    key=f"download_{timestamp}"
                )
                
                st.success(f"✅ Export ready! {len(export_df)} records.")
            else:
                st.warning("No records to export.")
                
        except Exception as e:
            st.error(f"Error exporting records: {e}")

    def _generate_barcodes_for_existing_records(self):
        """Generate barcodes for records without them"""
        try:
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT id FROM records WHERE barcode IS NULL OR barcode = "" OR barcode NOT GLOB "[0-9]*"')
            records_without_barcodes = cursor.fetchall()
            
            cursor.execute('SELECT MAX(CAST(barcode AS INTEGER)) as max_barcode FROM records WHERE barcode GLOB "[0-9]*"')
            result = cursor.fetchone()
            current_max = result[0] if result[0] is not None else 100000
            
            updated_count = 0
            for record in records_without_barcodes:
                record_id = record[0]
                current_max += 1
                cursor.execute('UPDATE records SET barcode = ? WHERE id = ?', (str(current_max), record_id))
                updated_count += 1
            
            conn.commit()
            conn.close()
            
            if updated_count > 0:
                st.success(f"✅ Generated barcodes for {updated_count} records!")
            else:
                st.info("✅ All records already have barcodes!")
                
            st.session_state.records_updated += 1
            st.rerun()
            
        except Exception as e:
            st.error(f"Error generating barcodes: {e}")

    def _send_to_print_tab(self):
        """Send selected records to print tab"""
        if 'selected_records' in st.session_state and st.session_state.selected_records:
            # Get the actual record data for selected IDs
            selected_ids = st.session_state.selected_records
            placeholders = ','.join(['?'] * len(selected_ids))
            
            conn = st.session_state.db_manager._get_connection()
            df = pd.read_sql(f'SELECT * FROM records WHERE id IN ({placeholders})', conn, params=selected_ids)
            conn.close()
            
            records_list = df.to_dict('records')
            st.session_state.records_to_print = records_list
            st.success(f"Sent {len(records_list)} records to Print tab!")
            # Clear selection
            st.session_state.selected_records = []
        else:
            st.warning("Please select records using the checkboxes in the table first.")