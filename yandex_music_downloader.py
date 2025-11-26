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
import time
from pathlib import Path
from typing import List, Optional
from tqdm import tqdm
import logging

# Import shared core functionality
from core import YandexMusicCore


class YandexMusicDownloader(YandexMusicCore):
    """CLI wrapper for downloading Yandex Music playlists."""
    
    def __init__(self, token: Optional[str] = None, output_dir: str = "downloads", preferred_format: str = "mp3"):
        """
        Initialize the downloader.
        
        Args:
            token: Yandex Music OAuth token
            output_dir: Directory to save downloaded files
            preferred_format: Preferred audio format (mp3, flac, aac)
        """
        super().__init__(token=token, preferred_format=preferred_format)
        self.output_dir = Path(output_dir)
        
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
    
    def authenticate_cli(self) -> bool:
        """
        Authenticate with Yandex Music API (CLI version with print statements).
        
        Returns:
            True if authentication successful, False otherwise
        """
        if not self.token:
            print("No token provided. Some features may be limited.")
        else:
            print("Authenticating with Yandex Music...")
        
        success, message = super().authenticate()
        
        if success:
            if self.token:
                print(f"✓ Successfully {message}")
            return True
        else:
            print(f"✗ Authentication failed: {message}")
            if "Invalid token" in message:
                print("💡 Get your token from: https://yandex-music.readthedocs.io/en/main/token.html")
            elif "Network" in message:
                print("💡 Check your internet connection and try again")
            return False
    
    # Inherited from YandexMusicCore: extract_playlist_id, sanitize_filename, get_best_quality_download_info
    
    def get_playlist(self, playlist_identifier: str):
        """
        Get playlist information.
        
        Args:
            playlist_identifier: Playlist URL or ID
            
        Returns:
            Playlist object or None
        """
        try:
            # Ensure client is initialized (for both public and authenticated requests)
            if not self.client:
                success, message = super().authenticate()
                if not success:
                    print(f"✗ Authentication failed: {message}")
                    self.logger.error(f"Authentication failed in get_playlist: {message}")
                    return None
            
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
                print("  - https://music.yandex.ru/playlists/<uuid>")
                print("  - username:123")
                print("  - 'liked' for your liked tracks")
                return None
            
            owner, playlist_id = playlist_info
            
            # UUID-style playlists (new public / personal links like /playlists/<uuid>)
            if owner == '__uuid_playlist__':
                print(f"Detected UUID playlist link: {playlist_id}")
                try:
                    playlist = self.resolve_uuid_playlist(playlist_id)
                except Exception as e:
                    print(f"✗ Error resolving UUID playlist: {e}")
                    self.logger.error(f"Error resolving UUID playlist {playlist_id}: {e}")
                    return None
                
                if not playlist:
                    print(f"✗ Could not find UUID playlist {playlist_id}")
                    print("This could mean:")
                    print("  - The playlist doesn't exist or is not available in your region")
                    print("  - The playlist is private and you don't have access")
                    return None
                
                track_count = len(playlist.tracks) if hasattr(playlist, 'tracks') and playlist.tracks else 0
                owner_obj = getattr(playlist, 'owner', None)
                owner_login = getattr(owner_obj, 'login', None) if owner_obj is not None else None
                owner_uid = getattr(playlist, 'uid', None)
                owner_display = owner_login or owner_uid or 'unknown'
                print(f"✓ Found playlist: {playlist.title} ({track_count} tracks) from user {owner_display}")
                return playlist
            
            # Legacy users/<owner>/playlists/<kind> style or owner:kind ID
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
    
    # sanitize_filename and get_best_quality_download_info inherited from YandexMusicCore
    
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
  %(prog)s https://music.yandex.ru/playlists/be5ecb55-0e70-5bf5-a70b-c26a123e2a84
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
        help='Playlist URL (old users/... or new /playlists/<uuid>), ID (format: owner:playlist_id), or "liked" for your liked tracks'
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
    if not downloader.authenticate_cli():
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
