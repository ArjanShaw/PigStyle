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

# Token storage
user_tokens = {}

def setup_logging():
    """Setup application logging"""
    logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    logging.basicConfig(level=logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)

    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'api.log'),
        maxBytes=1024 * 1024,
        backupCount=10
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))

    app.logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
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
        app.logger.debug(f"DEBUG: Exchanging code for token, redirect_uri: {redirect_uri}")
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
        app.logger.debug(f"DEBUG: Token exchange response status: {response.status_code}")

        if response.status_code == 200:
            token_data = response.json()
            token_data['expires_at'] = datetime.now().timestamp() + token_data.get('expires_in', 3600)
            app.logger.debug(f"DEBUG: Token exchange successful")
            return token_data
        else:
            app.logger.error(f"DEBUG: Token exchange failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        app.logger.error(f"DEBUG: Error exchanging token: {str(e)}")
        return None

def get_valid_token(token_key):
    """Get a valid access token, refreshing if necessary"""
    token_data = user_tokens.get(token_key)

    if not token_data:
        app.logger.debug(f"DEBUG: No token data for key: {token_key}")
        return None

    # Check if token is expired
    if datetime.now().timestamp() > token_data['expires_at']:
        app.logger.debug(f"DEBUG: Token expired, attempting refresh")
        refresh_token = token_data.get('refresh_token')
        if refresh_token:
            # Simple refresh - for now just return None to force re-auth
            app.logger.debug(f"DEBUG: Token needs refresh")
        return None

    app.logger.debug(f"DEBUG: Returning valid token for key: {token_key}")
    return token_data['access_token']

# ==================== SPOTIFY API FUNCTIONS ====================

def search_spotify_album_track(artist, album_title, access_token):
    """Search for an album on Spotify and return the MOST POPULAR track"""
    try:
        app.logger.debug(f"DEBUG: Searching Spotify for artist: {artist}, album: {album_title}")

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
        app.logger.debug(f"DEBUG: Spotify search response status: {response.status_code}")

        if response.status_code != 200:
            app.logger.debug(f"DEBUG: Spotify search failed with status: {response.status_code}")
            return None

        albums = response.json().get('albums', {}).get('items', [])
        app.logger.debug(f"DEBUG: Found {len(albums)} albums on Spotify")

        if not albums:
            app.logger.debug(f"DEBUG: No albums found for {artist} - {album_title}")
            return None

        # Get the first matching album
        album = albums[0]
        album_id = album['id']
        app.logger.debug(f"DEBUG: Selected album ID: {album_id}")

        # Get tracks from this album
        tracks_url = f'https://api.spotify.com/v1/albums/{album_id}/tracks?limit=50'
        tracks_response = requests.get(tracks_url, headers=headers)

        if tracks_response.status_code != 200:
            app.logger.debug(f"DEBUG: Failed to get album tracks: {tracks_response.status_code}")
            return None

        tracks = tracks_response.json().get('items', [])
        app.logger.debug(f"DEBUG: Found {len(tracks)} tracks in album")

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
            app.logger.debug(f"DEBUG: Found track: {most_popular_track['name']} (popularity: {most_popular_track.get('popularity', 0)})")
            return {
                'id': most_popular_track['id'],
                'name': most_popular_track['name'],
                'artists': [artist['name'] for artist in most_popular_track['artists']],
                'album': most_popular_track.get('album', {}).get('name', clean_album_title),
                'uri': most_popular_track['uri'],
                'popularity': most_popular_track.get('popularity', 0)
            }

        app.logger.debug(f"DEBUG: No suitable track found")
        return None

    except Exception as e:
        app.logger.error(f"DEBUG: Error searching album: {str(e)}")
        return None

def clear_spotify_playlist(playlist_id, access_token):
    """Clear all tracks from a Spotify playlist"""
    try:
        app.logger.debug(f"DEBUG: Clearing playlist: {playlist_id}")
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
            app.logger.debug(f"DEBUG: Get tracks response: {response.status_code}")

            if response.status_code != 200:
                return False, f"Failed to get playlist tracks: {response.status_code}"

            data = response.json()
            tracks = data.get('items', [])
            all_tracks.extend([{'uri': item['track']['uri']} for item in tracks])
            next_url = data.get('next')

        app.logger.debug(f"DEBUG: Found {len(all_tracks)} tracks to clear")

        if not all_tracks:
            return True, "Playlist is already empty"

        # Remove all tracks
        remove_url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
        remove_data = {'tracks': all_tracks}

        response = requests.delete(remove_url, headers=headers, json=remove_data)
        app.logger.debug(f"DEBUG: Clear response: {response.status_code}")

        if response.status_code == 200:
            return True, f"Cleared {len(all_tracks)} tracks"
        else:
            return False, f"Failed to clear: {response.status_code} - {response.text}"

    except Exception as e:
        app.logger.error(f"DEBUG: Error clearing playlist: {str(e)}")
        return False, f"Error: {str(e)}"

def add_tracks_to_playlist(playlist_id, track_uris, access_token):
    """Add tracks to a Spotify playlist"""
    try:
        app.logger.debug(f"DEBUG: Adding {len(track_uris)} tracks to playlist: {playlist_id}")
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
            app.logger.debug(f"DEBUG: Batch {i//100} add response: {response.status_code}")

            if response.status_code == 201:
                successful += len(batch)
                app.logger.debug(f"DEBUG: Batch {i//100} successful, added {len(batch)} tracks")
            else:
                app.logger.error(f"DEBUG: Failed batch {i//100}: {response.text}")

            time.sleep(0.1)

        app.logger.debug(f"DEBUG: Total successful: {successful}/{len(track_uris)}")
        return True, f"Added {successful}/{len(track_uris)} tracks"

    except Exception as e:
        app.logger.error(f"DEBUG: Error adding tracks: {str(e)}")
        return False, f"Error: {str(e)}"

def create_or_get_genre_playlist(genre_name, access_token):
    """Create a new playlist for a genre or get existing one - WITH DEBUG"""
    try:
        app.logger.debug(f"DEBUG: Creating/getting playlist for genre: {genre_name}")

        # Clean genre name for playlist naming
        clean_genre = re.sub(r'[^\w\s-]', '', genre_name).strip()
        if not clean_genre:
            clean_genre = "Miscellaneous"

        playlist_name = f"PigStyle: {clean_genre}"
        playlist_description = f"Vinyl records from PigStyle Records - Genre: {genre_name}"

        app.logger.debug(f"DEBUG: Playlist name: {playlist_name}")

        # First, get current user ID
        user_url = 'https://api.spotify.com/v1/me'
        headers = {'Authorization': f'Bearer {access_token}'}

        user_response = requests.get(user_url, headers=headers)
        app.logger.debug(f"DEBUG: Get user response: {user_response.status_code}")

        if user_response.status_code != 200:
            app.logger.error(f"DEBUG: Failed to get user info: {user_response.status_code}")
            return None

        user_id = user_response.json()['id']
        app.logger.debug(f"DEBUG: Got user ID: {user_id}")

        # Get user's playlists to check for existing
        playlists_url = f'https://api.spotify.com/v1/users/{user_id}/playlists?limit=50'
        playlists_response = requests.get(playlists_url, headers=headers)
        app.logger.debug(f"DEBUG: Get playlists response: {playlists_response.status_code}")

        if playlists_response.status_code == 200:
            playlists = playlists_response.json().get('items', [])
            app.logger.debug(f"DEBUG: Found {len(playlists)} playlists")

            for playlist in playlists:
                if playlist['name'] == playlist_name:
                    app.logger.debug(f"DEBUG: Found existing playlist: {playlist['id']}")
                    return playlist['id']

        # Create new playlist if not found
        app.logger.debug(f"DEBUG: Creating new playlist: {playlist_name}")
        create_url = f'https://api.spotify.com/v1/users/{user_id}/playlists'
        playlist_data = {
            'name': playlist_name,
            'description': playlist_description,
            'public': True
        }

        create_response = requests.post(create_url, headers=headers, json=playlist_data)
        app.logger.debug(f"DEBUG: Create playlist response: {create_response.status_code}")

        if create_response.status_code == 201:
            new_playlist = create_response.json()
            app.logger.debug(f"DEBUG: Created new playlist: {new_playlist['id']}")
            return new_playlist['id']
        else:
            app.logger.error(f"DEBUG: Failed to create playlist: {create_response.status_code} - {create_response.text}")
            return None

    except Exception as e:
        app.logger.error(f"DEBUG: Error creating/getting genre playlist: {str(e)}")
        return None

# ==================== INTERNAL AUTHORIZATION ENDPOINT ====================

@app.route('/spotify/authorize-and-update', methods=['GET'])
def authorize_and_update():
    """Internal endpoint that handles auth and playlist update in one call"""
    app.logger.debug("DEBUG: Starting authorize_and_update endpoint")

    # Get parameters
    limit = request.args.get('limit', default=20, type=int)
    state = secrets.token_hex(16)

    # Store in session for callback
    session['spotify_state'] = state
    session['spotify_limit'] = limit
    session['spotify_return_url'] = request.args.get('return_url', 'https://pigstylemusic.com')

    app.logger.debug(f"DEBUG: Generated state: {state}, limit: {limit}")

    # Build authorization URL
    params = {
        'client_id': SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': 'https://arjanshaw.pythonanywhere.com/spotify/callback',
        'scope': 'playlist-modify-public playlist-modify-private',
        'state': state,
        'show_dialog': 'false'
    }

    auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(params)}"
    app.logger.debug(f"DEBUG: Redirecting to auth URL")

    return redirect(auth_url)

