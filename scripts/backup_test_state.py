"""Passphrase-encrypted test-bot backup; verification/restoration never unpickles data."""
import argparse
import base64
from datetime import datetime, timezone
from getpass import getpass
import json
import os
from pathlib import Path
import sqlite3
import sys

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

ROOT = Path(__file__).resolve().parents[1]
MAGIC = b'HUMOBACKUP1\n'
ALLOWED = {'.env.test', 'bot_persistence.pkl', 'bot_persistence.key', 'application_numbers.sqlite3', 'bot_routes.json'}


def cipher(password, salt):
    key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def validate(files):
    if not isinstance(files, dict) or not set(files) <= ALLOWED:
        raise ValueError('Unknown backup contents')
    if not {'.env.test', 'bot_persistence.pkl', 'bot_persistence.key', 'application_numbers.sqlite3'} <= set(files):
        raise ValueError('Incomplete backup')
    state = files['bot_persistence.pkl']
    if not state.startswith(b'HUMOENC1\n'):
        raise ValueError('Encrypted state required')
    Fernet(files['bot_persistence.key'].strip()).decrypt(state[len(b'HUMOENC1\n'):])
    with sqlite3.connect(':memory:') as db:
        db.deserialize(files['application_numbers.sqlite3'])
        if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('Invalid counter database')
        db.execute('SELECT MAX(id) FROM sequence').fetchone()


def collect(root):
    state = root / '.test-bot-state'
    files = {}
    for name in ALLOWED - {'application_numbers.sqlite3'}:
        path = root / name if name == '.env.test' else state / name
        if path.is_symlink():
            raise ValueError('Symlinks are not permitted')
        if path.is_file():
            files[name] = path.read_bytes()
    path = state / 'application_numbers.sqlite3'
    if path.is_symlink() or not path.is_file():
        raise ValueError('Counter database missing')
    with sqlite3.connect(path) as source, sqlite3.connect(':memory:') as snapshot:
        source.backup(snapshot)
        files[path.name] = snapshot.serialize()
    validate(files)
    return files


def pack(files, password):
    validate(files)
    salt = os.urandom(16)
    content = json.dumps({key: base64.b64encode(value).decode() for key, value in files.items()}).encode()
    return MAGIC + salt + cipher(password, salt).encrypt(content)


def unpack(raw, password):
    if not raw.startswith(MAGIC) or len(raw) > 100_000_000:
        raise ValueError('Invalid backup')
    content = cipher(password, raw[len(MAGIC):len(MAGIC)+16]).decrypt(raw[len(MAGIC)+16:])
    files = {key: base64.b64decode(value, validate=True) for key, value in json.loads(content).items()}
    validate(files)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--restore-to', type=Path, help='New empty directory only; never replaces live files')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.restore_to and not args.verify:
        raise ValueError('--restore-to requires --verify BACKUP')
    password = getpass('Backup paroli (chatga yubormang): ')
    if args.verify:
        if args.verify.is_symlink():
            raise ValueError('Symlink backup rejected')
        files = unpack(args.verify.read_bytes(), password)
        if args.restore_to:
            target = args.restore_to
            if target.exists():
                raise ValueError('Restore destination must not exist')
            target.mkdir(parents=True, mode=0o700)
            state = target / '.test-bot-state'
            state.mkdir(mode=0o700)
            for name, data in files.items():
                path = target / name if name == '.env.test' else state / name
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
        print('Backup authenticated; state/key and counter verified. Live files unchanged.')
        return
    if len(password) < 16 or password != getpass('Backup parolini takrorlang: '):
        raise ValueError('Matching passphrase of at least 16 characters required')
    files = collect(ROOT)
    encrypted = pack(files, password)
    unpack(encrypted, password)
    directory = Path.home() / 'humobot-backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink():
        raise ValueError('Symlink backup directory rejected')
    path = args.output or directory / ('humobot-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '.enc')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encrypted)
        stream.flush()
        os.fsync(stream.fileno())
    print('Encrypted backup saved: ' + str(path))
    print('Keep an off-server copy and its passphrase separately; never share them in chat.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Backup operation failed: ' + type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
