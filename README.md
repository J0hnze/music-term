# music-term

A Linux terminal music player with YouTube Music search, local folder playback,
album previews, a saved playlist, an audio spectrum and a ten-band equalizer.
Requires Python 3.11 or newer. Environment and dependency management use **uv**.

## Setup with uv

Install the system audio tools on Ubuntu or Debian:

```sh
sudo apt update
sudo apt install python3 mpv ffmpeg pulseaudio-utils
```

Install uv if needed using the [official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
Then open the project directory and install its locked dependencies:

```sh
cd ~/projects/music-term
uv sync --extra dev
uv run music-term --check
uv run music-term
```

`uv sync` creates and manages `.venv`; you do not need to activate it or install
packages manually. `uv.lock` records the dependency versions and belongs in Git.
For subsequent launches, run `uv run music-term` from the project directory.
The `dev` extra installs the test tools; use `uv sync` for a playback-only setup.

For YouTube playback, yt-dlp may also need a JavaScript runtime. Install Deno
using its [official instructions](https://docs.deno.com/runtime/getting_started/installation/)
and make it available on PATH. The yt-dlp default extra includes its companion
challenge scripts. See the [yt-dlp EJS guide](https://github.com/yt-dlp/yt-dlp/wiki/EJS).
To update extraction support intentionally:

```sh
uv lock --upgrade-package yt-dlp
uv sync --extra dev
```

## Features and layout

- **Left:** song/album search results and the current playlist.
- **Right:** album cover and track list. Highlight a result to preview its album;
  select an album track and press Enter to queue and play it.
- **Bottom:** audio spectrum, playback modes and track status.
- Shuffle, repeat one track, repeat the playlist, pause/resume and volume controls.
- Playlist restoration after restarting, without automatic playback.
- Current track and paused state in the terminal window title.
- Ten-band EQ with presets, reset and bypass; adjustable spectrum bar density.

Use a terminal at least 80×24. True colour and Unicode half-block support improve
album artwork. The panes resize with the terminal; dialogs scroll on small screens.
Search, folder scanning, album lookup and stream resolution run off the UI thread.

## Online and Local modes

Press **Ctrl+M** to switch between Online and Local mode. Switching preserves the
playlist and current playback; local and online tracks can share a playlist.

In **Online** mode, select Songs or Albums, type a query and press Enter. You can
also paste a YouTube or YouTube Music URL. An existing local file path is accepted
in this search field too. Online search and streaming require internet access.

In **Local** mode, press **Ctrl+O**, enter a music folder path and select Open
folder (or press Enter). `~/Music` is offered initially. Ctrl+O can also open a
folder from Online mode and switch to Local automatically.

The app includes audio files in subfolders, up to 5,000 tracks. Supported
extensions are MP3, FLAC, WAV, OGG, OPUS, M4A, AAC, WMA, AIFF, AIF and ALAC;
actual decoding depends on mpv. Hidden folders/files and symlinks are skipped.
Search matches filenames and folder paths, ignoring case; multiple search words
must all match. Submit an empty search to list every scanned track. Ctrl+O can
choose another folder or rescan the current folder after adding files.

Local tracks use filenames as titles and do not yet read embedded tags or album
covers. Local folder search/playback needs no YouTube login. The folder selection
and search mode last for the current session; queued file paths are saved with
the playlist and restored at the next launch.

## Keyboard controls

| Key | Action |
| --- | --- |
| Ctrl+M | Switch Local / Online mode |
| Ctrl+O | Open a local music folder |
| `/` | Focus the search field |
| Enter in search | Search; an empty Local search lists all tracks |
| Escape | Leave the search field or close a dialog |
| Up / Down | Select a row |
| Enter on a song | Add it to the playlist and play |
| Enter on a playlist row | Play that track |
| Enter on an album | Queue the album and play its first available track |
| `a` | Queue the selected song or album |
| `b` | Queue the selected result's full album when online album metadata exists |
| Space | Play when idle; pause/resume when playing |
| `n` / `p` | Next / previous track |
| `s` | Toggle shuffle |
| `r` | Cycle repeat Off → One track → Playlist |
| `+` / `-` | Raise / lower volume by 5% |
| F5 / F6 | Fewer / more spectrum bars, from 10 to 120 |
| `e` | Open the equalizer |
| `l` | Open login settings |
| Tab | Move between widgets |
| `q` | Quit |

Text inputs accept normal typing, including spaces. Leave the input with Escape
before using letter shortcuts or Space for playback. Mode controls appear above
the playback status, and shortcuts appear in the footer.

Shuffle changes playback order while preserving the visible playlist order. Each
track plays once per cycle. Repeat Playlist wraps at the end; Repeat One restarts
the current track at EOF, while Next still skips to another track.

## YouTube Music login

Login uses a copied request from a successful sign-in in your normal browser.
The app does not launch a login browser or ask for your Google password.

1. Sign in at [YouTube Music](https://music.youtube.com) in your normal browser.
2. Open Developer Tools → Network, filter `browse`, and refresh or open Home/an album.
3. Select a successful **POST** request to `music.youtube.com/youtubei/v1/browse`.
4. Right-click the request → Copy → **Copy as cURL (bash)**.
5. Press `l` in music-term, paste the complete command in the masked field,
   and select **Save cURL**.

Copy the request, not its response or JSON payload. The complete command contains
session credentials: keep it private. Use bash/POSIX cURL syntax rather than
Windows cmd/PowerShell syntax. The app parses the command locally; it never
executes it or reads files named by it.

The extracted headers are saved as `browser.json` under
`$XDG_CONFIG_HOME/music-term`, or `~/.config/music-term` by default. On Linux the
config directory is private (0700), and credentials are private (0600). The paste
is cleared after saving, errors or closing the dialog.

The top-right banner shows **Logged in as: account name** when account lookup
succeeds. Saving a request confirms parsing/storage; a failed account lookup
shows Login unverified. Renew an expired session by pasting a fresh successful
request. Disconnect removes the app's saved credentials; it does not sign you
out of Google in your browser.

Online albums include available tracks in album order; unavailable tracks are
skipped. Account-restricted playback may still fail: browser header authentication
is used by ytmusicapi, while yt-dlp resolves public streams or uses a separately
saved legacy cookie file if present. The login dialog only accepts copied cURL.

## Spectrum, artwork and equalizer

The spectrum analyzes speaker output using FFmpeg and NumPy FFT. It selects the
default output monitor through `pactl`, supporting PulseAudio and PipeWire's
PulseAudio compatibility service. It does not select the default microphone.
Other applications playing through the same output may also affect the bars.
Bars clear when playback is paused or idle. PCM stays in memory and monitoring
stops when the app exits. Restart after changing the default output device.

F5/F6 adjust visual density only; the EQ always has ten bands. Additional bars
are grouped to fit narrow terminals. Online artwork comes from album/search
thumbnails or YouTube video thumbnails; it is cached in memory, resized for the
pane and fetched without saved authentication headers.

The EQ centers are 31, 62, 125, 250, 500, 1,000, 2,000, 4,000, 8,000 and 16,000 Hz.
Each band supports −12 to +12 dB. In the EQ dialog, Tab to a selector, press Enter,
choose a value with Up/Down and confirm with Enter. Presets are Flat, Bass, Treble,
Rock and Classical. Reset Flat and bypass are also available.

EQ changes apply through mpv's FFmpeg lavfi filters during playback. Conservative
preamp attenuation and a limiter reduce clipping; large boosts can lower overall
loudness. If mpv lacks the required equalizer/alimiter filters, use bypass or
install a full mpv build.

## Saved state and Git

The playlist, selected track and shuffle/repeat settings are atomically saved to
`tmp/playlist.json` inside the project when they change and on normal exit. The
file reloads on startup without autoplay; leave the input and press Space to
start the saved selection. Delete the file to reset the playlist. Local files
must still exist at their saved paths.

Git ignores `.venv`, `tmp`, caches, logs, private credentials and copied request
exports. Login credentials stay in the private config directory outside the
repository. Do not paste secrets into source files: ignore patterns only protect
matching filenames. The project has been initialized on `main` and prepared for
a first commit; no commit or remote push has been made.

## Troubleshooting

- **Missing audio tools:** run `uv run music-term --check`. Playback needs mpv;
  the spectrum needs FFmpeg, `pactl` and an accessible output monitor.
- **YouTube search/login fails:** check connectivity and paste a fresh successful
  browse request. The account banner reports whether lookup succeeded.
- **YouTube stream fails:** update yt-dlp and check Deno availability. Regional,
  account and YouTube restrictions can make some streams unavailable.
- **EQ unavailable:** the mpv build must include FFmpeg lavfi filter support;
  installing the FFmpeg executable alone does not change mpv's linked libraries.
- **No spectrum:** check `pulseaudio-utils` and the PulseAudio compatibility service.
  Playback can still work without the visualizer.
- **No local results:** check the chosen folder, supported extensions and access
  permissions, or submit an empty search to clear filtering.
- **Local playlist file moved:** reopen its new folder and add it again.

## Development and verification

```sh
uv sync --extra dev
uv run pytest -q
uv run music-term --version
uv run music-term --help
uv run music-term --check
```

The offline test suite covers authentication parsing/storage, queue modes,
playlist restoration, EQ, mocked mpv IPC, spectrum analysis, artwork, folder
scanning/search, mode switching and Textual keyboard/layout behavior. Tests do
not require a YouTube account or live playback engine. See `VERIFICATION.md` for
integration checks and remaining live-service limitations.

Main modules are `ui.py`, `local.py`, `search.py`, `player.py`, `queue.py`,
`state.py`, `auth.py`, `eq.py`, `spectrum.py`, `artwork.py` and `terminal.py`.
The project is MIT licensed.
