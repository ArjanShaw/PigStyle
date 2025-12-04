import os
import requests
import base64
from flask import Flask, jsonify, request, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
import hashlib
import secrets
import re
import logging
from logging.handlers import RotatingFileHandler
import random
import time
import urllib.parse
import json

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here-change-this')

# CORS Configuration
CORS(app, resources={
    r"/*": {
        "origins": [
            "https://pigstylemusic.com",
            "https://arjanshaw.github.io",
            "https://pigstylerecords.github.io",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "https://arjanshaw.pythonanywhere.com",
            "http://arjanshaw.pythonanywhere.com"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
        "expose_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False,
        "max_age": 600
    }
})

# Database configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "records.db")

# Spotify configuration
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', 'your-client-id-here')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', 'your-client-secret-here')
SPOTIFY_REDIRECT_URI = 'https://arjanshaw.pythonanywhere.com/spotify/callback'

# Your Spotify playlist ID
YOUR_SPOTIFY_PLAYLIST_ID = '72RkLX9Hhy5LZcaUTNSj60'

# Token storage (in production, use database or Redis)
user_tokens = {}

def setup_logging():
    """Setup application logging"""
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)

    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'api.log'),
        maxBytes=1024 * 1024,
        backupCount=10
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))

    app.logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    app.logger.addHandler(console_handler)

setup_logging()

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== TOKEN MANAGEMENT FUNCTIONS ====================

def get_basic_auth_header():
    """Get base64 encoded client credentials"""
    auth_string = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    auth_bytes = auth_string.encode('utf-8')
    return base64.b64encode(auth_bytes).decode('utf-8')

def exchange_code_for_token(code, redirect_uri=None):
    """Exchange authorization code for access token"""
    try:
        token_url = 'https://accounts.spotify.com/api/token'
        headers = {
            'Authorization': f'Basic {get_basic_auth_header()}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri or SPOTIFY_REDIRECT_URI
        }

        response = requests.post(token_url, headers=headers, data=data)
        if response.status_code == 200:
            token_data = response.json()
            # Store the token with expiration time
            token_data['expires_at'] = datetime.now().timestamp() + token_data.get('expires_in', 3600)
            return token_data
        else:
            app.logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        app.logger.error(f"Error exchanging token: {str(e)}")
        return None

