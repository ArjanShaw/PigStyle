from app import app, get_db
from flask import jsonify, request
from datetime import datetime

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