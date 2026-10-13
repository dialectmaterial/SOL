"""Verified, local source-page requests, independent of workspace and terminal UI.

The canonical corpus remains read-only. A capture binds its record metadata and
generation to a verified private PDF snapshot; rendering never substitutes a
different source file, records testimony, or moves a reading position.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import zlib

from sol.corpus.contract import CorpusError, load_snapshot, verify_snapshot_current
from sol.core.references import resolve_reference


class SourceError(ValueError):
    """An unavailable, changed, or unverified local source must not be displayed."""


_SHA = re.compile(r"[0-9a-f]{64}")
_SETTINGS = {"format": "png", "dpi": 120, "full_page": True}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_json(value)).hexdigest()


def _record_digest(record):
    # Text has its own digest. Everything else, including page locations,
    # attribution, context, and image references in metadata, belongs to this
    # captured inspection; workspace-v2 testimony retains its narrower binding.
    return _digest({key: value for key, value in record.items()
                    if key not in {"markdown", "plain_text"}})


def _xdg(name, fallback):
    value = os.environ.get(name)
    path = Path(value).expanduser() if value else Path.home() / fallback
    if not path.is_absolute():
        raise SourceError(f"{name} must be an absolute directory")
    return path


def source_config_path():
    return _xdg("XDG_CONFIG_HOME", ".config") / "sol" / "sources.json"


def source_cache_path():
    return _xdg("XDG_CACHE_HOME", ".cache") / "sol" / "source"


def _mapping():
    path = source_config_path()
    if path.is_symlink():
        raise SourceError(f"Source mapping must not be a symbolic link: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeError, ValueError) as error:
        raise SourceError(f"Cannot read source mapping {path}: {error}") from error
    if (not isinstance(data, dict) or type(data.get("version")) is not int
            or data["version"] != 1 or not isinstance(data.get("sources"), dict)):
        raise SourceError(f"Unrecognized source mapping {path}; expected version 1 and sources")
    for digest, location in data["sources"].items():
        if (not isinstance(digest, str) or not _SHA.fullmatch(digest)
                or not isinstance(location, str) or not Path(location).is_absolute()):
            raise SourceError(f"Invalid PDF fingerprint/path in source mapping {path}")
    return data["sources"]


def _atomic_bytes(path, payload, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + "-", dir=path.parent)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _mapping_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = path.with_suffix(".lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise SourceError(f"Source mapping is being updated: {lock}; retry after the update finishes") from error
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def _stat_identity(value):
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _verified_copy(source, destination, expected):
    """Hash the same opened bytes that become the renderer's private snapshot."""
    source, destination = Path(source), Path(destination)
    if source.is_symlink():
        # Resolve explicit source symlinks before this operation; cache files are
        # themselves never permitted to redirect to unrelated mutable files.
        raise SourceError(f"Verified PDF snapshot must not be a symbolic link: {source}")
    if not source.is_file():
        raise SourceError(f"Cannot read or snapshot PDF {source}: expected an existing regular PDF file")
    try:
        with source.open("rb") as original, destination.open("xb") as copied:
            before = os.fstat(original.fileno())
            digest = hashlib.sha256()
            for block in iter(lambda: original.read(1024 * 1024), b""):
                digest.update(block)
                copied.write(block)
            copied.flush()
            os.fsync(copied.fileno())
            after = os.fstat(original.fileno())
        if _stat_identity(before) != _stat_identity(after):
            raise SourceError("The PDF changed while being verified; retry with a stable source file")
        if digest.hexdigest() != expected:
            raise SourceError(f"PDF fingerprint mismatch: {source}. Select the original corpus source PDF.")
        destination.chmod(0o400)
    except OSError as error:
        raise SourceError(f"Cannot read or snapshot PDF {source}: {error}") from error


