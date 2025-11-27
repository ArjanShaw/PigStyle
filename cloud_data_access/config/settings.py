import os

# Database configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "records.db")

# API configuration
API_TITLE = "PigStyle Cloud Data Access"
API_DESCRIPTION = "Unified API for inventory management and voting system"
API_VERSION = "1.0.0"

# CORS origins (update with your actual domains)
ALLOWED_ORIGINS = [
    "http://localhost:8501",      # Streamlit local
    "https://*.streamlit.app",    # Streamlit Cloud
    "http://localhost:3000",      # Local web development
    "https://yourusername.pythonanywhere.com",  # PythonAnywhere itself
]