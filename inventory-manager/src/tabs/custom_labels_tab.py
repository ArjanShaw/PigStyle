import streamlit as st
import pandas as pd
from datetime import datetime
import tempfile
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm

class CustomLabelsTab:
    def __init__(self, config_cache=None):
        self.config_cache = config_cache
        self.base_url = "https://www.pigstylemusic.com"
        
        # Initialize config values
        self._validate_configuration()
    
    def _validate_configuration(self):
        """Validate that all required configuration values exist"""
        config_keys = [
            'LABEL_WIDTH_MM', 'LABEL_HEIGHT_MM', 'LEFT_MARGIN_MM',
            'GUTTER_SPACING_MM', 'TOP_MARGIN_MM'
        ]
        
        for key in config_keys:
            value = self._get_config_value(key)
            if value is None:
                st.error(f"Configuration key '{key}' not found")
                st.stop()
            
            # Convert to float
            st.session_state[key.lower()] = float(value)
    
    def _get_config_value(self, config_key, default=None):
        """Get config value from cache or API"""
        if hasattr(st.session_state, 'config_cache') and st.session_state.config_cache:
            value = st.session_state.config_cache.get(config_key)
            if value is not None:
                try:
                    return float(value) if '.' in str(value) else int(value)
                except:
                    return value
        return default
    
    def render(self):
        st.header("🏷️ Custom Labels Printing")
        
        # Display current layout settings
        with st.expander("📐 Current Layout Settings", expanded=False):
            self._render_layout_settings()
        
        st.divider()
        st.subheader("📝 Custom Label Content")
        
        # Explanation
        st.info("""
        **Instructions:**
        1. Enter custom text for each label (up to 60 labels per page)
        2. Text will be centered in each label with maximum font size
        3. Labels are arranged in 15 rows × 4 columns
        4. Empty labels will be skipped
        """)
        
        # Get layout parameters
        rows = 15
        columns = 4
        total_labels = rows * columns
        
        # Create a grid of text inputs
        st.write(f"**Enter text for {total_labels} labels:**")
        
        # Initialize session state for labels if not exists
        if 'custom_labels_text' not in st.session_state:
            st.session_state.custom_labels_text = [''] * total_labels
        
        # Create a responsive grid of text inputs
        labels_per_row = 4  # How many input columns per row in the UI
        
        # Add a clear all button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🗑️ Clear All", type="secondary"):
                st.session_state.custom_labels_text = [''] * total_labels
                st.rerun()
        
        # Create the grid
        for i in range(0, total_labels, labels_per_row):
            cols = st.columns(labels_per_row)
            for col_idx, col in enumerate(cols):
                label_idx = i + col_idx
                if label_idx < total_labels:
                    with col:
                        # Calculate position for user reference
                        row_num = (label_idx // columns) + 1
                        col_num = (label_idx % columns) + 1
                        
                        label_text = st.text_input(
                            f"R{row_num}C{col_num}",
                            value=st.session_state.custom_labels_text[label_idx],
                            key=f"label_{label_idx}",
                            help=f"Label at position: Row {row_num}, Column {col_num}"
                        )
                        st.session_state.custom_labels_text[label_idx] = label_text
        
        # Count non-empty labels
        non_empty_count = sum(1 for text in st.session_state.custom_labels_text if text.strip())
        
        # Action buttons
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("📝 Labels with Text", non_empty_count)
        
        with col2:
            if non_empty_count > 0:
                if st.button("🖨️ Generate Custom Labels PDF", type="primary", width='stretch'):
                    self._generate_custom_labels_pdf(st.session_state.custom_labels_text)
            else:
                st.button("🖨️ Generate Custom Labels PDF", disabled=True, width='stretch',
                         help="Add text to at least one label")
        
        # Add preview option
        if non_empty_count > 0:
            with st.expander("👁️ Preview Labels", expanded=False):
                self._preview_labels(st.session_state.custom_labels_text)
    
    def _render_layout_settings(self):
        """Display current layout settings (read-only)"""
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Label Width", f"{st.session_state.label_width_mm:.1f} mm")
            st.metric("Label Height", f"{st.session_state.label_height_mm:.1f} mm")
            st.metric("Left Margin", f"{st.session_state.left_margin_mm:.1f} mm")
        
        with col2:
            st.metric("Gutter Spacing", f"{st.session_state.gutter_spacing_mm:.1f} mm")
            st.metric("Top Margin", f"{st.session_state.top_margin_mm:.1f} mm")
            st.metric("Layout", "15 × 4 (60 labels/page)")
    
    def _generate_custom_labels_pdf(self, labels_text):
        """Generate PDF with custom labels"""
        if not any(text.strip() for text in labels_text):
            st.error("Please enter text for at least one label")
            return
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        output_path = temp_file.name
        temp_file.close()
        
        # Generate PDF
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
        
        # Progress indicator
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        labels_processed = 0
        non_empty_labels = [text for text in labels_text if text.strip()]
        total_to_process = len(non_empty_labels)
        
        for label_idx, text in enumerate(labels_text):
            if not text.strip():
                continue
            
            # Handle page breaks
            if labels_processed % labels_per_page == 0 and labels_processed > 0:
                c.showPage()
            
            # Calculate position on page
            position_on_page = labels_processed % labels_per_page
            row = position_on_page // columns
            col = position_on_page % columns
            
            # Calculate coordinates
            x = left_margin + col * (label_width + gutter_spacing)
            y = letter[1] - top_margin - (row + 1) * label_height
            
            # Draw label
            self._draw_custom_label(c, x, y, label_width, label_height, text.strip())
            
            labels_processed += 1
            
            # Update progress
            progress = labels_processed / total_to_process
            progress_bar.progress(progress)
            status_text.text(f"Generating label {labels_processed}/{total_to_process}")
        
        c.save()
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        # Read PDF data
        with open(output_path, "rb") as f:
            pdf_data = f.read()
        
        # Clean up
        os.unlink(output_path)
        
        # Show success and download button
        st.success(f"✅ Successfully generated {labels_processed} custom labels")
        
        # Create download button
        filename = f"custom_labels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        st.download_button(
            label="📥 Download Custom Labels PDF",
            data=pdf_data,
            file_name=filename,
            mime="application/pdf",
            type="primary"
        )
    
    def _draw_custom_label(self, c, x, y, label_width, label_height, text):
        """Draw a single custom label with centered text"""
        # REMOVED: Border drawing - labels will print without borders
        
        # Calculate text area with margins
        margin = 2 * mm
        text_area_width = label_width - (2 * margin)
        text_area_height = label_height - (2 * margin)
        
        # Start with maximum font size and decrease until text fits
        max_font_size = 72  # Start big
        font_name = "Helvetica-Bold"
        
        for font_size in range(max_font_size, 6, -1):
            c.setFont(font_name, font_size)
            text_width = c.stringWidth(text, font_name, font_size)
            text_height = font_size * 0.75  # Approximate
            
            # Check if text fits in available space
            if text_width <= text_area_width and text_height <= text_area_height:
                # Calculate position for centered text
                text_x = x + margin + (text_area_width - text_width) / 2
                
                # FIX: Adjusted Y position - lowered by 2mm
                # Calculate vertical center position
                vertical_center = y + margin + (text_area_height - text_height) / 2
                
                # Adjust down by 2mm to fix positioning
                text_y = vertical_center + text_height * 0.3 - (2 * mm)
                
                # Ensure text doesn't go below label bottom
                if text_y < y + margin:
                    text_y = y + margin + 1  # Minimum 1mm from bottom
                
                # Draw text
                c.drawString(text_x, text_y, text)
                break
    
    def _preview_labels(self, labels_text):
        """Create a visual preview of the labels"""
        rows = 15
        columns = 4
        
        # Create HTML table for preview
        html = """
        <style>
            .label-preview {
                border: 1px solid #ddd;
                padding: 4px;
                margin: 2px;
                min-height: 40px;
                font-size: 10px;
                word-wrap: break-word;
                overflow: hidden;
                background-color: #f9f9f9;
            }
            .empty-label {
                background-color: #eee;
                color: #999;
            }
            .preview-table {
                width: 100%;
                border-collapse: collapse;
            }
            .preview-table td {
                border: 1px solid #ddd;
                text-align: center;
                vertical-align: middle;
            }
        </style>
        """
        
        html += "<table class='preview-table'>"
        
        for row in range(rows):
            html += "<tr>"
            for col in range(columns):
                idx = row * columns + col
                text = labels_text[idx]
                css_class = "label-preview" + (" empty-label" if not text.strip() else "")
                display_text = text[:20] + "..." if len(text) > 20 else text
                display_text = display_text or "(empty)"
                
                html += f"<td class='{css_class}'><small><strong>R{row+1}C{col+1}:</strong><br>{display_text}</small></td>"
            html += "</tr>"
        
        html += "</table>"
        
        st.markdown(html, unsafe_allow_html=True)
        
        # Show statistics
        non_empty = sum(1 for text in labels_text if text.strip())
        st.caption(f"Preview showing {non_empty} of {len(labels_text)} labels with text")