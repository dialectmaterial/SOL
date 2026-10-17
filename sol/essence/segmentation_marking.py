"""Blind text-editor forms over existing, private segmentation-review samples.

Only inserted LF characters and the designated exclusion line are editable.
Canonical source whitespace and Unicode are never normalized or replaced.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from sol import core
from sol.essence.segmentation_check import MAX_REVIEW_BYTES, _write_private, prepare_sample


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unmarked(snapshot, sample):
    sampling = sample.get("sampling") if isinstance(sample, dict) else None
    if not isinstance(sampling, dict):
        raise ValueError("use the original unmarked segmentation-sample JSON")
    expected = prepare_sample(snapshot, per_doctrine=sampling.get("per_doctrine"), seed=sampling.get("seed"))
    if _canonical(sample) != _canonical(expected):
        raise ValueError("sample changed or already marked; use the original unmarked segmentation-sample JSON")


def _intro(sample):
    fingerprint = hashlib.sha256(_canonical(sample).encode("utf-8")).hexdigest()
    return ("SOL sentence marking form v1\n"
            f"Sample SHA256: {fingerprint}\n"
            "Add Enter (LF) after each sentence inside TEXT; KEEP every original space and character.\n"
            "Use soft wrap, not reformatting. Do not trim spaces, correct words or edit headings.\n"
            "Original source newlines are NOT marks; add another Enter there to mark a boundary.\n"
            "No added break means one whole sentence. Final passage ends need no mark.\n"
            "If uncertain, fill EXCLUDE with a reason; keep that passage's text intact.\n\n")


def _heading(number, row):
    return f"PASSAGE {number} | {row['doctrine']} | {row['id']}\n"


def _end(row):
    return f"\nEND PASSAGE {row['id']}\n\n"


def export_marking_form(snapshot, sample):
    """Render unsplit source blocks, never predicted sentences or counts."""
    _unmarked(snapshot, sample)
    blocks = [_intro(sample)]
    for number, row in enumerate(sample["passages"], 1):
        if _end(row) in "\n" + row["text"] + "\n":
            raise ValueError(f"passage {number} ({row['id']}) contains a reserved form delimiter")
        blocks.append(_heading(number, row) + "EXCLUDE: \nTEXT\n" + row["text"] + _end(row))
    form = "".join(blocks) + "END OF FORM\n"
    decode_marking_form(form)  # Apply the same UTF-8/size limit before writing.
    return form


def decode_marking_form(data):
    """Decode without universal-newline conversion or Unicode normalization."""
    try:
        raw = data.encode("utf-8") if isinstance(data, str) else data
        if not isinstance(raw, bytes) or len(raw) > MAX_REVIEW_BYTES:
            raise ValueError("marking form must be UTF-8 text of at most 8 MiB")
        return raw.decode("utf-8")
    except UnicodeError as error:
        raise ValueError("marking form must be UTF-8 text") from error


def write_marking_form(form, destination):
    return _write_private(decode_marking_form(form).encode("utf-8"), destination)


def _place(form, offset):
    line = form.count("\n", 0, offset) + 1
    column = offset - form.rfind("\n", 0, offset)
    return f"form line {line}, column {column}"


def _expect(form, offset, literal, label):
    if not form.startswith(literal, offset):
        common = 0
        for left, right in zip(form[offset:offset + len(literal)], literal):
            if left != right:
                break
            common += 1
        raise ValueError(f"{label} changed or missing at {_place(form, offset + common)}")
    return offset + len(literal)


def _sentences(source, body, *, form, body_start, label):
    """Match source as-is, recording only LF characters absent from the source.

    Consume an original newline before considering inserted ones at that place.
    Thus an existing newline never becomes a sentence mark just by exporting.
    """
    source_offset, start, sentences = 0, 0, []
    for position, character in enumerate(body):
        if source_offset < len(source) and character == source[source_offset]:
            source_offset += 1
        elif character == "\n":
            sentence = source[start:source_offset].strip()
            if sentence:
                sentences.append(sentence)
            start = source_offset
        else:
            raise ValueError(f"{label}: source mismatch at codepoint {source_offset + 1} "
                             f"({_place(form, body_start + position)}); only added LF line breaks are allowed")
    if source_offset != len(source):
        raise ValueError(f"{label}: source text missing at codepoint {source_offset + 1} "
                         f"({_place(form, body_start + len(body))}); retain all original characters")
    if source[start:].strip():
        sentences.append(source[start:].strip())
    return sentences


def import_marking_form(snapshot, sample, form, *, reviewer):
    """Fill the existing review fields after exact source and sample validation."""
    _unmarked(snapshot, sample)
    form = decode_marking_form(form)
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("supply a nonempty reviewer label")
    position = _expect(form, 0, _intro(sample), "Form header/sample binding")
    result = deepcopy(sample)
    result["reviewer"] = reviewer
    for number, row in enumerate(result["passages"], 1):
        label = f"Passage {number} ({row['id']})"
        position = _expect(form, position, _heading(number, row) + "EXCLUDE: ", label + " heading")
        end_reason = form.find("\n", position)
        if end_reason < 0:
            raise ValueError(f"{label}: missing exclusion line end at {_place(form, position)}")
        reason = form[position:end_reason].strip()
        position = _expect(form, end_reason, "\nTEXT\n", label + " TEXT heading")
        end_body = form.find(_end(row), position)
        if end_body < 0:
            raise ValueError(f"{label}: missing passage end after {_place(form, position)}")
        sentences = _sentences(row["text"], form[position:end_body], form=form, body_start=position, label=label)
        row.update(gold_sentences=None if reason else sentences, exclude_reason=reason or None)
        position = end_body + len(_end(row))
    position = _expect(form, position, "END OF FORM\n", "Form ending")
    if position != len(form):
        raise ValueError(f"unexpected text after form ending at {_place(form, position)}")
    if all(row["exclude_reason"] is not None for row in result["passages"]):
        raise ValueError("review contains no scored passages; adjudicate at least one passage")
    core.verify_snapshot_current(snapshot)
    return result