def _verify_file(path, expected):
    if path.is_symlink():
        raise SourceError(f"Verified PDF snapshot must not be a symbolic link: {path}")
    if not path.is_file():
        raise SourceError(f"Cannot read verified PDF snapshot {path}; capture the source again")
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
            after = os.fstat(stream.fileno())
    except OSError as error:
        raise SourceError(f"Cannot read verified PDF snapshot {path}: {error}; capture the source again") from error
    if _stat_identity(before) != _stat_identity(after) or digest.hexdigest() != expected:
        raise SourceError(f"Verified PDF snapshot changed: {path}; capture the source again")


def _cache_directory(directory, corpus):
    path = Path(directory).expanduser().resolve() if directory is not None else source_cache_path().resolve()
    corpus = Path(corpus).resolve()
    if path == corpus or corpus in path.parents:
        raise SourceError("Source cache must be outside the canonical corpus directory")
    return path


def _cache_subdirectory(path, corpus):
    # An existing child symlink must not send cache writes back into the corpus
    # or an unrelated directory after the cache root itself was checked.
    if path.is_symlink():
        raise SourceError(f"Source cache directory must not be a symbolic link: {path}")
    path = _cache_directory(path, corpus)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def _validate_sources(sources, page_count):
    if type(page_count) is not int or page_count < 1:
        raise SourceError("The corpus manifest has no valid PDF page count")
    if not isinstance(sources, list) or not sources:
        raise SourceError("This canonical record has no source pages")
    for item in sources:
        if (not isinstance(item, dict) or type(item.get("pdf_page")) is not int
                or not 1 <= item["pdf_page"] <= page_count):
            raise SourceError("Record source page is outside the declared physical PDF page count")
        if item.get("printed_page") is not None and not isinstance(item["printed_page"], str):
            raise SourceError("Printed page labels must be strings or null")


class SourceService:
    def __init__(self, book, source_pdf=None, cache_dir=None):
        self.book = book
        self.source_pdf = Path(source_pdf).expanduser().resolve() if source_pdf is not None else None
        if book.corpus_directory is None:
            raise SourceError("Source viewing requires a verified canonical corpus; use --corpus DIRECTORY")
        self.cache_dir = _cache_directory(cache_dir, book.corpus_directory)

    def _current(self):
        snapshot = self.book.corpus_snapshot
        if snapshot is None:
            raise SourceError("Source viewing requires a verified canonical corpus; reopen SOL with --corpus DIRECTORY")
        try:
            verify_snapshot_current(snapshot)
        except CorpusError as error:
            raise SourceError(f"The canonical corpus changed; reopen SOL before source viewing: {error}") from error
        return snapshot

    def _source(self):
        source = self.book.corpus_manifest.get("source", {})
        digest = source.get("sha256")
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise SourceError("The canonical corpus has no valid source PDF fingerprint")
        return source

    def _location(self):
        if self.source_pdf is not None:
            return self.source_pdf
        environment = os.environ.get("SOL_SOURCE_PDF")
        if environment:
            return Path(environment).expanduser().resolve()
        source = self._source()
        saved = _mapping().get(source["sha256"])
        if saved:
            return Path(saved).resolve()
        parent = Path(self.book.corpus_directory).resolve().parent
        filename = source.get("filename")
        candidates = []
        if isinstance(filename, str) and Path(filename).name == filename:
            candidates.append(parent / filename)
        candidates.append(parent / "Hegel-SOL.pdf")
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        raise SourceError("Source PDF not found. Supply --source-pdf PATH or remember it with source set-pdf PATH.")

    def _snapshot_pdf(self, path):
        digest = self._source()["sha256"]
        try:
            directory = _cache_subdirectory(self.cache_dir / "pdf", self.book.corpus_directory)
            with tempfile.TemporaryDirectory(prefix=".capture-", dir=directory) as temporary:
                captured = Path(temporary) / "source.pdf"
                _verified_copy(path, captured, digest)
                target = directory / (digest + ".pdf")
                os.replace(captured, target)
            return target
        except OSError as error:
            raise SourceError(f"Cannot create a private verified PDF snapshot in {self.cache_dir}: {error}") from error

    def set_pdf(self, path):
        self._current()
        path = Path(path).expanduser().resolve()
        self._snapshot_pdf(path)
        self._current()
        configuration = source_config_path()
        corpus = Path(self.book.corpus_directory).resolve()
        if configuration.resolve() == corpus or corpus in configuration.resolve().parents:
            raise SourceError("Source mapping must be outside the canonical corpus directory")
        try:
            with _mapping_lock(configuration):
                saved = _mapping()
                saved[self._source()["sha256"]] = str(path)
                _atomic_bytes(configuration, _json({"version": 1, "sources": saved}) + b"\n")
        except OSError as error:
            raise SourceError(f"Cannot remember source PDF in {configuration}: {error}") from error
        self.source_pdf = path
        return path

    def inspect_info(self):
        self._current()
        path = self._location()
        verified = self._snapshot_pdf(path)
        self._current()
        return {**deepcopy(self._source()), "path": str(path), "verified_pdf": str(verified)}

    def capture(self, identifier):
        snapshot = self._current()
        reference = resolve_reference(self.book, identifier)
        record = reference.record
        source = self._source()
        _validate_sources(record.get("sources"), source.get("pdf_pages"))
        path = self._location()
        verified = self._snapshot_pdf(path)
        self._current()
        return {
            "version": 1, "requested_id": reference.requested_id,
            "target_id": reference.target_id, "redirect_chain": list(reference.chain),
            "title": record.get("reader_title") or record.get("title") or record["type"],
            "record_type": record["type"], "document": record["document"],
            "attribution": deepcopy(record["attribution"]),
            "transcription_status": record.get("transcription_status"),
            "content_sha256": record["content_sha256"], "metadata_sha256": _record_digest(record),
            "sources": deepcopy(record["sources"]),
            "source": {**deepcopy(source), "path": str(path), "verified_pdf": str(verified)},
            "corpus": {"id": snapshot.corpus_id, "directory": str(snapshot.corpus_directory),
                       "manifest_sha256": snapshot.manifest_sha256,
                       "index_sha256": snapshot.index_sha256,
                       "index_metadata_sha256": snapshot.index_metadata_sha256},
        }


