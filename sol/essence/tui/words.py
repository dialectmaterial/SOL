"""Word frequencies from the interface: choices in, the engine's artifact out.

This module turns the Experiment screen's choices into the stage 2 engine's
providers (`sol.essence.words.analyze_words`), and its artifact into table
rows; with a reference, the stage 3 measures come from
`sol.essence.comparison`. It holds no Textual code. The engine is imported
lazily, so the interface still opens, and says so, when it is not installed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path

TARGETS = {"passage": "This passage", "section": "This section", "book": "Whole book", "file": "A text file"}
REFERENCES = {"none": "No reference", "section": "This section", "book": "Whole book", "file": "A text file"}
ROW_LIMIT = 2000
# How an undefined comparison measure is shown, by the engine's status.
UNDEFINED = {"zero_target_count": "absent in target", "zero_reference_count": "absent in reference",
             "empty_target": "empty target", "empty_reference": "empty reference", "empty_both": "both empty"}
METHOD_LINE = ("Difference: target rate minus reference rate, per 10,000 tokens. "
               "Log₂ ratio: log₂ of target rate over reference rate. No smoothing: "
               "a word absent on one side has no ratio.")


@dataclass
class Count:
    """One count: the saved v1 study, the comparison view, and their providers."""

    study: dict
    comparison: dict | None
    target: object
    reference: object | None


class EngineMissing(RuntimeError):
    """The word-frequency engine (ESSENCE stage 2) is not available."""


def engine():
    try:
        from sol.essence import word_inputs, words
    except ImportError as error:
        raise EngineMissing("Word frequencies need the ESSENCE stage 2 engine, which is not installed yet.") from error
    return words, word_inputs


def comparison_engine():
    try:
        from sol.essence import comparison
    except ImportError as error:
        raise EngineMissing("Comparison needs the ESSENCE stage 3 engine, which is not installed yet.") from error
    return comparison


def reader_section(book, target_id):
    """The reader path of the section holding the reader's passage."""
    from sol.core.paths import display_path
    passage = book.find_passage(target_id)
    return display_path(passage.path[:-1]) if len(passage.path) > 1 else display_path(passage.path)


def provider(choice, context, *, book=None, snapshot=None, path=None, inputs=None):
    """One side of the comparison, as an engine provider; None for no reference."""
    if choice == "none":
        return None
    if inputs is None:
        inputs = engine()[1]
    if choice == "file":
        if not path or not str(path).strip():
            raise ValueError("Name a UTF-8 text file to count.")
        return inputs.FileProvider(Path(str(path).strip()).expanduser())
    target_id = context["reference"]["reference"]["target_id"]
    scope = {"passage": {"kind": "passages", "ids": [target_id]},
             "section": {"kind": "within", "path": reader_section(book, target_id) if book is not None else None},
             "book": None}[choice]
    return inputs.CoreProvider(snapshot, scope)


def run(context, target_choice, reference_choice, *, target_file=None, reference_file=None, loader=None):
    """Count words for the chosen target and reference; returns a Count."""
    words, inputs = engine()
    book = snapshot = None
    if target_choice != "file" or reference_choice in {"section", "book"}:
        if not context["corpus"]:
            raise ValueError("This reader session has no CORE corpus; choose text files instead.")
        from sol import core
        load = loader or (lambda directory: core.load_corpus_book(Path(directory)))
        book = load(context["corpus"])
        snapshot = book.corpus_snapshot
        # The reader's position belongs to the corpus generation it was read
        # in; a changed corpus is refused rather than counted as if unchanged.
        from sol import core
        core.check_reference(snapshot, context["reference"])
    target = provider(target_choice, context, book=book, snapshot=snapshot, path=target_file, inputs=inputs)
    reference = provider(reference_choice, context, book=book, snapshot=snapshot, path=reference_file, inputs=inputs)
    if reference is None:
        return Count(words.analyze_words(target), None, target, None)
    # One computation: the comparison view carries the unchanged v1 study.
    comparison = comparison_engine().compare_words(target, reference=reference)
    return Count(comparison["study"], comparison, target, reference)


