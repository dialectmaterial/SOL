"""JSON reference exchange: capture or check a canonical reference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def build_parser() -> argparse.ArgumentParser:
    """Construct help without discovering or opening application data."""
    parser = argparse.ArgumentParser(
        prog="sol reference",
        description="Capture or check a canonical reference without opening a reader or workspace.",
    )
    actions = parser.add_subparsers(dest="action", required=True)
    capture = actions.add_parser("capture", help="print a portable reference as JSON")
    capture.add_argument("identifier", metavar="ID", help="canonical record UUID or unique prefix")
    check = actions.add_parser("check", help="verify reference JSON against a local corpus")
    check.add_argument("file", nargs="?", default="-", metavar="FILE|-",
                       help="reference JSON file, or - for piped input (default)")
    for command in (capture, check):
        command.add_argument("--corpus", type=Path, metavar="DIRECTORY",
                             help="use this local canonical corpus instead of discovery")
    return parser


def _read_reference(filename: str, maximum: int) -> bytes | str:
    """Compatibility seam; reference and experiment CLIs share bounded input."""
    from sol.core.wire import read_json_input

    return read_json_input(filename, maximum)


def main(arguments: list[str] | None = None) -> int:
    """Capture or check one canonical reference."""
    options = build_parser().parse_args(arguments)
    try:
        from sol.core import (
            MAX_REFERENCE_BYTES, capture_reference, check_reference,
            decode_reference, discover_corpus, encode_reference, load_snapshot,
        )

        payload = None
        if options.action == "check":
            payload = decode_reference(_read_reference(options.file, MAX_REFERENCE_BYTES))
        directory = discover_corpus(options.corpus)
        if directory is None:
            raise ValueError("No canonical corpus configured; use --corpus DIRECTORY or configure one with sol --set-corpus DIRECTORY")
        snapshot = load_snapshot(directory)
        if options.action == "capture":
            print(encode_reference(capture_reference(snapshot, options.identifier)))
        else:
            reference = check_reference(snapshot, payload)
            result = {
                "status": "current",
                "corpus_id": payload["corpus"]["id"],
                "generation": payload["generation"],
                "requested_id": reference.requested_id,
                "target_id": reference.target_id,
                "chain": list(reference.chain),
                "content_sha256": reference.record["content_sha256"],
                "type": reference.record["type"],
                "sources": payload["reference"]["sources"],
                "attribution": payload["reference"]["attribution"],
            }
            print(json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        if options.action == "check":
            status = getattr(error, "status", "invalid")
            result = {"status": status, "error": str(error)}
            if hasattr(error, "code"):
                result["code"] = error.code
            print(json.dumps(result, ensure_ascii=True,
                             sort_keys=True, separators=(",", ":")))
        print(f"sol: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
