from app import app, get_db
from flask import jsonify, request

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