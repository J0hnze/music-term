from unittest.mock import MagicMock
import numpy as np
import pytest
from music_term.spectrum import analyze, RATE, WINDOW, AudioMonitor
from music_term.auth import Credentials
from music_term.search import MusicService

def test_spectrum_silence_and_sine():
    assert analyze(bytes(WINDOW * 4)) == [0.0] * 10
    samples = .2 * np.sin(2 * np.pi * 1000 * np.arange(WINDOW) / RATE)
    levels = analyze(samples.astype('<f4').tobytes())
    assert levels.index(max(levels)) == 5
    assert max(levels) > .6
    assert all(0 <= level <= 1 for level in levels)
    with pytest.raises(ValueError): analyze(b'')

async def test_missing_monitor_dependencies(monkeypatch):
    import sys
    import asyncio
    if sys.platform == 'win32':
        monkeypatch.setitem(sys.modules, 'soundcard', None)
        monitor = AudioMonitor()
        await monitor.start()
        try:
            await asyncio.wait_for(monitor.task, 3)
            assert 'unavailable' in monitor.message.lower()
        finally:
            await monitor.close()
        return
    monkeypatch.setattr('music_term.spectrum.shutil.which', lambda name: None)
    monitor = AudioMonitor()
    await monitor.start()
    assert 'install' in monitor.message.lower()
    await monitor.close()

def test_album_search_and_track_order(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    client = MagicMock()
    monkeypatch.setattr('music_term.search.YTMusic', lambda *args: client)
    service = MusicService(Credentials())
    client.search.return_value = [{'title': 'Album', 'browseId': 'MPREtest', 'artists': [{'name': 'Artist'}]}]
    result = service.search('Album', 'albums')[0]
    assert result.is_album and result.album_id == 'MPREtest'
    client.search.assert_called_once_with('Album', filter='albums', limit=30)
    client.get_album.return_value = {'artists': [{'name': 'Artist'}], 'tracks': [
        {'title': 'First', 'videoId': 'one'}, {'title': 'Missing', 'videoId': None},
        {'title': 'Hidden', 'videoId': 'hidden', 'isAvailable': False},
        {'title': 'Second', 'videoId': 'two'}]}
    tracks = service.album_tracks(result.album_id)
    assert [track.title for track in tracks] == ['First', 'Second']
    assert all(track.artist == 'Artist' for track in tracks)
    client.get_album.side_effect = OSError('network')
    with pytest.raises(RuntimeError, match='Album could not be loaded'):
        service.album_tracks('MPREtest')

def test_artwork_render_and_fallback():
    from io import BytesIO
    from PIL import Image
    from music_term.artwork import render_image, load_artwork, artwork_url
    from music_term.queue import Track
    output = BytesIO()
    Image.new('RGB', (40, 40), (200, 10, 50)).save(output, 'PNG')
    rendered = render_image(output.getvalue())
    assert len(rendered.plain.splitlines()) == 8
    assert all(len(line) == 20 for line in rendered.plain.splitlines())
    assert artwork_url(Track('local', '', '/track.wav')) is None
    assert load_artwork(Track('local', '', '/track.wav')).plain == 'No album art'
    assert load_artwork(Track('bad', '', '', artwork='http://localhost/private')).plain == 'Art unavailable'

def test_variable_spectrum_density():
    samples = (.2 * np.sin(2 * np.pi * 1000 * np.arange(WINDOW) / RATE)).astype('<f4').tobytes()
    for count in (10, 20, 60, 120):
        values = analyze(samples, count)
        assert len(values) == count and all(0 <= value <= 1 for value in values)


def test_artwork_aspect_odd_height_and_dimensions():
    from io import BytesIO
    from PIL import Image
    from music_term.artwork import render_image
    output = BytesIO()
    Image.new('RGB', (120, 60), (200, 10, 50)).save(output, 'PNG')
    rendered = render_image(output.getvalue(), 24, 13)
    assert len(rendered.plain.splitlines()) == 7
    assert all(len(line) == 24 for line in rendered.plain.splitlines())
    with pytest.raises(ValueError):
        render_image(output.getvalue(), 0, 12)


def test_renderer_blocks_and_headless_auto(monkeypatch):
    import sys
    import music_term.artwork as artwork
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: False)
    artwork.configure_renderer('auto')
    assert artwork.IMAGE_WIDGET is None
    artwork.configure_renderer('blocks')
    assert artwork.IMAGE_WIDGET is None


async def test_artwork_graphics_update_clear_and_fallback(monkeypatch):
    from io import BytesIO
    from PIL import Image
    from textual.app import App
    from textual.widgets import Static
    import music_term.artwork as artwork
    class FakeGraphic(Static):
        def __init__(self, *, on_error, **kwargs):
            super().__init__(**kwargs)
            self.on_error = on_error
            self.image = None
    monkeypatch.setattr(artwork, 'IMAGE_WIDGET', FakeGraphic)
    art = artwork.Artwork()
    class Preview(App):
        def compose(self):
            yield art
    output = BytesIO()
    Image.new('RGB', (64, 64), (30, 100, 200)).save(output, 'PNG')
    async with Preview().run_test() as pilot:
        art.show_data(output.getvalue())
        await pilot.pause()
        assert art.graphics.display and art.graphics.image.size == (64, 64)
        assert art.render().plain == ''
        art.graphics_error(RuntimeError('unsupported'))
        assert not art.graphics.display
        assert '▀' in art.render().plain
        art.show_data(None, 'Loading art')
        assert art.graphics.image is None
        assert art.render().plain == 'Loading art'
        art.show_data(b'invalid')
        assert not art.graphics.display
        assert art.render().plain == 'Art unavailable'


def test_largest_thumbnail_uses_dimensions_not_order():
    from music_term.search import largest_thumbnail
    assert largest_thumbnail([
        {'url': 'large', 'width': 600, 'height': 600},
        {'url': 'small', 'width': 60, 'height': 60},
        {'url': 'bad', 'width': 'unknown'}]) == 'large'
    assert largest_thumbnail([]) is None
    assert largest_thumbnail([{'url': 'first'}, {'url': 'last'}]) == 'last'
