import pytest
from unittest.mock import AsyncMock
from textual.widgets import Input, DataTable, Select
from music_term.ui import MusicApp, EQModal, AuthModal
from music_term.queue import Track

@pytest.fixture(autouse=True)
def offline_account(monkeypatch, tmp_path):
    monkeypatch.setattr('music_term.state.playlist_path', lambda: tmp_path / 'tmp' / 'playlist.json')
    monkeypatch.setattr('music_term.ui.MusicService.account_name', lambda self: None)
    monkeypatch.setattr('music_term.ui.AudioMonitor.start', AsyncMock())

async def test_keyboard_search_queue_and_modals(monkeypatch):
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    app.service.search = lambda query: [Track('Test song', 'Artist', '/test.wav')]
    app.player.command = AsyncMock(return_value=None)
    async with app.run_test(size=(100, 35)) as pilot:
        await pilot.click('#search')
        await pilot.press('t', 'e', 's', 't', 'enter')
        await pilot.pause()
        await app.workers.wait_for_complete()
        assert app.query_one('#results', DataTable).row_count == 1
        await pilot.press('a')
        assert len(app.queue.tracks) == 1
        await pilot.press('e')
        await pilot.pause()
        assert isinstance(app.screen, EQModal)
        app.screen.query_one('#gain-0', Select).value = 4
        await pilot.pause()
        assert app.eq.gains[0] == 4
        await pilot.press('escape', 'l')
        await pilot.pause()
        assert isinstance(app.screen, AuthModal)
        assert app.screen.query_one('#headers-raw', Input).password
        await pilot.press('escape')

async def test_resize_and_shutdown(monkeypatch):
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    app.player.close = AsyncMock()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press('escape', 'e')
        await pilot.pause()
        await pilot.resize_terminal(60, 18)
        await pilot.pause()
        assert isinstance(app.screen, EQModal)
        await pilot.press('escape')
    app.player.close.assert_awaited_once()

async def test_playback_controls_and_eof(monkeypatch):
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    track = Track('Local', 'Artist', '/fake.wav')
    app.queue.add(track)
    app.service.resolve = lambda track: (track.source, {})
    app.player.load = AsyncMock()
    app.player.command = AsyncMock(return_value=None)
    async with app.run_test() as pilot:
        await pilot.press('escape', 'n')
        await app.workers.wait_for_complete()
        assert app.current == track
        app.player.load.assert_awaited_once_with('/fake.wav', {})
        await pilot.press('space', '+', '-')
        assert app.volume == 70
        assert any(call.args == ('cycle', 'pause') for call in app.player.command.call_args_list)
        app.player.writer = object()
        await app.player.events.put({'event': 'end-file', 'reason': 'eof'})
        await app.poll()
        assert app.queue.index == 0
        app.player.writer = None

async def test_multiline_masked_header_paste(monkeypatch, tmp_path):
    from textual import events
    from textual.widgets import Button
    from music_term.ui import HeaderPasteInput
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    async with app.run_test(size=(100, 50)) as pilot:
        await pilot.press('escape', 'l')
        await pilot.pause()
        modal = app.screen
        field = modal.query_one('#headers-raw', HeaderPasteInput)
        raw = (" " + chr(92) + "\n").join([
            "curl 'https://music.youtube.com/youtubei/v1/browse'",
            "-H 'cookie: FAKE_TEST_ONLY'",
            "-H 'authorization: SAPISIDHASH FAKE_TEST_ONLY'",
            "-H 'x-goog-authuser: 0'",
        ])
        field.post_message(events.Paste(raw))
        await pilot.pause()
        assert field.raw_headers == raw and field.password
        assert 'FAKE_TEST_ONLY' not in field.value
        await modal.on_button_pressed(Button.Pressed(modal.query_one('#import-headers')))
        assert app.credentials.path('browser') is not None
        assert field.raw_headers == '' and field.value == ''
        assert {button.id for button in modal.query(Button)} == {'import-headers', 'disconnect', 'close'}
        await modal.on_button_pressed(Button.Pressed(modal.query_one('#disconnect')))
        assert app.credentials.path('browser') is None


