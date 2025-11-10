# Yandex Music Playlist Downloader

A professional application for downloading Yandex Music playlists with both a command-line interface and a modern Django web interface. Supports multiple audio formats including FLAC, MP3, and AAC.

## Features

### Command Line Interface
- 🎵 Download complete playlists from Yandex Music
- 🎯 Support for playlist URLs, IDs, and liked tracks
- 🎼 **Multiple format support**: FLAC, MP3, AAC with quality selection
- 🔊 Smart format prioritization with fallback to best available quality
- 📁 Saves all files in a single organized directory with proper extensions
- 📊 Progress indicators and detailed logging
- 🔐 OAuth token authentication support
- 🛡️ Comprehensive error handling and recovery
- ⚡ Rate limiting to avoid API restrictions

### Django Web Interface
- 🌐 Modern responsive web interface with Bootstrap 5
- 👤 User registration and authentication
- 🎵 Playlist preview before downloading
- ☑️ Select individual tracks via checkboxes
- 📊 Real-time progress bars for loading and downloading
- 📂 Browse downloaded playlists and tracks
- 🔄 Pagination support (25/50/100 tracks per page)
- 📥 Direct file downloads from the browser

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package installer)

### Quick Start

Choose between the **Command Line Interface** (simple, no setup) or **Django Web Interface** (feature-rich, requires setup).

---

## Using the Django Web Interface

The Django web interface provides a user-friendly way to manage and download playlists through your browser.

### Installation

#### Step 1: Clone or Download

```bash
git clone https://github.com/m1ckk3y/yandex-music-downloader.git
cd yandex-music-downloader
```

#### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

#### Step 3: Setup Database

```bash
python manage.py migrate
```

#### Step 4: Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

#### Step 5: Run Development Server

```bash
python manage.py runserver
```

The web interface will be available at `http://127.0.0.1:8000/`

### Using the Web Interface

1. **Register an Account**: Navigate to the registration page and create an account
2. **Add Your Token**: Go to your profile and add your Yandex Music OAuth token
3. **Load a Playlist**: Enter a playlist URL to load it
4. **Preview & Select**: View all tracks and select which ones to download using checkboxes
5. **Download**: Click "Download Selected" and watch the real-time progress
6. **View Downloads**: Browse your downloaded playlists and play/download files

### Web Interface Features

- **User Management**: Each user has their own playlists and downloads
- **Playlist Preview**: See all tracks before downloading
- **Track Selection**: Use checkboxes to select specific tracks
- **Progress Tracking**: Real-time progress bars for loading and downloading
- **Pagination**: View 25, 50, or 100 tracks per page
- **Downloaded Library**: Browse and manage all downloaded playlists
- **Direct Downloads**: Download files directly from your browser

---

## Using the Command Line Interface

The CLI provides a simple way to download playlists without setting up a web server.

### Installation

#### Step 1: Clone or Download

```bash
git clone https://github.com/m1ckk3y/yandex-music-downloader.git
cd yandex-music-downloader
```

#### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

#### Step 3: Make Script Executable (Linux/macOS)

```bash
chmod +x yandex_music_downloader.py
```

### CLI Authentication

To access your personal playlists and liked tracks with the CLI, you need a Yandex Music OAuth token.

#### Getting Your Token

1. Visit the [Yandex Music API documentation](https://yandex-music.readthedocs.io/en/main/token.html)
2. Follow the instructions to generate your personal OAuth token
3. Keep your token secure and never share it publicly

#### Setting Up Your Token

You can provide your token in two ways:

##### Option 1: Environment Variable (Recommended)

```bash
# Linux/macOS
export YANDEX_MUSIC_TOKEN="your_token_here"

# Windows
set YANDEX_MUSIC_TOKEN=your_token_here
```

##### Option 2: Command Line Argument

```bash
python yandex_music_downloader.py --token "your_token_here" [playlist]
```

### CLI Usage

#### Basic Usage

```bash
# Download a public playlist
python yandex_music_downloader.py "https://music.yandex.ru/users/username/playlists/123"

# Download using playlist ID format
python yandex_music_downloader.py "username:123"

# Download your liked tracks (requires token)
python yandex_music_downloader.py "liked"
```

#### Advanced Usage

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

#### Command Line Options

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

#### CLI Examples

##### Download a Public Playlist

```bash
python yandex_music_downloader.py "https://music.yandex.ru/users/yamusic-daily/playlists/1036"
```

##### Download Your Liked Tracks

```bash
# Set token first
export YANDEX_MUSIC_TOKEN="your_token_here"
python yandex_music_downloader.py "liked"
```

##### Download to Custom Directory

```bash
python yandex_music_downloader.py "username:123" --output "./MyMusic"
```

##### Download in FLAC Format

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

#### Core Dependencies
- **yandex-music**: Unofficial Yandex Music API client
- **requests**: HTTP library for downloading tracks
- **tqdm**: Progress bar library (CLI)
- **pathlib**: Modern path handling (built-in Python 3.4+)

#### Web Interface Dependencies
- **Django**: Web framework (v5.0+)
- **Pillow**: Image processing
- **Bootstrap 5**: Frontend framework (loaded via CDN)

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

- **v2.0.0**: Django Web Interface
  - Added complete Django web application
  - User registration and authentication
  - Playlist preview with track selection
  - Real-time progress tracking
  - Downloaded playlist management
  - Responsive Bootstrap 5 UI
  - Pagination support
  - Direct file downloads

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
