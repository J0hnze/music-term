# music-term

A terminal music player for Linux and Windows through WSL2 with YouTube Music search, local folder playback,
album previews, a saved playlist, an audio spectrum and a ten-band equalizer.
Requires Python 3.11 or newer. Environment and dependency management use **uv**.

Run the commands below from the root of your cloned `music-term` repository
(the directory containing `README.md` and `pyproject.toml`). In File Explorer,
open the clone folder and choose **Open in Terminal**.

[Windows install](#install-on-windows) · [Windows start](#start-on-windows) · [Linux/macOS setup](#linux-and-macos-setup)

## Windows setup (WSL2 Ubuntu)

The current player uses mpv Unix-socket IPC and PulseAudio monitoring. **Native
Windows Python playback is not implemented**; use WSL2 Ubuntu. Windows-side uv,
mpv or FFmpeg installations are not used by this setup.

Use Windows 11 or Windows 10 build 19044+ with updated WSL2/WSLg. See Microsoft's
[WSLg prerequisites](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps)
and [WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install).
WSLg supplies the Linux audio connection; actual playback and spectrum depend on
that connection being available.

### Install on Windows

In **administrator PowerShell**, install WSL if it is not already available:

```powershell
wsl --install -d Ubuntu
```

Restart if requested. Open Ubuntu once and finish creating your Linux user and
password. For an existing installation, use `wsl --list --verbose` to check that
Ubuntu uses version 2; update WSL with `wsl --update` when needed.

Open **Windows Terminal → PowerShell** (ordinary user, not administrator), then
install the application dependencies:

```powershell
.\setup.bat
```

You can also double-click `setup.bat` in File Explorer. Setup
asks for your **Ubuntu sudo password**, installs Linux audio dependencies, installs
uv through its [official installer](https://docs.astral.sh/uv/getting-started/installation/)
when missing, and creates `.venv-wsl` with locked dependencies and Python 3.12.
The Linux environment is separate from `.venv`, and both are ignored by Git.
The wrappers use a process-scoped PowerShell execution-policy bypass; they do not
change your saved execution policy.

### Start on Windows

From a PowerShell tab in Windows Terminal:

```powershell
.\start.bat
```

Or double-click `start.bat`. Run setup once; use start for subsequent launches.
Keep this terminal open while listening and press `q` to quit. The start script
runs the Linux player inside Ubuntu; you do not need to activate its environment.

For explicit Windows Terminal image rendering:

```powershell
.\start.bat -Artwork sixel
```

The default is `auto`. Use `-Artwork blocks` for the portable artwork fallback.
Press **F11** in the player to cycle the available artwork modes. Click or drag
the volume slider below the spectrum to change volume.

### Other distributions and development setup

For another Ubuntu distribution name or development dependencies:

```powershell
.\setup.bat -Distribution Ubuntu-24.04 -Dev
.\start.bat -Distribution Ubuntu-24.04
powershell -NoProfile -ExecutionPolicy Bypass -File .\windows.ps1 -Mode check -Distribution Ubuntu-24.04
```

Use the exact distribution name shown by `wsl --list --verbose`. Automatic
package setup supports Ubuntu/Debian distributions. The check option checks mpv,
FFmpeg and the PulseAudio connection; it does not prove live YouTube playback.

### Start directly from Ubuntu

Open an Ubuntu tab in Windows Terminal and navigate to your clone directory.
From the repository root:

```sh
bash tools/windows-wsl.sh setup dev
bash tools/windows-wsl.sh start
```

To run tests using the same environment:

```sh
export UV_PROJECT_ENVIRONMENT="$PWD/.venv-wsl"
uv run --locked --extra dev pytest -q
```

The project's playlist remains in `tmp/playlist.json` alongside the source.
Credentials live in the **Linux user's** config directory inside WSL. To open
music files through Ctrl+O, use a relative path such as `./music` for a folder
inside the clone. External Windows folders must use their WSL `/mnt/<drive>/...`
path; pasted Windows drive paths do not work unchanged.
Keep using the same distribution and Linux user to retain access to saved login
credentials. As on Linux, choose **Copy as cURL (bash)** for the login request.

### Windows troubleshooting

- **Ubuntu unavailable:** complete its first launch; check the name with
  `wsl --list --verbose` and pass `-Distribution` if necessary.
- **WSL1:** use `wsl --set-version Ubuntu 2` from Windows.
- **No sound:** run the check option and `pactl info` inside Ubuntu. Update WSL,
  reopen Ubuntu, and check Windows output volume/device. Do not start another
  PulseAudio server over WSLg's connection.
- **No spectrum:** an output monitor must be exposed by the WSL audio server.
  Inspect `pactl list short sources` in Ubuntu. Playback can work without bars;
  WSL loopback capture is not verified on every audio setup.
- **YouTube stream errors:** install Deno **inside Ubuntu**, using the official
  instructions linked above; Windows-installed Deno is not the intended runtime.
- **Slow environment setup on /mnt/c:** a separate checkout in your Linux home
  directory can be faster. Keep its playlist and credentials out of source control.

## Linux and macOS setup

Install the system audio tools on Ubuntu or Debian:

```sh
sudo apt update
sudo apt install python3 mpv ffmpeg pulseaudio-utils
```

Or on MacOS:
```sh
brew update
brew install python mpv ffmpeg
```

Install uv if needed using the [official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
Then open your cloned repository root and install its locked dependencies:

```sh
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
- **Right:** album cover and track list side by side. Highlight a result to preview its album;
  select an album track and press Enter to queue and play it.
- **Bottom:** audio spectrum with a centred title, rainbow volume bar, playback
  modes and track status. The bar shows the player volume (0–100%), adjusted by
  clicking or dragging the slider (blue = low, red = high); it is not an audio loudness meter.
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
| `d` on a playlist row | Delete selected item; stops playback if it is the current track |
| Ctrl+C outside inputs/dialogs | Clear saved playlist and stop playback; does not quit |
| `n` / `p` | Next / previous track |
| `s` | Toggle shuffle |
| `r` | Cycle repeat Off → One track → Playlist |
| Click / drag volume slider | Set volume; blue is low, red is high |
| Left / Right on volume slider | Lower / raise volume by 5% |
| Home / End on volume slider | Set volume to 0% / 100% |
| F11 | Cycle artwork rendering: Auto, Blocks and available graphics protocol |
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

The spectrum starts with 50 bars. F5/F6 adjust visual density only; the EQ always has ten bands. Additional bars
are grouped to fit narrow terminals. Online artwork comes from album/search
thumbnails or YouTube video thumbnails; it is cached in memory, resized for the
pane and fetched without saved authentication headers.

### Higher-quality album artwork

The cover sits to the left of the album track list, with a larger share of the
workspace assigned to the album panel. The cover pane uses roughly half the total
workspace width; the album track list uses the remaining right-hand sixth. Artwork selects the largest thumbnail
provided by YouTube Music, preserves aspect ratio and uses Lanczos downsampling
in the portable half-block renderer.

On Python 3.12+, `textual-image` enables **actual image rendering** where the
terminal supports Sixel or Kitty graphics. Terminal detection happens before the
UI starts; unsupported terminals and Python 3.11 retain the true-colour half-block
fallback. Cached images resize locally without another download.

Press **F11** to cycle Auto → Blocks → the detected graphics protocol, without
restarting or downloading the cover again. Only detected or explicitly requested
protocols are offered; capability probing occurs before the UI starts. The
current mode appears in the status line. The default is automatic detection. To choose a renderer from Ubuntu:

```sh
export UV_PROJECT_ENVIRONMENT="$PWD/.venv-wsl"  # Windows WSL setup only
uv run --locked music-term --artwork auto
uv run --locked music-term --artwork sixel
uv run --locked music-term --artwork blocks
```

For the Windows launcher, set the override in PowerShell before starting:

```powershell
.\start.bat -Artwork sixel
# Or: $env:MUSIC_TERM_ARTWORK = 'sixel'; .\start.bat
```

Use `auto` normally; force `sixel` only on a compatible terminal. `kitty` selects
Kitty's graphics protocol. Set `blocks` if images fail to display or leave visual
artefacts. Recent Windows Terminal versions support Sixel; see
[Microsoft's Sixel announcement](https://devblogs.microsoft.com/commandline/windows-terminal-preview-1-22-release/).
See [textual-image](https://github.com/lnqs/textual-image) for protocol support.
Full graphics rendering is terminal-dependent and has not been visually verified
in this session; layout, resizing and fallback paths are covered by offline tests.

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
