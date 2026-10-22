"""Private launch choices, separate from authored workspace records.

These preferences remember an explicit actor/workspace session. They never infer
authorship from profile creation dates or from a workspace's latest activity.
Reading preferences creates no files; only a validated interactive launch saves
them. Removing a workspace may forget its choices without deleting actor labels.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import sqlite3
from uuid import UUID

from sol.being.workspace.profiles import actor_name


APPLICATION_ID = 0x534F4C4C  # SOLL
VERSION = 1
SCHEMAS = {
    "current_actor": "CREATE TABLE current_actor (singleton INTEGER PRIMARY KEY CHECK (singleton=1), actor TEXT NOT NULL)",
    "selections": "CREATE TABLE selections (actor TEXT NOT NULL, corpus_id TEXT NOT NULL, source_sha256 TEXT NOT NULL, workspace TEXT NOT NULL, PRIMARY KEY(actor,corpus_id,source_sha256))",
}


def launch_path() -> Path:
    configured = os.environ.get("XDG_DATA_HOME")
    root = Path(configured) if configured else Path.home() / ".local" / "share"
    if not root.is_absolute():
        raise ValueError("XDG_DATA_HOME must be an absolute directory")
    return root / "sol" / "launch.sqlite3"


def _workspace(value: str | Path) -> str:
    path = Path(value)
    if not path.is_absolute() or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.sqlite3", path.name):
        raise ValueError("remembered workspace must be an absolute named .sqlite3 path")
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in str(path)):
        raise ValueError("remembered workspace path must not contain terminal controls")
    return str(path.absolute())


def _binding(corpus_id: str, source_sha256: str) -> None:
    if not isinstance(corpus_id, str) or str(UUID(corpus_id)) != corpus_id:
        raise ValueError("invalid corpus identity in launch preferences")
    if not isinstance(source_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("invalid source fingerprint in launch preferences")


def _verify(connection) -> dict:
    if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID or \
            connection.execute("PRAGMA user_version").fetchone()[0] != VERSION:
        raise ValueError("unrecognized launch preferences; they were not changed")
    objects = connection.execute("SELECT type,name,sql FROM sqlite_master").fetchall()
    actual = {row[1]: " ".join(row[2].split()) for row in objects if row[0] == "table" and row[2]}
    if actual != SCHEMAS or any(row[0] not in {"table", "index"} or
                               (row[0] == "index" and row[2] is not None) for row in objects):
        raise ValueError("damaged or unrecognized launch preferences schema")
    if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
        raise ValueError("launch preferences failed their integrity check")
    current = connection.execute("SELECT singleton,actor FROM current_actor").fetchall()
    if len(current) > 1 or (current and (current[0][0] != 1 or actor_name(current[0][1]) != current[0][1])):
        raise ValueError("invalid last actor in launch preferences")
    choices = []
    for actor, corpus_id, source_sha256, workspace in connection.execute(
            "SELECT actor,corpus_id,source_sha256,workspace FROM selections ORDER BY actor,corpus_id,source_sha256"):
        if actor_name(actor) != actor:
            raise ValueError("invalid actor in launch preferences")
        _binding(corpus_id, source_sha256)
        if not isinstance(workspace, str) or _workspace(workspace) != workspace:
            raise ValueError("invalid workspace in launch preferences")
        choices.append({"actor": actor, "corpus_id": corpus_id, "source_sha256": source_sha256,
                        "workspace": workspace})
    return {"last_actor": current[0][1] if current else None, "selections": choices}


def _connect(path: Path, *, write: bool = False, create: bool = False):
    if path.is_symlink():
        raise ValueError("launch preferences must not be a symbolic link")
    if not write:
        # SQLite may create a shared-memory sidecar even for mode=ro when a
        # database uses WAL. A preference lookup must remain genuinely inert.
        with path.open("rb") as handle:
            header = handle.read(20)
        if header[:16] == b"SQLite format 3\x00" and 2 in header[18:20]:
            raise ValueError("read-only launch lookup does not open WAL preferences")
    new = False
    if create:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except FileExistsError:
            pass
        else:
            new = True
            try:
                if hasattr(os, "fchmod"):
                    os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
    connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if write else "?mode=ro"),
                                 uri=True, isolation_level=None, timeout=5)
    try:
        connection.execute("PRAGMA trusted_schema = OFF")
        connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        if new:
            for statement in SCHEMAS.values():
                connection.execute(statement)
            connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version = {VERSION}")
        state = _verify(connection)
        return connection, state
    except Exception:
        connection.close()
        raise


def read_launch_preferences(path: Path | None = None) -> dict:
    """Inspect remembered explicit choices without creating any personal state."""
    path = (path or launch_path()).expanduser().absolute()
    if not path.exists() and not path.is_symlink():
        return {"last_actor": None, "selections": []}
    try:
        connection, state = _connect(path)
        connection.close()
        return state
    except (sqlite3.Error, OSError, TypeError) as error:
        raise ValueError(f"cannot read launch preferences {path}: {error}") from error


def remember_launch(actor: str, workspace: Path, corpus_id: str, source_sha256: str,
                    path: Path | None = None) -> None:
    """Save the choice after profile and workspace validation, not onboarding."""
    actor = actor_name(actor)
    _binding(corpus_id, source_sha256)
    workspace = _workspace(workspace)
    path = (path or launch_path()).expanduser().absolute()
    try:
        connection, _ = _connect(path, write=True, create=True)
        try:
            connection.execute("INSERT OR REPLACE INTO current_actor VALUES (1,?)", (actor,))
            connection.execute("INSERT OR REPLACE INTO selections VALUES (?,?,?,?)",
                               (actor, corpus_id, source_sha256, workspace))
            connection.commit()
        finally:
            connection.close()
    except (sqlite3.Error, OSError, TypeError) as error:
        raise ValueError(f"cannot save launch preferences {path}: {error}") from error


def forget_workspace(workspace: Path, path: Path | None = None) -> None:
    """Forget a removed workspace for every actor without modifying profiles."""
    workspace = _workspace(workspace)
    path = (path or launch_path()).expanduser().absolute()
    if not path.exists() and not path.is_symlink():
        return
    try:
        connection, _ = _connect(path, write=True)
        try:
            connection.execute("DELETE FROM selections WHERE workspace=?", (workspace,))
            connection.commit()
        finally:
            connection.close()
    except (sqlite3.Error, OSError, TypeError) as error:
        raise ValueError(f"cannot update launch preferences {path}: {error}") from error
