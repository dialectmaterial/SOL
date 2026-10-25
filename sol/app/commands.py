"""sol read: print a complete canonical file from a real shell."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

from sol.core.files import _path_argument, resolve_file_path
from sol.presentation.text import safe_output


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
                from sol.presentation.text import display_text
                print(display_text("\n\n".join(record["markdown"] for record in records)))
            else:
                text = _text(selection, records, options.plain)
                if sys.stdout.isatty():
                    text = safe_output(text)
                print(text)
            return 0
    except ValueError as error:
        print("sol: " + safe_output(error), file=sys.stderr)
        return 2
    except RuntimeError as error:
        print("sol: " + safe_output(error), file=sys.stderr)
        return 1
