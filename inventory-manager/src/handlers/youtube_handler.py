import streamlit as st
import requests
import re
import time
import os  # ADD THIS IMPORT
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class YouTubeHandler:
    def __init__(self, debug_tab=None, api_key=None):
        self.debug_tab = debug_tab
        self.api_key = api_key or st.secrets.get('YOUTUBE_API_KEY') or os.getenv('YOUTUBE_API_KEY')
        
    def search_youtube_videos(self, search_query, record_data):
        """Search YouTube for videos matching the artist and title using real API"""
        if not self.api_key:
            st.error("YouTube API key not configured. Please set YOUTUBE_API_KEY in your environment variables or Streamlit secrets.")
            return []
            
        try:
            # Log the API call
            api_title = f"🎵 YouTube Search API: {search_query}"
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
                videoEmbeddable='true'  # Only get embeddable videos
            )
            
            response = request.execute()
            
            # Process real results
            real_results = []
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                snippet = item['snippet']
                real_results.append({
                    'title': snippet['title'],
                    'channel': snippet['channelTitle'],
                    'thumbnail': snippet['thumbnails']['default']['url'],
                    'url': f"https://www.youtube.com/watch?v={video_id}"
                })
            
            duration = round(time.time() - start_time, 2)
            
            # Log the real response
            self._log_api_response(api_title, {
                'status_code': 200,
                'results_count': len(real_results),
                'results_sample': real_results[:3] if real_results else []  # Log first 3 to avoid huge logs
            }, duration)
            
            return real_results
            
        except HttpError as e:
            duration = round(time.time() - start_time, 2)
            error_msg = f"YouTube API error: {e.resp.status} - {e._get_reason()}"
            self._log_api_response(api_title, {
                'status_code': e.resp.status,
                'error': error_msg
            }, duration)
            st.error(f"YouTube API error: {e._get_reason()}")
            return []
            
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            error_msg = f"YouTube search failed: {str(e)}"
            self._log_api_response(api_title, {
                'status_code': 'Unknown',
                'error': error_msg
            }, duration)
            st.error(f"YouTube search failed: {str(e)}")
            return []

    def extract_youtube_id(self, url):
        """Extract YouTube video ID from URL"""
        try:
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
        except:
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