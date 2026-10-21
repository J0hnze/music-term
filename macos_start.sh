#!/bin/bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_root"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macos_start.sh must be run on macOS." >&2
  exit 1
fi

command -v uv >/dev/null 2>&1 || {
  echo "uv is missing. Run ./macos_setup.sh first." >&2
  exit 1
}

if [[ -n "${TMUX:-}" ]] && command -v tmux >/dev/null 2>&1; then
  tmux set-option -g allow-passthrough all 2>/dev/null || true
  tmux set-option -g terminal-features 'xterm-kitty:sixel' 2>/dev/null || true
fi

# Textual's injected Sixel/Kitty image data is not reliable through tmux, even
# when tmux reports passthrough support. Use the color block renderer there so
# downloaded artwork is always visible. Native graphics remain available when
# launched outside tmux.
has_artwork_arg=false
for arg in "$@"; do
  [[ "$arg" == "--artwork" ]] && has_artwork_arg=true
done
if [[ "$has_artwork_arg" == false ]]; then
  default_artwork=blocks
  if [[ -z "${TMUX:-}" && ( "${TERM:-}" == *kitty* || -n "${KITTY_WINDOW_ID:-}" ) ]]; then
    default_artwork=kitty
  fi
  set -- --artwork "$default_artwork" "$@"
fi

exec uv run music-term "$@"
