from app import app, get_db
from flask import jsonify, request
import hashlib

@app.route('/users', methods=['GET'])
def get_all_users():
    """Get all users"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, email, role, full_name, created_at
            FROM users
            WHERE is_active = 1
            ORDER BY username
        ''')

        users = cursor.fetchall()
        conn.close()

        users_list = []
        for user in users:
            users_list.append({
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'full_name': user['full_name'],
                'created_at': user['created_at']
            })

        return jsonify({
            'status': 'success',
            'users': users_list
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user by ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, username, email, role, full_name, created_at
            FROM users
            WHERE id = ? AND is_active = 1
        ''', (user_id,))

        user = cursor.fetchone()
        conn.close()

        if user:
            return jsonify(dict(user))
        else:
            return jsonify({'error': 'User not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug/verify-login/<int:user_id>', methods=['POST'])
def debug_verify_login(user_id):
    """Debug endpoint to verify login"""
    try:
        data = request.get_json()
        if not data or 'password' not in data:
            return jsonify({'error': 'Password required'}), 400

        password = data['password']

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT password_hash FROM users WHERE id = ? AND is_active = 1', (user_id,))
        user = cursor.fetchone()
        conn.close()

        if not user:
            return jsonify({'login_valid': False, 'error': 'User not found'}), 404

        # Password verification function
        def verify_password(password, password_hash):
            try:
                if not password_hash or '$' not in password_hash:
                    return False
                salt, hash_value = password_hash.split('$')
                return hashlib.sha256((salt + password).encode()).hexdigest() == hash_value
            except:
                return False

        if verify_password(password, user['password_hash']):
            return jsonify({'login_valid': True, 'message': 'Password verified'})
        else:
            return jsonify({'login_valid': False, 'error': 'Invalid password'})

    except Exception as e:
        return jsonify({'login_valid': False, 'error': str(e)}), 500