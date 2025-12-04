from app import app, get_db
from flask import jsonify

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