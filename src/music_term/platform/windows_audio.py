"""Native WASAPI speaker loopback; samples stay in memory."""
import asyncio
import logging
import threading
import numpy as np
from ..spectrum import analyze, RATE, WINDOW


class AudioMonitor:
    def __init__(self) -> None:
        self.bar_count = 50
        self.levels = [0.0] * self.bar_count
        self.message = 'Starting Windows audio spectrum…'
        self.task = None
        self.stop = threading.Event()

    async def start(self) -> None:
        self.stop.clear()
        self.task = asyncio.create_task(asyncio.to_thread(self._capture))

    def _capture(self) -> None:
        try:
            import soundcard as sc
            speaker = sc.default_speaker()
            if speaker is None:
                raise RuntimeError('No default Windows output device')
            monitor = sc.get_microphone(id=speaker.id, include_loopback=True)
            logging.getLogger(__name__).info('Windows loopback device: %s', speaker.name)
            # Capture all channels: WASAPI single-channel capture is unreliable.
            with monitor.recorder(samplerate=RATE, blocksize=WINDOW) as recorder:
                while not self.stop.is_set():
                    data = recorder.record(numframes=WINDOW)
                    mono = np.mean(data, axis=1).astype('<f4')
                    self.levels = analyze(mono.tobytes(), self.bar_count)
                    self.message = ''
        except Exception as error:
            logging.getLogger(__name__).exception('Windows loopback capture failed')
            self.message = f'Spectrum unavailable: {error}'
            self.levels = [0.0] * self.bar_count

    async def close(self) -> None:
        self.stop.set()
        if self.task:
            try:
                await asyncio.wait_for(asyncio.shield(self.task), 3)
            except TimeoutError:
                logging.getLogger(__name__).warning('Windows audio device did not stop within 3 seconds')
