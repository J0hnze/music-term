import asyncio
from pathlib import Path
from textual import work, events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Input, Label, Select, Static
from .local import scan_folder, filter_tracks
from .auth import Credentials
from .eq import BANDS, PRESETS, Equalizer
from .player import Player, dependencies
from .queue import Queue, Track
from .state import load_playlist, save_playlist
from .terminal import window_title
from .search import MusicService
from .spectrum import AudioMonitor, Spectrum
from .artwork import Artwork, fetch_artwork

class HeaderPasteInput(Input):
    """Retain multiline clipboard data; ordinary Input keeps only the first line."""
    raw_headers: str = ""

    def _on_paste(self, event: events.Paste) -> None:
        event.prevent_default()
        self.raw_headers = event.text
        self.value = "cURL pasted" if event.text else ""
        event.stop()


class AuthModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self) -> None:
        super().__init__()
        self.header_input = HeaderPasteInput(placeholder="Paste copied cURL request (masked)", password=True, id="headers-raw")

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("Connect using a copied cURL request")
            yield Static("1. Sign in at music.youtube.com in your normal browser.\n2. Open Developer Tools → Network; filter browse and refresh or open Home.\n3. Select a successful POST /browse request → Copy → Copy as cURL (bash).\n4. Paste the complete command below, then Save cURL.\nThe command is parsed locally, never executed. Do not paste your password or request payload.")
            yield self.header_input
            yield Button("Save cURL", id="import-headers")
            yield Button("Disconnect", id="disconnect")
            yield Static("", id="auth-status", markup=False)
            yield Button("Close", id="close")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "import-headers":
            raw = self.header_input.raw_headers if self.header_input.value else ""
            self.clear_paste()
            try:
                self.app.credentials.import_curl(raw)
                self.app.refresh_account()
                self.query_one("#auth-status", Static).update("Saved browser.json privately. Authentication will be used for the next search.")
            except ValueError as error:
                self.query_one("#auth-status", Static).update(str(error))
        elif event.button.id == "disconnect":
            self.clear_paste()
            try:
                self.app.credentials.disconnect()
                self.app.refresh_account()
                self.query_one("#auth-status", Static).update("Saved credentials deleted.")
            except OSError:
                self.query_one("#auth-status", Static).update("Cannot delete saved credentials. Check config directory permissions.")
        elif event.button.id == "close":
            self.clear_paste()
            self.dismiss()

    def clear_paste(self) -> None:
        self.header_input.raw_headers = ""
        self.header_input.value = ""

    def on_unmount(self) -> None:
        self.clear_paste()

class FolderModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, folder: str) -> None:
        super().__init__()
        self.folder = folder

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("Open local music folder")
            yield Static("Enter a folder path. Audio files in subfolders are included (up to 5,000 tracks). Search matches filenames and folder names.")
            yield Input(value=self.folder, placeholder="~/Music", id="folder-path")
            yield Button("Open folder", id="open-folder", variant="primary")
            yield Static("", id="folder-status", markup=False)
            yield Button("Cancel", id="cancel-folder")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def submit_folder(self) -> None:
        value = self.query_one(Input).value.strip()
        path = Path(value).expanduser()
        if not value or not path.is_dir():
            self.query_one("#folder-status", Static).update("Choose an existing folder.")
            return
        self.dismiss(str(path.resolve()))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.submit_folder()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-folder":
            self.submit_folder()
        else:
            self.dismiss(None)

