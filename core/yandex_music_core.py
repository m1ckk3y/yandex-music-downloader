"""
Core Yandex Music API functionality.
Shared between CLI and Django applications.
"""

import re
import time
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import requests

try:
    from yandex_music import Client
    from yandex_music.exceptions import YandexMusicError, NetworkError, UnauthorizedError
except ImportError:
    raise ImportError(
        "yandex-music library not found. Please install it using:\n"
        "pip install -r requirements.txt"
    )


def chunked(iterable, size):
    """Split iterable into chunks of fixed size."""
    for i in range(0, len(iterable), size):
        yield iterable[i:i+size]


class YandexMusicCore:
    """Core class for Yandex Music API operations."""
    
    def __init__(self, token: Optional[str] = None, preferred_format: str = "mp3"):
        """
        Initialize the core client.
        
        Args:
            token: Yandex Music OAuth token
            preferred_format: Preferred audio format (mp3, flac, aac)
        """
        self.token = token
        self.preferred_format = preferred_format.lower()
        self.client = None
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
    
    def authenticate(self) -> Tuple[bool, str]:
        """
        Authenticate with Yandex Music API.
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            if not self.token:
                self.client = Client()
                return True, "Initialized without token (limited access)"
            
            self.client = Client(self.token).init()
            account_info = self.client.account_status()
            
            if account_info:
                display_name = account_info.account.display_name
                return True, f"Authenticated as: {display_name}"
            else:
                return False, "Authentication failed"
        
        except UnauthorizedError:
            return False, "Invalid token"
        except NetworkError:
            return False, "Network error"
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            return False, f"Authentication error: {str(e)}"
    
    def extract_playlist_id(self, url_or_id: str) -> Optional[Tuple[str, str]]:
        """
        Extract playlist ID and owner from URL or direct ID.
        
        Args:
            url_or_id: Playlist URL or ID
            
        Returns:
            Tuple of (owner, playlist_id) or None if invalid
        """
        url_pattern = r'https?://music\.yandex\.[a-z]+/users/([^/]+)/playlists/(\d+)'
        match = re.search(url_pattern, url_or_id)
        
        if match:
            return match.group(1), match.group(2)
        
        if ':' in url_or_id:
            parts = url_or_id.split(':')
            if len(parts) == 2:
                return parts[0], parts[1]
        
        return None
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for safe file system usage.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename.strip()
    
    def get_liked_tracks_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about user's liked tracks.
        
        Returns:
            Dict with playlist info or None
        """
        if not self.client:
            success, _ = self.authenticate()
            if not success:
                return None
        
        try:
            liked_tracks = self.client.users_likes_tracks()
            if not liked_tracks or not hasattr(liked_tracks, 'tracks_ids'):
                return None
            
            # Extract track IDs
            track_ids = []
            for ti in liked_tracks.tracks_ids:
                track_id = getattr(ti, 'id', None) or str(ti)
                if track_id:
                    track_ids.append(track_id)
            
            return {
                'owner': 'me',
                'playlist_id': 'liked',
                'title': 'Liked Tracks',
                'track_ids': track_ids,
                'track_count': len(track_ids)
            }
        
        except Exception as e:
            self.logger.error(f"Error getting liked tracks: {e}")
            return None
    
    def get_playlist_info(self, playlist_identifier: str) -> Optional[Dict[str, Any]]:
        """
        Get playlist information.
        
        Args:
            playlist_identifier: Playlist URL, ID, or 'liked'
            
        Returns:
            Dict with playlist info or None
        """
        if not self.client:
            success, _ = self.authenticate()
            if not success:
                return None
        
        try:
            # Handle liked tracks
            if playlist_identifier.lower() in ['liked', 'favorites', 'my']:
                return self.get_liked_tracks_info()
            
            # Parse playlist ID
            playlist_info = self.extract_playlist_id(playlist_identifier)
            if not playlist_info:
                return None
            
            owner, playlist_id = playlist_info
            playlist = self.client.users_playlists(playlist_id, owner)
            
            if not playlist:
                return None
            
            # Extract track IDs
            track_ids = []
            if hasattr(playlist, 'tracks') and playlist.tracks:
                for track_short in playlist.tracks:
                    if hasattr(track_short, 'track_id'):
                        track_ids.append(str(track_short.track_id))
                    elif hasattr(track_short, 'id'):
                        track_ids.append(str(track_short.id))
            
            return {
                'owner': owner,
                'playlist_id': playlist_id,
                'title': playlist.title,
                'track_ids': track_ids,
                'track_count': len(track_ids)
            }
        
        except Exception as e:
            self.logger.error(f"Error getting playlist: {e}")
            return None
    
    def fetch_tracks_batch(self, track_ids: List[str], batch_size: int = 100) -> List[Any]:
        """
        Fetch track details in batches.
        
        Args:
            track_ids: List of track IDs
            batch_size: Number of tracks per batch
            
        Returns:
            List of track objects
        """
        tracks = []
        
        for batch in chunked(track_ids, batch_size):
            try:
                batch_tracks = self.client.tracks(batch)
                tracks.extend([t for t in batch_tracks if t])
            except Exception as e:
                self.logger.error(f"Error fetching batch: {e}")
                # Try individual tracks
                for track_id in batch:
                    try:
                        track_list = self.client.tracks([track_id])
                        if track_list and track_list[0]:
                            tracks.append(track_list[0])
                    except Exception:
                        continue
        
        return tracks
    
    def get_track_metadata(self, track) -> Dict[str, Any]:
        """
        Extract metadata from track object.
        
        Args:
            track: Track object from API
            
        Returns:
            Dict with track metadata
        """
        try:
            artists = getattr(track, 'artists', [])
            if artists:
                artist = ', '.join([getattr(a, 'name', 'Unknown') for a in artists])
            else:
                artist = 'Unknown Artist'
            
            duration_ms = getattr(track, 'duration_ms', 0) or 0
            duration_sec = duration_ms // 1000
            
            return {
                'id': str(getattr(track, 'id', '')),
                'title': getattr(track, 'title', 'Unknown Title') or 'Unknown Title',
                'artist': artist,
                'duration': duration_sec
            }
        except Exception as e:
            self.logger.error(f"Error extracting metadata: {e}")
            return {
                'id': '',
                'title': 'Unknown',
                'artist': 'Unknown',
                'duration': 0
            }
    
    def get_best_quality_download_info(self, track_id: str, max_retries: int = 3):
        """
        Get the best quality download information for a track.
        
        Args:
            track_id: Track ID
            max_retries: Maximum number of retry attempts
            
        Returns:
            Download info object or None
        """
        for attempt in range(max_retries):
            try:
                download_infos = self.client.tracks_download_info(track_id)
                if not download_infos:
                    return None
                
                # Try preferred format first
                preferred_infos = [info for info in download_infos if info.codec == self.preferred_format]
                if preferred_infos:
                    return max(preferred_infos, key=lambda x: x.bitrate_in_kbps or 0)
                
                # Fallback: flac > mp3 > aac > other
                codec_priority = {'flac': 4, 'mp3': 3, 'aac': 2}
                best_info = max(download_infos, key=lambda x: (
                    codec_priority.get(x.codec, 0),
                    x.bitrate_in_kbps or 0
                ))
                
                return best_info
            
            except (NetworkError, requests.exceptions.RequestException) as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"Network error for track {track_id}: {e}")
                    return None
            except Exception as e:
                self.logger.error(f"Error getting download info: {e}")
                return None
        
        return None
    
    def download_track_file(self, track_id: str, output_path: Path) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Download a single track file.
        
        Args:
            track_id: Track ID
            output_path: Path where to save the file
            
        Returns:
            Tuple[bool, Optional[Dict]]: (success, file_info)
        """
        try:
            download_info = self.get_best_quality_download_info(track_id)
            if not download_info:
                return False, None
            
            download_url = download_info.get_direct_link()
            if not download_url:
                return False, None
            
            response = self.session.get(download_url, stream=True)
            response.raise_for_status()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_info = {
                'size': output_path.stat().st_size,
                'format': download_info.codec,
                'bitrate': download_info.bitrate_in_kbps
            }
            
            return True, file_info
        
        except Exception as e:
            self.logger.error(f"Error downloading track {track_id}: {e}")
            return False, None
