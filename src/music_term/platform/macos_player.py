"""macOS mpv playback with optional CoreAudio device routing."""
import os
from .mpv_player import Player as MpvPlayer, dependencies


class Player(MpvPlayer):
    def audio_options(self) -> list[str]:
        device = os.environ.get('MUSIC_TERM_MAC_PLAYER_DEVICE')
        return [f'--audio-device=coreaudio/{device}'] if device else []
