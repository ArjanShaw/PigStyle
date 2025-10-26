import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

class ImportExportTab:
    def __init__(self):
        pass
    
    def render(self):
        st.header("🔄 Import/Export Records")
        
        col1, col2 = st.columns(2)
        
        with col1:
            self._render_export_section()
        
        with col2:
            self._render_import_section()
            
        st.divider()
        
        self._render_genre_printing_section()

    def _render_export_section(self):
        """Render the export functionality"""
        st.subheader("Export Records")
        
        # Column selection for export
        available_columns = [
            "id", "artist", "title", "discogs_median_price", "discogs_lowest_price", 
            "discogs_highest_price", "ebay_median_price", "ebay_lowest_price", 
            "ebay_highest_price", "genre", "image_url", "barcode", "format", 
            "condition", "year", "catalog_number", "file_at", "status"
        ]
        
        selected_columns = st.multiselect(
            "Select columns to export:",
            options=available_columns,
            default=["id", "artist", "title", "genre", "discogs_median_price", "barcode", "file_at"],
            help="Choose which columns to include in the export"
        )
        
        # Status filter for export
        export_status = st.selectbox(
            "Export records with status:",
            options=["inventory", "sold", "all"],
            help="Choose which records to export"
        )
        
        if st.button("📤 Export Custom CSV", use_container_width=True):
            if selected_columns:
                self._export_custom_csv(selected_columns, export_status)
            else:
                st.warning("Please select at least one column to export")

    def _render_import_section(self):
        """Render the import functionality"""
        st.subheader("Import Records")
        
        uploaded_file = st.file_uploader(
            "Upload CSV file with record updates",
            type=['csv'],
            help="Upload a CSV file with updated record data. Must include 'id' column."
        )
        
        if uploaded_file is not None:
            try:
                import_df = pd.read_csv(uploaded_file)
                
                if 'id' not in import_df.columns:
                    st.error("CSV must contain an 'id' column to identify records")
                else:
                    st.write(f"Found {len(import_df)} records in upload file")
                    st.write("Preview of uploaded data:")
                    st.dataframe(import_df.head())
                    
                    if st.button("🔄 Process Import", use_container_width=True):
                        updated_count = self._process_import_data(import_df)
                        if updated_count > 0:
                            st.success(f"✅ Successfully updated {updated_count} records!")
                            st.session_state.records_updated += 1
                            st.rerun()
                        else:
                            st.warning("No records were updated. Check if the data matches existing records.")
                
            except Exception as e:
                st.error(f"Error processing import file: {e}")

    def _render_genre_printing_section(self):
        """Render the genre signs printing functionality"""
        st.subheader("Genre Signs Printing")
        
        # Get unique genres from inventory
        try:
            conn = st.session_state.db_manager._get_connection()
            genres_df = pd.read_sql(
                "SELECT DISTINCT genre FROM records WHERE genre IS NOT NULL AND genre != '' AND status = 'inventory' ORDER BY genre",
                conn
            )
            conn.close()
            
            if len(genres_df) > 0:
                genre_options = genres_df['genre'].tolist()
            else:
                genre_options = ["ROCK", "JAZZ", "HIP-HOP", "ELECTRONIC", "POP", "METAL", "FOLK", "SOUL"]
                st.info("No genres found in inventory. Using default genre options.")
        except Exception as e:
            st.error(f"Error loading genres: {e}")
            genre_options = ["ROCK", "JAZZ", "HIP-HOP", "ELECTRONIC", "POP", "METAL", "FOLK", "SOUL"]
        
        col1, col2 = st.columns(2)
        with col1:
            print_option = st.radio(
                "Print option:",
                ["Single Genre", "All Genres"],
                key="print_option"
            )
            
            if print_option == "Single Genre":
                genre_text = st.selectbox("Select genre:", options=genre_options, key="genre_select")
            else:
                genre_text = "ALL_GENRES"
        
        with col2:
            font_size = st.slider("Font Size", min_value=24, max_value=96, value=48, key="genre_font_size")
        
        if st.button("🖨️ Generate Genre Sign PDF"):
            try:
                if print_option == "All Genres":
                    pdf_buffer = self._generate_all_genre_signs_pdf(genre_options, font_size)
                    filename = f"all_genre_signs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                else:
                    pdf_buffer = self._generate_genre_sign_pdf(genre_text, font_size)
                    filename = f"genre_sign_{genre_text.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                
                st.download_button(
                    label="⬇️ Download Genre Sign PDF",
                    data=pdf_buffer.getvalue(),
                    file_name=filename,
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Error generating genre sign: {e}")

    def _export_custom_csv(self, columns, status):
        """Export records with selected columns"""
        try:
            # Get records based on status
            conn = st.session_state.db_manager._get_connection()
            
            # Build query with selected columns
            columns_str = ', '.join(columns)
            
            if status == "all":
                query = f"SELECT {columns_str} FROM records"
            else:
                query = f"SELECT {columns_str} FROM records WHERE status = '{status}'"
            
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if len(df) > 0:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"custom_export_{status}_{timestamp}.csv"
                
                csv_data = df.to_csv(index=False)
                
                st.download_button(
                    label="⬇️ Download Custom CSV",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    key=f"download_custom_{timestamp}"
                )
                
                st.success(f"✅ Export ready! {len(df)} {status} records with selected columns.")
            else:
                st.warning(f"No {status} records to export.")
                
        except Exception as e:
            st.error(f"Error exporting custom CSV: {e}")

    def _process_import_data(self, import_df):
        """Process imported CSV data and update records"""
        try:
            updated_count = 0
            conn = st.session_state.db_manager._get_connection()
            cursor = conn.cursor()
            
            for _, row in import_df.iterrows():
                record_id = row.get('id')
                if not record_id:
                    continue
                
                # Build update query dynamically based on available columns
                update_fields = []
                update_values = []
                
                for column, value in row.items():
                    if column != 'id' and pd.notna(value):
                        update_fields.append(f"{column} = ?")
                        update_values.append(value)
                
                if update_fields:
                    update_values.append(record_id)  # For WHERE clause
                    query = f"UPDATE records SET {', '.join(update_fields)} WHERE id = ?"
                    cursor.execute(query, update_values)
                    updated_count += 1
            
            conn.commit()
            conn.close()
            return updated_count
            
        except Exception as e:
            st.error(f"Error processing import: {e}")
            return 0

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

    def _generate_all_genre_signs_pdf(self, genres, font_size):
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