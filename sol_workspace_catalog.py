"""Read-only suggestions for choosing a compatible personal workspace.

The catalog is not an identity service or a migration tool. It reads recognized
workspace snapshots for the selected corpus and source, without looking at actor
profiles, loading book text, creating a directory, or opening a writable database.
Names that cannot safely be offered by the normal workspace-name prompt are not
suggested. An unavailable or incompatible candidate is simply omitted.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sqlite3

from sol_workspace import Workspace, WorkspaceError, _hash, _string, _timestamp, _uuid


_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_ACTIVITY_TABLES = (
    "state_history", "bookmarks", "annotations", "comparisons", "reviews", "relations",
)


def _directory(directory: str | Path | None) -> Path:
    if directory is None:
        configured = os.environ.get("XDG_DATA_HOME")
        if configured and not Path(configured).is_absolute():
            raise WorkspaceError("XDG_DATA_HOME must be an absolute directory")
        root = Path(configured) if configured else Path.home() / ".local" / "share"
        directory = root / "sol" / "workspaces"
    return Path(directory).expanduser().absolute()


def _moment(value: str) -> datetime:
    _timestamp(value, "catalog activity time")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _summary(workspace: Workspace, name: str) -> tuple[datetime, dict]:
    """Join the store's read transaction so identity, state, and dates agree."""
    with workspace._snapshot():
        # Opening validated an earlier snapshot. Revalidate inside this same
        # transaction so a concurrent save cannot separate our compatibility
        # decision from the metadata actually offered to the reader.
        workspace._check_schema_contents()
        state = workspace.get_state()
        activity = [(_moment(workspace.created_at), None)]
        # The exact schema and persisted records were checked by the read-only
        # store. Read only timestamp/actor columns, never copied note bodies.
        connection = workspace._db()
        for table in _ACTIVITY_TABLES:
            columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
            fields = [field for field in ("created_at", "updated_at") if field in columns]
            for row in connection.execute(f"SELECT actor,{','.join(fields)} FROM {table}"):
                actor = _string(row["actor"], "catalog actor")
                for field in fields:
                    activity.append((_moment(row[field]), actor))
        # Version two adds an append-only note audit. Revisions and truthful
        # legacy-baseline upgrades have their own saved-activity timestamp.
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "annotation_history" in tables:
            for row in connection.execute("SELECT editor,recorded_at FROM annotation_history"):
                editor = row["editor"]
                if editor is not None:
                    editor = _string(editor, "catalog annotation editor")
                activity.append((_moment(row["recorded_at"]), editor))
        # Equal timestamps do not identify a meaningful last actor. Pick a
        # stable display label only; it never selects the next session's actor.
        latest, actor = max(activity, key=lambda entry: (entry[0], entry[1] or ""))
        return latest, {
            "name": name,
            "schema_version": workspace.schema_version,
            "last_activity": latest.isoformat().replace("+00:00", "Z"),
            "current_id": None if state is None else state["current_id"],
            "scope": None if state is None else state["scope"],
            "last_actor": actor,
        }


def discover_workspaces(corpus_id: str, source_sha256: str | None,
                        directory: str | Path | None = None, limit: int = 10) -> list[dict]:
    """Return recent compatible workspaces, ordered by saved UTC activity.

    Each result contains ``name``, ``schema_version``, ``last_activity``,
    ``current_id``, ``scope`` and ``last_actor``. The latter is a stored
    attribution label, not an authenticated account or a default actor. Empty
    workspaces use their creation date, with null passage, scope, and actor.

    The limit is 1–20. Symlinks, WAL workspaces, unrecognized versions or schema,
    damaged data and different corpus/source identities are never suggested.
    Their omission does not delete or repair them; entering a name explicitly
    still uses the normal store's diagnostics. Missing directories return []
    without creating anything. No PDF, Markdown, or actor registry is opened.
    """
    corpus_id = _uuid(corpus_id, "corpus identity")
    source_sha256 = _hash(source_sha256, "source fingerprint")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise WorkspaceError("workspace catalog limit must be an integer between 1 and 20")
    root = _directory(directory)
    try:
        if root.is_symlink() or not root.is_dir():
            return []
        candidates = list(root.iterdir())
    except OSError:
        return []
    found = []
    for path in candidates:
        if path.suffix != ".sqlite3" or _NAME.fullmatch(path.stem) is None:
            continue
        try:
            if path.is_symlink() or not path.is_file():
                continue
            # A read-only SQLite connection can create WAL shared-memory files.
            # The store rejects WAL headers too; omit existing sidecar-bearing
            # candidates before connecting instead of ignoring pending writes.
            if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm")):
                continue
            with Workspace(path, corpus_id, {"source_sha256": source_sha256},
                           read_only=True) as workspace:
                found.append(_summary(workspace, path.stem))
        except (WorkspaceError, sqlite3.Error, OSError, TypeError, ValueError):
            continue
    # Sorting twice keeps names ascending for simultaneous activity while all
    # dates are compared as actual UTC instants rather than textual formatting.
    found.sort(key=lambda item: item[1]["name"])
    found.sort(key=lambda item: item[0], reverse=True)
    return [summary for _, summary in found[:limit]]
