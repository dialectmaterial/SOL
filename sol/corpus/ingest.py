"""Reviewed extraction-to-corpus proof: publish a new copy, never regenerate IDs.

OpenDataLoader supplies physical evidence. A caller-supplied review explicitly
chooses replacement Markdown for existing canonical records; it cannot change
edition, identities, provenance, hierarchy, attribution, or reciprocal notes.
The review label is a declaration, not authenticated authorship or workspace
testimony. This bounded prototype does not create a corpus from scratch.
"""

from __future__ import annotations

from collections import defaultdict
import ctypes
import errno
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

from sol.core import CorpusError, load_snapshot, verify_snapshot_current
from sol.corpus import contract


_GENERATED = {"markdown", "plain_text", "document", "context", "content_sha256"}
_REVIEW_FIELDS = {"review_version", "artifact_sha256", "reviewer", "changes", "exclusions"}


def _metadata(record):
    return {key: value for key, value in record.items() if key not in _GENERATED}


def _fingerprint(data):
    return hashlib.sha256(data).hexdigest()


def _regular_bytes(path):
    """Read stable regular-file bytes without following a final symlink."""
    path = Path(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                             | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise CorpusError(f"Expected a regular file: {path}")
            data = stream.read()
            after = os.fstat(stream.fileno())
        current = path.stat(follow_symlinks=False)
        state = lambda value: (value.st_dev, value.st_ino, value.st_size,
                               value.st_mtime_ns, value.st_ctime_ns)
        if state(before) != state(after) or state(current) != state(after):
            raise CorpusError(f"File changed while reading: {path}")
        return data
    except OSError as error:
        raise CorpusError(f"Cannot read regular file {path}: {error}") from error


def _decode_review(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CorpusError(f"Duplicate review JSON key: {key!r}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise CorpusError(f"Invalid review JSON numeric constant: {value}")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CorpusError(f"Cannot decode review JSON: {error}") from error


def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise CorpusError(f"{label} must be a nonempty string")


def _no_symlink_components(path):
    for part in (path, *path.parents):
        if part.is_symlink():
            raise CorpusError(f"Symbolic-link path components are not permitted: {part}")


def _output_path(path, baseline):
    target = Path(path).expanduser()
    if ".." in target.parts:
        raise CorpusError("Use an explicit ingestion destination without parent traversal")
    target = target.absolute()
    _no_symlink_components(target)
    if "sources" in target.parts:
        raise CorpusError("Read-only sources directories cannot contain ingestion output")
    if target.is_relative_to(baseline):
        raise CorpusError("Ingestion output must not be inside the baseline corpus")
    if target.exists():
        raise CorpusError("Ingestion destination already exists; choose a new directory")
    if not target.parent.is_dir():
        raise CorpusError("Ingestion destination parent must already be a directory")
    return target


def _require_private_destination(path, relative_files=()):
    """Refuse generated private content in Git unless every generated path is ignored."""
    path = Path(path)
    probe = path if path.is_dir() else path.parent
    repository = None
    for ancestor in (probe, *probe.parents):
        marker = ancestor / ".git"
        try:
            if not marker.exists():
                continue
            if marker.is_dir() and next(marker.iterdir(), None) is None:
                # Some filesystem sandboxes expose an empty read-only .git
                # placeholder outside repositories; it cannot track content.
                continue
            repository = ancestor
            break
        except OSError as error:
            raise CorpusError(f"Cannot inspect potential Git metadata: {error}") from error
    if repository is None:
        return
    try:
        found = subprocess.run(["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True, check=False)
        if found.returncode:
            raise CorpusError("Cannot establish the private destination's Git repository")
        root = Path(found.stdout.strip()).resolve()
        relative = path.relative_to(root)
        files = set(relative_files) | {"corpus.json", "index.jsonl", "index.meta.json",
                                      "audit/review-ingestion.json"}
        for filename in sorted(files):
            checked = subprocess.run(["git", "-C", str(root), "check-ignore", "--quiet",
                                      str(relative / filename)],
                                     capture_output=True, text=True, check=False)
            if checked.returncode:
                raise CorpusError(f"Private ingestion files must be Git-ignored: {relative / filename}")
    except (OSError, ValueError) as error:
        raise CorpusError(f"Cannot verify private ingestion destination: {error}") from error


def _document_path(root, relative):
    if (not isinstance(relative, str) or "\\" in relative or not relative.endswith(".md")
            or Path(relative).is_absolute()
            or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise CorpusError(f"Unsafe canonical document path: {relative!r}")
    path = root / relative
    _no_symlink_components(path)
    if not path.is_relative_to(root):
        raise CorpusError(f"Canonical document escapes the corpus: {relative!r}")
    return path


def _asset_files(root):
    assets = root / "assets"
    if assets.is_symlink():
        raise CorpusError("Baseline assets must not be symbolic links")
    if not assets.exists():
        return []
    if not assets.is_dir():
        raise CorpusError("Baseline assets must be a directory")
    result = []
    for path in sorted(assets.rglob("*")):
        if path.is_symlink():
            raise CorpusError(f"Baseline asset is a symbolic link: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise CorpusError(f"Baseline asset is not a regular file: {path}")
        lowered = path.name.lower()
        if (lowered.endswith(".pdf") or ".sqlite3" in lowered
                or lowered.endswith((".sol-workspace.json", ".sol-workspace.md"))):
            raise CorpusError(f"PDFs and personal workspace files are not corpus assets: {path}")
        result.append(path.relative_to(root).as_posix())
    return result


def _write_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _rewrite_document(source_bytes, rows, changed):
    """Replace approved records without reformatting neighboring record bytes."""
    by_id = {row["id"]: row for row in rows}
    replaced = set()
    text = source_bytes.decode("utf-8")
    pattern = re.compile(r'^<!-- sol:[^\r\n]+ -->\r?\n<a id="([0-9a-f-]+)"></a>\r?\n'
                         r'.*?^<!-- /sol -->(?:\r?\n|$)', re.M | re.S)

    def replace(match):
        identifier = match[1]
        if identifier not in changed:
            return match[0]
        if identifier not in by_id or identifier in replaced:
            raise CorpusError("Canonical document and its indexed identities disagree")
        replaced.add(identifier)
        return contract.render_record(_metadata(by_id[identifier]), changed[identifier])

    result = pattern.sub(replace, text)
    if replaced != set(by_id) & set(changed):
        raise CorpusError("Approved record is missing from its canonical Markdown document")
    return result.encode("utf-8")


def _publish_directory_noreplace(stage, target):
    """Atomically publish a complete sibling directory without replacing anything.

    Ordinary rename may replace an existing empty directory. Unsupported kernels
    or filesystems fail closed instead of weakening the no-clobber guarantee.
    """
    stage, target = Path(stage), Path(target)
    if ".." in stage.parts or ".." in target.parts:
        raise CorpusError("Corpus publication paths must not contain parent traversal")
    if sys.platform != "linux":
        raise CorpusError("Atomic no-clobber corpus publication currently requires Linux renameat2")
    if stage.parent != target.parent:
        raise CorpusError("Corpus publication requires a sibling staging directory")
    _no_symlink_components(stage)
    _no_symlink_components(target)
    try:
        rename = ctypes.CDLL(None, use_errno=True).renameat2
    except (OSError, AttributeError) as error:
        raise CorpusError("Atomic no-clobber publication is unavailable; nothing was published") from error
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    try:
        parent = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
        try:
            result = rename(parent, os.fsencode(stage.name), parent, os.fsencode(target.name), 1)
            if result != 0:
                code = ctypes.get_errno()
                if code in {errno.EEXIST, errno.ENOTEMPTY}:
                    raise CorpusError("Ingestion destination already exists; nothing was overwritten")
                if code in {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP}:
                    raise CorpusError("Atomic no-clobber publication is unsupported; nothing was published")
                raise CorpusError(f"Cannot publish reviewed corpus: {os.strerror(code)}")
            try:
                os.fsync(parent)
            except OSError as error:
                raise CorpusError(f"Corpus was published at {target}, but directory sync failed: {error}") from error
        finally:
            os.close(parent)
    except OSError as error:
        raise CorpusError(f"Cannot publish reviewed corpus: {error}") from error


def _sync_staging_directories(stage):
    for directory in [*sorted((path for path in stage.rglob("*") if path.is_dir()),
                              key=lambda path: len(path.parts), reverse=True), stage]:
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _annotated_note_links(markdown):
    """Retain both annotated identities and their human-readable destinations."""
    class Notes(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.links = set()

        def handle_starttag(self, tag, attrs):
            if tag == "sup":
                self.stack.append(dict(attrs).get("data-sol-note"))
            elif tag == "a":
                active = next((identifier for identifier in reversed(self.stack)
                               if identifier is not None), None)
                if active is not None:
                    self.links.add((active, dict(attrs).get("href")))

        def handle_endtag(self, tag):
            if tag == "sup" and self.stack:
                self.stack.pop()

    parser = Notes()
    for token in contract._commonmark_tokens(markdown):
        if token.type in {"html_inline", "html_block"}:
            parser.feed(token.content)
        elif token.type == "inline":
            for child in token.children or []:
                if child.type == "html_inline":
                    parser.feed(child.content)
                elif child.type == "link_open":
                    active = next((identifier for identifier in reversed(parser.stack)
                                   if identifier is not None), None)
                    if active is not None:
                        parser.links.add((active, child.attrGet("href")))
    parser.close()
    return parser.links


def _review_plan(artifact, artifact_sha256, review, snapshot):
    if (not isinstance(review, dict) or set(review) != _REVIEW_FIELDS
            or type(review.get("review_version")) is not int or review["review_version"] != 1):
        raise CorpusError("Review requires the exact version-1 review-copy fields")
    if review["artifact_sha256"] != artifact_sha256:
        raise CorpusError("Review artifact fingerprint does not match the candidate")
    _nonempty(review["reviewer"], "reviewer")
    if not isinstance(review["changes"], list) or not isinstance(review["exclusions"], list):
        raise CorpusError("Review changes and exclusions must be lists")
    source = artifact.get("source") if isinstance(artifact, dict) else None
    if (not isinstance(artifact, dict)
            or type(artifact.get("artifact_version")) is not int or artifact["artifact_version"] != 1
            or not isinstance(source, dict)
            or source.get("sha256") != snapshot.manifest["source"]["sha256"]
            or type(source.get("pdf_pages")) is not int
            or source["pdf_pages"] != snapshot.manifest["source"]["pdf_pages"]):
        raise CorpusError("Candidate must reference the baseline's exact source fingerprint and page count")
    if not isinstance(artifact.get("elements"), list):
        raise CorpusError("Candidate elements must be a list")
    elements = {}
    for element in artifact["elements"]:
        if not isinstance(element, dict):
            raise CorpusError("Candidate elements must be objects")
        selector = element.get("selector")
        if not isinstance(selector, str) or not selector.startswith("/") or selector in elements:
            raise CorpusError("Candidate selectors must be distinct JSON pointers")
        page = element.get("pdf_page")
        if type(page) is not int or not 1 <= page <= source["pdf_pages"]:
            raise CorpusError(f"Candidate element has an invalid PDF page: {selector}")
        elements[selector] = element
    by_id = {record["id"]: record for record in snapshot.records}
    changed = {}
    claimed = set()

    def claim(selector):
        if not isinstance(selector, str) or selector not in elements:
            raise CorpusError(f"Review cites an unknown selector: {selector!r}")
        if selector in claimed:
            raise CorpusError(f"Candidate selector is assigned or excluded more than once: {selector}")
        claimed.add(selector)

    for change in review["changes"]:
        if not isinstance(change, dict) or set(change) != {"record_id", "selectors", "markdown", "reason"}:
            raise CorpusError("Each change requires record_id, selectors, markdown, and reason only")
        identifier = change["record_id"]
        if not isinstance(identifier, str) or identifier not in by_id:
            raise CorpusError(f"Review references an unknown canonical record ID: {identifier!r}")
        if identifier in changed:
            raise CorpusError("Each canonical record may have only one approved change")
        _nonempty(change["markdown"], "approved Markdown")
        _nonempty(change["reason"], "change reason")
        selectors = change["selectors"]
        if not isinstance(selectors, list) or not selectors:
            raise CorpusError("Each change must map at least one complete candidate selector")
        pages = {reference["pdf_page"] for reference in by_id[identifier]["sources"]}
        for selector in selectors:
            claim(selector)
            if elements[selector]["pdf_page"] not in pages:
                raise CorpusError("Candidate PDF page is not among the target record's source references")
        # Serialization rejects marker injection and heading-type mismatches.
        canonical = contract.parse_document(contract.render_record(_metadata(by_id[identifier]),
                                                                  change["markdown"]))[0]
        # This proof freezes note metadata; removing a visible callout would leave
        # registered links whose scholarly attachment no longer matches the text.
        old_notes = contract._note_annotations(contract._commonmark_tokens(by_id[identifier]["markdown"]))
        new_notes = contract._note_annotations(contract._commonmark_tokens(canonical["markdown"]))
        if old_notes != new_notes:
            raise CorpusError("Approved Markdown must retain the existing annotated note target set")
        if _annotated_note_links(by_id[identifier]["markdown"]) != _annotated_note_links(canonical["markdown"]):
            raise CorpusError("Approved Markdown must retain the existing annotated note link destinations")
        changed[identifier] = canonical["markdown"]
    for exclusion in review["exclusions"]:
        if not isinstance(exclusion, dict) or set(exclusion) != {"selector", "reason"}:
            raise CorpusError("Each exclusion requires selector and reason only")
        _nonempty(exclusion["reason"], "exclusion reason")
        claim(exclusion["selector"])
    missing = set(elements) - claimed
    if missing:
        raise CorpusError(f"Candidate elements lack an explicit mapping or exclusion: {sorted(missing)}")
    return changed


def ingest_reviewed(candidate_path, review_path, baseline_dir, output_dir):
    """Validate a complete review and publish a new ID-preserving corpus copy.

    Only approved Markdown changes. The existing corpus remains read-only; this
    operation never opens its PDF or any personal workspace database. Only the
    declared Markdown and assets subtree are copied; other local adjuncts are
    deliberately not carried forward. Destination parents must already exist.
    """
    # Normalization remains a replaceable extraction-layer dependency.
    from sol.corpus.extraction import read_artifact

    candidate_path = Path(candidate_path).expanduser().absolute()
    review_path = Path(review_path).expanduser().absolute()
    _no_symlink_components(candidate_path)
    _no_symlink_components(review_path)
    artifact, artifact_sha256 = read_artifact(candidate_path)
    if _fingerprint(_regular_bytes(candidate_path)) != artifact_sha256:
        raise CorpusError("Candidate changed while loading; review a stable artifact")
    review_bytes = _regular_bytes(review_path)
    review_sha256 = _fingerprint(review_bytes)
    review = _decode_review(review_bytes)
    baseline = Path(baseline_dir).expanduser().absolute()
    _no_symlink_components(baseline)
    snapshot = load_snapshot(baseline)
    baseline = snapshot.corpus_directory
    if snapshot.corpus_id is None:
        raise CorpusError("Baseline requires an explicitly initialized corpus ID before review-copy ingestion")
    target = _output_path(output_dir, baseline)
    changed = _review_plan(artifact, artifact_sha256, review, snapshot)
    documents = snapshot.manifest["documents"]
    document_paths = {name: _document_path(baseline, name) for name in documents}
    assets = [name for name in _asset_files(baseline) if name not in documents]
    relative_files = [*documents, *assets]
    _require_private_destination(target, relative_files)
    manifest_path = baseline / contract.MANIFEST_FILENAME
    _no_symlink_components(manifest_path)
    manifest_bytes = _regular_bytes(manifest_path)
    if _fingerprint(manifest_bytes) != snapshot.manifest_sha256:
        raise CorpusError("Baseline manifest changed while preparing ingestion")
    grouped = defaultdict(list)
    for record in snapshot.records:
        grouped[record["document"]].append(record)
    asset_digests = {}
    stage = Path(tempfile.mkdtemp(prefix=target.name + ".building-", dir=target.parent))
    stage_identity = stage.stat().st_dev, stage.stat().st_ino
    try:
        stage.chmod(0o700)
        _require_private_destination(stage, relative_files)
        _write_private(stage / contract.MANIFEST_FILENAME, manifest_bytes)
        for document, source_path in document_paths.items():
            source_bytes = _regular_bytes(source_path)
            if _fingerprint(source_bytes) != snapshot.documents[document]:
                raise CorpusError(f"Baseline Markdown changed: {document}")
            rows = grouped[document]
            if any(row["id"] in changed for row in rows):
                payload = _rewrite_document(source_bytes, rows, changed)
            else:
                payload = source_bytes
            _write_private(stage / document, payload)
        for relative in assets:
            payload = _regular_bytes(baseline / relative)
            asset_digests[relative] = _fingerprint(payload)
            _write_private(stage / relative, payload)
        audit = {
            "review_version": 1, "artifact_sha256": artifact_sha256,
            "review_sha256": review_sha256, "reviewer": review["reviewer"],
            "reviewer_status": "caller_declared_not_authenticated",
            "baseline": {"corpus_id": snapshot.corpus_id,
                         "manifest_sha256": snapshot.manifest_sha256,
                         "index_sha256": snapshot.index_sha256},
            "changes": [{key: value for key, value in item.items() if key != "markdown"}
                        for item in review["changes"]],
            "exclusions": review["exclusions"],
            "counts": {"changed_records": len(changed),
                       "assigned_elements": sum(len(item["selectors"]) for item in review["changes"]),
                       "excluded_elements": len(review["exclusions"])},
        }
        _write_private(stage / "audit" / "review-ingestion.json",
                       (json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))
        contract.reindex(stage)
        reviewed = load_snapshot(stage)
        if reviewed.manifest != snapshot.manifest:
            raise CorpusError("Reviewed copy changed canonical manifest metadata")
        if [record["id"] for record in reviewed.records] != [record["id"] for record in snapshot.records]:
            raise CorpusError("Reviewed copy changed canonical identities or source order")
        for before, after in zip(snapshot.records, reviewed.records):
            if _metadata(before) != _metadata(after):
                raise CorpusError("Reviewed copy changed canonical record metadata")
            if after["markdown"] != changed.get(before["id"], before["markdown"]):
                raise CorpusError("Reviewed copy changed unapproved canonical Markdown")
        for relative, digest in asset_digests.items():
            if _fingerprint(_regular_bytes(baseline / relative)) != digest:
                raise CorpusError(f"Baseline asset changed during ingestion: {relative}")
        if [name for name in _asset_files(baseline) if name not in documents] != assets:
            raise CorpusError("Baseline asset inventory changed during ingestion")
        _sync_staging_directories(stage)
        verify_snapshot_current(snapshot)
        _no_symlink_components(candidate_path)
        _no_symlink_components(review_path)
        if (_fingerprint(_regular_bytes(candidate_path)) != artifact_sha256
                or _fingerprint(_regular_bytes(review_path)) != review_sha256):
            raise CorpusError("Candidate or review changed during ingestion; nothing was published")
        _no_symlink_components(target)
        _publish_directory_noreplace(stage, target)
        return {"corpus": str(target), "corpus_id": snapshot.corpus_id,
                "records": len(reviewed.records), **audit["counts"],
                "artifact_sha256": artifact_sha256, "review_sha256": review_sha256}
    finally:
        # Only this operation's private staging directory is removed. Publication
        # moves it, so failures never remove or overwrite the requested target.
        try:
            current = stage.lstat()
        except FileNotFoundError:
            pass
        else:
            if (stat.S_ISDIR(current.st_mode)
                    and (current.st_dev, current.st_ino) == stage_identity):
                shutil.rmtree(stage)
