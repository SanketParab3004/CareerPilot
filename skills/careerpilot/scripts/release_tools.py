"""Local setup, diagnostics and workspace lifecycle operations."""
import getpass
import io
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath
from uuid import uuid4

STEPS = ('profile', 'targets', 'browser', 'gmail', 'alerts')
ROOT_FILES = {'toolkit.sqlite3', 'private-settings.sqlite3', '.gitignore'}
FOLDERS = {'artifacts', 'imports', 'backups', 'exports', 'reports'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def setup(state, data):
    step, status = data.get('step'), data.get('status')
    need(step in STEPS and status in ('done', 'skipped', 'pending'), 'Choose a setup step and status.')
    state.setdefault('setup', {})[step] = status
    return {'setup': state['setup']}


def preferences(state, data):
    result = dict(state.get('international', {}))
    for key in ('country', 'currency', 'language', 'date_format'):
        if key in data:
            result[key] = data[key]
    for key, pattern in [('country', r'[A-Z]{2}'), ('currency', r'[A-Z]{3}'),
                         ('language', r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8})*')]:
        if key in result:
            need(isinstance(result[key], str) and re.fullmatch(pattern, result[key]), 'Invalid ' + key)
    need(result.get('date_format', 'locale') in ('locale', 'iso', 'dmy', 'mdy'), 'Invalid date format')
    if 'portals' in data:
        value = data['portals']
        need(isinstance(value, list) and value and all(x in ('LinkedIn', 'Indeed') for x in value)
             and len(set(value)) == len(value), 'Choose LinkedIn, Indeed, or both.')
        result['portals'] = value
    if 'authorization_questions' in data:
        value = data['authorization_questions']
        need(isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value),
             'Provide a list of local work-authorization questions.')
        result['authorization_questions'] = value
    state['international'] = result
    return {'international': result}


def doctor(ws, browser='unknown', gmail='unknown'):
    def check(status, fix=None):
        return {'status': status, 'fix': fix}
    exists = ws.db_path.is_file()
    checks = {
        'python': check('ready' if sys.version_info >= (3, 10) else 'blocked', 'Use Python 3.10 or later.'),
        'workspace': check('missing', 'Create or choose a private workspace with init.'),
        'permissions': check('unknown', 'Choose a private folder writable by your account.'),
        'browser_tool': check(browser, 'Open the host tools menu and verify that a browser tool is enabled.'),
        'gmail': check(gmail, 'Connect Gmail in the host and verify read access to the intended account.'),
        'telegram': check('unconfigured', 'Open Accounts & alerts to configure Telegram and test delivery.'),
    }
    if exists:
        try:
            with closing(sqlite3.connect(ws.db_path.as_uri()+'?mode=ro', uri=True)) as db:
                state = json.loads(db.execute('SELECT value FROM state WHERE id=1').fetchone()[0])
            version = state.get('schema_version')
            checks['workspace'] = check('ready' if version == 6 else 'check version',
                                        'Use migrate for a supported older workspace.')
            checks['permissions'] = check('writable (OS access check)' if os.access(ws.root, os.W_OK)
                                          and os.access(ws.db_path, os.W_OK) else 'blocked',
                                          'Check workspace folder and database permissions.')
            from private_settings import Settings
            telegram = Settings(ws.root).read().get('telegram', {})
            if telegram.get('token') and telegram.get('chat_id'):
                checks['telegram'] = check('configured; delivery untested', 'Use the dashboard test button.')
        except (ValueError, OSError, sqlite3.Error, TypeError):
            checks['workspace'] = check('needs review', 'Check database and local credential-store access.')
    checks['optional_packages'] = {name: bool(importlib.util.find_spec(name))
                                   for name in ('playwright', 'keyring', 'cryptography', 'pypdf')}
    checks['optional_package_help'] = 'Install only the dependency needed for your feature. See the release guide.'
    return {'workspace_path': str(ws.root), 'checks': checks}


def demo(ws):
    need(not ws.root.exists(), 'Choose a new directory for the synthetic demo.')
    ws.initialize()
    ws.mutate({'op': 'profile-save', 'profile': {'name': 'Demo Candidate', 'target_roles': ['Data Analyst']}})
    ws.mutate({'op': 'job-add', 'title': 'Data Analyst (demo)', 'company': 'Synthetic Employer',
               'description': 'Practice reviewing a saved job.', 'source': 'Synthetic demo',
               'url': 'https://example.invalid/demo'})
    return {'workspace': str(ws.root), 'synthetic': True}


def selected(root):
    for entry in sorted(root.iterdir()):
        if entry.name not in ROOT_FILES | FOLDERS:
            continue
        yield entry
        if entry.is_dir() and not entry.is_symlink():
            yield from sorted(entry.rglob('*'))


def valid_entry(path):
    return not path.is_symlink() and not getattr(path.stat(), 'st_file_attributes', 0) & 1024