def refresh_access_token(refresh_token):
    """Refresh access token using refresh token"""
    try:
        token_url = 'https://accounts.spotify.com/api/token'
        headers = {
            'Authorization': f'Basic {get_basic_auth_header()}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }

        response = requests.post(token_url, headers=headers, data=data)
        if response.status_code == 200:
            token_data = response.json()
            token_data['expires_at'] = datetime.now().timestamp() + token_data.get('expires_in', 3600)
            return token_data
        else:
            app.logger.error(f"Token refresh failed: {response.status_code}")
            return None
    except Exception as e:
        app.logger.error(f"Error refreshing token: {str(e)}")
        return None

def get_valid_token(token_key):
    """Get a valid access token, refreshing if necessary"""
    token_data = user_tokens.get(token_key)

    if not token_data:
        return None

    # Check if token is expired
    if datetime.now().timestamp() > token_data['expires_at']:
        refresh_token = token_data.get('refresh_token')
        if refresh_token:
            new_token_data = refresh_access_token(refresh_token)
            if new_token_data:
                # Preserve refresh token if not provided in refresh response
                if 'refresh_token' not in new_token_data:
                    new_token_data['refresh_token'] = refresh_token
                user_tokens[token_key] = new_token_data
                return new_token_data['access_token']
        return None

    return token_data['access_token']

# ==================== SPOTIFY API FUNCTIONS ====================

def search_spotify_album_track(artist, album_title, access_token):
    """Search for an album on Spotify and return the MOST POPULAR track"""
    try:
        # Clean up album title
        clean_album_title = album_title
        for suffix in ['(Vinyl)', '[Vinyl]', '(LP)', '[LP]', '(Album)', '[Album]']:
            clean_album_title = clean_album_title.replace(suffix, '').strip()

        # Search for the album
        search_query = f'album:"{clean_album_title}" artist:"{artist}"'
        search_url = 'https://api.spotify.com/v1/search'
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {'q': search_query, 'type': 'album', 'limit': 5}

        response = requests.get(search_url, headers=headers, params=params)
        if response.status_code != 200:
            return None

        albums = response.json().get('albums', {}).get('items', [])
        if not albums:
            return None

        # Get the first matching album
        album = albums[0]
        album_id = album['id']

        # Get tracks from this album
        tracks_url = f'https://api.spotify.com/v1/albums/{album_id}/tracks?limit=50'
        tracks_response = requests.get(tracks_url, headers=headers)

        if tracks_response.status_code != 200:
            return None

        tracks = tracks_response.json().get('items', [])
        if not tracks:
            return None

        # Get track details to find most popular
        most_popular_track = None
        highest_popularity = -1

        # Check first 10 tracks
        for track in tracks[:10]:
            track_id = track['id']
            track_details_url = f'https://api.spotify.com/v1/tracks/{track_id}'
            track_response = requests.get(track_details_url, headers=headers)

            if track_response.status_code == 200:
                track_detail = track_response.json()
                popularity = track_detail.get('popularity', 0)
                if popularity > highest_popularity:
                    highest_popularity = popularity
                    most_popular_track = track_detail

        # Fallback to first track
        if not most_popular_track and tracks:
            track_id = tracks[0]['id']
            track_url = f'https://api.spotify.com/v1/tracks/{track_id}'
            track_response = requests.get(track_url, headers=headers)
            if track_response.status_code == 200:
                most_popular_track = track_response.json()

        if most_popular_track:
            return {
                'id': most_popular_track['id'],
                'name': most_popular_track['name'],
                'artists': [artist['name'] for artist in most_popular_track['artists']],
                'album': most_popular_track.get('album', {}).get('name', clean_album_title),
                'uri': most_popular_track['uri'],
                'popularity': most_popular_track.get('popularity', 0)
            }
        return None

    except Exception as e:
        app.logger.error(f"Error searching album: {str(e)}")
        return None

def clear_spotify_playlist(playlist_id, access_token):
    """Clear all tracks from a Spotify playlist"""
    try:
        # Get all current tracks
        url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Get tracks (paginated)
        all_tracks = []
        next_url = f"{url}?fields=items(track(uri))&limit=100"

        while next_url:
            response = requests.get(next_url, headers=headers)
            if response.status_code != 200:
                return False, f"Failed to get playlist tracks: {response.status_code}"

            data = response.json()
            tracks = data.get('items', [])
            all_tracks.extend([{'uri': item['track']['uri']} for item in tracks])
            next_url = data.get('next')

        if not all_tracks:
            return True, "Playlist is already empty"

        # Remove all tracks
        remove_url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        remove_data = {'tracks': all_tracks}

        response = requests.delete(remove_url, headers=headers, json=remove_data)
        if response.status_code == 200:
            return True, f"Cleared {len(all_tracks)} tracks"
        else:
            return False, f"Failed to clear: {response.status_code} - {response.text}"

    except Exception as e:
        return False, f"Error: {str(e)}"

def add_tracks_to_playlist(playlist_id, track_uris, access_token):
    """Add tracks to a Spotify playlist"""
    try:
        url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        # Add in batches of 100
        successful = 0
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i:i+100]
            data = {'uris': batch}

            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 201:
                successful += len(batch)
            else:
                app.logger.error(f"Failed batch {i//100}: {response.text}")

            time.sleep(0.1)

        return True, f"Added {successful}/{len(track_uris)} tracks"

    except Exception as e:
        return False, f"Error: {str(e)}"

# ==================== TOKEN ENDPOINTS ====================

