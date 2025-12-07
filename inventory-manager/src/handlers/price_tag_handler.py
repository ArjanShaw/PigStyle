# inventory-manager/src/handlers/price_tag_handler.py

import sqlite3
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
import barcode
from barcode.writer import ImageWriter
import io
import tempfile
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import json
from pathlib import Path

class PriceTagHandler:
    """Price tag handler for configurable labels"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    def _get_config_path(self):
        """Get the unified configuration file path"""
        return Path(__file__).parent.parent / "print_config.json"
    
    def get_records_without_barcodes(self):
        """Get records that don't have barcodes using API - ORDERED BY CREATION TIME (latest first)"""
        # Get all records using API
        records_df = self.db_manager.get_all_records()
        
        if records_df.empty:
            return []
        
        # Filter records without barcodes
        records_without_barcodes = records_df[
            (records_df['barcode'].isna()) | 
            (records_df['barcode'] == '') | 
            (records_df['barcode'] == 'None')
        ]
        
        # Sort by ID (assuming higher IDs are newer)
        records_without_barcodes = records_without_barcodes.sort_values('id', ascending=False)
        
        return records_without_barcodes.to_dict('records')
    
    def clear_recent_barcodes(self):
        """Clear barcodes from recent records created in the last 24 hours"""
        try:
            # Calculate cutoff time (24 hours ago)
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            # Get all records with barcodes using API
            all_records = self.db_manager.get_all_records()
            
            if all_records.empty:
                return 0
            
            # Filter records with barcodes created in the last 24 hours
            recent_records = all_records[
                (all_records['barcode'].notna()) & 
                (all_records['barcode'] != '') & 
                (all_records['barcode'] != 'None') &
                (pd.to_datetime(all_records['created_at']) >= cutoff_time)
            ]
            
            if recent_records.empty:
                return 0
            
            # Clear barcodes for recent records using API
            cleared_count = 0
            for _, record in recent_records.iterrows():
                success = self.db_manager.update_record(record['id'], {'barcode': None})
                if success:
                    cleared_count += 1
            
            return cleared_count
            
        except Exception as e:
            st.error(f"Error clearing recent barcodes: {str(e)}")
            return 0
    
    def assign_barcodes(self, record_ids):
        """Assign sequential barcodes to records using the bulk API endpoint"""
        if not record_ids:
            return {}
        
        print(f"🔴 DEBUG: Calling assign_barcodes with record_ids: {record_ids}")
        
        try:
            # Use the bulk barcode assignment endpoint
            result = self.db_manager._make_request(
                'POST', 
                '/barcodes/assign',
                json={'record_ids': record_ids}
            )
            
            print(f"🔴 DEBUG: API response: {result}")
            
            if result and 'barcode_mapping' in result:
                print(f"🔴 DEBUG: Barcode assignment successful: {result['barcode_mapping']}")
                return result['barcode_mapping']
            else:
                print(f"🔴 DEBUG: Barcode assignment failed: {result}")
                return {}
                
        except Exception as e:
            print(f"🔴 DEBUG: Exception in assign_barcodes: {str(e)}")
            import traceback
            print(f"🔴 DEBUG: Traceback: {traceback.format_exc()}")
            return {}
    
    def generate_barcode(self, barcode_number):
        """Generate barcode image"""
        if not barcode_number:
            return None
            
        # Use Code128
        barcode_class = barcode.get_barcode_class('code128')
        barcode_obj = barcode_class(str(barcode_number), writer=ImageWriter())
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        barcode_obj.write(buffer, options={
            'module_height': 6.0,
            'font_size': 0,
            'quiet_zone': 1.0,
            'write_text': False
        })
        buffer.seek(0)
        
        return buffer
    
    def print_price_tags(self, record_ids):
        """Main printing method"""
        if not record_ids:
            return None, "No records selected"
        
        # Step 1: Assign barcodes
        barcode_mapping = self.assign_barcodes(record_ids)
        if not barcode_mapping:
            return None, "Failed to assign barcodes"
        
        # Step 2: Get record data using API
        all_records = self.db_manager.get_all_records()
        records_to_print = all_records[all_records['id'].isin(record_ids)]
        
        if records_to_print.empty:
            return None, "No records found for the selected IDs"
        
        # Step 3: Generate PDF
        pdf_path = self.generate_pdf(records_to_print, barcode_mapping)
        
        if pdf_path and os.path.exists(pdf_path):
            return pdf_path, f"✅ Printed {len(record_ids)} price tags"
        else:
            return None, "❌ Failed to generate PDF"
    
    def generate_pdf(self, df, barcode_mapping, layout_params=None, page_layout_params=None):
        """Generate PDF with price tags using configurable layout"""
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        output_path = temp_file.name
        temp_file.close()

        c = canvas.Canvas(output_path, pagesize=letter)
        
        # Use provided layout parameters or defaults
        params = layout_params if layout_params else self._get_default_layout_params()
        
        # Use provided page layout parameters or defaults
        page_params = page_layout_params if page_layout_params else self._get_default_page_layout_params()
        
        # Calculate layout from parameters
        label_width = page_params.get('label_width_mm', 45.0) * mm
        label_height = page_params.get('label_height_mm', 16.8) * mm
        left_margin = page_params.get('left_margin_mm', 6.5) * mm
        gutter_spacing = page_params.get('gutter_spacing_mm', 6.5) * mm
        top_margin = page_params.get('top_margin_mm', 14.0) * mm
        rows = 15  # Fixed rows
        columns = 4  # Fixed columns

        labels_per_page = rows * columns
        current_label = 0
        
        # Track errors for reporting
        errors = []
        
        for idx, (_, record) in enumerate(df.iterrows()):
            if current_label % labels_per_page == 0 and current_label > 0:
                c.showPage()
            
            # Calculate position
            row = (current_label % labels_per_page) // columns
            col = (current_label % labels_per_page) % columns
            
            x = left_margin + col * (label_width + gutter_spacing)
            y = letter[1] - top_margin - (row + 1) * label_height
            
            barcode_number = barcode_mapping.get(str(record['id']))
            
            # Draw tag and collect any errors
            error = self.draw_tag(c, x, y, label_width, label_height, record, barcode_number, params)
            if error:
                errors.append(f"Record ID {record['id']}: {error}")

            current_label += 1
        
        c.save()
        
        # If there were errors, raise them
        if errors:
            raise ValueError(f"Text overflow errors detected:\n" + "\n".join(errors))
        
        return output_path
    
    def _get_default_layout_params(self):
        """Get default layout parameters - ONLY BASIC PARAMS FOR PRICE TAGS"""
        return {
            'price_font_size': 10,  # Font size for price
            'price_y_pos': 12.0,  # Y position for price
            'text_font_size': 6,  # Font size for text
            'barcode_y_pos': 2.0,  # Y position for barcode
            'barcode_height': 6.0,  # Height for barcode
            'print_borders': True  # Print borders
        }
    
    def _get_default_page_layout_params(self):
        """Get default page layout parameters"""
        return {
            'label_width_mm': 45.0,
            'label_height_mm': 16.8,
            'left_margin_mm': 6.5,
            'gutter_spacing_mm': 6.5,
            'top_margin_mm': 14.0,
            'font_size': 7
        }
    
    def draw_tag(self, c, x, y, label_width, label_height, record, barcode_number, params):
        """Draw a single price tag with price, genre | artist (truncated to 35 chars), and barcode"""
        # Calculate printable area bounds (with 2mm margins on each side)
        left_bound = x + 2 * mm
        right_bound = x + label_width - 2 * mm
        printable_width = label_width - 4 * mm
        
        # Draw border only if enabled
        if params.get('print_borders', True):
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.5)
            c.rect(x, y, label_width, label_height, stroke=1, fill=0)
        
        # Top of label (starting from top going down)
        top_start = y + label_height - 2 * mm
        
        # PRICE - Top Center
        price = record.get('store_price', 0.0)
        price_text = f"${price:.2f}"
        c.setFont("Helvetica-Bold", params['price_font_size'])
        price_width = c.stringWidth(price_text, "Helvetica-Bold", params['price_font_size'])
        
        # Check if price text fits in printable area
        if price_width > printable_width:
            return f"Price text too wide: '{price_text}' ({price_width:.1f}mm > {printable_width/mm:.1f}mm printable width)"
        
        # Center price within printable area
        price_x = left_bound + (printable_width - price_width) / 2
        price_y = top_start - (params['price_y_pos'] * mm)
        c.drawString(price_x, price_y, price_text)
        
        # GENRE | ARTIST - Below Price (truncated to 35 characters total)
        genre = record.get('genre_name', 'Unknown')
        artist = record.get('artist', 'Unknown')
        
        # Format as "genre | artist"
        genre_artist_text = f"{genre} | {artist}"
        
        # Calculate maximum length (35 characters)
        MAX_LENGTH = 35
        SEPARATOR = ' | '
        
        # Don't truncate genre, truncate artist if needed
        if len(genre_artist_text) > MAX_LENGTH:
            # Calculate how many characters we have for artist
            # MAX_LENGTH - genre length - separator length (3)
            max_artist_length = MAX_LENGTH - len(genre) - len(SEPARATOR)
            
            if max_artist_length > 0:
                # Truncate artist with ellipsis if needed
                if len(artist) > max_artist_length:
                    artist = artist[:max_artist_length-1] + '…'
                genre_artist_text = f"{genre}{SEPARATOR}{artist}"
            else:
                # If genre is already too long, just show genre (this shouldn't happen with normal genre names)
                genre_artist_text = genre[:MAX_LENGTH-1] + '…'
        
        c.setFont("Helvetica", params['text_font_size'])
        genre_artist_width = c.stringWidth(genre_artist_text, "Helvetica", params['text_font_size'])
        
        # Check if genre/artist text fits in printable area
        if genre_artist_width > printable_width:
            return f"Genre/Artist text too wide: '{genre_artist_text}' ({genre_artist_width:.1f}mm > {printable_width/mm:.1f}mm printable width)"
        
        # Center genre/artist within printable area
        genre_artist_x = left_bound + (printable_width - genre_artist_width) / 2
        genre_artist_y = price_y - 4 * mm  # Fixed position below price
        c.drawString(genre_artist_x, genre_artist_y, genre_artist_text)
        
        # BARCODE - Center
        if barcode_number:
            barcode_bytes = self.generate_barcode(barcode_number)
            if barcode_bytes:
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    temp_file.write(barcode_bytes.getvalue())
                    temp_path = temp_file.name
                
                # Calculate barcode position - center it within printable area
                barcode_height = params['barcode_height'] * mm
                barcode_width = 25 * mm  # Fixed barcode width
                
                # Check if barcode fits in printable area
                if barcode_width > printable_width:
                    os.unlink(temp_path)
                    return f"Barcode too wide: {barcode_width:.1f}mm > {printable_width/mm:.1f}mm printable width"
                
                barcode_x = left_bound + (printable_width - barcode_width) / 2
                barcode_y = y + (params['barcode_y_pos'] * mm)
                
                c.drawImage(temp_path, barcode_x, barcode_y, width=barcode_width, height=barcode_height)
                os.unlink(temp_path)
        
        # NOTE: Barcode number display removed as requested
        # No barcode number text is displayed below the barcode
        
        return None  # No error