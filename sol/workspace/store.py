"""Personal research data, kept separate from SOL's canonical corpus.

Each database belongs to exactly one corpus identity. Passage identifiers are
opaque UUID references, never filenames, inferred matches, or copied book text.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from typing import Any, Iterator
import unicodedata
from uuid import UUID, uuid4

try:
    import fcntl
except ImportError:  # Normal reading remains available on non-POSIX hosts.
    fcntl = None


SCHEMA_VERSION = 3
APPLICATION_ID = 0x534F4C57  # SOLW
REVIEW_OUTCOMES = ("inspected", "correction_needed", "verified")


class WorkspaceError(ValueError):
    """An invalid, incompatible, unavailable, or damaged workspace."""


class WorkspaceConflict(WorkspaceError):
    """Another session saved the reading state before this session did."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _string(value: Any, label: str, *, empty: bool = False, multiline: bool = False) -> str:
    if not isinstance(value, str) or "\x00" in value:
        raise WorkspaceError(f"{label} must be a string without null characters")
    if not empty and not value.strip():
        raise WorkspaceError(f"{label} must not be empty")
    for character in value:
        if unicodedata.category(character) == "Cs" or (unicodedata.category(character) == "Cc"
                and not (multiline and character in "\n\t")) or (
                unicodedata.bidirectional(character) in {
                    "LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI"}):
            raise WorkspaceError(f"{label} contains unsafe control characters")
    return value


def _uuid(value: Any, label: str = "target identifier") -> str:
    _string(value, label)
    try:
        identifier = UUID(value)
    except ValueError as error:
        raise WorkspaceError(f"{label} must be a UUID") from error
    if str(identifier) != value.lower():
        raise WorkspaceError(f"{label} must be a complete, hyphenated UUID")
    return str(identifier)


