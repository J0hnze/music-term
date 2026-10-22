import asyncio
import shutil
import sys
from types import SimpleNamespace
import numpy as np
import pytest
from music_term.platform.windows_player import Player


def test_windows_endpoint_and_audio_ignore_macos_settings(monkeypatch):
    monkeypatch.setenv('MUSIC_TERM_MAC_PLAYER_DEVICE', 'BlackHole 2ch')
    first, second = Player(), Player()
    assert first.prepare_endpoint().startswith('\\\\.\\pipe\\music-term-')
    assert first.pipe_name != second.prepare_endpoint()
    assert first.audio_options() == ['--ao=wasapi']
    assert first.directory is None


@pytest.mark.skipif(sys.platform != 'win32' or not shutil.which('mpv'), reason='Requires native Windows mpv')
async def test_native_named_pipe_ipc_and_errors():
    player = Player()
    try:
        await player.start()
        assert 'mpv' in await player.command('get_property', 'mpv-version')
        assert await player.command('get_property', 'pid') == player.process.pid
        await player.command('set_property', 'volume', 35)
        assert await player.command('get_property', 'volume') == 35
        with pytest.raises(RuntimeError, match='rejected'):
            await player.command('not-a-real-command')
        assert player.pending == {}
    finally:
        await player.close()
    assert player.process.returncode is not None


async def test_windows_loopback_mixes_channels_and_stops(monkeypatch):
    from music_term.platform.windows_audio import AudioMonitor
    from music_term.spectrum import RATE, WINDOW
    monitor = AudioMonitor()
    class Recorder:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def record(self, numframes):
            monitor.stop.set()
            tone = .2 * np.sin(2 * np.pi * 1000 * np.arange(WINDOW) / RATE)
            return np.column_stack((tone, tone))
    def microphone(*, id, include_loopback):
        assert id == 'speakers' and include_loopback
        return SimpleNamespace(recorder=lambda **kwargs: Recorder())
    monkeypatch.setitem(sys.modules, 'soundcard', SimpleNamespace(
        default_speaker=lambda: SimpleNamespace(id='speakers', name='Test speaker'),
        get_microphone=microphone))
    await monitor.start()
    await asyncio.wait_for(monitor.task, 3)
    assert max(monitor.levels) > .6 and not monitor.message
    await monitor.close()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows console input records')
def test_synthetic_mouse_records_are_not_search_keystrokes():
    from music_term.platform.windows_input import key_character
    from textual._xterm_parser import XTermParser
    from textual.events import Key, MouseMove
    parser = XTermParser()
    output = []
    # ConPTY may tag ESC with a control modifier and virtual-key zero.
    for char in '\x1b[<35;46;23M':
        record = SimpleNamespace(bKeyDown=True, dwControlKeyState=8,
            wVirtualKeyCode=0, uChar=SimpleNamespace(UnicodeChar=char))
        output.extend(parser.feed(key_character(record)))
    assert len(output) == 1 and isinstance(output[0], MouseMove)
    assert not any(isinstance(event, Key) for event in output)
    assert output[0].x == 45 and output[0].y == 22
    null = SimpleNamespace(bKeyDown=True, uChar=SimpleNamespace(UnicodeChar='\x00'))
    assert key_character(null) == ''
    from music_term.ui import MusicApp
    from music_term.platform.windows_input import NativeWindowsDriver
    assert MusicApp().driver_class is NativeWindowsDriver
