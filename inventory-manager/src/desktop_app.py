import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add the correct path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# PyQt6 imports
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout, 
                            QWidget, QHBoxLayout, QLabel, QPushButton, QMessageBox,
                            QStatusBar, QTextEdit, QSplitter, QFrame)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QFont

# Import your existing modules
from database_manager import DatabaseManager
from handlers.discogs_handler import DiscogsHandler
from handlers.ebay_handler import EbayHandler
from handlers.api_key_handler import APIKeyHandler
from gallery.generator import GalleryJSONManager
from handlers.github_sync_handler import GitHubSyncHandler

# Import tab classes (you'll need to convert these)
from tabs.inventory_tab import InventoryTab
from tabs.statistics_tab import StatisticsTab
from tabs.ebay_tab import EBayTab
from tabs.expenses_tab import ExpensesTab
from tabs.database_switch_tab import DatabaseSwitchTab

class DebugConsole(QTextEdit):
    """Debug console to replace Streamlit's debug functionality"""
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setMaximumHeight(200)
        self.setFont(QFont("Courier", 9))
        
    def add_log(self, category, message, data=None):
        """Add a log entry"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        log_entry = f"[{timestamp}] {category}: {message}"
        if data:
            log_entry += f"\n    Data: {str(data)}"
        
        self.append(log_entry)
        # Auto-scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PigStyle Inventory Manager")
        self.setGeometry(100, 100, 1400, 900)
        
        # Initialize components
        self.debug_console = DebugConsole()
        self.api_key_handler = None
        self.db_manager = None
        self.discogs_handler = None
        self.ebay_handler = None
        self.gallery_json_manager = None
        self.github_sync_handler = None
        
        # Setup UI
        self.setup_ui()
        
        # Initialize application
        QTimer.singleShot(100, self.initialize_application)
    
    def setup_ui(self):
        """Setup the main user interface"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create splitter for main content and debug console
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Top part: Tabs
        self.tab_widget = QTabWidget()
        
        # Create tab instances (you'll need to convert these from Streamlit)
        self.inventory_tab = InventoryTab(self)
        self.ebay_tab = EBayTab(self)
        self.expenses_tab = ExpensesTab(self)
        self.statistics_tab = StatisticsTab(self)
        self.database_tab = DatabaseSwitchTab(self)
        
        # Add tabs
        self.tab_widget.addTab(self.inventory_tab, "📦 Inventory")
        self.tab_widget.addTab(self.ebay_tab, "🛒 eBay")
        self.tab_widget.addTab(self.expenses_tab, "💰 Expenses")
        self.tab_widget.addTab(self.statistics_tab, "📊 Statistics")
        self.tab_widget.addTab(self.database_tab, "🗃️ Database")
        
        splitter.addWidget(self.tab_widget)
        splitter.addWidget(self.debug_console)
        splitter.setSizes([700, 200])
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def initialize_application(self):
        """Initialize the application components"""
        try:
            # Initialize API Key Handler
            self.debug_console.add_log("INIT", "Initializing API Key Handler...")
            self.api_key_handler = APIKeyHandler(self)
            
            # Get environment variables
            env_vars = self.api_key_handler.get_environment_variables()
            
            IMAGEBB_API_KEY = env_vars["IMAGEBB_API_KEY"]
            DISCOGS_USER_TOKEN = env_vars["DISCOGS_USER_TOKEN"]
            EBAY_CLIENT_ID = env_vars["EBAY_CLIENT_ID"]
            EBAY_CLIENT_SECRET = env_vars["EBAY_CLIENT_SECRET"]
            
            # Initialize Database Manager
            self.debug_console.add_log("INIT", "Initializing Database Manager...")
            self.db_manager = DatabaseManager(gallery_json_manager=self.gallery_json_manager)
            
            # Initialize Gallery JSON Manager
            self.debug_console.add_log("INIT", "Initializing Gallery JSON Manager...")
            self.gallery_json_manager = GalleryJSONManager(self.db_manager)
            self.db_manager.gallery_json_manager = self.gallery_json_manager
            
            # Initialize GitHub Sync Handler
            self.debug_console.add_log("INIT", "Initializing GitHub Sync Handler...")
            self.github_sync_handler = GitHubSyncHandler(
                repo_path="/home/arjan-ubuntu/Documents/PigStyle",
                gallery_json_manager=self.gallery_json_manager
            )
            
            # Initialize Discogs handler
            if DISCOGS_USER_TOKEN:
                try:
                    self.debug_console.add_log("INIT", "Initializing Discogs Handler...")
                    self.discogs_handler = DiscogsHandler(DISCOGS_USER_TOKEN, self)
                except Exception as e:
                    self.debug_console.add_log("ERROR", f"Failed to initialize Discogs: {e}")
            
            # Initialize eBay handler
            if EBAY_CLIENT_ID and EBAY_CLIENT_SECRET:
                try:
                    self.debug_console.add_log("INIT", "Initializing eBay Handler...")
                    self.ebay_handler = EbayHandler(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, self)
                except Exception as e:
                    self.debug_console.add_log("ERROR", f"Failed to initialize eBay: {e}")
            
            # Pass handlers to tabs
            self.inventory_tab.set_handlers(self.discogs_handler, self.ebay_handler, self.gallery_json_manager)
            self.ebay_tab.set_handlers(self.ebay_handler, self.gallery_json_manager)
            
            self.debug_console.add_log("SUCCESS", "Application initialized successfully!")
            self.statusBar().showMessage("Application ready")
            
        except Exception as e:
            error_msg = f"Failed to initialize application: {str(e)}"
            self.debug_console.add_log("ERROR", error_msg)
            QMessageBox.critical(self, "Initialization Error", error_msg)
    
    def get_debug_console(self):
        """Get the debug console instance"""
        return self.debug_console

