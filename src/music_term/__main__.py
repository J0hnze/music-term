import argparse
from .player import dependencies

def main() -> None:
    parser = argparse.ArgumentParser(description="Terminal music player")
    parser.add_argument("--check", action="store_true", help="Check system dependencies without starting TUI")
    parser.add_argument("--version", action="version", version="music-term 0.1.0")
    args = parser.parse_args()
    if args.check:
        missing = dependencies()
        print("Missing: " + ", ".join(missing) + ". Install: sudo apt install mpv ffmpeg" if missing else "mpv and FFmpeg available")
        raise SystemExit(1 if missing else 0)
    from .ui import MusicApp
    MusicApp().run()

if __name__ == "__main__":
    main()
