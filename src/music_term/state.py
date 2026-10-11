"""Private, atomic playlist persistence inside the editable project tmp folder."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from .queue import Queue, Track

def playlist_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / 'tmp' / 'playlist.json'

def save_playlist(queue: Queue, path: Path | None = None) -> None:
    path = path or playlist_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    data = {'version': 1, 'tracks': [asdict(track) for track in queue.tracks],
            'index': queue.index, 'shuffle': queue.shuffle, 'repeat': queue.repeat}
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(data, output)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)

def load_playlist(path: Path | None = None) -> Queue:
    path = path or playlist_path()
    if not path.exists():
        return Queue()
    try:
        if path.stat().st_size > 5_000_000:
            raise ValueError()
        data = json.loads(path.read_text())
        if data.get('version') != 1 or not isinstance(data['tracks'], list) or len(data['tracks']) > 5000:
            raise ValueError()
        tracks = [Track(**record) for record in data['tracks']]
        if any(not isinstance(track.title, str) or not isinstance(track.artist, str)
               or not isinstance(track.source, str) or track.is_album for track in tracks):
            raise ValueError()
        index = data.get('index', -1)
        if not isinstance(index, int) or not -1 <= index < max(1, len(tracks)):
            raise ValueError()
        repeat = data.get('repeat', 'off')
        if repeat not in {'off', 'one', 'all'} or not isinstance(data.get('shuffle', False), bool):
            raise ValueError()
        return Queue(tracks=tracks, index=index, shuffle=data.get('shuffle', False), repeat=repeat)
    except (ValueError, TypeError, KeyError):
        raise ValueError('Saved playlist is invalid. Rename or remove tmp/playlist.json to reset it.') from None