def _request_current(request):
    try:
        if (not isinstance(request, dict) or type(request.get("version")) is not int
                or request["version"] != 1):
            raise SourceError("Unrecognized source-view request")
        binding = request["corpus"]
        snapshot = load_snapshot(binding["directory"])
        actual = {"id": snapshot.corpus_id, "directory": str(snapshot.corpus_directory),
                  "manifest_sha256": snapshot.manifest_sha256, "index_sha256": snapshot.index_sha256,
                  "index_metadata_sha256": snapshot.index_metadata_sha256}
        if binding != actual:
            raise SourceError("The canonical corpus generation changed; capture this source again after reopening SOL")
        book = type("SourceBook", (), {"canonical_records": {r["id"]: r for r in snapshot.records}})()
        reference = resolve_reference(book, request["requested_id"])
        record = reference.record
        if (reference.target_id != request["target_id"] or list(reference.chain) != request["redirect_chain"]
                or _record_digest(record) != request["metadata_sha256"]
                or record["content_sha256"] != request["content_sha256"]
                or record["sources"] != request["sources"]):
            raise SourceError("The captured record or its page metadata changed; capture this source again")
        source = snapshot.manifest["source"]
        if source["sha256"] != request["source"]["sha256"] or source["pdf_pages"] != request["source"]["pdf_pages"]:
            raise SourceError("The captured PDF source binding changed")
        _validate_sources(request["sources"], source["pdf_pages"])
        return snapshot
    except (KeyError, TypeError, CorpusError, OSError) as error:
        raise SourceError(f"Cannot validate source-view request: {error}; reopen SOL and capture again") from error


