import os
import requests
import base64
from flask import Flask, jsonify, request, session, redirect
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import hashlib
import secrets
import re
import logging
from logging.handlers import RotatingFileHandler
import random
import time
import urllib.parse
import json
import threading
import uuid

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here-change-this')

# CORS Configuration
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://pigstylemusic.com",
            "https://arjanshaw.github.io",
            "https://pigstylerecords.github.io",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "https://www.pigstylemusic.com",
            "http://arjanshaw.pythonanywhere.com"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
        "expose_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False,
        "max_age": 600
    }
})

# Database configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "records.db")

# Spotify configuration
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', 'your-client-id-here')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', 'your-client-secret-here')
SPOTIFY_REDIRECT_URI = 'https://www.pigstylemusic.com/spotify/callback'

# Token storage and background job storage
user_tokens = {}
background_jobs = {}  # Store job status and results

def setup_logging():
    """Setup application logging"""
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    logging.basicConfig(level=logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'api.log'),
        maxBytes=1024 * 1024,
        backupCount=10
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))

    app.logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    app.logger.addHandler(console_handler)

setup_logging()

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== AUTHENTICATION ENDPOINTS ====================

@app.route('/users', methods=['GET'])
def get_users():
    """Get all users from database for authentication"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, email, role, full_name, phone, address, created_at, last_login
            FROM users
            ORDER BY username
        ''')

        users = cursor.fetchall()
        conn.close()

        # Convert to list of dictionaries
        users_list = []
        for user in users:
            users_list.append({
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'full_name': user['full_name'],
                'phone': user['phone'],
                'address': user['address'],
                'created_at': user['created_at'],
                'last_login': user['last_login']
            })

        return jsonify({
            'status': 'success',
            'count': len(users_list),
            'users': users_list
        })

    except Exception as e:
        app.logger.error(f"Error in /users endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/debug/verify-login/<int:user_id>', methods=['POST'])
def verify_login(user_id):
    """Debug endpoint to verify user login credentials"""
    try:
        # Get password from request
        data = request.get_json()
        if not data or 'password' not in data:
            return jsonify({
                'status': 'error',
                'error': 'Password required'
            }), 400

        password = data['password']

        conn = get_db()
        cursor = conn.cursor()

        # Get user's stored password hash
        cursor.execute('''
            SELECT password_hash FROM users WHERE id = ?
        ''', (user_id,))

        user = cursor.fetchone()
        conn.close()

        if not user:
            return jsonify({
                'status': 'error',
                'error': 'User not found',
                'login_valid': False
            }), 404

        stored_hash = user['password_hash']

        # Simple password verification (you should use proper hashing in production)
        # This is a debug endpoint for testing
        app.logger.debug(f"Debug login attempt for user_id: {user_id}")

        # For now, accept any password for debug purposes
        # In production, you would verify against stored hash
        login_valid = True

        return jsonify({
            'status': 'success',
            'user_id': user_id,
            'login_valid': login_valid,
            'note': 'Debug endpoint - always returns True for testing'
        })

    except Exception as e:
        app.logger.error(f"Error in /debug/verify-login endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'login_valid': False
        }), 500

@app.route('/users/<int:user_id>/reset-password', methods=['POST'])
def reset_password(user_id):
    """Reset user password (admin only)"""
    try:
        data = request.get_json()
        if not data or 'new_password' not in data:
            return jsonify({'status': 'error', 'error': 'new_password required'}), 400

        new_password = data['new_password']

        conn = get_db()
        cursor = conn.cursor()

        # Hash the new password
        salt = secrets.token_hex(16)
        password_hash = f"{salt}${hashlib.sha256((salt + new_password).encode()).hexdigest()}"

        cursor.execute('''
            UPDATE users SET password_hash = ? WHERE id = ?
        ''', (password_hash, user_id))

        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Password reset successfully'})

    except Exception as e:
        app.logger.error(f"Error resetting password: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/users/<int:user_id>/change-password', methods=['POST'])
def change_password(user_id):
    """Change user password (requires current password)"""
    try:
        data = request.get_json()
        if not data or 'current_password' not in data or 'new_password' not in data:
            return jsonify({'status': 'error', 'error': 'current_password and new_password required'}), 400

        current_password = data['current_password']
        new_password = data['new_password']

        conn = get_db()
        cursor = conn.cursor()

        # Get current password hash
        cursor.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'status': 'error', 'error': 'User not found'}), 404

        # Verify current password
        stored_hash = user['password_hash']
        if '$' in stored_hash:
            salt, hash_value = stored_hash.split('$')
            current_hash = hashlib.sha256((salt + current_password).encode()).hexdigest()
            if current_hash != hash_value:
                return jsonify({'status': 'error', 'error': 'Current password incorrect'}), 400

        # Hash new password
        salt = secrets.token_hex(16)
        new_password_hash = f"{salt}${hashlib.sha256((salt + new_password).encode()).hexdigest()}"

        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_password_hash, user_id))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Password changed successfully'})

    except Exception as e:
        app.logger.error(f"Error changing password: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        conn.close()

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'service': 'PigStyle API',
            'endpoints': [
                '/users',
                '/debug/verify-login/<user_id>',
                '/health',
                '/genres',
                '/records',
                '/records/count',
                '/spotify/authorize-and-update',
                '/spotify/callback',
                '/spotify/job-status/<job_id>',
                '/spotify/stored-playlists'
            ]
        })

    except Exception as e:
        app.logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'database': 'disconnected'
        }), 500

# ==================== NEW ENDPOINTS FOR STREAMLIT APP ====================

@app.route('/barcodes/assign', methods=['POST'])
def assign_barcodes():
    """Assign sequential barcodes to records"""
    try:
        data = request.get_json()
        if not data or 'record_ids' not in data:
            return jsonify({'status': 'error', 'error': 'record_ids required'}), 400

        record_ids = data['record_ids']
        if not isinstance(record_ids, list):
            return jsonify({'status': 'error', 'error': 'record_ids must be a list'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Get the highest current barcode
        cursor.execute('SELECT MAX(CAST(barcode AS INTEGER)) as max_barcode FROM records WHERE barcode GLOB "[0-9]*"')
        result = cursor.fetchone()
        start_num = int(result['max_barcode']) + 1 if result['max_barcode'] else 1000

        barcode_mapping = {}
        for i, record_id in enumerate(record_ids):
            barcode = str(start_num + i)
            cursor.execute('UPDATE records SET barcode = ? WHERE id = ?', (barcode, record_id))
            barcode_mapping[str(record_id)] = barcode

        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'barcode_mapping': barcode_mapping})

    except Exception as e:
        app.logger.error(f"Error assigning barcodes: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/records', methods=['POST'])
def create_record():
    """Create a new record"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'error': 'No data provided'}), 400

        required_fields = ['artist', 'title']
        for field in required_fields:
            if field not in data:
                return jsonify({'status': 'error', 'error': f'{field} required'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Insert record
        cursor.execute('''
            INSERT INTO records (
                artist, title, barcode, genre_id, image_url, discogs_suggested_price,
                catalog_number, format, condition, store_price, ebay_sell_at,
                youtube_url, consignor_id, commission_rate, store_return_days, compilation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('artist'),
            data.get('title'),
            data.get('barcode', ''),
            data.get('genre_id'),
            data.get('image_url', ''),
            data.get('discogs_suggested_price'),
            data.get('catalog_number', ''),
            data.get('format', 'Vinyl'),
            data.get('condition', '4'),
            data.get('store_price'),
            data.get('ebay_sell_at', 0.0),
            data.get('youtube_url', ''),
            data.get('consignor_id'),
            data.get('commission_rate'),
            data.get('store_return_days'),
            data.get('compilation', False)
        ))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'record_id': record_id})

    except Exception as e:
        app.logger.error(f"Error creating record: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/records/<int:record_id>', methods=['GET'])
def get_record(record_id):
    """Get a single record by ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, COALESCE(g.genre_name, 'Unknown') as genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.id = ?
        ''', (record_id,))

        record = cursor.fetchone()
        conn.close()

        if not record:
            return jsonify({'status': 'error', 'error': 'Record not found'}), 404

        # Convert to dict
        record_dict = dict(record)
        return jsonify(record_dict)

    except Exception as e:
        app.logger.error(f"Error getting record: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/records/<int:record_id>', methods=['PUT'])
def update_record(record_id):
    """Update a record"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'error': 'No data provided'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Check if record exists
        cursor.execute('SELECT id FROM records WHERE id = ?', (record_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'status': 'error', 'error': 'Record not found'}), 404

        # Build update query dynamically
        update_fields = []
        update_values = []

        field_mapping = {
            'artist': 'artist',
            'title': 'title',
            'barcode': 'barcode',
            'genre_id': 'genre_id',
            'image_url': 'image_url',
            'discogs_suggested_price': 'discogs_suggested_price',
            'catalog_number': 'catalog_number',
            'format': 'format',
            'condition': 'condition',
            'store_price': 'store_price',
            'ebay_sell_at': 'ebay_sell_at',
            'youtube_url': 'youtube_url',
            'consignor_id': 'consignor_id',
            'commission_rate': 'commission_rate',
            'store_return_days': 'store_return_days',
            'compilation': 'compilation'
        }

        for key, value in data.items():
            if key in field_mapping:
                update_fields.append(f"{field_mapping[key]} = ?")
                update_values.append(value)

        if not update_fields:
            conn.close()
            return jsonify({'status': 'error', 'error': 'No valid fields to update'}), 400

        update_values.append(record_id)
        update_query = f"UPDATE records SET {', '.join(update_fields)} WHERE id = ?"

        cursor.execute(update_query, update_values)
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Record updated'})

    except Exception as e:
        app.logger.error(f"Error updating record: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    """Delete a record"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM records WHERE id = ?', (record_id,))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Record deleted'})

    except Exception as e:
        app.logger.error(f"Error deleting record: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/search', methods=['GET'])
def search_records():
    """Search records"""
    try:
        search_term = request.args.get('q', '')
        if not search_term:
            return jsonify({'status': 'error', 'error': 'Search term required'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Search in multiple fields
        cursor.execute('''
            SELECT r.*, COALESCE(g.genre_name, 'Unknown') as genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.artist LIKE ? OR r.title LIKE ? OR r.barcode LIKE ? OR r.catalog_number LIKE ?
            ORDER BY r.artist, r.title
            LIMIT 50
        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

        records = cursor.fetchall()
        conn.close()

        records_list = [dict(record) for record in records]
        return jsonify({'status': 'success', 'records': records_list})

    except Exception as e:
        app.logger.error(f"Error searching records: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/records/barcode/<barcode>', methods=['GET'])
def get_record_by_barcode(barcode):
    """Get record by barcode"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, COALESCE(g.genre_name, 'Unknown') as genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.barcode = ?
        ''', (barcode,))

        record = cursor.fetchone()
        conn.close()

        if not record:
            return jsonify({'status': 'error', 'error': 'Record not found'}), 404

        return jsonify(dict(record))

    except Exception as e:
        app.logger.error(f"Error getting record by barcode: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/config/<config_key>', methods=['GET'])
def get_config(config_key):
    """Get configuration value"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT config_value FROM app_config WHERE config_key = ?', (config_key,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return jsonify({'status': 'success', 'config_value': result['config_value']})
        else:
            return jsonify({'status': 'success', 'config_value': None})

    except Exception as e:
        app.logger.error(f"Error getting config: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/config', methods=['POST'])
def set_config():
    """Set configuration value"""
    try:
        data = request.get_json()
        if not data or 'config_key' not in data or 'config_value' not in data:
            return jsonify({'status': 'error', 'error': 'config_key and config_value required'}), 400

        config_key = data['config_key']
        config_value = data['config_value']

        conn = get_db()
        cursor = conn.cursor()

        # Check if config exists
        cursor.execute('SELECT config_key FROM app_config WHERE config_key = ?', (config_key,))
        if cursor.fetchone():
            cursor.execute('UPDATE app_config SET config_value = ? WHERE config_key = ?', (config_value, config_key))
        else:
            cursor.execute('INSERT INTO app_config (config_key, config_value) VALUES (?, ?)', (config_key, config_value))

        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Config updated'})

    except Exception as e:
        app.logger.error(f"Error setting config: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/config', methods=['GET'])
def get_all_config():
    """Get all configuration values"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT config_key, config_value FROM app_config ORDER BY config_key')
        configs = cursor.fetchall()
        conn.close()

        config_dict = {row['config_key']: row['config_value'] for row in configs}
        return jsonify({'status': 'success', 'configs': config_dict})

    except Exception as e:
        app.logger.error(f"Error getting all config: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/genres', methods=['POST'])
def create_genre():
    """Create a new genre"""
    try:
        data = request.get_json()
        if not data or 'genre_name' not in data:
            return jsonify({'status': 'error', 'error': 'genre_name required'}), 400

        genre_name = data['genre_name']

        conn = get_db()
        cursor = conn.cursor()

        # Check if genre already exists
        cursor.execute('SELECT id FROM genres WHERE genre_name = ?', (genre_name,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'status': 'error', 'error': 'Genre already exists'}), 400

        cursor.execute('INSERT INTO genres (genre_name) VALUES (?)', (genre_name,))
        genre_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'genre_id': genre_id})

    except Exception as e:
        app.logger.error(f"Error creating genre: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/genre-assignments', methods=['POST'])
def create_genre_assignment():
    """Assign genre to artist"""
    try:
        data = request.get_json()
        if not data or 'artist_name' not in data or 'genre_id' not in data:
            return jsonify({'status': 'error', 'error': 'artist_name and genre_id required'}), 400

        artist_name = data['artist_name']
        genre_id = data['genre_id']

        conn = get_db()
        cursor = conn.cursor()

        # Check if assignment already exists
        cursor.execute('SELECT id FROM genre_assignments WHERE artist_name = ?', (artist_name,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute('UPDATE genre_assignments SET genre_id = ? WHERE artist_name = ?', (genre_id, artist_name))
        else:
            cursor.execute('INSERT INTO genre_assignments (artist_name, genre_id) VALUES (?, ?)', (artist_name, genre_id))

        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Genre assigned to artist'})

    except Exception as e:
        app.logger.error(f"Error assigning genre: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/genre-assignments/artist/<artist_name>', methods=['DELETE'])
def delete_genre_assignment(artist_name):
    """Remove genre assignment from artist"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM genre_assignments WHERE artist_name = ?', (artist_name,))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Genre assignment removed'})

    except Exception as e:
        app.logger.error(f"Error removing genre assignment: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/genre-assignments/artist/<artist_name>', methods=['GET'])
def get_artist_genre(artist_name):
    """Get genre assigned to an artist"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ga.artist_name, g.id as genre_id, g.genre_name
            FROM genre_assignments ga
            JOIN genres g ON ga.genre_id = g.id
            WHERE ga.artist_name = ?
        ''', (artist_name,))

        assignment = cursor.fetchone()
        conn.close()

        if assignment:
            return jsonify(dict(assignment))
        else:
            return jsonify({'status': 'success', 'artist_name': artist_name, 'genre_id': None, 'genre_name': None})

    except Exception as e:
        app.logger.error(f"Error getting artist genre: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/artists/with-genres', methods=['GET'])
def get_artists_with_genres():
    """Get all artists from records and their assigned genres"""
    try:
        search_term = request.args.get('search', '')

        conn = get_db()
        cursor = conn.cursor()

        if search_term:
            cursor.execute('''
                SELECT DISTINCT r.artist as artist_name, COALESCE(g.genre_name, 'Unknown') as genre_name
                FROM records r
                LEFT JOIN genres g ON r.genre_id = g.id
                WHERE r.artist LIKE ?
                ORDER BY r.artist
            ''', (f'%{search_term}%',))
        else:
            cursor.execute('''
                SELECT DISTINCT r.artist as artist_name, COALESCE(g.genre_name, 'Unknown') as genre_name
                FROM records r
                LEFT JOIN genres g ON r.genre_id = g.id
                ORDER BY r.artist
            ''')

        artists = cursor.fetchall()
        conn.close()

        artists_list = [dict(artist) for artist in artists]
        return jsonify({'status': 'success', 'artists': artists_list})

    except Exception as e:
        app.logger.error(f"Error getting artists with genres: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/records/by-ids', methods=['POST'])
def get_records_by_ids():
    """Get records by multiple IDs (for price tag printing)"""
    try:
        data = request.get_json()
        if not data or 'record_ids' not in data:
            return jsonify({'status': 'error', 'error': 'record_ids required'}), 400

        record_ids = data['record_ids']
        if not isinstance(record_ids, list):
            return jsonify({'status': 'error', 'error': 'record_ids must be a list'}), 400

        # Convert to comma-separated string for SQL IN clause
        placeholders = ','.join('?' for _ in record_ids)

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(f'''
            SELECT r.*, COALESCE(g.genre_name, 'Unknown') as genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.id IN ({placeholders})
            ORDER BY r.artist, r.title
        ''', record_ids)

        records = cursor.fetchall()
        conn.close()

        records_list = [dict(record) for record in records]
        return jsonify({'status': 'success', 'records': records_list})

    except Exception as e:
        app.logger.error(f"Error getting records by IDs: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user by ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, email, role, full_name, phone, address, created_at, last_login
            FROM users WHERE id = ?
        ''', (user_id,))

        user = cursor.fetchone()
        conn.close()

        if not user:
            return jsonify({'status': 'error', 'error': 'User not found'}), 404

        return jsonify(dict(user))

    except Exception as e:
        app.logger.error(f"Error getting user: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get counts
        cursor.execute('SELECT COUNT(*) as records_count FROM records')
        records_count = cursor.fetchone()['records_count']

        cursor.execute('SELECT COUNT(*) as users_count FROM users')
        users_count = cursor.fetchone()['users_count']

        cursor.execute('SELECT MAX(created_at) as latest_record FROM records')
        latest_record = cursor.fetchone()['latest_record']

        conn.close()

        return jsonify({
            'status': 'success',
            'records_count': records_count,
            'users_count': users_count,
            'latest_record': latest_record,
            'db_path': 'API-based'
        })

    except Exception as e:
        app.logger.error(f"Error getting stats: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/stats/user/<int:user_id>', methods=['GET'])
def get_user_stats(user_id):
    """Get user-specific database statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'status': 'error', 'error': 'User not found'}), 404

        # Get user's record count
        cursor.execute('SELECT COUNT(*) as records_count FROM records WHERE consignor_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()

        return jsonify({
            'status': 'success',
            'records_count': result['records_count'],
            'db_path': 'API-based'
        })

    except Exception as e:
        app.logger.error(f"Error getting user stats: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/records/user/<int:user_id>', methods=['GET'])
def get_user_records(user_id):
    """Get records for a specific user (consignor)"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, COALESCE(g.genre_name, 'Unknown') as genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.consignor_id = ?
            ORDER BY r.artist, r.title
        ''', (user_id,))

        records = cursor.fetchall()
        conn.close()

        records_list = [dict(record) for record in records]
        return jsonify({'status': 'success', 'records': records_list})

    except Exception as e:
        app.logger.error(f"Error getting user records: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/records/no-barcodes', methods=['GET'])
def get_records_without_barcodes():
    """Get records without barcodes"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, COALESCE(g.genre_name, 'Unknown') as genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.barcode IS NULL OR r.barcode = '' OR r.barcode = 'None'
            ORDER BY r.artist, r.title
        ''')

        records = cursor.fetchall()
        conn.close()

        records_list = [dict(record) for record in records]
        return jsonify({'status': 'success', 'records': records_list})

    except Exception as e:
        app.logger.error(f"Error getting records without barcodes: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/records/update-file-locations', methods=['POST'])
def update_file_locations():
    """Update file_at column for all records"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get all records with their genres
        cursor.execute('''
            SELECT r.id, r.artist, r.compilation, g.genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
        ''')
        records = cursor.fetchall()

        updated_count = 0
        for record in records:
            record_id = record['id']
            artist = record['artist']
            compilation = record['compilation']
            genre_name = record['genre_name'] or 'Unknown'

            if not artist or not genre_name:
                continue

            # Calculate file_at
            if compilation:
                # For compilations: Comp(first_letter_of_genre)
                genre_first_char = genre_name[0].upper() if genre_name and genre_name[0].isalpha() else "?"
                file_at = f"Comp({genre_first_char})"
            else:
                # For regular records: genre(first_letter_of_artist)
                artist_clean = artist.strip().lower()

                if artist_clean.startswith('the '):
                    artist_clean = artist_clean[4:]

                if artist_clean and artist_clean[0].isdigit():
                    number_words = {
                        '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
                        '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
                    }
                    first_char = artist_clean[0]
                    file_at_letter = number_words.get(first_char, '?')[0].upper()
                elif artist_clean and artist_clean[0].isalpha():
                    file_at_letter = artist_clean[0].upper()
                else:
                    file_at_letter = "?"

                file_at = f"{genre_name}({file_at_letter})"

            cursor.execute('UPDATE records SET file_at = ? WHERE id = ?', (file_at, record_id))
            updated_count += 1

        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'updated_count': updated_count})

    except Exception as e:
        app.logger.error(f"Error updating file locations: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/database/clear', methods=['POST'])
def clear_database():
    """Clear all data from database"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM records')
        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Database cleared'})

    except Exception as e:
        app.logger.error(f"Error clearing database: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

# ==================== SPOTIFY FUNCTIONS ====================

def store_spotify_playlist(playlist_id, playlist_name, genre_name, spotify_url, embed_url, tracks_count):
    """Store or update Spotify playlist in database"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check if playlist already exists
        cursor.execute('''
            SELECT id FROM spotify_playlists WHERE playlist_id = ?
        ''', (playlist_id,))

        existing = cursor.fetchone()

        if existing:
            # Update existing playlist
            cursor.execute('''
                UPDATE spotify_playlists
                SET playlist_name = ?, genre_name = ?, spotify_url = ?, embed_url = ?,
                    tracks_count = ?, updated_at = CURRENT_TIMESTAMP, is_active = 1
                WHERE playlist_id = ?
            ''', (playlist_name, genre_name, spotify_url, embed_url, tracks_count, playlist_id))
        else:
            # Insert new playlist
            cursor.execute('''
                INSERT INTO spotify_playlists
                (playlist_id, playlist_name, genre_name, spotify_url, embed_url, tracks_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (playlist_id, playlist_name, genre_name, spotify_url, embed_url, tracks_count))

        conn.commit()
        conn.close()
        app.logger.debug(f"Stored playlist in database: {playlist_name} ({playlist_id})")
        return True
    except Exception as e:
        app.logger.error(f"Error storing playlist in database: {str(e)}")
        return False

def deactivate_all_playlists():
    """Deactivate all playlists (call before creating new ones)"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE spotify_playlists SET is_active = 0
        ''')

        conn.commit()
        conn.close()
        app.logger.debug("Deactivated all existing playlists")
        return True
    except Exception as e:
        app.logger.error(f"Error deactivating playlists: {str(e)}")
        return False

def get_stored_playlists(genre_filter=None):
    """Get stored Spotify playlists from database"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        if genre_filter:
            # Get playlists for specific genre
            cursor.execute('''
                SELECT playlist_id, playlist_name, genre_name, spotify_url, embed_url, tracks_count
                FROM spotify_playlists
                WHERE is_active = 1 AND genre_name = ?
                ORDER BY playlist_name
            ''', (genre_filter,))
        else:
            # Get all active playlists
            cursor.execute('''
                SELECT playlist_id, playlist_name, genre_name, spotify_url, embed_url, tracks_count
                FROM spotify_playlists
                WHERE is_active = 1
                ORDER BY genre_name, playlist_name
            ''')

        playlists = cursor.fetchall()
        conn.close()

        # Convert to list of dictionaries
        playlists_list = []
        for playlist in playlists:
            playlists_list.append({
                'id': playlist['playlist_id'],
                'name': playlist['playlist_name'],
                'genre': playlist['genre_name'],
                'url': playlist['spotify_url'],
                'embed_url': playlist['embed_url'],
                'tracks': playlist['tracks_count'],
                'public': True,
                'description': f"PigStyle: {playlist['genre_name']} - {playlist['tracks_count']} tracks"
            })

        return playlists_list
    except Exception as e:
        app.logger.error(f"Error getting stored playlists: {str(e)}")
        return []

# ==================== TOKEN MANAGEMENT FUNCTIONS ====================

def get_basic_auth_header():
    """Get base64 encoded client credentials"""
    auth_string = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    auth_bytes = auth_string.encode('utf-8')
    return base64.b64encode(auth_bytes).decode('utf-8')

def exchange_code_for_token(code, redirect_uri=None):
    """Exchange authorization code for access token"""
    try:
        app.logger.debug(f"DEBUG: Exchanging code for token, redirect_uri: {redirect_uri}")
        token_url = 'https://accounts.spotify.com/api/token'
        headers = {
            'Authorization': f'Basic {get_basic_auth_header()}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri or SPOTIFY_REDIRECT_URI
        }

        response = requests.post(token_url, headers=headers, data=data)
        app.logger.debug(f"DEBUG: Token exchange response status: {response.status_code}")

        if response.status_code == 200:
            token_data = response.json()
            token_data['expires_at'] = datetime.now().timestamp() + token_data.get('expires_in', 3600)
            app.logger.debug(f"DEBUG: Token exchange successful")
            return token_data
        else:
            app.logger.error(f"DEBUG: Token exchange failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        app.logger.error(f"DEBUG: Error exchanging token: {str(e)}")
        return None

def get_valid_token(token_key):
    """Get a valid access token, refreshing if necessary"""
    token_data = user_tokens.get(token_key)

    if not token_data:
        app.logger.debug(f"DEBUG: No token data for key: {token_key}")
        return None

    # Check if token is expired
    if datetime.now().timestamp() > token_data['expires_at']:
        app.logger.debug(f"DEBUG: Token expired, attempting refresh")
        refresh_token = token_data.get('refresh_token')
        if refresh_token:
            # Simple refresh - for now just return None to force re-auth
            app.logger.debug(f"DEBUG: Token needs refresh")
        return None

    app.logger.debug(f"DEBUG: Returning valid token for key: {token_key}")
    return token_data['access_token']

# ==================== SPOTIFY API FUNCTIONS ====================

def search_spotify_album_track(artist, album_title, access_token):
    """Search for an album on Spotify and return the MOST POPULAR track"""
    try:
        app.logger.debug(f"DEBUG: Searching Spotify for artist: {artist}, album: {album_title}")

        # Clean up album title
        clean_album_title = album_title
        for suffix in ['(Vinyl)', '[Vinyl]', '(LP)', '[LP]', '(Album)', '[Album]']:
            clean_album_title = clean_album_title.replace(suffix, '').strip()

        # Search for the album
        search_query = f'album:"{clean_album_title}" artist:"{artist}"'
        search_url = 'https://api.spotify.com/v1/search'
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {'q': search_query, 'type': 'album', 'limit': 5}

        response = requests.get(search_url, headers=headers, params=params)
        app.logger.debug(f"DEBUG: Spotify search response status: {response.status_code}")

        if response.status_code != 200:
            app.logger.debug(f"DEBUG: Spotify search failed with status: {response.status_code}")
            return None

        albums = response.json().get('albums', {}).get('items', [])
        app.logger.debug(f"DEBUG: Found {len(albums)} albums on Spotify")

        if not albums:
            app.logger.debug(f"DEBUG: No albums found for {artist} - {album_title}")
            return None

        # Get the first matching album
        album = albums[0]
        album_id = album['id']
        app.logger.debug(f"DEBUG: Selected album ID: {album_id}")

        # Get tracks from this album
        tracks_url = f'https://api.spotify.com/v1/albums/{album_id}/tracks?limit=50'
        tracks_response = requests.get(tracks_url, headers=headers)

        if tracks_response.status_code != 200:
            app.logger.debug(f"DEBUG: Failed to get album tracks: {tracks_response.status_code}")
            return None

        tracks = tracks_response.json().get('items', [])
        app.logger.debug(f"DEBUG: Found {len(tracks)} tracks in album")

        if not tracks:
            return None

        # Get track details to find most popular
        most_popular_track = None
        highest_popularity = -1

        # Check first 10 tracks
        for track in tracks[:10]:
            track_id = track['id']
            track_details_url = f'https://api.spotify.com/v1/tracks/{track_id}'
            track_response = requests.get(track_details_url, headers=headers)

            if track_response.status_code == 200:
                track_detail = track_response.json()
                popularity = track_detail.get('popularity', 0)
                if popularity > highest_popularity:
                    highest_popularity = popularity
                    most_popular_track = track_detail

        # Fallback to first track
        if not most_popular_track and tracks:
            track_id = tracks[0]['id']
            track_url = f'https://api.spotify.com/v1/tracks/{track_id}'
            track_response = requests.get(track_url, headers=headers)
            if track_response.status_code == 200:
                most_popular_track = track_response.json()

        if most_popular_track:
            app.logger.debug(f"DEBUG: Found track: {most_popular_track['name']} (popularity: {most_popular_track.get('popularity', 0)})")
            return {
                'id': most_popular_track['id'],
                'name': most_popular_track['name'],
                'artists': [artist['name'] for artist in most_popular_track['artists']],
                'album': most_popular_track.get('album', {}).get('name', clean_album_title),
                'uri': most_popular_track['uri'],
                'popularity': most_popular_track.get('popularity', 0)
            }

        app.logger.debug(f"DEBUG: No suitable track found")
        return None

    except Exception as e:
        app.logger.error(f"DEBUG: Error searching album: {str(e)}")
        return None

def clear_spotify_playlist(playlist_id, access_token):
    """Clear all tracks from a Spotify playlist"""
    try:
        app.logger.debug(f"DEBUG: Clearing playlist: {playlist_id}")
        url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Get tracks (paginated)
        all_tracks = []
        next_url = f"{url}?fields=items(track(uri))&limit=100"

        while next_url:
            response = requests.get(next_url, headers=headers)
            app.logger.debug(f"DEBUG: Get tracks response: {response.status_code}")

            if response.status_code != 200:
                return False, f"Failed to get playlist tracks: {response.status_code}"

            data = response.json()
            tracks = data.get('items', [])
            all_tracks.extend([{'uri': item['track']['uri']} for item in tracks])
            next_url = data.get('next')

        app.logger.debug(f"DEBUG: Found {len(all_tracks)} tracks to clear")

        if not all_tracks:
            return True, "Playlist is already empty"

        # Remove all tracks
        remove_url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        remove_data = {'tracks': all_tracks}

        response = requests.delete(remove_url, headers=headers, json=remove_data)
        app.logger.debug(f"DEBUG: Clear response: {response.status_code}")

        if response.status_code == 200:
            return True, f"Cleared {len(all_tracks)} tracks"
        else:
            return False, f"Failed to clear: {response.status_code} - {response.text}"

    except Exception as e:
        app.logger.error(f"DEBUG: Error clearing playlist: {str(e)}")
        return False, f"Error: {str(e)}"

def add_tracks_to_playlist(playlist_id, track_uris, access_token):
    """Add tracks to a Spotify playlist"""
    try:
        app.logger.debug(f"DEBUG: Adding {len(track_uris)} tracks to playlist: {playlist_id}")
        url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Add in batches of 100
        successful = 0
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i+100]
            data = {'uris': batch}

            response = requests.post(url, headers=headers, json=data)
            app.logger.debug(f"DEBUG: Batch {i//100} add response: {response.status_code}")

            if response.status_code == 201:
                successful += len(batch)
                app.logger.debug(f"DEBUG: Batch {i//100} successful, added {len(batch)} tracks")
            else:
                app.logger.error(f"DEBUG: Failed batch {i//100}: {response.text}")

            time.sleep(0.1)

        app.logger.debug(f"DEBUG: Total successful: {successful}/{len(track_uris)}")
        return True, f"Added {successful}/{len(track_uris)} tracks"

    except Exception as e:
        app.logger.error(f"DEBUG: Error adding tracks: {str(e)}")
        return False, f"Error: {str(e)}"

def create_or_get_genre_playlist(genre_name, access_token):
    """Create a new playlist for a genre or get existing one - WITH DEBUG"""
    try:
        app.logger.debug(f"DEBUG: Creating/getting playlist for genre: {genre_name}")

        # Clean genre name for playlist naming
        clean_genre = re.sub(r'[^\w\s-]', '', genre_name).strip()
        if not clean_genre:
            clean_genre = "Miscellaneous"

        playlist_name = f"PigStyle: {clean_genre}"
        playlist_description = f"Vinyl records from PigStyle Records - Genre: {genre_name}"

        app.logger.debug(f"DEBUG: Playlist name: {playlist_name}")

        # First, get current user ID
        user_url = 'https://api.spotify.com/v1/me'
        headers = {'Authorization': f'Bearer {access_token}'}

        user_response = requests.get(user_url, headers=headers)
        app.logger.debug(f"DEBUG: Get user response: {user_response.status_code}")

        if user_response.status_code != 200:
            app.logger.error(f"DEBUG: Failed to get user info: {user_response.status_code}")
            return None

        user_id = user_response.json()['id']
        app.logger.debug(f"DEBUG: Got user ID: {user_id}")

        # Get user's playlists to check for existing
        playlists_url = f'https://api.spotify.com/v1/users/{user_id}/playlists?limit=50'
        playlists_response = requests.get(playlists_url, headers=headers)
        app.logger.debug(f"DEBUG: Get playlists response: {playlists_response.status_code}")

        if playlists_response.status_code == 200:
            playlists = playlists_response.json().get('items', [])
            app.logger.debug(f"DEBUG: Found {len(playlists)} playlists")

            for playlist in playlists:
                if playlist['name'] == playlist_name:
                    app.logger.debug(f"DEBUG: Found existing playlist: {playlist['id']}")
                    return playlist['id']

        # Create new playlist if not found
        app.logger.debug(f"DEBUG: Creating new playlist: {playlist_name}")
        create_url = f'https://api.spotify.com/v1/users/{user_id}/playlists'
        playlist_data = {
            'name': playlist_name,
            'description': playlist_description,
            'public': True
        }

        create_response = requests.post(create_url, headers=headers, json=playlist_data)
        app.logger.debug(f"DEBUG: Create playlist response: {create_response.status_code}")

        if create_response.status_code == 201:
            new_playlist = create_response.json()
            app.logger.debug(f"DEBUG: Created new playlist: {new_playlist['id']}")
            return new_playlist['id']
        else:
            app.logger.error(f"DEBUG: Failed to create playlist: {create_response.status_code} - {create_response.text}")
            return None

    except Exception as e:
        app.logger.error(f"DEBUG: Error creating/getting genre playlist: {str(e)}")
        return None

# ==================== BACKGROUND JOB FUNCTIONS ====================

def process_spotify_update(job_id, code, state, limit, return_url):
    """Background job to process Spotify update - CREATES ALL GENRES PLAYLIST"""
    try:
        background_jobs[job_id]['status'] = 'processing'
        background_jobs[job_id]['message'] = 'Starting authorization...'

        # Exchange code for token
        background_jobs[job_id]['message'] = 'Exchanging code for access token...'
        token_data = exchange_code_for_token(code, 'https://www.pigstylemusic.com/spotify/callback')

        if not token_data:
            background_jobs[job_id]['status'] = 'failed'
            background_jobs[job_id]['message'] = 'Failed to exchange code for token'
            return

        access_token = token_data['access_token']

        # Store token for later use
        token_key = secrets.token_hex(16)
        user_tokens[token_key] = token_data

        # Deactivate all existing playlists in database before creating new ones
        deactivate_all_playlists()

        # Get database records GROUPED BY GENRE
        background_jobs[job_id]['message'] = 'Fetching records from database...'
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT r.artist, r.title, r.genre_id,
                   COALESCE(g.genre_name, 'Miscellaneous') as genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.artist IS NOT NULL AND r.title IS NOT NULL
            AND r.artist != '' AND r.title != ''
            ORDER BY genre_name, r.artist, r.title
        ''')

        records = cursor.fetchall()
        conn.close()

        background_jobs[job_id]['message'] = f'Found {len(records)} records in database'
        background_jobs[job_id]['total_records'] = len(records)

        if len(records) == 0:
            background_jobs[job_id]['status'] = 'failed'
            background_jobs[job_id]['message'] = 'No records found in database'
            return

        # Track all URIs for the master "All Genres" playlist
        all_genres_uris = []
        all_genres_tracks = []

        # Group records by genre
        genre_groups = {}
        for record in records:
            genre_name = record['genre_name']
            if genre_name not in genre_groups:
                genre_groups[genre_name] = []
            genre_groups[genre_name].append(record)

        background_jobs[job_id]['message'] = f'Processing {len(genre_groups)} genres...'
        background_jobs[job_id]['total_genres'] = len(genre_groups)

        results = {}
        all_tracks_added = 0
        genres_processed = 0

        # FIRST: Create "All Genres" master playlist
        background_jobs[job_id]['message'] = 'Creating "All Genres" master playlist...'
        all_genres_playlist_id = create_or_get_genre_playlist("All Genres", access_token)

        if not all_genres_playlist_id:
            background_jobs[job_id]['status'] = 'failed'
            background_jobs[job_id]['message'] = 'Failed to create "All Genres" playlist'
            return

        # Store "All Genres" playlist in database
        store_spotify_playlist(
            playlist_id=all_genres_playlist_id,
            playlist_name="PigStyle: All Genres",
            genre_name="All Genres",
            spotify_url=f"https://open.spotify.com/playlist/{all_genres_playlist_id}",
            embed_url=f"https://open.spotify.com/embed/playlist/{all_genres_playlist_id}?utm_source=generator&theme=0",
            tracks_count=0  # Will be updated later
        )

        # Clear existing tracks from master playlist
        clear_success, clear_msg = clear_spotify_playlist(all_genres_playlist_id, access_token)

        if not clear_success:
            background_jobs[job_id]['message'] = f'Failed to clear master playlist: {clear_msg}'

        # Process each genre
        for genre_name, genre_records in genre_groups.items():
            genres_processed += 1
            background_jobs[job_id]['message'] = f'Processing genre: {genre_name} ({genres_processed}/{len(genre_groups)})'
            background_jobs[job_id]['current_genre'] = genre_name
            background_jobs[job_id]['genres_processed'] = genres_processed

            # Create or get playlist for this genre
            playlist_id = create_or_get_genre_playlist(genre_name, access_token)

            if not playlist_id:
                background_jobs[job_id]['message'] = f'Failed to get playlist for genre: {genre_name}'
                results[genre_name] = {"error": "Failed to create/get playlist"}
                continue

            # Store playlist in database
            store_spotify_playlist(
                playlist_id=playlist_id,
                playlist_name=f"PigStyle: {genre_name}",
                genre_name=genre_name,
                spotify_url=f"https://open.spotify.com/playlist/{playlist_id}",
                embed_url=f"https://open.spotify.com/embed/playlist/{playlist_id}?utm_source=generator&theme=0",
                tracks_count=0  # Will be updated later
            )

            # Clear existing tracks
            clear_success, clear_msg = clear_spotify_playlist(playlist_id, access_token)

            if not clear_success:
                background_jobs[job_id]['message'] = f'Failed to clear playlist: {clear_msg}'
                results[genre_name] = {"error": f"Failed to clear: {clear_msg}"}
                continue

            # Search for tracks
            genre_tracks = []
            genre_track_uris = []

            background_jobs[job_id]['message'] = f'Searching Spotify for {len(genre_records)} tracks in {genre_name}...'
            for i, record in enumerate(genre_records):
                artist = record['artist']
                album = record['title']

                # Update progress for individual tracks
                if i % 5 == 0:
                    background_jobs[job_id]['message'] = f'Searching {genre_name}: {i+1}/{len(genre_records)} tracks...'

                track_info = search_spotify_album_track(artist, album, access_token)

                if track_info:
                    track_entry = {
                        'artist': artist,
                        'album': album,
                        'track': track_info['name'],
                        'uri': track_info['uri']
                    }
                    genre_tracks.append(track_entry)
                    genre_track_uris.append(track_info['uri'])

                    # Also add to master playlist collection
                    all_genres_tracks.append(track_entry)
                    all_genres_uris.append(track_info['uri'])

                time.sleep(0.2)  # Rate limiting

            background_jobs[job_id]['message'] = f'Found {len(genre_tracks)} tracks for genre {genre_name}'

            # Add tracks to genre-specific playlist
            if genre_track_uris:
                add_success, add_msg = add_tracks_to_playlist(playlist_id, genre_track_uris, access_token)

                if add_success:
                    # Update playlist in database with track count
                    store_spotify_playlist(
                        playlist_id=playlist_id,
                        playlist_name=f"PigStyle: {genre_name}",
                        genre_name=genre_name,
                        spotify_url=f"https://open.spotify.com/playlist/{playlist_id}",
                        embed_url=f"https://open.spotify.com/embed/playlist/{playlist_id}?utm_source=generator&theme=0",
                        tracks_count=len(genre_track_uris)
                    )

                    results[genre_name] = {
                        'playlist_id': playlist_id,
                        'playlist_url': f"https://open.spotify.com/playlist/{playlist_id}",
                        'tracks_added': len(genre_track_uris),
                        'total_records': len(genre_records),
                        'sample_tracks': genre_tracks[:5]
                    }
                    all_tracks_added += len(genre_track_uris)
                else:
                    results[genre_name] = {"error": add_msg}
            else:
                results[genre_name] = {"error": "No tracks found on Spotify"}

        # SECOND: Add all tracks to "All Genres" master playlist
        background_jobs[job_id]['message'] = f'Adding {len(all_genres_uris)} tracks to "All Genres" master playlist...'

        if all_genres_uris:
            # Shuffle tracks for variety
            import random
            random.shuffle(all_genres_uris)

            # Add in batches of 100
            add_success, add_msg = add_tracks_to_playlist(all_genres_playlist_id, all_genres_uris, access_token)

            if add_success:
                # Update "All Genres" playlist in database
                store_spotify_playlist(
                    playlist_id=all_genres_playlist_id,
                    playlist_name="PigStyle: All Genres",
                    genre_name="All Genres",
                    spotify_url=f"https://open.spotify.com/playlist/{all_genres_playlist_id}",
                    embed_url=f"https://open.spotify.com/embed/playlist/{all_genres_playlist_id}?utm_source=generator&theme=0",
                    tracks_count=len(all_genres_uris)
                )

                results["All Genres"] = {
                    'playlist_id': all_genres_playlist_id,
                    'playlist_url': f"https://open.spotify.com/playlist/{all_genres_playlist_id}",
                    'tracks_added': len(all_genres_uris),
                    'total_records': len(records),
                    'note': 'Mixed genres playlist'
                }
                background_jobs[job_id]['message'] = f'Created "All Genres" playlist with {len(all_genres_uris)} tracks'
            else:
                results["All Genres"] = {"error": f"Failed to create master playlist: {add_msg}"}
                background_jobs[job_id]['message'] = f'Failed to create "All Genres" playlist: {add_msg}'
        else:
            results["All Genres"] = {"error": "No tracks found for master playlist"}
            background_jobs[job_id]['message'] = 'No tracks found for "All Genres" playlist'

        # Prepare success response
        background_jobs[job_id]['status'] = 'completed'
        background_jobs[job_id]['message'] = f'Completed! Added {all_tracks_added} tracks across {len(results)} playlists including "All Genres"'
        background_jobs[job_id]['results'] = results
        background_jobs[job_id]['all_tracks_added'] = all_tracks_added
        background_jobs[job_id]['total_genres_processed'] = len(genre_groups) + 1  # +1 for "All Genres"
        background_jobs[job_id]['token_key'] = token_key
        background_jobs[job_id]['return_url'] = return_url

    except Exception as e:
        app.logger.error(f"Background job error: {str(e)}", exc_info=True)
        background_jobs[job_id]['status'] = 'failed'
        background_jobs[job_id]['message'] = f'Error: {str(e)}'

# ==================== INTERNAL AUTHORIZATION ENDPOINTS ====================

@app.route('/spotify/authorize-and-update', methods=['GET'])
def authorize_and_update():
    """Internal endpoint that handles auth and starts background playlist update"""
    app.logger.debug("DEBUG: Starting authorize_and_update endpoint")

    # Get parameters
    limit = request.args.get('limit', default=20, type=int)
    state = secrets.token_hex(16)

    # Store in session for callback
    session['spotify_state'] = state
    session['spotify_limit'] = limit
    session['spotify_return_url'] = request.args.get('return_url', 'https://pigstylemusic.com')

    app.logger.debug(f"DEBUG: Generated state: {state}, limit: {limit}")

    # Build authorization URL
    params = {
        'client_id': SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': 'https://www.pigstylemusic.com/spotify/callback',
        'scope': 'playlist-modify-public playlist-modify-private',
        'state': state,
        'show_dialog': 'false'
    }

    auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"
    app.logger.debug(f"DEBUG: Redirecting to auth URL")

    return redirect(auth_url)

@app.route('/spotify/callback', methods=['GET'])
def authorize_callback():
    """Callback for internal authorization - starts background job and returns immediately"""
    app.logger.debug("DEBUG: Starting authorize_callback")

    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    app.logger.debug(f"DEBUG: Callback params - code: {'yes' if code else 'no'}, state: {state}, error: {error}")

    if error:
        app.logger.error(f"DEBUG: Spotify auth error: {error}")
        return jsonify({'error': error}), 400

    if not code:
        app.logger.error("DEBUG: No code provided")
        return jsonify({'error': 'No code provided'}), 400

    # Verify state
    if state != session.get('spotify_state'):
        app.logger.error(f"DEBUG: State mismatch: {state} != {session.get('spotify_state')}")
        return jsonify({'error': 'State mismatch'}), 400

    limit = session.get('spotify_limit', 20)
    return_url = session.get('spotify_return_url', 'https://pigstylemusic.com')

    app.logger.debug(f"DEBUG: Proceeding with limit: {limit}")

    # Create background job
    job_id = str(uuid.uuid4())
    background_jobs[job_id] = {
        'status': 'starting',
        'message': 'Job created, starting soon...',
        'created_at': datetime.now().isoformat(),
        'job_id': job_id
    }

    # Start background job
    thread = threading.Thread(
        target=process_spotify_update,
        args=(job_id, code, state, limit, return_url)
    )
    thread.daemon = True  # Thread won't prevent app from exiting
    thread.start()

    app.logger.debug(f"DEBUG: Started background job: {job_id}")

    # Return immediately with job info
    return jsonify({
        "status": "processing",
        "message": "Spotify playlist update started in background",
        "job_id": job_id,
        "check_status_url": f"https://www.pigstylemusic.com/spotify/job-status/{job_id}",
        "estimated_time": "Several minutes (processing all records)",
        "note": "Keep this job_id to check status later"
    })

@app.route('/spotify/job-status/<job_id>', methods=['GET'])
def job_status(job_id):
    """Check status of background job"""
    job = background_jobs.get(job_id)

    if not job:
        return jsonify({
            'status': 'not_found',
            'message': f'Job {job_id} not found'
        }), 404

    # If job is completed, include redirect info
    response = {
        'job_id': job_id,
        'status': job.get('status', 'unknown'),
        'message': job.get('message', 'No status message'),
        'created_at': job.get('created_at'),
        'current_genre': job.get('current_genre'),
        'genres_processed': job.get('genres_processed', 0),
        'total_genres': job.get('total_genres', 0),
        'total_records': job.get('total_records', 0)
    }

    # Add results if completed
    if job['status'] == 'completed':
        response['results'] = job.get('results', {})
        response['all_tracks_added'] = job.get('all_tracks_added', 0)
        response['token_key'] = job.get('token_key')
        response['redirect_url'] = job.get('return_url', 'https://pigstylemusic.com')

        # You could also automatically redirect here if you want
        # return redirect(f"{job['return_url']}?spotify_success=true&job_id={job_id}")

    elif job['status'] == 'failed':
        response['error'] = job.get('message', 'Unknown error')

    return jsonify(response)

# ==================== SPOTIFY STORED PLAYLISTS ENDPOINT ====================

@app.route('/spotify/stored-playlists', methods=['GET'])
def get_stored_spotify_playlists():
    """Get stored Spotify playlists from database"""
    try:
        # Get genre filter from query parameter
        genre_filter = request.args.get('genre', None)

        # Get playlists from database
        playlists = get_stored_playlists(genre_filter)

        return jsonify({
            'status': 'success',
            'count': len(playlists),
            'playlists': playlists,
            'source': 'Database - Stored PigStyle Playlists'
        })

    except Exception as e:
        app.logger.error(f"Error in /spotify/stored-playlists endpoint: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'note': 'Exception occurred while fetching stored playlists'
        }), 500

# ==================== GENRES ENDPOINT ====================

@app.route('/genres', methods=['GET'])
def get_genres():
    """Get all genres from database for dropdown"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, genre_name
            FROM genres
            ORDER BY id
        ''')

        genres = cursor.fetchall()
        conn.close()

        # Convert to list of dictionaries
        genres_list = []
        for genre in genres:
            genres_list.append({
                'id': genre['id'],
                'genre_name': genre['genre_name']
            })

        return jsonify({
            'status': 'success',
            'count': len(genres_list),
            'genres': genres_list
        })

    except Exception as e:
        app.logger.error(f"Error in /genres endpoint: {str(e)}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

# ==================== RECORDS ENDPOINTS ====================

@app.route('/records', methods=['GET'])
def get_records():
    """Get all records from database for streaming page"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get query parameters
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)

        # Query database - JOIN with genres table to get genre names
        cursor.execute('''
            SELECT r.*, COALESCE(g.genre_name, 'Unknown') as genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.artist IS NOT NULL AND r.title IS NOT NULL
            AND r.artist != '' AND r.title != ''
            ORDER BY r.artist, r.title
            LIMIT ? OFFSET ?
        ''', (limit, offset))

        records = cursor.fetchall()
        conn.close()

        # Convert to list of dictionaries
        records_list = []
        for record in records:
            record_dict = dict(record)
            records_list.append(record_dict)

        return jsonify({
            'status': 'success',
            'count': len(records_list),
            'total': len(records_list),
            'records': records_list
        })

    except Exception as e:
        app.logger.error(f"Error in /records endpoint: {str(e)}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/records/count', methods=['GET'])
def get_records_count():
    """Get count of records in database"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM records')
        result = cursor.fetchone()
        conn.close()
        return jsonify({'status': 'success', 'count': result['count']})
    except Exception as e:
        app.logger.error(f"Error getting records count: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)