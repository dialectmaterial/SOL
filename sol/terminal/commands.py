"""SOL operations invoked from a real shell; no shell grammar is implemented."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import shlex
from pathlib import Path
import sys
import tempfile


def _path_argument(book, value):
    """Honor real shell cwd before corpus-relative and virtual compatibility."""
    candidate = Path(value).expanduser()
    if value.lower().endswith(".md") and not candidate.is_absolute():
        if candidate.exists() or candidate.is_symlink():
            return str(candidate.resolve())
    return str(candidate) if candidate.is_absolute() else value


def _records(book, value):
    from sol.workspace.comparison import resolve_comparison_path
    selection = resolve_comparison_path(book, _path_argument(book, value), ())
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
    elif action == "compare":
        parser.description = "Compare two complete files, then return to your shell with q."
        parser.add_argument("paths", nargs=2, metavar="FILE")
        parser.add_argument("--question", default="", help="optional inquiry to keep alongside the text")
        parser.add_argument("--json", action="store_true", help="print a comparison snapshot instead of opening the viewer")
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
                print("\n\n".join(record["markdown"] for record in records))
            else:
                text = _text(selection, records, options.plain)
                if sys.stdout.isatty():
                    from sol.workspace.reader import safe_output
                    text = safe_output(text)
                print(text)
            return 0
        from sol.workspace.comparison import capture_paths
        from sol.core.paths import resolve_path
        paths = [_path_argument(book, value) for value in options.paths]
        snapshot = capture_paths(book, paths, resolve_path=resolve_path, question=options.question)
        snapshot["terminal_mode"] = "foreground"
        snapshot["reopen_command"] = "sol compare " + " ".join(shlex.quote(s["path"]) for s in snapshot["selections"])
        if options.question:
            snapshot["reopen_command"] += " --question " + shlex.quote(options.question)
        if options.json:
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
            return 0
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ValueError("sol compare needs an interactive terminal; use --json for pipes or redirection")
        from sol.terminal.comparison import viewer_main
        with tempfile.TemporaryDirectory(prefix="sol-shell-comparison-") as temporary:
            mailbox = Path(temporary) / "selection.json"
            mailbox.write_text(json.dumps({"sequence": 1, "request": snapshot}), encoding="utf-8")
            mailbox.chmod(0o600)
            return viewer_main(mailbox)
    except ValueError as error:
        print(f"sol: {error}", file=sys.stderr)
        return 2
    except RuntimeError as error:
        print(f"sol: {error}", file=sys.stderr)
        return 1