def _hash(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{64}", value) is None:
        raise WorkspaceError(f"{label} must be a SHA-256 hexadecimal digest or null")
    return value.lower()


def _source_fingerprint(provenance: dict) -> str | None:
    direct = _hash(provenance.get("source_sha256"), "source fingerprint")
    source = provenance.get("source")
    nested = _hash(source.get("sha256"), "source fingerprint") if type(source) is dict else None
    if direct is not None and nested is not None and direct != nested:
        raise WorkspaceError("provenance contains conflicting source fingerprints")
    return direct if direct is not None else nested


def _timestamp(value: Any, label: str) -> None:
    try:
        parsed = datetime.fromisoformat(_string(value, label).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError("timestamp is not UTC")
    except (TypeError, ValueError) as error:
        raise WorkspaceError(f"{label} is not a valid UTC timestamp") from error


def _json_value(value: Any, depth: int = 0) -> None:
    if depth > 100:
        raise WorkspaceError("JSON metadata is nested too deeply")
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise WorkspaceError("JSON strings must contain valid Unicode") from error
        return
    if value is None or type(value) in {bool, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise WorkspaceError("JSON metadata cannot contain nonfinite numbers")
        return
    if type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if not isinstance(key, str):
                raise WorkspaceError("JSON metadata object keys must be strings")
            _json_value(key, depth + 1)
            _json_value(item, depth + 1)
        return
    raise WorkspaceError("metadata must contain only JSON values")


def _encode(value: Any) -> str:
    _json_value(value)
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError, UnicodeError) as error:
        raise WorkspaceError("metadata cannot be encoded as JSON") from error


def _decode(value: str) -> Any:
    def object_pairs(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise WorkspaceError("workspace contains duplicate JSON metadata keys")
            result[key] = item
        return result

    try:
        parsed = json.loads(value, object_pairs_hook=object_pairs,
                            parse_constant=lambda token: (_ for _ in ()).throw(
                                WorkspaceError(f"invalid JSON constant {token}")))
        _json_value(parsed)
        return parsed
    except (TypeError, ValueError, RecursionError) as error:
        raise WorkspaceError("workspace contains invalid JSON metadata") from error


_SCHEMA = (
    """CREATE TABLE workspace_metadata (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        schema_version INTEGER NOT NULL,
        corpus_id TEXT NOT NULL,
        provenance TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE reading_state (
        singleton INTEGER PRIMARY KEY REFERENCES workspace_metadata(singleton),
        cwd TEXT NOT NULL, scope TEXT NOT NULL, current_id TEXT, previous_cwd TEXT,
        revision INTEGER NOT NULL CHECK (revision > 0)
    )""",
    """CREATE TABLE state_history (
        revision INTEGER PRIMARY KEY CHECK (revision > 0),
        cwd TEXT NOT NULL, scope TEXT NOT NULL, current_id TEXT, previous_cwd TEXT,
        actor TEXT NOT NULL, created_at TEXT NOT NULL,
        workspace_id INTEGER NOT NULL DEFAULT 1 REFERENCES workspace_metadata(singleton)
    )""",
    """CREATE TABLE bookmarks (
        name TEXT PRIMARY KEY, target_id TEXT NOT NULL, actor TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        workspace_id INTEGER NOT NULL DEFAULT 1 REFERENCES workspace_metadata(singleton)
    )""",
    """CREATE TABLE annotations (
        id TEXT PRIMARY KEY, target_id TEXT NOT NULL, body TEXT NOT NULL,
        actor TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        content_sha256 TEXT,
        workspace_id INTEGER NOT NULL DEFAULT 1 REFERENCES workspace_metadata(singleton)
    )""",
    """CREATE TABLE comparisons (
        name TEXT PRIMARY KEY, question TEXT NOT NULL, actor TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        workspace_id INTEGER NOT NULL DEFAULT 1 REFERENCES workspace_metadata(singleton)
    )""",
    """CREATE TABLE comparison_items (
        comparison_name TEXT NOT NULL REFERENCES comparisons(name) ON DELETE CASCADE,
        position INTEGER NOT NULL CHECK (position >= 0), target_id TEXT NOT NULL,
        PRIMARY KEY (comparison_name, position)
    )""",
    """CREATE TABLE reviews (
        id TEXT PRIMARY KEY, target_id TEXT NOT NULL, actor TEXT NOT NULL,
        outcome TEXT NOT NULL, issue TEXT NOT NULL, created_at TEXT NOT NULL,
        content_sha256 TEXT, source_sha256 TEXT,
        workspace_id INTEGER NOT NULL DEFAULT 1 REFERENCES workspace_metadata(singleton)
    )""",
    """CREATE TABLE relations (
        id TEXT PRIMARY KEY, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
        kind TEXT NOT NULL, rationale TEXT NOT NULL, actor TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        workspace_id INTEGER NOT NULL DEFAULT 1 REFERENCES workspace_metadata(singleton)
    )""",
    """CREATE TRIGGER reviews_no_update BEFORE UPDATE ON reviews
        BEGIN SELECT RAISE(ABORT, 'review decisions are append-only'); END""",
    """CREATE TRIGGER reviews_no_delete BEFORE DELETE ON reviews
        BEGIN SELECT RAISE(ABORT, 'review decisions are append-only'); END""",
    """CREATE TRIGGER history_no_update BEFORE UPDATE ON state_history
        BEGIN SELECT RAISE(ABORT, 'reading history is append-only'); END""",
    """CREATE TRIGGER history_no_delete BEFORE DELETE ON state_history
        BEGIN SELECT RAISE(ABORT, 'reading history is append-only'); END""",
)

_COLUMNS = {
    "workspace_metadata": ("singleton", "schema_version", "corpus_id", "provenance", "created_at"),
    "reading_state": ("singleton", "cwd", "scope", "current_id", "previous_cwd", "revision"),
    "state_history": ("revision", "cwd", "scope", "current_id", "previous_cwd",
                      "actor", "created_at", "workspace_id"),
    "bookmarks": ("name", "target_id", "actor", "created_at", "updated_at", "workspace_id"),
    "annotations": ("id", "target_id", "body", "actor", "created_at", "updated_at",
                    "content_sha256", "workspace_id"),
    "comparisons": ("name", "question", "actor", "created_at", "updated_at", "workspace_id"),
    "comparison_items": ("comparison_name", "position", "target_id"),
    "reviews": ("id", "target_id", "actor", "outcome", "issue", "created_at",
                "content_sha256", "source_sha256", "workspace_id"),
    "relations": ("id", "source_id", "target_id", "kind", "rationale", "actor",
                  "created_at", "updated_at", "workspace_id"),
}

_DEFINITIONS = {
    re.match(r"CREATE (?:TABLE|TRIGGER) (\w+)", statement).group(1):
    " ".join(statement.strip().rstrip(";").split())
    for statement in _SCHEMA
}

# Version 1 remains an exact, recognized format. Version 2 only adds an audit
# ledger and protections; permanent annotation provenance is not a revision.
_ANNOTATION_SCHEMA = (
    """CREATE TABLE annotation_history (
        annotation_id TEXT NOT NULL REFERENCES annotations(id),
        revision INTEGER NOT NULL CHECK (revision > 0),
        target_id TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL, body TEXT NOT NULL, content_sha256 TEXT,
        editor TEXT, recorded_at TEXT NOT NULL, kind TEXT NOT NULL,
        PRIMARY KEY (annotation_id, revision)
    )""",
    """CREATE TRIGGER annotation_history_no_update BEFORE UPDATE ON annotation_history
        BEGIN SELECT RAISE(ABORT, 'annotation history is append-only'); END""",
    """CREATE TRIGGER annotation_history_no_delete BEFORE DELETE ON annotation_history
        BEGIN SELECT RAISE(ABORT, 'annotation history is append-only'); END""",
    """CREATE TRIGGER annotations_no_delete BEFORE DELETE ON annotations
        BEGIN SELECT RAISE(ABORT, 'audited annotations cannot be deleted'); END""",
    """CREATE TRIGGER annotations_provenance BEFORE UPDATE ON annotations
        WHEN NEW.id IS NOT OLD.id OR NEW.target_id IS NOT OLD.target_id
          OR NEW.actor IS NOT OLD.actor OR NEW.created_at IS NOT OLD.created_at
          OR NEW.content_sha256 IS NOT OLD.content_sha256
          OR NEW.workspace_id IS NOT OLD.workspace_id
        BEGIN SELECT RAISE(ABORT, 'annotation provenance is immutable'); END""",
    """CREATE TRIGGER annotations_audited_update BEFORE UPDATE ON annotations
        WHEN NOT EXISTS (
          SELECT 1 FROM annotation_history WHERE annotation_id = OLD.id
            AND revision = (SELECT MAX(revision) FROM annotation_history WHERE annotation_id = OLD.id)
            AND body IS NEW.body AND updated_at IS NEW.updated_at)
        BEGIN SELECT RAISE(ABORT, 'annotation update needs an audited snapshot'); END""",
)
_V2_COLUMNS = {**_COLUMNS, "annotation_history": (
    "annotation_id", "revision", "target_id", "actor", "created_at", "updated_at",
    "body", "content_sha256", "editor", "recorded_at", "kind")}
_V2_DEFINITIONS = {**_DEFINITIONS, **{
    re.match(r"CREATE (?:TABLE|TRIGGER) (\w+)", statement).group(1):
    " ".join(statement.strip().rstrip(";").split()) for statement in _ANNOTATION_SCHEMA}}

# Version 3 binds optional semantic reading positions to the SAME checkpoint
# revision. It does not reinterpret older checkpoints or mutate legacy stores.
_POSITION_SCHEMA = (
    """CREATE TABLE reading_positions (
        revision INTEGER PRIMARY KEY REFERENCES state_history(revision),
        target_id TEXT NOT NULL, content_sha256 TEXT NOT NULL,
        plain_text_sha256 TEXT NOT NULL, plain_text_length INTEGER NOT NULL CHECK (plain_text_length >= 0),
        cursor_offset INTEGER NOT NULL CHECK (cursor_offset >= 0 AND cursor_offset <= plain_text_length),
        viewport_offset INTEGER CHECK (viewport_offset >= 0 AND viewport_offset <= plain_text_length)
    )""",
    """CREATE TRIGGER reading_positions_no_update BEFORE UPDATE ON reading_positions
        BEGIN SELECT RAISE(ABORT, 'reading positions are append-only'); END""",
    """CREATE TRIGGER reading_positions_no_delete BEFORE DELETE ON reading_positions
        BEGIN SELECT RAISE(ABORT, 'reading positions are append-only'); END""",
)
_POSITION_FIELDS = ("target_id", "content_sha256", "plain_text_sha256", "plain_text_length",
                    "cursor_offset", "viewport_offset")
_V3_COLUMNS = {**_V2_COLUMNS, "reading_positions": ("revision",) + _POSITION_FIELDS}
_V3_DEFINITIONS = {**_V2_DEFINITIONS, **{
    re.match(r"CREATE (?:TABLE|TRIGGER) (\w+)", statement).group(1):
    " ".join(statement.strip().rstrip(";").split()) for statement in _POSITION_SCHEMA}}


def _position(value: Any) -> dict:
    if type(value) is not dict or set(value) != set(_POSITION_FIELDS):
        raise WorkspaceError("reading position must contain exactly the documented position fields")
    result = {"target_id": _uuid(value["target_id"], "reading position target")}
    for field in ("content_sha256", "plain_text_sha256"):
        result[field] = _hash(value[field], "reading position " + field)
        if result[field] is None:
            raise WorkspaceError("reading position requires text fingerprints")
    length = value["plain_text_length"]
    if type(length) is not int or not 0 <= length <= 2 ** 63 - 1:
        raise WorkspaceError("reading position text length must be a nonnegative bounded integer")
    result["plain_text_length"] = length
    for field in ("cursor_offset", "viewport_offset"):
        offset = value[field]
        if field == "viewport_offset" and offset is None:
            result[field] = None
            continue
        if type(offset) is not int or not 0 <= offset <= length:
            raise WorkspaceError("reading position offsets must be codepoint indices within the bound text")
        result[field] = offset
    return result


class Workspace:
    """Durable local records. Methods return JSON-compatible dictionaries."""

    def __init__(self, path: str | Path, corpus_id: str, provenance: dict,
                 actor: str = "Reader", *, read_only: bool = False) -> None:
        self.path = Path(path).expanduser().absolute()
        self.corpus_id = _uuid(corpus_id, "corpus identity")
        self.actor = _string(actor, "actor")
        if type(read_only) is not bool:
            raise WorkspaceError("read_only must be a boolean")
        self.read_only = read_only
        if type(provenance) is not dict:
            raise WorkspaceError("provenance must be a JSON object")
        encoded_provenance = _encode(provenance)
        self._requested_source_sha256 = _source_fingerprint(provenance)
        self._connection: sqlite3.Connection | None = None
        self._lease_descriptor: int | None = None
        try:
            if not read_only:
                self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.path.is_symlink():
                raise WorkspaceError("workspace database must not be a symbolic link")
            if read_only:
                if not self.path.is_file():
                    raise WorkspaceError("read-only workspace database must already exist")
                # SQLite's ordinary read-only WAL opening can create a -shm
                # sidecar. Never inspect WAL with immutable=1, which could hide
                # committed changes. A verified backup is the safe read desk.
                with self.path.open("rb") as handle:
                    header = handle.read(20)
                if header[:16] == b"SQLite format 3\x00" and 2 in header[18:20]:
                    raise WorkspaceError("read-only inspection does not open WAL workspaces; "
                                         "use a verified backup")
                new = False
            else:
                try:
                    descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
                except FileExistsError:
                    new = False
                else:
                    new = True
                    try:
                        if hasattr(os, "fchmod"):
                            os.fchmod(descriptor, 0o600)
                    finally:
                        os.close(descriptor)
            # A shared lifetime lease distinguishes an idle open SOL reader
            # from a closed workspace. SQLite transaction locks alone cannot
            # do that. Lifecycle deletion upgrades this same inode lease;
            # normal concurrent readers/writers continue to share it.
            if fcntl is not None:
                self._lease_descriptor = os.open(
                    self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                fcntl.flock(self._lease_descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
            connection = sqlite3.connect(
                self.path.as_uri() + ("?mode=ro" if read_only else "?mode=rw"),
                uri=True, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            self._connection = connection
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA trusted_schema = OFF")
            if new:
                with self._transaction():
                    for statement in _SCHEMA + _ANNOTATION_SCHEMA + _POSITION_SCHEMA:
                        connection.execute(statement)
                    connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
                    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                    connection.execute("INSERT INTO workspace_metadata VALUES (1, ?, ?, ?, ?)",
                                       (SCHEMA_VERSION, self.corpus_id, encoded_provenance, _now()))
            self._check_schema()
        except (sqlite3.Error, OSError) as error:
            self.close()
            raise WorkspaceError(f"cannot open workspace {self.path}: {error}") from error
        except Exception:
            self.close()
            raise

    def __enter__(self) -> Workspace:
        self._db()
        return self

    def __exit__(self, *exception_info) -> None:
        self.close()

    def close(self) -> None:
        try:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
        finally:
            if self._lease_descriptor is not None:
                os.close(self._lease_descriptor)
                self._lease_descriptor = None

    def _db(self) -> sqlite3.Connection:
        if self._connection is None:
            raise WorkspaceError("workspace is closed")
        return self._connection

    @contextmanager
    def _transaction(self, *, write: bool = True) -> Iterator[sqlite3.Connection]:
        connection = self._db()
        if write and self.read_only:
            raise WorkspaceError("workspace is read-only")
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except BaseException as error:
            connection.rollback()
            if isinstance(error, sqlite3.Error):
                raise WorkspaceError(f"workspace database operation failed: {error}") from error
            raise

    def _check_schema(self) -> None:
        with self._transaction(write=False):
            self._check_schema_contents()

    def _check_schema_contents(self) -> None:
        connection = self._db()
        if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            raise WorkspaceError("not a recognized SOL workspace; existing database was not changed")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (1, 2, SCHEMA_VERSION):
            raise WorkspaceError(f"unsupported workspace schema version {version}; "
                                 f"expected 1, 2 or {SCHEMA_VERSION}; no migration was attempted")
        self.schema_version = version
        columns_map = {1: _COLUMNS, 2: _V2_COLUMNS, 3: _V3_COLUMNS}[version]
        definitions = {1: _DEFINITIONS, 2: _V2_DEFINITIONS, 3: _V3_DEFINITIONS}[version]
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        if tables != set(columns_map):
            raise WorkspaceError("workspace schema is damaged or unrecognized")
        for table, columns in columns_map.items():
            actual = tuple(row["name"] for row in connection.execute(f"PRAGMA table_info({table})"))
            if actual != columns:
                raise WorkspaceError(f"workspace table {table} is damaged or unrecognized")
        triggers = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'")}
        expected_triggers = {name for name, definition in definitions.items()
                             if definition.startswith("CREATE TRIGGER")}
        if triggers != expected_triggers:
            raise WorkspaceError("workspace append-only protections are missing")
        for row in connection.execute("SELECT type,name,sql FROM sqlite_master"):
            if row["type"] in {"table", "trigger"}:
                actual = " ".join(row["sql"].strip().rstrip(";").split()) if row["sql"] else ""
                if actual != definitions.get(row["name"]):
                    raise WorkspaceError("workspace schema definitions or append-only protections "
                                         "are damaged or unrecognized")
            elif row["type"] != "index" or row["sql"] is not None:
                raise WorkspaceError("workspace contains unrecognized schema objects")
        if [row[0] for row in connection.execute("PRAGMA quick_check")] != ["ok"]:
            raise WorkspaceError("workspace database integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise WorkspaceError("workspace database contains broken references")
        metadata = connection.execute("SELECT * FROM workspace_metadata").fetchall()
        if len(metadata) != 1 or metadata[0]["singleton"] != 1:
            raise WorkspaceError("workspace identity metadata is damaged")
        metadata = metadata[0]
        if metadata["schema_version"] != version:
            raise WorkspaceError("workspace schema metadata disagrees with the database version")
        if metadata["corpus_id"] != self.corpus_id:
            raise WorkspaceError("workspace belongs to a different corpus; choose another workspace")
        provenance = _decode(metadata["provenance"])
        if type(provenance) is not dict:
            raise WorkspaceError("workspace provenance is not a JSON object")
        self.source_sha256 = _source_fingerprint(provenance)
        if self.source_sha256 != self._requested_source_sha256:
            raise WorkspaceError("workspace source fingerprint does not match this corpus; "
                                 "choose another workspace")
        self.provenance = provenance
        self.created_at = metadata["created_at"]
        _timestamp(self.created_at, "workspace creation time")
        # Validate persisted values as well as SQLite's structural integrity.
        state = self.get_state()
        history = self.list_history(1)
        if (state is None) != (not history) or (
                state is not None and any(state[field] != history[0][field]
                                          for field in state)):
            raise WorkspaceError("reading state and checkpoint history disagree")
        if state is not None and connection.execute(
                "SELECT COUNT(*) FROM state_history").fetchone()[0] != state["revision"]:
            raise WorkspaceError("reading checkpoint history has missing revisions")
        for row in connection.execute("SELECT * FROM state_history ORDER BY revision"):
            self._history(row)
        self.list_bookmarks()
        self.list_annotations()
        if version >= 2:
            self._validate_annotation_history()
        if version >= 3:
            for row in connection.execute("SELECT * FROM reading_positions"):
                _position({field: row[field] for field in _POSITION_FIELDS})
                history_row = connection.execute("SELECT current_id FROM state_history WHERE revision = ?",
                                                 (row["revision"],)).fetchone()
                if history_row is None or history_row["current_id"] is None:
                    raise WorkspaceError("reading position has no identified checkpoint passage")
        self.list_comparisons()
        self.list_reviews()
        self.list_relations()

    def _one(self, sql: str, parameters: tuple = ()) -> sqlite3.Row | None:
        try:
            return self._db().execute(sql, parameters).fetchone()
        except sqlite3.Error as error:
            raise WorkspaceError(f"cannot read workspace: {error}") from error

    def _all(self, sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
        try:
            return self._db().execute(sql, parameters).fetchall()
        except sqlite3.Error as error:
            raise WorkspaceError(f"cannot read workspace: {error}") from error

    def _record(self, row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        record = dict(row)
        record.pop("workspace_id", None)
        for field in ("id", "target_id", "source_id"):
            if field in record:
                record[field] = _uuid(record[field], "stored " + field)
        for field in ("content_sha256", "source_sha256"):
            if field in record:
                record[field] = _hash(record[field], "stored " + field)
        for field in ("name", "actor", "kind"):
            if field in record:
                _string(record[field], "stored " + field)
        for field in ("body", "question", "issue", "rationale"):
            if field in record:
                _string(record[field], "stored " + field, empty=field != "body", multiline=True)
        for field in ("created_at", "updated_at"):
            if field in record:
                _timestamp(record[field], "stored " + field)
        if "outcome" in record and record["outcome"] not in REVIEW_OUTCOMES:
            raise WorkspaceError("stored review outcome is invalid")
        if ("source_sha256" in record and record["source_sha256"] is not None
                and self.source_sha256 is not None and record["source_sha256"] != self.source_sha256):
            raise WorkspaceError("stored review source fingerprint disagrees with this workspace")
        record["corpus_id"] = self.corpus_id
        return record

    @staticmethod
    def _state(state: Any) -> dict:
        if type(state) is not dict or set(state) - {
                "cwd", "scope", "current_id", "previous_cwd", "revision", "position"}:
            raise WorkspaceError("reading state must contain only the documented state fields")
        result = {}
        for field in ("cwd", "scope"):
            value = _string(state.get(field), field)
            if not value.startswith("/"):
                raise WorkspaceError(f"{field} must be an absolute virtual path")
            result[field] = value
        result["current_id"] = (None if state.get("current_id") is None
                                else _uuid(state["current_id"], "current passage identifier"))
        previous = state.get("previous_cwd")
        if previous is not None and not _string(previous, "previous directory").startswith("/"):
            raise WorkspaceError("previous directory must be an absolute virtual path")
        result["previous_cwd"] = previous
        if "revision" in state and (type(state["revision"]) is not int or state["revision"] < 1):
            raise WorkspaceError("state revision must be a positive integer")
        if state.get("position") is not None:
            if result["current_id"] is None:
                raise WorkspaceError("reading position requires an identified current passage")
            result["position"] = _position(state["position"])
        return result

    def _saved_position(self, revision: int) -> dict | None:
        if self.schema_version < 3:
            return None
        row = self._one("SELECT * FROM reading_positions WHERE revision = ?", (revision,))
        return None if row is None else _position({field: row[field] for field in _POSITION_FIELDS})

    def get_state(self) -> dict | None:
        row = self._one("SELECT cwd, scope, current_id, previous_cwd, revision "
                        "FROM reading_state WHERE singleton = 1")
        if row is None:
            return None
        state = self._state(dict(row))
        revision = row["revision"]
        if type(revision) is not int or revision < 1:
            raise WorkspaceError("stored reading state revision is invalid")
        state["revision"] = revision
        position = self._saved_position(revision)
        if position is not None:
            state["position"] = position
        return state

    def save_state(self, state: dict, expected_revision: int | None = None) -> int:
        values = self._state(state)
        if values.get("position") is not None and self.schema_version < 3:
            raise WorkspaceError("reading positions need workspace version 3; upgrade a separate copy first")
        if expected_revision is not None and (type(expected_revision) is not int
                                               or expected_revision < 1):
            raise WorkspaceError("expected revision must be a positive integer or null")
        if "revision" in state and state["revision"] != expected_revision:
            raise WorkspaceError("state revision must agree with the expected revision")
        with self._transaction() as connection:
            current = connection.execute(
                "SELECT revision FROM reading_state WHERE singleton = 1").fetchone()
            actual = None if current is None else current["revision"]
            if actual != expected_revision:
                raise WorkspaceConflict("reading state changed in another session; "
                                        "reload it before saving or choose another workspace")
            if actual == 2 ** 63 - 1:
                raise WorkspaceError("reading state revision counter is exhausted")
            revision = 1 if actual is None else actual + 1
            connection.execute(
                "INSERT INTO reading_state VALUES (1, ?, ?, ?, ?, ?) "
                "ON CONFLICT(singleton) DO UPDATE SET cwd=excluded.cwd, scope=excluded.scope, "
                "current_id=excluded.current_id, previous_cwd=excluded.previous_cwd, "
                "revision=excluded.revision",
                (values["cwd"], values["scope"], values["current_id"],
                 values["previous_cwd"], revision))
            connection.execute(
                "INSERT INTO state_history(revision,cwd,scope,current_id,previous_cwd,actor,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (revision, values["cwd"], values["scope"], values["current_id"],
                 values["previous_cwd"], self.actor, _now()))
            if values.get("position") is not None:
                position = values["position"]
                connection.execute(
                    "INSERT INTO reading_positions VALUES (?,?,?,?,?,?,?)",
                    (revision,) + tuple(position[field] for field in _POSITION_FIELDS))
        return revision

    def _history(self, row: sqlite3.Row) -> dict:
        record = self._record(row)
        self._state({field: record[field] for field in (
            "cwd", "scope", "current_id", "previous_cwd", "revision")})
        position = self._saved_position(record["revision"])
        if position is not None:
            record["position"] = position
        return record

    def list_history(self, limit: int = 20) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise WorkspaceError("history limit must be an integer between 1 and 1000")
        return [self._history(row) for row in self._all(
            "SELECT * FROM state_history ORDER BY revision DESC LIMIT ?", (limit,))]

    def get_history(self, revision: int) -> dict | None:
        if type(revision) is not int or revision < 1:
            raise WorkspaceError("history revision must be a positive integer")
        if revision > 2 ** 63 - 1:
            return None
        row = self._one("SELECT * FROM state_history WHERE revision = ?", (revision,))
        return None if row is None else self._history(row)

    def set_bookmark(self, name: str, target_id: str, replace: bool = False) -> dict:
        name, target_id = _string(name, "bookmark name"), _uuid(target_id)
        if type(replace) is not bool:
            raise WorkspaceError("replace must be a boolean")
        timestamp = _now()
        with self._transaction() as connection:
            if not replace and connection.execute(
                    "SELECT 1 FROM bookmarks WHERE name = ?", (name,)).fetchone() is not None:
                raise WorkspaceError("bookmark name already exists; request replacement explicitly")
            connection.execute(
                "INSERT INTO bookmarks(name,target_id,actor,created_at,updated_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET target_id=excluded.target_id, "
                "actor=excluded.actor, updated_at=excluded.updated_at",
                (name, target_id, self.actor, timestamp, timestamp))
            result = self._record(connection.execute(
                "SELECT * FROM bookmarks WHERE name = ?", (name,)).fetchone())
        return result

    def get_bookmark(self, name: str) -> dict | None:
        return self._record(self._one("SELECT * FROM bookmarks WHERE name = ?",
                                     (_string(name, "bookmark name"),)))

    def list_bookmarks(self) -> list[dict]:
        return [self._record(row) for row in self._all("SELECT * FROM bookmarks ORDER BY name")]

    def _delete(self, table: str, column: str, key: str) -> bool:
        with self._transaction() as connection:
            return connection.execute(f"DELETE FROM {table} WHERE {column} = ?", (key,)).rowcount > 0

    def delete_bookmark(self, name: str) -> bool:
        return self._delete("bookmarks", "name", _string(name, "bookmark name"))

    def add_annotation(self, target_id: str, body: str, content_sha256: str | None = None) -> dict:
        target_id, body = _uuid(target_id), _string(body, "annotation body", multiline=True)
        digest = _hash(content_sha256, "content digest")
        identifier, timestamp = str(uuid4()), _now()
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO annotations(id,target_id,body,actor,created_at,updated_at,content_sha256) "
                "VALUES(?,?,?,?,?,?,?)",
                (identifier, target_id, body, self.actor, timestamp, timestamp, digest))
            if self.schema_version >= 2:
                self._append_annotation_snapshot(connection, identifier, 1, self.actor,
                                                 timestamp, "created")
            result = self._annotation(connection.execute(
                "SELECT * FROM annotations WHERE id = ?", (identifier,)).fetchone())
        return result

    def _annotation(self, row: sqlite3.Row | None) -> dict | None:
        record = self._record(row)
        if record is not None:
            record["attribution"] = {"role": "personal_note", "author": record["actor"]}
            record["revision"] = None if self.schema_version == 1 else self._one(
                "SELECT MAX(revision) AS revision FROM annotation_history WHERE annotation_id = ?",
                (record["id"],))["revision"]
            if self.schema_version >= 2 and (
                    type(record["revision"]) is not int or record["revision"] < 1):
                raise WorkspaceError("annotation is missing its audited revision")
        return record

    def get_annotation(self, identifier: str) -> dict | None:
        with self._snapshot():
            return self._annotation(self._one("SELECT * FROM annotations WHERE id = ?",
                                             (_uuid(identifier, "annotation identifier"),)))

    def list_annotations(self, target_id: str | None = None) -> list[dict]:
        clause, arguments = ("", ()) if target_id is None else (" WHERE target_id = ?", (_uuid(target_id),))
        with self._snapshot():
            return [self._annotation(row) for row in self._all(
                "SELECT * FROM annotations" + clause + " ORDER BY created_at,id", arguments)]

    def _append_annotation_snapshot(self, connection: sqlite3.Connection, identifier: str,
                                    revision: int, editor: str | None, recorded_at: str,
                                    kind: str) -> None:
        connection.execute(
            "INSERT INTO annotation_history(annotation_id,revision,target_id,actor,created_at,"
            "updated_at,body,content_sha256,editor,recorded_at,kind) "
            "SELECT id,?,target_id,actor,created_at,updated_at,body,content_sha256,?,?,? "
            "FROM annotations WHERE id = ?", (revision, editor, recorded_at, kind, identifier))

    def _annotation_snapshot(self, row: sqlite3.Row) -> dict:
        record = self._record(row)
        record["annotation_id"] = _uuid(record["annotation_id"], "stored annotation identifier")
        if type(record["revision"]) is not int or record["revision"] < 1:
            raise WorkspaceError("stored annotation revision is invalid")
        _timestamp(record["recorded_at"], "stored annotation audit time")
        if record["kind"] not in {"created", "edited", "legacy_baseline"}:
            raise WorkspaceError("stored annotation audit kind is invalid")
        if record["editor"] is not None:
            _string(record["editor"], "stored annotation editor")
        return record

    def list_annotation_history(self, identifier: str) -> list[dict]:
        identifier = _uuid(identifier, "annotation identifier")
        if self.schema_version == 1:
            return []
        return [self._annotation_snapshot(row) for row in self._all(
            "SELECT * FROM annotation_history WHERE annotation_id = ? ORDER BY revision",
            (identifier,))]

    def _validate_annotation_history(self, identifier: str | None = None) -> None:
        clause = "" if identifier is None else " WHERE id = ?"
        arguments = () if identifier is None else (identifier,)
        annotations = {row["id"]: self._record(row) for row in self._all(
            "SELECT * FROM annotations" + clause, arguments)}
        histories: dict[str, list[dict]] = {}
        clause = "" if identifier is None else " WHERE annotation_id = ?"
        for row in self._all("SELECT * FROM annotation_history" + clause +
                             " ORDER BY annotation_id,revision", arguments):
            snapshot = self._annotation_snapshot(row)
            histories.setdefault(snapshot["annotation_id"], []).append(snapshot)
        if set(histories) != set(annotations):
            raise WorkspaceError("annotation history is missing or has unknown annotations")
        for identifier, snapshots in histories.items():
            annotation = annotations[identifier]
            if [row["revision"] for row in snapshots] != list(range(1, len(snapshots) + 1)):
                raise WorkspaceError("annotation history has missing revisions")
            previous_time = None
            for position, snapshot in enumerate(snapshots):
                if any(snapshot[field] != annotation[field] for field in (
                        "target_id", "actor", "created_at", "content_sha256")):
                    raise WorkspaceError("annotation history provenance disagrees with its annotation")
                if position == 0:
                    if snapshot["kind"] not in {"created", "legacy_baseline"}:
                        raise WorkspaceError("annotation history needs a creation or legacy baseline")
                elif snapshot["kind"] != "edited":
                    raise WorkspaceError("annotation history contains an invalid later baseline")
                baseline = snapshot["kind"] == "legacy_baseline"
                if (baseline and snapshot["editor"] is not None) or (
                        not baseline and snapshot["editor"] != annotation["actor"]):
                    raise WorkspaceError("annotation history editor attribution is invalid")
                if not baseline and snapshot["updated_at"] != snapshot["recorded_at"]:
                    raise WorkspaceError("annotation history update and audit timestamps disagree")
                if snapshot["kind"] == "created" and snapshot["created_at"] != snapshot["recorded_at"]:
                    raise WorkspaceError("annotation creation timestamp disagrees with its audit")
                moment = datetime.fromisoformat(snapshot["recorded_at"].replace("Z", "+00:00"))
                if previous_time is not None and moment < previous_time:
                    raise WorkspaceError("annotation history audit timestamps go backwards")
                previous_time = moment
                if position and snapshot["body"] == snapshots[position - 1]["body"]:
                    raise WorkspaceError("annotation history contains an unchanged-body revision")
            latest = snapshots[-1]
            if any(latest[field] != annotation[field] for field in (
                    "body", "updated_at", "content_sha256")):
                raise WorkspaceError("annotation projection and latest history disagree")

    def update_annotation(self, identifier: str, body: str,
                          content_sha256: str | None = None, *,
                          expected_revision: int | None = None) -> dict:
        if self.schema_version == 1:
            raise WorkspaceError("editing needs workspace schema 2; explicitly copy-upgrade this "
                                 "workspace with 'workspace upgrade NEW.sqlite3' first")
        if type(expected_revision) is not int or expected_revision < 1:
            raise WorkspaceError("an explicit positive expected annotation revision is required")
        identifier = _uuid(identifier, "annotation identifier")
        body, digest = _string(body, "annotation body", multiline=True), _hash(content_sha256, "content digest")
        with self._transaction() as connection:
            existing = connection.execute("SELECT * FROM annotations WHERE id = ?",
                                          (identifier,)).fetchone()
            if existing is None:
                raise WorkspaceError("no such annotation")
            if existing["actor"] != self.actor:
                raise WorkspaceError("annotation belongs to another actor; its authorship "
                                     "cannot be reassigned by editing")
            if digest is not None and digest != existing["content_sha256"]:
                raise WorkspaceError("annotation content digest is immutable; body editing "
                                     "cannot rebind its source")
            # Validate the target inside the same write transaction as CAS. A
            # long-lived session must not append to a malformed concurrent head.
            self._validate_annotation_history(identifier)
            head = connection.execute(
                "SELECT revision,recorded_at FROM annotation_history WHERE annotation_id = ? "
                "ORDER BY revision DESC LIMIT 1", (identifier,)).fetchone()
            revision = head["revision"]
            if revision != expected_revision:
                raise WorkspaceConflict("annotation changed in another session; reload its "
                                        "revision before editing")
            if body == existing["body"]:
                return self._annotation(existing)
            if revision == 2 ** 63 - 1:
                raise WorkspaceError("annotation revision counter is exhausted")
            timestamp = _now()
            _timestamp(timestamp, "annotation edit time")
            if (datetime.fromisoformat(timestamp.replace("Z", "+00:00")) <
                    datetime.fromisoformat(head["recorded_at"].replace("Z", "+00:00"))):
                raise WorkspaceError("system clock precedes the latest annotation audit; "
                                     "correct the clock before editing")
            connection.execute(
                "INSERT INTO annotation_history(annotation_id,revision,target_id,actor,created_at,"
                "updated_at,body,content_sha256,editor,recorded_at,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (identifier, revision + 1, existing["target_id"], existing["actor"],
                 existing["created_at"], timestamp, body, existing["content_sha256"],
                 self.actor, timestamp, "edited"))
            connection.execute("UPDATE annotations SET body=?, updated_at=? WHERE id=?",
                               (body, timestamp, identifier))
            result = self._annotation(connection.execute(
                "SELECT * FROM annotations WHERE id = ?", (identifier,)).fetchone())
        return result

    def delete_annotation(self, identifier: str) -> bool:
        if self.schema_version >= 2:
            raise WorkspaceError("audited annotations cannot be deleted; their revision history "
                                 "is permanent")
        return self._delete("annotations", "id", _uuid(identifier, "annotation identifier"))

    def save_comparison(self, name: str, target_ids: list[str], question: str = "",
                        replace: bool = False) -> dict:
        name, question = _string(name, "comparison name"), _string(question, "question", empty=True, multiline=True)
        if type(replace) is not bool:
            raise WorkspaceError("replace must be a boolean")
        if type(target_ids) is not list or not target_ids:
            raise WorkspaceError("comparison targets must be a nonempty ordered JSON array")
        targets = [_uuid(identifier) for identifier in target_ids]
        timestamp = _now()
        with self._transaction() as connection:
            if not replace and connection.execute(
                    "SELECT 1 FROM comparisons WHERE name = ?", (name,)).fetchone() is not None:
                raise WorkspaceError("comparison name already exists; request replacement explicitly")
            connection.execute(
                "INSERT INTO comparisons(name,question,actor,created_at,updated_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET question=excluded.question, actor=excluded.actor, "
                "updated_at=excluded.updated_at",
                (name, question, self.actor, timestamp, timestamp))
            connection.execute("DELETE FROM comparison_items WHERE comparison_name = ?", (name,))
            connection.executemany("INSERT INTO comparison_items VALUES(?,?,?)",
                                   [(name, position, identifier) for position, identifier in enumerate(targets)])
            result = self._comparison(connection.execute(
                "SELECT * FROM comparisons WHERE name = ?", (name,)).fetchone())
        return result

    def _comparison(self, row: sqlite3.Row | None) -> dict | None:
        record = self._record(row)
        if record is not None:
            items = self._all("SELECT position,target_id FROM comparison_items "
                              "WHERE comparison_name = ? ORDER BY position", (record["name"],))
            if not items or [item["position"] for item in items] != list(range(len(items))):
                raise WorkspaceError("comparison ordering is damaged")
            record["target_ids"] = [_uuid(item["target_id"], "stored comparison target") for item in items]
        return record

    def get_comparison(self, name: str) -> dict | None:
        name = _string(name, "comparison name")
        with self._snapshot():
            return self._comparison(self._one("SELECT * FROM comparisons WHERE name = ?", (name,)))

    def list_comparisons(self) -> list[dict]:
        with self._snapshot():
            return [self._comparison(row) for row in self._all("SELECT * FROM comparisons ORDER BY name")]

    @contextmanager
    def _snapshot(self) -> Iterator[None]:
        """Join an existing transaction, otherwise hold one coherent read view."""
        if self._db().in_transaction:
            yield
        else:
            with self._transaction(write=False):
                yield

    def delete_comparison(self, name: str) -> bool:
        return self._delete("comparisons", "name", _string(name, "comparison name"))

    def add_review(self, target_id: str, outcome: str, issue: str = "",
                   content_sha256: str | None = None, source_sha256: str | None = None) -> dict:
        target_id, outcome = _uuid(target_id), _string(outcome, "review outcome")
        if outcome not in REVIEW_OUTCOMES:
            raise WorkspaceError("review outcome must be one of: " + ", ".join(REVIEW_OUTCOMES))
        issue = _string(issue, "review issue", empty=True, multiline=True)
        content = _hash(content_sha256, "content digest")
        source = _hash(source_sha256, "source digest")
        if source is not None and self.source_sha256 is not None and source != self.source_sha256:
            raise WorkspaceError("review source fingerprint disagrees with this workspace")
        identifier, timestamp = str(uuid4()), _now()
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO reviews(id,target_id,actor,outcome,issue,created_at,"
                "content_sha256,source_sha256) VALUES(?,?,?,?,?,?,?,?)",
                (identifier, target_id, self.actor, outcome, issue, timestamp, content, source))
            result = self._record(connection.execute(
                "SELECT * FROM reviews WHERE id = ?", (identifier,)).fetchone())
        return result

    def list_reviews(self, target_id: str | None = None) -> list[dict]:
        clause, arguments = ("", ()) if target_id is None else (" WHERE target_id = ?", (_uuid(target_id),))
        return [self._record(row) for row in self._all(
            "SELECT * FROM reviews" + clause + " ORDER BY rowid", arguments)]

    def add_relation(self, source_id: str, target_id: str, kind: str, rationale: str = "") -> dict:
        source_id, target_id = _uuid(source_id, "source identifier"), _uuid(target_id)
        kind, rationale = _string(kind, "relation kind"), _string(rationale, "rationale", empty=True, multiline=True)
        identifier, timestamp = str(uuid4()), _now()
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO relations(id,source_id,target_id,kind,rationale,actor,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (identifier, source_id, target_id, kind, rationale, self.actor, timestamp, timestamp))
            result = self._relation(connection.execute(
                "SELECT * FROM relations WHERE id = ?", (identifier,)).fetchone())
        return result

    def _relation(self, row: sqlite3.Row | None) -> dict | None:
        record = self._record(row)
        if record is not None:
            record["evidence_origin"] = "reader"
        return record

    def get_relation(self, identifier: str) -> dict | None:
        return self._relation(self._one("SELECT * FROM relations WHERE id = ?",
                                       (_uuid(identifier, "relation identifier"),)))

    def list_relations(self, target_id: str | None = None) -> list[dict]:
        clause, arguments = ("", ()) if target_id is None else (
            " WHERE source_id = ? OR target_id = ?", (_uuid(target_id), _uuid(target_id)))
        return [self._relation(row) for row in self._all(
            "SELECT * FROM relations" + clause + " ORDER BY created_at,id", arguments)]

    def delete_relation(self, identifier: str) -> bool:
        return self._delete("relations", "id", _uuid(identifier, "relation identifier"))

    def backup(self, destination: str | Path) -> Path:
        """Publish a verified SQLite snapshot without overwriting any path.

        The destination directory must already exist. The same-directory staged
        file is published by an exclusive hard link; unsupported filesystems fail
        closed rather than falling back to an overwrite-capable rename.
        """
        return self._publish_copy(destination, upgrade=False)

    def upgrade_copy(self, destination: str | Path) -> Path:
        """Explicitly create a current-schema copy; never migrate the source."""
        self._db()
        if self.schema_version == SCHEMA_VERSION:
            raise WorkspaceError(f"workspace is already schema {SCHEMA_VERSION}; use backup for a same-version copy")
        return self._publish_copy(destination, upgrade=True)

    def _migrate_staged(self) -> None:
        if self.schema_version not in (1, 2):
            raise WorkspaceError("copy upgrade requires a verified version 1 or 2 workspace")
        timestamp = _now()
        with self._transaction() as connection:
            if self.schema_version == 1:
                for statement in _ANNOTATION_SCHEMA:
                    connection.execute(statement)
                # A legacy snapshot is evidence of the body at upgrade time only.
                # Preserve its original updated_at; no past editor is invented.
                for row in connection.execute("SELECT id FROM annotations ORDER BY id").fetchall():
                    self._append_annotation_snapshot(connection, row["id"], 1, None,
                                                     timestamp, "legacy_baseline")
            for statement in _POSITION_SCHEMA:
                connection.execute(statement)
            connection.execute("UPDATE workspace_metadata SET schema_version = ? WHERE singleton = 1",
                               (SCHEMA_VERSION,))
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._check_schema_contents()

    def _publish_copy(self, destination: str | Path, *, upgrade: bool) -> Path:
        source = self._db()
        if source.in_transaction:
            raise WorkspaceError("finish the active workspace transaction before creating a backup")
        if not isinstance(destination, (str, Path)):
            raise WorkspaceError("backup destination must be a filesystem path")
        target = Path(destination).expanduser().absolute()
        _string(str(target), "backup destination")
        if target.suffix.lower() != ".sqlite3":
            raise WorkspaceError("backup destination must end in .sqlite3")
        staged: Path | None = None
        published = False
        completed = False
        try:
            if target.is_symlink():
                raise WorkspaceError("backup destination must not be a symbolic link")
            if target.resolve() == self.path.resolve() or (
                    target.exists() and os.path.samefile(target, self.path)):
                raise WorkspaceError("backup destination must not refer to the source workspace")
            if target.exists():
                raise WorkspaceError("backup destination already exists; choose a new filename")
            if not target.parent.is_dir():
                raise WorkspaceError("backup destination directory must already exist")
            descriptor, temporary = tempfile.mkstemp(
                prefix=".sol-backup-", suffix=".sqlite3", dir=target.parent)
            staged = Path(temporary)
            try:
                if hasattr(os, "fchmod"):
                    os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
            deadline = time.monotonic() + 30

            def progress(status: int, remaining: int, total: int) -> None:
                if time.monotonic() > deadline:
                    raise WorkspaceError("workspace backup timed out; no backup was published")

            snapshot = sqlite3.connect(staged.as_uri() + "?mode=rw", uri=True, isolation_level=None)
            try:
                source.backup(snapshot, pages=128, progress=progress, sleep=0.05)
            finally:
                snapshot.close()
            # Opening an already initialized workspace performs only read checks.
            with Workspace(staged, self.corpus_id, self.provenance, self.actor) as snapshot_workspace:
                if upgrade:
                    snapshot_workspace._migrate_staged()
            with staged.open("rb") as handle:
                os.fsync(handle.fileno())
            try:
                os.link(staged, target)
            except FileExistsError as error:
                raise WorkspaceError("backup destination already exists; choose a new filename") from error
            published = True
            if hasattr(os, "O_DIRECTORY"):
                directory_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            completed = True
            return target
        except (sqlite3.Error, OSError) as error:
            raise WorkspaceError(f"cannot create workspace backup: {error}") from error
        finally:
            # Delete only the private files created for this operation. If an
            # exception followed publication, remove our link only while its inode
            # still matches the staging file; never remove a replacement file.
            if staged is not None:
                if not completed and published:
                    try:
                        if os.path.samefile(staged, target):
                            target.unlink()
                    except FileNotFoundError:
                        pass
                for path in (staged, Path(str(staged) + "-journal"),
                             Path(str(staged) + "-wal"), Path(str(staged) + "-shm")):
                    path.unlink(missing_ok=True)

    def export(self) -> dict:
        """A consistent portable snapshot containing references, not corpus text."""
        with self._transaction(write=False):
            exported = {
                "format": "sol-workspace", "schema_version": self.schema_version,
                "corpus_id": self.corpus_id, "provenance": self.provenance,
                "created_at": self.created_at, "exported_at": _now(),
                "state": self.get_state(), "bookmarks": self.list_bookmarks(),
                "history": [self._history(row) for row in self._all(
                    "SELECT * FROM state_history ORDER BY revision DESC")],
                "annotations": self.list_annotations(), "comparisons": self.list_comparisons(),
                "reviews": self.list_reviews(), "relations": self.list_relations(),
            }
            if self.schema_version >= 2:
                exported["annotation_history"] = [self._annotation_snapshot(row) for row in self._all(
                    "SELECT * FROM annotation_history ORDER BY annotation_id,revision")]
            _json_value(exported)
        # Return an independent JSON value, including an independent provenance.
        return _decode(_encode(exported))
