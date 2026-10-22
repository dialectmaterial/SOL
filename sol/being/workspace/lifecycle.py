"""List and recoverably remove exact, recognized personal workspaces.

This is a local-data operation, not a corpus or actor-registry operation. A
removed database is retained unchanged inside a private ``.trash`` directory.
Restoration is an explicit move back to its original name while SOL is closed.
No directory tree, glob, schema migration, or database repair is involved.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import stat
from uuid import uuid4

from sol.being.workspace.catalog import _directory, _NAME
from sol.being.workspace.store import (
    APPLICATION_ID, Workspace, WorkspaceError, _decode, _source_fingerprint, _uuid,
    fcntl,
)


_SIDECARS = ("-wal", "-shm", "-journal")


def _root(directory: str | Path | None, *, missing: bool = False) -> Path:
    root = _directory(directory)
    # Reject symlinks in ancestors too: an exact workspace name must not be a
    # route into a different authority selected by a mutable directory link.
    if ".." in root.parts or root.resolve(strict=False) != root:
        raise WorkspaceError("workspace directory must not contain symbolic links or '..'")
    if not root.exists():
        if missing:
            return root
        raise WorkspaceError("workspace directory does not exist")
    info = root.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise WorkspaceError("workspace directory is not a directory")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise WorkspaceError("workspace directory must belong to the current user")
    return root


def _file(path: Path) -> os.stat_result:
    try:
        info = path.lstat()
    except OSError as error:
        raise WorkspaceError(f"workspace does not exist: {path.stem}") from error
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise WorkspaceError("workspace must be a regular file, not a symbolic or hard link")
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise WorkspaceError("workspace must belong to the current user")
    if any(os.path.lexists(str(path) + suffix) for suffix in _SIDECARS):
        raise WorkspaceError("workspace has SQLite sidecars; close it cleanly before removal")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise WorkspaceError("workspace changed during inspection; nothing was removed")
        header = os.read(descriptor, 20)
    finally:
        os.close(descriptor)
    if header[:16] != b"SQLite format 3\x00":
        raise WorkspaceError("not a recognized SQLite workspace")
    if 2 in header[18:20]:
        raise WorkspaceError("WAL workspace must be closed and checkpointed before removal")
    return info


def _same_file(path: Path, expected: os.stat_result) -> None:
    actual = _file(path)
    if (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino):
        raise WorkspaceError("workspace changed during removal; nothing was removed")


def _identity(path: Path) -> tuple[str, dict]:
    """Read only enough identity to ask the existing store for full validation."""
    _file(path)
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                                    isolation_level=None, timeout=0)) as connection:
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("BEGIN")
            if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
                raise WorkspaceError("not a recognized SOL workspace; it was not removed")
            rows = connection.execute("SELECT corpus_id,provenance FROM workspace_metadata").fetchall()
            if len(rows) != 1:
                raise WorkspaceError("workspace identity metadata is damaged")
            corpus_id = _uuid(rows[0][0], "workspace corpus identity")
            provenance = _decode(rows[0][1])
            if type(provenance) is not dict:
                raise WorkspaceError("workspace provenance is not a JSON object")
            _source_fingerprint(provenance)
            return corpus_id, provenance
    except (sqlite3.Error, OSError, TypeError) as error:
        raise WorkspaceError(f"cannot inspect workspace {path.stem}: {error}") from error


def _summary(workspace: Workspace) -> dict:
    return {
        "name": workspace.path.stem,
        "path": str(workspace.path),
        "corpus_id": workspace.corpus_id,
        "source_sha256": workspace.source_sha256,
        "schema_version": workspace.schema_version,
        "created_at": workspace.created_at,
    }


def list_workspaces(directory: str | Path | None = None) -> list[dict]:
    """List recognized named databases, without creating or changing any files.

    All corpus/source identities are shown. Foreign, damaged, linked, unsafe or
    sidecar-bearing files are omitted, not repaired or removed. Explicit removal
    of such a name gives an error instead of silently omitting it.
    """
    try:
        root = _root(directory, missing=True)
        if not root.exists():
            return []
        paths = sorted(root.iterdir())
    except OSError as error:
        raise WorkspaceError(f"cannot list workspace directory: {error}") from error
    found = []
    for path in paths:
        if path.suffix != ".sqlite3" or _NAME.fullmatch(path.stem) is None:
            continue
        try:
            corpus_id, provenance = _identity(path)
            with Workspace(path, corpus_id, provenance, read_only=True) as workspace:
                found.append(_summary(workspace))
        except (WorkspaceError, sqlite3.Error, OSError, ValueError, TypeError):
            continue
    return found


def _refuse_open_inode(expected: os.stat_result, *, ignore_self: bool = False) -> None:
    """Additional Linux defense for pre-lease SOL and raw idle SQLite handles.

    The lifetime flock is the portable authority for current SOL sessions. On
    Linux, inspect accessible same-user processes too. Inaccessible unrelated
    processes are not treated as proof of activity or grounds to block deletion.
    SQLite's exclusive transaction still rejects active external transactions.
    """
    proc = Path("/proc")
    if not proc.is_dir():
        return
    for process in proc.iterdir():
        if not process.name.isdigit() or (ignore_self and int(process.name) == os.getpid()):
            continue
        try:
            if hasattr(os, "getuid") and process.stat().st_uid != os.getuid():
                continue
            descriptors = list((process / "fd").iterdir())
        except OSError:
            continue
        for descriptor in descriptors:
            try:
                opened = descriptor.stat()
            except OSError:
                continue
            if (opened.st_dev, opened.st_ino) == (expected.st_dev, expected.st_ino):
                raise WorkspaceError("workspace is open in a running process; close it before removal")


def _trash(root: Path) -> Path:
    directory = root / ".trash"
    try:
        directory.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or
            (hasattr(os, "getuid") and info.st_uid != os.getuid())):
        raise WorkspaceError("workspace .trash must be a private, current-user directory")
    return directory


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) |
                         getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def delete_workspace(name: str, directory: str | Path | None = None) -> dict:
    """Recoverably remove one exact named workspace, refusing open/unsafe data.

    Returns the listed identity fields plus ``recovery_path``. The original
    database bytes are retained under a unique private subdirectory of .trash;
    nothing is overwritten. No actor profile or recent-session preference is
    changed here. Callers should clear a preference that names this workspace.

    Removal requires POSIX inode leases, used by current SOL sessions. Arbitrary
    external software that ignores both leases and SQLite locking cannot be
    made safe by this API; close other database tools before removal.
    """
    if not isinstance(name, str) or _NAME.fullmatch(name) is None:
        raise WorkspaceError("workspace name must contain 1–64 letters, numbers, underscores or hyphens")
    if fcntl is None:
        raise WorkspaceError("safe workspace removal needs POSIX file locking on this host")
    try:
        root = _root(directory)
        path = root / (name + ".sqlite3")
        original = _file(path)
        _refuse_open_inode(original)
        corpus_id, provenance = _identity(path)
    except OSError as error:
        raise WorkspaceError(f"cannot prepare workspace removal: {error}") from error
    try:
        with Workspace(path, corpus_id, provenance, read_only=True) as workspace:
            descriptor = workspace._lease_descriptor
            if descriptor is None:
                raise WorkspaceError("workspace has no safe lifetime lease; it was not removed")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise WorkspaceError("workspace is open in SOL; close it before removal") from error
            # mode=ro accepts BEGIN EXCLUSIVE but cannot obtain SQLite's write
            # reservation: it does not actually exclude another writer. Keep
            # the lifetime inode lease, replace our inspection connection with
            # an existing-file-only rw connection, and perform NO SQL writes.
            # Workspace.read_only stays true, prohibiting public write methods.
            workspace._db().close()
            workspace._connection = None
            connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True,
                                         isolation_level=None, timeout=0)
            connection.row_factory = sqlite3.Row
            workspace._connection = connection
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("BEGIN EXCLUSIVE")
            try:
                workspace._check_schema_contents()
                _same_file(path, original)
                opened = os.fstat(descriptor)
                if (opened.st_dev, opened.st_ino) != (original.st_dev, original.st_ino):
                    raise WorkspaceError("workspace changed during removal; nothing was removed")
                _refuse_open_inode(original, ignore_self=True)
                result = _summary(workspace)
                trash = _trash(root)
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                destination = trash / f"{name}-{timestamp}-{uuid4().hex}"
                destination.mkdir(mode=0o700)  # Exclusive: never reuse an archive.
                recovery = destination / path.name
                try:
                    # link() refuses an existing destination. Both names are on
                    # the same filesystem; a crash between link and unlink
                    # leaves a recoverable duplicate rather than losing data.
                    os.link(path, recovery, follow_symlinks=False)
                    # Make the recovery name and its parent entries durable
                    # before removing the original name. An interrupted move
                    # may leave duplicates, but must not lose the database.
                    _sync_directory(destination)
                    _sync_directory(trash)
                    _sync_directory(root)
                    current = path.lstat()
                    if (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
                        raise WorkspaceError("workspace changed before removal; recovery copy retained")
                    path.unlink()
                except Exception as error:
                    if recovery.exists():
                        raise WorkspaceError(
                            f"workspace removal stopped; recovery retained at {recovery}: {error}"
                        ) from error
                    destination.rmdir()
                    raise
                result["recovery_path"] = str(recovery)
                return result
            finally:
                connection.rollback()
    except (sqlite3.Error, OSError) as error:
        # Closing/rolling back can fail after the file has already moved. Do
        # not falsely promise that the original name still exists in that case.
        raise WorkspaceError(f"cannot complete workspace removal: {error}") from error