@app.route('/spotify/token', methods=['POST'])
def get_token_endpoint():
    """Get or refresh Spotify access token"""
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    grant_type = data.get('grant_type')

    if grant_type == 'authorization_code':
        # Exchange code for token
        code = data.get('code')
        redirect_uri = data.get('redirect_uri', SPOTIFY_REDIRECT_URI)

        if not code:
            return jsonify({"error": "Authorization code required"}), 400

        token_data = exchange_code_for_token(code, redirect_uri)
        if not token_data:
            return jsonify({"error": "Failed to exchange code for token"}), 400

        # Generate a token key (user ID from Spotify could be used here)
        token_key = secrets.token_hex(16)
        user_tokens[token_key] = token_data

        return jsonify({
            "access_token": token_data['access_token'],
            "token_type": token_data['token_type'],
            "expires_in": token_data.get('expires_in', 3600),
            "refresh_token": token_data.get('refresh_token'),
            "token_key": token_key  # Return key for future use
        })

    elif grant_type == 'refresh_token':
        # Refresh token
        refresh_token = data.get('refresh_token')
        token_key = data.get('token_key')

        if refresh_token:
            token_data = refresh_access_token(refresh_token)
        elif token_key and token_key in user_tokens:
            old_token = user_tokens[token_key]
            refresh_token = old_token.get('refresh_token')
            token_data = refresh_access_token(refresh_token) if refresh_token else None
        else:
            return jsonify({"error": "Refresh token or token_key required"}), 400

        if not token_data:
            return jsonify({"error": "Failed to refresh token"}), 400

        # Update stored token
        if token_key and token_key in user_tokens:
            if 'refresh_token' not in token_data:
                token_data['refresh_token'] = user_tokens[token_key].get('refresh_token')
            user_tokens[token_key] = token_data

        return jsonify({
            "access_token": token_data['access_token'],
            "token_type": token_data['token_type'],
            "expires_in": token_data.get('expires_in', 3600)
        })

    else:
        return jsonify({"error": "Invalid grant_type"}), 400

@app.route('/spotify/token/validate', methods=['POST'])
def validate_token():
    """Validate and get a working access token"""
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    token_key = data.get('token_key')
    access_token = data.get('access_token')

    if token_key:
        # Get token from stored tokens
        valid_token = get_valid_token(token_key)
        if valid_token:
            return jsonify({"access_token": valid_token, "source": "stored"})

    if access_token:
        # Validate provided token
        test_url = 'https://api.spotify.com/v1/me'
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(test_url, headers=headers)

        if response.status_code == 200:
            return jsonify({"access_token": access_token, "source": "provided", "valid": True})
        else:
            return jsonify({"error": "Invalid access token", "spotify_error": response.text}), 401

    return jsonify({"error": "token_key or access_token required"}), 400

# ==================== RECORDS API ENDPOINT (UPDATED WITH JOIN) ====================