def _png_digest(path):
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SourceError("Source-page render is not a PNG")
    offset, seen_header, seen_data, seen_end = 8, False, False, False
    while offset < len(data):
        if offset + 12 > len(data):
            raise SourceError("Source-page PNG is truncated")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise SourceError("Source-page PNG is truncated")
        payload = data[offset + 8:offset + 8 + length]
        if zlib.crc32(kind + payload) & 0xffffffff != struct.unpack(">I", data[end - 4:end])[0]:
            raise SourceError("Source-page PNG failed its integrity check")
        if not seen_header:
            if kind != b"IHDR" or length != 13 or not all(struct.unpack(">II", payload[:8])):
                raise SourceError("Source-page PNG has an invalid image header")
            seen_header = True
        seen_data = seen_data or kind == b"IDAT"
        offset = end
        if kind == b"IEND":
            seen_end = length == 0 and offset == len(data)
            break
    if not (seen_header and seen_data and seen_end):
        raise SourceError("Source-page PNG is incomplete")
    return hashlib.sha256(data).hexdigest()


def render_page(request, page_index, cache_dir=None):
    """Render one exact source-list entry; PNG cache never determines provenance."""
    snapshot = _request_current(request)
    if type(page_index) is not int or not 0 <= page_index < len(request["sources"]):
        raise SourceError("Choose a source page index within this record's captured page list")
    page = request["sources"][page_index]["pdf_page"]
    digest = request["source"]["sha256"]
    pdf = Path(request["source"]["verified_pdf"])
    _verify_file(pdf, digest)
    directory = _cache_directory(cache_dir, snapshot.corpus_directory) / "renders"
    if directory.is_symlink():
        raise SourceError(f"Source cache directory must not be a symbolic link: {directory}")
    program = shutil.which("pdftoppm")
    if not program:
        raise SourceError("Source-page viewing requires Poppler's pdftoppm; install poppler-utils")
    try:
        version = subprocess.run([program, "-v"], capture_output=True, check=True, timeout=10)
        renderer = (version.stdout + version.stderr).decode("utf-8", errors="replace").strip()
        expected = {"version": 1, "source_sha256": digest, "pdf_page": page,
                    "renderer": renderer, "settings": _SETTINGS}
        key = _digest(expected)
        target = directory / (key + ".png")
        metadata = directory / (key + ".json")
        if target.is_file() and metadata.is_file() and not target.is_symlink() and not metadata.is_symlink():
            try:
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                if saved == {**expected, "png_sha256": _png_digest(target)}:
                    _request_current(request)
                    return target
            except (OSError, ValueError, UnicodeError):
                pass  # A damaged or partially replaced artifact must be rerendered.
        directory = _cache_subdirectory(directory, snapshot.corpus_directory)
        with tempfile.TemporaryDirectory(prefix=".page-", dir=directory) as temporary:
            temporary = Path(temporary)
            stable_pdf, prefix = temporary / "source.pdf", temporary / "page"
            _verified_copy(pdf, stable_pdf, digest)
            result = subprocess.run([program, "-f", str(page), "-l", str(page),
                                     "-singlefile", "-png", "-r", str(_SETTINGS["dpi"]),
                                     str(stable_pdf), str(prefix)],
                                    capture_output=True, timeout=60)
            if result.returncode:
                detail = result.stderr.decode("utf-8", errors="replace").strip()[-1000:]
                raise SourceError(f"Poppler could not render physical PDF page {page}: {detail}")
            completed = prefix.with_suffix(".png")
            png_digest = _png_digest(completed)
            _request_current(request)
            completed.chmod(0o600)
            os.replace(completed, target)
            _atomic_bytes(metadata, _json({**expected, "png_sha256": png_digest}) + b"\n")
        return target
    except subprocess.TimeoutExpired as error:
        raise SourceError(f"Source-page renderer timed out for physical PDF page {page}") from error
    except (OSError, subprocess.CalledProcessError) as error:
        raise SourceError(f"Cannot render physical PDF page {page}: {error}") from error
