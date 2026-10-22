import time

import requests

BASE_URL = "https://api.themoviedb.org/3"
MAX_APPEND = 20  # TMDb's limit on append_to_response entries per request


class TMDbAPI:
    def __init__(self, api_key, timeout=15):
        self.timeout = timeout
        self.session = requests.Session()
        # v3 API keys go in the query string; v4 read access tokens (JWTs) go in a header
        if api_key.startswith("eyJ"):
            self.session.headers["Authorization"] = f"Bearer {api_key}"
            self._auth_params = {}
        else:
            self._auth_params = {"api_key": api_key}

    def _get(self, path, **params):
        """GET a TMDb endpoint, backing off briefly if rate limited."""
        params = {**self._auth_params, **params}
        for attempt in range(3):
            response = self.session.get(f"{BASE_URL}{path}", params=params, timeout=self.timeout)
            if response.status_code != 429:
                break
            time.sleep(float(response.headers.get("Retry-After", 1 + attempt)))
        response.raise_for_status()
        return response.json()

    def search_show(self, title, year=None):
        """Return the TMDb ID of the best match for a show title, or None."""
        attempts = [{"query": title, "first_air_date_year": year}] if year else []
        attempts.append({"query": title})
        for params in attempts:
            results = self._get("/search/tv", **params).get("results")
            if results:
                return results[0]["id"]
        return None

    def get_show(self, tmdb_id, season_numbers=()):
        """Fetch show details plus full episode lists for the requested seasons.

        Returns (details, {season_number: season_details}).
        """
        seasons = sorted(set(season_numbers))
        appended, extra = seasons[:MAX_APPEND], seasons[MAX_APPEND:]
        details = self._get(
            f"/tv/{tmdb_id}",
            append_to_response=",".join(f"season/{n}" for n in appended) or None,
        )
        season_details = {n: details.pop(f"season/{n}", {}) for n in appended}
        for n in extra:
            season_details[n] = self._get(f"/tv/{tmdb_id}/season/{n}")
        return details, season_details
