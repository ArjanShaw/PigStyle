from app import app, get_db
from flask import jsonify, request

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