def rows(count, limit=ROW_LIMIT):
    """Table rows: word, count and rate for each side, then the two measures."""
    def cells(cell):
        if cell is None:
            return ("", "")
        rate = cell["rate_per_10000_tokens"]
        return (str(cell["count"]), "undefined" if rate is None else f"{rate:.2f}")
    def measure(value, status):
        return f"{value:+.2f}" if status == "defined" else UNDEFINED.get(status, status)
    if count.comparison is None:
        table = [(row["word"], *cells(row["target"]), *cells(row["reference"]))
                 for row in count.study["frequencies"][:limit]]
    else:
        table = [(row["word"], *cells(row["target"]), *cells(row["reference"]),
                  measure(row["rate_difference_per_10000_tokens"], row["rate_difference_status"]),
                  measure(row["log2_rate_ratio"], row["log2_ratio_status"]))
                 for row in count.comparison["rows"][:limit]]
    return table, len(count.study["frequencies"])


def sources(count, index):
    """Where row `index`'s word occurs: one entry per contributing input and side.

    An entry from the corpus carries what the reader needs to open it (the
    record ID, the word's first offset and the counted text's digest); an
    entry from a text file has none, since the reader cannot show it.
    """
    row = count.study["frequencies"][index]
    found = []
    for side in ("target", "reference"):
        cell, part = row[side], count.study[side]
        if cell is None:
            continue
        for input_index, occurrences, start, _ in cell["locations"]:
            item = part["inputs"][input_index]
            if part["provider"] == "core":
                pages = item["sources"][0]["printed_page"] if item["sources"] else None
                label = f"{item['reader_path']} | p. {pages}" if pages else item["reader_path"]
                opens = {"id": item["id"], "start": start, "content_sha256": item["content_sha256"]}
            else:
                label, opens = f"text file, at character {start:,}", None
            found.append({"side": side, "count": occurrences, "label": label, "open": opens})
    return found


def summary(count):
    """Plain lines describing both sides, denominators first."""
    result = count.study
    def side(name, part):
        if part is None:
            return f"{name}: none"
        totals = part["summary"]
        where = part["scope"].get("path") or part["scope"]["kind"]
        return (f"{name}: {totals['token_count']:,} tokens, {totals['type_count']:,} distinct words, "
                f"{totals['input_count']:,} inputs ({part['provider']}, {where})")
    if count.comparison is None:
        return [side("Target", result["target"]), side("Reference", result["reference"]),
                *(f"Note: {warning}" for warning in result["warnings"])]
    return [side("Target", result["target"]), side("Reference", result["reference"]), METHOD_LINE,
            *(f"Note: {warning}" for warning in count.comparison["warnings"])]


def save(count, *, data_home=None):
    """Save the v1 artifact owner-only beside the other studies; never overwrite."""
    words, _ = engine()
    data = (words.encode_word_result(count.study) + "\n").encode("utf-8")
    return _create(data, ".sol-analysis.json", data_home)


def export(count, table_format, *, data_home=None):
    """Write the comparison as CSV or TSV beside the studies; never overwrite.

    The engine checks the providers against the study again first, so a
    source changed since the count is refused rather than exported.
    """
    if count.reference is None:
        raise ValueError("Export needs a reference: what is exported is the comparison table.")
    text = comparison_engine().export_word_comparison(count.target, reference=count.reference,
                                                      result=count.study, format=table_format)
    return _create(text.encode("utf-8"), "." + table_format, data_home)


def _create(data, suffix, data_home):
    home = Path(data_home or os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    directory = home / "sol" / "studies"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for number in range(100):
        path = directory / (f"words-{stamp}" + (f"-{number}" if number else "") + suffix)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            continue
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        return path
    raise ValueError("could not create a new study file")
