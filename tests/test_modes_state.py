from pathlib import Path
import pytest
from music_term.queue import Queue, Track
from music_term.state import save_playlist, load_playlist
from music_term.terminal import window_title

def tracks(): return [Track(str(i), 'Artist', f'/file{i}') for i in range(5)]

def test_repeat_one_and_manual_next():
    queue = Queue(tracks=tracks(), index=2, repeat='one')
    assert queue.next(automatic=True).title == '2'
    assert queue.next().title == '3'
    queue.index = 4
    queue.repeat = 'all'
    assert queue.next(automatic=True).title == '0'
    assert queue.previous().title == '4'

def test_shuffle_cycle_and_new_tracks():
    queue = Queue(tracks=tracks())
    queue.set_shuffle(True)
    played = []
    while (track := queue.next()) is not None: played.append(track.title)
    assert sorted(played) == ['0','1','2','3','4']
    assert [track.title for track in queue.tracks] == ['0','1','2','3','4']
    queue.repeat = 'all'
    assert queue.next().title != played[-1]
    queue.add(Track('New', 'Artist', '/new'))
    assert len(set(queue._order)) == 6

def test_playlist_roundtrip_and_permissions(tmp_path):
    path = tmp_path / 'tmp' / 'playlist.json'
    queue = Queue(tracks=tracks(), index=3, shuffle=True, repeat='all')
    save_playlist(queue, path)
    restored = load_playlist(path)
    assert restored.tracks == queue.tracks and restored.index == 3
    assert restored.shuffle and restored.repeat == 'all'
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    path.write_text('{broken')
    with pytest.raises(ValueError, match='invalid'): load_playlist(path)

def test_terminal_title_escapes_removed():
    title = window_title(Track('Track\x1b]0;evil\x07', 'Artist\n', '/local'), True)
    assert '\x1b' not in title and '\x07' not in title and '\n' not in title
    assert title.startswith('Paused') and 'music-term' in title


def test_remove_preserves_current_and_shuffle_order():
    queue = Queue(tracks=tracks(), index=3, shuffle=True)
    queue._order = [3, 1, 4, 0, 2]
    queue.remove(1)
    assert queue.index == 2 and queue.tracks[queue.index].title == '3'
    assert queue._order == [2, 3, 0, 1]
    assert queue.remove(99) is None
    queue.remove(2)
    assert queue.tracks[queue.index].title == '4'
    queue.clear()
    assert queue.tracks == [] and queue.index == -1 and queue._order == []
    assert queue.shuffle and queue.repeat == 'off'
