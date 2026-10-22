import logging
from music_term.diagnostics import RedactedFormatter


def test_diagnostic_redaction():
    record = logging.LogRecord('music_term', logging.ERROR, '', 0,
        'HTTP 403 https://example.com/stream?sig=secret\nCookie: SID=secret\nAuthorization: Bearer secret', (), None)
    output = RedactedFormatter().format(record)
    assert 'HTTP 403' in output
    assert 'secret' not in output
    assert '[URL redacted]' in output


def test_remote_artwork_never_checks_url_as_local_path(monkeypatch):
    from pathlib import Path
    from unittest.mock import MagicMock
    from music_term.artwork import fetch_artwork
    from music_term.queue import Track
    monkeypatch.setattr(Path, 'is_file', lambda self: (_ for _ in ()).throw(OSError('Filename too long')))
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_content.return_value = [b'image']
    monkeypatch.setattr('music_term.artwork.requests.get', lambda *a, **kw: response)
    assert fetch_artwork(Track('test', '', '', artwork='https://lh3.googleusercontent.com/' + 'a' * 300)) == b'image'


def test_linux_monitor_selected():
    import sys
    from music_term.spectrum import AudioMonitor
    assert AudioMonitor.__module__ == ('music_term.platform.macos_audio' if sys.platform == 'darwin' else 'music_term.platform.linux_audio')
