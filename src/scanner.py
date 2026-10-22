import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import artwork
from models import Episode, Season, ShowResult
from plex_api import PlexAPI

log = logging.getLogger(__name__)


class LibraryScanner:
    """Compares each Plex show against TMDb to find missing seasons and episodes."""

    def __init__(self, plex_api, tmdb_api, workers=4):
        self.plex = plex_api
        self.tmdb = tmdb_api
        self.workers = workers

    def scan(self, shows, cancel_event, on_result):
        """Scan shows concurrently, calling on_result(ShowResult) as each finishes.

        Returns True if the scan ran to completion, False if it was cancelled.
        """
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = [executor.submit(self.scan_show, show) for show in shows]
            for future in as_completed(futures):
                if cancel_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    return False
                on_result(future.result())
        return True

    def scan_show(self, show):
        result = ShowResult(
            title=show.title,
            year=show.year,
            rating_key=str(show.ratingKey),
            summary=show.summary or "",
        )
        try:
            self._compare_with_tmdb(show, result)
        except Exception as e:
            log.exception("Error checking %s", show.title)
            result.error = f"Error: {e}"
        self._render_artwork(show, result)
        return result

    def _compare_with_tmdb(self, show, result):
        owned = PlexAPI.get_owned_episodes(show)
        result.tmdb_id = PlexAPI.get_tmdb_id(show) or self.tmdb.search_show(
            PlexAPI.clean_show_title(show.title), show.year
        )
        if not result.tmdb_id:
            result.error = "No TMDb match found"
            return

        regular_owned = {n for n in owned if n > 0}  # Season 0 is specials
        details, season_details = self.tmdb.get_show(result.tmdb_id, regular_owned)
        today = date.today().isoformat()

        for tmdb_season in details.get("seasons", []):
            number = tmdb_season["season_number"]
            name = tmdb_season.get("name") or f"Season {number}"
            if number == 0:
                continue
            if number in owned:
                aired = [
                    Episode(ep["episode_number"], ep.get("name") or "", ep["air_date"])
                    for ep in season_details.get(number, {}).get("episodes", [])
                    if ep.get("air_date") and ep["air_date"] <= today
                ]
                result.seasons.append(Season(
                    number=number,
                    name=name,
                    aired_count=len(aired),
                    owned_count=len(owned[number]),
                    missing_episodes=[ep for ep in aired if ep.number not in owned[number]],
                ))
            elif tmdb_season.get("air_date") and tmdb_season["air_date"] <= today \
                    and tmdb_season.get("episode_count"):
                result.seasons.append(Season(number, name, aired_count=tmdb_season["episode_count"]))

        # Seasons on Plex that TMDb doesn't know about (e.g. different season ordering)
        known = {s.number for s in result.seasons}
        for number in sorted(regular_owned - known):
            result.seasons.append(Season(number, f"Season {number}", len(owned[number]), len(owned[number])))
        result.seasons.sort(key=lambda s: s.number)

        if not result.seasons:
            result.error = "TMDb has no released seasons for this show"

    def _render_artwork(self, show, result):
        """Fetch the poster and pre-render card images off the UI thread."""
        try:
            data = self.plex.fetch_poster(show, *artwork.DETAIL_SIZE)
        except Exception as e:
            log.warning("Poster download failed for %s: %s", show.title, e)
            data = None
        result.poster = artwork.load_poster(data, show.title)
        result.card_image = artwork.render_card(result.poster, result)
        result.hover_image = artwork.render_hover(result.poster, result)
