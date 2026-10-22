# Plex Season Checker

A Python GUI application that scans your Plex TV library and identifies missing seasons **and missing episodes** by comparing against TMDb's season and episode data.

[Future Enhancements - Hopefully....maybe.....I'll Think About it]
- Identify Missing Movies from Collections

## Features

- **Missing seasons and episodes**: Every show is compared season by season against TMDb. Only seasons and episodes that have already aired are counted, and specials (Season 0) are ignored
- **Poster library view**: Shows appear as a grid of their Plex posters. Badges summarise what is missing, and hovering over a poster shows a badge for each missing season (red) and each season with missing episodes (amber)
- **Show details**: Click a poster to see every season with its status. Seasons with gaps expand to list each missing episode with its title and air date
- **Log tab**: A colour-coded list of every show checked and its result. Double-click a row to open its details
- **Search and filters**: Filter the library by title or by status (missing seasons, missing episodes, complete, unmatched)
- **Fast, responsive scanning**: Shows are checked in parallel in the background, with a progress bar and the option to cancel
- **Accurate matching**: Uses the TMDb ID stored in your Plex metadata where available, and falls back to a title search otherwise
- **Secure settings**: Credentials are kept in your OS credential store (Windows Credential Manager, macOS Keychain or Secret Service on Linux)

## Requirements

- Python 3.9 or higher
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

Open **⚙ Settings** in the app (it opens automatically on first launch) and enter:

| Setting | Description |
|---|---|
| Plex server URL | e.g. `http://localhost:32400` |
| Plex token | See below |
| TMDb API key | Either the v3 API key or the v4 read access token |

### Where settings are stored

- **Server URL**: `settings.json` in your per-user config directory
  - Windows: `%LOCALAPPDATA%\PlexMissingCollections\settings.json`
  - macOS: `~/Library/Application Support/PlexMissingCollections/settings.json`
  - Linux: `~/.config/PlexMissingCollections/settings.json`
- **Plex token and TMDb key**: your OS credential store, under the service name `PlexMissingCollections`. If no credential store is available, they fall back to `settings.json`.

If a `config.json` from an earlier version exists in the project root, it is imported automatically on first launch. After that it is no longer used and can be deleted.

### Getting API Keys

1. **Plex Token**: 
   - log in to your Plex Web App, select any individual media item, click Get Info, choose View XML, and copy the value at the very end of the URL where it says X-Plex-Token=

2. **TMDB API Key**:
   - Visit https://www.themoviedb.org/settings/api
   - Sign in and request an API key
   - Accept the terms of use
   - Copy your API key

## Usage

### Running the Application

Start the application using:
```bash
python src/main.py
```

Or, after `pip install -e .`, run:
```bash
plex-season-checker
```

### After Launch

1. Configure your Plex connection via **⚙ Settings**
2. Click **▶ Scan Library** to begin scanning
3. Watch posters appear in the **Library** tab as each show is checked. The stat tiles keep running totals
4. Hover over a poster to see its missing seasons and episodes, then click it for the full breakdown
5. Switch to the **Log** tab for a list view of every result
6. Click **Cancel** to stop at any time

### Known limitations

- Comparisons use TMDb's default episode order. Shows that Plex orders differently (e.g. absolute or DVD order for some anime) may report false gaps
- A multi-episode file (e.g. `S01E01-E02`) is indexed by Plex under its first episode only, so the second episode may be reported as missing

## Project Structure

```
Plex_Missing_Collections/
├── src/
│   ├── main.py           # Application window, scan orchestration
│   ├── widgets.py        # Poster grid, log view, show detail and settings dialogs
│   ├── artwork.py        # Poster card / hover overlay rendering (Pillow)
│   ├── scanner.py        # Compares Plex against TMDb per show
│   ├── models.py         # Show / season / episode result types
│   ├── plex_api.py       # Plex server access
│   ├── tmdb_api.py       # TMDb API client
│   └── config_manager.py # Settings file + OS credential store
├── pyproject.toml        # Project metadata and dependencies
└── README.md             # This file
```

## License

MIT License