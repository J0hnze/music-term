"""Safe terminal window titles: no track-controlled escape sequences."""
from .queue import Track

def window_title(track: Track | None, paused: bool = False) -> str:
    if track is None:
        return 'music-term'
    text = f'{track.title} — {track.artist} | music-term'
    cleaned = ''.join(character for character in text if character.isprintable())[:200]
    return ('Paused • ' if paused else '') + cleaned
