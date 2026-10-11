"""Ten octave-spaced FFmpeg equalizers, with conservative headroom."""
from dataclasses import dataclass, field
BANDS = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
PRESETS = {
    "Flat": (0,) * 10,
    "Bass": (6, 5, 3, 1, 0, 0, 0, 0, 0, 0),
    "Treble": (0, 0, 0, 0, 0, 1, 2, 3, 5, 6),
    "Rock": (4, 3, 1, -2, -3, -1, 2, 3, 4, 4),
    "Classical": (3, 2, 0, 0, -1, -1, 0, 2, 3, 3),
}
@dataclass
class Equalizer:
    gains: list[int] = field(default_factory=lambda: [0] * 10)
    bypass: bool = False

    def set_band(self, index: int, gain: int) -> None:
        if not isinstance(gain, int) or not -12 <= gain <= 12:
            raise ValueError("Gain must be an integer from -12 to +12 dB")
        if not 0 <= index < 10:
            raise ValueError("Unknown band")
        self.gains[index] = gain

    def preset(self, name: str) -> None:
        self.gains = list(PRESETS[name])
        self.bypass = False

    def filters(self) -> list[str]:
        if self.bypass:
            return []
        # Sum of positive gains is a conservative bound for overlapping filters.
        headroom = sum(max(0, gain) for gain in self.gains)
        graph = [f"volume=-{headroom}dB"]
        graph += [f"equalizer=f={hz}:t=o:w=1:g={gain}" for hz, gain in zip(BANDS, self.gains)]
        graph += ["alimiter=limit=0.95:level=false"]
        return ["lavfi=[" + ",".join(graph) + "]"]
