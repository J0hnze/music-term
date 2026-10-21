"""macOS audio-monitor backend.

Playback uses mpv's Unix IPC, which macOS supports. Spectrum monitoring is
optional and uses FFmpeg's AVFoundation input. To monitor system playback,
install a virtual audio device such as BlackHole 2ch and route mpv through it.
"""
import asyncio
import os
import shutil
import sys

from ..spectrum import analyze, RATE, WINDOW


class AudioMonitor:
    def __init__(self) -> None:
        self.bar_count = 50
        self.levels = [0.0] * self.bar_count
        self.message = 'Starting audio spectrum…'
        self.process: asyncio.subprocess.Process | None = None
        self.task: asyncio.Task | None = None

    async def start(self) -> None:
        if not shutil.which('ffmpeg'):
            self.message = 'Spectrum unavailable: install FFmpeg'
            return
        if sys.platform != 'darwin':
            self.message = 'Spectrum unavailable: this backend requires macOS'
            return

        # AVFoundation expects the numeric device index after the colon.
        # Homebrew's BlackHole 2ch is normally device 1; override this when
        # another order is reported by ffmpeg's AVFoundation device listing.
        device = os.environ.get('MUSIC_TERM_MAC_SPECTRUM_DEVICE', '1')
        self.process = await asyncio.create_subprocess_exec('ffmpeg', '-nostdin', '-hide_banner',
            '-loglevel', 'error', '-f', 'avfoundation', '-audio_device_index', device,
            '-i', ':', '-ac', '1', '-ar', str(RATE),
            '-f', 'f32le', 'pipe:1', stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        self.task = asyncio.create_task(self._read())

    async def _read(self) -> None:
        previous = bytes(WINDOW * 2)
        try:
            while True:
                block = await self.process.stdout.readexactly(WINDOW * 2)
                pcm = previous + block
                previous = block
                self.levels = await asyncio.to_thread(analyze, pcm, self.bar_count)
                self.message = '' if max(self.levels, default=0.0) > 0.001 else 'Spectrum waiting for audio on BlackHole 2ch'
        except (asyncio.IncompleteReadError, OSError):
            self.levels = [0.0] * self.bar_count
            device = os.environ.get('MUSIC_TERM_MAC_SPECTRUM_DEVICE', '1')
            self.message = f'Spectrum unavailable: install/configure a macOS audio monitor ({device})'

    async def close(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 2)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
