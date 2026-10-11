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
