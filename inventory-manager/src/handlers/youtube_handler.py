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
        self.quota_exceeded = False
        
    def search_youtube_videos(self, search_query, record_data, track_titles=None):
        """Search YouTube for videos matching track titles from the record"""
        if not self.enabled:
            st.error("🎵 YouTube API key not configured. Please set YOUTUBE_API_KEY in your environment variables.")
            return []
        
        if self.quota_exceeded:
            st.warning("🎵 YouTube API quota exceeded. YouTube search is temporarily disabled.")
            return []
            
        # Always search for the album first, then filter results
        return self._search_album_and_filter_tracks(search_query, record_data, track_titles)

    def _search_album_and_filter_tracks(self, search_query, record_data, track_titles):
        """Search once for the album and filter results to match track titles"""
        artist = record_data.get('artist', '')
        album_title = record_data.get('title', '')
        
        # Log the API call
        api_title = f"🎵 YouTube Album Search API: {search_query}"
        start_time = time.time()
        self._log_api_call(api_title, {
            'endpoint': 'https://www.googleapis.com/youtube/v3/search',
            'request': {
                'search_query': search_query,
                'artist': artist,
                'album_title': album_title,
                'track_titles_count': len(track_titles) if track_titles else 0,
                'maxResults': 20  # Get more results to filter through
            }
        })
        
        try:
            youtube = build('youtube', 'v3', developerKey=self.api_key)
            request = youtube.search().list(
                q=search_query,
                part='snippet',
                type='video',
                maxResults=20,  # Get more results to find matching tracks
                videoEmbeddable='true'
            )
            
            response = request.execute()
            
            # Process all results and categorize them
            all_results = self._process_youtube_results(response, track_titles, artist, album_title)
            
            duration = round(time.time() - start_time, 2)
            
            # Log the response
            self._log_api_response(api_title, {
                'status_code': 200,
                'results_count': len(all_results),
                'track_matches': len([r for r in all_results if r.get('type') == 'track']),
                'album_matches': len([r for r in all_results if r.get('type') == 'album'])
            }, duration)
            
            return all_results
            
        except HttpError as e:
            duration = round(time.time() - start_time, 2)
            if e.resp.status == 403 and 'quotaExceeded' in str(e):
                self.quota_exceeded = True
                self._log_api_response(api_title, {
                    'status_code': 403,
                    'error': 'YouTube API quota exceeded'
                }, duration)
                st.error("🎵 YouTube API quota exceeded. Please try again tomorrow.")
                return []
            else:
                self._log_api_response(api_title, {
                    'status_code': e.resp.status,
                    'error': str(e)
                }, duration)
                st.error(f"🎵 YouTube API error: {e}")
                return []
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            self._log_api_response(api_title, {
                'status_code': 'Error',
                'error': str(e)
            }, duration)
            st.error(f"🎵 YouTube search error: {e}")
            return []

    def _process_youtube_results(self, response, track_titles, artist, album_title):
        """Process YouTube search results and categorize them by track matches"""
        track_results = []
        album_results = []
        
        for item in response.get('items', []):
            video_id = item['id']['videoId']
            snippet = item['snippet']
            video_title = snippet['title']
            
            video_data = {
                'title': snippet['title'],
                'channel': snippet['channelTitle'],
                'thumbnail': snippet['thumbnails']['default']['url'],
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'video_id': video_id
            }
            
            # Check if this video matches any track title
            matched_track = self._find_matching_track(video_title, track_titles, artist)
            if matched_track:
                video_data['type'] = 'track'
                video_data['track_title'] = matched_track
                track_results.append(video_data)
            else:
                # Check if it's likely album content
                if self._is_album_content(video_title, album_title, artist):
                    video_data['type'] = 'album'
                    album_results.append(video_data)
                else:
                    video_data['type'] = 'other'
                    album_results.append(video_data)
        
        # Return track matches first, then album content
        return track_results + album_results

    def _find_matching_track(self, video_title, track_titles, artist):
        """Find if video title matches any track title from the record"""
        if not track_titles:
            return None
            
        video_lower = video_title.lower()
        artist_lower = artist.lower()
        
        for track_title in track_titles:
            track_lower = track_title.lower()
            
            # Clean both titles for better matching
            clean_video = self._clean_video_title(video_lower)
            clean_track = self._clean_track_title(track_lower)
            
            # Check various matching strategies
            if self._is_track_match(clean_video, clean_track, artist_lower):
                return track_title
                
        return None

    def _is_track_match(self, video_title, track_title, artist):
        """Check if video title matches track title"""
        # Remove artist name from video title for cleaner matching
        video_without_artist = video_title.replace(artist, '').strip()
        
        # Check if clean track title appears in video title
        if track_title in video_title or track_title in video_without_artist:
            return True
        
        # Check for common variations
        variations = [
            track_title,
            track_title.replace('(', '').replace(')', ''),
            track_title.replace('-', ' '),
            track_title.replace("'", ''),
            track_title.replace('"', '')
        ]
        
        for variation in variations:
            if variation and len(variation) > 3 and variation in video_title:
                return True
        
        return False

    def _is_album_content(self, video_title, album_title, artist):
        """Check if video is likely album content (full album, review, etc.)"""
        video_lower = video_title.lower()
        album_lower = album_title.lower()
        artist_lower = artist.lower()
        
        # Check for full album indicators
        full_album_indicators = [
            'full album',
            'complete album',
            'album completo',
            f'{album_lower} full',
            f'{album_lower} complete'
        ]
        
        for indicator in full_album_indicators:
            if indicator in video_lower:
                return True
        
        # Check if video contains both artist and album title
        if artist_lower in video_lower and album_lower in video_lower:
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