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
from typing import Any, Iterator
import unicodedata
from uuid import UUID, uuid4


SCHEMA_VERSION = 1
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


class Workspace:
    """Durable local records. Methods return JSON-compatible dictionaries."""

    def __init__(self, path: str | Path, corpus_id: str, provenance: dict,
                 actor: str = "Reader") -> None:
        self.path = Path(path).expanduser().absolute()
        self.corpus_id = _uuid(corpus_id, "corpus identity")
        self.actor = _string(actor, "actor")
        if type(provenance) is not dict:
            raise WorkspaceError("provenance must be a JSON object")
        encoded_provenance = _encode(provenance)
        self._requested_source_sha256 = _source_fingerprint(provenance)
        self._connection: sqlite3.Connection | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.path.is_symlink():
                raise WorkspaceError("workspace database must not be a symbolic link")
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
            connection = sqlite3.connect(
                self.path.as_uri() + "?mode=rw", uri=True, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            self._connection = connection
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA trusted_schema = OFF")
            if new:
                with self._transaction():
                    for statement in _SCHEMA:
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
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _db(self) -> sqlite3.Connection:
        if self._connection is None:
            raise WorkspaceError("workspace is closed")
        return self._connection

    @contextmanager
    def _transaction(self, *, write: bool = True) -> Iterator[sqlite3.Connection]:
        connection = self._db()
        try:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except Exception as error:
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
        if version != SCHEMA_VERSION:
            raise WorkspaceError(f"unsupported workspace schema version {version}; "
                                 f"expected {SCHEMA_VERSION}; no migration was attempted")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        if tables != set(_COLUMNS):
            raise WorkspaceError("workspace schema is damaged or unrecognized")
        for table, columns in _COLUMNS.items():
            actual = tuple(row["name"] for row in connection.execute(f"PRAGMA table_info({table})"))
            if actual != columns:
                raise WorkspaceError(f"workspace table {table} is damaged or unrecognized")
        triggers = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'")}
        if triggers != {"reviews_no_update", "reviews_no_delete",
                        "history_no_update", "history_no_delete"}:
            raise WorkspaceError("workspace append-only protections are missing")
        for row in connection.execute("SELECT type,name,sql FROM sqlite_master"):
            if row["type"] in {"table", "trigger"}:
                actual = " ".join(row["sql"].strip().rstrip(";").split()) if row["sql"] else ""
                if actual != _DEFINITIONS.get(row["name"]):
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
        if metadata["schema_version"] != SCHEMA_VERSION:
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
        self.list_bookmarks()
        self.list_annotations()
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
                "cwd", "scope", "current_id", "previous_cwd", "revision"}:
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
        return result

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
        return state

    def save_state(self, state: dict, expected_revision: int | None = None) -> int:
        values = self._state(state)
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
        return revision

    def _history(self, row: sqlite3.Row) -> dict:
        record = self._record(row)
        self._state({field: record[field] for field in (
            "cwd", "scope", "current_id", "previous_cwd", "revision")})
        return record

    def list_history(self, limit: int = 20) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise WorkspaceError("history limit must be an integer between 1 and 1000")
        return [self._history(row) for row in self._all(
            "SELECT * FROM state_history ORDER BY revision DESC LIMIT ?", (limit,))]

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
            result = self._annotation(connection.execute(
                "SELECT * FROM annotations WHERE id = ?", (identifier,)).fetchone())
        return result

    def _annotation(self, row: sqlite3.Row | None) -> dict | None:
        record = self._record(row)
        if record is not None:
            record["attribution"] = {"role": "personal_note", "author": record["actor"]}
        return record

    def get_annotation(self, identifier: str) -> dict | None:
        return self._annotation(self._one("SELECT * FROM annotations WHERE id = ?",
                                         (_uuid(identifier, "annotation identifier"),)))

    def list_annotations(self, target_id: str | None = None) -> list[dict]:
        clause, arguments = ("", ()) if target_id is None else (" WHERE target_id = ?", (_uuid(target_id),))
        return [self._annotation(row) for row in self._all(
            "SELECT * FROM annotations" + clause + " ORDER BY created_at,id", arguments)]

    def update_annotation(self, identifier: str, body: str,
                          content_sha256: str | None = None) -> dict:
        identifier = _uuid(identifier, "annotation identifier")
        body, digest = _string(body, "annotation body", multiline=True), _hash(content_sha256, "content digest")
        with self._transaction() as connection:
            existing = connection.execute("SELECT actor FROM annotations WHERE id = ?",
                                          (identifier,)).fetchone()
            if existing is None:
                raise WorkspaceError("no such annotation")
            if existing["actor"] != self.actor:
                raise WorkspaceError("annotation belongs to another actor; its authorship "
                                     "cannot be reassigned by editing")
            changed = connection.execute(
                "UPDATE annotations SET body=?, updated_at=?, "
                "content_sha256=COALESCE(?, content_sha256) WHERE id=?",
                (body, _now(), digest, identifier)).rowcount
            if not changed:
                raise WorkspaceError("no such annotation")
            result = self._annotation(connection.execute(
                "SELECT * FROM annotations WHERE id = ?", (identifier,)).fetchone())
        return result

    def delete_annotation(self, identifier: str) -> bool:
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
        return self._comparison(self._one("SELECT * FROM comparisons WHERE name = ?",
                                         (_string(name, "comparison name"),)))

    def list_comparisons(self) -> list[dict]:
        return [self._comparison(row) for row in self._all("SELECT * FROM comparisons ORDER BY name")]

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

    def export(self) -> dict:
        """A consistent portable snapshot containing references, not corpus text."""
        with self._transaction(write=False):
            exported = {
                "format": "sol-workspace", "schema_version": SCHEMA_VERSION,
                "corpus_id": self.corpus_id, "provenance": self.provenance,
                "created_at": self.created_at, "exported_at": _now(),
                "state": self.get_state(), "bookmarks": self.list_bookmarks(),
                "history": [self._history(row) for row in self._all(
                    "SELECT * FROM state_history ORDER BY revision DESC")],
                "annotations": self.list_annotations(), "comparisons": self.list_comparisons(),
                "reviews": self.list_reviews(), "relations": self.list_relations(),
            }
            _json_value(exported)
        # Return an independent JSON value, including an independent provenance.
        return _decode(_encode(exported))
