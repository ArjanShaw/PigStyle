import os
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
from datetime import datetime
import hashlib
import secrets
import re

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here-change-this')

# CORS Configuration
CORS(app, resources={
    r"/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False,
        "max_age": 600
    }
})

# Database configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "records.db")

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Import all endpoints
from app.voting_endpoints import *
from app.core_record_endpoints import *
from app.genre_endpoints import *
from app.user_endpoints import *
from app.configuration_endpoints import *
from app.statistics_endpoints import *
from app.barcode_endpoints import *
from app.record_operations import *
from app.spotify_endpoints import *

# Root endpoints remain in __init__.py
@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'PigStyle Inventory API',
        'endpoints': [
            {'path': '/records', 'method': 'GET', 'description': 'Get all records'},
            {'path': '/records/<id>', 'method': 'GET', 'description': 'Get single record'},
            {'path': '/search', 'method': 'GET', 'description': 'Search records'},
            {'path': '/users', 'method': 'GET', 'description': 'Get all users'},
            {'path': '/config', 'method': 'GET', 'description': 'Get all config'},
            {'path': '/stats', 'method': 'GET', 'description': 'Get database stats'},
            {'path': '/vote/<record_id>/<ip>/<type>', 'method': 'POST', 'description': 'Record a vote'}
        ]
    })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        conn.close()

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)