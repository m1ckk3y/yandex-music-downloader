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
    
    def __init__(self, token: Optional[str] = None, output_dir: str = "downloads"):
        """
        Initialize the downloader.
        
        Args:
            token: Yandex Music OAuth token
            output_dir: Directory to save downloaded files
        """
        self.token = token
        self.output_dir = Path(output_dir)
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
            return False
        except Exception as e:
            print(f"✗ Authentication error: {e}")
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
                return self.client.users_likes_tracks()
            
            # Extract playlist ID from URL or use direct ID
            playlist_info = self.extract_playlist_id(playlist_identifier)
            if not playlist_info:
                print(f"✗ Invalid playlist URL or ID: {playlist_identifier}")
                return None
            
            owner, playlist_id = playlist_info
            print(f"Getting playlist {playlist_id} from user {owner}...")
            
            playlist = self.client.users_playlists(playlist_id, owner)
            if playlist:
                print(f"✓ Found playlist: {playlist.title} ({len(playlist.tracks)} tracks)")
                return playlist
            else:
                print("✗ Playlist not found or not accessible")
                return None
                
        except Exception as e:
            print(f"✗ Error getting playlist: {e}")
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
    
    def get_best_quality_download_info(self, track_id: str):
        """
        Get the best quality download information for a track.
        
        Args:
            track_id: Track ID
            
        Returns:
            Download info object or None
        """
        try:
            download_infos = self.client.tracks_download_info(track_id)
            if not download_infos:
                return None
            
            # Priority order: mp3 > aac > other codecs
            # Higher bitrate is better
            codec_priority = {'mp3': 3, 'aac': 2, 'other': 1}
            
            best_info = max(download_infos, key=lambda x: (
                codec_priority.get(x.codec, 0),
                x.bitrate_in_kbps or 0
            ))
            
            return best_info
            
        except Exception as e:
            self.logger.error(f"Error getting download info for track {track_id}: {e}")
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
            # Get track info
            if hasattr(track, 'track'):
                track_obj = track.track
            else:
                track_obj = track
            
            if not track_obj:
                print(f"✗ Track {track_num}: Invalid track object")
                return False
            
            # Create filename
            artists = ', '.join([artist.name for artist in track_obj.artists]) if track_obj.artists else 'Unknown Artist'
            title = track_obj.title or 'Unknown Title'
            
            filename = f"{artists} - {title}.mp3"
            filename = self.sanitize_filename(filename)
            filepath = self.output_dir / filename
            
            # Skip if file already exists
            if filepath.exists():
                print(f"⏭ Track {track_num}/{total_tracks}: {filename} (already exists)")
                return True
            
            # Get download info
            download_info = self.get_best_quality_download_info(track_obj.id)
            if not download_info:
                print(f"✗ Track {track_num}/{total_tracks}: No download info available for {filename}")
                return False
            
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
            if hasattr(playlist, 'tracks'):
                tracks = playlist.tracks
            elif hasattr(playlist, 'track_ids'):
                # For liked tracks, we need to fetch the actual tracks
                tracks = []
                print("Fetching track details...")
                for track_id in tqdm(playlist.track_ids, desc="Loading tracks"):
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
            
            for i, track in enumerate(tracks, 1):
                if self.download_track(track, i, len(tracks)):
                    successful_downloads += 1
                else:
                    failed_downloads += 1
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            # Summary
            print(f"\n📊 Download Summary:")
            print(f"✓ Successful: {successful_downloads}")
            print(f"✗ Failed: {failed_downloads}")
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
    downloader = YandexMusicDownloader(token=token, output_dir=args.output)
    
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
