import argparse
import os
import sys
from .player import dependencies

def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal music player")
    parser.add_argument("--check", action="store_true", help="Check system dependencies without starting TUI")
    parser.add_argument("--version", action="version", version="music-term 0.1.0")
    parser.add_argument('--artwork', choices=('auto', 'blocks', 'sixel', 'kitty'),
                        default=os.environ.get('MUSIC_TERM_ARTWORK', 'auto'),
                        help='Album art renderer: detect graphics support, portable blocks, Sixel or Kitty')
    parser.add_argument('--debug', '--deugb', action='store_true', help='Save diagnostic log under tmp/')
    parser.add_argument('--test-artwork', action='store_true', help='Display a standalone Sixel colour test and exit')
    args = parser.parse_args()
    if args.debug or os.environ.get('MUSIC_TERM_DEBUG') == '1':
        from .diagnostics import configure
        print(f'Debug log: {configure()}', flush=True)
    if args.test_artwork:
        from .artwork import test_sixel
        test_sixel()
        return
    if args.check:
        missing = dependencies()
        install = 'run win_setup.bat' if sys.platform == 'win32' else 'install mpv and FFmpeg with your package manager'
        print('Missing: ' + ', '.join(missing) + '. ' + install if missing else 'mpv and FFmpeg available')
        from .player import Player
        from .spectrum import AudioMonitor
        print(f'Playback backend: {Player.__module__}; spectrum: {AudioMonitor.__module__}')
        raise SystemExit(1 if missing else 0)
    from .artwork import configure_renderer
    try:
        configure_renderer(args.artwork)
    except ValueError as error:
        parser.error(str(error))
    from .ui import MusicApp
    MusicApp().run()

if __name__ == "__main__":
    main()
