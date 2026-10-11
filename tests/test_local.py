from unittest.mock import AsyncMock
from textual.widgets import Input, DataTable
from music_term.local import scan_folder, filter_tracks
from music_term.ui import MusicApp, FolderModal
import pytest


def test_recursive_scan_and_search(tmp_path):
    album = tmp_path / 'Artist' / 'Album'
    album.mkdir(parents=True)
    (album / 'First Song.MP3').write_bytes(b'')
    (album / 'Second.flac').write_bytes(b'')
    (album / 'notes.txt').write_text('ignored')
    hidden = tmp_path / '.hidden'
    hidden.mkdir()
    (hidden / 'secret.mp3').write_bytes(b'')
    tracks = scan_folder(str(tmp_path))
    assert len(tracks) == 2
    assert filter_tracks(tracks, 'artist FIRST')[0].title == 'First Song'
    assert filter_tracks(tracks, '') == tracks
    assert filter_tracks(tracks, 'missing') == []
    with pytest.raises(ValueError):
        scan_folder(str(tmp_path / 'absent'))


async def test_mode_folder_search_and_local_playback(monkeypatch, tmp_path):
    monkeypatch.setattr('music_term.state.playlist_path', lambda: tmp_path / 'state' / 'playlist.json')
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    monkeypatch.setattr('music_term.ui.MusicService.account_name', lambda self: None)
    monkeypatch.setattr('music_term.ui.AudioMonitor.start', AsyncMock())
    (tmp_path / 'First.mp3').write_bytes(b'')
    (tmp_path / 'Second.wav').write_bytes(b'')
    app = MusicApp()
    app.player.load = AsyncMock()
    app.player.command = AsyncMock()
    app.service.search = lambda *args: pytest.fail('Local mode used online search')
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.press('ctrl+m')
        await pilot.pause()
        assert isinstance(app.screen, FolderModal)
        app.screen.query_one(Input).value = str(tmp_path)
        await pilot.press('enter')
        await app.workers.wait_for_complete()
        assert app.local_mode
        assert len(app.results) == 2
        app.query_one('#search', Input).value = 'second'
        await pilot.press('enter')
        await app.workers.wait_for_complete()
        assert app.query_one('#results', DataTable).row_count == 1
        await pilot.press('enter')
        await app.workers.wait_for_complete()
        app.player.load.assert_awaited_with(str(tmp_path / 'Second.wav'), {})
        await pilot.press('ctrl+m')
        assert not app.local_mode
        assert len(app.queue.tracks) == 1
        await pilot.press('ctrl+o')
        await pilot.pause()
        assert isinstance(app.screen, FolderModal)
        await pilot.press('escape')
