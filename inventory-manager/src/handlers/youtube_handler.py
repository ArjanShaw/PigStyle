import streamlit as st
import requests
import re
import time
import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class YouTubeHandler:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        self.enabled = bool(self.api_key)
        
    def search_youtube_videos(self, search_query, record_data, track_titles=None):
        """Search YouTube for videos matching track titles from the record"""
        if not self.enabled:
            st.error("🎵 YouTube API key not configured. Please set YOUTUBE_API_KEY in your environment variables.")
            return []
            
        if track_titles and len(track_titles) > 0:
            # Search for individual tracks from the record
            return self._search_track_videos(record_data, track_titles)
        else:
            # Fallback to album search
            return self._search_album_videos(search_query, record_data)

    def _search_track_videos(self, record_data, track_titles):
        """Search YouTube for individual track videos"""
        artist = record_data.get('artist', '')
        all_results = []
        
        # Limit to first 5 tracks to avoid too many API calls
        tracks_to_search = track_titles[:5]
        
        for track_title in tracks_to_search:
            track_query = f"{artist} {track_title}"
            
            # Log the API call
            api_title = f"🎵 YouTube Track Search API: {track_query}"
            start_time = time.time()
            self._log_api_call(api_title, {
                'endpoint': 'https://www.googleapis.com/youtube/v3/search',
                'request': {
                    'search_query': track_query,
                    'artist': artist,
                    'track_title': track_title,
                    'maxResults': 5
                }
            })
            
            try:
                youtube = build('youtube', 'v3', developerKey=self.api_key)
                request = youtube.search().list(
                    q=track_query,
                    part='snippet',
                    type='video',
                    maxResults=5,
                    videoEmbeddable='true',
                    videoDuration='short',
                    order='relevance'
                )
                
                response = request.execute()
                track_results = self._process_track_results(response, track_title, artist)
                all_results.extend(track_results)
                
                duration = round(time.time() - start_time, 2)
                self._log_api_response(api_title, {
                    'status_code': 200,
                    'track': track_title,
                    'results_count': len(track_results),
                    'results_sample': track_results[:2] if track_results else []
                }, duration)
                
            except Exception as e:
                duration = round(time.time() - start_time, 2)
                self._log_api_response(api_title, {
                    'status_code': 'Error',
                    'error': str(e),
                    'track': track_title
                }, duration)
        
        # Remove duplicates by video URL
        unique_results = []
        seen_urls = set()
        for result in all_results:
            if result['url'] not in seen_urls:
                seen_urls.add(result['url'])
                unique_results.append(result)
        
        return unique_results

    def _search_album_videos(self, search_query, record_data):
        """Fallback: Search YouTube for album videos (original behavior)"""
        # Log the API call
        api_title = f"🎵 YouTube Album Search API: {search_query}"
        start_time = time.time()
        self._log_api_call(api_title, {
            'endpoint': 'https://www.googleapis.com/youtube/v3/search',
            'request': {
                'search_query': search_query,
                'artist': record_data.get('artist'),
                'title': record_data.get('title'),
                'maxResults': 10
            }
        })
        
        # Build YouTube service and make real API call
        youtube = build('youtube', 'v3', developerKey=self.api_key)
        
        request = youtube.search().list(
            q=search_query,
            part='snippet',
            type='video',
            maxResults=10,
            videoEmbeddable='true',
            videoDuration='short',
            order='relevance'
        )
        
        response = request.execute()
        
        # Process results
        results = []
        for item in response.get('items', []):
            video_id = item['id']['videoId']
            snippet = item['snippet']
            results.append({
                'title': snippet['title'],
                'channel': snippet['channelTitle'],
                'thumbnail': snippet['thumbnails']['default']['url'],
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'type': 'album'
            })
        
        duration = round(time.time() - start_time, 2)
        
        # Log the response
        self._log_api_response(api_title, {
            'status_code': 200,
            'results_count': len(results),
            'results_sample': results[:3] if results else []
        }, duration)
        
        return results

    def _process_track_results(self, response, track_title, artist):
        """Process YouTube search results and filter for track matches"""
        results = []
        
        for item in response.get('items', []):
            video_id = item['id']['videoId']
            snippet = item['snippet']
            video_title = snippet['title']
            
            # Check if video title contains the track title (case insensitive)
            if self._is_track_match(video_title, track_title, artist):
                results.append({
                    'title': snippet['title'],
                    'channel': snippet['channelTitle'],
                    'thumbnail': snippet['thumbnails']['default']['url'],
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'type': 'track',
                    'track_title': track_title
                })
        
        return results

    def _is_track_match(self, video_title, track_title, artist):
        """Check if video title matches the track title"""
        # Convert to lowercase for case-insensitive matching
        video_lower = video_title.lower()
        track_lower = track_title.lower()
        artist_lower = artist.lower()
        
        # Remove common prefixes and suffixes
        clean_track = self._clean_track_title(track_lower)
        clean_video = self._clean_video_title(video_lower)
        
        # Check if clean track title appears in clean video title
        if clean_track in clean_video:
            return True
        
        # Check if track title appears in video title (with some tolerance)
        if track_lower in video_lower:
            return True
            
        # Check for common variations
        variations = [
            track_lower,
            track_lower.replace('(', '').replace(')', ''),
            track_lower.replace('-', ' '),
            track_lower.replace("'", '')
        ]
        
        for variation in variations:
            if variation and len(variation) > 3 and variation in video_lower:
                return True
        
        return False

    def _clean_track_title(self, track_title):
        """Clean track title for matching"""
        # Remove common prefixes and suffixes
        removals = [
            'track',
            'song',
            'music',
            'video',
            'official',
            'lyrics',
            'hd',
            '4k',
            'live',
            'performance',
            'cover'
        ]
        
        cleaned = track_title
        for removal in removals:
            cleaned = cleaned.replace(removal, '')
        
        # Remove extra spaces and trim
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _clean_video_title(self, video_title):
        """Clean video title for matching"""
        # Remove common YouTube prefixes/suffixes
        patterns = [
            r'\[.*?\]',
            r'\(.*?\)',
            r'\b(?:official|video|music|lyrics|hd|4k|live|performance|cover)\b',
            r'\s+'
        ]
        
        cleaned = video_title
        for pattern in patterns:
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
        
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def extract_youtube_id(self, url):
        """Extract YouTube video ID from URL"""
        # Handle various YouTube URL formats
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?]+)',
            r'youtube\.com\/embed\/([^&\n?]+)',
            r'youtube\.com\/v\/([^&\n?]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _log_api_call(self, title, request_data):
        """Log API call in unified format"""
        if 'api_logs' not in st.session_state:
            st.session_state.api_logs = []
        if 'api_details' not in st.session_state:
            st.session_state.api_details = {}
            
        st.session_state.api_logs.append(title)
        st.session_state.api_details[title] = {'request': request_data}

    def _log_api_response(self, title, response_data, duration):
        """Log API response in unified format"""
        if 'api_details' in st.session_state and title in st.session_state.api_details:
            st.session_state.api_details[title]['response'] = response_data
            st.session_state.api_details[title]['duration'] = duration

    def is_enabled(self):
        """Check if YouTube handler is enabled"""
        return self.enabled