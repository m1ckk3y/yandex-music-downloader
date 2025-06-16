#!/usr/bin/env python3
"""
Example usage of Yandex Music Downloader

This script demonstrates how to use the downloader programmatically.
"""

import os
from yandex_music_downloader import YandexMusicDownloader

def main():
    """Example usage of the downloader."""
    
    # Get token from environment variable
    token = os.getenv('YANDEX_MUSIC_TOKEN')
    
    if not token:
        print("Please set YANDEX_MUSIC_TOKEN environment variable")
        return
    
    # Initialize downloader
    downloader = YandexMusicDownloader(token=token, output_dir="example_downloads")
    
    # Authenticate
    if not downloader.authenticate():
        print("Authentication failed")
        return
    
    # Example: Download liked tracks
    print("Downloading your liked tracks...")
    success = downloader.download_playlist("liked")
    
    if success:
        print("Download completed successfully!")
    else:
        print("Download failed!")

if __name__ == '__main__':
    main()
