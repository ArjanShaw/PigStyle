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

# ==================== VOTING ENDPOINTS ====================

@app.route('/vote/<int:record_id>/<ip_address>/<vote_type>', methods=['POST'])
def record_vote(record_id, ip_address, vote_type):
    """Record a vote (upvote or downvote) for a record from a specific IP"""
    try:
        if vote_type not in ['upvote', 'downvote']:
            return jsonify({'error': 'Invalid vote type. Use "upvote" or "downvote"'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Check if this IP has already voted for this record
        cursor.execute('''
            SELECT id FROM record_votes
            WHERE record_id = ? AND ip_address = ?
        ''', (record_id, ip_address))

        existing_vote = cursor.fetchone()

        if existing_vote:
            # Update existing vote
            cursor.execute('''
                UPDATE record_votes
                SET vote_type = ?, voted_at = ?
                WHERE id = ?
            ''', (vote_type, datetime.now(), existing_vote['id']))
        else:
            # Insert new vote
            cursor.execute('''
                INSERT INTO record_votes (record_id, ip_address, vote_type, voted_at)
                VALUES (?, ?, ?, ?)
            ''', (record_id, ip_address, vote_type, datetime.now()))

        # Update vote counts in records table
        cursor.execute('''
            SELECT
                SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes
            FROM record_votes
            WHERE record_id = ?
        ''', (record_id,))

        counts = cursor.fetchone()
        upvotes = counts['upvotes'] or 0
        downvotes = counts['downvotes'] or 0

        cursor.execute('''
            UPDATE records
            SET upvotes = ?, downvotes = ?
            WHERE id = ?
        ''', (upvotes, downvotes, record_id))

        conn.commit()
        conn.close()

        return jsonify({
            'status': 'success',
            'message': f'{vote_type} recorded',
            'upvotes': upvotes,
            'downvotes': downvotes
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/votes/record/<int:record_id>', methods=['GET'])
def get_record_votes(record_id):
    """Get vote counts for a specific record"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT upvotes, downvotes FROM records WHERE id = ?
        ''', (record_id,))

        record = cursor.fetchone()

        if not record:
            conn.close()
            return jsonify({'error': 'Record not found'}), 404

        # Get vote breakdown by IP
        cursor.execute('''
            SELECT ip_address, vote_type, voted_at
            FROM record_votes
            WHERE record_id = ?
            ORDER BY voted_at DESC
        ''', (record_id,))

        votes = cursor.fetchall()
        votes_list = []
        for vote in votes:
            votes_list.append({
                'ip_address': vote['ip_address'],
                'vote_type': vote['vote_type'],
                'voted_at': vote['voted_at']
            })

        conn.close()

        return jsonify({
            'status': 'success',
            'record_id': record_id,
            'upvotes': record['upvotes'] or 0,
            'downvotes': record['downvotes'] or 0,
            'total_votes': (record['upvotes'] or 0) + (record['downvotes'] or 0),
            'votes': votes_list
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== CORE RECORD ENDPOINTS ====================

@app.route('/records', methods=['GET'])
def get_all_records():
    """Get all records with genre names via JOIN"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        limit = request.args.get('limit', default=1000, type=int)
        offset = request.args.get('offset', default=0, type=int)

        cursor.execute('''
            SELECT r.*, g.genre_name as genre
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            ORDER BY r.id
            LIMIT ? OFFSET ?
        ''', (limit, offset))

        records = cursor.fetchall()
        conn.close()

        records_list = []
        for record in records:
            record_dict = dict(record)
            records_list.append(record_dict)

        return jsonify({
            'status': 'success',
            'records': records_list
        })

    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/records/<int:record_id>', methods=['GET'])
def get_record_by_id(record_id):
    """Get a single record by ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, g.genre_name as genre
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.id = ?
        ''', (record_id,))

        record = cursor.fetchone()
        conn.close()

        if record:
            return jsonify(dict(record))
        else:
            return jsonify({'error': 'Record not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/records/barcode/<barcode>', methods=['GET'])
def get_record_by_barcode(barcode):
    """Get record by barcode"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, g.genre_name as genre
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.barcode = ?
        ''', (barcode,))

        record = cursor.fetchone()
        conn.close()

        if record:
            return jsonify(dict(record))
        else:
            return jsonify({'error': 'Record not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/search', methods=['GET'])
def search_records():
    """Search records"""
    try:
        search_term = request.args.get('q', '')
        if not search_term:
            return jsonify({'records': []})

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, g.genre_name as genre
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.artist LIKE ? OR r.title LIKE ? OR r.barcode LIKE ?
            ORDER BY r.artist, r.title
            LIMIT 100
        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

        records = cursor.fetchall()
        conn.close()

        records_list = []
        for record in records:
            records_list.append(dict(record))

        return jsonify({
            'status': 'success',
            'records': records_list
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/records/no-barcodes', methods=['GET'])
def get_records_without_barcodes():
    """Get records without barcodes"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, g.genre_name as genre
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.barcode IS NULL OR r.barcode = '' OR r.barcode = 'None'
            ORDER BY r.id
        ''')

        records = cursor.fetchall()
        conn.close()

        records_list = []
        for record in records:
            records_list.append(dict(record))

        return jsonify({
            'status': 'success',
            'records': records_list
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/records/user/<int:user_id>', methods=['GET'])
def get_user_records(user_id):
    """Get records for a specific user (consignor)"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, g.genre_name as genre
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.consignor_id = ?
            ORDER BY r.id
        ''', (user_id,))

        records = cursor.fetchall()
        conn.close()

        records_list = []
        for record in records:
            records_list.append(dict(record))

        return jsonify({
            'status': 'success',
            'records': records_list
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== GENRE ENDPOINTS ====================

@app.route('/genres', methods=['GET'])
def get_all_genres():
    """Get all genres"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT id, genre_name FROM genres ORDER BY genre_name')

        genres = cursor.fetchall()
        conn.close()

        genres_list = []
        for genre in genres:
            genres_list.append({
                'id': genre['id'],
                'genre_name': genre['genre_name']
            })

        return jsonify({
            'status': 'success',
            'genres': genres_list
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/genres', methods=['POST'])
def add_genre():
    """Add a new genre"""
    try:
        data = request.get_json()
        if not data or 'genre_name' not in data:
            return jsonify({'error': 'genre_name required'}), 400

        genre_name = data['genre_name'].strip()

        conn = get_db()
        cursor = conn.cursor()

        # Check if genre already exists
        cursor.execute('SELECT id FROM genres WHERE genre_name = ?', (genre_name,))
        existing = cursor.fetchone()

        if existing:
            conn.close()
            return jsonify({
                'status': 'success',
                'genre_id': existing['id'],
                'message': 'Genre already exists'
            })

        # Insert new genre
        cursor.execute('INSERT INTO genres (genre_name) VALUES (?)', (genre_name,))
        genre_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'status': 'success',
            'genre_id': genre_id,
            'message': 'Genre created'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/genre-assignments/artist/<artist_name>', methods=['GET'])
def get_artist_genre(artist_name):
    """Get genre assigned to an artist"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get the most common genre for this artist from records
        cursor.execute('''
            SELECT g.genre_name, COUNT(*) as count
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.artist = ?
            GROUP BY g.genre_name
            ORDER BY count DESC
            LIMIT 1
        ''', (artist_name,))

        result = cursor.fetchone()
        conn.close()

        if result and result['genre_name']:
            return jsonify({
                'artist_name': artist_name,
                'genre_name': result['genre_name']
            })
        else:
            return jsonify({
                'artist_name': artist_name,
                'genre_name': None
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/genre-assignments', methods=['POST'])
def assign_genre_to_artist():
    """Assign genre to artist"""
    try:
        data = request.get_json()
        if not data or 'artist_name' not in data or 'genre_id' not in data:
            return jsonify({'error': 'artist_name and genre_id required'}), 400

        artist_name = data['artist_name']
        genre_id = data['genre_id']

        conn = get_db()
        cursor = conn.cursor()

        # Update all records by this artist
        cursor.execute('''
            UPDATE records
            SET genre_id = ?
            WHERE artist = ?
        ''', (genre_id, artist_name))

        updated_count = cursor.rowcount
        conn.commit()
        conn.close()

        return jsonify({
            'status': 'success',
            'updated_count': updated_count,
            'message': f'Updated {updated_count} records'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/genre-assignments/artist/<artist_name>', methods=['DELETE'])
def remove_genre_from_artist(artist_name):
    """Remove genre assignment from artist"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Set genre_id to NULL for all records by this artist
        cursor.execute('''
            UPDATE records
            SET genre_id = NULL
            WHERE artist = ?
        ''', (artist_name,))

        updated_count = cursor.rowcount
        conn.commit()
        conn.close()

        return jsonify({
            'status': 'success',
            'updated_count': updated_count,
            'message': f'Removed genre from {updated_count} records'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== USER ENDPOINTS ====================

@app.route('/users', methods=['GET'])
def get_all_users():
    """Get all users"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, email, role, full_name, created_at
            FROM users
            WHERE is_active = 1
            ORDER BY username
        ''')

        users = cursor.fetchall()
        conn.close()

        users_list = []
        for user in users:
            users_list.append({
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'full_name': user['full_name'],
                'created_at': user['created_at']
            })

        return jsonify({
            'status': 'success',
            'users': users_list
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user by ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, email, role, full_name, created_at
            FROM users
            WHERE id = ? AND is_active = 1
        ''', (user_id,))

        user = cursor.fetchone()
        conn.close()

        if user:
            return jsonify(dict(user))
        else:
            return jsonify({'error': 'User not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/verify-login/<int:user_id>', methods=['POST'])
def debug_verify_login(user_id):
    """Debug endpoint to verify login"""
    try:
        data = request.get_json()
        if not data or 'password' not in data:
            return jsonify({'error': 'Password required'}), 400

        password = data['password']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT password_hash FROM users WHERE id = ? AND is_active = 1', (user_id,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            return jsonify({'login_valid': False, 'error': 'User not found'}), 404

        # Password verification function
        def verify_password(password, password_hash):
            try:
                if not password_hash or '$' not in password_hash:
                    return False
                salt, hash_value = password_hash.split('$')
                return hashlib.sha256((salt + password).encode()).hexdigest() == hash_value
            except:
                return False

        if verify_password(password, user['password_hash']):
            return jsonify({'login_valid': True, 'message': 'Password verified'})
        else:
            return jsonify({'login_valid': False, 'error': 'Invalid password'})

    except Exception as e:
        return jsonify({'login_valid': False, 'error': str(e)}), 500

# ==================== CONFIGURATION ENDPOINTS ====================

@app.route('/config', methods=['GET'])
def get_all_config():
    """Get all configuration values"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT config_key, config_value FROM app_config')

        configs = cursor.fetchall()
        conn.close()

        config_dict = {}
        for config in configs:
            config_dict[config['config_key']] = config['config_value']

        return jsonify({
            'status': 'success',
            'configs': config_dict
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== STATISTICS ENDPOINTS ====================

@app.route('/stats', methods=['GET'])
def get_database_stats():
    """Get database statistics"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get record count
        cursor.execute('SELECT COUNT(*) as count FROM records')
        records_count = cursor.fetchone()['count']

        # Get user count
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE is_active = 1')
        users_count = cursor.fetchone()['count']

        # Get latest record
        cursor.execute('SELECT artist, title FROM records ORDER BY id DESC LIMIT 1')
        latest_record = cursor.fetchone()

        conn.close()

        return jsonify({
            'status': 'success',
            'records_count': records_count,
            'users_count': users_count,
            'latest_record': f"{latest_record['artist']} - {latest_record['title']}" if latest_record else 'N/A',
            'db_path': DB_PATH
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== BARCODE ENDPOINTS ====================

@app.route('/barcodes/assign', methods=['POST'])
def assign_barcodes():
    """Assign barcodes to records"""
    try:
        data = request.get_json()
        if not data or 'record_ids' not in data:
            return jsonify({'error': 'record_ids required'}), 400

        record_ids = data['record_ids']
        if not isinstance(record_ids, list):
            return jsonify({'error': 'record_ids must be a list'}), 400

        conn = get_db()
        cursor = conn.cursor()

        barcode_mapping = {}

        for record_id in record_ids:
            # Generate a new barcode (simple sequential for now)
            cursor.execute('SELECT MAX(CAST(barcode AS INTEGER)) as max_barcode FROM records WHERE barcode GLOB "[0-9]*"')
            result = cursor.fetchone()
            max_barcode = result['max_barcode'] or 100000

            new_barcode = str(max_barcode + 1)

            # Update the record
            cursor.execute('UPDATE records SET barcode = ? WHERE id = ?', (new_barcode, record_id))

            barcode_mapping[str(record_id)] = new_barcode

        conn.commit()
        conn.close()

        return jsonify({
            'status': 'success',
            'barcode_mapping': barcode_mapping,
            'message': f'Assigned barcodes to {len(record_ids)} records'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== RECORD OPERATIONS ====================

@app.route('/records/<int:record_id>', methods=['PUT'])
def update_record(record_id):
    """Update a record"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Build update query
        update_fields = []
        update_values = []

        for key, value in data.items():
            update_fields.append(f"{key} = ?")
            update_values.append(value)

        update_values.append(record_id)

        query = f"UPDATE records SET {', '.join(update_fields)}, updated_at = ? WHERE id = ?"
        update_values.append(datetime.now())

        cursor.execute(query, update_values)
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()

        if rows_affected > 0:
            return jsonify({'status': 'success', 'message': 'Record updated'})
        else:
            return jsonify({'error': 'Record not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/records', methods=['POST'])
def create_record():
    """Create a new record"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        required_fields = ['artist', 'title']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Build insert query
        fields = ['artist', 'title', 'created_at', 'updated_at']
        placeholders = ['?'] * len(fields)
        values = [data.get('artist'), data.get('title'), datetime.now(), datetime.now()]

        # Add optional fields
        optional_fields = ['genre_id', 'image_url', 'discogs_suggested_price', 'catalog_number',
                          'format', 'condition', 'store_price', 'ebay_sell_at', 'youtube_url',
                          'compilation', 'consignor_id', 'commission_rate', 'store_return_days',
                          'upvotes', 'downvotes']

        for field in optional_fields:
            if field in data:
                fields.append(field)
                placeholders.append('?')
                values.append(data[field])

        query = f"INSERT INTO records ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(query, values)

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'status': 'success',
            'record_id': record_id,
            'message': 'Record created'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ROOT ENDPOINT ====================

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