async def test_account_banner(monkeypatch):
    from textual.widgets import Static
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    app.service.account_name = lambda: 'Sample User'
    async with app.run_test(size=(80, 24)):
        await app.workers.wait_for_complete()
        banner = app.query_one('#account', Static)
        assert str(banner.content) == 'Logged in as: Sample User'
        app.service.account_name = lambda: None
        app.refresh_account()
        await app.workers.wait_for_complete()
        assert str(banner.content) == 'Not logged in'
        def failure(): raise RuntimeError('offline')
        app.service.account_name = failure
        app.refresh_account()
        await app.workers.wait_for_complete()
        assert str(banner.content) == 'Login unverified • press l'


async def test_add_album_from_song_and_album_search(monkeypatch):
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    tracks = [Track('First', 'Artist', '/first'), Track('Second', 'Artist', '/second')]
    app.service.album_tracks = lambda album_id: tracks
    app.results = [Track('Song', 'Artist', '/song', 'MPREtest')]
    async with app.run_test() as pilot:
        app.query_one('#results', DataTable).add_row('Song', 'Artist')
        await pilot.press('escape', 'b')
        await app.workers.wait_for_complete()
        assert app.queue.tracks == tracks
        app.results = [Track('Album', 'Artist', '', 'MPREtest', True)]
        app.action_add()
        await app.workers.wait_for_complete()
        assert app.queue.tracks == tracks + tracks
        assert not any(track.is_album for track in app.queue.tracks)

async def test_eq_uses_mpv_filter_string_and_meter_pause(monkeypatch):
    from music_term.spectrum import Spectrum
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    app.player.command = AsyncMock()
    async with app.run_test(size=(80, 24)):
        await app.apply_eq()
        assert isinstance(app.player.command.call_args.args[2], str)
        app.eq.bypass = True
        await app.apply_eq()
        assert app.player.command.call_args.args == ('set_property', 'af', '')
        app.monitor.message = ''
        app.monitor.levels = [1.0] * 10
        app.playback_active = True
        app.render_spectrum()
        meter = app.query_one('#spectrum', Spectrum)
        assert '█' in meter.content.plain
        app.playback_paused = True
        app.render_spectrum()
        assert '█' not in meter.content.plain

async def test_beta_layout_album_preview_and_track_play(monkeypatch):
    from io import BytesIO
    from PIL import Image
    from textual.widgets import Static
    from music_term.artwork import Artwork
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    image = BytesIO()
    Image.new('RGB', (100, 100), (70, 130, 180)).save(image, 'PNG')
    monkeypatch.setattr('music_term.ui.fetch_artwork', lambda track: image.getvalue())
    app = MusicApp()
    tracks = [Track('First', 'Artist', '/first', 'MPREtest', album_title='Album'),
              Track('Second', 'Artist', '/second', 'MPREtest', album_title='Album')]
    app.service.album_tracks = lambda album_id: tracks
    app.service.resolve = lambda track: (track.source, {})
    app.player.load = AsyncMock()
    app.player.command = AsyncMock(return_value=None)
    async with app.run_test(size=(140, 45)) as pilot:
        app.results = [Track('Album', 'Artist', '', 'MPREtest', True)]
        app.query_one('#results', DataTable).add_row('Album', 'Artist')
        await pilot.pause(0.4)
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.query_one('#album-tracks', DataTable).row_count == 2
        assert str(app.query_one('#album-title', Static).content) == 'Album — Artist'
        for size in [(140, 45), (80, 24)]:
            await pilot.resize_terminal(*size)
            await pilot.pause()
            left = app.query_one('#library').region
            right = app.query_one('#album-panel').region
            meter = app.query_one('#spectrum').region
            assert left.right <= right.x and left.y == right.y
            assert meter.y >= left.bottom and meter.width >= left.width + right.width
            assert meter.bottom <= app.query_one('#now').region.y
            art = app.query_one('#artwork', Artwork)
            artwork_column = app.query_one('#artwork-column')
            track_list = app.query_one('#album-tracks', DataTable).region
            assert art.region.right <= track_list.x
            assert artwork_column.region.y == track_list.y
            assert art.region.y == track_list.y + 1
            assert art.region.width > 0 and track_list.width > 0
            assert art.region.width >= track_list.width * 2.5
            assert art.region.bottom <= right.bottom
            assert track_list.bottom <= right.bottom
            rendered = art.render()
            assert rendered.plain.count('▀') > 0
            assert len(rendered.plain.splitlines()) <= art.content_size.height
        app.query_one('#album-tracks', DataTable).focus()
        await pilot.press('enter')
        await app.workers.wait_for_complete()
        assert app.current == tracks[0]
        assert app.queue.tracks == [tracks[0]]

