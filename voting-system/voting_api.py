# /home/arjanshaw/voting_api.py
from flask import Flask, request, jsonify
import sqlite3
import os

# Use 'application' for PythonAnywhere
application = Flask(__name__)

# Database configuration - absolute path
DATABASE = '/home/arjanshaw/votes.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the database with required tables"""
    try:
        # Ensure the database file exists and is writable
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create votes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist_title TEXT NOT NULL,
                voter_hash TEXT NOT NULL,
                vote_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(artist_title, voter_hash)
            )
        ''')
        
        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_artist_title ON votes (artist_title)
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        # Create an empty database file if it doesn't exist
        try:
            open(DATABASE, 'a').close()
            print("✅ Created empty database file")
        except:
            print("❌ Could not create database file")

# Initialize database when app starts
init_database()

@application.after_request
def after_request(response):
    """Add CORS headers to all responses - NO flask_cors needed!"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@application.route('/')
def home():
    """Root endpoint - API information"""
    return jsonify({
        'message': 'PigStyle Records Voting API',
        'status': 'online',
        'version': '1.0',
        'endpoints': {
            '/': 'GET - API information (this page)',
            '/api/votes': 'GET - Get all vote counts',
            '/api/votes/<artist_title>': 'GET - Get votes for specific record',
            '/api/vote': 'POST - Record a vote'
        }
    })

@application.route('/api/votes', methods=['GET'])
def get_all_votes():
    """Get all vote counts for all records"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get vote counts for all artist_title combinations
        cursor.execute('''
            SELECT 
                artist_title,
                SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes
            FROM votes 
            GROUP BY artist_title
        ''')
        
        vote_counts = {}
        for row in cursor.fetchall():
            vote_counts[row['artist_title']] = {
                'upvotes': row['upvotes'] or 0,
                'downvotes': row['downvotes'] or 0
            }
        
        conn.close()
        
        return jsonify({
            'success': True,
            'vote_counts': vote_counts,
            'total_records': len(vote_counts)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@application.route('/api/vote', methods=['POST', 'OPTIONS'])
def record_vote():
    """Record a vote using artist_title as key"""
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'})
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['artist_title', 'voter_hash', 'vote_type']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        artist_title = data['artist_title']
        voter_hash = data['voter_hash']
        vote_type = data['vote_type']
        
        # Validate vote_type
        if vote_type not in ['upvote', 'downvote']:
            return jsonify({
                'success': False,
                'error': 'Invalid vote_type. Must be "upvote" or "downvote"'
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Use INSERT OR REPLACE to handle vote changes
        cursor.execute('''
            INSERT OR REPLACE INTO votes (artist_title, voter_hash, vote_type)
            VALUES (?, ?, ?)
        ''', (artist_title, voter_hash, vote_type))
        
        conn.commit()
        
        # Get updated vote counts for this artist_title
        cursor.execute('''
            SELECT 
                SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes
            FROM votes 
            WHERE artist_title = ?
        ''', (artist_title,))
        
        result = cursor.fetchone()
        vote_counts = {
            artist_title: {
                'upvotes': result['upvotes'] or 0,
                'downvotes': result['downvotes'] or 0
            }
        }
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{vote_type} recorded successfully for {artist_title}',
            'vote_counts': vote_counts
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@application.route('/api/votes/<path:artist_title>', methods=['GET'])
def get_votes_for_artist_title(artist_title):
    """Get vote counts for a specific artist_title"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes
            FROM votes 
            WHERE artist_title = ?
        ''', (artist_title,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'artist_title': artist_title,
                'upvotes': result['upvotes'] or 0,
                'downvotes': result['downvotes'] or 0
            })
        else:
            return jsonify({
                'success': True,
                'artist_title': artist_title,
                'upvotes': 0,
                'downvotes': 0,
                'message': 'No votes found for this record'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# For local development
if __name__ == '__main__':
    application.run(debug=True)