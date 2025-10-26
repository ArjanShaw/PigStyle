import streamlit as st
import barcode
from barcode.writer import ImageWriter
import io
import os

class BarcodeGenerator:
    """Generates scannable barcodes for inventory items"""
    
    def __init__(self):
        self.barcode_dir = "barcodes"
        os.makedirs(self.barcode_dir, exist_ok=True)
    
    def generate_barcode_image(self, barcode_number, barcode_type='code128'):
        """Generate a barcode image for the given number"""
        try:
            # Validate barcode number is numeric
            if not barcode_number.isdigit():
                raise ValueError("Barcode must contain only digits")
            
            # Create barcode
            if barcode_type == 'code128':
                barcode_class = barcode.get_barcode_class('code128')
            elif barcode_type == 'code39':
                barcode_class = barcode.get_barcode_class('code39')
            else:
                barcode_class = barcode.get_barcode_class('code128')
            
            # Generate barcode
            barcode_obj = barcode_class(barcode_number, writer=ImageWriter())
            
            # Save to bytes buffer
            buffer = io.BytesIO()
            barcode_obj.write(buffer)
            buffer.seek(0)
            
            return buffer
            
        except Exception as e:
            st.error(f"Error generating barcode: {e}")
            return None
    
    def save_barcode_image(self, barcode_number, filename=None):
        """Save barcode image to file"""
        try:
            if filename is None:
                filename = f"barcode_{barcode_number}.png"
            
            filepath = os.path.join(self.barcode_dir, filename)
            buffer = self.generate_barcode_image(barcode_number)
            
            if buffer:
                with open(filepath, 'wb') as f:
                    f.write(buffer.getvalue())
                return filepath
            return None
            
        except Exception as e:
            st.error(f"Error saving barcode: {e}")
            return None
    
    def display_barcode(self, barcode_number, width=200):
        """Display barcode in Streamlit"""
        try:
            buffer = self.generate_barcode_image(barcode_number)
            if buffer:
                st.image(buffer, width=width, caption=f"Barcode: {barcode_number}")
                return buffer
            return None
        except Exception as e:
            st.error(f"Error displaying barcode: {e}")
            return None