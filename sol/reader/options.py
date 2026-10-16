"""Reader command-line arguments without loading a book or interface."""

from __future__ import annotations

import argparse
from pathlib import Path

from sol import __version__ as VERSION

DEFAULT_READER_WIDTH = 72


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sol", usage="%(prog)s [OPTIONS]\n       %(prog)s guide [--depth N]\n       %(prog)s {read,compare,reference,analyze} --help",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="SOL Organizes Logic\n\n"
                    "Read Hegel's Science of Logic directly in your terminal.\n"
                    "sol opens the reader at the last actor's saved workspace and position.\n"
                    "First use asks for an actor and offers to create a workspace.",
        epilog="Start here:\n"
               "  sol                         resume reading\n"
               "  sol -n                      read without a workspace or actor\n"
               "  sol --actor NAME            use that actor's last workspace\n"
               "  sol --workspace NAME        choose a different workspace\n"
               "  sol guide                   reader keys, examples, and book structure\n"
               "  sol -r                      print one random passage and leave\n\n"
               "Reader keys: j/k lines, b/n passages, / search, v select, c context,\n"
               "f focus, ? keys, Ctrl-Q save and quit. Alacritty is a normal host;\n"
               "Kitty is optional. Use --shell for the separate book command interface.\n"
               "Native read, compare, reference, and analyze commands have their own --help.")
    parser.add_argument("command", nargs="?", choices=("guide",), help="reader guide and a small source-derived book tree")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    reader = parser.add_argument_group("Reader (the default)")
    reader.add_argument("--reader", action="store_true", help="open the full-screen reader (also what bare sol does)")
    reader.add_argument("-n", "--none", action="store_true", help="read without saving; no workspace or actor")
    reader.add_argument("--workspace", metavar="NAME", help="open this workspace instead of the actor's last one")
    reader.add_argument("--actor", metavar="NAME", help="name attributed to your personal notes; remembers that actor's workspace")
    reader.add_argument("--width", type=int, metavar="COLUMNS", help="maximum reading measure (20–240; reader default 72)")
    reader.add_argument("--emphasis", choices=("auto", "italic", "underline"),
                        help="semantic emphasis presentation; auto falls back to underline")
    modes = parser.add_argument_group("Other actions (choose one)")
    mode = modes.add_mutually_exclusive_group()
    mode.add_argument("--structure", action="store_true", help="show the outline (prefer the indexed local corpus)")
    mode.add_argument("--guide", action="store_true", help="reader keys, examples, and book structure; same as sol guide")
    mode.add_argument("--shell", action="store_true", help="open the optional book command interface instead of the reader")
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
    mode.add_argument("--workspace-upgrade", type=Path, metavar="FILE", help="upgrade an older workspace into a separate verified copy")
    mode.add_argument("--workspace-list", action="store_true", help="list local workspaces without opening the reader or corpus")
    mode.add_argument("--workspace-delete", metavar="NAME", help="remove a workspace from use, retaining a recoverable private archive")
    mode.add_argument("--review-queue", action="store_true", help="show canonical pending transcriptions; optionally include workspace testimony")
    storage = parser.add_argument_group("Workspace storage and exports")
    storage.add_argument("--workspace-dir", type=Path, metavar="DIRECTORY", help="local workspace database directory (default XDG data directory)")
    storage.add_argument("--export-format", choices=("json", "markdown"),
                        help="format for --workspace-export (default JSON)")
    storage.add_argument("--include-passages", action="store_true",
                        help="include current referenced canonical Markdown in a Markdown workspace export")
    storage.add_argument("--resume-revision", type=int, metavar="N", help="with --resume, restore a historical checkpoint as a new visit")
    prompt = parser.add_argument_group("Optional book command interface (--shell)")
    prompt.add_argument("--ui", choices=("auto", "basic", "prompt"), help="command input: enhanced prompt or basic input (default auto)")
    prompt.add_argument("--editing-mode", choices=("emacs", "vi"), help="editing keys for the command prompt")
    source = parser.add_argument_group("Corpus selection").add_mutually_exclusive_group()
    source.add_argument("--corpus", type=Path, metavar="DIRECTORY",
                        help="canonical corpus for this run (otherwise discover a local or saved corpus)")
    source.add_argument("--pdf", type=Path, metavar="PATH",
                        help="explicit legacy PDF reading (slow; not used for ordinary reading)")
    prompt.add_argument("--source-pdf", type=Path, metavar="PATH",
                        help="local evidence PDF for source viewing in the canonical shell")
    printing = parser.add_argument_group("One-shot output and outline options")
    printing.add_argument("--within", metavar="PATH", help="restrict --search to this subtree")
    printing.add_argument("--word", action="store_true", help="whole-word --search rather than substring")
    printing.add_argument("--limit", type=int, metavar="N", help="maximum search results (1–1000; default 20)")
    printing.add_argument("--context", type=int, metavar="N", help="neighbors around --passage (0–10 on each side)")
    printing.add_argument("--depth", type=int, metavar="N", help="outline depth (0–32; guide default 1)")
    output = printing.add_mutually_exclusive_group()
    output.add_argument("--plain", action="store_true", help="passage text without metadata or ANSI styling")
    output.add_argument("--json", action="store_true", help="structured output for scripts")
    return parser
