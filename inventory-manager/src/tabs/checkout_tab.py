import streamlit as st
import pandas as pd
from datetime import datetime

class CheckoutTab:
    def __init__(self):
        if 'scanned_records' not in st.session_state:
            st.session_state.scanned_records = []
        if 'barcode_input_key' not in st.session_state:
            st.session_state.barcode_input_key = 0
        if 'receipt_content' not in st.session_state:
            st.session_state.receipt_content = None
        if 'show_receipt_download' not in st.session_state:
            st.session_state.show_receipt_download = False

    def render(self):
        st.header("📦 Checkout")
        
        # Show receipt download if available
        if st.session_state.show_receipt_download and st.session_state.receipt_content:
            st.success("✅ Sale processed! Download your receipt below.")
            st.download_button(
                label="⬇️ Download Receipt",
                data=st.session_state.receipt_content,
                file_name=f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                key="download_receipt"
            )
            if st.button("Clear Receipt", use_container_width=True):
                st.session_state.receipt_content = None
                st.session_state.show_receipt_download = False
                st.rerun()
        
        # Barcode scanner input
        st.subheader("Scan Barcode")
        barcode_input = st.text_input(
            "Enter barcode:",
            placeholder="Scan or enter barcode here...",
            key=f"barcode_input_{st.session_state.barcode_input_key}",
            label_visibility="collapsed"
        )
        
        # Auto-focus the input field
        st.markdown(
            """
            <script>
            var input = window.parent.document.querySelector('input[placeholder="Scan or enter barcode here..."]');
            if (input) input.focus();
            </script>
            """,
            unsafe_allow_html=True
        )
        
        # Process barcode when entered
        if barcode_input and barcode_input.strip():
            self._process_barcode(barcode_input.strip())
            # Clear the input field by incrementing the key
            st.session_state.barcode_input_key += 1
            st.rerun()
        
        # Display scanned records
        st.subheader("Scanned Records")
        
        if st.session_state.scanned_records:
            # Calculate total value
            total_value = sum(record.get('discogs_median_price', 0) or 0 for record in st.session_state.scanned_records)
            
            # Display summary
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Items Scanned", len(st.session_state.scanned_records))
            with col2:
                st.metric("Total Value", f"${total_value:.2f}")
            
            # Display scanned records in a table
            display_data = []
            for record in st.session_state.scanned_records:
                display_data.append({
                    'Artist': record.get('artist', ''),
                    'Title': record.get('title', ''),
                    'Barcode': record.get('barcode', ''),
                    'File At': record.get('file_at', ''),
                    'Price': f"${record.get('discogs_median_price', 0) or 0:.2f}",
                    'Format': record.get('format', ''),
                    'Condition': record.get('condition', '')
                })
            
            df = pd.DataFrame(display_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Action buttons - only Print Receipt button
            if st.button("🧾 Print Receipt & Mark as Sold", use_container_width=True):
                self._process_sale()
        else:
            st.info("No records scanned yet. Start scanning barcodes above.")
    
    def _process_barcode(self, barcode):
        """Process a scanned barcode"""
        try:
            # Look up record by barcode
            record = st.session_state.db_manager.get_record_by_barcode(barcode)
            
            if record is not None:
                # Check if record is already in the scanned list
                if any(r.get('barcode') == barcode for r in st.session_state.scanned_records):
                    st.warning(f"Record '{record.get('artist', '')} - {record.get('title', '')}' already scanned!")
                else:
                    # Add to scanned records
                    st.session_state.scanned_records.append(record)
                    st.success(f"✅ Added: {record.get('artist', '')} - {record.get('title', '')}")
            else:
                st.error(f"❌ No record found with barcode: {barcode}")
                
        except Exception as e:
            st.error(f"Error processing barcode: {e}")
    
    def _process_sale(self):
        """Process the sale - mark scanned records as sold"""
        if not st.session_state.scanned_records:
            st.warning("No records to process.")
            return
        
        try:
            # Update records status to 'sold'
            updated_count = 0
            for record in st.session_state.scanned_records:
                record_id = record.get('id')
                if record_id:
                    conn = st.session_state.db_manager._get_connection()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE records SET status = ? WHERE id = ?', ('sold', record_id))
                    conn.commit()
                    conn.close()
                    updated_count += 1
            
            if updated_count > 0:
                # Generate receipt
                receipt_content = self._generate_receipt_content()
                st.session_state.receipt_content = receipt_content
                st.session_state.show_receipt_download = True
                
                # Clear scanned records
                st.session_state.scanned_records = []
                st.session_state.records_updated += 1
                st.rerun()
            else:
                st.error("Failed to update any records.")
                
        except Exception as e:
            st.error(f"Error processing sale: {e}")
    
    def _generate_receipt_content(self):
        """Generate receipt content for the scanned records"""
        try:
            # Create receipt content
            receipt_lines = []
            receipt_lines.append("PIGSTYLE RECORDS - CHECKOUT RECEIPT")
            receipt_lines.append("=" * 40)
            receipt_lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            receipt_lines.append(f"Items: {len(st.session_state.scanned_records)}")
            receipt_lines.append("")
            
            total = 0
            for i, record in enumerate(st.session_state.scanned_records, 1):
                artist = record.get('artist', 'Unknown Artist')
                title = record.get('title', 'Unknown Title')
                price = record.get('discogs_median_price', 0) or 0
                total += price
                
                # Truncate long titles for receipt format
                if len(title) > 30:
                    title = title[:27] + "..."
                if len(artist) > 20:
                    artist = artist[:17] + "..."
                
                receipt_lines.append(f"{i:2d}. {artist:<20} {title:<30} ${price:>6.2f}")
            
            receipt_lines.append("")
            receipt_lines.append("=" * 40)
            receipt_lines.append(f"TOTAL: ${total:>33.2f}")
            receipt_lines.append("")
            receipt_lines.append("Thank you for your purchase!")
            
            return "\n".join(receipt_lines)
            
        except Exception as e:
            return f"Error generating receipt: {e}"