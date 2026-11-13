"""Build a portable skill ZIP containing only its canonical source files."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def release_files(source):
    names = (ROOT / 'tools' / 'skill-files.txt').read_text(encoding='utf-8').splitlines()
    paths = []
    for name in names:
        relative = Path(name)
        path = source / relative
        if (relative.is_absolute() or '..' in relative.parts or '__pycache__' in relative.parts
                or relative.suffix not in {'.md', '.py', '.txt', '.js', '.html', '.css', '.yaml'}
                or not path.is_file() or path.resolve() != path.absolute()):
            raise ValueError(f'Invalid release member: {name}')
        paths.append(path)
    if len(set(paths)) != len(paths):
        raise ValueError('Duplicate release members')
    return paths


def package(destination):
    source = ROOT / 'skills' / 'careerpilot'
    paths = release_files(source)
    destination = Path(destination).resolve()
    if destination.is_relative_to(source.resolve()):
        raise ValueError('Archive destination must be outside skill source')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, 'careerpilot/' + path.relative_to(source).as_posix())
    return {'archive': str(destination), 'files': len(paths), 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist' / 'careerpilot.zip')
    args = parser.parse_args()
    print(json.dumps(package(args.output), indent=2))
