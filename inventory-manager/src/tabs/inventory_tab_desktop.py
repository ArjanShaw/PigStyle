from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QComboBox, QTextEdit,
                            QTableWidget, QTableWidgetItem, QHeaderView,
                            QGroupBox, QScrollArea, QSplitter, QFrame)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
import pandas as pd

class InventoryTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.discogs_handler = None
        self.ebay_handler = None
        self.gallery_json_manager = None
        
        # State variables
        self.search_results = []
        self.selected_record = None
        self.current_search = ""
        
        self.setup_ui()
    
    def set_handlers(self, discogs_handler, ebay_handler, gallery_json_manager):
        """Set external handlers"""
        self.discogs_handler = discogs_handler
        self.ebay_handler = ebay_handler
        self.gallery_json_manager = gallery_json_manager
    
    def setup_ui(self):
        """Setup the inventory tab UI"""
        layout = QVBoxLayout(self)
        
        # Search section
        search_group = QGroupBox("Search & Add Records")
        search_layout = QVBoxLayout(search_group)
        
        # Search type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Action:"))
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["Add item", "Edit or Delete item"])
        type_layout.addWidget(self.search_type_combo)
        type_layout.addStretch()
        search_layout.addLayout(type_layout)
        
        # Search input
        search_input_layout = QHBoxLayout()
        search_input_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter barcode, artist, or title...")
        self.search_input.returnPressed.connect(self.perform_search)
        search_input_layout.addWidget(self.search_input)
        
        self.search_button = QPushButton("🔍 Search")
        self.search_button.clicked.connect(self.perform_search)
        search_input_layout.addWidget(self.search_button)
        search_layout.addLayout(search_input_layout)
        
        layout.addWidget(search_group)
        
        # Results section
        self.results_area = QScrollArea()
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_area.setWidget(self.results_widget)
        self.results_area.setWidgetResizable(True)
        layout.addWidget(self.results_area)
        
        # Initially hide results
        self.results_area.hide()
    
    def perform_search(self):
        """Perform search based on current type"""
        search_term = self.search_input.text().strip()
        if not search_term:
            return
        
        self.current_search = search_term
        search_type = self.search_type_combo.currentText()
        
        # Show loading state
        self.clear_results()
        loading_label = QLabel("Searching...")
        self.results_layout.addWidget(loading_label)
        self.results_area.show()
        
        # Use QTimer to perform search in the next event loop iteration
        QTimer.singleShot(100, lambda: self._execute_search(search_term, search_type))
    
    def _execute_search(self, search_term, search_type):
        """Execute the search (called via QTimer)"""
        try:
            self.clear_results()
            
            if search_type == "Add item":
                # Use Discogs search
                if self.discogs_handler:
                    results = self.perform_discogs_search(search_term)
                else:
                    self.show_error("Discogs handler not available")
                    return
            else:
                # Use database search
                results = self.perform_database_search(search_term)
            
            self.display_results(results, search_type)
            
        except Exception as e:
            self.show_error(f"Search error: {str(e)}")
    
    def perform_discogs_search(self, search_term):
        """Perform Discogs search"""
        # This would use your existing Discogs handler logic
        # Simplified for example
        return []
    
    def perform_database_search(self, search_term):
        """Perform database search"""
        # This would use your existing database search logic
        # Simplified for example
        return []
    
    def display_results(self, results, search_type):
        """Display search results"""
        self.clear_results()
        
        if not results:
            no_results_label = QLabel("No results found")
            self.results_layout.addWidget(no_results_label)
            return
        
        for i, record in enumerate(results):
            self.add_result_item(record, i, search_type)
        
        self.results_area.show()
    
    def add_result_item(self, record, index, search_type):
        """Add a single result item to the results layout"""
        # Create result item widget
        item_widget = QFrame()
        item_widget.setFrameStyle(QFrame.Shape.Box)
        item_layout = QHBoxLayout(item_widget)
        
        # Image
        # You would add image loading here
        
        # Text info
        text_layout = QVBoxLayout()
        artist = record.get('artist', 'Unknown Artist')
        title = record.get('title', 'Unknown Title')
        
        artist_label = QLabel(f"<b>{artist}</b>")
        title_label = QLabel(title)
        
        text_layout.addWidget(artist_label)
        text_layout.addWidget(title_label)
        
        # Add additional fields based on search type
        if search_type == "Edit or Delete item":
            # Add database record details
            pass
        
        item_layout.addLayout(text_layout)
        item_layout.addStretch()
        
        # Select button
        select_button = QPushButton("Select")
        select_button.clicked.connect(lambda: self.select_record(record, search_type))
        item_layout.addWidget(select_button)
        
        # Delete button for database items
        if search_type == "Edit or Delete item":
            delete_button = QPushButton("🗑️ Delete")
            delete_button.clicked.connect(lambda: self.delete_record(record))
            item_layout.addWidget(delete_button)
        
        self.results_layout.addWidget(item_widget)
    
    def select_record(self, record, search_type):
        """Handle record selection"""
        self.selected_record = record
        self.show_record_details(record, search_type)
    
    def show_record_details(self, record, search_type):
        """Show detailed view of selected record"""
        self.clear_results()
        
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        # Back button
        back_button = QPushButton("← Back to Results")
        back_button.clicked.connect(self.show_results)
        details_layout.addWidget(back_button)
        
        # Record details
        # Add detailed record view here
        
        self.results_layout.addWidget(details_widget)
    
    def show_results(self):
        """Show results again after viewing details"""
        self.selected_record = None
        # Re-display results
        search_type = self.search_type_combo.currentText()
        self.display_results(self.search_results, search_type)
    
    def delete_record(self, record):
        """Delete a record"""
        # Implement delete functionality
        pass
    
    def clear_results(self):
        """Clear the results area"""
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def show_error(self, message):
        """Show error message"""
        self.clear_results()
        error_label = QLabel(f"Error: {message}")
        error_label.setStyleSheet("color: red;")
        self.results_layout.addWidget(error_label)
        self.results_area.show()