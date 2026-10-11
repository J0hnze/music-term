"""Offline folder scanning and searching (no account or network required)."""
import os
from pathlib import Path
from .queue import Track

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".opus", ".m4a", ".aac", ".wma", ".aiff", ".aif", ".alac"}

def scan_folder(folder: str) -> list[Track]:
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Choose an existing music folder.")
    if not os.access(root, os.R_OK | os.X_OK):
        raise ValueError("Cannot read this folder. Check permissions.")
    tracks = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if name.startswith('.') or path.is_symlink() or path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            if not os.access(path, os.R_OK):
                continue
            tracks.append(Track(path.stem, "Local file", str(path), album_title=path.parent.name))
            if len(tracks) >= 5000:
                return tracks
    return tracks

def filter_tracks(tracks: list[Track], query: str) -> list[Track]:
    words = query.casefold().split()
    return [track for track in tracks if all(word in f"{track.title} {track.artist} {track.source}".casefold() for word in words)]
