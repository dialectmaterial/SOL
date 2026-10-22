"""Explicit prose inputs for analysis, with canonical organization kept as metadata.

This is a derived view, never a replacement for canonical Markdown/plain_text.
Only passages[].text is a feature input. The export does not train a model or
interpret Hegel's section tree as a claim about semantic similarity.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from sol import core
from sol.corpus.markdown import commonmark_tokens, tokens_plain_text


_PROSE_TYPES = {"paragraph", "quotation", "list_item"}
_REASONS = ("record_type", "attribution", "generated_text", "review", "empty_text")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def prose_text(markdown: str) -> str:
    """Remove structural headings/images, retaining the same words in running prose.

    CommonMark handles ATX/setext headings even inside lists or quotations. Raw
    HTML headings and image alt labels are also omitted. Code, emphasis, links,
    mathematical superscripts and SOL's existing note-callout semantics remain
    those of the canonical visible-text renderer. No lexical normalization or
    heading-word blacklist is applied.
    """
    return tokens_plain_text(commonmark_tokens(markdown), exclude_headings=True, exclude_images=True)


def _fresh(snapshot):
    if not isinstance(snapshot, core.CorpusSnapshot):
        raise ValueError("Prose input requires a verified canonical CorpusSnapshot")
    fresh = core.load_snapshot(snapshot.corpus_directory, index=snapshot.index_file)
    if any(getattr(fresh, key) != getattr(snapshot, key) for key in (
            "manifest_sha256", "index_sha256", "index_metadata_sha256", "documents")):
        raise ValueError("The corpus generation changed; reload before exporting prose")
    if _json(snapshot.manifest) != _json(fresh.manifest) or _json(snapshot.records) != _json(fresh.records):
        raise ValueError("The in-memory corpus snapshot was modified; reload canonical data")
    if fresh.corpus_id is None:
        raise ValueError("The corpus needs an explicitly initialized permanent identity")
    return fresh


def _ancestry(record, by_id):
    ancestors = []
    parent = record["parent_id"]
    while parent is not None:
        ancestor = by_id[parent]
        ancestors.append({key: ancestor[key] for key in ("id", "type", "title", "label", "path")
                          if key in ancestor})
        parent = ancestor["parent_id"]
    return list(reversed(ancestors))


def export_prose(snapshot) -> dict:
    """Export one checked generation, all eligible Hegel main prose, in source order.

    Eligibility does not depend on a reader path or an inferred doctrine label.
    Parent links, rather than the cached reader view, supply canonical ancestry.
    Metadata is copied so consumers cannot mutate the input snapshot through it.
    """
    fresh = _fresh(snapshot)
    by_id = {record["id"]: record for record in fresh.records}
    counts = dict.fromkeys(_REASONS, 0)
    passages = []
    for record in fresh.records:
        attribution = record["attribution"]
        if record["type"] not in _PROSE_TYPES:
            reason = "record_type"
        elif attribution["author"] != "G. W. F. Hegel" or attribution["role"] != "main_text":
            reason = "attribution"
        elif record.get("generated_text") is True:
            reason = "generated_text"
        elif record.get("transcription_status") in {"needs_review", "needs_visual_review"}:
            reason = "review"
        else:
            text = prose_text(record["markdown"])
            reason = "empty_text" if not text else None
        if reason:
            counts[reason] += 1
            continue
        metadata = {key: deepcopy(record[key]) for key in (
            "type", "parent_id", "order", "content_sha256", "document", "sources", "attribution",
            "title", "label", "heading", "path", "reader_title", "reader_path", "transcription_status",
        ) if key in record}
        metadata["ancestry"] = _ancestry(record, by_id)
        passages.append({"id": record["id"], "text": text, "text_sha256": _sha(text), "metadata": metadata})
    result = {
        "format": "sol.prose-input", "version": 1,
        "corpus": {"id": fresh.corpus_id, "edition_sha256": _sha(_json(fresh.manifest["edition"])),
                   "source": {key: fresh.manifest["source"][key] for key in ("sha256", "pdf_pages")}},
        "generation": {"manifest_sha256": fresh.manifest_sha256, "index_sha256": fresh.index_sha256},
        "method": {"selection": "hegel-main-text-no-pending-flags-v1",
                   "projection": "commonmark-visible-without-headings-or-images-v1",
                   "feature_field": "passages[].text", "normalization": "none",
                   "ancestry": "canonical-parent-chain-root-first", "order": "canonical-corpus-order"},
        "passages": passages,
        "exclusions": {"input_records": len(fresh.records), "excluded_records": sum(counts.values()),
                       "by_reason": counts},
    }
    core.verify_snapshot_current(fresh)
    return result
