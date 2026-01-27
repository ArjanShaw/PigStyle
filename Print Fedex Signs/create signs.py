import sys
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import inch

class SignCreator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.signs = []  # List to store multiple signs
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Multi-Sign Creator")
        self.setGeometry(100, 100, 800, 800)
        
        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Left panel for sign list and settings
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Font settings
        font_group = QGroupBox("Font Settings")
        font_layout = QGridLayout()
        
        font_layout.addWidget(QLabel("Font File:"), 0, 0)
        self.font_path_edit = QLineEdit("keep-on-truckin/KEEPT___.TTF")
        self.font_path_edit.setPlaceholderText("Path to .ttf font file")
        font_layout.addWidget(self.font_path_edit, 0, 1)
        
        self.browse_font_btn = QPushButton("Browse...")
        self.browse_font_btn.clicked.connect(self.browse_font)
        font_layout.addWidget(self.browse_font_btn, 0, 2)
        
        font_layout.addWidget(QLabel("Default Font Size (in):"), 1, 0)
        self.font_size_spin = QDoubleSpinBox()
        self.font_size_spin.setRange(0.5, 20.0)
        self.font_size_spin.setValue(6.0)
        self.font_size_spin.setSingleStep(0.5)
        font_layout.addWidget(self.font_size_spin, 1, 1)
        
        font_layout.addWidget(QLabel("Default Margin (in):"), 2, 0)
        self.margin_spin = QDoubleSpinBox()
        self.margin_spin.setRange(0.1, 3.0)
        self.margin_spin.setValue(1.0)
        self.margin_spin.setSingleStep(0.1)
        font_layout.addWidget(self.margin_spin, 2, 1)
        
        font_group.setLayout(font_layout)
        left_layout.addWidget(font_group)
        
        # Current sign settings
        sign_group = QGroupBox("Current Sign Settings")
        sign_layout = QVBoxLayout()
        
        sign_layout.addWidget(QLabel("Main Text:"))
        self.main_text_edit = QTextEdit()
        self.main_text_edit.setMaximumHeight(80)
        self.main_text_edit.setText("Loveland's Coolest Record Store")
        sign_layout.addWidget(self.main_text_edit)
        
        sign_layout.addWidget(QLabel("Subscript Text (optional):"))
        self.subscript_edit = QLineEdit()
        self.subscript_edit.setPlaceholderText("Optional smaller text below main text")
        sign_layout.addWidget(self.subscript_edit)
        
        sign_layout.addWidget(QLabel("Subscript Size (points):"))
        self.subscript_size_spin = QSpinBox()
        self.subscript_size_spin.setRange(10, 72)
        self.subscript_size_spin.setValue(36)
        sign_layout.addWidget(self.subscript_size_spin)
        
        # Color selection
        color_widget = QWidget()
        color_layout = QHBoxLayout(color_widget)
        
        color_layout.addWidget(QLabel("Color:"))
        
        # Color dropdown
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Red", "Green", "Blue", "Black", "Purple", "Orange", "Custom..."])
        color_layout.addWidget(self.color_combo)
        
        # Custom color button
        self.custom_color_btn = QPushButton("Custom")
        self.custom_color_btn.clicked.connect(self.choose_custom_color)
        color_layout.addWidget(self.custom_color_btn)
        
        sign_layout.addWidget(color_widget)
        
        # Color preview
        self.color_preview = QLabel()
        self.color_preview.setMinimumHeight(30)
        self.color_preview.setStyleSheet("background-color: rgb(255, 0, 0); border: 1px solid black;")
        sign_layout.addWidget(self.color_preview)
        
        sign_group.setLayout(sign_layout)
        left_layout.addWidget(sign_group)
        
        # Sign management buttons
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        
        self.add_sign_btn = QPushButton("Add Sign")
        self.add_sign_btn.clicked.connect(self.add_sign)
        self.add_sign_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        button_layout.addWidget(self.add_sign_btn)
        
        self.update_sign_btn = QPushButton("Update Selected")
        self.update_sign_btn.clicked.connect(self.update_selected_sign)
        self.update_sign_btn.setStyleSheet("background-color: #2196F3; color: white;")
        button_layout.addWidget(self.update_sign_btn)
        
        self.remove_sign_btn = QPushButton("Remove Selected")
        self.remove_sign_btn.clicked.connect(self.remove_selected_sign)
        self.remove_sign_btn.setStyleSheet("background-color: #f44336; color: white;")
        button_layout.addWidget(self.remove_sign_btn)
        
        left_layout.addWidget(button_widget)
        
        # Output settings
        output_group = QGroupBox("Output Settings")
        output_layout = QGridLayout()
        
        output_layout.addWidget(QLabel("Output Filename:"), 0, 0)
        self.output_edit = QLineEdit("multi_signs.pdf")
        self.output_edit.setPlaceholderText("Enter output PDF filename")
        output_layout.addWidget(self.output_edit, 0, 1)
        
        self.browse_output_btn = QPushButton("Browse...")
        self.browse_output_btn.clicked.connect(self.browse_output)
        output_layout.addWidget(self.browse_output_btn, 0, 2)
        
        # Page orientation
        output_layout.addWidget(QLabel("Page Size:"), 1, 0)
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["Auto (Fit to text)", "Letter (8.5x11 in)", "A4 (210x297 mm)", "Custom"])
        output_layout.addWidget(self.page_size_combo, 1, 1)
        
        output_group.setLayout(output_layout)
        left_layout.addWidget(output_group)
        
        # Create PDF button
        self.create_btn = QPushButton("Create Multi-Sign PDF")
        self.create_btn.clicked.connect(self.create_pdf)
        self.create_btn.setStyleSheet("""
            background-color: #2196F3; 
            color: white; 
            font-weight: bold; 
            padding: 12px;
            font-size: 14px;
        """)
        left_layout.addWidget(self.create_btn)
        
        # Add stretch to push everything up
        left_layout.addStretch()
        
        # Right panel for sign list
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Sign list header
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.addWidget(QLabel("Signs in PDF (each will be on separate page)"))
        header_layout.addStretch()
        right_layout.addWidget(header_widget)
        
        # Sign list
        self.sign_list = QListWidget()
        self.sign_list.setAlternatingRowColors(True)
        self.sign_list.itemSelectionChanged.connect(self.load_selected_sign)
        right_layout.addWidget(self.sign_list)
        
        # Sign list buttons
        list_buttons_widget = QWidget()
        list_buttons_layout = QHBoxLayout(list_buttons_widget)
        
        self.move_up_btn = QPushButton("Move Up")
        self.move_up_btn.clicked.connect(self.move_sign_up)
        list_buttons_layout.addWidget(self.move_up_btn)
        
        self.move_down_btn = QPushButton("Move Down")
        self.move_down_btn.clicked.connect(self.move_sign_down)
        list_buttons_layout.addWidget(self.move_down_btn)
        
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all_signs)
        self.clear_all_btn.setStyleSheet("background-color: #ff9800; color: white;")
        list_buttons_layout.addWidget(self.clear_all_btn)
        
        right_layout.addWidget(list_buttons_widget)
        
        # Add panels to main layout
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 1)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Current color (default to red)
        self.current_color = QColor(255, 0, 0)
        
        # Add a sample sign
        self.add_sample_sign()
        
    def add_sample_sign(self):
        """Add a sample sign to start with"""
        sign_data = {
            'main_text': "Loveland's Coolest Record Store",
            'subscript': "",
            'color': QColor(255, 0, 0),
            'font_size': 6.0,
            'margin': 1.0,
            'subscript_size': 36
        }
        self.signs.append(sign_data)
        self.update_sign_list()
        
    def browse_font(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Font File", "", "TrueType Fonts (*.ttf);;All Files (*.*)"
        )
        if filename:
            self.font_path_edit.setText(filename)
            
    def browse_output(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save PDF As", "", "PDF Files (*.pdf);;All Files (*.*)"
        )
        if filename:
            if not filename.lower().endswith('.pdf'):
                filename += '.pdf'
            self.output_edit.setText(filename)
            
    def choose_custom_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Choose Text Color")
        if color.isValid():
            self.current_color = color
            self.update_color_preview()
            self.color_combo.setCurrentText("Custom...")
            
    def update_color_preview(self):
        r, g, b, _ = self.current_color.getRgb()
        self.color_preview.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;")
        
    def add_sign(self):
        """Add current settings as a new sign"""
        main_text = self.main_text_edit.toPlainText().strip()
        if not main_text:
            QMessageBox.warning(self, "Warning", "Please enter some text for the sign.")
            return
            
        # Get color based on dropdown selection
        color_name = self.color_combo.currentText()
        if color_name == "Custom...":
            color = self.current_color
        else:
            # Map color names to QColor
            color_map = {
                "Red": QColor(255, 0, 0),
                "Green": QColor(0, 255, 0),
                "Blue": QColor(0, 0, 255),
                "Black": QColor(0, 0, 0),
                "Purple": QColor(128, 0, 128),
                "Orange": QColor(255, 165, 0),
            }
            color = color_map.get(color_name, QColor(255, 0, 0))
            self.current_color = color
            self.update_color_preview()
        
        sign_data = {
            'main_text': main_text,
            'subscript': self.subscript_edit.text().strip(),
            'color': color,
            'font_size': self.font_size_spin.value(),
            'margin': self.margin_spin.value(),
            'subscript_size': self.subscript_size_spin.value()
        }
        
        self.signs.append(sign_data)
        self.update_sign_list()
        self.status_bar.showMessage(f"Added sign: {main_text[:30]}...", 3000)
        
    def update_selected_sign(self):
        """Update the currently selected sign with current settings"""
        selected_items = self.sign_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a sign to update.")
            return
            
        index = self.sign_list.row(selected_items[0])
        main_text = self.main_text_edit.toPlainText().strip()
        if not main_text:
            QMessageBox.warning(self, "Warning", "Please enter some text for the sign.")
            return
        
        # Get color based on dropdown selection
        color_name = self.color_combo.currentText()
        if color_name == "Custom...":
            color = self.current_color
        else:
            color_map = {
                "Red": QColor(255, 0, 0),
                "Green": QColor(0, 255, 0),
                "Blue": QColor(0, 0, 255),
                "Black": QColor(0, 0, 0),
                "Purple": QColor(128, 0, 128),
                "Orange": QColor(255, 165, 0),
            }
            color = color_map.get(color_name, QColor(255, 0, 0))
            self.current_color = color
            self.update_color_preview()
        
        self.signs[index] = {
            'main_text': main_text,
            'subscript': self.subscript_edit.text().strip(),
            'color': color,
            'font_size': self.font_size_spin.value(),
            'margin': self.margin_spin.value(),
            'subscript_size': self.subscript_size_spin.value()
        }
        
        self.update_sign_list()
        self.status_bar.showMessage(f"Updated sign: {main_text[:30]}...", 3000)
        
    def remove_selected_sign(self):
        """Remove the selected sign"""
        selected_items = self.sign_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a sign to remove.")
            return
            
        index = self.sign_list.row(selected_items[0])
        removed_text = self.signs[index]['main_text']
        del self.signs[index]
        self.update_sign_list()
        self.status_bar.showMessage(f"Removed sign: {removed_text[:30]}...", 3000)
        
    def move_sign_up(self):
        """Move selected sign up in the list"""
        selected_items = self.sign_list.selectedItems()
        if not selected_items:
            return
            
        index = self.sign_list.row(selected_items[0])
        if index > 0:
            self.signs[index], self.signs[index-1] = self.signs[index-1], self.signs[index]
            self.update_sign_list()
            self.sign_list.setCurrentRow(index-1)
            
    def move_sign_down(self):
        """Move selected sign down in the list"""
        selected_items = self.sign_list.selectedItems()
        if not selected_items:
            return
            
        index = self.sign_list.row(selected_items[0])
        if index < len(self.signs) - 1:
            self.signs[index], self.signs[index+1] = self.signs[index+1], self.signs[index]
            self.update_sign_list()
            self.sign_list.setCurrentRow(index+1)
            
    def clear_all_signs(self):
        """Clear all signs from the list"""
        if self.signs:
            reply = QMessageBox.question(
                self, "Clear All", 
                f"Are you sure you want to remove all {len(self.signs)} signs?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.signs.clear()
                self.update_sign_list()
                self.status_bar.showMessage("Cleared all signs", 3000)
        
    def update_sign_list(self):
        """Update the list widget with current signs"""
        self.sign_list.clear()
        for i, sign in enumerate(self.signs, 1):
            main_text = sign['main_text']
            subscript = sign['subscript']
            color = sign['color'].name()
            
            # Truncate long text for display
            display_text = f"{i}. {main_text[:40]}"
            if len(main_text) > 40:
                display_text += "..."
                
            if subscript:
                display_text += f"\n   ↳ {subscript[:30]}"
                if len(subscript) > 30:
                    display_text += "..."
            
            item = QListWidgetItem(display_text)
            
            # Set color indicator
            r, g, b, _ = sign['color'].getRgb()
            item.setForeground(QBrush(QColor(r, g, b)))
            
            # Add tooltip with full text
            tooltip = f"Main: {main_text}"
            if subscript:
                tooltip += f"\nSubscript: {subscript}"
            tooltip += f"\nColor: RGB({r}, {g}, {b})"
            tooltip += f"\nFont Size: {sign['font_size']} inches"
            item.setToolTip(tooltip)
            
            self.sign_list.addItem(item)
            
    def load_selected_sign(self):
        """Load selected sign into the editor"""
        selected_items = self.sign_list.selectedItems()
        if not selected_items:
            return
            
        index = self.sign_list.row(selected_items[0])
        sign = self.signs[index]
        
        # Load sign data into editor
        self.main_text_edit.setPlainText(sign['main_text'])
        self.subscript_edit.setText(sign['subscript'])
        self.font_size_spin.setValue(sign['font_size'])
        self.margin_spin.setValue(sign['margin'])
        self.subscript_size_spin.setValue(sign['subscript_size'])
        
        # Set color
        self.current_color = sign['color']
        self.update_color_preview()
        
        # Try to match color in combo box
        r, g, b, _ = sign['color'].getRgb()
        color_name = self.get_color_name(r, g, b)
        self.color_combo.setCurrentText(color_name)
        
    def get_color_name(self, r, g, b):
        """Get approximate color name from RGB values"""
        colors = {
            (255, 0, 0): "Red",
            (0, 255, 0): "Green",
            (0, 0, 255): "Blue",
            (0, 0, 0): "Black",
            (128, 0, 128): "Purple",
            (255, 165, 0): "Orange",
        }
        
        # Find closest color
        closest_name = "Custom..."
        closest_distance = float('inf')
        
        for (cr, cg, cb), name in colors.items():
            distance = abs(r - cr) + abs(g - cg) + abs(b - cb)
            if distance < closest_distance:
                closest_distance = distance
                closest_name = name
                
        # If not close enough to any predefined color, use custom
        if closest_distance > 50:
            return "Custom..."
        return closest_name
        
    def create_pdf(self):
        """Create PDF with all signs, each on a separate page"""
        # Validate inputs
        font_path = self.font_path_edit.text().strip()
        output_file = self.output_edit.text().strip()
        
        if not font_path:
            QMessageBox.critical(self, "Error", "Please specify a font file.")
            return
            
        if not output_file:
            QMessageBox.critical(self, "Error", "Please specify an output filename.")
            return
            
        if not self.signs:
            QMessageBox.critical(self, "Error", "Please add at least one sign to create.")
            return
            
        # Check if font exists
        if not os.path.exists(font_path):
            QMessageBox.critical(self, "Error", f"Font file not found:\n{font_path}")
            return
            
        try:
            # Register font
            pdfmetrics.registerFont(TTFont("CustomFont", font_path))
            
            # Create canvas
            c = canvas.Canvas(output_file)
            
            # Get page size option
            page_size_option = self.page_size_combo.currentText()
            
            # Create each sign on a separate page
            for i, sign in enumerate(self.signs, 1):
                self.status_bar.showMessage(f"Creating sign {i} of {len(self.signs)}...")
                QApplication.processEvents()  # Update UI
                
                # Convert inches to points
                font_size_points = sign['font_size'] * 72
                margin_points = sign['margin'] * 72
                
                # Measure text width
                text_width = pdfmetrics.stringWidth(sign['main_text'], "CustomFont", font_size_points)
                
                # Calculate page size based on option
                if page_size_option == "Auto (Fit to text)":
                    page_width = text_width + 2 * margin_points
                    
                    if sign['subscript']:
                        subscript_size = sign['subscript_size']
                        subscript_width = pdfmetrics.stringWidth(sign['subscript'], "CustomFont", subscript_size)
                        page_width = max(page_width, subscript_width + 2 * margin_points)
                        page_height = font_size_points + 2 * margin_points + subscript_size + 10
                    else:
                        page_height = font_size_points + 2 * margin_points
                        
                elif page_size_option == "Letter (8.5x11 in)":
                    page_width = 8.5 * 72
                    page_height = 11 * 72
                    
                elif page_size_option == "A4 (210x297 mm)":
                    page_width = 210 / 25.4 * 72  # mm to inches to points
                    page_height = 297 / 25.4 * 72
                    
                else:  # Custom - default to Auto
                    page_width = text_width + 2 * margin_points
                    page_height = font_size_points + 2 * margin_points
                    if sign['subscript']:
                        subscript_size = sign['subscript_size']
                        page_height += subscript_size + 10
                
                # Set page size
                c.setPageSize((page_width, page_height))
                
                # Set color
                r = sign['color'].red() / 255.0
                g = sign['color'].green() / 255.0
                b = sign['color'].blue() / 255.0
                c.setFillColorRGB(r, g, b)
                
                # Draw main text (centered)
                c.setFont("CustomFont", font_size_points)
                
                # Calculate y position based on page size
                if page_size_option.startswith("Auto"):
                    x = (page_width - text_width) / 2
                    y = (page_height - font_size_points) / 2
                else:
                    # Center in fixed-size page
                    x = (page_width - text_width) / 2
                    y = page_height / 2  # Center vertically
                
                c.drawString(x, y, sign['main_text'])
                
                # Draw subscript if provided
                if sign['subscript']:
                    c.setFont("CustomFont", sign['subscript_size'])
                    subscript_width = pdfmetrics.stringWidth(sign['subscript'], "CustomFont", sign['subscript_size'])
                    subscript_x = (page_width - subscript_width) / 2
                    subscript_y = y - sign['subscript_size'] - 10
                    c.drawString(subscript_x, subscript_y, sign['subscript'])
                
                # Add page number (small, at bottom)
                c.setFont("Helvetica", 8)
                c.setFillColorRGB(0.5, 0.5, 0.5)  # Gray color
                c.drawRightString(page_width - 10, 10, f"Sign {i} of {len(self.signs)}")
                
                # Start new page (unless it's the last sign)
                if i < len(self.signs):
                    c.showPage()
            
            c.save()
            
            # Show success message
            success_msg = f"PDF successfully created with {len(self.signs)} signs!\n\n"
            success_msg += f"Output: {os.path.abspath(output_file)}\n"
            success_msg += f"Page Size: {page_size_option}"
            
            QMessageBox.information(self, "Success", success_msg)
            self.status_bar.showMessage(f"PDF created with {len(self.signs)} signs", 5000)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create PDF:\n{str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    
    # Set application icon (optional)
    app.setWindowIcon(QIcon.fromTheme("document-edit"))
    
    window = SignCreator()
    window.show()
    sys.exit(app.exec_())