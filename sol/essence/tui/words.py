"""Word frequencies from the interface: choices in, the engine's artifact out.

This module turns the Experiment screen's choices into the stage 2 engine's
providers (`sol.essence.words.analyze_words`), and its artifact into table
rows. It holds no Textual code. The engine is imported lazily, so the
interface still opens, and says so, when the engine is not installed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path

TARGETS = {"passage": "This passage", "section": "This section", "book": "Whole book", "file": "A text file"}
REFERENCES = {"none": "No reference", "section": "This section", "book": "Whole book", "file": "A text file"}
ROW_LIMIT = 2000


class EngineMissing(RuntimeError):
    """The word-frequency engine (ESSENCE stage 2) is not available."""


def engine():
    try:
        from sol.essence import word_inputs, words
    except ImportError as error:
        raise EngineMissing("Word frequencies need the ESSENCE stage 2 engine, which is not installed yet.") from error
    return words, word_inputs


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
    """Count words for the chosen target and reference; returns the artifact."""
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
    return words.analyze_words(target, reference=reference)


def rows(result, limit=ROW_LIMIT):
    """Table rows: word, then count and rate for the target and the reference."""
    def cells(cell):
        if cell is None:
            return ("", "")
        rate = cell["rate_per_10000_tokens"]
        return (str(cell["count"]), "undefined" if rate is None else f"{rate:.2f}")
    table = [(row["word"], *cells(row["target"]), *cells(row["reference"])) for row in result["frequencies"][:limit]]
    return table, len(result["frequencies"])


def summary(result):
    """Plain lines describing both sides, denominators first."""
    def side(name, part):
        if part is None:
            return f"{name}: none"
        totals = part["summary"]
        where = part["scope"].get("path") or part["scope"]["kind"]
        return (f"{name}: {totals['token_count']:,} tokens, {totals['type_count']:,} distinct words, "
                f"{totals['input_count']:,} inputs ({part['provider']}, {where})")
    return [side("Target", result["target"]), side("Reference", result["reference"]),
            *(f"Note: {warning}" for warning in result["warnings"])]


def save(result, *, data_home=None):
    """Save the artifact owner-only beside the other studies; never overwrite."""
    words, _ = engine()
    home = Path(data_home or os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    directory = home / "sol" / "studies"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    data = (words.encode_word_result(result) + "\n").encode("utf-8")
    for number in range(100):
        path = directory / (f"words-{stamp}" + (f"-{number}" if number else "") + ".sol-analysis.json")
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        except FileExistsError:
            continue
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        return path
    raise ValueError("could not create a new study file")
