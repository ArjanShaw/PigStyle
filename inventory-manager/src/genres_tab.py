import streamlit as st
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import os
import json
from datetime import datetime

class PrintConfig:
    def __init__(self, config_file="print_config.json"):
        self.config_file = config_file
        self.defaults = {
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

class GenresTab:
    def __init__(self):
        self.config = PrintConfig()
    
    def render(self):
        st.header("🎵 Genres Management")
        
        try:
            col1, col2 = st.columns(2)
            
            with col1:
                self._render_genre_management()
            
            with col2:
                self._render_genre_sign_printing()
                
        except Exception as e:
            st.error(f"Error loading genres: {e}")

    def _render_genre_management(self):
        """Render genre management section"""
        st.subheader("Manage Genres")
        
        # Get all genres
        all_genres = st.session_state.db_manager.get_all_genres()
        
        # Display current genres with delete buttons
        if len(all_genres) > 0:
            st.write("**Current Genres:**")
            for _, genre in all_genres.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(genre['genre_name'])
                with col2:
                    if st.button("Delete", key=f"delete_{genre['id']}"):
                        success = st.session_state.db_manager.delete_genre(genre['id'])
                        if success:
                            st.success(f"Deleted genre: {genre['genre_name']}")
                            st.rerun()
                        else:
                            st.error("Failed to delete genre")
        
        # Add new genre
        st.write("**Add New Genre:**")
        new_genre = st.text_input("Genre name:", key="new_genre")
        if st.button("Add Genre"):
            if new_genre and new_genre.strip():
                success, genre_id = st.session_state.db_manager.add_genre(new_genre.strip())
                if success:
                    st.success(f"Added genre: {new_genre}")
                    st.rerun()
                else:
                    st.error(f"Genre '{new_genre}' already exists")
            else:
                st.error("Please enter a genre name")

    def _render_genre_sign_printing(self):
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