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
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    def get_records_without_barcodes(self):
        records_df = self.db_manager.get_all_records()
        
        if records_df.empty:
            return []
        
        records_without_barcodes = records_df[
            (records_df['barcode'].isna()) | 
            (records_df['barcode'] == '') | 
            (records_df['barcode'] == 'None')
        ]
        
        records_without_barcodes = records_without_barcodes.sort_values('id', ascending=False)
        
        return records_without_barcodes.to_dict('records')
    
    def clear_recent_barcodes(self):
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        all_records = self.db_manager.get_all_records()
        
        if all_records.empty:
            return 0
        
        recent_records = all_records[
            (all_records['barcode'].notna()) & 
            (all_records['barcode'] != '') & 
            (all_records['barcode'] != 'None') &
            (pd.to_datetime(all_records['created_at']) >= cutoff_time)
        ]
        
        if recent_records.empty:
            return 0
        
        cleared_count = 0
        for _, record in recent_records.iterrows():
            success = self.db_manager.update_record(record['id'], {'barcode': None})
            if success:
                cleared_count += 1
        
        return cleared_count
    
    def assign_barcodes(self, record_ids):
        if not record_ids:
            return {}
        
        result = self.db_manager._make_request(
            'POST', 
            '/barcodes/assign',
            json={'record_ids': record_ids}
        )
        
        if result and 'barcode_mapping' in result:
            return result['barcode_mapping']
        else:
            return {}
    
    def generate_barcode(self, barcode_number):
        if not barcode_number:
            return None
            
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
    
    def print_price_tags(self, record_ids):
        if not record_ids:
            return None, "No records selected"
        
        barcode_mapping = self.assign_barcodes(record_ids)
        if not barcode_mapping:
            return None, "Failed to assign barcodes"
        
        all_records = self.db_manager.get_all_records()
        records_to_print = all_records[all_records['id'].isin(record_ids)]
        
        if records_to_print.empty:
            return None, "No records found for the selected IDs"
        
        pdf_path = self.generate_pdf(records_to_print, barcode_mapping)
        
        if pdf_path and os.path.exists(pdf_path):
            return pdf_path, f"✅ Printed {len(record_ids)} price tags"
        else:
            return None, "❌ Failed to generate PDF"
    
    def generate_pdf(self, df, barcode_mapping, layout_params=None, page_layout_params=None):
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        output_path = temp_file.name
        temp_file.close()

        c = canvas.Canvas(output_path, pagesize=letter)
        
        # Get params from config if not provided
        if not layout_params:
            from config import AppConfig
            config = AppConfig()
            layout_params = {
                'price_font_size': config.get('price_font_size'),
                'price_y_pos': config.get('price_y_pos'),
                'text_font_size': config.get('text_font_size'),
                'barcode_y_pos': config.get('barcode_y_pos'),
                'barcode_height': config.get('barcode_height'),
                'print_borders': config.get('print_borders')
            }
        
        if not page_layout_params:
            from config import AppConfig
            config = AppConfig()
            page_layout_params = {
                'label_width_mm': config.get('label_width_mm'),
                'label_height_mm': config.get('label_height_mm'),
                'left_margin_mm': config.get('left_margin_mm'),
                'gutter_spacing_mm': config.get('gutter_spacing_mm'),
                'top_margin_mm': config.get('top_margin_mm'),
                'font_size': config.get('font_size')
            }
        
        label_width = page_layout_params.get('label_width_mm', 45.0) * mm
        label_height = page_layout_params.get('label_height_mm', 16.8) * mm
        left_margin = page_layout_params.get('left_margin_mm', 6.5) * mm
        gutter_spacing = page_layout_params.get('gutter_spacing_mm', 6.5) * mm
        top_margin = page_layout_params.get('top_margin_mm', 14.0) * mm
        rows = 15
        columns = 4

        labels_per_page = rows * columns
        current_label = 0
        
        errors = []
        
        for idx, (_, record) in enumerate(df.iterrows()):
            if current_label % labels_per_page == 0 and current_label > 0:
                c.showPage()
            
            row = (current_label % labels_per_page) // columns
            col = (current_label % labels_per_page) % columns
            
            x = left_margin + col * (label_width + gutter_spacing)
            y = letter[1] - top_margin - (row + 1) * label_height
            
            barcode_number = barcode_mapping.get(str(record['id']))
            
            error = self.draw_tag(c, x, y, label_width, label_height, record, barcode_number, layout_params)
            if error:
                errors.append(f"Record ID {record['id']}: {error}")

            current_label += 1
        
        c.save()
        
        if errors:
            raise ValueError(f"Text overflow errors detected:\n" + "\n".join(errors))
        
        return output_path
    
    def draw_tag(self, c, x, y, label_width, label_height, record, barcode_number, params):
        left_bound = x + 2 * mm
        right_bound = x + label_width - 2 * mm
        printable_width = label_width - 4 * mm
        
        if params.get('print_borders', True):
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.5)
            c.rect(x, y, label_width, label_height, stroke=1, fill=0)
        
        top_start = y + label_height - 2 * mm
        
        price = record.get('store_price', 0.0)
        price_text = f"${price:.2f}"
        c.setFont("Helvetica-Bold", params['price_font_size'])
        price_width = c.stringWidth(price_text, "Helvetica-Bold", params['price_font_size'])
        
        if price_width > printable_width:
            return f"Price text too wide: '{price_text}' ({price_width:.1f}mm > {printable_width/mm:.1f}mm printable width)"
        
        price_x = left_bound + (printable_width - price_width) / 2
        price_y = top_start - (params['price_y_pos'] * mm)
        c.drawString(price_x, price_y, price_text)
        
        genre = record.get('genre_name', 'Unknown')
        artist = record.get('artist', 'Unknown')
        
        genre_artist_text = f"{genre} | {artist}"
        
        MAX_LENGTH = 35
        SEPARATOR = ' | '
        
        if len(genre_artist_text) > MAX_LENGTH:
            max_artist_length = MAX_LENGTH - len(genre) - len(SEPARATOR)
            
            if max_artist_length > 0:
                if len(artist) > max_artist_length:
                    artist = artist[:max_artist_length-1] + '…'
                genre_artist_text = f"{genre}{SEPARATOR}{artist}"
            else:
                genre_artist_text = genre[:MAX_LENGTH-1] + '…'
        
        c.setFont("Helvetica", params['text_font_size'])
        genre_artist_width = c.stringWidth(genre_artist_text, "Helvetica", params['text_font_size'])
        
        if genre_artist_width > printable_width:
            return f"Genre/Artist text too wide: '{genre_artist_text}' ({genre_artist_width:.1f}mm > {printable_width/mm:.1f}mm printable width)"
        
        genre_artist_x = left_bound + (printable_width - genre_artist_width) / 2
        genre_artist_y = price_y - 4 * mm
        c.drawString(genre_artist_x, genre_artist_y, genre_artist_text)
        
        if barcode_number:
            barcode_bytes = self.generate_barcode(barcode_number)
            if barcode_bytes:
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    temp_file.write(barcode_bytes.getvalue())
                    temp_path = temp_file.name
                
                barcode_height = params['barcode_height'] * mm
                barcode_width = 25 * mm
                
                if barcode_width > printable_width:
                    os.unlink(temp_path)
                    return f"Barcode too wide: {barcode_width:.1f}mm > {printable_width/mm:.1f}mm printable width"
                
                barcode_x = left_bound + (printable_width - barcode_width) / 2
                barcode_y = y + (params['barcode_y_pos'] * mm)
                
                c.drawImage(temp_path, barcode_x, barcode_y, width=barcode_width, height=barcode_height)
                os.unlink(temp_path)
        
        return None