# Yandex Music Playlist Downloader

A professional command-line application for downloading Yandex Music playlists with support for multiple audio formats including FLAC, MP3, and AAC.

## Features

- 🎵 Download complete playlists from Yandex Music
- 🎯 Support for playlist URLs, IDs, and liked tracks
- 🎼 **Multiple format support**: FLAC, MP3, AAC with quality selection
- 🔊 Smart format prioritization with fallback to best available quality
- 📁 Saves all files in a single organized directory with proper extensions
- 📊 Progress indicators and detailed logging
- 🔐 OAuth token authentication support
- 🛡️ Comprehensive error handling and recovery
- ⚡ Rate limiting to avoid API restrictions

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Step 1: Clone or Download

Download the application files to your local machine:

```bash
# If using git
git clone https://github.com/m1ckk3y/yandex-music-downloader.git
cd yandex-music-downloader

# Or download and extract the ZIP file
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Make Script Executable (Linux/macOS)

```bash
chmod +x yandex_music_downloader.py
```

## Authentication

To access your personal playlists and liked tracks, you need a Yandex Music OAuth token.

### Getting Your Token

1. Visit the [Yandex Music API documentation](https://yandex-music.readthedocs.io/en/main/token.html)
2. Follow the instructions to generate your personal OAuth token
3. Keep your token secure and never share it publicly

### Setting Up Your Token

You can provide your token in two ways:

#### Option 1: Environment Variable (Recommended)

```bash
# Linux/macOS
export YANDEX_MUSIC_TOKEN="your_token_here"

# Windows
set YANDEX_MUSIC_TOKEN=your_token_here
```

#### Option 2: Command Line Argument

```bash
python yandex_music_downloader.py --token "your_token_here" [playlist]
```

## Usage

### Basic Usage

```bash
# Download a public playlist
python yandex_music_downloader.py "https://music.yandex.ru/users/username/playlists/123"

# Download using playlist ID format
python yandex_music_downloader.py "username:123"

# Download your liked tracks (requires token)
python yandex_music_downloader.py "liked"
```

### Advanced Usage

```bash
# Download in FLAC format (highest quality lossless)
python yandex_music_downloader.py "https://music.yandex.ru/users/username/playlists/123" --format flac

# Download in AAC format
python yandex_music_downloader.py "username:123" --format aac

# Specify custom output directory
python yandex_music_downloader.py "https://music.yandex.ru/users/username/playlists/123" --output "./my_music"

# Use token from command line
python yandex_music_downloader.py "liked" --token "your_token_here"

# Combine all options
python yandex_music_downloader.py "username:123" --format flac --output "./downloads" --token "your_token_here"
```

### Command Line Options

```
positional arguments:
  playlist              Playlist URL, ID (format: owner:playlist_id), or "liked" for your liked tracks

optional arguments:
  -h, --help            Show help message and exit
  --token TOKEN, -t TOKEN
                        Yandex Music OAuth token (required for private playlists and liked tracks)
  --output OUTPUT, -o OUTPUT
                        Output directory for downloaded files (default: downloads)
  --format {mp3,flac,aac}, -f {mp3,flac,aac}
                        Preferred audio format (default: mp3). Will fallback to best available if preferred format is not available.
  --version             Show program's version number and exit
```

## Examples

### Download a Public Playlist

```bash
python yandex_music_downloader.py "https://music.yandex.ru/users/yamusic-daily/playlists/1036"
```

### Download Your Liked Tracks

```bash
# Set token first
export YANDEX_MUSIC_TOKEN="your_token_here"
python yandex_music_downloader.py "liked"
```

### Download to Custom Directory

```bash
python yandex_music_downloader.py "username:123" --output "./MyMusic"
```

### Download in FLAC Format

```bash
# Download your liked tracks in FLAC format
export YANDEX_MUSIC_TOKEN="your_token_here"
python yandex_music_downloader.py "liked" --format flac

