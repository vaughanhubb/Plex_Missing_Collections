# Plex Season Checker

A Python GUI application that scans your Plex TV library and identifies missing seasons by comparing against TMDB's comprehensive season data.

[Future Enhancements - Hopefully....maybe.....I'll Think About it]
- Identify Missing Episodes
- Identify Missing Movies from Collections
- Improved UI

## Features

- **Automatic Scan**: Iterates through all your Plex TV shows to check for missing seasons
- **Visual Interface**: Clean Tkinter-based GUI with ttkbootstrap styling
- **Progress Tracking**: Real-time progress bar showing scan progress
- **Easy Configuration**: Edit Plex credentials and API keys via Settings menu
- **Cancel Support**: Stop the scan at any time using the Cancel button

## Requirements

- Python 3.8 or higher
- pip
- tkinter (included with standard Python installation)

### Dependencies

Install project dependencies:
```bash
pip install -e .
```

The application requires:
- Plex Media Server API access (requires a [Plex Token](https://plex.tv/api/token))
- TMDb API Key ([Get one here](https://www.themoviedb.org/settings/api))

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/Plex_Missing_Collections.git
   cd Plex_Missing_Collections
   ```

2. Install the project in development mode:
   ```bash
   pip install -e .
   ```

## Configuration

The application uses a `config.json` file (located in the project root) for configuration:

```json
{
  "plex_token": "your-plex-api-token",
  "server_url": "http://localhost:32400",
  "tmdb_api_key": "your-tmdb-api-key"
}
```

### Getting API Keys

1. **Plex Token**: 
   - log in to your Plex Web App, select any individual media item, click Get Info, choose View XML, and copy the value at the very end of the URL where it says X-Plex-Token=

2. **TMDB API Key**:
   - Visit https://www.themoviedb.org/settings/api
   - Sign in and request an API key
   - Accept the terms of use
   - Copy your API key

### Using the Settings Menu

Instead of editing `config.json` directly, you can:
1. Launch the application
2. Go to **Settings** → **Edit Config** menu item
3. Enter or modify the configuration values in the dialog window
4. Click "Save" and the app will automatically apply new config ready for running search

## Usage

### Running the Application

Start the application using:
```bash
python src/main.py
```

### After Launch

1. Configure your Plex connection via **Settings** → **Edit Config**
2. Click **"Search for Missing Seasons"** to begin scanning
3. View results in the main window showing each show and its missing seasons
4. Use the progress bar to track scan progress
5. Click **"Cancel Search for Missing Seasons"** to stop at any time

### Viewing Results

The application displays:
- Show name with missing seasons (e.g., "Breaking Bad: Missing Season 4")
- Error messages if a show cannot be checked
- Overall completion status at the bottom

## Project Structure

```
Plex_Missing_Collections/
├── src/
│   ├── main.py           # Main application entry point
│   ├── plex_api.py       # Plex API wrapper and season checking logic
│   └── config_manager.py # Configuration file handler
├── config.json           # User configuration (credentials)
├── pyproject.toml        # Project metadata and dependencies
└── README.md             # This file
```

## License

MIT License