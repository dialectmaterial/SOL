"""Explicit checkout-only launchers; never modify SOL configuration or defaults."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


def main(argv=None):
    parser = argparse.ArgumentParser(description="Isolated SOL reader-surface research (no personal workspace)")
    parser.add_argument("--corpus", required=True, type=Path, help="existing verified indexed corpus, never a PDF")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--start", help="existing passage ID or unambiguous prefix")
    choice.add_argument("--trial", choices=("beginning", "opening"), help="source-bounded chapter or short opening; no UUID needed")
    parser.add_argument("--count", type=int, help="adjacent passages, 1..64 (default 24; not combined with --trial)")
    commands = parser.add_subparsers(dest="mode", required=True)
    commands.add_parser("inventory", help="measure verified loading and report bounded sample, without quotes")
    baseline = commands.add_parser("baseline", help="existing reader at the same sample start; ordinary navigation, no workspace")
    baseline.add_argument("--width", type=int, default=72)
    tui = commands.add_parser("tui", help="opt-in continuous terminal proof")
    tui.add_argument("--width", type=int, default=72)
    html = commands.add_parser("html", help="create one private offline typeset artifact, refusing overwrite")
    html.add_argument("--output", required=True, type=Path)
    validate = commands.add_parser("validate", help="validate a downloaded research packet; save nothing")
    validate.add_argument("packet", type=Path)
    args = parser.parse_args(argv)
    if args.trial is not None and args.count is not None:
        parser.error("--trial fixes its complete extent; do not combine it with --count")
    try:
        if args.mode in {"baseline", "tui"}:
            from sol.terminal.reader import validate_reader_environment
            validate_reader_environment()
        from sol.core.corpus import load_corpus_book
        from .common import sample_from_book, validate_packet
        started = time.perf_counter()
        book = load_corpus_book(args.corpus)
        loaded = time.perf_counter()
        trial = None
        if args.trial is not None:
            from .trials import select_trial
            trial = select_trial(book, args.trial)
        sample = trial.sample if trial is not None else sample_from_book(book, args.start, 24 if args.count is None else args.count)
        if args.mode == "inventory":
            inventory = {"load_seconds": round(loaded - started, 4),
                              "sample_seconds": round(time.perf_counter() - loaded, 4),
                              "book_passages": len(book.passages), "sample_passages": len(sample.passages),
                              "sample_codepoints": sum(len(p.text) for p in sample.passages),
                              "start": sample.passages[0].identifier, "workspace": None}
            if trial is not None:
                inventory["trial"] = trial.metadata
            print(json.dumps(inventory, indent=2))
        elif args.mode == "html":
            from .html import write_html
            if trial is None:
                write_html(sample, args.output)
            else:
                write_html(sample, args.output, trial=trial)
            print(f"Created private offline experiment: {args.output.resolve()}")
        elif args.mode == "validate":
            if args.packet.stat().st_size > 1024 * 1024:
                raise ValueError("research packet exceeds 1 MiB")
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate packet JSON field")
                    result[key] = value
                return result
            packet = json.loads(args.packet.read_text(encoding="utf-8"), object_pairs_hook=unique)
            selected = validate_packet(book, packet)
            print(json.dumps({"accepted": True, "target_id": packet["reference"]["reference"]["target_id"],
                              "cursor_offset": packet["cursor_offset"],
                              "span": None if selected is None else [selected.start, selected.end],
                              "workspace_written": False}))
        elif args.mode == "baseline":
            from sol.terminal.reader import ReaderView
            return ReaderView(sample.actions, width=args.width).run()
        else:
            from .tui import run
            return run(sample, width=args.width)
    except (ValueError, OSError, RuntimeError, ImportError, RecursionError) as error:
        print(f"reader experiment: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
