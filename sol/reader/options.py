"""Reader command-line arguments without loading a book or interface."""

from __future__ import annotations

import argparse
from enum import Enum
import re
from pathlib import Path

from sol import __version__ as VERSION

DEFAULT_READER_WIDTH = 66
# Presentation presets; their highlight data lives in sol.terminal.theme.
# Paper and Night are SOL's own, from actualspirit.com; Catppuccin Mocha and
# Latte (catppuccin.com); Terminal inherits your own colors.
READER_THEMES = ("mocha", "latte", "paper", "night", "terminal")
DEFAULT_READER_THEME = "mocha"
# A name saved before Catppuccin replaced the earlier Dark preset.
LEGACY_READER_THEMES = {"dark": "mocha"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sol", usage="%(prog)s [being] [OPTIONS]\n       %(prog)s guide [--depth N]\n       %(prog)s {read,reference,essence} --help",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="SOL Organizes Logic\n\n"
                    "Read Hegel's Science of Logic directly in your terminal.\n"
                    "sol opens the reader at the last actor's saved workspace and position.\n"
                    "First use imports your supported PDF, then sets up your reading workspace.",
        epilog="Start here:\n"
               "  sol                         resume reading (the same as sol being)\n"
               "  sol -n                      read without a workspace or actor\n"
               "  sol --dynamic-structure     explore the book tree interactively\n"
               "  sol --actor NAME            use that actor's last workspace\n"
               "  sol --workspace NAME        choose a different workspace\n"
               "  sol guide                   reader keys, examples, and book structure\n"
               "  sol -r                      print one random passage and leave\n\n"
               "Reader keys: j/k lines, b/n paragraphs, p reading mode, / search,\n"
               "m1-3 markers, y copy, t tree, c context, f focus, ? help, :q save and quit.\n"
               "Runs in ordinary capable terminals; no particular emulator is required.\n"
               "--shell opens a minimal command interface for browsing the book.\n"
               "sol read, sol reference and sol essence have their own --help.")
    parser.add_argument("command", nargs="?", choices=("being", "guide"),
                        help="being: the reader (also bare sol); guide: reader guide and a small book tree")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    reader = parser.add_argument_group("Reader: sol being (the default)")
    reader.add_argument("-n", "--none", action="store_true", help="read without saving; no workspace or actor")
    reader.add_argument("--workspace", metavar="NAME", help="open this workspace instead of the actor's last one")
    reader.add_argument("--actor", metavar="NAME", help="name attributed to your personal notes; remembers that actor's workspace")
    reader.add_argument("--width", type=int, metavar="COLUMNS", help="maximum reading measure (20–240; reader default 66)")
    reader.add_argument("--emphasis", choices=("auto", "italic", "underline"),
                        help="semantic emphasis presentation; auto falls back to underline")
    reader.add_argument("--theme", choices=READER_THEMES,
                        help="reading preset for this session (default: saved theme, else mocha); T cycles it")
    modes = parser.add_argument_group("Other actions (choose one)")
    mode = modes.add_mutually_exclusive_group()
    mode.add_argument("--structure", action="store_true", help="show the outline (prefer the indexed local corpus)")
    mode.add_argument("--dynamic-structure", action="store_true",
                      help="open the reader's book outline directly (temporary session)")
    mode.add_argument("--guide", action="store_true", help="reader keys, examples, and book structure; same as sol guide")
    mode.add_argument("--shell", action="store_true", help="browse the book in a minimal command interface; saves nothing")
    mode.add_argument("-r", "--random", action="store_true", help="print a random passage and leave")
    mode.add_argument("--read", metavar="PATH", help="read a random paragraph within a virtual path")
    mode.add_argument("--first", metavar="PATH", help="read the first paragraph within a virtual path")
    mode.add_argument("--cat", metavar="FILE", help="display a virtual file completely, in book order")
    mode.add_argument("--search", metavar="QUERY", help="literal case-insensitive passage search")
    mode.add_argument("--passage", metavar="ID", help="open a passage by exact ID or unique prefix")
    mode.add_argument("--info", metavar="PATH", help="show location, source range, and passage counts")
    mode.add_argument("--set-corpus", type=Path, metavar="DIRECTORY",
                      help="validate and remember the default corpus for reading from any directory")
    mode.add_argument("--set-source-pdf", type=Path, metavar="PATH",
                      help="verify and remember the corpus's original PDF for source previews (s in the reader)")
    mode.add_argument("--set-theme", choices=READER_THEMES, metavar="{" + ",".join(READER_THEMES) + "}",
                      help="remember the reader's theme: Catppuccin mocha (dark) or latte (light); SOL's paper (light) or night (dark); terminal inherits your colors")
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
    parser.add_argument_group("Corpus selection").add_argument(
        "--corpus", type=Path, metavar="DIRECTORY",
        help="canonical corpus for this run (otherwise discover a local or saved corpus)")
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