@app.route('/records', methods=['GET'])
def get_records():
    """Get all records from database for streaming page"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Get query parameters
        limit = request.args.get('limit', default=100, type=int)
        offset = request.args.get('offset', default=0, type=int)

        # Query database - JOIN with genres table to get genre names
        cursor.execute('''
            SELECT r.id, r.artist, r.title, r.barcode, r.genre_id,
                   r.image_url, r.discogs_suggested_price, r.catalog_number,
                   r.format, r.condition, r.store_price, r.ebay_sell_at,
                   r.youtube_url, r.created_at, r.updated_at,
                   r.date_added, r.date_sold, r.compilation,
                   r.consignor_id, r.commission_rate,
                   COALESCE(g.genre_name, 'Unknown Genre') as genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.artist IS NOT NULL AND r.title IS NOT NULL
            AND r.artist != '' AND r.title != ''
            ORDER BY r.artist, r.title
            LIMIT ? OFFSET ?
        ''', (limit, offset))

        records = cursor.fetchall()
        conn.close()

        # Convert to list of dictionaries
        records_list = []
        for record in records:
            record_dict = dict(record)
            records_list.append(record_dict)

        return jsonify({
            'status': 'success',
            'count': len(records_list),
            'total': len(records_list),
            'records': records_list
        })

    except Exception as e:
        app.logger.error(f"Error in /records endpoint: {str(e)}")
        return jsonify({'error': str(e), 'status': 'error'}), 500


@app.route('/records/count', methods=['GET'])
def get_records_count():
    """Get count of records in database"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) as count
            FROM records
            WHERE artist IS NOT NULL AND title IS NOT NULL
            AND artist != '' AND title != ''
        ''')

        result = cursor.fetchone()
        conn.close()

        return jsonify({
            'status': 'success',
            'count': result['count']
        })

    except Exception as e:
        app.logger.error(f"Error getting record count: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== PLAYLIST SYNC ENDPOINT ====================

@app.route('/spotify/playlist/update', methods=['POST'])
def update_playlist_from_db():
    """Update Spotify playlist from database records"""
    app.logger.info("Starting playlist update from database...")

    data = request.get_json() or {}

    # Get token parameters
    token_key = data.get('token_key')
    access_token = data.get('access_token')
    code = data.get('code')
    redirect_uri = data.get('redirect_uri', SPOTIFY_REDIRECT_URI)

    # Optional: limit parameter
    limit = data.get('limit', 50)

    # Step 1: Get a valid access token
    valid_token = None

    if access_token:
        valid_token = access_token
        app.logger.info("Using provided access token")
    elif token_key:
        valid_token = get_valid_token(token_key)
        if valid_token:
            app.logger.info(f"Using stored token for key: {token_key}")
    elif code:
        app.logger.info("Exchanging code for token...")
        token_data = exchange_code_for_token(code, redirect_uri)
        if token_data:
            new_token_key = secrets.token_hex(16)
            user_tokens[new_token_key] = token_data
            valid_token = token_data['access_token']
            token_key = new_token_key
            app.logger.info(f"Got new token with key: {token_key}")

    if not valid_token:
        return jsonify({
            "error": "No valid access token",
            "instructions": "Provide either: access_token, token_key, or code",
            "auth_url": f"https://accounts.spotify.com/authorize?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope=playlist-modify-public%20playlist-modify-private"
        }), 401

    # Verify token works
    test_url = 'https://api.spotify.com/v1/me'
    headers = {'Authorization': f'Bearer {valid_token}'}
    test_response = requests.get(test_url, headers=headers)

    if test_response.status_code != 200:
        return jsonify({
            "error": "Invalid access token",
            "spotify_error": test_response.text
        }), 401

    try:
        # Get database records using same logic as /records endpoint
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT artist, title
            FROM records
            WHERE artist IS NOT NULL AND title IS NOT NULL
            AND artist != '' AND title != ''
            ORDER BY artist, title
            LIMIT ?
        ''', (limit,))

        records = cursor.fetchall()
        conn.close()

        total_records = len(records)
        app.logger.info(f"Found {total_records} records")

        if total_records == 0:
            return jsonify({"error": "No records found in database"}), 400

        # Step 2: Clear playlist
        app.logger.info("Clearing playlist...")
        clear_success, clear_msg = clear_spotify_playlist(YOUR_SPOTIFY_PLAYLIST_ID, valid_token)
        if not clear_success:
            return jsonify({"error": f"Failed to clear playlist: {clear_msg}"}), 500

        # Step 3: Search for tracks
        app.logger.info("Searching for tracks on Spotify...")
        found_tracks = []
        track_uris = []

        for i, record in enumerate(records):
            artist = record['artist']
            album = record['title']

            if i % 10 == 0:
                app.logger.info(f"Progress: {i}/{total_records}")

            track_info = search_spotify_album_track(artist, album, valid_token)

            if track_info:
                found_tracks.append({
                    'artist': artist,
                    'album': album,
                    'track': track_info['name'],
                    'spotify_uri': track_info['uri']
                })
                track_uris.append(track_info['uri'])

            time.sleep(0.2)  # Rate limiting

        app.logger.info(f"Found {len(found_tracks)} tracks on Spotify")

        if len(found_tracks) == 0:
            return jsonify({
                "error": "No tracks found on Spotify",
                "stats": {
                    "total_database_records": total_records,
                    "found_tracks": 0
                }
            }), 400

        # Step 4: Add tracks to playlist
        app.logger.info(f"Adding {len(track_uris)} tracks to playlist...")
        add_success, add_msg = add_tracks_to_playlist(YOUR_SPOTIFY_PLAYLIST_ID, track_uris, valid_token)

        if not add_success:
            return jsonify({"error": f"Failed to add tracks: {add_msg}"}), 500

        # Success response
        response_data = {
            "status": "success",
            "message": "Playlist updated successfully",
            "playlist_id": YOUR_SPOTIFY_PLAYLIST_ID,
            "playlist_url": f"https://open.spotify.com/playlist/{YOUR_SPOTIFY_PLAYLIST_ID}",
            "stats": {
                "total_database_records": total_records,
                "found_on_spotify": len(found_tracks),
                "added_to_playlist": len(track_uris)
            }
        }

        # Include token key if we created one
        if token_key:
            response_data['token_key'] = token_key

        # Include sample tracks
        response_data['sample_tracks'] = found_tracks[:10]

        app.logger.info("Playlist update complete!")
        return jsonify(response_data)

    except Exception as e:
        app.logger.error(f"Playlist update error: {str(e)}")
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

