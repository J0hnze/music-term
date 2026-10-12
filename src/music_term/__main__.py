import argparse
import os
from .player import dependencies

def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal music player")
    parser.add_argument("--check", action="store_true", help="Check system dependencies without starting TUI")
    parser.add_argument("--version", action="version", version="music-term 0.1.0")
    parser.add_argument('--artwork', choices=('auto', 'blocks', 'sixel', 'kitty'),
                        default=os.environ.get('MUSIC_TERM_ARTWORK', 'auto'),
                        help='Album art renderer: detect graphics support, portable blocks, Sixel or Kitty')
    args = parser.parse_args()
    if args.check:
        missing = dependencies()
        print("Missing: " + ", ".join(missing) + ". Install: sudo apt install mpv ffmpeg" if missing else "mpv and FFmpeg available")
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