class ExecutionMode(str, Enum):
    """One interpreted action, independent of the spelling used to select it."""
    READER = "reader"
    SHELL = "shell"
    GUIDE = "guide"
    STRUCTURE = "structure"
    DYNAMIC_STRUCTURE = "dynamic_structure"
    RANDOM = "random"
    READ = "read"
    FIRST = "first"
    CAT = "cat"
    SEARCH = "search"
    PASSAGE = "passage"
    INFO = "info"
    SET_CORPUS = "set_corpus"
    SET_THEME = "set_theme"
    SET_SOURCE_PDF = "set_source_pdf"
    RESUME = "resume"
    WORKSPACE_EXPORT = "workspace_export"
    WORKSPACE_CHECK = "workspace_check"
    WORKSPACE_BACKUP = "workspace_backup"
    WORKSPACE_UPGRADE = "workspace_upgrade"
    WORKSPACE_LIST = "workspace_list"
    WORKSPACE_DELETE = "workspace_delete"
    REVIEW_QUEUE = "review_queue"

    @property
    def interactive(self) -> bool:
        return self in (ExecutionMode.READER, ExecutionMode.SHELL)

    @property
    def personal(self) -> bool:
        """Only the reader keeps a workspace and an actor; the shell saves nothing."""
        return self is ExecutionMode.READER


def _selected_actions(args):
    return [mode for mode in ExecutionMode
            if mode not in (ExecutionMode.READER, ExecutionMode.SHELL)
            and getattr(args, mode.value) is not None
            and getattr(args, mode.value) is not False]


def select_execution_mode(args: argparse.Namespace) -> ExecutionMode:
    actions = _selected_actions(args)
    if args.command == "being" and (args.shell or actions):
        raise ValueError("sol being opens the reader; it cannot be combined with --shell or another action")
    if actions:
        return actions[0]
    return ExecutionMode.SHELL if args.shell else ExecutionMode.READER


