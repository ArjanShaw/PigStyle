from app import app, get_db
from flask import jsonify

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