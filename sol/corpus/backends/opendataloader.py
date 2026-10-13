"""Run the optional OpenDataLoader SDK locally into a fresh private directory.

This boundary returns the engine's JSON without assigning SOL identifiers or
changing a corpus. The caller owns the disposable output directory and decides
how to normalize, review, or publish an extraction artifact.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
from importlib import import_module, metadata
from io import StringIO
import json
import math
import os
from pathlib import Path
import re
import shutil


SUPPORTED_VERSION = "2.5.13"


class ExtractionError(RuntimeError):
    """An optional engine or its raw output could not be verified."""


def _source_state(pdf: Path) -> tuple[str, tuple[int, ...]]:
    try:
        if pdf.is_symlink() or not pdf.is_file():
            raise ExtractionError("Source PDF must be a regular, non-symlink file")
        digest = hashlib.sha256()
        with pdf.open("rb") as stream:
            started = os.fstat(stream.fileno())
            header = stream.read(1024)
            if b"%PDF-" not in header:
                raise ExtractionError("Source file does not have a PDF header")
            digest.update(header)
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            finished = os.fstat(stream.fileno())
        stat = pdf.stat()
        def state_of(value):
            return (value.st_dev, value.st_ino, value.st_size,
                    value.st_mtime_ns, value.st_ctime_ns)
        state = state_of(stat)
        if state_of(started) != state_of(finished) or state != state_of(finished):
            raise ExtractionError("Source PDF changed while its fingerprint was being read")
        return digest.hexdigest(), state
    except OSError as error:
        raise ExtractionError("Cannot read source PDF") from error


def _reject_constant(value: str):
    raise ExtractionError(f"Non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ExtractionError("Non-finite JSON number")
    return number


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ExtractionError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _raw_document(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ExtractionError("OpenDataLoader did not produce the expected JSON file")
    try:
        document = json.loads(path.read_text(encoding="utf-8"),
                              object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant,
                              parse_float=_finite_float)
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise ExtractionError("Invalid OpenDataLoader JSON output") from error
    # These are the documented root fields, not guessed aliases. Element
    # normalization and coordinate validation belong to SOL's artifact adapter.
    if not isinstance(document, dict):
        raise ExtractionError("OpenDataLoader JSON root must be an object")
    if not isinstance(document.get("file name"), str):
        raise ExtractionError("OpenDataLoader JSON is missing its file name")
    count = document.get("number of pages")
    if type(count) is not int or count < 1:
        raise ExtractionError("OpenDataLoader JSON has an invalid page count")
    if not isinstance(document.get("kids"), list):
        raise ExtractionError("OpenDataLoader JSON is missing its kids array")
    for key in ("author", "title", "creation date", "modification date"):
        if key not in document or (document[key] is not None
                                   and not isinstance(document[key], str)):
            raise ExtractionError(f"OpenDataLoader JSON has invalid metadata: {key}")
    return document


def _pages_option(pages: str | None) -> str | None:
    if pages is None:
        return None
    if not isinstance(pages, str) or not re.fullmatch(
            r"[1-9][0-9]*(?:-[1-9][0-9]*)?(?:,[1-9][0-9]*(?:-[1-9][0-9]*)?)*", pages):
        raise ExtractionError("Pages must be positive 1-based numbers or ranges, e.g. 1,3-5")
    for item in pages.split(","):
        if "-" in item:
            first, last = map(int, item.split("-"))
            if first > last:
                raise ExtractionError("Page ranges must be ascending")
    return pages


def extract_pdf(pdf: Path, output_dir: Path, *, pages: str | None = None) -> dict:
    """Extract raw, local-only JSON with verified source and engine provenance.

    ``output_dir`` must not already exist, even if empty. SDK and Java errors
    never trigger another engine or remote fallback. No persistent cache is used.
    """
    pdf = Path(pdf).absolute()
    output_dir = Path(output_dir).absolute()
    pages = _pages_option(pages)
    before = _source_state(pdf)
    if output_dir.exists() or output_dir.is_symlink():
        raise ExtractionError("Extraction output directory must not already exist")
    if any(parent.is_symlink() for parent in output_dir.parents):
        raise ExtractionError("Extraction output path must not contain symlinks")
    if not output_dir.parent.is_dir():
        raise ExtractionError("Extraction output parent directory must already exist")
    try:
        sdk_version = metadata.version("opendataloader-pdf")
    except metadata.PackageNotFoundError as error:
        raise ExtractionError("OpenDataLoader is optional; install SOL's extraction extra") from error
    if sdk_version != SUPPORTED_VERSION:
        raise ExtractionError(f"Supported OpenDataLoader version is {SUPPORTED_VERSION}; "
                              f"found {sdk_version}")
    try:
        sdk = import_module("opendataloader_pdf")
    except ImportError as error:
        raise ExtractionError("OpenDataLoader is optional; install SOL's extraction extra") from error
    if shutil.which("java") is None:
        raise ExtractionError("OpenDataLoader requires Java 11 or newer on PATH")
    options = {"format": "json", "hybrid": "off", "image_output": "off", "quiet": True}
    if pages is not None:
        options["pages"] = pages
    try:
        output_dir.mkdir(mode=0o700)
    except OSError as error:
        raise ExtractionError("Cannot create a fresh extraction output directory") from error
    failure = None
    # Quiet SDK versions can still print a summary (or PDF content on errors).
    # Keep machine-readable callers clean and do not expose extraction in logs.
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        try:
            sdk.convert(input_path=[str(pdf)], output_dir=str(output_dir), **options)
        except Exception as error:
            # SDK/JVM failures are an external boundary. Even an unexpected SDK
            # exception must not skip the post-extraction source verification.
            failure = error
    if _source_state(pdf) != before:
        raise ExtractionError("Source PDF changed during extraction; discard the output")
    if failure is not None:
        if isinstance(failure, FileNotFoundError):
            message = "OpenDataLoader could not start; check its bundled JAR and Java 11+"
        else:
            message = "OpenDataLoader extraction failed; no alternate or remote engine was used"
        raise ExtractionError(message) from failure
    if output_dir.is_symlink():
        raise ExtractionError("Extraction output directory became a symlink")
    document = _raw_document(output_dir / (pdf.stem + ".json"))
    if document["file name"] != pdf.name:
        raise ExtractionError("OpenDataLoader JSON names a different source PDF")
    return {"source": {"filename": pdf.name, "sha256": before[0],
                       "pdf_pages": document["number of pages"]},
            "backend": {"name": "opendataloader", "version": sdk_version,
                        "options": options},
            "document": document}
