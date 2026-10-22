import tkinter as tk
import webbrowser

import ttkbootstrap as ttk
from PIL import ImageTk

import artwork

STATUS_LABELS = {
    "missing": "Missing seasons",
    "partial": "Missing episodes",
    "complete": "Complete",
    "error": "Unmatched",
}
STATUS_STYLES = {"missing": "danger", "partial": "warning", "complete": "success", "error": "light"}


def bind_mousewheel(container, target):
    """Scroll `target` with the mouse wheel while the pointer is over `container` or its children."""
    prefix = str(container)

    def on_wheel(event):
        if not str(event.widget).startswith(prefix):
            return
        if event.num == 4 or event.delta > 0:
            target.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            target.yview_scroll(1, "units")

    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        container.bind_all(sequence, on_wheel, add="+")


class ShowCard(ttk.Frame):
    """A poster tile that swaps to an overlay of missing seasons on hover."""

    def __init__(self, master, result, on_click):
        super().__init__(master, padding=6)
        self.result = result
        self._card = ImageTk.PhotoImage(result.card_image)
        self._hover = ImageTk.PhotoImage(result.hover_image)

        self.poster = ttk.Label(self, image=self._card, cursor="hand2")
        self.poster.pack()
        title = result.title if len(result.title) <= 22 else result.title[:21] + "…"
        self.title = ttk.Label(self, text=title, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.title.pack(anchor="w", pady=(4, 0))
        self.subtitle = ttk.Label(self, text=self._subtitle(), font=("Segoe UI", 9),
                                  bootstyle=STATUS_STYLES[result.status])
        self.subtitle.pack(anchor="w")

        for widget in (self, self.poster, self.title, self.subtitle):
            widget.bind("<Enter>", lambda _: self.poster.configure(image=self._hover), add="+")
            widget.bind("<Leave>", lambda _: self.poster.configure(image=self._card), add="+")
            widget.bind("<Button-1>", lambda _: on_click(result))

    def _subtitle(self):
        year = f"{self.result.year} · " if self.result.year else ""
        return year + STATUS_LABELS[self.result.status]


class PosterGrid(ttk.Frame):
    """Scrollable, reflowing grid of ShowCards with search and status filters."""

    FILTERS = (("All", None), ("Missing seasons", "missing"), ("Missing episodes", "partial"),
               ("Complete", "complete"), ("Unmatched", "error"))

    def __init__(self, master, on_select):
        super().__init__(master)
        self.on_select = on_select
        self.cards = []
        self._columns = 0

        toolbar = ttk.Frame(self, padding=(10, 10, 10, 4))
        toolbar.pack(fill="x")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.reflow())
        ttk.Label(toolbar, text="Search", bootstyle="light").pack(side="left", padx=(0, 8))
        ttk.Entry(toolbar, textvariable=self.search_var, width=30).pack(side="left")

        self.filter_var = tk.StringVar(value="All")
        for label, _ in reversed(self.FILTERS):
            ttk.Radiobutton(toolbar, text=label, value=label, variable=self.filter_var,
                            bootstyle="info-outline-toolbutton",
                            command=self.reflow).pack(side="right", padx=1)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, highlightthickness=0, bd=0,
                                background=ttk.Style().colors.bg)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview,
                                  bootstyle="round")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = ttk.Frame(self.canvas, padding=8)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_resize)
        bind_mousewheel(self.canvas, self.canvas)

        self.empty_label = ttk.Label(self.inner, font=("Segoe UI", 12), bootstyle="light",
                                     text="Run a scan to see your TV library here.")
        self.empty_label.grid(row=0, column=0, padx=20, pady=40)

    def clear(self):
        for card in self.cards:
            card.destroy()
        self.cards.clear()
        self.reflow()

    def add(self, result):
        card = ShowCard(self.inner, result, self.on_select)
        self.cards.append(card)
        if self._matches(card):
            self._place(card, sum(1 for c in self.cards if c.winfo_manager()))
            self.empty_label.grid_remove()

    def sort(self):
        self.cards.sort(key=lambda c: c.result.title.lower())
        self.reflow()

    def _matches(self, card):
        wanted = dict(self.FILTERS)[self.filter_var.get()]
        query = self.search_var.get().strip().lower()
        return (wanted is None or card.result.status == wanted) \
            and (not query or query in card.result.title.lower())

    def _place(self, card, index):
        columns = max(self._columns, 1)
        card.grid(row=index // columns, column=index % columns, sticky="n")

    def reflow(self):
        visible = [c for c in self.cards if self._matches(c)]
        for card in self.cards:
            card.grid_forget()
        for i, card in enumerate(visible):
            self._place(card, i)
        if visible:
            self.empty_label.grid_remove()
        else:
            self.empty_label.configure(text="No shows match this filter." if self.cards
                                       else "Run a scan to see your TV library here.")
            self.empty_label.grid(row=0, column=0, padx=20, pady=40)
        self.canvas.yview_moveto(0)

    def _on_resize(self, event):
        card_width = artwork.CARD_SIZE[0] + 12
        columns = max(1, (event.width - 16) // card_width)
        if columns != self._columns:
            self._columns = columns
            self.reflow()


class LogView(ttk.Frame):
    """Tabular log of every show checked, colour coded by status."""

    def __init__(self, master, on_select):
        super().__init__(master, padding=10)
        self.results = {}
        columns = ("show", "status", "details")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", bootstyle="dark")
        for col, text, width, stretch in (("show", "Show", 260, False),
                                          ("status", "Status", 140, False),
                                          ("details", "Details", 500, True)):
            self.tree.heading(col, text=text, anchor="w")
            self.tree.column(col, width=width, stretch=stretch, anchor="w")
        colors = ttk.Style().colors
        for status, style in STATUS_STYLES.items():
            self.tree.tag_configure(status, foreground=getattr(colors, style))
        self.tree.tag_configure("info", foreground=colors.info)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview, bootstyle="round")
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _: self._open(on_select))

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self.results.clear()

    def add(self, result):
        item = self.tree.insert("", "end", tags=(result.status,), values=(
            result.title, STATUS_LABELS[result.status], result.describe()))
        self.results[item] = result
        self.tree.see(item)

    def message(self, text):
        self.tree.see(self.tree.insert("", "end", values=("—", "Info", text), tags=("info",)))

    def _open(self, on_select):
        selection = self.tree.selection()
        if selection and selection[0] in self.results:
            on_select(self.results[selection[0]])


