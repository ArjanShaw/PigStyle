from app import app, get_db
from flask import jsonify
from datetime import datetime

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