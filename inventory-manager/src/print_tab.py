import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.graphics.barcode import code128
import io
import os
from datetime import datetime

class PrintConfig:
    def __init__(self, config_file="print_config.json"):
        self.config_file = config_file
        self.defaults = {
            "label_width_mm": 45.0,
            "label_height_mm": 16.80,
            "left_margin_mm": 6.50,
            "gutter_spacing_mm": 6.50,
            "top_margin_mm": 14.00,
            "font_size": 7,
            "last_genre": "",
            "genre_font_size": 48
        }
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file or use defaults"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    config = self.defaults.copy()
                    config.update(loaded_config)
                    return config
            except Exception as e:
                print(f"Error loading config file: {e}. Using defaults.")
                return self.defaults.copy()
        else:
            # Create default config file
            self._save_config(self.defaults)
            return self.defaults.copy()
    
    def _save_config(self, config):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config file: {e}")
    
    def get(self, key, default=None):
        """Get a configuration value with optional default"""
        return self.config.get(key, default if default is not None else self.defaults.get(key))
    
    def update(self, new_config):
        """Update configuration and save to file"""
        self.config.update(new_config)
        self._save_config(self.config)
    
    def get_all(self):
        """Get all configuration values"""
        return self.config.copy()

class PrintTab:
    def __init__(self):
        self.config = PrintConfig()
        self.labels_per_sheet = 60
        self.page_width, self.page_height = letter
        self._update_dimensions_from_config()
        
    def _update_dimensions_from_config(self):
        """Update dimensions from configuration"""
        config = self.config.get_all()
        self.label_width = config["label_width_mm"] * mm
        self.label_height = config["label_height_mm"] * mm
        self.left_margin = config["left_margin_mm"] * mm
        self.gutter_spacing = config["gutter_spacing_mm"] * mm
        self.top_margin = config["top_margin_mm"] * mm
        self.font_size = config["font_size"]
        
    def render(self):
        st.header("🖨️ Print")
        
        tab1, tab2 = st.tabs(["🏷️ Price Tags", "🎵 Genre Signs"])
        
        with tab1:
            self._render_price_tags()
        
        with tab2:
            self._render_genre_signs()
    
    def _render_price_tags(self):
        """Render the price tags printing interface"""
        st.subheader("Price Tags Printing")
        
        # Layout reference
        self._render_layout_reference()
        
        # Price tags content
        self._render_price_tags_content()
    
    def _render_layout_reference(self):
        """Render the layout reference"""
        st.write("### Layout Reference")
        
        # Try to load the image
        try:
            st.image("price_tag_printt_payout_avery5195.png", 
                    caption="Avery 5195 Label Layout")
        except Exception as e:
            st.info("Avery 5195 layout: 4 columns × 15 rows = 60 labels per sheet")
    
    def _render_price_tags_content(self):
        """Render the price tags content"""
        # Get records from session state (sent from Records tab)
        records_to_print = st.session_state.get('records_to_print', [])
        
        if records_to_print:
            st.success(f"📦 Received {len(records_to_print)} records from Records tab")
            
            # Show selected records
            st.write("### Records to Print")
            for i, record in enumerate(records_to_print):
                artist = record.get('artist', 'Unknown Artist')
                title = record.get('title', 'Unknown Title')
                price = record.get('discogs_median_price', 0) or 0
                price_display = f"${float(price):.2f}" if price else "$N/A"
                st.write(f"{i+1}. **{artist}** - {title} - {price_display}")
            
            # Print settings
            with st.expander("⚙️ Print Settings", expanded=False):
                current_config = self.config.get_all()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    start_label = st.number_input("Start Label Number (1-60)", min_value=1, max_value=60, value=1, key="start_label")
                    font_size = st.slider("Font Size", min_value=6, max_value=12, value=self.config.get("font_size"), key="font_size")
                    
                with col2:
                    label_width_mm = st.number_input("Label Width (mm)", min_value=30.0, max_value=60.0, value=current_config["label_width_mm"], step=0.1, key="label_width")
                    label_height_mm = st.number_input("Label Height (mm)", min_value=10.0, max_value=30.0, value=current_config["label_height_mm"], step=0.1, key="label_height")
                    left_margin_mm = st.number_input("Left Margin (mm)", min_value=1.0, max_value=20.0, value=current_config["left_margin_mm"], step=0.1, key="left_margin")
                
                col3, col4 = st.columns(2)
                
                with col3:
                    gutter_mm = st.number_input("Gutter Spacing (mm)", min_value=1.0, max_value=20.0, value=current_config["gutter_spacing_mm"], step=0.1, key="gutter")
                    top_margin_mm = st.number_input("Top Margin (mm)", min_value=5.0, max_value=30.0, value=current_config["top_margin_mm"], step=0.1, key="top_margin")
            
            # Save configuration
            new_config = {
                "label_width_mm": label_width_mm,
                "label_height_mm": label_height_mm,
                "left_margin_mm": left_margin_mm,
                "gutter_spacing_mm": gutter_mm,
                "top_margin_mm": top_margin_mm,
                "font_size": font_size
            }
            self.config.update(new_config)
            self._update_dimensions_from_config()
            
            # Print buttons
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🖨️ Generate Price Tags PDF"):
                    try:
                        pdf_buffer = self._generate_price_tags_pdf(records_to_print, start_label)
                        st.download_button(
                            label="⬇️ Download Price Tags PDF",
                            data=pdf_buffer.getvalue(),
                            file_name=f"price_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"Error generating PDF: {e}")
            
            with col2:
                if st.button("📄 Generate Test Print"):
                    try:
                        pdf_buffer = self._generate_test_print_pdf(start_label)
                        st.download_button(
                            label="⬇️ Download Test Print PDF",
                            data=pdf_buffer.getvalue(),
                            file_name=f"test_print_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"Error generating test print: {e}")
                
                if st.button("🗑️ Clear Records"):
                    st.session_state.records_to_print = []
                    st.rerun()
        
        else:
            st.info("No records selected for printing. Go to the Records tab and select records to print.")
    
    def _render_genre_signs(self):
        """Render the genre signs printing interface"""
        st.subheader("Genre Signs Printing")
        
        # Get available genres from database
        try:
            all_genres = st.session_state.db_manager.get_all_genres()
            genre_options = all_genres['genre_name'].tolist()
        except:
            genre_options = ["ROCK", "JAZZ", "HIP-HOP", "ELECTRONIC", "POP", "METAL", "FOLK", "SOUL"]
        
        genre_text = st.selectbox("Select genre:", options=genre_options, key="genre_select")
        font_size = st.slider("Font Size", min_value=24, max_value=96, value=48, key="genre_font_size")
        
        if st.button("🖨️ Generate Genre Sign PDF"):
            try:
                pdf_buffer = self._generate_genre_sign_pdf(genre_text, font_size)
                st.download_button(
                    label="⬇️ Download Genre Sign PDF",
                    data=pdf_buffer.getvalue(),
                    file_name=f"genre_sign_{genre_text.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Error generating genre sign: {e}")
    
    def _generate_price_tags_pdf(self, records, start_label):
        """Generate PDF with price tags"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Calculate positions
        array_positions = []
        for array_num in range(4):
            x_start = self.left_margin + (array_num * (self.label_width + self.gutter_spacing))
            array_positions.append(x_start)
        
        # Convert start_label to row/col
        start_row, start_col = self._label_number_to_position(start_label)
        
        # Draw price tags
        self._draw_price_tags(c, records, array_positions, self.top_margin, start_row, start_col)
        
        c.save()
        buffer.seek(0)
        return buffer
    
    def _generate_test_print_pdf(self, start_label):
        """Generate test print PDF"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Calculate positions
        array_positions = []
        for array_num in range(4):
            x_start = self.left_margin + (array_num * (self.label_width + self.gutter_spacing))
            array_positions.append(x_start)
        
        # Convert start_label to row/col
        start_row, start_col = self._label_number_to_position(start_label)
        
        # Draw test page
        self._draw_test_page(c, array_positions, self.top_margin, start_row, start_col)
        
        c.save()
        buffer.seek(0)
        return buffer
    
    def _label_number_to_position(self, label_number):
        """Convert label number to row and column"""
        label_number = label_number - 1
        col = label_number % 4
        row = label_number // 4
        return row + 1, col + 1
    
    def _draw_test_page(self, c, array_positions, top_margin, start_row, start_col):
        """Draw test page with label borders"""
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.5)
        
        start_row_idx = start_row - 1
        start_col_idx = start_col - 1
        
        for array_num, x_start in enumerate(array_positions):
            if array_num < start_col_idx:
                continue
                
            for row in range(15):
                if array_num == start_col_idx and row < start_row_idx:
                    continue
                    
                y_pos = self.page_height - top_margin - (row * self.label_height)
                c.rect(x_start, y_pos - self.label_height, self.label_width, self.label_height)
                
                c.setFont("Helvetica", 6)
                label_num = (array_num * 15) + row + 1
                c.drawString(x_start + 2, y_pos - self.label_height + 2, f"{label_num}")
        
        c.setFont("Helvetica", 12)
        c.drawString(72, 72, f"TEST PRINT - Starting at label {start_row},{start_col}")
    
    def _draw_price_tags(self, c, records, array_positions, top_margin, start_row, start_col):
        """Draw price tags with record information"""
        current_label = 0
        total_labels = len(records)
        
        start_row_idx = start_row - 1
        start_col_idx = start_col - 1
        
        for array_num, x_start in enumerate(array_positions):
            if array_num < start_col_idx:
                continue
                
            for row in range(15):
                if array_num == start_col_idx and row < start_row_idx:
                    continue
                    
                if current_label >= total_labels:
                    break
                
                y_pos = self.page_height - top_margin - (row * self.label_height)
                
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(0.25)
                c.rect(x_start, y_pos - self.label_height, self.label_width, self.label_height)
                
                record = records[current_label]
                self._draw_label_content(c, record, x_start, y_pos)
                
                current_label += 1
            
            if current_label >= total_labels:
                break
        
        while current_label < total_labels:
            c.showPage()
            current_label = self._draw_next_page(c, records, current_label)
    
    def _draw_next_page(self, c, records, start_index):
        """Draw additional page with price tags"""
        array_positions = []
        for array_num in range(4):
            x_start = self.left_margin + (array_num * (self.label_width + self.gutter_spacing))
            array_positions.append(x_start)
        
        current_label = start_index
        total_labels = len(records)
        
        for array_num, x_start in enumerate(array_positions):
            for row in range(15):
                if current_label >= total_labels:
                    return current_label
                
                y_pos = self.page_height - self.top_margin - (row * self.label_height)
                
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(0.25)
                c.rect(x_start, y_pos - self.label_height, self.label_width, self.label_height)
                
                record = records[current_label]
                self._draw_label_content(c, record, x_start, y_pos)
                
                current_label += 1
        
        return current_label
    
    def _draw_label_content(self, c, record, x, y):
        """Draw content for a single price tag"""
        padding = 2
        content_width = self.label_width - (2 * padding)
        font_size = self.font_size
        
        # Artist/title abbreviation
        artist = record.get('artist', '')
        title = record.get('title', '')
        abbreviation = self._create_abbreviation(artist, title)
        
        # Price
        price = record.get('discogs_median_price', 0)
        if price:
            c.setFont("Helvetica-Bold", font_size + 2)
            price_text = f"${float(price):.2f}"
            c.drawString(x + padding, y - 10, price_text)
        
        # Date
        c.setFont("Helvetica", font_size - 1)
        date_text = datetime.now().strftime("%m/%d/%y")
        date_width = c.stringWidth(date_text, "Helvetica", font_size - 1)
        c.drawString(x + self.label_width - date_width - padding, y - 10, date_text)
        
        # Artist/title
        if abbreviation:
            c.setFont("Helvetica", font_size - 1)
            if c.stringWidth(abbreviation, "Helvetica", font_size - 1) > content_width:
                abbreviation = self._truncate_text(c, abbreviation, content_width, font_size - 1)
            c.drawString(x + padding, y - 20, abbreviation)
        
        # Barcode
        barcode = record.get('barcode', '')
        if barcode:
            try:
                barcode_obj = code128.Code128(barcode, barWidth=0.4*mm, barHeight=4*mm)
                barcode_x = x + padding - (5 * mm)
                barcode_y = y - 42 - (1.5 * mm)
                barcode_obj.drawOn(c, barcode_x, barcode_y)
            except:
                c.setFont("Helvetica", font_size - 2)
                barcode_text = f"#{barcode}"
                barcode_x = x + padding - (5 * mm)
                barcode_y = y - 42 - (1.5 * mm)
                c.drawString(barcode_x, barcode_y, barcode_text)
    
    def _create_abbreviation(self, artist, title):
        """Create abbreviation from artist and title"""
        if not artist and not title:
            return ""
        
        artist_words = artist.split()[:3]
        title_words = title.split()[:2]
        
        abbreviation = ""
        if artist_words:
            abbreviation = " ".join(artist_words)
        if title_words:
            if abbreviation:
                abbreviation += " - "
            abbreviation += " ".join(title_words)
        
        if len(abbreviation) > 25:
            abbreviation = abbreviation[:22] + "..."
        
        return abbreviation
    
    def _generate_genre_sign_pdf(self, genre, font_size):
        """Generate PDF with genre sign"""
        buffer = io.BytesIO()
        page_width, page_height = letter
        c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
        
        text = genre.upper()
        font_name = "Helvetica-Bold"
        
        c.setFont(font_name, font_size)
        text_width = c.stringWidth(text, font_name, font_size)
        text_height = font_size
        
        x_center = page_width / 2
        y_center = page_height / 2
        
        border_padding = 12
        border_width = text_height + (2 * border_padding)
        border_height = text_width + (2 * border_padding)
        border_x = x_center - (border_width / 2)
        border_y = y_center - (border_height / 2)
        
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(2)
        c.rect(border_x, border_y, border_width, border_height)
        
        c.saveState()
        c.translate(x_center, y_center)
        c.rotate(-90)
        c.setFont(font_name, font_size)
        c.drawString(-text_width/2, -text_height/2, text)
        c.restoreState()
        
        c.save()
        buffer.seek(0)
        return buffer
    
    def _truncate_text(self, c, text, max_width, font_size):
        """Truncate text to fit within max width"""
        font_name = "Helvetica"
        if c.stringWidth(text, font_name, font_size) <= max_width:
            return text
        
        low, high = 0, len(text)
        while low < high:
            mid = (low + high) // 2
            test_text = text[:mid] + "..."
            if c.stringWidth(test_text, font_name, font_size) <= max_width:
                low = mid + 1
            else:
                high = mid
        
        return text[:low-1] + "..."