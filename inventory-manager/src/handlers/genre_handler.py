import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io

class GenreHandler:
    def get_unique_genres(self):
        """Get unique genres from inventory"""
        try:
            conn = st.session_state.db_manager._get_connection()
            genres_df = pd.read_sql(
                "SELECT DISTINCT genre FROM records_with_genres WHERE genre IS NOT NULL AND genre != '' ORDER BY genre",
                conn
            )
            conn.close()
            
            if len(genres_df) > 0:
                return genres_df['genre'].tolist()
            else:
                return ["ROCK", "JAZZ", "HIP-HOP", "ELECTRONIC", "POP", "METAL", "FOLK", "SOUL"]
        except Exception as e:
            return ["ROCK", "JAZZ", "HIP-HOP", "ELECTRONIC", "POP", "METAL", "FOLK", "SOUL"]
    
    def generate_genre_sign_pdf(self, genre, font_size):
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

    def generate_all_genre_signs_pdf(self, genres, font_size):
        """Generate PDF with all genre signs, one per page"""
        buffer = io.BytesIO()
        page_width, page_height = letter
        c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
        font_name = "Helvetica-Bold"
        
        for i, genre in enumerate(genres):
            if i > 0:  # Start new page for each genre after the first one
                c.showPage()
            
            text = genre.upper()
            
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