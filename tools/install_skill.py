"""Install the canonical skill into a supported host without overwriting files."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / 'skills' / 'careerpilot'

def release_files():
    names = (Path(__file__).with_name('skill-files.txt')).read_text(encoding='utf-8').splitlines()
    result = [SOURCE / name for name in names]
    if any(not path.is_file() or path.resolve() != path.absolute() or not path.is_relative_to(SOURCE) for path in result):
        raise ValueError('Invalid release manifest')
    return result

def files(root):
    return sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')

def manifest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in (release_files() if root == SOURCE else files(root))}

def install(destination, dry_run=False):
    destination = destination.expanduser().resolve()
    if destination == SOURCE.resolve() or destination.is_relative_to(SOURCE.resolve()):
        raise ValueError('Choose a destination outside the canonical source')
    if destination.exists():
        if destination.is_dir() and manifest(destination) == manifest(SOURCE):
            return {'installed': str(destination), 'unchanged': True}
        raise ValueError('Destination already exists with different content. Back it up and select a new destination; no files were overwritten.')
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.mkdir()
        for source in release_files():
            target = destination / source.relative_to(SOURCE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    return {'destination': str(destination), 'dry_run': dry_run, 'files': len(release_files())}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=['codex', 'claude', 'generic'])
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--project', type=Path)
    scope.add_argument('--user', action='store_true')
    scope.add_argument('--destination', type=Path, help='Exact skill directory for another compatible host')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not args.destination and not args.host:
        parser.error('--host is required with --project or --user')
    if args.host == 'generic' and not args.destination:
        parser.error('Use --destination for the generic host')
    if args.destination and args.host not in (None, 'generic'):
        parser.error('--destination cannot be combined with --host')
    root = Path.home() if args.user else args.project
    destination = args.destination or root / ('.agents' if args.host == 'codex' else '.claude') / 'skills' / 'careerpilot'
    try:
        print(json.dumps(install(destination, args.dry_run), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({'error': str(exc)}))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
