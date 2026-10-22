"""Application settings.

Non-secret settings live in a JSON file in the per-user config directory
(e.g. %APPDATA%\\PlexMissingCollections\\settings.json on Windows,
~/.config/PlexMissingCollections/settings.json on Linux). Secrets (the Plex
token and TMDb key) are stored in the OS credential store via keyring, falling
back to the settings file only if no credential store is available.
"""
import json
import logging
from pathlib import Path

from platformdirs import user_config_dir

try:
    import keyring
    from keyring.errors import KeyringError
except ImportError:  # keyring is optional at runtime
    keyring = None
    KeyringError = Exception

APP_NAME = "PlexMissingCollections"
SECRET_KEYS = ("plex_token", "tmdb_api_key")
DEFAULTS = {
    "server_url": "http://localhost:32400",
    "plex_token": "",
    "tmdb_api_key": "",
}
# Pre-2.0 versions kept config.json in the project root
LEGACY_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

log = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_dir=None):
        self.config_dir = Path(config_dir or user_config_dir(APP_NAME, appauthor=False))
        self.config_path = self.config_dir / "settings.json"
        self._migrate_legacy_config()

    def get_config(self):
        """Return all settings, including secrets, merged over the defaults."""
        config = {**DEFAULTS, **self._read_file()}
        for key in SECRET_KEYS:
            secret = self._get_secret(key)
            if secret is not None:
                config[key] = secret
        return config

    def set_config(self, config):
        """Persist settings, routing secrets to the credential store where possible."""
        file_data = {k: v for k, v in config.items() if k not in SECRET_KEYS}
        for key in SECRET_KEYS:
            if key in config and not self._set_secret(key, config[key]):
                file_data[key] = config[key]
        self._write_file(file_data)

    def is_complete(self):
        config = self.get_config()
        return all(config.get(k) for k in DEFAULTS)

    @property
    def secrets_backend(self):
        """Human readable description of where secrets are stored."""
        return "OS credential store" if self._keyring_usable() else str(self.config_path)

    def _read_file(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write_file(self, data):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _keyring_usable(self):
        if keyring is None:
            return False
        backend = keyring.get_keyring()
        return getattr(backend, "priority", 0) > 0 and "fail" not in type(backend).__module__

    def _get_secret(self, key):
        if not self._keyring_usable():
            return None
        try:
            return keyring.get_password(APP_NAME, key)
        except KeyringError as e:
            log.warning("Could not read %s from credential store: %s", key, e)
            return None

    def _set_secret(self, key, value):
        """Store a secret in the credential store. Returns False if unavailable."""
        if not self._keyring_usable():
            return False
        try:
            if value:
                keyring.set_password(APP_NAME, key, value)
            elif keyring.get_password(APP_NAME, key) is not None:
                keyring.delete_password(APP_NAME, key)
            return True
        except KeyringError as e:
            log.warning("Could not store %s in credential store: %s", key, e)
            return False

    def _migrate_legacy_config(self):
        """Move settings from the old project-root config.json on first run."""
        if self.config_path.exists() or not LEGACY_CONFIG_PATH.exists():
            return
        try:
            with open(LEGACY_CONFIG_PATH, "r", encoding="utf-8") as f:
                legacy = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        self.set_config({k: legacy.get(k, v) for k, v in DEFAULTS.items()})
        log.info("Migrated legacy %s to %s; the old file can now be deleted",
                 LEGACY_CONFIG_PATH, self.config_path)