class ShowDetailWindow(ttk.Toplevel):
    """Season-by-season breakdown for one show, with missing episodes listed."""

    def __init__(self, master, result):
        super().__init__(title=result.title, master=master, transient=master,
                         size=(820, 520), minsize=(640, 400))
        self.bind("<Escape>", lambda _: self.destroy())

        side = ttk.Frame(self, padding=16)
        side.pack(side="left", fill="y")
        self._poster = ImageTk.PhotoImage(result.poster)
        ttk.Label(side, image=self._poster).pack()
        if result.tmdb_id:
            ttk.Button(side, text="View on TMDb", bootstyle="info-outline",
                       command=lambda: webbrowser.open(
                           f"https://www.themoviedb.org/tv/{result.tmdb_id}")
                       ).pack(fill="x", pady=(12, 0))

        main = ttk.Frame(self, padding=(0, 16, 16, 16))
        main.pack(side="left", fill="both", expand=True)
        heading = result.title + (f"  ({result.year})" if result.year else "")
        ttk.Label(main, text=heading, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(main, text=result.describe(), bootstyle=STATUS_STYLES[result.status],
                  font=("Segoe UI", 10), wraplength=560).pack(anchor="w", pady=(2, 8))
        if result.summary:
            ttk.Label(main, text=result.summary, wraplength=560, bootstyle="light",
                      font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(tree_frame, columns=("status", "episodes"), bootstyle="dark")
        tree.heading("#0", text="Season / Episode", anchor="w")
        tree.heading("status", text="Status", anchor="w")
        tree.heading("episodes", text="On Plex", anchor="w")
        tree.column("#0", width=300, anchor="w")
        tree.column("status", width=150, anchor="w")
        tree.column("episodes", width=90, anchor="w")
        colors = ttk.Style().colors
        for status, style in STATUS_STYLES.items():
            tree.tag_configure(status, foreground=getattr(colors, style))
        tree.tag_configure("episode", foreground=colors.light)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview, bootstyle="round")
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)

        season_status = {"missing": "Not in library", "partial": "Missing episodes",
                         "complete": "Complete"}
        for season in result.seasons:
            label = season.name if season.name.lower() == f"season {season.number}" \
                else f"Season {season.number} — {season.name}"
            node = tree.insert("", "end", text=label, open=season.status == "partial",
                               tags=(season.status,), values=(
                                   season_status[season.status],
                                   f"{season.owned_count} / {season.aired_count}"))
            for ep in season.missing_episodes:
                title = f"E{ep.number:02d}  {ep.title}".rstrip()
                tree.insert(node, "end", text=title, tags=("episode",),
                            values=("Missing", f"aired {ep.air_date}"))
        if not result.seasons:
            tree.insert("", "end", text=result.error or "No season data", tags=("error",))


