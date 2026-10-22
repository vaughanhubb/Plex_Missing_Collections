import re
from collections import defaultdict

import requests
from plexapi.server import PlexServer


class PlexAPI:
    def __init__(self, server_url, token, timeout=30):
        self.server_url = server_url
        self.token = token
        self.timeout = timeout
        self.plex = self.connect_to_plex()

    def connect_to_plex(self):
        """Connect to the Plex server with provided credentials."""
        try:
            return PlexServer(self.server_url, self.token, timeout=self.timeout)
        except Exception as e:
            raise ConnectionError(f"Plex connection failed: {e}") from e

    def get_all_shows(self):
        """Get every show from all TV libraries on the server."""
        shows = []
        for section in self.plex.library.sections():
            if section.type == "show":
                shows.extend(section.all())
        return sorted(shows, key=lambda s: (s.titleSort or s.title).lower())

    @staticmethod
    def get_owned_episodes(show):
        """Map season number -> set of episode numbers present on Plex."""
        owned = defaultdict(set)
        for episode in show.episodes():
            if episode.seasonNumber is not None and episode.index is not None:
                owned[episode.seasonNumber].add(episode.index)
        return dict(owned)

    @staticmethod
    def get_tmdb_id(show):
        """TMDb ID from the show's Plex metadata guids, if the agent provided one."""
        for guid in getattr(show, "guids", None) or []:
            if guid.id.startswith("tmdb://"):
                try:
                    return int(guid.id.removeprefix("tmdb://"))
                except ValueError:
                    pass
        return None

    @staticmethod
    def clean_show_title(title):
        """Strip trailing year / country tags, e.g. 'The Office (US)' or 'Doctor Who (2005)'."""
        return re.sub(r"\s*\((\d{4}|[A-Z]{2,3})\)\s*$", "", title).strip() or title

    def fetch_poster(self, show, width, height):
        """Download a show's poster, resized by the Plex transcoder. Returns bytes or None."""
        if not show.thumb:
            return None
        url = self.plex.transcodeImage(show.thumb, height=height, width=width)
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.content
