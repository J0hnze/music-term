# Verification — current cURL-only login

- Editable install and package imports verified.
- 32 offline tests passed: EQ limits/presets, XDG paths/permissions, credential
  storage/disconnect, queue transitions, mocked IPC, keyboard playback controls,
  resize/shutdown, strict cURL parsing and masked multiline cURL paste.
- Login modal tested to contain only Save cURL, Disconnect and Close buttons.
- Plain headers, payloads and file references are rejected by the cURL login path.
- Automatic Firefox module and Playwright dependency extra removed.
- Existing saved browser.json is retained. Credentials are excluded from ZIP.
- Archive contents listed and CRC integrity verified using the source allowlist.

Live Google authentication and YouTube playback were not tested. Actual local
EQ and monitor capture were verified as described below.
Saving cURL validates its required headers and storage, not live account access.

Account banner tested for verified username, disconnected state and lookup failure.
Account lookup uses documented ytmusicapi get_account_info() in a background
thread with a UI timeout; no live account request was made during tests.

## Spectrum, albums, artwork and EQ command format

- Album search and available-track ordering tested with mocked ytmusicapi.
- Keyboard album queueing tested for song metadata and album result rows.
- Spectrum tested using silence and synthetic 1kHz PCM; band selection and
  pause clearing verified. Missing monitoring dependencies handled cleanly.
- Artwork verified from synthetic PNG; invalid hosts/local placeholders tested.
- Corrected mpv `af` property value from a list of strings to a filter string.
- Real mpv accepts the corrected filter string; rejects the former list format.
- Live YouTube album fetching and remote artwork rendering were not tested.

- Real integration verification passed using a temporary PulseAudio null sink:
  mpv loaded a synthetic local WAV, changed EQ to Rock during playback, and
  bypassed the chain successfully. FFmpeg output-monitor capture and FFT detected
  its 1kHz tone in the correct band. Sink/processes/test audio were cleaned up;
  no tone was sent to the user's speakers.

## Beta layout

- Left pane contains search controls/results and playlist; right pane contains
  album cover/title and the album track list; full-width spectrum sits below.
- Headless geometry checks passed at 140×45 and 80×24: panes do not overlap,
  visualizer spans both panes, and status remains below it.
- Cached artwork resizes within its pane; album-preview track list and Enter
  to queue/play an album track tested using synthetic artwork and mocked metadata.
- Existing playback, authentication, EQ, queue and spectrum checks still pass.

## End-of-day player controls and Git preparation

- Shuffle traverses a full cycle without duplicates and keeps display order.
- Repeat-one applies at EOF; manual Next advances; repeat-playlist wraps.
- Playlist/modes roundtrip with 0700 tmp directory and 0600 atomic JSON file.
- Space restores/starts a saved selection and toggles pause/resume; text inputs
  still accept spaces. Terminal title strips control characters from track data.
- F5/F6 adjust FFT bar density from 10 to 120; variable-density FFT tested.
- Git ignores private state and credential/export filenames. No archive update
  was requested for these changes. Repository is prepared without making a commit.

## Local mode and uv

- Recursive audio scanning, case-insensitive multiword search and invalid folders tested.
- Ctrl+M/Ctrl+O folder selection, local playback and playlist preservation tested.
- uv.lock generated; locked dev environment and CLI checked with uv.

## Windows setup via WSL2 — 12 October 2026

- Added setup.bat/start.bat, windows.ps1 and tools/windows-wsl.sh for WSL2 Ubuntu, with optional distribution selection and development dependencies.
- PowerShell parser and Ubuntu bash -n syntax checks passed. Invoked the check launcher and verified its setup-required failure and exit code before installation.
- Checked shell LF line endings and the source archive allowlist, which now includes Windows setup files. git diff --check passed.
- Setup installation, WSLg audio playback, output-monitor spectrum and live YouTube playback were not exercised. Native Windows mpv IPC remains unimplemented; the supported setup path is Linux inside WSL2.

## Side-by-side album preview and graphics — 12 October 2026

- John confirmed the WSL Windows setup works and uses Windows Terminal.
- Album artwork and album tracks now share a horizontal row; album panel receives two-thirds of the workspace.
- Added pre-UI automatic Sixel/Kitty detection using textual-image on Python 3.12+, explicit renderer options and portable half-block fallback. Windows launcher forwards the renderer into WSL.
- Improved block downsampling with Lanczos/EXIF orientation, raised resolution cap and selected the largest supplied thumbnail by dimensions.
- 36 offline tests passed, including 140x45/80x24 side-by-side bounds, graphics widget update/clear/fallback with a test double, thumbnail choice and odd-height rendering. CLI help, PowerShell/Bash syntax and whitespace checks passed.
- Actual Sixel/Kitty display was not visually verified. Runtime terminal capability detection happens before the Textual input thread starts.

## Spectrum title and volume bar

- Spectrum heading centred; responsive rainbow player-volume bar added below it. +/− updates the bar immediately.
- Eleven UI tests passed, covering title positioning, gradient, 0/100 percent volume, keyboard updates and 80x24/140x45 resizing.

## Playlist deletion and clearing

- D removes the selected row only when the playlist is focused. Ctrl+C clears outside inputs/dialogs and does not quit. Saved state updates after either action.
- Active-track removal and clear stop mpv playback; other deletion preserves current-track indexing and shuffle order. Pending album/play work is cancelled on clear.
- Seventeen queue/UI tests passed, including keyboard guards, current-track deletion, empty saved state and shuffle-index remapping.

## Native Windows migration — 22 October 2026

- Renamed launchers to win_setup.bat and win_start.bat; replaced the PowerShell WSL entry point with native Windows tool installation and .venv-win.
- Native player uses Windows mpv WASAPI and asynchronous named-pipe IPC. Shared protocol code lives in mpv_player.py; macOS has its own CoreAudio wrapper. Native Windows never imports macos_player.
- Windows spectrum uses SoundCard WASAPI speaker loopback; live tone playback/capture succeeded with FFT peak 0.637. No WSLg/PulseAudio or Mac virtual audio device is used.
- Native setup completed successfully using installed Windows tools; native dependency/backend check passed. Fresh-machine winget installation was not exercised.
- Native Windows suite: 45 passed, 2 Unix-transport tests skipped. Linux suite: 46 passed, 1 Windows integration test skipped. Native named-pipe integration, volume commands and error handling passed.
- Source-only packaging passed: 43 allowlisted files, including the new native backends, diagnostics and launchers; no local state, logs or environments included.
- Native Sixel appearance in an interactive terminal still needs user confirmation; the standalone test is available through win_start.bat --test-artwork.