from flask import Flask, request, jsonify
import sqlite3
import hashlib
import os
from datetime import datetime

app = Flask(__name__)

# Database configuration
DB_PATH = '/home/arjanshaw/votes.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the database if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create voter_tracking table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voter_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            voter_hash TEXT NOT NULL,
            vote_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(record_id, voter_hash)
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/api/vote', methods=['POST'])
def record_vote():
    """Record a vote for a record"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'record_id' not in data or 'vote_type' not in data:
            return jsonify({'error': 'Missing required fields: record_id and vote_type'}), 400
        
        record_id = data['record_id']
        vote_type = data['vote_type']
        
        # Validate vote type
        if vote_type not in ['upvote', 'downvote']:
            return jsonify({'error': 'Invalid vote_type. Must be "upvote" or "downvote"'}), 400
        
        # Generate voter hash from IP address and user agent
        voter_ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        voter_string = f"{voter_ip}{user_agent}"
        voter_hash = hashlib.md5(voter_string.encode()).hexdigest()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Use INSERT OR REPLACE to handle vote changes
            cursor.execute('''
                INSERT OR REPLACE INTO voter_tracking (record_id, voter_hash, vote_type)
                VALUES (?, ?, ?)
            ''', (record_id, voter_hash, vote_type))
            
            conn.commit()
            
            # Get updated vote counts
            vote_counts = get_vote_counts(record_id)
            
            return jsonify({
                'success': True,
                'record_id': record_id,
                'vote_type': vote_type,
                'vote_counts': vote_counts
            })
            
        except sqlite3.IntegrityError as e:
            return jsonify({'error': f'Database integrity error: {str(e)}'}), 400
        except Exception as e:
            return jsonify({'error': f'Database error: {str(e)}'}), 500
        finally:
            conn.close()
            
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/votes/<int:record_id>', methods=['GET'])
def get_votes(record_id):
    """Get vote counts for a specific record"""
    try:
        vote_counts = get_vote_counts(record_id)
        return jsonify({
            'success': True,
            'record_id': record_id,
            'vote_counts': vote_counts
        })
    except Exception as e:
        return jsonify({'error': f'Error retrieving votes: {str(e)}'}), 500

def get_vote_counts(record_id):
    """Get vote counts for a specific record"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
            SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes
        FROM voter_tracking 
        WHERE record_id = ?
    ''', (record_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    upvotes = result['upvotes'] if result and result['upvotes'] is not None else 0
    downvotes = result['downvotes'] if result and result['downvotes'] is not None else 0
    
    return {
        'upvotes': int(upvotes),
        'downvotes': int(downvotes)
    }

@app.route('/api/votes', methods=['GET'])
def get_all_votes():
    """Get vote counts for all records"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                record_id,
                SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
                SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes
            FROM voter_tracking 
            GROUP BY record_id
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        vote_counts = {}
        for row in results:
            vote_counts[row['record_id']] = {
                'upvotes': int(row['upvotes']),
                'downvotes': int(row['downvotes'])
            }
        
        return jsonify({
            'success': True,
            'vote_counts': vote_counts
        })
        
    except Exception as e:
        return jsonify({'error': f'Error retrieving all votes: {str(e)}'}), 500

@app.route('/api/user_vote/<int:record_id>', methods=['GET'])
def get_user_vote(record_id):
    """Get a user's vote for a specific record"""
    try:
        # Generate voter hash from IP address and user agent
        voter_ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        voter_string = f"{voter_ip}{user_agent}"
        voter_hash = hashlib.md5(voter_string.encode()).hexdigest()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT vote_type FROM voter_tracking 
            WHERE record_id = ? AND voter_hash = ?
        ''', (record_id, voter_hash))
        
        result = cursor.fetchone()
        conn.close()
        
        user_vote = result['vote_type'] if result else None
        
        return jsonify({
            'success': True,
            'record_id': record_id,
            'user_vote': user_vote
        })
        
    except Exception as e:
        return jsonify({'error': f'Error retrieving user vote: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# Initialize database when starting
init_database()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
