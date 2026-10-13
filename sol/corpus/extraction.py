"""Private physical extraction artifacts, separate from canonical SOL records.

Selectors describe positions in one immutable candidate, not passage identities.
Raw typography and nesting remain available for human review. No Markdown,
printed-page labels, attribution, UUIDs, or logical hierarchy are inferred here.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import tempfile

from sol.corpus.contract import CorpusError


ARTIFACT_VERSION = 1
_CHILDREN = ("kids", "list items", "rows", "cells")
_NORMALIZATION = {
    "backend_schema": "opendataloader-json",
    "coordinate_status": "unconverted",
    "semantic_review_required": True,
    "element_selector_kind": "json_pointer",
    "metadata_author_is_attribution": False,
}


class ExtractionError(CorpusError):
    """Extraction evidence cannot be validated or privately published."""


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ExtractionError(f"Duplicate JSON field: {key!r}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ExtractionError(f"Non-finite JSON number: {value}")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ExtractionError("Non-finite JSON number")
    return result


def _decode(data):
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant, parse_float=_finite_float)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ExtractionError(f"Invalid extraction JSON: {error}") from error


def _json_copy(value, depth=0):
    # Reject non-JSON objects and coerced dictionary keys rather than silently
    # altering extractor evidence. Bound recursion before walking child arrays.
    if depth > 128:
        raise ExtractionError("Extraction JSON nesting exceeds 128 levels")
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise ExtractionError("Extraction strings must be valid UTF-8") from error
        return value
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, list):
        return [_json_copy(item, depth + 1) for item in value]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {_json_copy(key, depth + 1): _json_copy(item, depth + 1) for key, item in value.items()}
    raise ExtractionError("Extraction evidence must contain only finite JSON values")


def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ExtractionError(f"{label} must be a nonempty string")


def _finite_coordinate(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def make_artifact(result):
    """Normalize physical evidence without modifying its content or meaning."""
    if not isinstance(result, dict):
        raise ExtractionError("Extraction result must be an object")
    source = _json_copy(result.get("source"))
    backend = _json_copy(result.get("backend"))
    document = _json_copy(result.get("document"))
    if not isinstance(source, dict) or set(source) != {"filename", "sha256", "pdf_pages"}:
        raise ExtractionError("Source requires filename, sha256, and pdf_pages")
    filename = source["filename"]
    _nonempty(filename, "Source filename")
    if filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise ExtractionError("Source filename must be a basename")
    if not isinstance(source["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
        raise ExtractionError("Source fingerprint must be a lowercase SHA-256")
    pages = source["pdf_pages"]
    if type(pages) is not int or pages < 1:
        raise ExtractionError("Source PDF page count must be a positive integer")
    if not isinstance(backend, dict) or backend.get("name") != "opendataloader":
        raise ExtractionError("This artifact adapter requires the OpenDataLoader backend")
    _nonempty(backend.get("version"), "Backend version")
    if not isinstance(backend.get("options"), dict):
        raise ExtractionError("Backend options must be an object")
    if not isinstance(document, dict) or document.get("file name") != filename:
        raise ExtractionError("Raw JSON must name the supplied source PDF")
    if type(document.get("number of pages")) is not int or document["number of pages"] != pages:
        raise ExtractionError("Raw JSON page count must match the source declaration")
    if not isinstance(document.get("kids"), list):
        raise ExtractionError("Raw JSON requires a kids array")
    for key in ("author", "title", "creation date", "modification date"):
        if key not in document or (document[key] is not None and not isinstance(document[key], str)):
            raise ExtractionError(f"Raw JSON has invalid document metadata: {key}")
    elements = []

    def walk(node, selector, parent_kind=None, collection=None):
        if not isinstance(node, dict):
            raise ExtractionError(f"Physical element must be an object: {selector}")
        kind = node.get("type")
        _nonempty(kind, f"Element type at {selector}")
        # The vendor's table-row schema contains cells but no page/bbox. It is
        # a structural wrapper; the table and its cells carry physical evidence.
        if kind == "table row":
            if (parent_kind != "table" or collection != "rows"
                    or type(node.get("row number")) is not int or node["row number"] < 1
                    or not isinstance(node.get("cells"), list)):
                raise ExtractionError(f"Invalid structural table row: {selector}")
            if any(field in node for field in ("page number", "bounding box", "content", "kids", "list items", "rows")):
                raise ExtractionError(f"Unsupported physical evidence on a structural table row: {selector}")
        else:
            page = node.get("page number")
            if type(page) is not int or not 1 <= page <= pages:
                raise ExtractionError(f"Element has an invalid 1-based PDF page: {selector}")
            box = node.get("bounding box")
            if (not isinstance(box, list) or len(box) != 4
                    or any(not _finite_coordinate(item) for item in box)
                    or box[0] > box[2] or box[1] > box[3]):
                raise ExtractionError(f"Element has an invalid native bounding box: {selector}")
            identifier = node.get("id")
            if identifier is not None and type(identifier) is not int:
                raise ExtractionError(f"Backend element ID must be an integer: {selector}")
            content = node.get("content")
            if content is not None and not isinstance(content, str):
                raise ExtractionError(f"Element content must be a string: {selector}")
            elements.append({
                "selector": selector, "type": kind, "pdf_page": page,
                "backend_id": identifier,
                "bounding_box": {
                    "coordinate_space": "opendataloader_pdf_points_bottom_left_unverified",
                    "values": box,
                },
                "content": content,
            })
        for field in _CHILDREN:
            if field not in node:
                continue
            if not isinstance(node[field], list):
                raise ExtractionError(f"Physical child collection must be an array: {selector}/{field}")
            escaped = field.replace("~", "~0").replace("/", "~1")
            for index, child in enumerate(node[field]):
                walk(child, f"{selector}/{escaped}/{index}", kind, field)

    for index, node in enumerate(document["kids"]):
        walk(node, f"/kids/{index}")
    return {"artifact_version": ARTIFACT_VERSION, "source": source, "backend": backend,
            "raw_document": document, "elements": elements,
            "normalization": dict(_NORMALIZATION)}


def _validate_artifact(artifact):
    if (not isinstance(artifact, dict) or type(artifact.get("artifact_version")) is not int
            or artifact["artifact_version"] != ARTIFACT_VERSION):
        raise ExtractionError("Unsupported extraction artifact version")
    expected = make_artifact({"source": artifact.get("source"), "backend": artifact.get("backend"),
                              "document": artifact.get("raw_document")})
    # Validate the whole JSON value as well: Python equality treats True == 1.
    actual = _json_copy(artifact)
    if json.dumps(actual, sort_keys=True, ensure_ascii=False) != json.dumps(expected, sort_keys=True, ensure_ascii=False):
        raise ExtractionError("Artifact selectors or derived evidence disagree with its raw document")
    return expected


def _no_symlinks(path):
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ExtractionError(f"Symbolic-link path components are not permitted: {item}")


def _absolute(path):
    path = Path(path).expanduser()
    if ".." in path.parts:
        raise ExtractionError("Use an explicit path without parent traversal")
    return path.absolute()


def _regular_bytes(path):
    path = _absolute(path)
    _no_symlinks(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                             | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            started = os.fstat(stream.fileno())
            if not stat.S_ISREG(started.st_mode):
                raise ExtractionError("Extraction input must be a regular file")
            data = stream.read()
            finished = os.fstat(stream.fileno())
        current = path.stat(follow_symlinks=False)
        state = lambda value: (value.st_dev, value.st_ino, value.st_size,
                               value.st_mtime_ns, value.st_ctime_ns)
        if state(started) != state(finished) or state(current) != state(finished):
            raise ExtractionError("Extraction input changed while reading")
        return data
    except OSError as error:
        raise ExtractionError(f"Cannot read extraction input: {error}") from error


def read_artifact(path):
    """Validate an artifact and return it with the SHA-256 of its exact bytes."""
    data = _regular_bytes(path)
    return _validate_artifact(_decode(data)), _digest(data)


def _require_ignored(path):
    existing = next((item for item in (path.parent, *path.parent.parents) if item.is_dir()), None)
    if existing is None:
        raise ExtractionError("Extraction destination has no existing parent directory")
    def git_marker(ancestor):
        marker = ancestor / ".git"
        if not marker.exists():
            return False
        # Some restricted hosts expose empty metadata placeholders. An empty
        # directory cannot be a Git repository; every other marker fails closed
        # unless Git can verify it. Inaccessible markers are not ignored.
        try:
            return not marker.is_dir() or any(marker.iterdir())
        except OSError as error:
            raise ExtractionError("Cannot inspect destination repository metadata") from error

    repository = next((item for item in (existing, *existing.parents) if git_marker(item)), None)
    if repository is None:
        return
    try:
        found = subprocess.run(["git", "-C", str(existing), "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True, check=False)
        if found.returncode:
            raise ExtractionError("Cannot establish the extraction destination's Git repository")
        root = Path(found.stdout.strip()).resolve()
        relative = path.relative_to(root)
        checked = subprocess.run(["git", "-C", str(root), "check-ignore", "--quiet", "--", str(relative)],
                                 capture_output=True, text=True, check=False)
        if checked.returncode:
            raise ExtractionError(f"Private extraction files must be Git-ignored: {relative}")
    except (OSError, ValueError) as error:
        raise ExtractionError(f"Cannot verify private extraction destination: {error}") from error


def _destination(path):
    path = _absolute(path)
    _no_symlinks(path)
    if "sources" in path.parts:
        raise ExtractionError("Read-only sources directories cannot contain extraction output")
    if path.exists():
        raise ExtractionError("Extraction destination already exists; choose a new file")
    for parent in path.parents:
        if parent.exists() and not parent.is_dir():
            raise ExtractionError("Extraction destination parent is not a directory")
    _require_ignored(path)
    return path


def _private_parents(path):
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for item in reversed(missing):
        item.mkdir(mode=0o700)


def write_artifact(artifact, path):
    """Publish private UTF-8 JSON exclusively; never overwrite another file."""
    artifact = _validate_artifact(artifact)
    target = _destination(path)
    data = (json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            + "\n").encode("utf-8")
    temporary = target.with_name(target.name + ".building-" + secrets.token_hex(8))
    _require_ignored(temporary)
    created = False
    try:
        _private_parents(target)
        _no_symlinks(target)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | getattr(os, "O_NOFOLLOW", 0), 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _no_symlinks(target)
        os.link(temporary, target, follow_symlinks=False)
        parent = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
        try:
            try:
                os.fsync(parent)
            except OSError as error:
                raise ExtractionError(f"Artifact was published at {target}, but directory sync failed") from error
        finally:
            os.close(parent)
        return _digest(data)
    except OSError as error:
        raise ExtractionError(f"Cannot publish extraction artifact without overwriting: {error}") from error
    finally:
        if created:
            temporary.unlink()


def _summary(artifact, output, digest):
    return {"artifact": str(_absolute(output)), "artifact_sha256": digest,
            "source": artifact["source"], "backend": artifact["backend"],
            "elements": len(artifact["elements"]), "status": "unreviewed_candidate"}


def extract_candidate(pdf, output, *, pages=None):
    """Run the optional, pinned local engine only when explicitly requested."""
    _destination(output)  # Fail before running the engine for unsafe destinations.
    pdf = _absolute(pdf)
    _no_symlinks(pdf)
    from sol.corpus.backends.opendataloader import ExtractionError as BackendError, extract_pdf

    try:
        with tempfile.TemporaryDirectory(prefix="sol-local-extraction-") as scratch:
            result = extract_pdf(pdf, Path(scratch) / "raw", pages=pages)
            result["backend"]["origin"] = "sol_local_execution"
            artifact = make_artifact(result)
            digest = write_artifact(artifact, output)
    except BackendError as error:
        raise ExtractionError(str(error)) from error
    return _summary(artifact, output, digest)


def normalize_candidate(raw_json, pdf, output, *, backend_version):
    """Wrap caller-supplied raw JSON without importing the extraction SDK.

    The PDF is fingerprinted, but the declared engine/version and the relation
    between those bytes and external JSON are not authenticated by this command.
    """
    _destination(output)
    _nonempty(backend_version, "Declared external backend version")
    from sol.corpus.backends.opendataloader import ExtractionError as BackendError, _source_state

    pdf = _absolute(pdf)
    _no_symlinks(pdf)
    raw_bytes = _regular_bytes(raw_json)
    document = _decode(raw_bytes)
    try:
        before = _source_state(pdf)
        artifact = make_artifact({
            "source": {"filename": pdf.name, "sha256": before[0],
                       "pdf_pages": document.get("number of pages") if isinstance(document, dict) else None},
            "backend": {"name": "opendataloader", "version": backend_version, "options": {},
                        "origin": "external_json_declared", "raw_input_sha256": _digest(raw_bytes)},
            "document": document,
        })
        if _source_state(pdf) != before or _regular_bytes(raw_json) != raw_bytes:
            raise ExtractionError("Source PDF or raw JSON changed during normalization")
        digest = write_artifact(artifact, output)
    except BackendError as error:
        raise ExtractionError(str(error)) from error
    return _summary(artifact, output, digest)
