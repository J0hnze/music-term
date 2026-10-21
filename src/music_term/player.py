"""Compatibility facade for the active macOS/mpv playback backend."""
import shutil

from .platform.macos_player import Player, dependencies

__all__ = ["Player", "dependencies"]
