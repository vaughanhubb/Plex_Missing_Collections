import re
import requests
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
import json
from datetime import datetime

class PlexAPI:
    def __init__(self, server_url, token, tmdb_api_key):
        self.server_url = server_url
        self.token = token
        self.tmdb_api_key = tmdb_api_key
        self.plex = self.connect_to_plex()

    def connect_to_plex(self):
        """Connect to the Plex server with provided credentials."""
        try:
            return PlexServer(self.server_url, self.token)
        except Exception as e:
            print(f"Failed to connect to Plex: {e}")
            raise ConnectionError(f"Plex connection failed: {e}")

    def get_all_shows(self):
        """Get all TV shows from the Plex library."""
        if not self.plex:
            print("Plex API connection is not available")
            return []
        
        try:
            shows = []
            for section in self.plex.library.sections():
                if section and section.type == "show":
                    for show in section.all():
                        if show and hasattr(show, 'title'):
                            # Clean up show title to remove season/year formatting
                            cleaned_title = self.clean_show_title(show.title)
                            shows.append({
                                "show_name": show.title,
                                "tmdb_show_name": cleaned_title,
                                "year": show.year,
                                "key": str(show.key)  # Store key to get seasons later
                            })
            return shows
        except Exception as e:
            print(f"Failed to retrieve TV shows: {e}")
            return []

    def clean_show_title(self, title):
        """Clean show titles by removing season numbers and year formatting."""
        cleaned = re.sub(r'[^a-zA-Z\s]+$', '', title)
        cleaned = re.sub(r"\([0-9]+\)", '', cleaned).strip()
        cleaned = re.sub(r"!", '', cleaned).strip()
        cleaned = re.sub(r'Season \d+', '', cleaned).strip()
        return cleaned

    def search_tmdb_for_show(self, show_name, year=None):
        """Search TMDb for a TV show by name."""
        base_url = "https://api.themoviedb.org/3"
        url = f"{base_url}/search/tv?api_key={self.tmdb_api_key}&query={show_name}"
        if year:
            url += f"&year={year}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("results") and len(data["results"]) > 0:
                tmdb_id = data["results"][0].get("id")
                # print(f"Found TMDb ID for '{show_name}': {tmdb_id}")  # ✅ Debug log
                return tmdb_id
            else:
                print(f"No TMDb match found for '{show_name}'")  # ✅ Debug log
                return None

        except Exception as e:
            print(f"TMDb search error: {e}")
            return None

    def get_total_released_seasons_from_tmdb(self, tmdb_id):
        """Get the number of released seasons from TMDb using air dates and episode count."""
        base_url = "https://api.themoviedb.org/3"
        url = f"{base_url}/tv/{tmdb_id}?api_key={self.tmdb_api_key}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # Log all seasons for debugging
            print(f"\n--- TMDb Seasons Info for Show ID: {tmdb_id} ---")
            for season in data.get("seasons", []):
                air_date = season.get("air_date")
                episode_count = season.get("episode_count")
                name = season.get("name")

            # Count seasons that have an air date in the past AND have episodes
            total_released_seasons = 0
            for season in data.get("seasons", []):
                air_date = season.get("air_date")
                episode_count = season.get("episode_count")
                name = season.get("name")

                if air_date and episode_count > 0 and name != "Specials":
                    try:
                        parsed_air_date = datetime.strptime(air_date, "%Y-%m-%d")
                        # Only count seasons that have aired in the past or are currently airing
                        if parsed_air_date <= datetime.now():
                            total_released_seasons += 1
                    except ValueError:
                        # Invalid date format — skip this season
                        continue

            return total_released_seasons

        except Exception as e:
            print(f"TMDb season count error: {e}")
            return 0

    def check_missing_seasons(self, show):
        """Check which seasons are missing for a specific TV show using TMDb (only released seasons)."""
        try:
            # Find the exact show (using name + key)
            tmdb_id = self.search_tmdb_for_show(show['tmdb_show_name'], show['year'])

            if not tmdb_id:
                return {"error": f"Show '{show['tmdb_show_name']}' not found on Plex or TMDb."}

            total_released_seasons = self.get_total_released_seasons_from_tmdb(tmdb_id)

            # If no seasons are expected, skip
            if total_released_seasons == 0:
                print(f"No released seasons found for '{show['tmdb_show_name']}': TMDb data may be incomplete or future-only.")  # ✅ Debug log
                return {"error": f"TMDb has no data on released seasons for '{show['tmdb_show_name']}'."}

            # Get existing seasons from Plex
            for section in self.plex.library.sections():
                if section and section.type == "show":
                    for shw in section.all():
                        if shw.title == show['show_name']:
                            existing_seasons = set()
                            for episode in shw.episodes():
                                existing_seasons.add(episode.seasonNumber)

                            missing_seasons = [str(season) for season in range(1, total_released_seasons + 1) if season not in existing_seasons]

                            return {
                                "show": show['show_name'],
                                "missing": sorted(missing_seasons),
                                "total": total_released_seasons
                            }

            # If the show was not found on Plex
            print(f"Show '{show['show_name']}' not found in Plex library.")  # ✅ Debug log
            return {"error": f"Show '{show['show_name']}' not found in Plex library"}

        except Exception as e:
            print(f"Error checking missing seasons for {show['show_name']}: {e}")
            return {"error": str(e)}