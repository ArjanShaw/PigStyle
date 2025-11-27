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
from datetime import datetime
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
        """Get records that don't have barcodes - FIXED QUERY (uses users table)"""
        try:
            conn = self.db_manager._get_connection()
            query = '''
                SELECT r.*, g.genre_name as genre, u.username as consignor_name, u.full_name
                FROM records r
                LEFT JOIN genres g ON r.genre_id = g.id
                LEFT JOIN users u ON r.consignor_id = u.id
                WHERE r.barcode IS NULL OR r.barcode = ''
                ORDER BY r.artist, r.title
            '''
            df = pd.read_sql(query, conn)
            conn.close()
            return df.to_dict('records')
        except Exception as e:
            st.error(f"Error getting records: {e}")
            return []
    
    def assign_barcodes(self, record_ids):
        """Assign sequential barcodes to records"""
        if not record_ids:
            return {}
        
        conn = None
        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT MAX(CAST(barcode AS INTEGER)) FROM records WHERE barcode != '' AND barcode IS NOT NULL")
            result = cursor.fetchone()
            
            if result and result[0] is not None:
                start_barcode = result[0] + 1
            else:
                start_barcode = 100000
            
            barcode_mapping = {}
            current_barcode = start_barcode
            
            for record_id in record_ids:
                barcode_str = str(current_barcode)
                cursor.execute('UPDATE records SET barcode = ? WHERE id = ?', (barcode_str, record_id))
                barcode_mapping[record_id] = barcode_str
                current_barcode += 1
            
            conn.commit()
            return barcode_mapping
            
        except Exception as e:
            if conn:
                conn.rollback()
            return {}
        finally:
            if conn:
                conn.close()
    
    def generate_barcode(self, barcode_number):
        """Generate barcode image"""
        try:
            if not barcode_number:
                return None
                
            # Use Code128
            barcode_class = barcode.get_barcode_class('code128')
            barcode_obj = barcode_class(str(barcode_number), writer=ImageWriter())
            
            # Save to bytes buffer
            buffer = io.BytesIO()
            barcode_obj.write(buffer, options={
                'module_height': 6.0,  # Reduced height
                'font_size': 0,
                'quiet_zone': 1.0,    # Reduced quiet zone
                'write_text': False
            })
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            st.error(f"Barcode error: {e}")
            return None
    
    def print_price_tags(self, record_ids):
        """Main printing method"""
        if not record_ids:
            return None, "No records selected"
        
        try:
            # Step 1: Assign barcodes
            barcode_mapping = self.assign_barcodes(record_ids)
            if not barcode_mapping:
                return None, "Failed to assign barcodes"
            
            # Step 2: Get record data - FIXED QUERY (uses users table)
            conn = self.db_manager._get_connection()
            placeholders = ','.join(['?'] * len(record_ids))
            query = f'''
                SELECT r.*, g.genre_name as genre, u.username as consignor_name, u.full_name
                FROM records r
                LEFT JOIN genres g ON r.genre_id = g.id
                LEFT JOIN users u ON r.consignor_id = u.id
                WHERE r.id IN ({placeholders})
            '''
            df = pd.read_sql(query, conn, params=record_ids)
            conn.close()
            
            # Step 3: Generate PDF
            pdf_path = self.generate_pdf(df, barcode_mapping)
            
            if pdf_path and os.path.exists(pdf_path):
                return pdf_path, f"✅ Printed {len(record_ids)} price tags"
            else:
                return None, "❌ Failed to generate PDF"
            
        except Exception as e:
            return None, f"❌ Error: {str(e)}"
    
    def generate_pdf(self, df, barcode_mapping, layout_params=None):
        """Generate PDF with price tags using configurable layout"""
        try:
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            output_path = temp_file.name
            temp_file.close()
            
            c = canvas.Canvas(output_path, pagesize=letter)
            
            # Use provided layout parameters or defaults
            params = layout_params if layout_params else self._get_default_layout_params()
            
            # Calculate layout from parameters
            label_width = params['label_width_mm'] * mm
            label_height = params['label_height_mm'] * mm
            left_margin = params['left_margin_mm'] * mm
            gutter_spacing = params['gutter_spacing_mm'] * mm
            top_margin = params['top_margin_mm'] * mm
            rows = params['rows']
            columns = params['columns']
            
            labels_per_page = rows * columns
            current_label = 0
            
            for _, record in df.iterrows():
                if current_label % labels_per_page == 0 and current_label > 0:
                    c.showPage()
                
                # Calculate position
                row = (current_label % labels_per_page) // columns
                col = (current_label % labels_per_page) % columns
                
                x = left_margin + col * (label_width + gutter_spacing)
                y = letter[1] - top_margin - (row + 1) * label_height
                
                self.draw_tag(c, x, y, label_width, label_height, record, barcode_mapping.get(record['id']), params)
                current_label += 1
            
            c.save()
            return output_path
            
        except Exception as e:
            st.error(f"PDF error: {e}")
            return None
    
    def _get_default_layout_params(self):
        """Get default layout parameters"""
        config_file = self._get_config_path()
        if not config_file.exists():
            raise Exception(f"Configuration file not found: {config_file}")
        
        try:
            with open(config_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    raise Exception("Configuration file is empty")
                config = json.loads(content)
            return config
        except (json.JSONDecodeError, Exception) as e:
            raise Exception(f"Error loading layout config: {e}")
    
    def draw_tag(self, c, x, y, label_width, label_height, record, barcode_number, params):
        """Draw a single price tag with configurable layout"""
        try:
            # Draw border only if enabled
            if params.get('print_borders', True):
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(0.5)
                c.rect(x, y, label_width, label_height, stroke=1, fill=0)
            
            # Calculate positions with proper spacing
            left_margin = x + 2 * mm
            right_margin = x + label_width - 2 * mm
            
            # Top of label (starting from top going down)
            top_start = y + label_height - 2 * mm
            
            # PRICE
            price = record.get('store_price', 0)
            price_text = f"${price:.2f}" if price else "$0.00"
            c.setFont("Helvetica-Bold", params['price_font_size'])
            price_y = top_start - (params['price_y_pos'] * mm)
            c.drawString(left_margin, price_y, price_text)
            
            # ARTIST - TITLE
            c.setFont("Helvetica", params['text_font_size'])
            artist = record.get('artist', '')[:15]
            title = record.get('title', '')[:15]
            artist_title = f"{artist} - {title}"
            artist_title_y = top_start - (params['artist_y_pos'] * mm)
            c.drawString(left_margin, artist_title_y, artist_title)
            
            # FILE LOCATION
            file_at = record.get('file_at', '')[:20]
            if file_at:
                file_at_y = top_start - (params['file_y_pos'] * mm)
                c.drawString(left_margin, file_at_y, file_at)
            
            # BARCODE
            if barcode_number:
                barcode_bytes = self.generate_barcode(barcode_number)
                if barcode_bytes:
                    try:
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                            temp_file.write(barcode_bytes.getvalue())
                            temp_path = temp_file.name
                        
                        # Calculate barcode position
                        barcode_height = params['barcode_height'] * mm
                        barcode_width = 25 * mm
                        barcode_x = left_margin
                        barcode_y = y + (params['barcode_y_pos'] * mm)
                        
                        c.drawImage(temp_path, barcode_x, barcode_y, width=barcode_width, height=barcode_height)
                        os.unlink(temp_path)
                    except Exception:
                        pass  # Skip barcode on error
            
            # RIGHT SIDE INFO - date and consignor
            print_date = datetime.now().strftime("%m/%d/%y")
            c.setFont("Helvetica", params['date_font_size'])
            
            # Date at top right
            date_y = top_start - (params['date_y_pos'] * mm)
            c.drawRightString(right_margin, date_y, print_date)
            
            # Consignor below date
            consignor = record.get('consignor_name', '')[:10]
            if consignor:
                consignor_y = date_y - (3.5 * mm)  # Fixed spacing below date
                c.drawRightString(right_margin, consignor_y, consignor)
                
        except Exception as e:
            print(f"Error drawing tag: {e}")  # Debug output
            pass  # Continue if one tag fails