async def test_shuffle_repeat_density_and_space_restore(monkeypatch):
    from music_term.state import save_playlist
    from music_term.queue import Queue
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    tracks = [Track('Saved', 'Artist', '/saved')]
    save_playlist(Queue(tracks=tracks, index=0))
    app = MusicApp()
    app.service.resolve = lambda track: (track.source, {})
    app.player.load = AsyncMock()
    app.player.command = AsyncMock()
    async with app.run_test(size=(100, 35)) as pilot:
        assert app.queue.tracks == tracks and app.current is None
        await pilot.press('escape', 's', 'r', 'k', 'k', 'j', 'space')
        await pilot.pause(.3)
        await app.workers.wait_for_complete()
        assert app.queue.shuffle and app.queue.repeat == 'one'
        assert app.monitor.bar_count == 60
        assert app.current == tracks[0] and 'Saved' in app.title
        await pilot.press('space')
        assert app.playback_paused
        await pilot.press('space')
        assert not app.playback_paused


async def test_c_switches_cached_artwork_renderer(monkeypatch):
    from io import BytesIO
    from PIL import Image
    from music_term.artwork import Artwork
    from textual.widgets import Static
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    async with app.run_test(size=(140, 45)) as pilot:
        art = app.query_one('#artwork', Artwork)
        class FakeGraphic(Static):
            def __init__(self, *, on_error, **kwargs):
                super().__init__(**kwargs)
                self.image = None
        art.renderers = {'auto': None, 'blocks': None, 'sixel': FakeGraphic}
        art.mode = 'auto'
        image = BytesIO()
        Image.new('RGB', (40, 40), (80, 120, 160)).save(image, 'PNG')
        data = image.getvalue()
        art.show_data(data)
        await pilot.press('escape', 'c')
        assert art.mode == 'blocks' and art.graphics is None
        await pilot.press('c')
        assert art.mode == 'sixel' and art.graphics.display
        assert art.graphics.image.size == (40, 40)
        previous = art.graphics
        await pilot.press('c')
        assert art.mode == 'auto' and art.graphics is None
        assert previous not in art.children
        assert art.data == data
        assert 'Artwork mode: auto' in str(app.query_one('#status', Static).content)


