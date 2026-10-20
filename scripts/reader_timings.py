#!/usr/bin/env python3
"""Read-only, warm-process reader measurements; no optimisations or GUI launch.

Run from a checkout. Invented corpus by default; --corpus is always explicit.
Reported operations overlap: independent stage times must not be added together.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
from unittest.mock import patch
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sol import core
from sol.core.paths import display_path, resolve_path
from sol.corpus import contract
from sol.reader.actions import ReaderActions
from sol.reader.render import render_passage
from sol.reader.surface import Sample, note_paragraph_ids
from sol.reader.typography import map_typography
from sol.terminal import neovim, neovim_reader
from sol.workspace.reader import WorkspaceReader
from sol.workspace.store import Workspace


OPERATIONS = ("snapshot_load", "corpus_book_load", "core_verify", "payload_ordinary",
              "payload_footnote_heavy", "typography_ordinary", "typography_footnote_heavy",
              "startup_python_first_payload", "controller_next", "controller_previous",
              "controller_search", "controller_search_open", "controller_history_back",
              "controller_occurrence_next", "controller_occurrence_previous",
              "controller_passage_next", "controller_passage_previous", "controller_outline_open")


def synthetic_corpus(directory):
    """Build a small, deterministic three-section source, not an extraction mock."""
    directory.mkdir()
    chunks, order = [], 0

    def add(kind, text, parent, chapter, **extra):
        nonlocal order
        order += 1
        identifier = str(UUID(int=order))
        metadata = {"id": identifier, "type": kind, "parent_id": parent, "order": order,
                    "sources": [{"pdf_page": 1, "printed_page": "1"}],
                    "attribution": {"author": "G. W. F. Hegel", "role": "main_text", "status": "confirmed"},
                    "reader_path": f"/BEING/{chapter}.txt", "reader_title": chapter, **extra}
        chunks.append(contract.render_record(metadata, text))
        return identifier

    for chapter in ("ordinary", "notes", "last"):
        section = add("section", f"# {chapter}", None, chapter, title=chapter, path=f"/{chapter}", level=4)
        for number in range(3):
            # Reserve the following six IDs for each note and its body.
            notes = [str(UUID(int=order + 2 + offset * 2)) for offset in range(3)] if chapter == "notes" else []
            calls = "".join(f'<sup data-sol-note="{note}">[{i + 1}](sample.md#{note})</sup>'
                            for i, note in enumerate(notes))
            passage = add("paragraph", f"An *invented* {chapter} passage {number} considers a distinction{calls}. "
                          "Another **claim** follows; 界 and e\u0301 remain exact.", section, chapter, note_ids=notes)
            for i, note in enumerate(notes):
                created = add("note", f"Note {i + 1}", None, chapter, backlinks=[passage], label=str(i + 1),
                              attribution={"author": "Invented editor", "role": "editorial_note", "status": "confirmed"})
                if created != note:
                    raise ValueError("synthetic note IDs disagree")
                add("note_paragraph", "An invented *editorial* clarification. Another sentence follows.", created,
                    chapter, attribution={"author": "Invented editor", "role": "editorial_note", "status": "confirmed"})
    (directory / "sample.md").write_text("\n".join(chunks), encoding="utf-8")
    manifest = {"contract_version": 1, "corpus_id": str(UUID(int=10000)),
                "edition": {"title": "Invented reader timing corpus"},
                "source": {"filename": "absent.pdf", "sha256": "0" * 64, "pdf_pages": 1},
                "documents": ["sample.md"],
                "page_inventory": [{"pdf_page": 1, "printed_page": "1", "disposition": "records"}]}
    (directory / "corpus.json").write_text(json.dumps(manifest), encoding="utf-8")
    contract.reindex(directory)
    return directory


@contextmanager
def isolated_state(root):
    environment = {f"XDG_{kind}_HOME": str(root / kind.lower()) for kind in ("CONFIG", "DATA", "CACHE", "STATE")}
    environment["NVIM_LOG_FILE"] = str(root / "nvim.log")
    with patch.dict(os.environ, environment):
        yield


def sections(book):
    """Use actual chapter/64-record bounds, not guessed or equal-sized chapters."""
    result, at = [], 0
    while at < len(book.passages):
        extent = neovim_reader.reading_section(book, book.passages[at].identifier)
        passages = tuple(book.passages[extent.first:extent.last + 1])
        result.append(Sample(book, passages, ReaderActions(book)))
        at = extent.last + 1
    if len(result) < 2:
        raise ValueError("timing section transitions requires at least two reader sections")
    return result


def shape(sample):
    return {"first_id": sample.passages[0].identifier, "passages": len(sample.passages),
            "source_codepoints": sum(len(p.text) for p in sample.passages),
            "linked_notes": sum(len(sample.book.canonical_records[p.identifier].get("note_ids", []))
                                for p in sample.passages)}


def typography(sample):
    bodies = note_paragraph_ids(sample.book)
    for passage in sample.passages:
        ids = [passage.identifier]
        for note in sample.book.canonical_records[passage.identifier].get("note_ids", []):
            ids += bodies.get(note, []) or [note]
        for identifier in ids:
            record = sample.book.canonical_records[identifier]
            map_typography(record["markdown"], record["plain_text"])


def controller_session(directory, root, number, width, measure):
    """Drive the real controller; replace only its terminal boundary, not guards."""
    started = time.perf_counter()
    book = core.load_corpus_book(directory)
    store = Workspace(root / f"session-{number}.sqlite3", book.corpus_manifest["corpus_id"],
                      {key: book.corpus_manifest[key] for key in ("edition", "source")}, actor="SOL timing probe")
    service = WorkspaceReader(book, store, "SOL timing probe", resolve_path, display_path,
                              render_passage, width, False, False)
    startup = None

    def frontend(payload, executable, *, on_request):
        nonlocal startup
        startup = time.perf_counter() - started
        first = payload["records"][0]
        # Derive a guaranteed match from source; never include the query/snippet in the report.
        query = " ".join(first["plain_text"].split())[:80]
        if not query:
            raise ValueError("first passage has no searchable text")

        def request(operation, *, packet=None, **fields):
            nonlocal payload
            row = payload["records"][0]
            packet = packet or payload.get("restore") or {"reference": row["reference"], "selection": None, "cursor_offset": 0}
            response = on_request({"op": operation, "packet": packet, "mode": "continuous", **fields})
            if "payload" in response:
                payload = response["payload"]
            elif "position" in response:
                payload = {**payload, **response["position"]}
            return response

        measure("controller_next", lambda: request("next"))
        destination = payload["records"][0]["id"]
        if destination == first["id"]:
            raise ValueError("next did not change the displayed section")
        measure("controller_previous", lambda: request("previous"))
        if payload["records"][0]["id"] != first["id"]:
            raise ValueError("previous did not return to the initial section")
        request("next")  # Untimed setup: search result opens a different section.
        search = measure("controller_search", lambda: request("search", query=query))
        if not search["search"]["rows"]:
            raise ValueError("derived benchmark query found no search results")
        measure("controller_search_open", lambda: request("search_open", result=1))
        if payload["records"][0]["id"] != first["id"]:
            raise ValueError("search_open did not return to the queried section")
        measure("controller_history_back", lambda: request("history_back"))
        if payload["records"][0]["id"] != destination:
            raise ValueError("history did not restore the previous section")
        request("previous")
        # Prefer an ordinary repeated word; fall back to a repeated letter for
        # very short opening paragraphs. Never export this private query.
        text = first["plain_text"].casefold()
        counts = Counter(char for char in text if char.isalpha())
        if not counts or counts.most_common(1)[0][1] < 2:
            raise ValueError("occurrence timing needs a repeated letter in the opening passage")
        repeated = "the" if text.count("the") >= 2 else counts.most_common(1)[0][0]
        request("search", query=repeated)
        request("search_open", result=1)
        origin = payload["restore"]["reference"]["reference"]["target_id"]
        for name, op in (("controller_occurrence_next", "search_next"),
                         ("controller_occurrence_previous", "search_previous")):
            measure(name, lambda: request(op))
            if payload["restore"]["reference"]["reference"]["target_id"] != origin:
                raise ValueError("occurrence probe must stay in the shown passage")
        last = payload["records"][-1]
        boundary = {"reference": last["reference"], "selection": None, "cursor_offset": len(last["plain_text"])}
        measure("controller_passage_next", lambda: request("passage_next", packet=boundary))
        if payload["records"][0]["id"] != destination:
            raise ValueError("paragraph probe must cross the loaded section boundary")
        measure("controller_passage_previous", lambda: request("passage_previous"))
        node = next(row for row in payload["structure"]["nodes"] if row["target"] == destination)
        measure("controller_outline_open", lambda: request("node_open", node=node["key"]))
        return 0, None  # Exit without a fake editor quit packet.

    try:
        with patch.object(neovim, "validate_environment", return_value="not-launched"), \
                patch.object(neovim, "launch_payload", side_effect=frontend):
            neovim_reader.run_reader(book, service, width=width, emphasis="underline")
        if startup is None:
            raise ValueError("controller did not prepare its first payload")
        return startup
    finally:
        store.close()


def summary(values):
    quartiles = statistics.quantiles(values, n=4, method="inclusive") if len(values) > 1 else values * 3
    return {"median_ms": statistics.median(values), "min_ms": min(values), "max_ms": max(values),
            "p25_ms": quartiles[0], "p75_ms": quartiles[2], "samples_ms": values}


def benchmark(corpus=None, *, repeats=5, warmups=1, width=72):
    if type(repeats) is not int or not 1 <= repeats <= 30:
        raise ValueError("repeats must be an integer from 1 to 30")
    if type(warmups) is not int or not 0 <= warmups <= 10:
        raise ValueError("warmups must be an integer from 0 to 10")
    if type(width) is not int or not 20 <= width <= 240:
        raise ValueError("width must be an integer from 20 to 240")
    values = {name: [] for name in OPERATIONS}
    with tempfile.TemporaryDirectory(prefix="sol-reader-timings-") as temporary:
        root = Path(temporary)
        with isolated_state(root):
            directory = Path(corpus).expanduser().resolve() if corpus is not None else synthetic_corpus(root / "corpus")
            book = core.load_corpus_book(directory)
            samples = sections(book)
            ordinary = min(samples, key=lambda sample: shape(sample)["linked_notes"])
            heavy = max(samples, key=lambda sample: shape(sample)["linked_notes"])
            if not shape(heavy)["linked_notes"]:
                raise ValueError("a footnote-heavy view needs at least one linked source note")
            for number in range(warmups + repeats):
                def measure(name, operation):
                    start = time.perf_counter()
                    result = operation()
                    elapsed = (time.perf_counter() - start) * 1000
                    if number >= warmups:
                        values[name].append(elapsed)
                    return result

                measure("snapshot_load", lambda: core.load_snapshot(directory))
                measure("corpus_book_load", lambda: core.load_corpus_book(directory))
                measure("core_verify", lambda: core.verify_snapshot_current(book.corpus_snapshot))
                for label, sample in (("ordinary", ordinary), ("footnote_heavy", heavy)):
                    measure("payload_" + label, lambda: neovim.build_payload(sample, width, emphasis="underline"))
                    measure("typography_" + label, lambda: typography(sample))
                elapsed = controller_session(directory, root, number, width, measure)
                if number >= warmups:
                    values["startup_python_first_payload"].append(elapsed * 1000)
            core.verify_snapshot_current(book.corpus_snapshot)
            return {"measurement_version": 2, "clock": "time.perf_counter", "repeats": repeats,
                    "discarded_warmups": warmups, "width": width,
                    "host": {"python": platform.python_version(), "platform": platform.platform(),
                             "logical_cpus": os.cpu_count()},
                    "dataset": {"kind": "synthetic" if corpus is None else "explicit local corpus",
                                "corpus_id": book.corpus_snapshot.corpus_id,
                                "index_sha256": book.corpus_snapshot.index_sha256,
                                "records": len(book.corpus_snapshot.records), "passages": len(book.passages),
                                "ordinary": shape(ordinary), "footnote_heavy": shape(heavy),
                                "controller_origin": shape(samples[0]), "controller_study_section": shape(samples[1])},
                    "limits": ["Warm process and OS cache; imports and corpus-selection setup are excluded.",
                               "No Neovim process, IPC, painting, terminal or human-latency measurement.",
                               "Startup includes fresh book load, temporary SQLite creation and first controller payload.",
                               "Controller operations include real validation, persistence and payload preparation.",
                               "Occurrence steps stay in one passage; paragraph steps cross the loaded section boundary; outline opens the second section.",
                               "Search uses the first 80 whitespace-normalized characters of the first passage, all matching passages.",
                               "Typography is a standalone single pass, not an attributed part of payload time.",
                               "Stage/operation timings overlap; do not add them or infer causation from subtraction.",
                               "Ordinary=min linked notes, heavy=max; section lengths are not matched."],
                    "operations": {name: summary(rows) for name, rows in values.items()}}


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, help="explicit verified local corpus; default: temporary invented corpus")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--width", type=int, default=72)
    parser.add_argument("--json", action="store_true", help="text-free measurement report; keep real-book reports outside Git")
    options = parser.parse_args(arguments)
    try:
        report = benchmark(options.corpus, repeats=options.repeats, warmups=options.warmups, width=options.width)
    except (ValueError, OSError) as error:
        print(f"reader_timings: {str(error)!r}", file=sys.stderr)
        return 2
    if options.json:
        print(json.dumps(report, ensure_ascii=True, allow_nan=False, indent=2))
    else:
        print(f"Reader Python timings: {report['dataset']['kind']}; {options.repeats} runs, width {options.width}")
        print("Operation                          median ms    min–max ms")
        for name, row in report["operations"].items():
            print(f"{name:34} {row['median_ms']:9.2f}    {row['min_ms']:.2f}–{row['max_ms']:.2f}")
        print("\n" + "\n".join(report["limits"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
