from flask import Flask, request, jsonify
import sqlite3
import hashlib
import json
from datetime import datetime
from functools import wraps

app = Flask(__name__)

# Database configuration
DATABASE = 'votes.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create votes table - using artist_title as primary key
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

def cors_headers(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)
        if isinstance(response, tuple):
            response, status = response
        else:
            status = 200
        
        # Add CORS headers
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
        
        if isinstance(response, dict):
            return jsonify(response), status, headers
        else:
            return response, status, headers
    return decorated_function

@app.route('/api/votes', methods=['GET', 'OPTIONS'])
@cors_headers
def get_all_votes():
    """Get all vote counts for all records"""
    if request.method == 'OPTIONS':
        return {}
    
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
        
        return {
            'success': True,
            'vote_counts': vote_counts
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }, 500

@app.route('/api/vote', methods=['POST', 'OPTIONS'])
@cors_headers
def record_vote():
    """Record a vote using artist_title as key"""
    if request.method == 'OPTIONS':
        return {}
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['artist_title', 'voter_hash', 'vote_type']
        for field in required_fields:
            if field not in data:
                return {
                    'success': False,
                    'error': f'Missing required field: {field}'
                }, 400
        
        artist_title = data['artist_title']
        voter_hash = data['voter_hash']
        vote_type = data['vote_type']
        
        # Validate vote_type
        if vote_type not in ['upvote', 'downvote']:
            return {
                'success': False,
                'error': 'Invalid vote_type. Must be "upvote" or "downvote"'
            }, 400
        
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
        
        return {
            'success': True,
            'message': f'{vote_type} recorded successfully for {artist_title}',
            'vote_counts': vote_counts
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }, 500

@app.route('/api/votes/<path:artist_title>', methods=['GET', 'OPTIONS'])
@cors_headers
def get_votes_for_artist_title(artist_title):
    """Get vote counts for a specific artist_title"""
    if request.method == 'OPTIONS':
        return {}
    
    try:
        # URL decode the artist_title
        import urllib.parse
        artist_title = urllib.parse.unquote(artist_title)
        
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
            return {
                'success': True,
                'artist_title': artist_title,
                'upvotes': result['upvotes'] or 0,
                'downvotes': result['downvotes'] or 0
            }
        else:
            return {
                'success': True,
                'artist_title': artist_title,
                'upvotes': 0,
                'downvotes': 0
            }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }, 500

# Initialize database when starting
init_database()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)