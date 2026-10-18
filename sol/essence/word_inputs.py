"""The word study's CORE/file boundary. File input never imports CORE.

Providers are explicit caller-owned inputs, not authority stored in an artifact.
Their loaded text is private to the computation and never serialized.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
from typing import Callable


MAX_INPUT_BYTES = 64 * 1024 * 1024


class WordStudyError(ValueError):
    """A refusal with a stable machine-readable status and code."""

    def __init__(self, message, *, status="invalid", code="invalid_word_study"):
        super().__init__(message)
        self.status, self.code = status, code


@dataclass(frozen=True)
class CoreProvider:
    """A verified CorpusSnapshot and corpus/within/passages/span scope.

    None selects the whole eligible corpus. A span names one exact record ID
    and half-open plain_text codepoints. Other scopes retain canonical order.
    """

    snapshot: object
    scope: dict | None = None


@dataclass(frozen=True)
class FileProvider:
    """A caller-selected regular UTF-8 file and optional codepoint span.

    None selects the whole file. Newlines and Unicode are not rewritten; the
    binding hashes the original bytes, including a BOM if present.
    """

    path: str | Path
    scope: dict | None = None


@dataclass
class _Loaded:
    provider: str
    binding: dict
    scope: dict
    rows: list[dict]
    exclusions: dict
    verify_current: Callable[[], None]


def _scope(value, provider):
    value = deepcopy(value) if value is not None else {"kind": "corpus" if provider == "core" else "file"}
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise WordStudyError("Scope must be a typed object", code="invalid_scope")
    kind = value["kind"]
    fields = {"corpus": {"kind"}, "file": {"kind"}, "within": {"kind", "path"},
              "passages": {"kind", "ids"}, "span": {"kind", "start", "end"}}
    if provider == "core" and kind == "span":
        fields["span"] = fields["span"] | {"id"}
    allowed = {"corpus", "within", "passages", "span"} if provider == "core" else {"file", "span"}
    if kind not in allowed or set(value) != fields[kind]:
        raise WordStudyError("Scope fields do not match the selected provider", code="invalid_scope")
    if kind == "within":
        path = value["path"]
        if (not isinstance(path, str) or not path.startswith("/") or "\\" in path or len(path) > 512
                or any(part in {".", "..", ""} for part in path.split("/")[1:]) and path != "/"):
            raise WordStudyError("Use an absolute reader path without empty or dot components", code="invalid_scope")
    if kind == "passages":
        ids = value["ids"]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 4096
                or not all(isinstance(item, str) for item in ids) or len(set(ids)) != len(ids)):
            raise WordStudyError("Passage scope needs 1–4096 distinct exact IDs", code="invalid_scope")
    if kind == "span":
        if (type(value["start"]) is not int or type(value["end"]) is not int
                or not 0 <= value["start"] <= value["end"]
                or provider == "core" and not isinstance(value["id"], str)):
            raise WordStudyError("Span needs ordered nonnegative codepoints and an exact CORE ID", code="invalid_scope")
    return value


def _read_file(path, maximum=MAX_INPUT_BYTES):
    """Bounded stable regular-file read, refusing symlinks and special files."""
    def state(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns

    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise WordStudyError("Word input must be a regular file, not a symlink or special file", code="invalid_file")
    if before.st_size > maximum:
        raise WordStudyError(f"Input exceeds {maximum} bytes", code="size_limit")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or state(before) != state(opened):
            raise WordStudyError("File changed while opening", status="stale", code="file_changed")
        raw = stream.read(maximum + 1)
        if state(opened) != state(os.fstat(stream.fileno())) or state(opened) != state(path.lstat()):
            raise WordStudyError("File changed while reading", status="stale", code="file_changed")
    if len(raw) > maximum:
        raise WordStudyError(f"Input exceeds {maximum} bytes", code="size_limit")
    return raw


def _file(provider):
    scope = _scope(provider.scope, "file")
    path = Path(provider.path).expanduser().absolute()
    raw = _read_file(path)
    try:
        text = raw.decode("utf-8")
    except UnicodeError as error:
        raise WordStudyError("Word input must be valid UTF-8", code="invalid_utf8") from error
    binding = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}

    def current():
        try:
            matches = hashlib.sha256(_read_file(path)).hexdigest() == binding["sha256"]
        except (OSError, WordStudyError) as error:
            raise WordStudyError("File changed during the study", status="stale", code="file_changed") from error
        if not matches:
            raise WordStudyError("File changed during the study", status="stale", code="file_changed")

    start, end = (scope["start"], scope["end"]) if scope["kind"] == "span" else (0, len(text))
    if end > len(text):
        raise WordStudyError("Span extends beyond the file", code="invalid_scope")
    row = {"span": [start, end], "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
           "text": text, "masks": []}
    return _Loaded("file", binding, scope, [row], {"by_reason": {}, "masked_tokens": 0}, current)


def _core(provider):
    # This adapter alone imports CORE and the established corpus projection.
    from sol.essence.terms import _binding, _current, _facsimile_spans, _fresh, _selection

    scope = _scope(provider.scope, "core")
    snapshot = _fresh(provider.snapshot)
    records = snapshot.records
    known = {record["id"] for record in records}
    if scope["kind"] in {"passages", "span"}:
        ids = scope["ids"] if scope["kind"] == "passages" else [scope["id"]]
        if any(identifier not in known for identifier in ids):
            raise WordStudyError("Scope names an unknown exact record ID", code="invalid_scope")

    def selected(record):
        if scope["kind"] == "corpus":
            return True
        if scope["kind"] == "within":
            prefix, path = scope["path"].rstrip("/"), record.get("reader_path") or ""
            return path == prefix or path.startswith(prefix + "/")
        return record["id"] in (scope["ids"] if scope["kind"] == "passages" else [scope["id"]])

    if scope["kind"] == "within" and not any(selected(record) for record in records):
        raise WordStudyError("Reader path names no records", code="invalid_scope")
    exclusions = {"by_reason": dict.fromkeys(
        ("scope", "attribution", "record_type", "review", "reader_path"), 0), "masked_tokens": 0}
    rows = []
    for record in records:
        _, reason = _selection(record, None) if selected(record) else (None, "scope")
        if scope["kind"] == "span" and selected(record) and scope["end"] > len(record["plain_text"]):
            raise WordStudyError("Span extends beyond the record", code="invalid_scope")
        if reason:
            exclusions["by_reason"][reason] += 1
            continue
        text = record["plain_text"]
        start, end = (scope["start"], scope["end"]) if scope["kind"] == "span" else (0, len(text))
        rows.append({"id": record["id"], "content_sha256": record["content_sha256"],
                     "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "span": [start, end],
                     "reader_path": record["reader_path"],
                     "sources": [{key: deepcopy(value) for key, value in source.items()
                                  if key in {"pdf_page", "printed_page", "bbox"}} for source in record["sources"]],
                     "attribution": {key: record["attribution"][key] for key in ("author", "role", "status")},
                     "text": text, "masks": _facsimile_spans(record)})
    return _Loaded("core", _binding(snapshot), scope, rows, exclusions, lambda: _current(snapshot))


def load_input(provider):
    """Load one explicit provider; no input is reconstructed from artifact paths."""
    if isinstance(provider, FileProvider):
        return _file(provider)
    if isinstance(provider, CoreProvider):
        try:
            loaded = _core(provider)
        except ValueError as error:
            if isinstance(error, WordStudyError):
                raise
            raise WordStudyError(str(error), status=getattr(error, "status", "invalid"),
                                 code=getattr(error, "code", "invalid_corpus")) from error
        current = loaded.verify_current

        def verify():
            try:
                current()
            except ValueError as error:
                raise WordStudyError(str(error), status=getattr(error, "status", "stale"),
                                     code=getattr(error, "code", "generation_changed")) from error

        loaded.verify_current = verify
        return loaded
    raise WordStudyError("Expected CoreProvider or FileProvider", code="invalid_provider")
