import streamlit as st
import os
import sys

# Add the inventory-manager/src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'inventory-manager/src'))

from streamlit_app import main

if __name__ == "__main__":
    main()