import sys
import pytest
from music_term.auth import Credentials, curl_headers

CURL = "curl --url 'https://music.youtube.com/youtubei/v1/browse' -H 'authorization: SAPISIDHASH FAKE_TEST_ONLY' --header='x-goog-authuser: 0' -b 'SAPISID=FAKE_TEST_ONLY' --data-raw '{}'"

def test_curl_only_import(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    credentials = Credentials()
    credentials.import_curl(CURL)
    if sys.platform != 'win32':
        assert credentials.path('browser').stat().st_mode & 0o777 == 0o600
    assert 'cookie: SAPISID=FAKE_TEST_ONLY' in curl_headers(CURL)
    for invalid in ["curl -H @/private/file", '{"context":{}}', 'cookie: FAKE_TEST_ONLY\nx-goog-authuser: 0']:
        with pytest.raises(ValueError):
            credentials.import_curl(invalid)
