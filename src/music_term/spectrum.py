"""Real output-monitor spectrum; PCM is analyzed in memory and never saved."""
import colorsys
import shutil
import sys
import numpy as np
from rich.text import Text
from textual.widgets import Static
from textual.message import Message
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

if sys.platform == 'darwin':
    from .platform.macos_audio import AudioMonitor
else:
    from .platform.linux_audio import AudioMonitor

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
        gap = 1 if width > 1 else 0
        # The last bar has no trailing gap: centre the visible bars themselves.
        left_padding = (self.content_size.width - (count * width - gap)) // 2
        rows = max(1, self.content_size.height - 2)
        heights = [round(max(0.0, min(1.0, level)) * rows) if active else 0 for level in levels]
        heading = Text(f'Audio spectrum • {len(levels)} bars • j: EQ− / k: EQ+ • e: EQ', style='cyan')
        heading.truncate(self.content_size.width)
        output = Text(' ' * max(0, (self.content_size.width - heading.cell_len) // 2))
        output.append_text(heading)
        output.append('\n')
        for row in range(rows, 0, -1):
            output.append(" " * left_padding)
            for index, height in enumerate(heights):
                output.append(('█' * max(1, width - gap) if height >= row else ' ' * max(1, width - gap)) + (' ' if gap and index < count - 1 else ''),
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


class VolumeBar(Static, can_focus=True):
    """Rainbow fill represents the player's volume setting, not measured audio."""
    class Changed(Message):
        def __init__(self, volume: int):
            super().__init__()
            self.volume = volume

    BINDINGS = [('left', 'lower', 'Lower volume'), ('right', 'raise', 'Raise volume'),
                ('home', 'minimum', 'Mute'), ('end', 'maximum', 'Maximum volume')]

    def __init__(self, volume: int = 70, **kwargs):
        super().__init__(**kwargs)
        self.volume = volume
        self.dragging = False

    def show_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, volume))
        self.refresh()

    def set_volume(self, volume: int) -> None:
        self.show_volume(volume)
        self.post_message(self.Changed(self.volume))

    def action_lower(self):
        self.set_volume(self.volume - 5)

    def action_raise(self):
        self.set_volume(self.volume + 5)

    def action_minimum(self):
        self.set_volume(0)

    def action_maximum(self):
        self.set_volume(100)

    def mouse_volume(self, event, clamp: bool = False):
        label_width = len(f'Volume {self.volume:3d}%  ')
        width = self.content_size.width - label_width
        position = event.screen_x - self.content_region.x - label_width
        if width <= 1 or (not clamp and not 0 <= position < width):
            return None
        return round(max(0, min(width - 1, position)) / (width - 1) * 100)

    def on_mouse_down(self, event):
        if event.button != 1:
            return
        volume = self.mouse_volume(event)
        if volume is not None:
            event.stop()
            self.focus()
            self.dragging = True
            self.capture_mouse()
            self.set_volume(volume)

    def on_mouse_move(self, event):
        if self.dragging:
            event.stop()
            volume = self.mouse_volume(event, clamp=True)
            if volume is not None and volume != self.volume:
                self.set_volume(volume)

    def on_mouse_up(self, event):
        if self.dragging and event.button == 1:
            event.stop()
            volume = self.mouse_volume(event, clamp=True)
            if volume is not None and volume != self.volume:
                self.set_volume(volume)
            self.dragging = False
            self.release_mouse()

    def render(self) -> Text:
        available = max(1, self.content_size.width)
        label = Text(f'Volume {self.volume:3d}%  ', style='bold cyan')
        label.truncate(available)
        width = max(0, available - label.cell_len)
        filled = round(width * self.volume / 100)
        for index in range(width):
            red, green, blue = colorsys.hsv_to_rgb((1 - index / max(1, width - 1)) * (2 / 3), 1, 1)
            color = f'#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}'
            thumb = round(max(0, width - 1) * self.volume / 100)
            label.append('●' if index == thumb else ('█' if index < filled else '░'), style=color if index <= thumb else '#394554')
        return label