@app.route('/spotify/callback', methods=['GET'])
def authorize_callback():
    """Callback for internal authorization"""
    app.logger.debug("DEBUG: Starting authorize_callback")

    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    app.logger.debug(f"DEBUG: Callback params - code: {'yes' if code else 'no'}, state: {state}, error: {error}")

    if error:
        app.logger.error(f"DEBUG: Spotify auth error: {error}")
        return jsonify({'error': error}), 400

    if not code:
        app.logger.error("DEBUG: No code provided")
        return jsonify({'error': 'No code provided'}), 400

    # Verify state
    if state != session.get('spotify_state'):
        app.logger.error(f"DEBUG: State mismatch: {state} != {session.get('spotify_state')}")
        return jsonify({'error': 'State mismatch'}), 400

    limit = session.get('spotify_limit', 20)
    return_url = session.get('spotify_return_url', 'https://pigstylemusic.com')

    app.logger.debug(f"DEBUG: Proceeding with limit: {limit}")

    try:
        # Exchange code for token
        app.logger.debug("DEBUG: Exchanging code for token")
        token_data = exchange_code_for_token(code, 'https://arjanshaw.pythonanywhere.com/spotify/callback')

        if not token_data:
            app.logger.error("DEBUG: Token exchange failed")
            return jsonify({"error": "Failed to exchange code for token"}), 400

        access_token = token_data['access_token']
        app.logger.debug("DEBUG: Got access token")

        # Store token for later use
        token_key = secrets.token_hex(16)
        user_tokens[token_key] = token_data

        # Get database records GROUPED BY GENRE
        app.logger.debug("DEBUG: Getting records from database")
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT r.artist, r.title, r.genre_id,
                   COALESCE(g.genre_name, 'Miscellaneous') as genre_name
            FROM records r
            LEFT JOIN genres g ON r.genre_id = g.id
            WHERE r.artist IS NOT NULL AND r.title IS NOT NULL
            AND r.artist != '' AND r.title != ''
            ORDER BY genre_name, r.artist, r.title
        ''')

        records = cursor.fetchall()
        conn.close()

        app.logger.debug(f"DEBUG: Found {len(records)} total records")

        if len(records) == 0:
            app.logger.error("DEBUG: No records found")
            return jsonify({"error": "No records found in database"}), 400

        # Group records by genre
        genre_groups = {}
        for record in records:
            genre_name = record['genre_name']
            if genre_name not in genre_groups:
                genre_groups[genre_name] = []
            genre_groups[genre_name].append(record)

        app.logger.debug(f"DEBUG: Grouped into {len(genre_groups)} genres: {list(genre_groups.keys())}")

        results = {}
        all_tracks_added = 0

        # Process each genre
        for genre_name, genre_records in genre_groups.items():
            app.logger.debug(f"DEBUG: Processing genre: {genre_name} ({len(genre_records)} records)")

            # Create or get playlist for this genre
            playlist_id = create_or_get_genre_playlist(genre_name, access_token)

            if not playlist_id:
                app.logger.error(f"DEBUG: Failed to get playlist for genre: {genre_name}")
                results[genre_name] = {"error": "Failed to create/get playlist"}
                continue

            # Clear existing tracks
            app.logger.debug(f"DEBUG: Clearing playlist for {genre_name}")
            clear_success, clear_msg = clear_spotify_playlist(playlist_id, access_token)

            if not clear_success:
                app.logger.error(f"DEBUG: Failed to clear playlist: {clear_msg}")
                results[genre_name] = {"error": f"Failed to clear: {clear_msg}"}
                continue

            # Search for tracks
            genre_tracks = []
            genre_track_uris = []

            app.logger.debug(f"DEBUG: Searching for {len(genre_records)} tracks in genre {genre_name}")
            for i, record in enumerate(genre_records):
                artist = record['artist']
                album = record['title']

                track_info = search_spotify_album_track(artist, album, access_token)

                if track_info:
                    genre_tracks.append({
                        'artist': artist,
                        'album': album,
                        'track': track_info['name'],
                        'uri': track_info['uri']
                    })
                    genre_track_uris.append(track_info['uri'])
                    app.logger.debug(f"DEBUG: Found track: {track_info['name']}")

                time.sleep(0.2)  # Rate limiting

            app.logger.debug(f"DEBUG: Found {len(genre_tracks)} tracks for genre {genre_name}")

            # Add tracks to playlist
            if genre_track_uris:
                app.logger.debug(f"DEBUG: Adding {len(genre_track_uris)} tracks to {genre_name} playlist")
                add_success, add_msg = add_tracks_to_playlist(playlist_id, genre_track_uris, access_token)

                if add_success:
                    results[genre_name] = {
                        'playlist_id': playlist_id,
                        'playlist_url': f"https://open.spotify.com/playlist/{playlist_id}",
                        'tracks_added': len(genre_track_uris),
                        'total_records': len(genre_records),
                        'sample_tracks': genre_tracks[:5]
                    }
                    all_tracks_added += len(genre_track_uris)
                    app.logger.debug(f"DEBUG: Successfully added tracks to {genre_name} playlist")
                else:
                    results[genre_name] = {"error": add_msg}
                    app.logger.error(f"DEBUG: Failed to add tracks: {add_msg}")
            else:
                results[genre_name] = {"error": "No tracks found on Spotify"}
                app.logger.warning(f"DEBUG: No tracks found for genre {genre_name}")

        # Prepare success response
        app.logger.debug(f"DEBUG: Processed all genres. Total tracks added: {all_tracks_added}")

        if all_tracks_added == 0:
            return jsonify({
                "error": "No tracks could be added to any playlists",
                "genre_results": results,
                "total_records": len(records),
                "genres_processed": len(genre_groups)
            }), 400

        # Redirect back to original site with success message
        success_data = {
            "status": "success",
            "message": f"Added {all_tracks_added} tracks across {len(results)} genre playlists",
            "genre_results": results,
            "token_key": token_key,
            "total_records": len(records),
            "genres_processed": len(genre_groups)
        }

        # Encode the success data for URL
        encoded_data = urllib.parse.quote(json.dumps(success_data))

        app.logger.debug(f"DEBUG: Redirecting to: {return_url}")
        return redirect(f"{return_url}?spotify_success={encoded_data}")

    except Exception as e:
        app.logger.error(f"DEBUG: Error in authorize_callback: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

# ==================== EXISTING ENDPOINTS (KEPT AS IS) ====================

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

if __name__ == '__main__':
    app.logger.info("Starting PigStyle API with Spotify integration...")
    app.run(host='0.0.0.0', port=5000, debug=True)
else:
    app.logger.info("PigStyle API loaded")