#!/bin/bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_root"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macos_setup.sh must be run on macOS." >&2
  exit 1
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required. Install it from https://brew.sh, then rerun this script." >&2
  exit 1
fi

echo "Installing macOS runtime tools..."
brew install python mpv ffmpeg uv deno libsixel
brew install --cask blackhole-2ch

echo "Creating the locked music-term environment..."
uv sync --locked

echo "Checking mpv and FFmpeg..."
uv run music-term --check
if uv run python -c "from music_term.artwork import configure_renderer; configure_renderer('sixel')" >/dev/null 2>&1; then
  echo "Sixel renderer available"
else
  echo "Sixel renderer unavailable; use the block renderer or check the terminal setup." >&2
fi

if command -v tmux >/dev/null 2>&1; then
  echo "Enabling tmux graphics passthrough..."
  tmux set-option -g allow-passthrough all 2>/dev/null || true
  tmux set-option -g terminal-features 'xterm-kitty:sixel' 2>/dev/null || true

  tmux_config="${TMUX_CONFIG_FILE:-$HOME/.tmux.conf}"
  touch "$tmux_config"
  grep -Fqx 'set -g allow-passthrough all' "$tmux_config" || \
    printf '%s\n' 'set -g allow-passthrough all' >> "$tmux_config"
  grep -Fqx "set -as terminal-features ',xterm-kitty:sixel'" "$tmux_config" || \
    printf '%s\n' "set -as terminal-features ',xterm-kitty:sixel'" >> "$tmux_config"
  echo "Saved tmux passthrough settings to $tmux_config"
fi

echo
echo "Setup complete. Start music-term with:"
echo "  ./macos_start.sh"
echo
echo "BlackHole 2ch was installed for optional system-audio spectrum bars."
echo "Create a Multi-Output Device in Audio MIDI Setup containing your speakers/headphones and BlackHole 2ch."
echo "Set it as the macOS sound output, then start with ./macos_start.sh."
echo "The default spectrum input is AVFoundation device 1 (BlackHole 2ch). Override with:"
echo "  export MUSIC_TERM_MAC_SPECTRUM_DEVICE='1'"
echo "Verify device indexes with: ffmpeg -f avfoundation -list_devices true -i ''"
