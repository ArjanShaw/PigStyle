from app import app, get_db
from flask import jsonify, request

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