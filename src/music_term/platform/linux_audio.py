"""PulseAudio output monitor for Linux and WSLg."""
import asyncio
import shutil
from ..spectrum import analyze, RATE, WINDOW

class AudioMonitor:
    def __init__(self) -> None:
        self.bar_count = 50
        self.levels = [0.0] * self.bar_count
        self.message = 'Starting audio spectrum…'
        self.process: asyncio.subprocess.Process | None = None
        self.task: asyncio.Task | None = None

    async def start(self) -> None:
        if not shutil.which('ffmpeg') or not shutil.which('pactl'):
            self.message = 'Spectrum unavailable: install ffmpeg pulseaudio-utils'
            return
        query = await asyncio.create_subprocess_exec('pactl', 'get-default-sink',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            output, _ = await asyncio.wait_for(query.communicate(), 3)
        except TimeoutError:
            query.kill()
            await query.wait()
            self.message = 'Spectrum unavailable: audio server did not respond'
            return
        sink = output.decode(errors='replace').strip()
        if query.returncode or not sink or '\n' in sink:
            self.message = 'Spectrum unavailable: start PulseAudio or PipeWire-Pulse'
            return
        self.process = await asyncio.create_subprocess_exec('ffmpeg', '-nostdin', '-hide_banner',
            '-loglevel', 'error', '-f', 'pulse', '-sample_rate', str(RATE), '-channels', '1',
            '-i', sink + '.monitor', '-ac', '1', '-ar', str(RATE),
            '-f', 'f32le', 'pipe:1', stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL)
        self.task = asyncio.create_task(self._read())

    async def _read(self) -> None:
        previous = bytes(WINDOW * 2)
        try:
            while True:
                block = await self.process.stdout.readexactly(WINDOW * 2)
                pcm = previous + block
                previous = block
                self.levels = await asyncio.to_thread(analyze, pcm, self.bar_count)
                self.message = ''
        except (asyncio.IncompleteReadError, OSError):
            self.levels = [0.0] * self.bar_count
            self.message = 'Spectrum unavailable: check FFmpeg pulse input and output-monitor access'

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

