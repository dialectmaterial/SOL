"""sol read: print a complete canonical file from a real shell."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import posixpath
import sys

from sol.core.paths import resolve_path


def _path_argument(book, value):
    """Honor real shell cwd before corpus-relative and virtual compatibility."""
    candidate = Path(value).expanduser()
    if value.lower().endswith(".md") and not candidate.is_absolute():
        if candidate.exists() or candidate.is_symlink():
            return str(candidate.resolve())
    return str(candidate) if candidate.is_absolute() else value


def resolve_file_path(book, value, cwd=()):
    """Select complete ordered canonical text, without reading arbitrary files.

    .txt paths belong to SOL's virtual tree; .md paths are relative to the
    configured corpus or absolute filenames within it. Both resolve to IDs from
    the loaded index. Physical Markdown is never parsed a second time here.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Choose a SOL text path or a canonical Markdown file")
    records = book.canonical_records
    if value.lower().endswith(".md"):
        documents = book.corpus_manifest.get("documents", [])
        candidate = Path(value).expanduser()
        directory = getattr(book, "corpus_directory", None)
        if candidate.is_absolute():
            if directory is None:
                raise ValueError("No canonical corpus directory is configured")
            try:
                document = candidate.resolve().relative_to(Path(directory).resolve()).as_posix()
            except ValueError as error:
                raise ValueError("Choose a Markdown file inside the configured SOL corpus") from error
        else:
            document = posixpath.normpath(value)
            if directory is not None and document.startswith(Path(directory).name + "/"):
                document = document[len(Path(directory).name) + 1:]
        if document not in documents:
            raise ValueError(f"Not a canonical Markdown file: {value}. Use a path from the SOL corpus.")
        selected = [r for r in records.values() if r.get("document") == document
                    and r.get("type") != "retired_record"]
        display = str(Path(directory) / document) if directory is not None else document
        title = next((r.get("title") for r in selected if r.get("type") == "section" and r.get("title")),
                     Path(document).stem.replace("-", " "))
        kind = "markdown_file"
    else:
        node, scope = resolve_path(value, cwd, book.root)
        passage_ids = {p.identifier for p in book.selection(scope)}
        prefix = "/" + "/".join(scope)
        selected = [r for r in records.values() if r["id"] in passage_ids
                    or (r.get("type") == "section" and isinstance(r.get("reader_path"), str)
                        and (r["reader_path"] == prefix or r["reader_path"].startswith(prefix.rstrip("/") + "/")))]
        display, title, kind = prefix, node.title, "reader_path"
    selected.sort(key=lambda r: r["order"])
    if not selected:
        raise ValueError(f"No canonical text in {value}")
    return {"path": display, "display_path": document if kind == "markdown_file" else display,
            "title": title, "kind": kind,
            "target_ids": [r["id"] for r in selected]}


def _records(book, value):
    selection = resolve_file_path(book, _path_argument(book, value))
    records = [deepcopy(book.canonical_records[identifier]) for identifier in selection["target_ids"]]
    return selection, records


def _text(selection, records, plain):
    blocks = [] if plain else [selection["title"], selection["display_path"]]
    previous = None
    for record in records:
        if not plain:
            attribution = record.get("attribution") or {}
            current = attribution.get("author"), attribution.get("role")
            if current != previous:
                author, role = current
                label = "Text by " + (author or "unattributed edition contributor")
                if role and role != "main_text":
                    label += " | " + role.replace("_", " ")
                blocks.append(label)
            if record.get("transcription_status") in {"needs_review", "needs_visual_review"}:
                blocks.append("[Transcription needs source review]")
            previous = current
        blocks.append(record["plain_text"])
    return "\n\n".join(blocks)


def main(arguments):
    action = arguments[0]
    parser = argparse.ArgumentParser(prog="sol " + action)
    parser.add_argument("--corpus", type=Path, metavar="DIRECTORY", help="use this canonical corpus")
    if action == "read":
        parser.description = "Read a complete canonical file in order; output can be piped."
        parser.add_argument("path", metavar="FILE")
        outputs = parser.add_mutually_exclusive_group()
        outputs.add_argument("--plain", action="store_true", help="unwrapped text only")
        outputs.add_argument("--markdown", action="store_true", help="original record Markdown")
        outputs.add_argument("--json", action="store_true", help="canonical records with IDs, attribution and sources")
    else:
        raise ValueError("Unsupported native SOL action")
    options = parser.parse_args(arguments[1:])
    try:
        from sol.core.config import discover_corpus
        from sol.core.corpus import load_corpus_book
        directory = discover_corpus(options.corpus)
        if directory is None:
            raise ValueError("No canonical corpus configured; use sol --set-corpus DIRECTORY or --corpus DIRECTORY")
        book = load_corpus_book(directory)
        if action == "read":
            selection, records = _records(book, options.path)
            if options.json:
                print(json.dumps({"selection": selection, "corpus": book.corpus_manifest,
                                  "records": records}, ensure_ascii=False, indent=2))
            elif options.markdown:
                from sol.terminal.text import display_text
                print(display_text("\n\n".join(record["markdown"] for record in records)))
            else:
                text = _text(selection, records, options.plain)
                if sys.stdout.isatty():
                    from sol.terminal.text import safe_output
                    text = safe_output(text)
                print(text)
            return 0
    except ValueError as error:
        print(f"sol: {error}", file=sys.stderr)
        return 2
    except RuntimeError as error:
        print(f"sol: {error}", file=sys.stderr)
        return 1
