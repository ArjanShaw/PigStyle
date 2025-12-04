from app import app, get_db
from flask import jsonify, request
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from collections import defaultdict
import time

# Spotify configuration
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://localhost:5000/callback')
SPOTIFY_USER_ID = os.environ.get('SPOTIFY_USER_ID')

def get_spotify_client():
    """Get authenticated Spotify client"""
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope='playlist-modify-public playlist-modify-private',
            cache_path='.spotify_cache'
        ))
        return sp
    except Exception as e:
        print(f"Spotify auth error: {e}")
        raise

def search_spotify_track(sp, artist, title, max_retries=3):
    """Search for a track on Spotify with retry logic"""
    search_query = f"{artist} {title}"
    
    for attempt in range(max_retries):
        try:
            results = sp.search(q=search_query, type='track', limit=5)
            
            if results['tracks']['items']:
                # Return first match
                track = results['tracks']['items'][0]
                return {
                    'uri': track['uri'],
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'album': track['album']['name'],
                    'duration_ms': track['duration_ms']
                }
            else:
                # Try with just artist name
                results = sp.search(q=artist, type='track', limit=5)
                if results['tracks']['items']:
                    track = results['tracks']['items'][0]
                    return {
                        'uri': track['uri'],
                        'name': track['name'],
                        'artist': track['artists'][0]['name'],
                        'album': track['album']['name'],
                        'duration_ms': track['duration_ms']
                    }
                return None
                
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"Failed to search for {artist} - {title}: {e}")
                return None

