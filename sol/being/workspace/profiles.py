"""Local actor labels for shell onboarding, not authenticated system accounts.

The registry is separate from the frozen workspace-v1 schema. Existing authored
records retain their original name; creating a profile never rewrites them.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import unicodedata
from uuid import UUID, uuid4

from sol.being.workspace.time import parse_utc_timestamp


APPLICATION_ID = 0x534F4C41  # SOLA
VERSION = 1
SCHEMA = "CREATE TABLE actors (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL)"


def profile_path() -> Path:
    configured = os.environ.get('XDG_DATA_HOME')
    root = Path(configured) if configured else Path.home() / '.local' / 'share'
    if not root.is_absolute():
        raise ValueError('XDG_DATA_HOME must be an absolute directory')
    return root / 'sol' / 'profiles.sqlite3'


def actor_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 128:
        raise ValueError('actor name must contain 1–128 characters')
    if any(unicodedata.category(c) in {'Cc', 'Cs'} or unicodedata.bidirectional(c) in {
        'LRE', 'RLE', 'LRO', 'RLO', 'PDF', 'LRI', 'RLI', 'FSI', 'PDI'} for c in value):
        raise ValueError('actor name must not contain terminal controls or direction overrides')
    return value.strip()


def _verify(connection):
    if connection.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID or \
            connection.execute('PRAGMA user_version').fetchone()[0] != VERSION:
        raise ValueError('unrecognized actor registry; it was not changed')
    objects = connection.execute('SELECT type,name,sql FROM sqlite_master').fetchall()
    actual = {row[1]: ' '.join(row[2].split()) for row in objects if row[0] == 'table' and row[2]}
    if actual != {'actors': SCHEMA} or any(row[0] not in {'table', 'index'} or
                                         (row[0] == 'index' and row[2] is not None) for row in objects):
        raise ValueError('damaged or unrecognized actor registry schema')
    if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
        raise ValueError('actor registry failed its integrity check')
    rows = connection.execute('SELECT id,name,created_at FROM actors ORDER BY created_at,name').fetchall()
    for identifier, name, timestamp in rows:
        if not isinstance(identifier, str) or not isinstance(timestamp, str):
            raise ValueError('invalid actor profile metadata')
        if str(UUID(identifier)) != identifier or actor_name(name) != name:
            raise ValueError('invalid actor profile metadata')
        try:
            parse_utc_timestamp(timestamp)
        except ValueError as error:
            raise ValueError('invalid actor profile timestamp') from error
    return [{'id': identifier, 'name': name, 'created_at': timestamp} for identifier, name, timestamp in rows]


def list_actors(path: Path | None = None) -> list[dict]:
    """Read known labels without creating a registry or its directory."""
    path = (path or profile_path()).expanduser().absolute()
    if path.is_symlink():
        raise ValueError('actor registry must not be a symbolic link')
    if not path.exists():
        return []
    try:
        connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, isolation_level=None)
        try:
            connection.execute('PRAGMA trusted_schema = OFF')
            connection.execute('BEGIN')
            return _verify(connection)
        finally:
            connection.close()
    except (sqlite3.Error, OSError, TypeError) as error:
        raise ValueError(f'cannot read actor registry {path}: {error}') from error


def register_actor(name: str, path: Path | None = None) -> dict:
    name = actor_name(name)
    path = (path or profile_path()).expanduser().absolute()
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise ValueError('actor registry must not be a symbolic link')
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except FileExistsError:
            new = False
        else:
            new = True
            try:
                if hasattr(os, 'fchmod'):
                    os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
        connection = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, isolation_level=None, timeout=5)
        try:
            connection.execute('PRAGMA trusted_schema = OFF')
            connection.execute('BEGIN IMMEDIATE')
            if new:
                connection.execute(SCHEMA)
                connection.execute(f'PRAGMA application_id = {APPLICATION_ID}')
                connection.execute(f'PRAGMA user_version = {VERSION}')
            _verify(connection)
            row = connection.execute('SELECT id,name,created_at FROM actors WHERE name=?', (name,)).fetchone()
            if row is None:
                row = (str(uuid4()), name, datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
                connection.execute('INSERT INTO actors VALUES (?,?,?)', row)
            connection.commit()
            return {'id': row[0], 'name': row[1], 'created_at': row[2]}
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    except (sqlite3.Error, OSError, TypeError) as error:
        raise ValueError(f'cannot register actor in {path}: {error}') from error