def cipher():
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    except ImportError as exc:
        raise ValueError('Install cryptography to use password-encrypted archives.') from exc
    import base64
    password = getpass.getpass('Archive passphrase: ')
    need(len(password) >= 12, 'Use at least 12 characters for the archive passphrase.')

    def key(salt):
        return Fernet(base64.urlsafe_b64encode(
            Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(password.encode())))
    return key


def backup(ws, destination, encrypted=False):
    destination = destination.resolve()
    need(ws.db_path.is_file(), 'Choose an initialized workspace.')
    need(not destination.is_relative_to(ws.root), 'Save the archive outside the workspace.')
    need(not any(ws.root.glob('*.sqlite3-*')), 'Stop workspace tools and close database connections before backup.')
    key = cipher() if encrypted else None
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as output:
        for path in selected(ws.root):
            need(valid_entry(path), 'Remove linked files or folders before backup.')
            if path.is_file():
                output.write(path, path.relative_to(ws.root).as_posix())
    data = buffer.getvalue()
    if key:
        salt = os.urandom(16)
        data = b'CPENC1' + salt + key(salt).encrypt(data)
    with destination.open('xb') as target:
        target.write(data)
    return {'archive': str(destination), 'encrypted': encrypted}


def restore(ws, archive):
    need(not ws.root.exists(), 'Restore into a new workspace directory.')
    data = archive.read_bytes()
    if data.startswith(b'CPENC1'):
        decrypt = cipher()
        from cryptography.fernet import InvalidToken
        try:
            data = decrypt()(data[6:22]).decrypt(data[22:])
        except InvalidToken as exc:
            raise ValueError('Incorrect passphrase or damaged archive.') from exc
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as source:
            seen = set()
            for item in source.infolist():
                name = item.filename
                path = PurePosixPath(name)
                parts = path.parts
                need(parts and not path.is_absolute() and '..' not in parts and '\\' not in name
                     and not any(part.endswith(('.', ' ')) or
                                 re.fullmatch(r'(?i)(con|prn|aux|nul|com[0-9¹²³]|lpt[0-9¹²³])(?:\..*)?', part)
                                 for part in parts)
                     and not any(char in name for char in ':*?<>|"') and path.as_posix() == name and not item.is_dir()
                     and name.casefold() not in seen and not stat.S_ISLNK(item.external_attr >> 16)
                     and (name in ROOT_FILES or len(parts) > 1 and parts[0] in FOLDERS),
                     'Archive contains an unsafe or unexpected path.')
                seen.add(name.casefold())
            need('toolkit.sqlite3' in source.namelist(), 'Archive has no CareerPilot database.')
            ws.root.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=ws.root.parent) as folder:
                stage = Path(folder) / 'workspace'
                source.extractall(stage)
                with closing(sqlite3.connect((stage/'toolkit.sqlite3').as_uri()+'?mode=ro', uri=True)) as db:
                    state = json.loads(db.execute('SELECT value FROM state WHERE id=1').fetchone()[0])
                    need(state.get('schema_version') in range(1, 7), 'Unsupported workspace database.')
                need(not ws.root.exists(), 'Restore destination now exists.')
                stage.rename(ws.root)
    except zipfile.BadZipFile as exc:
        raise ValueError('Invalid CareerPilot archive.') from exc
    return {'restored': str(ws.root), 'credentials': 'Reconnect if the original OS credential store is unavailable.'}


def delete(ws, confirmation):
    need(confirmation == str(ws.root), 'Confirm deletion with the exact resolved workspace path.')
    need(ws.db_path.is_file() and not (ws.root / '.git').exists(), 'Choose a dedicated CareerPilot workspace.')
    need(not any(ws.root.glob('*.sqlite3-*')), 'Close all workspace tools before deleting.')
    need(all(p.name in ROOT_FILES | FOLDERS for p in ws.root.iterdir()),
         'Move unrelated files out of the workspace before deleting.')
    need(all(valid_entry(p) for p in selected(ws.root)), 'Remove linked files before deleting.')
    if os.name != 'nt' and (ws.root / 'private-settings.sqlite3').exists():
        from private_settings import remove_keychain_key
        remove_keychain_key(ws.root)
    shutil.rmtree(ws.root)
    return {'deleted': str(ws.root), 'note': 'Remove separate backups and snapshots yourself. File deletion does not sanitize storage.'}


def metrics(ws, destination, consent):
    need(consent, 'Use --consent to export aggregate counts.')
    state = ws.read()
    counts = {}
    for status in ('Submitted', 'Interview', 'Offer', 'Rejected'):
        n = sum(j.get('status') == status for j in state['jobs'].values())
        if n >= 5:
            counts[status] = n
    with destination.open('x', encoding='utf-8') as output:
        json.dump({'format': 1, 'status_counts': counts, 'minimum_cell_size': 5}, output)
    return {'export': str(destination)}
