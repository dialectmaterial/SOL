"""Shared verified CORE selection and provenance for ESSENCE studies."""
import hashlib
import posixpath
import re

from sol import core
from sol.essence.essence_as_reflection_within_itself.validation import TermExperimentError, _json, _json_value

_DOCTRINES = ("BEING", "ESSENCE", "CONCEPT")
_TYPES = {"paragraph", "quotation", "list_item"}


def _fresh(snapshot):
    if not isinstance(snapshot, core.CorpusSnapshot):
        raise TermExperimentError("A verified canonical CorpusSnapshot is required", code="unverified_snapshot")
    try:
        fresh = core.load_snapshot(snapshot.corpus_directory, index=snapshot.index_file)
    except core.CorpusError as error:
        raise TermExperimentError("The selected corpus generation is no longer valid; reopen after reindexing",
                                  status="stale", code="generation_changed") from error
    if (fresh.manifest_sha256 != snapshot.manifest_sha256 or fresh.index_sha256 != snapshot.index_sha256
            or fresh.index_metadata_sha256 != snapshot.index_metadata_sha256 or fresh.documents != snapshot.documents):
        raise TermExperimentError("The corpus generation changed; reopen before studying it",
                                  status="stale", code="generation_changed")
    if (_json(_json_value(snapshot.manifest)) != _json(fresh.manifest)
            or _json(_json_value(snapshot.records)) != _json(fresh.records)):
        raise TermExperimentError("The in-memory corpus snapshot was modified; reload canonical data",
                                  status="stale", code="snapshot_modified")
    if fresh.corpus_id is None:
        raise TermExperimentError("The corpus needs an explicitly initialized permanent identity",
                                  code="missing_corpus_identity")
    return fresh


def _current(snapshot):
    try:
        core.verify_snapshot_current(snapshot)
    except core.CorpusError as error:
        raise TermExperimentError("The corpus changed during the study; reopen and retry",
                                  status="stale", code="generation_changed") from error


def _binding(snapshot):
    return {
        "corpus": {"id": snapshot.corpus_id,
                   "edition_sha256": hashlib.sha256(_json(snapshot.manifest["edition"]).encode("utf-8")).hexdigest(),
                   "source": {key: snapshot.manifest["source"][key] for key in ("sha256", "pdf_pages")}},
        "generation": {"manifest_sha256": snapshot.manifest_sha256, "index_sha256": snapshot.index_sha256},
    }


def _reader_doctrine(value):
    if not isinstance(value, str) or not value.startswith("/") or "\\" in value:
        return None
    parts = value.split("/")[1:]
    if (len(parts) < 2 or parts[0] not in _DOCTRINES or not parts[-1].endswith(".txt")
            or any(part in {"", ".", ".."} for part in parts)
            or any(part.endswith(".txt") for part in parts[:-1])):
        return None
    return parts[0]


def _facsimile_spans(record):
    """Mask only exact trailing labels produced by this corpus's converter.

    This is not Markdown parsing: ordinary images, inline labels, and earlier
    identical prose are retained. Unsupported image layouts are not guessed at.
    """
    markdown = record["markdown"].rstrip()
    plain = record["plain_text"]
    end = len(plain)
    spans = []
    source_labels = {(str(source["printed_page"]), f"{record['id']}-{source['pdf_page']}.png")
                     for source in record["sources"]}
    while True:
        image = re.search(r"(?:^|\n)\!\[(Source facsimile, printed page ([^\]\r\n]*))\]\(([^)\r\n]*)\)$", markdown)
        if not image:
            break
        if (image[2], posixpath.basename(image[3])) not in source_labels:
            break
        end = len(plain[:end].rstrip())
        label = image[1]
        start = end - len(label)
        if start < 0 or plain[start:end] != label or (start > 0 and plain[start - 1] != "\n"):
            break
        spans.append((start, end))
        end = start
        markdown = markdown[:image.start()].rstrip()
    return spans


def _selection(record, doctrine):
    attribution = record["attribution"]
    if attribution["author"] != "G. W. F. Hegel" or attribution["role"] != "main_text":
        return None, "attribution"
    if record["type"] not in _TYPES or record.get("generated_text") is True:
        return None, "record_type"
    if record.get("transcription_status") in {"needs_review", "needs_visual_review"}:
        return None, "review"
    name = _reader_doctrine(record.get("reader_path"))
    if name is None:
        return None, "reader_path"
    if doctrine is not None and name != doctrine:
        return None, "doctrine"
    return name, None
