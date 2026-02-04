import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os
import time
import threading
import queue
import json
from pathlib import Path
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm, inch
import barcode
from barcode.writer import ImageWriter
import io
from handlers.contract_handler import ContractHandler
from conditions import DiscogsConditions

class PriceTagTab:
    def __init__(self, genre_cache=None):
        # Get config cache from session state (set up in streamlit_app.py)
        self.genre_cache = genre_cache  # Store genre cache reference
        self.contract_handler = None  # Will be initialized when needed
        
        self.base_url = "https://www.pigstylemusic.com"

        # Initialize config values from database
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Validate that all required configuration values exist in database"""
        config_keys = [
            'LABEL_WIDTH_MM', 'LABEL_HEIGHT_MM', 'LEFT_MARGIN_MM',
            'GUTTER_SPACING_MM', 'TOP_MARGIN_MM', 'FONT_SIZE',
            'PRICE_FONT_SIZE', 'PRICE_Y_POS', 'TEXT_FONT_SIZE',
            'BARCODE_Y_POS', 'BARCODE_HEIGHT', 'PRINT_BORDERS'
        ]
        
        for key in config_keys:
            value = self._get_config_value(key)
            if value is None:
                st.error(f"Configuration key '{key}' not found in database")
                st.stop()
            
            # Convert string values to appropriate types
            if key == 'PRINT_BORDERS':
                # FIX: Handle boolean values properly
                if isinstance(value, bool):
                    st.session_state[key.lower()] = value
                elif isinstance(value, str):
                    st.session_state[key.lower()] = value.lower() == 'true'
                else:
                    st.session_state[key.lower()] = False
            elif key in ['FONT_SIZE', 'PRICE_FONT_SIZE', 'TEXT_FONT_SIZE', 'GENRE_FONT_SIZE']:
                try:
                    st.session_state[key.lower()] = int(float(value))
                except (ValueError, TypeError):
                    st.session_state[key.lower()] = self._get_default_value(key)
            else:
                try:
                    st.session_state[key.lower()] = float(value)
                except (ValueError, TypeError):
                    st.session_state[key.lower()] = value
    
    
    def _get_config_value(self, config_key, default=None):
        """Get config value from cache - FIXED: Use config_cache from session state"""
        # First try to get from session state config cache
        if hasattr(st.session_state, 'config_cache') and st.session_state.config_cache:
            value = st.session_state.config_cache.get(config_key)
            if value is not None:
                # Convert to appropriate type
                if config_key == 'PRINT_BORDERS':
                    if isinstance(value, bool):
                        return value
                    elif isinstance(value, str):
                        return value.lower() == 'true'
                    else:
                        return default
                elif config_key in ['FONT_SIZE', 'PRICE_FONT_SIZE', 'TEXT_FONT_SIZE', 'GENRE_FONT_SIZE']:
                    try:
                        return int(float(value))
                    except (ValueError, TypeError):
                        return default
                else:
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return value
        
        # If not in cache, try API call
        try:
            response = requests.get(f"https://www.pigstylemusic.com/config/{config_key}")
            if response.status_code == 200:
                data = response.json()
                value = data.get('config_value', default)
                
                # Update cache
                if hasattr(st.session_state, 'config_cache'):
                    st.session_state.config_cache[config_key] = value
                
                # Convert to appropriate type
                if config_key == 'PRINT_BORDERS':
                    if isinstance(value, bool):
                        return value
                    elif isinstance(value, str):
                        return value.lower() == 'true'
                    else:
                        return default
                elif config_key in ['FONT_SIZE', 'PRICE_FONT_SIZE', 'TEXT_FONT_SIZE', 'GENRE_FONT_SIZE']:
                    try:
                        return int(float(value))
                    except (ValueError, TypeError):
                        return default
                else:
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return value
            return default
        except Exception as e:
            print(f"Error getting config {config_key}: {e}")
            return default
    
    def _save_page_layout_config(self, key, value):
        """Save page layout configuration to database via API"""
        # Convert key to uppercase for database storage
        db_key = key.upper()
        
        try:
            success = self._save_config_value(db_key, str(value))
            if success:
                st.session_state[key] = value
                st.session_state.needs_refresh = True
                st.stop()
        except Exception as e:
            st.error(f"Error saving configuration: {e}")
    
    def _save_tag_design_config(self, key, value):
        """Save tag design configuration to database via API"""
        # Both page layout and tag design are stored in the same database table
        self._save_page_layout_config(key, value)
    
    def _save_config_value(self, config_key, config_value):
        """Save config value via API"""
        try:
            response = requests.put(
                f"https://www.pigstylemusic.com/config/{config_key}",
                json={'config_value': config_value}
            )
            
            # Update cache after saving
            if response.status_code == 200 and hasattr(st.session_state, 'config_cache'):
                st.session_state.config_cache[config_key] = config_value
            
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error saving config: {e}")
            return False
    
    def render(self):
        st.header("🏷️ Print Price Tags")
        
        # Check dependencies
        try:
            import barcode
            import reportlab
            st.success("✅ Printing dependencies available")
        except ImportError as e:
            st.error(f"Missing dependencies: {e}")
            return
        
        # Two columns for configuration
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📐 Page/Layout Configuration", expanded=False):
                self._render_page_layout_configuration()
        
        with col2:
            with st.expander("⚙️ Price Tag Design", expanded=False):
                self._render_price_tag_design_configuration()
        
        # Get all users for selection - USE CACHED DATA IF AVAILABLE
        users = self._get_all_users()
        
        # User selection combobox - FIXED: Handle None/empty users list
        user_options = ["All Users"]
        if users and isinstance(users, list) and len(users) > 0:
            user_options += [f"{user.get('username', 'Unknown')} (ID: {user['id']})" for user in users]
        else:
            st.info("No users found in the system. Only 'All Users' option available.")
        
        selected_user = st.selectbox(
            "Select User:",
            options=user_options,
            index=0,
            key="user_selection"
        )
        
        # Parse selected user ID
        selected_user_id = None
        selected_user_data = None
        if selected_user != "All Users":
            try:
                # Extract user ID from the selection string
                user_id_str = selected_user.split("(ID: ")[1].replace(")", "")
                selected_user_id = int(user_id_str)
                # Get user data
                selected_user_data = self._get_user_by_id(selected_user_id, users or [])
            except:
                st.error("Invalid user selection")
                return
        
        # NEW: Simplified interface - ALWAYS show input and buttons
        st.divider()
        st.subheader("📊 Price Tag Management")
        
        # Get NEW records for printing (status_id = 1) sorted by creation date descending
        new_records = self._get_new_records_for_user(selected_user_id)
        total_records = self._get_all_records_for_user(selected_user_id)
        
        # NEW: Display table of inactive records that will be printed
        if new_records:
            st.subheader("📋 Inactive Records Ready for Printing")
            st.write(f"**Found {len(new_records)} inactive records (status_id = 1) sorted by creation date (newest first):**")
            
            # Create display table
            display_data = []
            for i, record in enumerate(new_records, 1):
                # Calculate page position for printing
                position = i
                row = (position - 1) // 4  # 0-indexed row
                col = (position - 1) % 4   # 0-indexed column
                
                # Format data for display
                artist = record.get('artist', 'Unknown')[:25]
                title = record.get('title', 'Unknown')[:30]
                price = record.get('store_price', 0.0)
                catalog = record.get('catalog_number', 'N/A')[:15]
                genre = record.get('genre_name', record.get('genre', 'Unknown'))[:20]
                barcode_num = record.get('barcode', 'N/A')
                created_at = record.get('created_at', 'Unknown')
                
                # Format date if available
                if created_at and created_at != 'Unknown':
                    try:
                        if 'T' in created_at:
                            date_part = created_at.split('T')[0]
                            created_at = date_part
                    except:
                        pass
                
                display_data.append({
                    '#': i,
                    'Artist': artist,
                    'Title': title,
                    'Price': f"${price:.2f}",
                    'Catalog': catalog,
                    'Genre': genre,
                    'Barcode': barcode_num,
                    'Created': created_at,
                    'Page Pos': f"R{row+1}C{col+1}"
                })
            
            # Create DataFrame and display
            df = pd.DataFrame(display_data)
            
            column_config = {
                '#': st.column_config.NumberColumn('#', width='small'),
                'Artist': st.column_config.TextColumn('Artist', width='medium'),
                'Title': st.column_config.TextColumn('Title', width='large'),
                'Price': st.column_config.TextColumn('Price', width='small'),
                'Catalog': st.column_config.TextColumn('Catalog', width='medium'),
                'Genre': st.column_config.TextColumn('Genre', width='medium'),
                'Barcode': st.column_config.TextColumn('Barcode', width='medium'),
                'Created': st.column_config.TextColumn('Created', width='small'),
                'Page Pos': st.column_config.TextColumn('Page Position', width='small')
            }
            
            st.dataframe(
                df,
                column_config=column_config,
                hide_index=True,
                width='stretch',
                height=400
            )
            
            # Show printing position explanation
            with st.expander("📄 Printing Position Explanation", expanded=False):
                st.write("""
                **Page Position Key:**
                - **R1C1**: Row 1, Column 1 (top-left corner of page)
                - **R1C2**: Row 1, Column 2
                - **R2C1**: Row 2, Column 1
                - etc.
                
                **Layout:**
                - Each page has 15 rows × 4 columns = 60 labels
                - Labels are filled left-to-right, top-to-bottom
                - Position numbers show where each record will print
                """)
        else:
            st.info("No inactive records (status_id = 1) found for printing.")
        
        # Display counts
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📄 Total Records", len(total_records))
        with col2:
            # FIXED: Changed label to show count of new records (status_id = 1)
            st.metric("📅 Inactive Records Ready", len(new_records))
        
        # Input for number of tags to process
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Get last batch size from config for default value
            last_batch_size = self._get_config_value('LAST_PRINT_BATCH_SIZE', '10')
            try:
                default_batch_size = int(last_batch_size)
            except:
                default_batch_size = 10
            
            # Calculate max value for input - use new_records count
            max_for_printing = len(new_records)
            
            batch_size = st.number_input(
                "Number of tags to print:",
                min_value=1,
                max_value=max(max_for_printing, 1),
                value=min(default_batch_size, max(max_for_printing, 1)),
                step=1,
                key="batch_size_input",
                help="Enter the number of price tags to print"
            )
        
        with col2:
            # Show info about what will be processed
            if batch_size > 0 and new_records:
                st.info(f"Will print the {batch_size} most recent NEW records (created_at descending)")
        
        # Action buttons - only print button remains
        col1, col2 = st.columns(2)
        
        with col1:
            print_enabled = len(new_records) > 0 and batch_size <= len(new_records)
            if print_enabled:
                if st.button("🖨️ Print Price Tags", type="primary", width='stretch',
                            help=f"Print price tags for {batch_size} most recent new records"):
                    # Get the most recent new records (already sorted by created_at descending)
                    records_to_print = new_records[:batch_size]
                    
                    self._process_print_tags(records_to_print, batch_size, selected_user_id, selected_user_data)
            else:
                disabled_reason = "No new records available" if len(new_records) == 0 else f"Only {len(new_records)} new records available"
                st.button("🖨️ Print Price Tags", disabled=True, width='stretch',
                         help=disabled_reason)
        
     
    def _process_print_tags(self, records, batch_size, user_id, user_data):
        
        """Process printing price tags for specified number of NEW records"""
        if batch_size <= 0:
            st.error("Please enter a valid number of tags to print")
            return
        
        # Get the most recent new records (already filtered and sorted newest first)
        records_to_print = records[:batch_size]
        
       
        for i, record in enumerate(records_to_print):
            position = i + 1
            # Calculate page position
            row = (position - 1) // 4  # 0-indexed row
            col = (position - 1) % 4   # 0-indexed column
        
        
        # Print tags with receipt
        
        if user_id:
            store_credit_option = st.checkbox(
                "📋 Include in consignment with store credit bonus (+20%)",
                value=False,
                help="Consignor chooses store credit payout (20% commission bonus)"
            )
        
        self._print_tags_with_receipt(
            records_to_print,  
            user_id,
            user_data
        )
        
        # Save batch size to config
        self._save_config_value('LAST_PRINT_BATCH_SIZE', str(batch_size))
    
    def _generate_consignment_contract(self, user_data):
        """Generate and download consignment contract"""
        if not self.contract_handler:
            # Initialize API client for contract handler
            class APIClient:
                def __init__(self):
                    pass
                
                def get_config_value(self, key, default=None):
                    return self._get_config_value(key, default)
                
                def _get_config_value(self, key, default=None):
                    """Get config value via API"""
                    return self._get_config_value(key, default)
            
            api_client = APIClient()
            self.contract_handler = ContractHandler(api_client)
        
        # Get commission rate from config
        commission_rate_value = self._get_config_value('DEFAULT_COMMISSION_RATE', '0.20')
        commission_rate = float(commission_rate_value) if commission_rate_value else 0.20
        
        # Prepare batch data
        batch_data = {
            'batch_id': f"BATCH{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'item_count': 0,  # Will be filled when actually printing
            'total_value': 0,  # Will be filled when actually printing
            'commission_rate': commission_rate
        }
        
        # Generate contract
        store_credit_option = st.session_state.get('store_credit_option', False)
        pdf_data = self.contract_handler.generate_consignment_contract(
            user_data, batch_data, store_credit_option
        )
        
        # Download button
        filename = f"PigStyle_Consignment_{datetime.now().strftime('%Y%m%d')}_{user_data.get('username', 'user')}.pdf"
        
        st.download_button(
            label="⬇️ Download Consignment Contract",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            width='stretch'
        )
    
    def _print_tags_with_receipt(self, records, user_id, user_data):
         
        # Initialize session state for printing
        st.session_state.print_status = "processing"
        st.session_state.print_message = f"🔄 Starting price tag generation for {len(records)} records..."
        st.session_state.print_success = False

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step 1: Load record data - USE THE RECORDS WE ALREADY HAVE
        status_text.text("Step 1/3: Loading record data...")
        progress_bar.progress(33)
         
        # Step 2: Generate PDF price tags
        status_text.text("Step 2/3: Generating price tags PDF...")
        pdf_tags_data = self._generate_tags_pdf(records)
        progress_bar.progress(66)
         
        # Step 3: Generate receipt and contract (if consignor)
        receipt_text = None
        receipt_pdf = None
        contract_pdf = None
        
        # Initialize contract handler if not already initialized
        if not self.contract_handler:
            self._initialize_contract_handler()

        for record in records:   
                record_id = record.get('id')   
                success = self._update_record(record_id, {  
                    'status_id': 2   
                })

        if user_id:
            # Get commission rate
            commission_rate_value = self._get_config_value('DEFAULT_COMMISSION_RATE', '0.20')
            commission_rate = float(commission_rate_value) if commission_rate_value else 0.20
                
            # Generate receipt
            receipt_text, receipt_pdf, receipt_number = self.contract_handler.generate_batch_receipt(
                user_data, records, commission_rate
            )
                
            # Generate contract
            total_value = sum(r.get('store_price', 0) for r in records)
            batch_data = {
                'batch_id': receipt_number,
                'item_count': len(records),
                'total_value': total_value,
                'commission_rate': commission_rate
            }
                
            contract_pdf = self.contract_handler.generate_consignment_contract(
                user_data, batch_data
            )
                
            
            if success:
                st.session_state.records_updated = st.session_state.get('records_updated', 0) + 1
            
                        
        progress_bar.progress(100)
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        # Display results
        st.session_state.print_status = "completed"
        st.session_state.print_message = f"✅ Successfully generated price tags for {len(records)} records"
        st.session_state.print_success = True
        
        st.success(st.session_state.print_message)
        
        # Create download section
        st.subheader("📦 Download Files")
        
        # 1. Price Tags PDF
        col1, col2, col3 = st.columns(3)
        
        with col1:
            tags_filename = f"price_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            st.download_button(
                label="🏷️ Price Tags PDF",
                data=pdf_tags_data,
                file_name=tags_filename,
                mime="application/pdf",
                width='stretch',
                key=f"download_tags_{datetime.now().strftime('%H%M%S')}"
            )
        
        # 2. Receipt PDF (if consignor)
        if receipt_pdf:
            with col2:
                receipt_filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                st.download_button(
                    label="🧾 Batch Receipt PDF",
                    data=receipt_pdf,
                    file_name=receipt_filename,
                    mime="application/pdf",
                    width='stretch',
                    key=f"download_receipt_{datetime.now().strftime('%H%M%S')}"
                )
            
            # Show receipt text for thermal printing
            with st.expander("📋 Receipt Text (for thermal printer)", expanded=False):
                st.code(receipt_text, language=None)
                
                if st.button("📋 Copy Receipt Text"):
                    st.code(receipt_text, language=None)
                    st.info("Receipt text copied to clipboard (simulated)")
        
        # 3. Contract PDF (if consignor)
        if contract_pdf:
            with col3:
                contract_filename = f"consignment_contract_{datetime.now().strftime('%Y%m%d')}_{user_data.get('username', 'user')}.pdf"
                st.download_button(
                    label="📝 Consignment Contract",
                    data=contract_pdf,
                    file_name=contract_filename,
                    mime="application/pdf",
                    width='stretch',
                    key=f"download_contract_{datetime.now().strftime('%H%M%S')}"
                )
        
        # Save the batch size to config for future clearing
        batch_size = len(records)
        self._save_config_value('LAST_PRINT_BATCH_SIZE', str(batch_size))
        
        # Update session state
        st.session_state.pdf_data = pdf_tags_data
        st.session_state.pdf_filename = tags_filename
    
    def _initialize_contract_handler(self):
        """Initialize contract handler with proper API client"""
        # Create a simple API client for the contract handler
        class ContractAPIClient:
            def __init__(self, price_tag_tab):
                self.price_tag_tab = price_tag_tab
            
            def get_config_value(self, key, default=None):
                # Delegate to PriceTagTab's config getter
                return self.price_tag_tab._get_config_value(key, default)
        
        api_client = ContractAPIClient(self)
        self.contract_handler = ContractHandler(api_client)
        return self.contract_handler
    
    def _generate_tags_pdf(self, records):
        """Generate PDF with price tags"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        output_path = temp_file.name
        temp_file.close()

        c = canvas.Canvas(output_path, pagesize=letter)
        
        # Layout parameters
        label_width = st.session_state.label_width_mm * mm
        label_height = st.session_state.label_height_mm * mm
        left_margin = st.session_state.left_margin_mm * mm
        gutter_spacing = st.session_state.gutter_spacing_mm * mm
        top_margin = st.session_state.top_margin_mm * mm
        rows = 15
        columns = 4

        labels_per_page = rows * columns
        current_label = 0
        
        # Pre-fetch consignor data for all records
        consignor_cache = {}
        consignor_ids = set()
        
        # Collect unique consignor IDs
        for record in records:
            consignor_id = record.get('consignor_id')
            if consignor_id:
                consignor_ids.add(consignor_id)
        
        # Fetch consignor data for all unique IDs
        for consignor_id in consignor_ids:
            initials = self._get_consignor_initials(consignor_id)
            if initials:
                consignor_cache[consignor_id] = initials
                print(f"[INITIALS LOG] Consignor ID {consignor_id} -> Initials: '{initials}'")
            else:
                print(f"[INITIALS LOG] Consignor ID {consignor_id} -> No initials found")
        
        for idx, record in enumerate(records):
            if current_label % labels_per_page == 0 and current_label > 0:
                c.showPage()
            
            row = (current_label % labels_per_page) // columns
            col = (current_label % labels_per_page) % columns
            
            # FIXED: Use row instead of (row + 1) to start from top
            x = left_margin + col * (label_width + gutter_spacing)
            y = letter[1] - top_margin - (row+1) * label_height  # CHANGED: row instead of (row + 1)
            
            barcode_number = record.get('barcode')

            if not barcode_number:
                raise ValueError(f"Record ID {record.get('id')} has null barcode. Artist: {record.get('artist', 'Unknown')}, Title: {record.get('title', 'Unknown')}")

            # Get consignor initials from cache
            consignor_id = record.get('consignor_id')
            consignor_initials = consignor_cache.get(consignor_id) if consignor_id else None
            
            print(f"[TAG LOG] Generating tag #{idx+1}: Record ID {record.get('id')}, Artist: {record.get('artist')}, Consignor ID: {consignor_id}, Initials: '{consignor_initials}'")
            
            error = self._draw_tag(c, x, y, label_width, label_height, record, barcode_number, consignor_initials)
            if error:
                print(f"[TAG ERROR] {error}")

            current_label += 1
        
        c.save()
        
        # Read PDF data
        with open(output_path, "rb") as f:
            pdf_data = f.read()
        
        # Clean up
        os.unlink(output_path)
        
        return pdf_data

    def _draw_tag(self, c, x, y, label_width, label_height, record, barcode_number, consignor_initials=None):
        """Draw a single price tag with consignor initials in format: genre|artist|(consignor initials)"""
        if not barcode_number:
            raise ValueError(f"Record ID {record.get('id')} has null barcode. Artist: {record.get('artist', 'Unknown')}, Title: {record.get('title', 'Unknown')}")

        # Use lowercase keys from session_state
        params = {
            'price_font_size': st.session_state.price_font_size,
            'price_y_pos': st.session_state.price_y_pos,
            'text_font_size': st.session_state.text_font_size,
            'barcode_y_pos': st.session_state.barcode_y_pos,
            'barcode_height': st.session_state.barcode_height,
            'print_borders': st.session_state.print_borders
        }
        
        left_bound = x + 2 * mm
        right_bound = x + label_width - 2 * mm
        printable_width = label_width - 4 * mm

        if params.get('print_borders', True):
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.5)
            c.rect(x, y, label_width, label_height, stroke=1, fill=0)
        
        top_start = y + label_height - 2 * mm

        # Draw price
        price = record.get('store_price', 0.0)
        price_text = f"${price:.2f}"
        c.setFont("Helvetica-Bold", params['price_font_size'])
        price_width = c.stringWidth(price_text, "Helvetica-Bold", params['price_font_size'])
        
        if price_width > printable_width:
            return f"Price text too wide: '{price_text}'"
        
        price_x = left_bound + (printable_width - price_width) / 2
        price_y = top_start - (params['price_y_pos'] * mm)
        c.drawString(price_x, price_y, price_text)
        
        # Draw genre, artist, and consignor initials
        genre = record.get('genre_name', 'Unknown')[:15]
        artist = record.get('artist', 'Unknown')[:20]
        
        # Build the text with consignor initials
        if consignor_initials and consignor_initials.strip():
            # Format: genre|artist|(initials)
            genre_artist_text = f"{genre} | {artist} | ({consignor_initials})"
            print(f"[DRAW LOG] With initials: {genre_artist_text}")
        else:
            # Format: genre|artist
            genre_artist_text = f"{genre} | {artist}"
            print(f"[DRAW LOG] Without initials: {genre_artist_text}")
        
        MAX_LENGTH = 40  # Increased from 35 to accommodate initials
        SEPARATOR = ' | '
        
        # Truncate text if too long
        if len(genre_artist_text) > MAX_LENGTH:
            # Try to truncate artist first
            parts = genre_artist_text.split(SEPARATOR)
            if len(parts) >= 3:  # Has initials: genre, artist, (initials)
                genre_part = parts[0]
                artist_part = parts[1]
                initials_part = parts[2] if len(parts) > 2 else ""
                
                # Calculate available space for artist
                available_length = MAX_LENGTH - len(genre_part) - len(SEPARATOR)*2 - len(initials_part)
                if available_length > 3:  # Need at least 3 chars for artist (e.g., "A…")
                    artist_part = artist_part[:available_length-1] + '…'
                    genre_artist_text = f"{genre_part}{SEPARATOR}{artist_part}{SEPARATOR}{initials_part}"
                else:
                    # Artist too short, truncate genre instead
                    available_length = MAX_LENGTH - len(artist_part) - len(SEPARATOR)*2 - len(initials_part)
                    if available_length > 3:
                        genre_part = genre_part[:available_length-1] + '…'
                        genre_artist_text = f"{genre_part}{SEPARATOR}{artist_part}{SEPARATOR}{initials_part}"
                    else:
                        # Everything too long, use just genre and initials
                        available_length = MAX_LENGTH - len(initials_part) - len(SEPARATOR)
                        if available_length > 3:
                            genre_part = genre_part[:available_length-1] + '…'
                            genre_artist_text = f"{genre_part}{SEPARATOR}{initials_part}"
                        else:
                            # Still too long, use just genre
                            genre_artist_text = genre_part[:MAX_LENGTH-1] + '…'
            elif len(parts) == 2:  # No initials: genre, artist
                genre_part = parts[0]
                artist_part = parts[1]
                
                # Calculate available space
                available_length = MAX_LENGTH - len(genre_part) - len(SEPARATOR)
                if available_length > 3:
                    artist_part = artist_part[:available_length-1] + '…'
                    genre_artist_text = f"{genre_part}{SEPARATOR}{artist_part}"
                else:
                    # Artist too short, truncate genre instead
                    available_length = MAX_LENGTH - len(artist_part) - len(SEPARATOR)
                    if available_length > 3:
                        genre_part = genre_part[:available_length-1] + '…'
                        genre_artist_text = f"{genre_part}{SEPARATOR}{artist_part}"
                    else:
                        # Everything too long, use just genre
                        genre_artist_text = genre_part[:MAX_LENGTH-1] + '…'
        
        c.setFont("Helvetica", params['text_font_size'])
        genre_artist_width = c.stringWidth(genre_artist_text, "Helvetica", params['text_font_size'])
        
        if genre_artist_width > printable_width:
            return f"Genre/Artist text too wide: '{genre_artist_text}'"
        
        genre_artist_x = left_bound + (printable_width - genre_artist_width) / 2
        genre_artist_y = price_y - 4 * mm
        c.drawString(genre_artist_x, genre_artist_y, genre_artist_text)

        # Draw barcode
        if barcode_number:
            barcode_bytes = self._generate_barcode(barcode_number)
            if barcode_bytes:
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    temp_file.write(barcode_bytes.getvalue())
                    temp_path = temp_file.name
                
                barcode_height = params['barcode_height'] * mm
                barcode_width = 25 * mm
                
                if barcode_width > printable_width:
                    os.unlink(temp_path)
                    return f"Barcode too wide"
                
                barcode_x = left_bound + (printable_width - barcode_width) / 2
                barcode_y = y + (params['barcode_y_pos'] * mm)
                
                c.drawImage(temp_path, barcode_x, barcode_y, width=barcode_width, height=barcode_height)
                os.unlink(temp_path)
        
        return None

    def _get_consignor_initials(self, consignor_id):
        """Get consignor initials by ID"""
        if not consignor_id:
            print(f"[INITIALS LOG] No consignor_id provided")
            return None
            
        try:
            print(f"[INITIALS LOG] Getting initials for consignor_id: {consignor_id}")
            
            # First try to get from the users list if we have it cached
            if hasattr(st.session_state, 'users_cache') and st.session_state.users_cache:
                print(f"[INITIALS LOG] Checking users_cache (size: {len(st.session_state.users_cache)})")
                for user in st.session_state.users_cache:
                    if user['id'] == consignor_id:
                        initials = user.get('initials')
                        print(f"[INITIALS LOG] Found in cache: user {user.get('username')}, initials='{initials}'")
                        if initials and str(initials).strip():
                            return str(initials).strip()
                        return None
            
            # If not in cache, fetch directly from API
            print(f"[INITIALS LOG] Fetching from API: {self.base_url}/users/{consignor_id}")
            response = requests.get(f"{self.base_url}/users/{consignor_id}")
            if response.status_code == 200:
                user_data = response.json()
                initials = user_data.get('initials')
                print(f"[INITIALS LOG] API response: initials='{initials}'")
                if initials and str(initials).strip():
                    return str(initials).strip()
                else:
                    print(f"[INITIALS LOG] No initials in API response or empty")
            else:
                print(f"[INITIALS LOG] API error: {response.status_code}")
        except Exception as e:
            print(f"[INITIALS LOG] Exception getting initials: {e}")
        
        return None
    
    def _render_page_layout_configuration(self):
        st.write("**Page Layout Settings**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            label_width_mm = st.number_input(
                "Label Width (mm)",
                min_value=10.0,
                max_value=100.0,
                value=st.session_state.label_width_mm,
                step=0.5,
                key="widget_label_width_mm",
                on_change=lambda: self._save_page_layout_config('label_width_mm', st.session_state.widget_label_width_mm)
            )
            
            label_height_mm = st.number_input(
                "Label Height (mm)",
                min_value=10.0,
                max_value=100.0,
                value=st.session_state.label_height_mm,
                step=0.5,
                key="widget_label_height_mm",
                on_change=lambda: self._save_page_layout_config('label_height_mm', st.session_state.widget_label_height_mm)
            )
            
            left_margin_mm = st.number_input(
                "Left Margin (mm)",
                min_value=0.0,
                max_value=50.0,
                value=st.session_state.left_margin_mm,
                step=0.5,
                key="widget_left_margin_mm",
                on_change=lambda: self._save_page_layout_config('left_margin_mm', st.session_state.widget_left_margin_mm)
            )
        
        with col2:
            gutter_spacing_mm = st.number_input(
                "Gutter Spacing (mm)",
                min_value=0.0,
                max_value=50.0,
                value=st.session_state.gutter_spacing_mm,
                step=0.5,
                key="widget_gutter_spacing_mm",
                on_change=lambda: self._save_page_layout_config('gutter_spacing_mm', st.session_state.widget_gutter_spacing_mm)
            )
            
            top_margin_mm = st.number_input(
                "Top Margin (mm)",
                min_value=0.0,
                max_value=50.0,
                value=st.session_state.top_margin_mm,
                step=0.5,
                key="widget_top_margin_mm",
                on_change=lambda: self._save_page_layout_config('top_margin_mm', st.session_state.widget_top_margin_mm)
            )
            
            font_size = st.number_input(
                "Base Font Size",
                min_value=4,
                max_value=20,
                value=st.session_state.font_size,
                key="widget_font_size",
                on_change=lambda: self._save_page_layout_config('font_size', st.session_state.widget_font_size)
            )
    
    def _render_price_tag_design_configuration(self):
        st.write("**Price Tag Design Settings**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            price_font_size = st.number_input(
                "Price Font Size",
                min_value=6,
                max_value=20,
                value=st.session_state.price_font_size,
                key="widget_price_font_size",
                on_change=lambda: self._save_tag_design_config('price_font_size', st.session_state.widget_price_font_size)
            )
            
            price_y_pos = st.number_input(
                "Price Y Position (mm)",
                min_value=0.0,
                max_value=20.0,
                value=st.session_state.price_y_pos,
                step=0.5,
                key="widget_price_y_pos",
                on_change=lambda: self._save_tag_design_config('price_y_pos', st.session_state.widget_price_y_pos)
            )
            
            text_font_size = st.number_input(
                "Text Font Size",
                min_value=4,
                max_value=12,
                value=st.session_state.text_font_size,
                key="widget_text_font_size",
                on_change=lambda: self._save_tag_design_config('text_font_size', st.session_state.widget_text_font_size)
            )
                
        with col2:
            barcode_y_pos = st.number_input(
                "Barcode Y Position (mm)",
                min_value=0.0,
                max_value=20.0,
                value=st.session_state.barcode_y_pos,
                step=0.5,
                key="widget_barcode_y_pos",
                on_change=lambda: self._save_tag_design_config('barcode_y_pos', st.session_state.widget_barcode_y_pos)
            )
            
            barcode_height = st.number_input(
                "Barcode Height (mm)",
                min_value=0.0,
                max_value=12.0,
                value=st.session_state.barcode_height,
                step=0.5,
                key="widget_barcode_height",
                on_change=lambda: self._save_tag_design_config('barcode_height', st.session_state.widget_barcode_height)
            )
            
            print_borders = st.checkbox(
                "Print Borders Around Labels",
                value=st.session_state.print_borders,
                key="widget_print_borders",
                on_change=lambda: self._save_tag_design_config('print_borders', st.session_state.widget_print_borders)
            )

    def _get_all_users(self):
        """Get all users via API - FIXED: Use cache if available"""
        try:
            # Check if we have users in session state cache
            if hasattr(st.session_state, 'users_cache') and st.session_state.users_cache:
                return st.session_state.users_cache
            
            # Otherwise make API call
            response = requests.get(f"https://www.pigstylemusic.com/users")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    users = data.get('users', [])
                    # Cache the users
                    st.session_state.users_cache = users
                    print(f"[USERS LOG] Loaded {len(users)} users into cache")
                    for user in users:
                        print(f"[USERS LOG] User: {user.get('username')} (ID: {user.get('id')}), Initials: '{user.get('initials')}'")
                    return users
            # Return empty list instead of None
            return []
        except Exception as e:
            st.error(f"Error getting users: {e}")
            return []  # Return empty list instead of None
    
    def _get_new_records_for_user(self, user_id=None):
        """
        Get NEW records (status_id = 1) for a specific user (or all users) 
        sorted by creation date (newest first).
        """
        try:
            if user_id:
                # Get all records for this user
                response = requests.get(f"{self.base_url}/records/user/{user_id}")
            else:
                # Get all records
                response = requests.get(f"{self.base_url}/records")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    records = data.get('records', [])
                    
                    # Filter for NEW records (status_id = 1)
                    new_records = [r for r in records if r.get('status_id') == 1]
                    
                    # Sort by creation date (NEWEST first)
                    new_records.sort(key=lambda x: x.get('created_at', '') or '', reverse=True)
                    
                    print(f"[RECORDS LOG] Found {len(new_records)} new records for user_id: {user_id}")
                    return new_records
            return []
        except Exception as e:
            st.error(f"Error getting new records: {e}")
            return []
    
    def _get_all_records_for_user(self, user_id=None):
        """
        Get ALL records for a specific user (or all users) 
        sorted by creation date (newest first).
        """
        try:
            if user_id:
                # Get all records for this user
                response = requests.get(f"{self.base_url}/records/user/{user_id}")
            else:
                # Get all records
                response = requests.get(f"{self.base_url}/records")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    records = data.get('records', [])
                    
                    # Sort by creation date (NEWEST first)
                    records.sort(key=lambda x: x.get('created_at', '') or '', reverse=True)
                    
                    return records
            return []
        except Exception as e:
            st.error(f"Error getting all records: {e}")
            return []
    
    def _get_user_by_id(self, user_id, users_list):
        """Get user by ID from users list"""
        for user in users_list:
            if user['id'] == user_id:
                return user
        return None
    
    def _generate_barcode(self, barcode_number):
        """Generate barcode image"""
        if not barcode_number:
            return None
            
        try:
            barcode_class = barcode.get_barcode_class('code128')
            barcode_obj = barcode_class(str(barcode_number), writer=ImageWriter())
            
            buffer = io.BytesIO()
            barcode_obj.write(buffer, options={
                'module_height': 6.0,
                'font_size': 0,
                'quiet_zone': 1.0,
                'write_text': False
            })
            buffer.seek(0)
            
            return buffer
        except Exception as e:
            st.error(f"Error generating barcode: {e}")
            return None
    
    def _get_records_by_ids(self, record_ids):
        """Get records by IDs via API"""
        try:
            response = requests.post(
                f"https://www.pigstylemusic.com/records/by-ids",
                json={'record_ids': record_ids}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('records', [])
            return []
        except Exception as e:
            st.error(f"Error getting records by IDs: {e}")
            return []
    
    def _update_record(self, record_id, updates):
        print(f"_update_record record_id: {record_id}, updates {updates}")

        """Update record via API"""
        try:
            response = requests.put(
                f"https://www.pigstylemusic.com/records/{record_id}",
                json=updates
            )
            return response.status_code == 200
        except Exception as e:
            st.error(f"Error updating record: {e}")
            return False