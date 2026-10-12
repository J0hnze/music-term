"""Real output-monitor spectrum; PCM is analyzed in memory and never saved."""
import asyncio
import colorsys
import shutil
import numpy as np
from rich.text import Text
from textual.widgets import Static
from .eq import BANDS

RATE = 48000
WINDOW = 4096

def analyze(pcm: bytes, bars: int = 10) -> list[float]:
    samples = np.frombuffer(pcm, dtype='<f4')
    if len(samples) != WINDOW:
        raise ValueError('Expected one complete audio window')
    samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
    window = np.hanning(WINDOW)
    magnitudes = np.abs(np.fft.rfft(samples * window)) * 2 / window.sum()
    frequencies = np.fft.rfftfreq(WINDOW, 1 / RATE)
    if not 10 <= bars <= 120:
        raise ValueError('Expected 10–120 bands')
    levels = []
    centers = np.array(BANDS) if bars == 10 else np.geomspace(31, 16000, bars)
    ratio = np.sqrt(2) if bars == 10 else np.sqrt(centers[1] / centers[0])
    for center in centers:
        mask = (frequencies >= center / ratio) & (frequencies < center * ratio)
        power = float(np.sqrt(np.sum(magnitudes[mask] ** 2)))
        db = 20 * np.log10(max(power, 1e-10))
        levels.append(float(np.clip((db + 70) / 65, 0, 1)))
    return levels

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

class Spectrum(Static):
    """Centred spectrum meter; width follows terminal resizing."""
    def show_levels(self, levels: list[float], message: str = '', active: bool = True) -> None:
        if message:
            heading = Text('Audio spectrum', style='cyan')
            heading.truncate(self.content_size.width)
            output = Text(' ' * max(0, (self.content_size.width - heading.cell_len) // 2))
            output.append_text(heading)
            output.append('\n' + message, style='dim')
            self.update(output)
            return
        count = max(1, min(len(levels), self.content_size.width))
        if count < len(levels):
            levels = [max(chunk) for chunk in np.array_split(levels, count)]
        width = max(1, self.content_size.width // count)
        left_padding = (self.content_size.width - count * width) // 2
        rows = max(1, self.content_size.height - 2)
        heights = [round(max(0.0, min(1.0, level)) * rows) if active else 0 for level in levels]
        heading = Text(f'Audio spectrum • {len(levels)} bars • F5 − / F6 + • e: EQ', style='cyan')
        heading.truncate(self.content_size.width)
        output = Text(' ' * max(0, (self.content_size.width - heading.cell_len) // 2))
        output.append_text(heading)
        output.append('\n')
        gap = 1 if width > 1 else 0
        for row in range(rows, 0, -1):
            output.append(" " * left_padding)
            for height in heights:
                output.append(('█' * max(1, width - gap) if height >= row else ' ' * max(1, width - gap)) + (' ' if gap else ''),
                              style='red' if row > rows * .8 else 'yellow' if row > rows * .55 else 'green')
            output.append('\n')
        if width < 4:
            output.append('31 Hz ← low frequencies / high frequencies → 16 kHz'[:self.content_size.width], style='dim')
            self.update(output)
            return
        centers = BANDS if count == 10 else np.geomspace(31, 16000, count)
        output.append(" " * left_padding)
        for hz in centers:
            hz = int(hz)
            label = str(hz) if hz < 1000 else f'{hz // 1000}k'
            output.append(label[:width].center(width), style='dim')
        self.update(output)


class VolumeBar(Static):
    """Rainbow fill represents the player's volume setting, not measured audio."""
    def __init__(self, volume: int = 70, **kwargs):
        super().__init__(**kwargs)
        self.volume = volume

    def show_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, volume))
        self.refresh()

    def render(self) -> Text:
        available = max(1, self.content_size.width)
        label = Text(f'Volume {self.volume:3d}%  ', style='bold cyan')
        label.truncate(available)
        width = max(0, available - label.cell_len)
        filled = round(width * self.volume / 100)
        for index in range(width):
            red, green, blue = colorsys.hsv_to_rgb(index / max(1, width - 1) * .8, 1, 1)
            color = f'#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}'
            label.append('█' if index < filled else '░', style=color if index < filled else '#394554')
        return label
