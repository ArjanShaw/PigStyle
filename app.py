import streamlit as st
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import from streamlit_app (not streamlit_app_api)
from streamlit_app import main

if __name__ == "__main__":
    main()