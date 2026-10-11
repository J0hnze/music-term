"""Private credential storage for copied cURL authentication."""
import json
import shlex
from urllib.parse import urlparse
import os
from pathlib import Path
import tempfile
import http.cookiejar

def config_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    if not base.is_absolute():
        base = Path.home() / ".config"
    path = base / "music-term"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path

def curl_headers(raw: str) -> str:
    """Extract literal headers from copied POSIX cURL, never execute/read files."""
    tokens = shlex.split(raw.replace("\\\n", " "))
    if not tokens or tokens[0] != "curl":
        raise ValueError("Expected copied cURL")
    urls = [urlparse(token) for token in tokens if token.startswith("https://")]
    if not any(url.hostname == "music.youtube.com" and url.path == "/youtubei/v1/browse" for url in urls):
        raise ValueError("Expected a YouTube Music browse request")
    headers: list[str] = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        value = None
        cookie = False
        if token in {"-H", "--header", "-b", "--cookie"}:
            index += 1
            value = tokens[index]
            cookie = token in {"-b", "--cookie"}
        elif token.startswith("--header="):
            value = token.split("=", 1)[1]
        elif token.startswith("--cookie="):
            value = token.split("=", 1)[1]
            cookie = True
        elif token.startswith("-H") and len(token) > 2:
            value = token[2:]
        elif token in {"--data", "--data-raw", "--data-binary", "-d", "--url", "-X", "--request"}:
            index += 1  # Ignore bodies and other arguments entirely.
        if value is not None:
            if value.startswith("@") or "\n" in value or "\r" in value:
                raise ValueError("Only literal headers are supported")
            if cookie:
                if "=" not in value:
                    raise ValueError("Cookie file references are unsupported")
                headers.append("cookie: " + value)
            elif ":" in value:
                name, content = value.split(":", 1)
                headers.append(name.strip() + ": " + content.strip())
        index += 1
    return "\n".join(headers)

class Credentials:
    names = {"browser": "browser.json", "cookies": "cookies.txt"}

    def path(self, kind: str) -> Path | None:
        path = config_dir() / self.names[kind]
        return path if path.is_file() else None

    def import_file(self, kind: str, source: str) -> None:
        try:
            data = Path(source).expanduser().read_bytes()
            if kind == "browser":
                headers = json.loads(data)
                if not isinstance(headers, dict):
                    raise ValueError()
                keys = {key.lower() for key in headers}
                if not {"cookie", "authorization"} <= keys:
                    raise ValueError()
            else:
                jar = http.cookiejar.MozillaCookieJar(source)
                jar.load(ignore_discard=True, ignore_expires=True)
                if not list(jar):
                    raise ValueError()
        except Exception:
            raise ValueError("Invalid credential file. Use browser headers JSON or Netscape cookies as labeled.") from None
        self._save(kind, data)

    def import_curl(self, raw: str) -> None:
        """Only accept copied cURL; parse locally without executing anything."""
        from ytmusicapi import setup
        try:
            headers = curl_headers(raw)
            if not headers:
                raise ValueError("No headers found")
            self.save_browser_json(setup(headers_raw=headers))
        except Exception:
            raise ValueError("Invalid cURL. Copy as cURL (bash) from a successful signed-in POST /browse request; plain headers and payloads are not accepted.") from None

    def save_browser_json(self, data: str) -> None:
        headers = json.loads(data)
        if not isinstance(headers, dict) or not {"cookie", "authorization"} <= {key.lower() for key in headers}:
            raise ValueError("Invalid browser JSON")
        self._save("browser", data.encode())

    def _save(self, kind: str, data: bytes) -> None:
        directory = config_dir()
        fd, temp = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(data)
            os.chmod(temp, 0o600)
            os.replace(temp, directory / self.names[kind])
        finally:
            Path(temp).unlink(missing_ok=True)

    def disconnect(self) -> None:
        for name in self.names.values():
            (config_dir() / name).unlink(missing_ok=True)
