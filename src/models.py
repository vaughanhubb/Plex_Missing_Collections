from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Episode:
    number: int
    title: str
    air_date: Optional[str]


@dataclass
class Season:
    number: int
    name: str
    aired_count: int        # Episodes TMDb reports as aired
    owned_count: int = 0    # Episodes present on Plex
    missing_episodes: list = field(default_factory=list)

    @property
    def in_library(self):
        return self.owned_count > 0

    @property
    def status(self):
        if not self.in_library:
            return "missing"
        return "partial" if self.missing_episodes else "complete"


@dataclass
class ShowResult:
    title: str
    year: Optional[int]
    rating_key: str
    tmdb_id: Optional[int] = None
    summary: str = ""
    seasons: list = field(default_factory=list)
    error: Optional[str] = None
    poster: object = None   # PIL.Image, rendered by the scanner thread
    card_image: object = None
    hover_image: object = None

    @property
    def missing_seasons(self):
        return [s for s in self.seasons if s.status == "missing"]

    @property
    def incomplete_seasons(self):
        return [s for s in self.seasons if s.status == "partial"]

    @property
    def missing_episode_count(self):
        return sum(len(s.missing_episodes) for s in self.incomplete_seasons)

    @property
    def status(self):
        if self.error:
            return "error"
        if self.missing_seasons:
            return "missing"
        if self.incomplete_seasons:
            return "partial"
        return "complete"

    def describe(self):
        """One-line human readable description of what's missing."""
        if self.error:
            return self.error
        parts = []
        if self.missing_seasons:
            parts.append("Missing " + ", ".join(f"Season {s.number}" for s in self.missing_seasons))
        if self.incomplete_seasons:
            per_season = ", ".join(f"S{s.number}: {len(s.missing_episodes)}" for s in self.incomplete_seasons)
            parts.append(f"{self.missing_episode_count} missing episode(s) ({per_season})")
        return " | ".join(parts) or "Complete"
