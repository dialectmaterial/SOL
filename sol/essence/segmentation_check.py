"""Private, blind boundary review of the unchanged punctuation-rules-v1.

Review files contain canonical text and belong outside Git. They are local
annotation forms, not sentence-study artifacts, CORE packets or canonical edits.
Gold sentences are supplied by a reviewer, never by the segmenter being measured.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

from sol import core
from sol.essence.sentences import analyze_sentences, segment


MAX_REVIEW_BYTES = 8 * 1024 * 1024
DOCTRINES = ("BEING", "ESSENCE", "CONCEPT")
_FIELDS = {"review_version", "corpus", "generation", "method", "sampling", "reviewer", "passages"}
_ROW_FIELDS = {"id", "doctrine", "type", "sources", "content_sha256", "text_sha256", "text",
               "gold_sentences", "exclude_reason", "comment"}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{label} has missing or unexpected fields")


def _population(snapshot):
    # The existing study verifies its snapshot and owns its eligibility policy.
    # Its predicted sentence counts/boundaries never enter the blind review form.
    study = analyze_sentences(snapshot)
    records = {record["id"]: record for record in snapshot.records}
    groups = {name: [] for name in DOCTRINES}
    for row in study["passages"]:
        record = records[row["id"]]
        if record["plain_text"].strip():
            path = row.get("reader_path")
            parts = path.split("/") if isinstance(path, str) else []
            doctrine = parts[1].upper() if len(parts) > 1 and not parts[0] else None
            if doctrine not in groups:
                raise ValueError("sentence-segmentation sampling requires reader_path under "
                                 "/BEING, /ESSENCE or /CONCEPT")
            groups[doctrine].append(record)
    return study, groups


def prepare_sample(snapshot, *, per_doctrine, seed):
    """Select whole eligible passages reproducibly, without exposing predictions.

    The caller chooses the size and seed explicitly. Equal passage counts by
    doctrine are a stratified pilot, not a book-wide weighted error estimate.
    """
    if type(per_doctrine) is not int or not 1 <= per_doctrine <= 1000:
        raise ValueError("per-doctrine sample size must be an integer from 1 to 1000")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("sample seed must be an integer from 0 to 4294967295")
    study, groups = _population(snapshot)
    selected = []
    for doctrine, records in groups.items():
        if len(records) < per_doctrine:
            raise ValueError(f"{doctrine} has only {len(records)} eligible nonempty passages; "
                             "choose a smaller explicit sample size")
        # A declared hash ranking avoids changes to random.sample across Python
        # releases. UUIDs and the seed are ASCII and the tie-break is explicit.
        ranked = sorted(records, key=lambda row: (_sha(f"{seed}:{row['id']}"), row["id"]))
        selected.extend((record, doctrine) for record in ranked[:per_doctrine])
    passages = []
    for record, doctrine in sorted(selected, key=lambda item: item[0]["order"]):
        text = record["plain_text"]
        passages.append({"id": record["id"], "doctrine": doctrine, "type": record["type"],
                         "sources": deepcopy(record["sources"]), "content_sha256": record["content_sha256"],
                         "text_sha256": _sha(text), "text": text, "gold_sentences": None,
                         "exclude_reason": None, "comment": ""})
    result = {"review_version": 1, **{key: deepcopy(study[key]) for key in ("corpus", "generation", "method")},
              "sampling": {"strategy": "sha256-ranked-passages-per-doctrine-v1", "seed": seed,
                           "per_doctrine": per_doctrine,
                           "population": {name: len(rows) for name, rows in groups.items()}},
              "reviewer": "", "passages": passages}
    core.verify_snapshot_current(snapshot)
    return result


def _gold_spans(text, sentences):
    if not isinstance(sentences, list) or (text.strip() and not sentences):
        raise ValueError("gold_sentences must list every sentence, not only difficult examples")
    spans, cursor = [], 0
    for sentence in sentences:
        if not isinstance(sentence, str) or not sentence or sentence != sentence.strip():
            raise ValueError("each gold sentence must be nonempty with no surrounding whitespace")
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if not text.startswith(sentence, cursor):
            raise ValueError("gold sentences must match the source exactly and in order; do not edit its words")
        spans.append((cursor, cursor + len(sentence)))
        cursor += len(sentence)
    if text[cursor:].strip():
        raise ValueError("gold sentences leave source text unmarked")
    return spans


def _metrics(true_positives, false_splits, misses):
    predicted, gold = true_positives + false_splits, true_positives + misses
    denominator = 2 * true_positives + false_splits + misses
    return {"true_positives": true_positives, "false_splits": false_splits, "misses": misses,
            "predicted_boundaries": predicted, "gold_boundaries": gold,
            "precision": true_positives / predicted if predicted else None,
            "recall": true_positives / gold if gold else None,
            "f1": 2 * true_positives / denominator if denominator else None}


def compare_text(text, gold_sentences):
    """Exact internal boundary scores in Unicode codepoints, never text edits.

    A boundary is the end of a trimmed sentence, including its punctuation and
    closing quotes/brackets. The obligatory final passage end is not scored.
    A displaced boundary counts as one false split and one miss; no fuzzy match.
    """
    if not isinstance(text, str):
        raise ValueError("source text must be a string")
    gold = {end for _, end in _gold_spans(text, gold_sentences)[:-1]}
    predicted = {end for _, end in segment(text)[:-1]}
    false_splits, misses = sorted(predicted - gold), sorted(gold - predicted)
    return {**_metrics(len(gold & predicted), len(false_splits), len(misses)),
            "false_split_offsets": false_splits, "missed_offsets": misses}


def compare_sample(snapshot, sample):
    """Verify the source and compare only fully marked or explicitly excluded rows.

    A complete review is required. Exclusions are accounted for rather than
    silently discarded. The reviewer label is declared attribution, not proof
    of human annotation or independent adjudication.
    """
    _keys(sample, _FIELDS, "Review")
    if type(sample["review_version"]) is not int or sample["review_version"] != 1:
        raise ValueError("unsupported local review version")
    sampling = sample["sampling"]
    _keys(sampling, {"strategy", "seed", "per_doctrine", "population"}, "Sampling")
    if sampling["strategy"] != "sha256-ranked-passages-per-doctrine-v1":
        raise ValueError("unsupported sampling strategy")
    # Reconstruct the blind selection as well as the generation binding. This
    # detects dropped, duplicated, substituted and reordered sample passages.
    expected = prepare_sample(snapshot, per_doctrine=sampling["per_doctrine"], seed=sampling["seed"])
    for key in ("corpus", "generation", "method", "sampling"):
        if sample[key] != expected[key]:
            raise ValueError(f"review {key} differs from the current sample; retain the original source generation")
    if not isinstance(sample["reviewer"], str) or not sample["reviewer"].strip():
        raise ValueError("record a nonempty reviewer label before scoring")
    passages = sample["passages"]
    if not isinstance(passages, list) or len(passages) != len(expected["passages"]):
        raise ValueError("review must retain every sampled passage")
    rows, exclusions = [], []
    for row, original in zip(passages, expected["passages"]):
        _keys(row, _ROW_FIELDS, "Reviewed passage")
        for key in _ROW_FIELDS - {"gold_sentences", "exclude_reason", "comment"}:
            if row[key] != original[key]:
                raise ValueError(f"sampled source {key} changed; do not correct text inside the review file")
        if not isinstance(row["comment"], str):
            raise ValueError("review comments must be strings")
        reason = row["exclude_reason"]
        if reason is not None:
            if not isinstance(reason, str) or not reason.strip() or row["gold_sentences"] is not None:
                raise ValueError("an exclusion needs a reason and null gold_sentences")
            exclusions.append({"id": row["id"], "doctrine": row["doctrine"], "reason": reason})
            continue
        if row["gold_sentences"] is None:
            raise ValueError("review has unmarked passages; mark each one or record an explicit exclusion")
        rows.append({"id": row["id"], "doctrine": row["doctrine"],
                     **compare_text(row["text"], row["gold_sentences"])})
    if not rows:
        raise ValueError("review contains no scored passages")

    def total(own):
        return {"passages": len(own),
                "passages_with_errors": sum(bool(row["false_splits"] or row["misses"]) for row in own),
                **_metrics(*(sum(row[key] for row in own) for key in ("true_positives", "false_splits", "misses")))}

    core.verify_snapshot_current(snapshot)
    return {"review_version": 1, "reviewer": sample["reviewer"],
            **{key: deepcopy(sample[key]) for key in ("corpus", "generation", "method", "sampling")},
            "boundary_unit": "trimmed sentence ends in source codepoints; final passage ends excluded",
            "summary": total(rows),
            "by_doctrine": {name: total([row for row in rows if row["doctrine"] == name]) for name in DOCTRINES},
            "excluded_passages": exclusions, "passages": rows}


def decode_sample(data):
    """Read a bounded local annotation form; source verification occurs on compare."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if not isinstance(raw, bytes) or len(raw) > MAX_REVIEW_BYTES:
        raise ValueError("local segmentation review must be UTF-8 JSON of at most 8 MiB")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate segmentation-review JSON field")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError("segmentation review requires finite JSON values")

    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
        json.dumps(result, allow_nan=False)  # Also reject overflowed finite literals.
    except (UnicodeError, RecursionError) as error:
        raise ValueError("invalid segmentation-review JSON") from error
    _keys(result, _FIELDS, "Review")
    return result


def write_sample(sample, destination):
    """Create a private annotation form outside Git, refusing any existing target."""
    payload = json.dumps(sample, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n"
    return _write_private(payload, destination)


def _write_private(payload, destination):
    """Shared privacy guard for local JSON reviews and plain-text marking forms."""
    destination = Path(destination).expanduser()
    parent = destination.parent.resolve(strict=True)
    # Linked worktrees have a .git file; ordinary checkouts have .git/HEAD.
    # An empty .git sentinel is not a checkout (some sandbox temp roots have one).
    if any((directory / ".git").is_file() or (directory / ".git" / "HEAD").is_file()
           for directory in (parent, *parent.parents)):
        raise ValueError("segmentation samples contain book text; choose a location outside every Git checkout")
    path = parent / destination.name
    if len(payload) > MAX_REVIEW_BYTES:
        raise ValueError("sample exceeds 8 MiB; choose fewer passages")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
    return path
