import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/inventory-manager/src'))

# Import and run the main app from src
from streamlit_app import main

if __name__ == "__main__":
    main()
