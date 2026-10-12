"""Album artwork rendered as terminal true-colour half blocks."""
from io import BytesIO
import re
from urllib.parse import urlparse, parse_qs
import requests
from PIL import Image, ImageOps
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
    if width < 1 or height < 1:
        raise ValueError('Artwork dimensions must be positive')
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > 20_000_000:
            raise ValueError('Artwork too large')
        image = ImageOps.exif_transpose(image).convert('RGB')
        # Fit rather than stretch arbitrary artwork; square canvas preserves aspect.
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (width, height), (20, 20, 20))
        canvas.paste(image, ((width-image.width)//2, (height-image.height)//2))
        output = Text()
        for y in range(0, height, 2):
            for x in range(width):
                top, bottom = canvas.getpixel((x,y)), canvas.getpixel((x,min(y+1, height-1)))
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

IMAGE_WIDGET = None
RENDERER_MODE = 'auto'
RENDERERS = {'auto': None, 'blocks': None}


def configure_renderer(mode: str = 'auto') -> None:
    """Probe graphics before Textual starts its input thread; blocks stay portable."""
    import sys
    global IMAGE_WIDGET, RENDERER_MODE, RENDERERS
    if mode not in {'auto', 'blocks', 'sixel', 'kitty'}:
        raise ValueError('Unknown artwork renderer; choose auto, blocks, sixel or kitty.')
    IMAGE_WIDGET = None
    RENDERER_MODE = mode
    RENDERERS = {'auto': None, 'blocks': None}
    if not sys.stdout.isatty() and mode in {'auto', 'blocks'}:
        return
    try:
        from textual_image.widget import Image as AutoImage, SixelImage, TGPImage
        from textual_image.renderable import Image as AutoRenderable
        detected = AutoRenderable.__module__.rsplit('.', 1)[-1]
        if detected in {'sixel', 'tgp'}:
            RENDERERS['auto'] = AutoImage
            RENDERERS['sixel' if detected == 'sixel' else 'kitty'] = SixelImage if detected == 'sixel' else TGPImage
        if mode == 'sixel':
            RENDERERS['sixel'] = SixelImage
            IMAGE_WIDGET = SixelImage
        elif mode == 'kitty':
            RENDERERS['kitty'] = TGPImage
            IMAGE_WIDGET = TGPImage
        elif mode == 'auto' and AutoRenderable.__module__.endswith(('.sixel', '.tgp')):
            IMAGE_WIDGET = AutoImage
    except (ImportError, OSError, RuntimeError) as error:
        if mode != 'auto':
            raise ValueError('Graphics renderer unavailable; use Python 3.12+, run uv sync, or choose --artwork blocks.') from error


class Artwork(Static):
    """Resize cached artwork locally without fetching it again."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        import asyncio
        self.mode = RENDERER_MODE
        self.renderers = dict(RENDERERS)
        self.switch_lock = asyncio.Lock()
        self.graphics = IMAGE_WIDGET(id="artwork-image", on_error=self.graphics_error) if IMAGE_WIDGET else None
        self.data: bytes | None = None
        self.message = "No album art"
        self.cached_size = (0, 0)
        self.cached_render = Text(self.message)

    def compose(self):
        if self.graphics:
            self.graphics.display = False
            yield self.graphics

    async def cycle_mode(self) -> str:
        """Switch cached renderers without probing the running terminal or refetching art."""
        async with self.switch_lock:
            modes = list(self.renderers)
            index = modes.index(self.mode) if self.mode in modes else -1
            self.mode = modes[(index + 1) % len(modes)]
            previous = self.graphics
            self.graphics = None
            if previous:
                previous.image = None
                await previous.remove()
            factory = self.renderers[self.mode]
            if factory:
                self.graphics = factory(id='artwork-image', on_error=self.graphics_error)
                self.graphics.display = False
                await self.mount(self.graphics)
            self.show_data(self.data, self.message)
            self.refresh(layout=True)
            return self.mode

    def graphics_error(self, error):
        self.graphics.display = False
        self.refresh()
        return Static('')

    def show_data(self, data: bytes | None, message: str = '') -> None:
        self.data = data
        self.message = message
        self.cached_size = (0, 0)
        if self.graphics:
            try:
                image = None
                if data:
                    with Image.open(BytesIO(data)) as source:
                        if source.width * source.height > 20_000_000:
                            raise ValueError('Artwork too large')
                        image = ImageOps.exif_transpose(source).convert('RGB')
                self.graphics.image = image
                self.graphics.display = image is not None
            except (OSError, ValueError):
                self.graphics.display = False
        self.refresh()

    def render(self) -> Text:
        if self.graphics and self.graphics.display:
            return Text('')
        if not self.data:
            return Text(self.message, style='dim')
        width = max(2, min(160, self.content_size.width, self.content_size.height * 2))
        width -= width % 2
        size = (width, width)
        if self.cached_size != size:
            try:
                self.cached_render = render_image(self.data, *size)
            except Exception:
                self.cached_render = Text('Art unavailable', style='dim')
            self.cached_size = size
        return self.cached_render
