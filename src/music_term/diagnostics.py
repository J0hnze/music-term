"""Opt-in diagnostic logging with sensitive network values removed."""
import logging
import os
from pathlib import Path
import platform
import re
import shutil
from datetime import datetime
from importlib.metadata import version


class RedactedFormatter(logging.Formatter):
    def format(self, record):
        text = super().format(record)
        text = re.sub(r'https?://[^\s\x1b\"\'<>]+', '[URL redacted]', text)
        return re.sub(r'(?im)(authorization|cookie|set-cookie|x-goog-visitor-id|visitor_data)\s*[:=].*', r'\1: [redacted]', text)


def configure() -> Path:
    directory = Path(__file__).resolve().parents[2] / 'tmp'
    directory.mkdir(exist_ok=True)
    path = directory / f'music-term-debug-{datetime.now():%Y-%m-%d-%H%M%S}-{os.getpid()}.log'
    handler = logging.FileHandler(path, encoding='utf-8')
    path.chmod(0o600)
    handler.setFormatter(RedactedFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logger = logging.getLogger('music_term')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    image_logger = logging.getLogger('textual_image')
    image_logger.setLevel(logging.DEBUG)
    image_logger.addHandler(handler)
    logger.info('Platform: %s; Python: %s', platform.platform(), platform.python_version())
    for package in ('yt-dlp', 'ytmusicapi', 'textual', 'textual-image', 'Pillow'):
        logger.info('%s: %s', package, version(package))
    for command in ('mpv', 'ffmpeg', 'pactl', 'deno'):
        logger.info('%s: %s', command, shutil.which(command) or 'MISSING')
    logger.info('Audio server: %s; artwork mode: %s', os.environ.get('PULSE_SERVER', 'default'), os.environ.get('MUSIC_TERM_ARTWORK', 'auto'))
    return path
