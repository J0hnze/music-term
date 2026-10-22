"""Select native playback for the current operating system."""
import shutil
import sys

if sys.platform == 'win32':
    from .platform.windows_player import Player, dependencies
elif sys.platform == 'darwin':
    from .platform.macos_player import Player, dependencies
else:
    from .platform.mpv_player import Player, dependencies

__all__ = ["Player", "dependencies"]
