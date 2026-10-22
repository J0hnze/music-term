import sys
import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from music_term.eq import Equalizer, PRESETS, BANDS
from music_term.auth import Credentials, config_dir
from music_term.queue import Queue, Track
from music_term.player import Player

@pytest.mark.parametrize('gain', [-13, 13, 1.5])
def test_eq_limits(gain):
    with pytest.raises(ValueError):
        Equalizer().set_band(0, gain)

def test_eq_presets():
    eq = Equalizer()
    assert BANDS == (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
    for name, gains in PRESETS.items():
        eq.preset(name)
        assert eq.gains == list(gains)
        assert len(gains) == 10 and all(-12 <= gain <= 12 for gain in gains)
    eq.set_band(0, 12)
    assert 'equalizer=f=31:t=o:w=1:g=12' in eq.filters()[0]
    assert 'volume=-' in eq.filters()[0] and 'alimiter' in eq.filters()[0]
    eq.bypass = True
    assert eq.filters() == []

def test_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    credentials = Credentials()
    source = tmp_path / 'input.json'
    source.write_text(json.dumps({'cookie': 'FAKE_TEST_ONLY', 'authorization': 'FAKE_TEST_ONLY'}))
    credentials.import_file('browser', str(source))
    assert config_dir() == tmp_path / 'config' / 'music-term'
    if sys.platform != 'win32':
        assert config_dir().stat().st_mode & 0o777 == 0o700
    if sys.platform != 'win32':
        assert credentials.path('browser').stat().st_mode & 0o777 == 0o600
    cookies = tmp_path / 'input.txt'
    cookies.write_text('# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t2147483647\ttest\tFAKE_TEST_ONLY\n')
    credentials.import_file('cookies', str(cookies))
    if sys.platform != 'win32':
        assert credentials.path('cookies').stat().st_mode & 0o777 == 0o600
    credentials.disconnect()
    assert credentials.path('browser') is None and credentials.path('cookies') is None
    assert source.exists()
    source.write_text('Cookie: fake')
    with pytest.raises(ValueError):
        credentials.import_file('cookies', str(source))

def test_relative_config_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    monkeypatch.setenv('XDG_CONFIG_HOME', 'relative')
    assert config_dir() == tmp_path / '.config' / 'music-term'

def test_queue():
    queue = Queue()
    assert queue.next() is None and queue.previous() is None
    tracks = [Track(str(i), 'Artist', '/fake') for i in range(3)]
    for track in tracks: queue.add(track)
    assert queue.next() == tracks[0]
    assert queue.next() == tracks[1]
    assert queue.previous() == tracks[0]
    assert queue.select(2) == tracks[2]
    assert queue.next() is None and queue.index == 2
    assert queue.select(99) is None

@pytest.mark.skipif(sys.platform == 'win32', reason='Unix-socket transport; Windows pipe tested separately')
async def test_ipc_correlates_events_and_responses(tmp_path):
    async def serve(reader, writer):
        request = json.loads(await reader.readline())
        writer.write(b'{"event":"file-loaded"}\n')
        writer.write((json.dumps({'request_id': request['request_id'], 'error': 'success', 'data': 42}) + '\n').encode())
        await writer.drain()
        await reader.read()
        writer.close()
        await writer.wait_closed()
    path = str(tmp_path / 'ipc')
    server = await asyncio.start_unix_server(serve, path)
    player = Player()
    player.reader, player.writer = await asyncio.open_unix_connection(path)
    player.task = asyncio.create_task(player._read())
    assert await player.command('get_property', 'volume') == 42
    assert (await player.events.get())['event'] == 'file-loaded'
    assert player.pending == {}
    await player.close()
    server.close()
    await server.wait_closed()

async def test_load_clears_headers_and_unpauses():
    player = Player()
    player.command = AsyncMock()
    await player.load('/local.wav', {})
    assert player.command.call_args_list[0].args == ('set_property', 'http-header-fields', [])
    assert player.command.call_args_list[1].args == ('loadfile', '/local.wav', 'replace')
    assert player.command.call_args_list[2].args == ('set_property', 'pause', False)

async def test_missing_mpv(monkeypatch):
    monkeypatch.setattr('music_term.player.shutil.which', lambda _: None)
    with pytest.raises(RuntimeError, match='mpv is missing'):
        await Player().start()

@pytest.mark.skipif(sys.platform == 'win32', reason='Unix-socket transport; Windows pipe tested separately')
async def test_ipc_rejection(tmp_path):
    async def serve(reader, writer):
        request = json.loads(await reader.readline())
        writer.write((json.dumps({'request_id': request['request_id'], 'error': 'invalid parameter'}) + '\n').encode())
        await writer.drain()
        await reader.read()
        writer.close()
        await writer.wait_closed()
    server = await asyncio.start_unix_server(serve, str(tmp_path / 'ipc'))
    player = Player()
    player.reader, player.writer = await asyncio.open_unix_connection(str(tmp_path / 'ipc'))
    player.task = asyncio.create_task(player._read())
    with pytest.raises(RuntimeError, match='rejected'):
        await player.command('set_property', 'af', ['unsupported'])
    assert player.pending == {}
    await player.close()
    server.close()
    await server.wait_closed()
