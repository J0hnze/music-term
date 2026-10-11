"""Album artwork rendered as terminal true-colour half blocks."""
from io import BytesIO
import re
from urllib.parse import urlparse, parse_qs
import requests
from PIL import Image
from rich.text import Text
from textual.widgets import Static
from .queue import Track

def artwork_url(track: Track) -> str | None:
    if track.artwork:
        return track.artwork
    url = urlparse(track.source)
    video = url.path.strip('/') if url.hostname == 'youtu.be' else parse_qs(url.query).get('v', [''])[0]
    return f'https://i.ytimg.com/vi/{video}/hqdefault.jpg' if re.fullmatch(r'[A-Za-z0-9_-]{11}', video) else None

def render_image(data: bytes, width: int = 20, height: int = 16) -> Text:
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > 20_000_000:
            raise ValueError('Artwork too large')
        image = image.convert('RGB')
        # Fit rather than stretch arbitrary artwork; square canvas preserves aspect.
        image.thumbnail((width, height))
        canvas = Image.new('RGB', (width, height), (20, 20, 20))
        canvas.paste(image, ((width-image.width)//2, (height-image.height)//2))
        output = Text()
        for y in range(0, height, 2):
            for x in range(width):
                top, bottom = canvas.getpixel((x,y)), canvas.getpixel((x,y+1))
                output.append('▀', style=f'#{top[0]:02x}{top[1]:02x}{top[2]:02x} on #{bottom[0]:02x}{bottom[1]:02x}{bottom[2]:02x}')
            if y < height - 2:
                output.append('\n')
        return output

def fetch_artwork(track: Track) -> bytes | None:
    url = artwork_url(track)
    if not url:
        return None
    # Accept only thumbnail hosts; never send saved authentication headers.
    host = urlparse(url).hostname or ''
    if urlparse(url).scheme != 'https' or not (host.endswith('.googleusercontent.com') or host.endswith('.ggpht.com') or host.endswith('.ytimg.com')):
        return None
    try:
        with requests.get(url, timeout=(5, 10), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 5_000_000:
                    raise ValueError()
        return bytes(data)
    except Exception:
        return None


def load_artwork(track: Track) -> Text:
    data = fetch_artwork(track)
    if data:
        try:
            return render_image(data)
        except Exception:
            return Text('Art unavailable', style='dim')
    return Text('No album art' if not artwork_url(track) else 'Art unavailable', style='dim')

class Artwork(Static):
    """Resize cached artwork locally without fetching it again."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data: bytes | None = None
        self.message = "No album art"
        self.cached_size = (0, 0)
        self.cached_render = Text(self.message)

    def show_data(self, data: bytes | None, message: str = '') -> None:
        self.data = data
        self.message = message
        self.cached_size = (0, 0)
        self.refresh()

    def render(self) -> Text:
        if not self.data:
            return Text(self.message, style='dim')
        width = max(2, min(60, self.content_size.width, self.content_size.height * 2))
        width -= width % 2
        size = (width, width)
        if self.cached_size != size:
            try:
                self.cached_render = render_image(self.data, *size)
            except Exception:
                self.cached_render = Text('Art unavailable', style='dim')
            self.cached_size = size
        return self.cached_render
