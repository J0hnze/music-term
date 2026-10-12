#!/usr/bin/env bash
set -euo pipefail
mode="${1:-start}"
dev="${2:-runtime}"
export MUSIC_TERM_ARTWORK="${3:-${MUSIC_TERM_ARTWORK:-auto}}"
case "$MUSIC_TERM_ARTWORK" in auto|blocks|sixel|kitty) ;; *) echo "Unknown artwork renderer" >&2; exit 2 ;; esac
case "$mode" in setup|start|check) ;; *) echo "Unknown mode: $mode" >&2; exit 2 ;; esac
if [[ "$(uname -r)" != *microsoft-standard* && "$(uname -r)" != *WSL2* ]]; then
    echo "Use a WSL2 distribution. From Windows run: wsl --set-version Ubuntu 2" >&2
    exit 1
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_dir"
export PATH="$HOME/.local/bin:$PATH"
# Keep Linux executables separate from any native Windows Python environment.
export UV_PROJECT_ENVIRONMENT="$project_dir/.venv-wsl"
if [[ "$mode" == setup ]]; then
    if ! command -v apt-get >/dev/null; then
        echo "Automatic setup requires Ubuntu/Debian. Install uv, mpv, ffmpeg and pactl manually in your WSL2 distribution." >&2
        exit 1
    fi
    sudo apt-get update
    sudo apt-get install -y mpv ffmpeg pulseaudio-utils curl ca-certificates
    if ! command -v uv >/dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi
    args=(sync --locked --python 3.12)
    if [[ "$dev" == dev ]]; then args+=(--extra dev); fi
    uv "${args[@]}"
    uv run --locked music-term --check
    if ! pactl info >/dev/null 2>&1; then
        echo "Audio server unavailable. Check WSLg, run wsl --update from Windows, and reopen Ubuntu."
    fi
    echo "Setup complete. Run start.bat or windows.ps1 -Mode start."
else
    if ! command -v uv >/dev/null || [[ ! -d "$UV_PROJECT_ENVIRONMENT" ]]; then
        echo "Run setup.bat first (or windows.ps1 -Mode setup)." >&2
        exit 1
    fi
    if [[ "$mode" == check ]]; then
        uv run --locked music-term --check
        pactl info
    else
        exec uv run --locked music-term
    fi
fi
