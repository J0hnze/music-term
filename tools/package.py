"""Build a source-only archive using an explicit file allowlist."""
from pathlib import Path
import argparse
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    '.gitattributes', 'windows.ps1', 'win_setup.bat', 'win_start.bat', 'macos_setup.sh', 'macos_start.sh', 'tools/windows-wsl.sh',
    '.gitignore', 'uv.lock', 'pyproject.toml', 'README.md', 'LICENSE', 'VERIFICATION.md',
    'src/music_term/__init__.py', 'src/music_term/__main__.py',
    'src/music_term/platform/__init__.py', 'src/music_term/platform/mpv_player.py',
    'src/music_term/platform/windows_player.py', 'src/music_term/platform/windows_audio.py',
    'src/music_term/platform/linux_audio.py', 'src/music_term/platform/macos_player.py', 'src/music_term/platform/macos_audio.py',
    'src/music_term/diagnostics.py',
    'src/music_term/local.py', 'src/music_term/state.py', 'src/music_term/terminal.py', 'src/music_term/auth.py', 'src/music_term/eq.py', 'src/music_term/player.py',
    'src/music_term/artwork.py', 'src/music_term/spectrum.py', 'src/music_term/queue.py', 'src/music_term/search.py', 'src/music_term/ui.py',
    'tests/test_local.py', 'tests/test_spectrum_albums.py', 'tests/test_modes_state.py', 'tests/test_auth.py', 'tests/test_core.py', 'tests/test_ui.py', 'tests/test_diagnostics.py', 'tests/test_windows.py', 'tools/package.py',
]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    output = parser.parse_args().output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for relative in FILES:
            path = ROOT / relative
            if path.is_symlink():
                raise RuntimeError('Symlinks are excluded')
            archive.write(path, 'music-term/' + relative)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert names == ['music-term/' + name for name in FILES]
        assert not any(part in {'.venv', '.git', '__pycache__', '.pytest_cache'}
                       for name in names for part in Path(name).parts)
        assert not any(Path(name).name in {'browser.json', 'cookies.txt'} for name in names)
        for name in names:
            print(name)
    print(f'Verified {len(FILES)} allowlisted source/documentation files; no credential or virtualenv files.')
    print(f'SHA256: {hashlib.sha256(output.read_bytes()).hexdigest()}')
    print(output)

if __name__ == '__main__':
    main()