def validate_options(args: argparse.Namespace) -> ExecutionMode:
    management = bool(getattr(args, "workspace_list", False) or
                      getattr(args, "workspace_delete", None) is not None)
    if args.command == "guide":
        if _selected_actions(args) or args.shell or args.none:
            raise ValueError("guide cannot be combined with another action")
        args.guide = True
    if management:
        # Management validation owns its smaller surface and runs before I/O.
        return ExecutionMode.WORKSPACE_LIST if args.workspace_list else ExecutionMode.WORKSPACE_DELETE
    if args.none and _selected_actions(args):
        raise ValueError("-n/--none is a temporary interactive session; omit one-shot/guide actions")
    mode = select_execution_mode(args)
    args.reader = mode is ExecutionMode.READER
    if mode is ExecutionMode.DYNAMIC_STRUCTURE:
        if args.workspace is not None or args.actor is not None or args.plain or args.json:
            raise ValueError("--dynamic-structure uses a temporary Neovim tree; omit workspace/output options")
        if args.depth is not None and not 1 <= args.depth <= 6:
            raise ValueError("dynamic tree depth must be between 1 and 6")
    if args.reader:
        if args.plain or args.json:
            raise ValueError("the reader is interactive; omit --plain and --json")
    elif args.emphasis is not None:
        raise ValueError("--emphasis belongs to the reader (sol being)")
    if args.theme is not None and not args.reader and mode is not ExecutionMode.DYNAMIC_STRUCTURE:
        raise ValueError("--theme selects the interactive reader's presentation; use --set-theme to save one")
    if args.shell and (args.workspace is not None or args.actor is not None or args.workspace_dir is not None):
        raise ValueError("the shell browses the book and saves nothing; omit workspace and actor options")
    if args.none and (args.workspace is not None or args.actor is not None or args.workspace_dir is not None):
        raise ValueError("-n/--none does not use a workspace or actor; omit workspace options")
    if args.word and args.search is None:
        raise ValueError("--word requires --search")
    if args.search is None and not args.review_queue and (args.within is not None or args.limit is not None):
        raise ValueError("--within and --limit require --search or --review-queue")
    if args.search is not None and not args.search.strip():
        raise ValueError("search requires a nonempty query")
    if args.limit is not None and not 1 <= args.limit <= 1000:
        raise ValueError("--limit must be between 1 and 1000")
    if args.context is not None:
        if args.passage is None:
            raise ValueError("--context requires --passage")
        if not 0 <= args.context <= 10:
            raise ValueError("--context must be between 0 and 10")
    if args.depth is not None:
        if not args.structure and not args.guide and not args.dynamic_structure:
            raise ValueError("--depth requires --structure, --dynamic-structure or guide")
        if not 0 <= args.depth <= 32:
            raise ValueError("--depth must be between 0 and 32")
    if args.json and (args.shell or args.guide):
        raise ValueError("--json is not a shell/guide mode; use sol -r --json for a random passage")
    if args.set_corpus is not None and args.corpus is not None:
        raise ValueError("--set-corpus cannot be combined with --corpus")
    if args.workspace is None and not mode.personal and (args.workspace_dir is not None or args.actor is not None or args.resume
                                   or args.workspace_export or args.workspace_check or args.workspace_backup is not None
                                   or args.workspace_upgrade is not None):
        raise ValueError("workspace options require --workspace NAME")
    if args.resume_revision is not None and (not args.resume or args.resume_revision < 1):
        raise ValueError("--resume-revision requires --resume and a positive checkpoint revision")
    if args.workspace is not None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.workspace):
            raise ValueError("workspace name must contain 1–64 letters, numbers, underscores or hyphens")
        if args.actor is not None and not args.actor.strip():
            raise ValueError("--actor requires a nonempty name")
        if args.set_corpus is not None or args.set_source_pdf is not None or args.guide or args.structure:
            raise ValueError("--workspace cannot accompany --set-corpus or an outline action")
        if args.search is not None or args.info is not None or args.cat is not None:
            raise ValueError("--workspace is available for reading, --resume and the workspace commands")
        if args.context is not None:
            raise ValueError("workspace reading does not yet save a context view; use --passage ID --context N without --workspace")
    if args.workspace_export and args.plain:
        raise ValueError("--workspace-export emits an artifact, not plain passage output; omit --plain")
    if args.export_format is not None and not args.workspace_export:
        raise ValueError("--export-format requires --workspace-export")
    if args.workspace_export and args.export_format == "markdown" and args.json:
        raise ValueError("--json cannot accompany a Markdown export; omit --json or choose --export-format json")
    if args.include_passages and not (args.workspace_export and args.export_format == "markdown"):
        raise ValueError("--include-passages requires --workspace-export --export-format markdown")

    return mode


def validate_workspace_management(args) -> None:
    """Keep local-data management independent of book and reader setup."""
    if not (args.workspace_list or args.workspace_delete is not None):
        return
    allowed = {"workspace_list", "workspace_delete", "workspace_dir", "json"}
    incompatible = ["--" + key.replace("_", "-") for key, value in vars(args).items()
                    if key not in allowed and value is not None and value is not False]
    if incompatible:
        raise ValueError("workspace listing/removal accepts only --workspace-dir and --json; omit "
                         + ", ".join(incompatible))