class APIKeyHandler:
    """Modified APIKeyHandler for desktop app"""
    def __init__(self, main_window):
        self.main_window = main_window
        self.env_vars = {}
        self.env_vars_loaded = False
    
    def get_environment_variables(self):
        """Get environment variables ONLY from .env file"""
        if self.env_vars_loaded:
            return self.env_vars
            
        required_vars = [
            "IMAGEBB_API_KEY",
            "DISCOGS_USER_TOKEN", 
            "EBAY_CLIENT_ID",
            "EBAY_CLIENT_SECRET"
        ]
        
        # Get the project base directory and .env file path
        current_dir = os.getcwd()
        env_file_path = os.path.join(current_dir, '.env')
        
        # Check if .env file exists
        if not os.path.exists(env_file_path):
            error_msg = f"❌ .env file not found at {env_file_path}"
            self.main_window.debug_console.add_log("ERROR", error_msg)
            raise Exception(error_msg)
        
        # Load environment variables from .env file
        try:
            with open(env_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Remove quotes if present
                        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]
                        self.env_vars[key] = value
        except Exception as e:
            error_msg = f"❌ Error reading .env file: {str(e)}"
            self.main_window.debug_console.add_log("ERROR", error_msg)
            raise Exception(error_msg)
        
        # Validate all required variables are present
        missing_vars = []
        for var in required_vars:
            if var not in self.env_vars or not self.env_vars[var]:
                missing_vars.append(var)
        
        if missing_vars:
            error_msg = f"❌ Missing required variables in .env file: {', '.join(missing_vars)}"
            self.main_window.debug_console.add_log("ERROR", error_msg)
            raise Exception(error_msg)
        
        # Log successful loading
        for var in required_vars:
            self.main_window.debug_console.add_log("ENV", f"✅ {var} loaded from .env file")
        
        self.env_vars_loaded = True
        return self.env_vars

def main():
    """Main function to run the desktop application"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("PigStyle Inventory Manager")
    app.setApplicationVersion("1.0")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Start the application event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()