# Download specific playlist in FLAC
python yandex_music_downloader.py "https://music.yandex.ru/users/username/playlists/123" --format flac --token "your_token_here"
```

## File Organization

Downloaded files are organized as follows:

```
downloads/
├── Artist Name - Song Title.flac
├── Another Artist - Another Song.mp3
├── Yet Another Artist - Title.aac
├── download.log
└── ...
```

- Files are named in the format: `Artist - Title.{format}`
- File extensions automatically match the downloaded format (`.flac`, `.mp3`, `.aac`)
- Invalid characters in filenames are automatically sanitized
- A log file tracks all download activities
- Existing files are automatically skipped

## Format Selection & Quality

The application supports multiple audio formats with intelligent quality selection:

### Available Formats
- **FLAC**: Lossless compression, highest quality (when available)
- **MP3**: Lossy compression, widely compatible
- **AAC**: Lossy compression, good quality-to-size ratio

### Selection Logic
1. **Preferred Format**: Downloads your specified format if available
2. **Fallback Priority**: FLAC > MP3 > AAC > Other formats
3. **Bitrate Priority**: Highest bitrate within chosen format
4. **Typical Qualities**: FLAC (lossless), MP3/AAC (320kbps, 192kbps, 128kbps)

### Usage Examples
```bash
# Download in FLAC (lossless) when available
python yandex_music_downloader.py playlist_url --format flac

# Download in MP3 (default)
python yandex_music_downloader.py playlist_url --format mp3

# Download in AAC
python yandex_music_downloader.py playlist_url --format aac
```

## Error Handling

The application includes comprehensive error handling:

- **Network Issues**: Automatic retry with exponential backoff
- **Authentication Errors**: Clear error messages and suggestions
- **Invalid URLs**: Format validation and helpful error messages
- **Missing Tracks**: Continues downloading available tracks
- **File System Errors**: Proper error reporting and logging

## Logging

All activities are logged to `download.log` in the output directory:

- Download progress and results
- Error messages and stack traces
- Authentication status
- API response details

## Troubleshooting

### Common Issues

#### "Authentication failed: Invalid token"
- Verify your token is correct and not expired
- Generate a new token if necessary

#### "Playlist not found or not accessible"
- Check if the playlist URL is correct
- Ensure the playlist is public or you have access
- Verify your token has the necessary permissions

#### "No download info available"
- Some tracks may not be available for download due to licensing
- Try downloading other tracks from the playlist

#### Import Error: yandex-music not found
- Run `pip install -r requirements.txt`
- Ensure you're using the correct Python environment

### Getting Help

1. Check the log file for detailed error information
2. Verify your internet connection
3. Ensure your token is valid and has necessary permissions
4. Try downloading a different playlist to isolate the issue

## Legal Disclaimer

⚠️ **Important Legal Notice**

This tool is provided for educational and personal use only. Users are responsible for complying with:

- Yandex Music Terms of Service
- Local copyright laws and regulations
- Applicable licensing agreements

**Please note:**
- Only download music you have the legal right to access
- Respect artists' and copyright holders' rights
- Use downloaded content for personal use only
- Do not redistribute or share downloaded content

The developers of this tool are not responsible for any misuse or legal consequences arising from its use.

## Technical Details

### Dependencies

- **yandex-music**: Unofficial Yandex Music API client
- **requests**: HTTP library for downloading tracks
- **tqdm**: Progress bar library
- **pathlib**: Modern path handling (built-in Python 3.4+)

### API Rate Limiting

The application includes built-in rate limiting:
- 0.5-second delay between track downloads
- Exponential backoff for failed requests
- Respectful API usage patterns

### Supported Formats

- **Audio Formats**: FLAC (lossless), MP3, AAC
- **Quality Range**: FLAC (lossless), MP3/AAC (128kbps to 320kbps)
- **Format Selection**: User-selectable with intelligent fallback
- **Metadata**: Artist, title, album information preserved

## Contributing

This is an open-source project. Contributions are welcome:

1. Report bugs and issues
2. Suggest new features
3. Submit pull requests
4. Improve documentation

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Version History

- **v1.1.0**: FLAC support and format selection
  - Added FLAC download support
  - Implemented format selection (--format option)
  - Smart quality prioritization with fallback
  - Proper file extensions based on actual format
  - Enhanced quality selection logic

- **v1.0.0**: Initial release with core functionality
  - Playlist downloading
  - OAuth authentication
  - Quality selection
  - Error handling
  - Logging system

---

**Disclaimer**: This is an unofficial tool and is not affiliated with Yandex Music. Use responsibly and in accordance with applicable laws and terms of service.
