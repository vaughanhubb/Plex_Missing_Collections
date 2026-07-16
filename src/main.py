import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from threading import Thread, Event
from plex_api import PlexAPI
from config_manager import ConfigManager
import os

# Get the workspace folder and project root
workspace_folder = os.path.dirname(os.path.abspath(__file__))


class PlexMissingSeasonsApp:
    def __init__(self, root):
        self._cancel_event = Event()  # Use Event for thread-safe cancellation signal
        self.root = root
        self.root.title("Plex Season Checker")
        self.root.geometry("1000x600")
        self.root.resizable(True, True)

        self.create_ui()
        try:
            self.config = ConfigManager()
            config_data = self.config.get_config()
            self.plex_token = config_data.get("plex_token")
            self.server_url = config_data.get("server_url")
            self.tmdb_api_key = config_data.get("tmdb_api_key")

            if self.plex_token != "":
                self.plex_api = PlexAPI(
                    server_url=self.server_url,
                    token=self.plex_token,
                    tmdb_api_key=self.tmdb_api_key
                )
        except Exception as e:
            self.show_error(f"Failed to load config: {str(e)}")
            return

    def create_ui(self):
        # Create settings menu
        self.menu_bar = tk.Menu(self.root)
        self.settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.settings_menu.add_command(label="Edit Config", command=self.edit_config)
        self.menu_bar.add_cascade(label="Settings", menu=self.settings_menu)
        self.root.config(menu=self.menu_bar)

        # Main display Initialisation
        self.notebook = ttk.Notebook(self.root, style="vapor")
        self.shows_frame = tk.Frame(self.notebook)
        self.stats_frame = tk.Frame(self.notebook)
        self.notebook.add(self.shows_frame, text="Shows")
        self.notebook.pack(expand=True, fill='both')
        self.show_listbox = tk.Listbox(self.shows_frame)
        self.show_listbox.pack(fill='both', expand=True)
        self.stats_text = ttk.Text(self.stats_frame, wrap='word')
        self.stats_text.insert(tk.END, "Status: Ready")
        self.stats_text.pack(fill='both', expand=True)
        self.status_bar = ttk.Label(self.root, text="", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        # Start Search Button
        self.search_button = ttk.Button(
            self.root,
            bootstyle=DARK,
            text="Search for Missing Seasons",
            command=self.start_search
        )
        self.search_button.pack(pady=5)

        # Cancel Run Button
        self.stop_button = ttk.Button(
            self.root,
            bootstyle=DANGER,
            text="Cancel Search for Missing Seasons",
            command=self.stop_search,
            state=tk.DISABLED
        )
        self.stop_button.pack(pady=5)

        # Progress bar for showing search progress
        self.progress_bar = ttk.Progressbar(self.root, mode='determinate')
        self.status_text = tk.Label(
            self.root,
            text="",
            anchor=tk.W
        )
        self.progress_bar.pack_forget()
        self.status_text.pack_forget()

    def stop_search(self):
        """Cancel the ongoing search for missing seasons."""
        self._cancel_event.set()
        self.show_info("Stopping search...")

    def start_search(self):
        """Trigger the search for missing seasons with loading indicator."""
        if not hasattr(self, "plex_api") or not self.plex_api:
            self.show_error("Plex connection not initialized. Refresh config first.")
            return
        
        self.show_listbox.delete(0, tk.END)
        self.stats_text.delete(1.0, tk.END)

        # Show progress bar and status text
        self.search_button.config(state=tk.DISABLED)
        self.progress_bar.pack(fill='x', padx=5, pady=5)
        self.status_text.pack(fill='x', padx=5)
        self.status_text.config(text="Starting season check...")

        def search_wrapper():
            """Wrapper to run async function in thread using asyncio."""
            try:
                import asyncio
                self.stop_button.config(state=tk.NORMAL)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.run_search())
            except Exception as e:
                self.show_error(f"Error during search: {str(e)}")
            finally:
                # Hide progress bar and re-enable button in finally block
                self.progress_bar.pack_forget()
                self.status_text.pack_forget()

        Thread(target=search_wrapper, daemon=True).start()

    async def run_search(self):
        """Actually perform the season check asynchronously."""
        try:
            shows = self.plex_api.get_all_shows()
            total_shows = len(shows)
            
            self.progress_bar['value'] = 1
            
            for idx, show in enumerate(shows):
                if self._cancel_event.is_set():    
                    print("Search cancelled by user")
                    break
                
                # Update progress bar as each show is checked (fills from 1% to ~99%)
                completion = (idx + 1) / total_shows * 99
                self.progress_bar['value'] = completion
                self.status_text.config(text=f"Checking {show['show_name']} ({idx+1}/{total_shows})")
                self.root.update_idletasks()

                details = self.plex_api.check_missing_seasons(show)
                
                if self._cancel_event.is_set():
                    print("Search cancelled by user")
                    break
                
                if 'error' in details:
                    self.show_listbox.insert(tk.END, f"{show['show_name']} - {details['error']}")
                else:
                    if details.get('missing'):
                        formatted_missing = ", ".join([f"Season {s}" for s in details['missing']])
                        self.show_listbox.insert(tk.END, f"{show['show_name']}: Missing {formatted_missing}")
            
            # End of search (normal completion or cancelled)
            if self._cancel_event.is_set():
                self.status_text.config(text="Search was cancelled by user")
                self.show_info("Search stopped.")
                self._cancel_event.clear()
            else:
                self.status_text.config(text="All shows checked!")
        except Exception as e:
            self.show_error(f"Error during season check: {str(e)}")
        finally:
            # Hide progress bar and re-enable button
            self.progress_bar.pack_forget()
            self.status_text.pack_forget()
            self.show_info("Search completed.")
            self.search_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def load_shows(self):
        """Only show shows that have missing seasons."""
        try:
            shows = self.plex_api.get_all_shows()
            if not shows:
                self.show_listbox.insert(tk.END, "No TV shows found in Plex library")
                return

            for show in shows:
                # Call API to check missing seasons
                missing_seasons = self.plex_api.check_missing_seasons(show)
                
                # Only add to list if there are missing seasons
                if 'error' in missing_seasons:
                    self.show_listbox.insert(tk.END, f"{show['name']} - {missing_seasons['error']}")
                else:
                    if missing_seasons.get('missing'):
                        # Format seasons as "Season 1, Season 2" instead of ["1", "2"]
                        formatted_missing = ", ".join([f"Season {s}" for s in missing_seasons['missing']])
                        self.show_listbox.insert(tk.END, f"{show['name']}: Missing {formatted_missing}")
                    else:
                        # Show has all seasons
                        pass

        except Exception as e:
            self.show_error(f"Failed to load shows: {str(e)}")

    def edit_config(self):
        # Create a new dialog window for editing configuration
        config_window = tk.Toplevel(self.root)
        config_window.title("Edit Configuration")
        config_window.geometry("500x350")

        # Labels and input fields for Plex Token, Server URL, and TMDB API Key
        tk.Label(config_window, text="Plex Token:").pack(pady=5)
        token_entry = tk.Entry(config_window, width=60, show='*')
        token_entry.pack(pady=5)

        tk.Label(config_window, text="Server URL:").pack(pady=5)
        url_entry = tk.Entry(config_window, width=60)
        url_entry.pack(pady=5)

        tk.Label(config_window, text="TMDb API Key (https://www.themoviedb.org/settings/api):").pack(pady=5)
        tmdb_api_key_entry = tk.Entry(config_window, width=60)
        tmdb_api_key_entry.pack(pady=5)

        # Load current config values into the input fields
        config_data = self.config.get_config()
        token_entry.insert(0, config_data.get("plex_token", ""))
        url_entry.insert(0, config_data.get("server_url", ""))
        tmdb_api_key_entry.insert(0, config_data.get("tmdb_api_key", ""))

        def save_config():
            new_token = token_entry.get().strip()
            new_url = url_entry.get().strip()
            new_tmdb_api_key = tmdb_api_key_entry.get().strip()

            if not new_token or not new_url or not new_tmdb_api_key:
                messagebox.showerror("Error", "All fields are required")
                return

            # Update the config with new values
            self.config.set_config({
                "plex_token": new_token,
                "server_url": new_url,
                "tmdb_api_key": new_tmdb_api_key
            })
            messagebox.showinfo("Success", "Configuration saved successfully")
            config_window.destroy()
            self.refresh_config()  # Refresh app automatically after Config saved

        save_button = tk.Button(config_window, text="Save", command=save_config)
        save_button.pack(pady=10)

        config_window.bind("<Escape>", lambda e: config_window.destroy())

    def refresh_config(self):
        """Reloads the configuration and reconnects to Plex."""
        try:
            self.config = ConfigManager()
            config_data = self.config.get_config()
            self.plex_token = config_data.get("plex_token")
            self.server_url = config_data.get("server_url")
            self.tmdb_api_key = config_data.get("tmdb_api_key")

            self.plex_api = PlexAPI(
                server_url=self.server_url,
                token=self.plex_token,
                tmdb_api_key=self.tmdb_api_key
            )
            self.show_info("Configuration reloaded successfully.")
        except Exception as e:
            self.show_error(f"Failed to refresh config: {str(e)}")

    def show_error(self, message):
        self.status_bar.config(text=message, foreground="red")

    def show_info(self, message):
        self.status_bar.config(text=message, foreground="white")

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(theme="darkly")
    app = PlexMissingSeasonsApp(root)
    root.mainloop()