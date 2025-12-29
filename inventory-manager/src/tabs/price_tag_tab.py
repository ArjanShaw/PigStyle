import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import tempfile
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io
from PIL import Image
import time

class PriceTagTab:
    def __init__(self, base_url="https://arjanshaw.pythonanywhere.com"):
        """Initialize with API base URL"""
        self.base_url = base_url
        self.api_client = APIClient(base_url)
    
    def render(self):
        st.title("🏷️ Price Tag Printer")
        
        # Initialize session state for selected records
        if 'selected_records_for_printing' not in st.session_state:
            st.session_state.selected_records_for_printing = []
        
        if 'search_results_price_tags' not in st.session_state:
            st.session_state.search_results_price_tags = []
        
        # Two column layout for search and selection
        col1, col2 = st.columns([2, 1])
        
        with col1:
            self._render_search_section()
        
        with col2:
            self._render_selection_section()
        
        # Print button and options
        if st.session_state.selected_records_for_printing:
            st.divider()
            self._render_print_options()

    def _render_search_section(self):
        """Render the search section"""
        st.subheader("🔍 Search Records")
        
        with st.form(key="price_tag_search_form"):
            search_input = st.text_input(
                "Search by artist, title, or catalog number:",
                placeholder="Enter search term..."
            )
            
            col1, col2 = st.columns(2)
            with col1:
                search_button = st.form_submit_button("🔍 Search", use_container_width=True)
            with col2:
                if st.form_submit_button("🗑️ Clear Results", type="secondary", use_container_width=True):
                    st.session_state.search_results_price_tags = []
                    st.rerun()
        
        if search_button and search_input:
            with st.spinner("Searching records..."):
                results = self._search_records(search_input)
                st.session_state.search_results_price_tags = results
        
        # Display search results
        if st.session_state.search_results_price_tags:
            st.write(f"**Found {len(st.session_state.search_results_price_tags)} records:**")
            
            for record in st.session_state.search_results_price_tags:
                self._render_search_result_item(record)

    def _render_search_result_item(self, record):
        """Render individual search result item"""
        col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
        
        with col1:
            if record.get('image_url'):
                try:
                    st.image(record['image_url'], width=50)
                except:
                    st.write("📷")
            else:
                st.write("📷")
        
        with col2:
            st.write(f"**{record.get('artist', 'Unknown')}**")
            st.write(f"*{record.get('title', 'Unknown')}*")
            st.write(f"Cat: {record.get('catalog_number', 'N/A')}")
        
        with col3:
            price = record.get('store_price', 0)
            st.write(f"**${price:.2f}**")
        
        with col4:
            # Check if already selected
            is_selected = any(r.get('id') == record.get('id') for r in st.session_state.selected_records_for_printing)
            
            if is_selected:
                if st.button("✅ Added", key=f"added_{record['id']}", disabled=True, use_container_width=True):
                    pass
            else:
                if st.button("➕ Add", key=f"add_{record['id']}", use_container_width=True):
                    st.session_state.selected_records_for_printing.append(record)
                    st.success(f"Added {record.get('artist', 'Unknown')} - {record.get('title', 'Unknown')}")
                    st.rerun()
        
        st.divider()

    def _render_selection_section(self):
        """Render the selection section"""
        st.subheader("🛒 Selected for Printing")
        
        selected_count = len(st.session_state.selected_records_for_printing)
        
        if selected_count == 0:
            st.info("No records selected. Search and add records to print price tags.")
            return
        
        st.success(f"**{selected_count} records selected**")
        
        # Calculate total value
        total_value = sum(float(r.get('store_price', 0)) for r in st.session_state.selected_records_for_printing)
        st.write(f"**Total Value:** ${total_value:.2f}")
        
        # Show selected items with remove option
        for i, record in enumerate(st.session_state.selected_records_for_printing):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"{record.get('artist', 'Unknown')}")
                st.write(f"*{record.get('title', 'Unknown')[:20]}...*")
            
            with col2:
                st.write(f"${record.get('store_price', 0):.2f}")
            
            with col3:
                if st.button("❌", key=f"remove_{record['id']}", help="Remove"):
                    st.session_state.selected_records_for_printing.pop(i)
                    st.rerun()
        
        # Clear all button
        if st.button("🗑️ Clear All", type="secondary", use_container_width=True):
            st.session_state.selected_records_for_printing = []
            st.rerun()

    def _render_print_options(self):
        """Render printing options"""
        st.subheader("🖨️ Print Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            tag_size = st.selectbox(
                "Tag Size:",
                ["Small (2\" x 3\")", "Medium (2.5\" x 3.5\")", "Large (3\" x 4\")"],
                index=1
            )
            
            include_barcode = st.checkbox("Include Barcode", value=True)
            include_image = st.checkbox("Include Album Art", value=True)
        
        with col2:
            copies_per_record = st.number_input("Copies per record:", min_value=1, max_value=10, value=1)
            
            paper_size = st.selectbox(
                "Paper Size:",
                ["Letter (8.5\" x 11\")", "A4 (210mm x 297mm)"],
                index=0
            )
        
        # Layout options
        layout = st.radio(
            "Layout:",
            ["Single column", "Two columns", "Auto-fit"],
            index=2,
            horizontal=True
        )
        
        # Preview and print buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("👁️ Preview PDF", use_container_width=True, type="secondary"):
                self._generate_preview_pdf()
        
        with col2:
            if st.button("🖨️ Generate PDF", type="primary", use_container_width=True):
                pdf_bytes = self._generate_pdf(
                    st.session_state.selected_records_for_printing,
                    tag_size,
                    include_barcode,
                    include_image,
                    copies_per_record,
                    paper_size,
                    layout
                )
                
                # Offer download
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_bytes,
                    file_name=f"price_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

    def _search_records(self, search_term):
        """Search records via API"""
        try:
            response = requests.get(f"{self.base_url}/search?q={search_term}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('records', [])
            
            # Fallback: get all records and filter
            response = requests.get(f"{self.base_url}/records?limit=1000")
            if response.status_code == 200:
                data = response.json()
                records = data.get('records', [])
                
                # Filter locally
                search_lower = search_term.lower()
                filtered = []
                
                for record in records:
                    artist = str(record.get('artist', '')).lower()
                    title = str(record.get('title', '')).lower()
                    catalog = str(record.get('catalog_number', '')).lower()
                    
                    if (search_lower in artist or 
                        search_lower in title or 
                        search_lower in catalog):
                        filtered.append(record)
                
                return filtered
            
            return []
            
        except Exception as e:
            st.error(f"Search error: {e}")
            return []

    def _generate_preview_pdf(self):
        """Generate a preview of the price tags"""
        with st.spinner("Generating preview..."):
            try:
                # Create a simple preview
                preview_html = self._generate_preview_html()
                st.components.v1.html(preview_html, height=400, scrolling=True)
                
                st.success("Preview generated successfully!")
                
            except Exception as e:
                st.error(f"Error generating preview: {e}")

    def _generate_preview_html(self):
        """Generate HTML preview of price tags"""
        html = """
        <style>
            .preview-container {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                padding: 20px;
                background: #f5f5f5;
                border-radius: 10px;
            }
            .price-tag {
                background: white;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .artist {
                font-weight: bold;
                font-size: 12px;
                margin: 0;
            }
            .title {
                font-size: 10px;
                color: #666;
                margin: 2px 0;
            }
            .price {
                font-size: 14px;
                font-weight: bold;
                color: #e74c3c;
                margin: 5px 0;
            }
            .barcode {
                font-family: monospace;
                font-size: 8px;
                letter-spacing: 1px;
                background: #f8f8f8;
                padding: 2px;
                border-radius: 2px;
            }
        </style>
        <div class="preview-container">
        """
        
        # Add preview items (first 6 records or all if less)
        records_to_preview = st.session_state.selected_records_for_printing[:6]
        
        for record in records_to_preview:
            artist = record.get('artist', 'Unknown')[:20]
            title = record.get('title', 'Unknown')[:30]
            price = record.get('store_price', 0)
            barcode = record.get('barcode', '1234567890')
            
            html += f"""
            <div class="price-tag">
                <p class="artist">{artist}</p>
                <p class="title">{title}</p>
                <p class="price">${price:.2f}</p>
                <div class="barcode">{barcode}</div>
            </div>
            """
        
        html += "</div>"
        return html

    def _generate_pdf(self, records, tag_size, include_barcode, include_image, copies, paper_size, layout):
        """Generate PDF with price tags"""
        try:
            # Create PDF in memory
            buffer = io.BytesIO()
            
            # Set up PDF canvas
            if paper_size == "A4 (210mm x 297mm)":
                pagesize = (595, 842)  # A4 in points
            else:
                pagesize = letter
            
            c = canvas.Canvas(buffer, pagesize=pagesize)
            
            # Calculate positions based on layout
            width, height = pagesize
            
            if layout == "Single column":
                cols = 1
                rows = 8
            elif layout == "Two columns":
                cols = 2
                rows = 12
            else:  # Auto-fit
                if tag_size == "Small (2\" x 3\")":
                    cols = 3
                    rows = 15
                elif tag_size == "Medium (2.5\" x 3.5\")":
                    cols = 2
                    rows = 10
                else:  # Large
                    cols = 2
                    rows = 8
            
            # Calculate cell dimensions
            cell_width = width / cols
            cell_height = height / rows
            
            # Current position
            current_col = 0
            current_row = 0
            
            # Generate tags
            for record in records:
                for copy_num in range(copies):
                    # Calculate position
                    x = current_col * cell_width
                    y = height - ((current_row + 1) * cell_height)
                    
                    # Draw price tag
                    self._draw_price_tag(
                        c, record, 
                        x + 10, y + 10, 
                        cell_width - 20, cell_height - 20,
                        include_barcode, include_image
                    )
                    
                    # Move to next position
                    current_col += 1
                    if current_col >= cols:
                        current_col = 0
                        current_row += 1
                        
                        if current_row >= rows:
                            # New page
                            c.showPage()
                            current_row = 0
            
            # Save PDF
            c.save()
            
            # Get PDF bytes
            buffer.seek(0)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            return pdf_bytes
            
        except Exception as e:
            st.error(f"Error generating PDF: {e}")
            return b""

    def _draw_price_tag(self, canvas, record, x, y, width, height, include_barcode, include_image):
        """Draw a single price tag"""
        try:
            # Draw border
            canvas.setStrokeColorRGB(0.8, 0.8, 0.8)
            canvas.setLineWidth(1)
            canvas.rect(x, y, width, height)
            
            # Set up text
            canvas.setFont("Helvetica", 9)
            canvas.setFillColorRGB(0, 0, 0)
            
            # Artist (bold)
            artist = record.get('artist', 'Unknown Artist')
            if len(artist) > 25:
                artist = artist[:22] + "..."
            
            canvas.setFont("Helvetica-Bold", 10)
            canvas.drawString(x + 5, y + height - 15, artist)
            
            # Title
            title = record.get('title', 'Unknown Title')
            if len(title) > 30:
                title = title[:27] + "..."
            
            canvas.setFont("Helvetica", 8)
            canvas.drawString(x + 5, y + height - 30, title)
            
            # Price (large and red)
            price = float(record.get('store_price', 0))
            canvas.setFont("Helvetica-Bold", 16)
            canvas.setFillColorRGB(0.9, 0.2, 0.2)  # Red
            canvas.drawString(x + 5, y + 20, f"${price:.2f}")
            
            # Barcode (if available)
            if include_barcode:
                barcode = record.get('barcode', '')
                if barcode:
                    canvas.setFont("Courier", 7)
                    canvas.setFillColorRGB(0, 0, 0)
                    canvas.drawString(x + width - 60, y + 15, f"#{barcode}")
            
            # Catalog number
            catalog = record.get('catalog_number', '')
            if catalog:
                canvas.setFont("Helvetica", 7)
                canvas.setFillColorRGB(0.4, 0.4, 0.4)
                canvas.drawString(x + 5, y + 10, f"Cat: {catalog}")
            
            # Try to add image if requested
            if include_image and record.get('image_url'):
                try:
                    # This is simplified - in production you'd fetch and resize the image
                    canvas.setFont("Helvetica", 6)
                    canvas.setFillColorRGB(0.7, 0.7, 0.7)
                    canvas.drawString(x + width - 40, y + height - 15, "[IMG]")
                except:
                    pass
                    
        except Exception as e:
            # If there's an error drawing, just skip this tag
            pass

class APIClient:
    """API client for price tag operations"""
    
    def __init__(self, base_url="https://arjanshaw.pythonanywhere.com"):
        self.base_url = base_url
    
    def search_records(self, search_term):
        """Search records via API"""
        try:
            response = requests.get(f"{self.base_url}/search?q={search_term}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return data.get('records', [])
            
            return []
        except Exception as e:
            st.error(f"Search error: {e}")
            return []
    
    def get_record(self, record_id):
        """Get single record via API"""
        try:
            response = requests.get(f"{self.base_url}/records/{record_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            st.error(f"API Error getting record: {e}")
            return None