@app.route('/spotify/genre-playlists/create-all', methods=['POST'])
def create_all_genre_playlists():
    """Create or update Spotify playlists for all genres"""
    try:
        data = request.get_json() or {}
        update_existing = data.get('update_existing', True)
        dry_run = data.get('dry_run', False)
        max_tracks_per_playlist = data.get('max_tracks', 100)
        
        # Get all genres with their records
        conn = get_db()
        cursor = conn.cursor()
        
        # Get genres with record counts
        cursor.execute('''
            SELECT g.id, g.genre_name, COUNT(r.id) as record_count
            FROM genres g
            LEFT JOIN records r ON g.id = r.genre_id
            WHERE r.artist IS NOT NULL AND r.artist != ''
            GROUP BY g.id, g.genre_name
            HAVING record_count > 0
            ORDER BY g.genre_name
        ''')
        
        genres = cursor.fetchall()
        
        genre_data = {}
        for genre in genres:
            # Get records for this genre
            cursor.execute('''
                SELECT DISTINCT r.artist, r.title
                FROM records r
                WHERE r.genre_id = ? 
                AND r.artist IS NOT NULL 
                AND r.artist != ''
                ORDER BY r.artist, r.title
                LIMIT ?
            ''', (genre['id'], max_tracks_per_playlist))
            
            records = cursor.fetchall()
            genre_data[genre['genre_name']] = {
                'genre_id': genre['id'],
                'records': [dict(record) for record in records],
                'count': len(records)
            }
        
        conn.close()
        
        if dry_run:
            return jsonify({
                'status': 'success',
                'dry_run': True,
                'genres_found': len(genres),
                'genre_data': genre_data
            })
        
        # Initialize Spotify client
        sp = get_spotify_client()
        user_id = sp.current_user()['id']
        
        # Get existing playlists
        existing_playlists = {}
        offset = 0
        limit = 50
        
        while True:
            playlists = sp.current_user_playlists(limit=limit, offset=offset)
            for playlist in playlists['items']:
                existing_playlists[playlist['name']] = playlist['id']
            
            if len(playlists['items']) < limit:
                break
            offset += limit
        
        results = {
            'created': [],
            'updated': [],
            'failed': [],
            'total_tracks_found': 0,
            'total_tracks_added': 0
        }
        
        # Process each genre
        for genre_name, genre_info in genre_data.items():
            try:
                playlist_name = f"PigStyle: {genre_name}"
                track_uris = []
                found_tracks = 0
                
                # Search for tracks on Spotify
                for record in genre_info['records']:
                    track = search_spotify_track(sp, record['artist'], record['title'])
                    if track:
                        track_uris.append(track['uri'])
                        found_tracks += 1
                
                if not track_uris:
                    results['failed'].append({
                        'genre': genre_name,
                        'error': 'No tracks found on Spotify'
                    })
                    continue
                
                results['total_tracks_found'] += found_tracks
                
                if playlist_name in existing_playlists and update_existing:
                    # Update existing playlist
                    playlist_id = existing_playlists[playlist_name]
                    
                    # Clear existing tracks
                    sp.playlist_replace_items(playlist_id, [])
                    
                    # Add new tracks (Spotify API limit: 100 tracks per request)
                    for i in range(0, len(track_uris), 100):
                        batch = track_uris[i:i+100]
                        sp.playlist_add_items(playlist_id, batch)
                    
                    results['updated'].append({
                        'genre': genre_name,
                        'playlist_id': playlist_id,
                        'tracks_added': len(track_uris),
                        'playlist_url': f"https://open.spotify.com/playlist/{playlist_id}"
                    })
                    results['total_tracks_added'] += len(track_uris)
                    
                else:
                    # Create new playlist
                    playlist = sp.user_playlist_create(
                        user=user_id,
                        name=playlist_name,
                        description=f"Records from PigStyle inventory - Genre: {genre_name}",
                        public=True
                    )
                    
                    playlist_id = playlist['id']
                    
                    # Add tracks (Spotify API limit: 100 tracks per request)
                    for i in range(0, len(track_uris), 100):
                        batch = track_uris[i:i+100]
                        sp.playlist_add_items(playlist_id, batch)
                    
                    results['created'].append({
                        'genre': genre_name,
                        'playlist_id': playlist_id,
                        'tracks_added': len(track_uris),
                        'playlist_url': f"https://open.spotify.com/playlist/{playlist_id}"
                    })
                    results['total_tracks_added'] += len(track_uris)
                    
            except Exception as e:
                results['failed'].append({
                    'genre': genre_name,
                    'error': str(e)
                })
        
        return jsonify({
            'status': 'success',
            'results': results,
            'summary': {
                'genres_processed': len(genre_data),
                'playlists_created': len(results['created']),
                'playlists_updated': len(results['updated']),
                'playlists_failed': len(results['failed']),
                'total_tracks_found': results['total_tracks_found'],
                'total_tracks_added': results['total_tracks_added']
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/spotify/genre-playlists/<genre_name>', methods=['POST'])
def create_genre_playlist(genre_name):
    """Create or update a Spotify playlist for a specific genre"""
    try:
        data = request.get_json() or {}
        update_existing = data.get('update_existing', True)
        max_tracks = data.get('max_tracks', 100)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get genre ID
        cursor.execute('SELECT id FROM genres WHERE genre_name = ?', (genre_name,))
        genre = cursor.fetchone()
        
        if not genre:
            conn.close()
            return jsonify({'error': f'Genre "{genre_name}" not found'}), 404
        
        genre_id = genre['id']
        
        # Get records for this genre
        cursor.execute('''
            SELECT DISTINCT r.artist, r.title
            FROM records r
            WHERE r.genre_id = ? 
            AND r.artist IS NOT NULL 
            AND r.artist != ''
            ORDER BY r.artist, r.title
            LIMIT ?
        ''', (genre_id, max_tracks))
        
        records = cursor.fetchall()
        conn.close()
        
        if not records:
            return jsonify({'error': f'No records found for genre "{genre_name}"'}), 404
        
        # Initialize Spotify client
        sp = get_spotify_client()
        user_id = sp.current_user()['id']
        
        # Search for tracks on Spotify
        track_uris = []
        track_details = []
        
        for record in records:
            track = search_spotify_track(sp, record['artist'], record['title'])
            if track:
                track_uris.append(track['uri'])
                track_details.append({
                    'original_artist': record['artist'],
                    'original_title': record['title'],
                    'spotify_artist': track['artist'],
                    'spotify_title': track['name'],
                    'spotify_album': track['album']
                })
        
        if not track_uris:
            return jsonify({
                'status': 'error',
                'message': f'No tracks found on Spotify for genre "{genre_name}"',
                'records_searched': len(records)
            }), 404
        
        playlist_name = f"PigStyle: {genre_name}"
        
        # Check if playlist already exists
        existing_playlist_id = None
        offset = 0
        limit = 50
        
        while True:
            playlists = sp.current_user_playlists(limit=limit, offset=offset)
            for playlist in playlists['items']:
                if playlist['name'] == playlist_name:
                    existing_playlist_id = playlist['id']
                    break
            
            if existing_playlist_id or len(playlists['items']) < limit:
                break
            offset += limit
        
        if existing_playlist_id and update_existing:
            # Update existing playlist
            # Clear existing tracks
            sp.playlist_replace_items(existing_playlist_id, [])
            
            # Add new tracks
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i:i+100]
                sp.playlist_add_items(existing_playlist_id, batch)
            
            playlist_id = existing_playlist_id
            action = 'updated'
            
        else:
            # Create new playlist
            playlist = sp.user_playlist_create(
                user=user_id,
                name=playlist_name,
                description=f"Records from PigStyle inventory - Genre: {genre_name}",
                public=True
            )
            
            playlist_id = playlist['id']
            
            # Add tracks
            for i in range(0, len(track_uris), 100):
                batch = track_uris[i:i+100]
                sp.playlist_add_items(playlist_id, batch)
            
            action = 'created'
        
        return jsonify({
            'status': 'success',
            'action': action,
            'genre': genre_name,
            'playlist_id': playlist_id,
            'playlist_url': f"https://open.spotify.com/playlist/{playlist_id}",
            'stats': {
                'records_in_database': len(records),
                'tracks_found_on_spotify': len(track_uris),
                'success_rate': f"{(len(track_uris) / len(records)) * 100:.1f}%"
            },
            'tracks': track_details
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/spotify/playlists', methods=['GET'])
def get_spotify_playlists():
    """Get all Spotify playlists for the authenticated user"""
    try:
        sp = get_spotify_client()
        
        playlists = []
        offset = 0
        limit = 50
        
        while True:
            response = sp.current_user_playlists(limit=limit, offset=offset)
            for playlist in response['items']:
                playlists.append({
                    'id': playlist['id'],
                    'name': playlist['name'],
                    'description': playlist.get('description', ''),
                    'tracks_total': playlist['tracks']['total'],
                    'owner': playlist['owner']['display_name'],
                    'public': playlist['public'],
                    'url': playlist['external_urls']['spotify']
                })
            
            if len(response['items']) < limit:
                break
            offset += limit
        
        return jsonify({
            'status': 'success',
            'playlists': playlists,
            'total': len(playlists)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500