# ==================== HELPER ENDPOINTS ====================

@app.route('/spotify/auth/url', methods=['GET'])
def get_auth_url():
    """Get Spotify authorization URL"""
    params = {
        'client_id': SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'scope': 'playlist-modify-public playlist-modify-private',
        'state': secrets.token_hex(16)
    }

    auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"
    return jsonify({'auth_url': auth_url})

@app.route('/spotify/callback', methods=['GET'])
def callback():
    """Handle Spotify OAuth callback"""
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return jsonify({'error': error}), 400

    if not code:
        return jsonify({'error': 'No code provided'}), 400

    # Return the code for the user to use
    return f"""
    <html>
    <head><title>Spotify Authentication</title></head>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h1>✅ Authentication Successful</h1>
        <p>Your authorization code: <code>{code}</code></p>
        <p>You can now use this code to get an access token.</p>
        <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3>Example curl command:</h3>
            <pre style="background: white; padding: 10px; border-radius: 3px;">
curl -X POST https://arjanshaw.pythonanywhere.com/spotify/token \\
  -H "Content-Type: application/json" \\
  -d '{{
    "grant_type": "authorization_code",
    "code": "{code}",
    "redirect_uri": "https://arjanshaw.pythonanywhere.com/spotify/callback"
  }}'
            </pre>
        </div>
    </body>
    </html>
    """

@app.route('/spotify/playlist/status', methods=['GET'])
def get_playlist_status():
    """Get current playlist status"""
    try:
        # Get app token for reading
        auth_string = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
        auth_bytes = auth_string.encode('utf-8')
        auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')

        token_url = 'https://accounts.spotify.com/api/token'
        headers = {
            'Authorization': f'Basic {auth_base64}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {'grant_type': 'client_credentials'}

        response = requests.post(token_url, headers=headers, data=data)
        if response.status_code != 200:
            return jsonify({"error": "Failed to get app token"}), 500

        access_token = response.json()['access_token']

        # Get playlist info
        url = f'https://api.spotify.com/v1/playlists/{YOUR_SPOTIFY_PLAYLIST_ID}'
        headers = {'Authorization': f'Bearer {access_token}'}

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                "status": "success",
                "playlist": {
                    "name": data.get('name'),
                    "description": data.get('description'),
                    "tracks": data.get('tracks', {}).get('total', 0),
                    "public": data.get('public', False),
                    "url": data.get('external_urls', {}).get('spotify')
                }
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Failed to get playlist: {response.status_code}"
            }), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.logger.info("Starting PigStyle API with Spotify integration...")
    app.run(host='0.0.0.0', port=5000, debug=True)
else:
    app.logger.info("PigStyle API loaded")