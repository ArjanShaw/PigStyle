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
        if not self.enabled:
            st.error("🎵 YouTube API key not configured. Please set YOUTUBE_API_KEY in your environment variables.")
            return []
        
        if self.quota_exceeded:
            st.warning("🎵 YouTube API quota exceeded. YouTube search is temporarily disabled.")
            return []
            
        return self._search_album_and_filter_tracks(search_query, record_data, track_titles)

    def _search_album_and_filter_tracks(self, search_query, record_data, track_titles):
        artist = record_data.get('artist', '')
        album_title = record_data.get('title', '')
        
        youtube = build('youtube', 'v3', developerKey=self.api_key)
        request = youtube.search().list(
            q=search_query,
            part='snippet',
            type='video',
            maxResults=20,
            videoEmbeddable='true',
            videoDuration='short',
            order='relevance'
        )
        
        response = request.execute()
        
        all_results = self._process_youtube_results(response, track_titles, artist, album_title)
        
        return all_results

    def _process_youtube_results(self, response, track_titles, artist, album_title):
        track_results = []
        album_results = []
        
        for item in response.get('items', []):
            # FIX: Safely get video ID
            video_id = item.get('id', {}).get('videoId')
            if not video_id:
                # Skip items without video ID
                continue
                
            snippet = item.get('snippet', {})
            if not snippet:
                continue
                
            video_title = snippet.get('title', '')
            channel_title = snippet.get('channelTitle', '')
            thumbnails = snippet.get('thumbnails', {})
            
            video_data = {
                'title': video_title,
                'channel': channel_title,
                'thumbnail': thumbnails.get('default', {}).get('url', ''),
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'video_id': video_id
            }
            
            matched_track = self._find_matching_track(video_title, track_titles, artist)
            if matched_track:
                video_data['type'] = 'track'
                video_data['track_title'] = matched_track
                track_results.append(video_data)
            else:
                if self._is_album_content(video_title, album_title, artist):
                    video_data['type'] = 'album'
                    album_results.append(video_data)
                else:
                    video_data['type'] = 'other'
                    album_results.append(video_data)
        
        return track_results + album_results

    def _find_matching_track(self, video_title, track_titles, artist):
        if not track_titles:
            return None
            
        video_lower = video_title.lower()
        artist_lower = artist.lower()
        
        for track_title in track_titles:
            track_lower = track_title.lower()
            
            clean_video = self._clean_video_title(video_lower)
            clean_track = self._clean_track_title(track_lower)
            
            if self._is_track_match(clean_video, clean_track, artist_lower):
                return track_title
                
        return None

    def _is_track_match(self, video_title, track_title, artist):
        video_without_artist = video_title.replace(artist, '').strip()
        
        if track_title in video_title or track_title in video_without_artist:
            return True
        
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
        video_lower = video_title.lower()
        album_lower = album_title.lower()
        artist_lower = artist.lower()
        
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
        
        if artist_lower in video_lower and album_lower in video_lower:
            return True
            
        return False

    def _clean_track_title(self, track_title):
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
        
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _clean_video_title(self, video_title):
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

    def is_enabled(self):
        return self.enabled