async def test_centred_spectrum_and_rainbow_volume(monkeypatch):
    from music_term.spectrum import Spectrum, VolumeBar
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    async with app.run_test(size=(140, 45)) as pilot:
        spectrum = app.query_one('#spectrum', Spectrum)
        bar = app.query_one('#volume-bar', VolumeBar)
        assert bar.region.y >= spectrum.region.bottom
        assert bar.region.bottom <= app.query_one('#modes').region.y
        spectrum.show_levels([.5] * 50)
        heading = spectrum.content.plain.splitlines()[0]
        assert abs((spectrum.content_size.width - len(heading.strip())) // 2 - (len(heading) - len(heading.lstrip()))) <= 1
        for count in (10, 50, 120):
            spectrum.show_levels([1.0] * count)
            bars = spectrum.content.plain.splitlines()[1]
            left = len(bars) - len(bars.lstrip())
            right = spectrum.content_size.width - len(bars.rstrip())
            assert abs(left - right) <= 1
        app.safe_command = AsyncMock()
        await app.action_louder()
        assert bar.volume == app.volume == 75
        await app.action_quieter()
        assert bar.volume == 70
        await app.action_louder()
        assert bar.volume == 75
        await app.action_quieter()
        assert bar.volume == 70
        app.query_one('#search', Input).focus()
        await pilot.press('+', '-')
        assert bar.volume == 70
        assert app.query_one('#search', Input).value == '+-'
        output = bar.render()
        assert 'Volume  70%' in output.plain
        assert '█' in output.plain and '░' in output.plain
        assert len({span.style for span in output.spans}) > 10
        for size in [(80, 24), (140, 45)]:
            await pilot.resize_terminal(*size)
            await pilot.pause()
            assert bar.render().cell_len <= bar.content_size.width
        bar.show_volume(0)
        assert '█' not in bar.render().plain
        bar.show_volume(100)
        assert '░' not in bar.render().plain


async def test_playlist_delete_clear_and_input_guards(monkeypatch):
    from music_term.state import load_playlist
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    app.player.command = AsyncMock()
    items = [Track('First', '', '/first'), Track('Playing', '', '/playing'), Track('Last', '', '/last')]
    async with app.run_test(size=(140, 45)) as pilot:
        app.queue.tracks = items.copy()
        app.queue.index = 1
        app.current = items[1]
        app.playback_active = True
        app.refresh_queue()
        search = app.query_one('#search', Input)
        search.focus()
        await pilot.press('d')
        assert search.value == 'd' and len(app.queue.tracks) == 3
        await pilot.press('ctrl+c')
        assert len(app.queue.tracks) == 3
        table = app.query_one('#queue', DataTable)
        table.focus()
        table.move_cursor(row=0)
        await pilot.press('d')
        assert app.queue.tracks == items[1:] and app.queue.index == 0
        assert app.current == items[1] and app.playback_active
        app.player.writer = object()
        table.move_cursor(row=0)
        await pilot.press('d')
        assert app.queue.tracks == [items[2]]
        assert app.current is None and not app.playback_active
        app.player.command.assert_any_call('stop')
        await pilot.press('ctrl+c')
        assert app.queue.tracks == [] and table.row_count == 0
        assert load_playlist().tracks == []
        assert app.is_running
        app.player.writer = None


async def test_volume_slider_click_and_keyboard(monkeypatch):
    from music_term.spectrum import VolumeBar
    monkeypatch.setattr('music_term.ui.dependencies', lambda: ['mpv', 'ffmpeg'])
    app = MusicApp()
    app.safe_command = AsyncMock()
    async with app.run_test(size=(140, 45)) as pilot:
        bar = app.query_one('#volume-bar', VolumeBar)
        left = bar.content_region.x - bar.region.x + 13
        last = bar.content_size.width - 13 - 1
        y = bar.content_region.y - bar.region.y
        await pilot.click('#volume-bar', offset=(left, y))
        assert app.volume == bar.volume == 0
        assert str(bar.render().spans[-1].style) == '#394554'
        await pilot.click('#volume-bar', offset=(left + last, y))
        assert app.volume == bar.volume == 100
        assert str(bar.render().spans[-1].style) == '#ff0000'
        await pilot.click('#volume-bar', offset=(left + last // 2, y))
        assert 49 <= app.volume <= 51
        await pilot.press('home', 'right')
        assert app.volume == 5
        await pilot.press('end', 'left')
        assert app.volume == 95
        app.safe_command.assert_called_with('set_property', 'volume', 95)
        assert not bar.dragging
        await pilot.mouse_down('#volume-bar', offset=(left, y))
        assert bar.dragging
        await pilot.hover('#volume-bar', offset=(left + last // 2, y))
        assert 49 <= app.volume <= 51
        await pilot.mouse_up('#volume-bar', offset=(left + last, y))
        assert app.volume == 100 and not bar.dragging
