"""Reader command-line arguments without loading a book or interface."""

from __future__ import annotations

import argparse
from pathlib import Path

from sol import __version__ as VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sol", description="Read and navigate Hegel's Science of Logic.")
    parser.add_argument("command", nargs="?", choices=("guide",), help="open the beginner guide")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--structure", action="store_true", help="show the outline (prefer the indexed local corpus)")
    mode.add_argument("--guide", action="store_true", help="beginner guide, examples, and book tree")
    mode.add_argument("--shell", action="store_true", help="open the workspace reader (also the default)")
    mode.add_argument("-n", "--none", action="store_true", help="open the shell without workspace or actor")
    mode.add_argument("-r", "--random", action="store_true", help="print a random passage and leave")
    mode.add_argument("--read", metavar="PATH", help="read a random paragraph within a virtual path")
    mode.add_argument("--first", metavar="PATH", help="read the first paragraph within a virtual path")
    mode.add_argument("--cat", metavar="FILE", help="display a virtual file completely, in book order")
    mode.add_argument("--search", metavar="QUERY", help="literal case-insensitive passage search")
    mode.add_argument("--passage", metavar="ID", help="open a passage by exact ID or unique prefix")
    mode.add_argument("--info", metavar="PATH", help="show location, source range, and passage counts")
    mode.add_argument("--set-corpus", type=Path, metavar="DIRECTORY",
                      help="validate and remember the default corpus for reading from any directory")
    mode.add_argument("--resume", action="store_true", help="resume the named workspace's saved passage")
    mode.add_argument("--workspace-export", action="store_true", help="export a workspace snapshot (JSON by default)")
    mode.add_argument("--workspace-check", action="store_true", help="report unresolved, retired and versioned workspace references")
    mode.add_argument("--workspace-backup", type=Path, metavar="FILE", help="create a new, verified .sqlite3 backup without overwriting")
    mode.add_argument("--workspace-upgrade", type=Path, metavar="FILE", help="upgrade a version-1 workspace into a separate verified copy")
    mode.add_argument("--review-queue", action="store_true", help="show canonical pending transcriptions; optionally include workspace testimony")
    parser.add_argument("--workspace", metavar="NAME", help="choose a named reading workspace without prompting")
    parser.add_argument("--workspace-dir", type=Path, metavar="DIRECTORY", help="directory for local workspace databases")
    parser.add_argument("--actor", metavar="NAME", help="explicit author for workspace notes and assertions")
    parser.add_argument("--export-format", choices=("json", "markdown"),
                        help="format for --workspace-export (default JSON)")
    parser.add_argument("--include-passages", action="store_true",
                        help="include current referenced canonical Markdown in a Markdown workspace export")
    parser.add_argument("--resume-revision", type=int, metavar="N", help="with --resume, restore a historical checkpoint as a new visit")
    parser.add_argument("--ui", choices=("auto", "basic", "prompt"), help="shell input: optional enhanced prompt or basic input (default auto)")
    parser.add_argument("--editing-mode", choices=("emacs", "vi"), help="editing keys for the enhanced shell prompt")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--corpus", type=Path, metavar="DIRECTORY",
                        help="canonical corpus for this run (otherwise discover a local or saved corpus)")
    source.add_argument("--pdf", type=Path, metavar="PATH",
                        help="explicit legacy PDF reading (slow; not used for ordinary reading)")
    parser.add_argument("--source-pdf", type=Path, metavar="PATH",
                        help="local evidence PDF for source viewing in the canonical shell")
    parser.add_argument("--width", type=int, metavar="COLUMNS", help="line width (20–240; default fits the terminal, up to 88)")
    parser.add_argument("--within", metavar="PATH", help="restrict --search to this subtree")
    parser.add_argument("--word", action="store_true", help="whole-word --search rather than substring")
    parser.add_argument("--limit", type=int, metavar="N", help="maximum search results (1–1000; default 20)")
    parser.add_argument("--context", type=int, metavar="N", help="neighbors around --passage (0–10 on each side)")
    parser.add_argument("--depth", type=int, metavar="N", help="outline depth (0–32; guide default 1)")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--plain", action="store_true", help="passage text without metadata or ANSI styling")
    output.add_argument("--json", action="store_true", help="structured output for scripts")
    return parser