class EQModal(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close")]
    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("10-band EQ — Tab to a band, Up/Down changes 1 dB")
            yield Static("Conservative preamp attenuation and limiter protect against clipping; boosts reduce overall loudness.")
            yield Select([(name, name) for name in PRESETS], prompt="Choose preset", id="preset")
            for index, hz in enumerate(BANDS):
                with Horizontal(classes="band"):
                    yield Label(f"{hz} Hz")
                    yield Select([(f"{gain:+d} dB", gain) for gain in range(-12, 13)],
                                 value=self.app.eq.gains[index], allow_blank=False, id=f"gain-{index}")
            yield Button("Reset Flat", id="reset")
            yield Button("Toggle bypass", id="bypass")
            yield Static(f"Bypass: {self.app.eq.bypass}", id="eq-status")
            yield Button("Close", id="close")

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.value is Select.BLANK:
            return
        if event.select.id == "preset":
            self.app.eq.preset(str(event.value))
            for index, gain in enumerate(self.app.eq.gains):
                self.query_one(f"#gain-{index}", Select).value = gain
        else:
            self.app.eq.set_band(int(event.select.id.split("-")[1]), int(event.value))
        await self.app.apply_eq()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss()
            return
        if event.button.id == "reset":
            self.app.eq.preset("Flat")
            for index in range(10):
                self.query_one(f"#gain-{index}", Select).value = 0
        else:
            self.app.eq.bypass = not self.app.eq.bypass
        self.query_one("#eq-status", Static).update(f"Bypass: {self.app.eq.bypass}")
        await self.app.apply_eq()

class MusicApp(App):
    TITLE = "music-term"
    CSS = """
    Screen { background: $surface; }
    #topbar { dock: top; height: 1; background: $primary; }
    #app-title { width: 1fr; padding-left: 1; }
    #account { width: auto; max-width: 75%; text-align: right; padding-right: 1; height: 1; }
    #search-row { height: 3; }
    #search-mode { width: 18; }
    #search { width: 1fr; }
    #workspace { height: 3fr; min-height: 10; }
    #library { width: 1fr; border: solid $primary; }
    #album-panel { width: 1fr; border: solid $secondary; }
    #album-title { height: auto; max-height: 3; padding: 0 1; }
    #artwork { height: 1fr; min-height: 3; content-align: center middle; }
    #spectrum { height: 1fr; min-height: 6; width: 100%; border: solid $success; padding: 0 1; }
    DataTable { width: 100%; height: 1fr; }
    #results { height: 2fr; }
    #queue { height: 1fr; border-top: solid $primary; }
    #album-tracks { height: 1fr; border-top: solid $secondary; }
    #now, #status { height: auto; min-height: 2; }
    ModalScreen { align: center middle; background: $background 80%; }
    ModalScreen > VerticalScroll { width: 90%; max-width: 100; height: 90%; border: thick $primary; padding: 1 2; background: $surface; }
    .band { height: 3; }
    .band Label { width: 16; padding-top: 1; }
    .band Select { width: 1fr; }
    """
    BINDINGS = [Binding("ctrl+m", "switch_mode", "Local/Online", priority=True), Binding("ctrl+o", "open_folder", "Open folder", priority=True), ("/", "search", "Search"), ("a", "add", "Add"), ("b", "album", "Add album"), Binding("space", "pause", "Play/Pause", priority=True),
                ("f5", "fewer_bars", "Fewer bars"), ("f6", "more_bars", "More bars"), ("s", "shuffle", "Shuffle"), ("r", "repeat", "Repeat"), ("n", "next", "Next"), ("p", "previous", "Previous"), ("e", "eq", "EQ"),
                ("l", "login", "Login"), ("+", "louder", "Vol +"), ("-", "quieter", "Vol -"), ("q", "quit", "Quit")]
    def __init__(self) -> None:
        super().__init__()
        self.credentials = Credentials()
        self.service = MusicService(self.credentials)
        self.player = Player()
        self.eq = Equalizer()
        self.queue = Queue()
        self.results: list[Track] = []
        self.current: Track | None = None
        self.volume = 70
        self.loading = False
        self.monitor = AudioMonitor()
        self.spectrum_widget = Spectrum(id="spectrum")
        self.playback_active = False
        self.playback_paused = False
        self.album_tracks: list[Track] = []
        self._last_terminal_title = ""
        self.local_mode = False
        self.local_tracks: list[Track] = []
        self.local_folder = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static("music-term", id="app-title")
            yield Static("Not logged in", id="account", markup=False)
        with Horizontal(id="workspace"):
            with Vertical(id="library"):
                with Horizontal(id="search-row"):
                    yield Select([("Songs", "songs"), ("Albums", "albums")], value="songs", allow_blank=False, id="search-mode")
                    yield Input(placeholder="Search songs/albums or paste URL/path", id="search")
                yield DataTable(id="results", cursor_type="row")
                yield DataTable(id="queue", cursor_type="row")
            with Vertical(id="album-panel"):
                yield Static("Album cover & track list", id="album-title", markup=False)
                yield Artwork(id="artwork")
                yield DataTable(id="album-tracks", cursor_type="row")
        yield self.spectrum_widget
        yield Static("Shuffle: Off • Repeat: Off • Space: Play/Pause", id="modes", markup=False)
        yield Static("No track • Volume 70%", id="now", markup=False)
        yield Static("Enter plays selected row • a queues • l login • e EQ • Esc leaves input", id="status", markup=False)
        yield Footer()

    async def on_mount(self) -> None:
        for name in ("results", "queue", "album-tracks"):
            self.query_one(f"#{name}", DataTable).add_columns({"results": "Search results", "queue": "Playlist", "album-tracks": "Album tracks"}[name], "Artist")
        try:
            restored = load_playlist()
            if not self.queue.tracks:
                self.queue = restored
            self.refresh_queue()
            if self.queue.index >= 0:
                self.query_one("#queue", DataTable).move_cursor(row=self.queue.index)
            if self.queue.tracks:
                self.status("Playlist restored • Space plays selected track")
        except (ValueError, OSError) as error:
            self.status(str(error) if isinstance(error, ValueError) else "Cannot read tmp/playlist.json. Check permissions.")
        self.update_modes()
        self.update_terminal_title(None)
        missing = dependencies()
        if missing:
            self.status("Missing " + ", ".join(missing) + ". Install: sudo apt install mpv ffmpeg")
        if "mpv" not in missing:
            try:
                await self.player.start()
            except RuntimeError as error:
                self.status(str(error))
        self.query_one("#search", Input).focus()
        self.set_interval(0.5, self.poll)
        self.refresh_account()
        self.start_spectrum()
        self.set_interval(0.08, self.render_spectrum)

    @work(exclusive=True, group="account")
    async def refresh_account(self) -> None:
        banner = self.query_one("#account", Static)
        banner.update("Checking login…")
        try:
            name = await asyncio.wait_for(asyncio.to_thread(self.service.account_name), timeout=20)
            banner.update(f"Logged in as: {name}" if name else "Not logged in")
        except (RuntimeError, TimeoutError, OSError):
            banner.update("Login unverified • press l")

    @work(group="spectrum")
    async def start_spectrum(self) -> None:
        try:
            await self.monitor.start()
        except OSError:
            self.monitor.message = "Spectrum unavailable: check ffmpeg and pulseaudio-utils"

    def render_spectrum(self) -> None:
        self.spectrum_widget.show_levels(
            self.monitor.levels, self.monitor.message,
            self.playback_active and not self.playback_paused and not self.loading)

    def status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def on_key(self, event) -> None:
        if event.key == "escape" and isinstance(self.focused, Input):
            self.query_one("#results").focus()

    def action_search(self) -> None:
        self.query_one("#search").focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search" and (event.value.strip() or self.local_mode):
            self.search_tracks(event.value.strip())

    @work(exclusive=True, group="search")
    async def search_tracks(self, query: str) -> None:
        self.status("Searching…")
        try:
            mode = self.query_one("#search-mode", Select).value
            if self.local_mode:
                self.results = filter_tracks(self.local_tracks, query)
            elif mode == "songs":
                self.results = await asyncio.to_thread(self.service.search, query)
            else:
                self.results = await asyncio.to_thread(self.service.search, query, "albums")
            table = self.query_one("#results", DataTable)
            table.clear()
            for track in self.results:
                table.add_row(("[Album] " if track.is_album else "") + track.title, track.artist)
            table.focus()
            self.status(f"{len(self.results)} results • Enter plays • a queues • b adds album")
        except (RuntimeError, ValueError) as error:
            self.status(str(error))

    def selected(self) -> Track | None:
        table = self.query_one("#results", DataTable)
        return self.results[table.cursor_row] if self.results and table.cursor_row < len(self.results) else None

    def refresh_queue(self) -> None:
        table = self.query_one("#queue", DataTable)
        table.clear()
        for index, track in enumerate(self.queue.tracks):
            table.add_row(("▶ " if index == self.queue.index else "") + track.title, track.artist)
        self.persist_playlist()

    def action_add(self) -> None:
        track = self.selected()
        if track and track.is_album:
            self.queue_album(track, False)
        elif track:
            self.queue.add(track)
            self.refresh_queue()
            self.status("Added to queue")

    def action_album(self) -> None:
        track = self.selected()
        if track and track.album_id:
            self.queue_album(track, False)
        else:
            self.status("No album metadata for this result. Select Albums and search for its title.")

    @work(exclusive=True, group="album")
    async def queue_album(self, result: Track, play: bool = False) -> None:
        if not result.album_id:
            self.status("No album metadata; try an Albums search.")
            return
        self.status("Loading album tracks…")
        try:
            tracks = await asyncio.to_thread(self.service.album_tracks, result.album_id)
            first = len(self.queue.tracks)
            for item in tracks:
                self.queue.add(item)
            self.display_album(result, tracks)
            self.refresh_queue()
            self.status(f"Added {len(tracks)} album tracks in order (available tracks only)")
            if play:
                self.queue.select(first)
                self.play(tracks[0])
        except RuntimeError as error:
            self.status(str(error))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "results":
            track = self.selected()
            if track and track.is_album:
                self.queue_album(track, True)
            elif track:
                self.queue.add(track)
                self.queue.select(len(self.queue.tracks) - 1)
                self.play(track)
        elif event.data_table.id == "album-tracks":
            if 0 <= event.cursor_row < len(self.album_tracks):
                track = self.album_tracks[event.cursor_row]
                self.queue.add(track)
                self.queue.select(len(self.queue.tracks) - 1)
                self.play(track)
        else:
            track = self.queue.select(event.cursor_row)
            if track:
                self.play(track)

    @work(exclusive=True, group="play")
    async def play(self, track: Track) -> None:
        self.loading = True
        self.status("Resolving stream…")
        try:
            source, headers = await asyncio.to_thread(self.service.resolve, track)
            # Discard end events from the replaced track before/after load.
            while not self.player.events.empty():
                self.player.events.get_nowait()
            await self.player.load(source, headers)
            self.current = track
            self.update_terminal_title(track)
            self.show_album(track)
            self.playback_active = True
            self.playback_paused = False
            eq_ok = await self.apply_eq()
            self.refresh_queue()
            if eq_ok:
                self.status("Playing • Space pauses • n/p moves through queue")
        except RuntimeError as error:
            self.status(str(error))
        finally:
            self.loading = False

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "results":
            track = self.selected()
            if track:
                self.show_album(track)

    def display_album(self, track: Track, tracks: list[Track]) -> None:
        self.album_tracks = tracks
        table = self.query_one("#album-tracks", DataTable)
        table.clear()
        for item in tracks:
            table.add_row(item.title, item.artist)
        title = track.title if track.is_album else track.album_title or "Album tracks"
        if not track.album_id:
            title = track.title
        self.query_one("#album-title", Static).update(f"{title} — {track.artist}")
        self.refresh_artwork(track if track.artwork or not tracks else tracks[0])

    @work(exclusive=True, group="album-preview")
    async def show_album(self, track: Track) -> None:
        await asyncio.sleep(0.2)  # Avoid requests for rows passed while scrolling.
        self.query_one("#album-title", Static).update("Loading album…")
        try:
            tracks = await asyncio.to_thread(self.service.album_tracks, track.album_id) if track.album_id else [track]
            self.display_album(track, tracks)
        except RuntimeError:
            self.display_album(track, [track] if not track.is_album else [])
            self.query_one("#album-title", Static).update("Album unavailable • check network/session")

    @work(exclusive=True, group="artwork")
    async def refresh_artwork(self, track: Track) -> None:
        art = self.query_one("#artwork", Artwork)
        art.show_data(None, "Loading art…")
        try:
            data = await asyncio.wait_for(asyncio.to_thread(fetch_artwork, track), timeout=15)
            art.show_data(data, "No album art" if not data else "")
        except TimeoutError:
            art.show_data(None, "Art unavailable")

    async def apply_eq(self) -> bool:
        try:
            await self.player.command("set_property", "af", ",".join(self.eq.filters()))
            return True
        except RuntimeError:
            self.status("EQ unavailable: mpv needs FFmpeg lavfi equalizer/alimiter support. Use bypass or install a full mpv build.")
            return False

    async def safe_command(self, *args) -> None:
        try:
            await self.player.command(*args)
        except RuntimeError as error:
            self.status(str(error))

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "pause" and (isinstance(self.focused, (Input, Select)) or isinstance(self.screen, ModalScreen)):
            return False
        return True

    def update_terminal_title(self, track: Track | None, paused: bool = False) -> None:
        title = window_title(track, paused)
        self.title = title
        if title != self._last_terminal_title:
            self.console.set_window_title(title)
            self._last_terminal_title = title

    def persist_playlist(self) -> None:
        try:
            save_playlist(self.queue)
        except OSError:
            self.status("Cannot save playlist in tmp/. Check project directory permissions.")

    def update_modes(self) -> None:
        repeat = {"off": "Off", "one": "One track", "all": "Playlist"}[self.queue.repeat]
        self.query_one("#modes", Static).update(f"{'Local' if self.local_mode else 'Online'} • Ctrl+M switches • Ctrl+O folder • Shuffle: {'On' if self.queue.shuffle else 'Off'} • Repeat: {repeat} • Space: Play/Pause")

    def action_switch_mode(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.workers.cancel_group(self, "search")
        self.local_mode = not self.local_mode
        self.query_one("#search-mode", Select).disabled = self.local_mode
        search = self.query_one("#search", Input)
        search.value = ""
        search.placeholder = "Search local filenames/folders (Enter lists all)" if self.local_mode else "Search songs/albums or paste URL/path"
        self.results = []
        self.query_one("#results", DataTable).clear()
        self.update_modes()
        if self.local_mode:
            if self.local_folder:
                self.search_tracks("")
            else:
                self.action_open_folder()
        else:
            search.focus()
            self.status("Online mode • Enter a YouTube Music search")

    def action_open_folder(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        self.push_screen(FolderModal(self.local_folder or str(Path.home() / "Music")), self.folder_chosen)

    def folder_chosen(self, folder: str | None) -> None:
        if folder:
            self.local_mode = True
            self.query_one("#search-mode", Select).disabled = True
            self.query_one("#search", Input).placeholder = "Search local filenames/folders (Enter lists all)"
            self.query_one("#search", Input).value = ""
            self.update_modes()
            self.load_folder(folder)

    @work(exclusive=True, group="search")
    async def load_folder(self, folder: str) -> None:
        self.status("Scanning local music folder…")
        try:
            tracks = await asyncio.to_thread(scan_folder, folder)
            self.local_folder = folder
            self.local_tracks = tracks
            self.results = tracks
            table = self.query_one("#results", DataTable)
            table.clear()
            for track in tracks:
                table.add_row(track.title, track.artist)
            self.query_one("#search", Input).focus()
            self.status(f"{len(tracks)} local tracks • {folder} • Search filenames/folders; Enter lists all • Ctrl+O changes folder")
        except (OSError, ValueError) as error:
            self.status(str(error) if isinstance(error, ValueError) else "Cannot read music folder. Check permissions.")

    def action_fewer_bars(self) -> None:
        self.monitor.bar_count = max(10, self.monitor.bar_count - 10)
        self.monitor.levels = [0.0] * self.monitor.bar_count
        self.status(f"Spectrum: {self.monitor.bar_count} bars • F5 fewer / F6 more")

    def action_more_bars(self) -> None:
        self.monitor.bar_count = min(120, self.monitor.bar_count + 10)
        self.monitor.levels = [0.0] * self.monitor.bar_count
        self.status(f"Spectrum: {self.monitor.bar_count} bars • F5 fewer / F6 more")

    def action_shuffle(self) -> None:
        self.queue.set_shuffle(not self.queue.shuffle)
        self.update_modes()
        self.persist_playlist()

    def action_repeat(self) -> None:
        self.queue.cycle_repeat()
        self.update_modes()
        self.persist_playlist()

    async def action_pause(self) -> None:
        if self.current is None or not self.playback_active:
            track = self.queue.select(self.queue.index if self.queue.index >= 0 else 0)
            if track:
                self.play(track)
            else:
                self.status("Add a track to the playlist first")
            return
        try:
            await self.player.command("cycle", "pause")
            self.playback_paused = not self.playback_paused
            self.update_terminal_title(self.current, self.playback_paused)
        except RuntimeError as error:
            self.status(str(error))

    def advance(self, automatic: bool = False) -> None:
        track = self.queue.next(automatic=automatic)
        if track:
            self.play(track)
        else:
            self.status("End of playlist • Space restarts the selected track")

    def action_next(self) -> None:
        self.advance()

    def action_previous(self) -> None:
        track = self.queue.previous()
        if track:
            self.play(track)

    async def action_louder(self) -> None:
        self.volume = min(100, self.volume + 5)
        await self.safe_command("set_property", "volume", self.volume)

    async def action_quieter(self) -> None:
        self.volume = max(0, self.volume - 5)
        await self.safe_command("set_property", "volume", self.volume)

    def action_eq(self) -> None:
        self.push_screen(EQModal())

    def action_login(self) -> None:
        self.push_screen(AuthModal())

    async def poll(self) -> None:
        if not self.player.writer or self.loading:
            return
        while not self.player.events.empty():
            event = self.player.events.get_nowait()
            if event.get("event") == "end-file":
                if event.get("reason") == "eof":
                    self.playback_active = False
                    self.advance(automatic=True)
                elif event.get("reason") == "error":
                    self.playback_active = False
                    self.status("Playback failed. Check audio device/network, refresh your session, or try a local file.")
        try:
            async def optional_property(name: str):
                try:
                    return await self.player.command("get_property", name)
                except RuntimeError:
                    return None
            elapsed = await optional_property("time-pos")
            duration = await optional_property("duration")
            paused = await self.player.command("get_property", "pause")
            self.playback_paused = bool(paused)
            self.update_terminal_title(self.current, self.playback_paused)
            title = f"{self.current.title} — {self.current.artist}" if self.current else "No track"
            def stamp(value):
                return f"{int(value)//60}:{int(value)%60:02d}" if value is not None else "--:--"
            self.query_one("#now", Static).update(f"{title} • {'Paused' if paused else 'Playing'} • {stamp(elapsed)}/{stamp(duration)} • Volume {self.volume}%")
        except RuntimeError:
            pass  # time/duration are unavailable while idle or on live streams

    async def on_unmount(self) -> None:
        self.persist_playlist()
        self.console.set_window_title("music-term")
        await self.monitor.close()
        await self.player.close()
