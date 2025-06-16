#!/usr/bin/env python3
"""
Yandex Music Playlist Downloader

A command-line application for downloading Yandex Music playlists.
Supports downloading tracks in the highest available quality.

Author: Yandex Music Downloader
License: MIT
"""

import argparse
import os
import sys
import re
import time
from pathlib import Path
from typing import List, Optional, Tuple
import requests
from tqdm import tqdm
import logging

try:
    from yandex_music import Client
    from yandex_music.exceptions import YandexMusicError, NetworkError, UnauthorizedError
except ImportError:
    print("Error: yandex-music library not found. Please install it using:")
    print("pip install -r requirements.txt")
    sys.exit(1)


class YandexMusicDownloader:
    """Main class for downloading Yandex Music playlists."""
    
    def __init__(self, token: Optional[str] = None, output_dir: str = "downloads", preferred_format: str = "mp3"):
        """
        Initialize the downloader.
        
        Args:
            token: Yandex Music OAuth token
            output_dir: Directory to save downloaded files
            preferred_format: Preferred audio format (mp3, flac, aac)
        """
        self.token = token
        self.output_dir = Path(output_dir)
        self.preferred_format = preferred_format.lower()
        self.client = None
        self.session = requests.Session()
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.output_dir / 'download.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def authenticate(self) -> bool:
        """
        Authenticate with Yandex Music API.
        
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            if not self.token:
                print("No token provided. Some features may be limited.")
                self.client = Client()
                return True
            
            print("Authenticating with Yandex Music...")
            self.client = Client(self.token).init()
            
            # Test authentication by getting account info
            account_info = self.client.account_status()
            if account_info:
                print(f"✓ Successfully authenticated as: {account_info.account.display_name}")
                return True
            else:
                print("✗ Authentication failed")
                return False
                
        except UnauthorizedError:
            print("✗ Authentication failed: Invalid token")
            print("💡 Get your token from: https://yandex-music.readthedocs.io/en/main/token.html")
            return False
        except (NetworkError, requests.exceptions.RequestException, requests.exceptions.ConnectionError) as e:
            print(f"✗ Network error during authentication: {e}")
            print("💡 Check your internet connection and try again")
            return False
        except Exception as e:
            print(f"✗ Authentication error: {e}")
            self.logger.error(f"Authentication error: {e}")
            return False
    
    def extract_playlist_id(self, url_or_id: str) -> Optional[Tuple[str, str]]:
        """
        Extract playlist ID and owner from URL or direct ID.
        
        Args:
            url_or_id: Playlist URL or ID
            
        Returns:
            Tuple of (owner, playlist_id) or None if invalid
        """
        # Pattern for Yandex Music playlist URLs
        url_pattern = r'https?://music\.yandex\.[a-z]+/users/([^/]+)/playlists/(\d+)'
        
        match = re.search(url_pattern, url_or_id)
        if match:
            return match.group(1), match.group(2)
        
        # Check if it's a direct playlist ID format (owner:playlist_id)
        if ':' in url_or_id:
            parts = url_or_id.split(':')
            if len(parts) == 2:
                return parts[0], parts[1]
        
        return None
    
    def get_playlist(self, playlist_identifier: str):
        """
        Get playlist information.
        
        Args:
            playlist_identifier: Playlist URL or ID
            
        Returns:
            Playlist object or None
        """
        try:
            # Handle special cases
            if playlist_identifier.lower() in ['liked', 'favorites', 'my']:
                print("Getting your liked tracks...")
                try:
                    liked_tracks = self.client.users_likes_tracks()
                    if liked_tracks:
                        # TracksList has tracks_ids (with underscore), not track_ids
                        track_count = len(liked_tracks.tracks_ids) if hasattr(liked_tracks, 'tracks_ids') and liked_tracks.tracks_ids else 0
                        print(f"✓ Found {track_count} liked tracks")
                        return liked_tracks
                    else:
                        print("✗ No liked tracks found")
                        return None
                except Exception as e:
                    print(f"✗ Error getting liked tracks: {e}")
                    self.logger.error(f"Error getting liked tracks: {e}")
                    return None
            
            # Extract playlist ID from URL or use direct ID
            playlist_info = self.extract_playlist_id(playlist_identifier)
            if not playlist_info:
                print(f"✗ Invalid playlist URL or ID: {playlist_identifier}")
                print("Valid formats:")
                print("  - https://music.yandex.ru/users/username/playlists/123")
                print("  - username:123")
                print("  - 'liked' for your liked tracks")
                return None
            
            owner, playlist_id = playlist_info
            print(f"Getting playlist {playlist_id} from user {owner}...")
            
            try:
                playlist = self.client.users_playlists(playlist_id, owner)
                if playlist:
                    track_count = len(playlist.tracks) if hasattr(playlist, 'tracks') and playlist.tracks else 0
                    print(f"✓ Found playlist: {playlist.title} ({track_count} tracks)")
                    return playlist
                else:
                    print("✗ Playlist not found or not accessible")
                    return None
            except Exception as playlist_error:
                # Handle specific Yandex Music API errors
                error_msg = str(playlist_error)
                if 'playlist-not-found' in error_msg:
                    print(f"✗ Playlist not found: {owner}:{playlist_id}")
                    print("This could mean:")
                    print("  - The playlist doesn't exist")
                    print("  - The playlist is private and you don't have access")
                    print("  - The owner username is incorrect")
                elif 'not-found' in error_msg:
                    print(f"✗ User '{owner}' not found")
                elif 'access-denied' in error_msg or 'forbidden' in error_msg:
                    print(f"✗ Access denied to playlist {owner}:{playlist_id}")
                    print("This playlist might be private")
                else:
                    print(f"✗ Error accessing playlist: {playlist_error}")
                
                self.logger.error(f"Error getting playlist {owner}:{playlist_id}: {playlist_error}")
                return None
                
        except Exception as e:
            print(f"✗ Unexpected error getting playlist: {e}")
            self.logger.error(f"Unexpected error getting playlist: {e}")
            return None
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename for safe file system usage.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename.strip()
    
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
                
                # First, try to find the preferred format
                preferred_infos = [info for info in download_infos if info.codec == self.preferred_format]
                if preferred_infos:
                    # If preferred format is available, get the highest bitrate version
                    return max(preferred_infos, key=lambda x: x.bitrate_in_kbps or 0)
                
                # If preferred format is not available, fall back to quality priority
                # Priority order: flac > mp3 > aac > other codecs
                codec_priority = {'flac': 4, 'mp3': 3, 'aac': 2, 'other': 1}
                
                best_info = max(download_infos, key=lambda x: (
                    codec_priority.get(x.codec, 0),
                    x.bitrate_in_kbps or 0
                ))
                
                return best_info
                
            except (NetworkError, requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"⚠️  Network error getting download info for track {track_id}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"Network error getting download info for track {track_id} after {max_retries} attempts: {e}")
                    return None
            except Exception as e:
                self.logger.error(f"Error getting download info for track {track_id}: {e}")
                return None
        
        return None
    
    def download_track(self, track, track_num: int = 0, total_tracks: int = 0) -> bool:
        """
        Download a single track.
        
        Args:
            track: Track object
            track_num: Current track number
            total_tracks: Total number of tracks
            
        Returns:
            True if download successful, False otherwise
        """
        try:
            # Get track info - handle different track object structures
            track_obj = None
            
            if track is None:
                print(f"✗ Track {track_num}/{total_tracks}: Track object is None")
                return False
            
            # Handle different track object types
            if hasattr(track, 'track') and track.track is not None:
                track_obj = track.track
            elif hasattr(track, 'id') and hasattr(track, 'title'):
                # Direct track object
                track_obj = track
            elif hasattr(track, 'track_id'):
                # Track reference - need to fetch the actual track
                try:
                    track_obj = self.client.tracks([track.track_id])[0]
                except Exception as e:
                    print(f"✗ Track {track_num}/{total_tracks}: Could not fetch track details: {e}")
                    return False
            else:
                print(f"✗ Track {track_num}/{total_tracks}: Unknown track object type: {type(track)}")
                return False
            
            if not track_obj or not hasattr(track_obj, 'id'):
                print(f"✗ Track {track_num}/{total_tracks}: Invalid track object after processing")
                return False
            
            # Create filename
            artists = 'Unknown Artist'
            if hasattr(track_obj, 'artists') and track_obj.artists:
                try:
                    artists = ', '.join([artist.name for artist in track_obj.artists if hasattr(artist, 'name')])
                except Exception:
                    artists = 'Unknown Artist'
            
            title = getattr(track_obj, 'title', 'Unknown Title') or 'Unknown Title'
            
            # Get download info first to determine the actual format
            download_info = self.get_best_quality_download_info(track_obj.id)
            if not download_info:
                print(f"✗ Track {track_num}/{total_tracks}: No download info available")
                return False
            
            # Use the actual format from download info for file extension
            file_extension = download_info.codec if download_info.codec in ['mp3', 'flac', 'aac'] else 'mp3'
            filename = f"{artists} - {title}.{file_extension}"
            filename = self.sanitize_filename(filename)
            filepath = self.output_dir / filename
            
            # Skip if file already exists
            if filepath.exists():
                print(f"⏭ Track {track_num}/{total_tracks}: {filename} (already exists)")
                return True
            
            # Get direct download link
            download_url = download_info.get_direct_link()
            if not download_url:
                print(f"✗ Track {track_num}/{total_tracks}: Could not get download link for {filename}")
                return False
            
            # Download the track
            print(f"⬇ Track {track_num}/{total_tracks}: {filename} ({download_info.codec.upper()}, {download_info.bitrate_in_kbps}kbps)")
            
            response = self.session.get(download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(filepath, 'wb') as f, tqdm(
                desc=f"Downloading",
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                leave=False
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
            
            print(f"✓ Track {track_num}/{total_tracks}: {filename} downloaded successfully")
            self.logger.info(f"Downloaded: {filename}")
            return True
            
        except Exception as e:
            print(f"✗ Track {track_num}/{total_tracks}: Error downloading {filename}: {e}")
            self.logger.error(f"Error downloading {filename}: {e}")
            return False
    
    def download_playlist(self, playlist_identifier: str) -> bool:
        """
        Download entire playlist.
        
        Args:
            playlist_identifier: Playlist URL or ID
            
        Returns:
            True if download successful, False otherwise
        """
        try:
            # Get playlist
            playlist = self.get_playlist(playlist_identifier)
            if not playlist:
                return False
            
            # Get tracks
            if hasattr(playlist, 'tracks') and playlist.tracks:
                tracks = playlist.tracks
            elif hasattr(playlist, 'tracks_ids'):
                # For liked tracks, we need to fetch the actual tracks
                tracks = []
                print("Fetching track details...")
                for track_id in tqdm(playlist.tracks_ids, desc="Loading tracks"):
                    try:
                        track = self.client.tracks([track_id.id])[0]
                        tracks.append(track)
                    except Exception as e:
                        self.logger.error(f"Error fetching track {track_id.id}: {e}")
                        continue
            else:
                print("✗ Could not get tracks from playlist")
                return False
            
            if not tracks:
                print("✗ No tracks found in playlist")
                return False
            
            print(f"\n🎵 Starting download of {len(tracks)} tracks...")
            print(f"📁 Saving to: {self.output_dir.absolute()}")
            
            # Download tracks
            successful_downloads = 0
            failed_downloads = 0
            skipped_tracks = 0
            
            # Filter out invalid tracks before processing
            valid_tracks = []
            for track in tracks:
                if track is None:
                    skipped_tracks += 1
                    continue
                
                # Check if track has required attributes
                track_obj = None
                if hasattr(track, 'track') and track.track is not None:
                    track_obj = track.track
                elif hasattr(track, 'id'):
                    track_obj = track
                elif hasattr(track, 'track_id'):
                    # This will be handled in download_track
                    track_obj = track
                
                if track_obj is None:
                    skipped_tracks += 1
                    continue
                    
                valid_tracks.append(track)
            
            if skipped_tracks > 0:
                print(f"⚠️  Skipped {skipped_tracks} invalid track objects")
            
            if not valid_tracks:
                print("✗ No valid tracks found in playlist")
                return False
            
            print(f"\n🎵 Processing {len(valid_tracks)} valid tracks (skipped {skipped_tracks} invalid)...")
            
            for i, track in enumerate(valid_tracks, 1):
                if self.download_track(track, i, len(valid_tracks)):
                    successful_downloads += 1
                else:
                    failed_downloads += 1
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            # Summary
            print(f"\n📊 Download Summary:")
            print(f"✓ Successful: {successful_downloads}")
            print(f"✗ Failed: {failed_downloads}")
            if skipped_tracks > 0:
                print(f"⏭️ Skipped: {skipped_tracks} (invalid track objects)")
            print(f"📁 Files saved to: {self.output_dir.absolute()}")
            
            return successful_downloads > 0
            
        except Exception as e:
            print(f"✗ Error downloading playlist: {e}")
            self.logger.error(f"Error downloading playlist: {e}")
            return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Download Yandex Music playlists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://music.yandex.ru/users/username/playlists/123
  %(prog)s username:123
  %(prog)s liked --token YOUR_TOKEN
  %(prog)s https://music.yandex.ru/users/username/playlists/123 --output ./music --token YOUR_TOKEN
  %(prog)s https://music.yandex.ru/users/username/playlists/123 --format flac --token YOUR_TOKEN

Note: A token is required for accessing private playlists and liked tracks.
Get your token from: https://yandex-music.readthedocs.io/en/main/token.html
        """
    )
    
    parser.add_argument(
        'playlist',
        help='Playlist URL, ID (format: owner:playlist_id), or "liked" for your liked tracks'
    )
    
    parser.add_argument(
        '--token', '-t',
        help='Yandex Music OAuth token (required for private playlists and liked tracks)'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='downloads',
        help='Output directory for downloaded files (default: downloads)'
    )
    
    parser.add_argument(
        '--format', '-f',
        choices=['mp3', 'flac', 'aac'],
        default='mp3',
        help='Preferred audio format (default: mp3). Will fallback to best available if preferred format is not available.'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='Yandex Music Downloader 1.0.0'
    )
    
    args = parser.parse_args()
    
    # Check for token in environment variable if not provided
    token = args.token or os.getenv('YANDEX_MUSIC_TOKEN')
    
    print("🎵 Yandex Music Playlist Downloader")
    print("=" * 40)
    
    # Initialize downloader
    downloader = YandexMusicDownloader(token=token, output_dir=args.output, preferred_format=args.format)
    
    # Authenticate
    if not downloader.authenticate():
        print("\n⚠️  Authentication failed. You can still try to download public playlists.")
        if not token:
            print("💡 Tip: Set YANDEX_MUSIC_TOKEN environment variable or use --token option")
    
    # Download playlist
    print(f"\n🎯 Target: {args.playlist}")
    success = downloader.download_playlist(args.playlist)
    
    if success:
        print("\n🎉 Download completed!")
        sys.exit(0)
    else:
        print("\n💥 Download failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()