class ConfigDialog(ttk.Toplevel):
    """Settings form for the Plex server and TMDb credentials."""

    FIELDS = (
        ("server_url", "Plex server URL", False, "e.g. http://192.168.1.10:32400"),
        ("plex_token", "Plex token", True, "Get Info → View XML → X-Plex-Token in the URL"),
        ("tmdb_api_key", "TMDb API key or read access token", True,
         "https://www.themoviedb.org/settings/api"),
    )

    def __init__(self, master, config_manager, on_save):
        super().__init__(title="Settings", master=master, transient=master,
                         size=(520, 400), resizable=(False, False))
        self.grab_set()
        self.config_manager = config_manager
        self.on_save = on_save
        self.bind("<Escape>", lambda _: self.destroy())

        body = ttk.Frame(self, padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Settings", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(body, text=f"Credentials are stored in: {config_manager.secrets_backend}",
                  bootstyle="light", font=("Segoe UI", 9), wraplength=470
                  ).pack(anchor="w", pady=(0, 10))

        current = config_manager.get_config()
        self.vars = {}
        self.entries = []
        for key, label, secret, hint in self.FIELDS:
            ttk.Label(body, text=label, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(6, 2))
            var = tk.StringVar(value=current.get(key, ""))
            entry = ttk.Entry(body, textvariable=var, show="•" if secret else "")
            entry.pack(fill="x")
            ttk.Label(body, text=hint, bootstyle="light", font=("Segoe UI", 8)).pack(anchor="w")
            self.vars[key] = var
            if secret:
                self.entries.append(entry)

        self.show_secrets = tk.BooleanVar()
        ttk.Checkbutton(body, text="Show credentials", variable=self.show_secrets,
                        bootstyle="round-toggle", command=self._toggle_secrets
                        ).pack(anchor="w", pady=(10, 0))

        buttons = ttk.Frame(body)
        buttons.pack(side="bottom", fill="x")
        ttk.Button(buttons, text="Save", bootstyle="warning", command=self._save).pack(side="right")
        ttk.Button(buttons, text="Cancel", bootstyle="light-outline",
                   command=self.destroy).pack(side="right", padx=8)

    def _toggle_secrets(self):
        for entry in self.entries:
            entry.configure(show="" if self.show_secrets.get() else "•")

    def _save(self):
        values = {key: var.get().strip() for key, var in self.vars.items()}
        if not all(values.values()):
            from ttkbootstrap.dialogs import Messagebox
            Messagebox.show_error("All fields are required.", title="Settings", parent=self)
            return
        self.config_manager.set_config(values)
        self.destroy()
        self.on_save()
