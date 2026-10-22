import logging
import queue
from threading import Event, Thread

import ttkbootstrap as ttk

from config_manager import ConfigManager
from plex_api import PlexAPI
from scanner import LibraryScanner
from tmdb_api import TMDbAPI
from widgets import ConfigDialog, LogView, PosterGrid, ShowDetailWindow

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

POLL_MS = 100


class PlexMissingSeasonsApp:
    def __init__(self, root):
        self.root = root
        self.config = ConfigManager()
        self._cancel_event = Event()
        self._queue = queue.Queue()
        self._scanning = False
        self.stats = {}

        self.create_ui()
        if not self.config.is_complete():
            self.show_info("Welcome! Open Settings to connect your Plex server and TMDb account.")
            self.root.after(300, self.edit_config)
        self.root.after(POLL_MS, self._process_queue)

    def create_ui(self):
        colors = self.root.style.colors

        # Header: title, stats and actions
        header = ttk.Frame(self.root, padding=(20, 16, 20, 8))
        header.pack(fill="x")
        title_box = ttk.Frame(header)
        title_box.pack(side="left")
        ttk.Label(title_box, text="Plex Season Checker", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(title_box, text="Find missing seasons and episodes in your TV library",
                  bootstyle="light", font=("Segoe UI", 10)).pack(anchor="w")

        ttk.Button(header, text="⚙  Settings", bootstyle="light-outline",
                   command=self.edit_config).pack(side="right", padx=(8, 0))
        self.stop_button = ttk.Button(header, text="Cancel", bootstyle="danger-outline",
                                      command=self.stop_search, state="disabled")
        self.stop_button.pack(side="right", padx=(8, 0))
        self.search_button = ttk.Button(header, text="▶  Scan Library", bootstyle="warning",
                                        command=self.start_search)
        self.search_button.pack(side="right")

        # Stat tiles
        tiles = ttk.Frame(self.root, padding=(16, 4, 16, 8))
        tiles.pack(fill="x")
        self.stat_labels = {}
        for key, label, color in (("shows", "Shows checked", colors.fg),
                                  ("missing", "Missing seasons", colors.danger),
                                  ("episodes", "Missing episodes", colors.warning),
                                  ("complete", "Complete shows", colors.success),
                                  ("error", "Unmatched", colors.light)):
            tile = ttk.Frame(tiles, padding=(14, 8), bootstyle="dark")
            tile.pack(side="left", fill="x", expand=True, padx=4)
            value = ttk.Label(tile, text="0", font=("Segoe UI", 18, "bold"),
                              foreground=color, background=colors.dark)
            value.pack(anchor="w")
            ttk.Label(tile, text=label, font=("Segoe UI", 9), foreground=colors.light,
                      background=colors.dark).pack(anchor="w")
            self.stat_labels[key] = value

        # Progress
        progress = ttk.Frame(self.root, padding=(20, 0, 20, 4))
        progress.pack(fill="x")
        self.progress_bar = ttk.Progressbar(progress, mode="determinate", bootstyle="warning-striped")
        self.progress_bar.pack(fill="x")
        self.status_text = ttk.Label(progress, text="Ready", bootstyle="light", font=("Segoe UI", 9))
        self.status_text.pack(anchor="w", pady=(2, 0))

        # Status bar packs before the notebook so it keeps its space when the window shrinks
        self.status_bar = ttk.Label(self.root, text="", padding=(20, 4), font=("Segoe UI", 9))
        self.status_bar.pack(side="bottom", fill="x")

        self.notebook = ttk.Notebook(self.root, bootstyle="dark")
        self.notebook.pack(expand=True, fill="both", padx=16, pady=(4, 0))
        self.grid_view = PosterGrid(self.notebook, on_select=self.open_show)
        self.log_view = LogView(self.notebook, on_select=self.open_show)
        self.notebook.add(self.grid_view, text="  Library  ")
        self.notebook.add(self.log_view, text="  Log  ")

    # Scanning -------------------------------------------------------------

    def start_search(self):
        """Start a background scan. Results are passed back via self._queue."""
        if self._scanning:
            return
        if not self.config.is_complete():
            self.show_error("Plex and TMDb settings are incomplete.")
            self.edit_config()
            return

        self._scanning = True
        self._cancel_event.clear()
        self.grid_view.clear()
        self.log_view.clear()
        self.stats = dict.fromkeys(self.stat_labels, 0)
        self._update_stats()
        self.search_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.progress_bar.configure(value=0)
        self.status_text.configure(text="Connecting to Plex…")
        self.show_info("")
        Thread(target=self._scan_worker, args=(self.config.get_config(),), daemon=True).start()

    def _scan_worker(self, config):
        """Runs off the UI thread; never touches widgets directly."""
        post = self._queue.put
        try:
            plex_api = PlexAPI(config["server_url"], config["plex_token"])
            shows = plex_api.get_all_shows()
            post(("total", len(shows)))
            scanner = LibraryScanner(plex_api, TMDbAPI(config["tmdb_api_key"]))
            completed = scanner.scan(shows, self._cancel_event, lambda r: post(("result", r)))
            post(("done", completed))
        except Exception as e:
            logging.exception("Scan failed")
            post(("failed", str(e)))

    def stop_search(self):
        """Cancel the ongoing search."""
        self._cancel_event.set()
        self.stop_button.configure(state="disabled")
        self.status_text.configure(text="Cancelling… waiting for in-flight shows to finish")

    def _process_queue(self):
        try:
            for _ in range(25):  # Cap work per tick so the UI stays responsive
                kind, payload = self._queue.get_nowait()
                getattr(self, f"_on_{kind}")(payload)
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._process_queue)

    def _on_total(self, total):
        self.progress_bar.configure(maximum=max(total, 1))
        self.status_text.configure(text=f"Found {total} shows. Checking against TMDb…")
        if not total:
            self.log_view.message("No TV shows found in Plex library")

    def _on_result(self, result):
        self.grid_view.add(result)
        self.log_view.add(result)
        self.stats["shows"] += 1
        self.stats["missing"] += bool(result.missing_seasons)
        self.stats["episodes"] += result.missing_episode_count
        self.stats["complete"] += result.status == "complete"
        self.stats["error"] += result.status == "error"
        self._update_stats()
        self.progress_bar.step(1)
        self.status_text.configure(
            text=f"Checked {result.title} ({self.stats['shows']}/{int(self.progress_bar['maximum'])})")

    def _on_done(self, completed):
        self._finish_scan()
        if completed:
            self.status_text.configure(text="All shows checked!")
            self.show_info("Scan completed.")
        else:
            self.status_text.configure(text="Scan was cancelled")
            self.log_view.message("Scan cancelled by user")
            self.show_info("Scan stopped.")

    def _on_failed(self, message):
        self._finish_scan()
        self.status_text.configure(text="Scan failed")
        self.log_view.message(message)
        self.show_error(message)

    def _finish_scan(self):
        self._scanning = False
        self.grid_view.sort()
        self.search_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def _update_stats(self):
        for key, label in self.stat_labels.items():
            label.configure(text=str(self.stats.get(key, 0)))

    # Dialogs --------------------------------------------------------------

    def open_show(self, result):
        ShowDetailWindow(self.root, result)

    def edit_config(self):
        ConfigDialog(self.root, self.config,
                     on_save=lambda: self.show_info("Settings saved. Ready to scan."))

    def show_error(self, message):
        self.status_bar.configure(text=message, bootstyle="danger")

    def show_info(self, message):
        self.status_bar.configure(text=message, bootstyle="default")


def main():
    root = ttk.Window(title="Plex Season Checker", themename="darkly",
                      size=(1180, 780), minsize=(820, 560))
    PlexMissingSeasonsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
