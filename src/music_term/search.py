from pathlib import Path
import logging
from urllib.parse import urlparse
from ytmusicapi import YTMusic
from yt_dlp import YoutubeDL
from .auth import Credentials
from .queue import Track

def largest_thumbnail(thumbnails: list[dict]) -> str | None:
    """Choose the highest-resolution supplied URL, regardless of API ordering."""
    candidates = [item for item in thumbnails if isinstance(item, dict) and isinstance(item.get('url'), str) and item['url']]
    def area(item):
        width, height = item.get('width', 0), item.get('height', 0)
        return width * height if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0 else 0
    return max(reversed(candidates), key=area)['url'] if candidates else None


class QuietLogger:
    def debug(self, message: str) -> None: logging.getLogger(__name__).debug('yt-dlp: %s', message)
    def warning(self, message: str) -> None: logging.getLogger(__name__).warning('yt-dlp: %s', message)
    def error(self, message: str) -> None: logging.getLogger(__name__).error('yt-dlp: %s', message)

class MusicService:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials

    def account_name(self) -> str | None:
        """Read the authenticated account name without exposing session data."""
        path = self.credentials.path("browser")
        if path is None:
            return None
        try:
            info = YTMusic(str(path)).get_account_info()
            name = info.get("accountName") or info.get("channelHandle")
            if not isinstance(name, str) or not name.strip():
                raise ValueError()
            return "".join(character for character in name if character.isprintable()).strip()
        except Exception:
            raise RuntimeError("Cannot verify account. Check network or paste a fresh signed-in cURL.") from None

    def search(self, query: str, mode: str = "songs") -> list[Track]:
        path = Path(query).expanduser()
        if path.is_file():
            return [Track(path.name, "Local file", str(path.resolve()))]
        parsed = urlparse(query)
        if parsed.scheme in ("http", "https"):
            if parsed.hostname not in {"youtube.com", "www.youtube.com", "music.youtube.com", "youtu.be", "m.youtube.com"}:
                raise ValueError("Paste a YouTube URL or an existing local file path.")
            return [Track("YouTube URL", "", query)]
        try:
            client = YTMusic(str(self.credentials.path("browser"))) if self.credentials.path("browser") else YTMusic()
            results = client.search(query, filter=mode, limit=30)
            if mode == "albums":
                return [Track(r.get("title", "Unknown album"), ", ".join(a.get("name", "") for a in r.get("artists", [])),
                              "", r["browseId"], True, largest_thumbnail(r.get("thumbnails") or [])) for r in results if r.get("browseId")]
            return [Track(r.get("title", "Unknown"), ", ".join(a.get("name", "") for a in r.get("artists", [])),
                          "https://music.youtube.com/watch?v=" + r["videoId"], (r.get("album") or {}).get("id"), False, largest_thumbnail(r.get("thumbnails") or []), (r.get("album") or {}).get("name"))
                    for r in results if r.get("videoId")]
        except Exception:
            raise RuntimeError("Search failed. Check network; paste a fresh signed-in browse cURL request or Disconnect. Try a URL/local path.") from None

    def album_tracks(self, album_id: str) -> list[Track]:
        try:
            path = self.credentials.path("browser")
            client = YTMusic(str(path)) if path else YTMusic()
            album = client.get_album(album_id)
            artist = ", ".join(a.get("name", "") for a in album.get("artists", []))
            tracks = [Track(r.get("title", "Unknown"),
                            ", ".join(a.get("name", "") for a in r.get("artists", [])) or artist,
                            "https://music.youtube.com/watch?v=" + r["videoId"], album_id, False,
                            largest_thumbnail((r.get("thumbnails") or []) + (album.get("thumbnails") or [])), album.get("title"))
                      for r in album.get("tracks", []) if r.get("videoId") and r.get("isAvailable", True)]
            if not tracks:
                raise ValueError()
            return tracks
        except Exception:
            raise RuntimeError("Album could not be loaded. Check network/session; some tracks may be unavailable.") from None

    def resolve(self, track: Track) -> tuple[str, dict[str, str]]:
        logging.getLogger(__name__).info('Resolving stream (local=%s, authenticated=%s)', Path(track.source).is_file(), bool(self.credentials.path('cookies')))
        if Path(track.source).is_file():
            return track.source, {}
        if not urlparse(track.source).scheme:
            raise RuntimeError("Local audio file is missing or unreadable. Open its folder again and re-add the track.")
        options = {"format": "bestaudio/best", "quiet": True, "no_warnings": True,
                   "logger": QuietLogger(), "noplaylist": True, "socket_timeout": 20,
                   "retries": 1, "skip_download": True}
        cookies = self.credentials.path("cookies")
        if cookies:
            options["cookiefile"] = str(cookies)
        try:
            with YoutubeDL(options) as downloader:
                info = downloader.extract_info(track.source, download=False)
                if not info or not info.get("url"):
                    raise ValueError()
                return info["url"], info.get("http_headers", {})
        except Exception:
            logging.getLogger(__name__).exception('Stream resolution failed')
            raise RuntimeError("Stream resolution failed. Check network, update yt-dlp, or try a public track/local file. Some YouTube streams need a JS runtime; see README.") from None
