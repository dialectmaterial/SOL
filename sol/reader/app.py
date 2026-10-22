#!/usr/bin/env python3
"""SOL: a terminal reader for the Cambridge *Science of Logic*.

Canonical local Markdown is indexed once and read through a verified JSONL
index using standard-library Python. Corpus loading and the terminal interface
stay separate.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path


from sol.corpus.edition import PDF_FILENAME, ROOT
from sol.core.config import (
    config_path, configured_corpus, configured_theme, discover_corpus, installed_project_directory,
    save_corpus, save_theme, source_project_directory,
)
from sol.core.models import Book, Node, Passage, node_path, presentation_text
from sol.core.paths import alias, child_by_name, display_path
from sol.core.paths import resolve_path as resolve_book_path
from sol.presentation.theme import (DEFAULT_READER_THEME, DEFAULT_READER_WIDTH,
                                    LEGACY_READER_THEMES, READER_THEMES)
from sol.reader.options import (ExecutionMode, build_parser, validate_options,
                                validate_workspace_management)
from sol.reader.actions import ReaderActions, ReadingSession, context_passages
from sol.reader.launch import interactive_input_available, shell_identity
from sol.presentation.text import display_text, safe_output
from sol.reader.render import (    sensible_width, page_range, source_line, fold_path, fold_body, render_passage,
    passage_data, render_context, render_search_results, location_data, render_info,
    render_listing, render_tree, render_guide)


def run_shell(*args, **kwargs):
    """Import the minimal book command interface only when selected."""
    from sol.reader.shell import run_shell as run
    return run(*args, **kwargs)


def load_corpus_book(corpus: Path) -> Book:
    """Compatibility entry point for the shared verified-corpus loader."""
    from sol.core.corpus import load_corpus_book as load_canonical_book

    return load_canonical_book(corpus)


def resolve_path(value: str | None, cwd: tuple[str, ...], root: Node = ROOT) -> tuple[Node, tuple[str, ...]]:
    """Keep the reader's edition-outline default over the shared path resolver."""
    return resolve_book_path(value, cwd, root)


def run_reader(book: Book, workspace_reader=None, *, width=DEFAULT_READER_WIDTH,
               emphasis="auto", theme=DEFAULT_READER_THEME) -> int:
    """Load the terminal adapter only for interactive reading."""
    from sol.terminal.neovim_reader import run_reader as run_view

    return run_view(book, workspace_reader, width=width, emphasis=emphasis, theme=theme)


def tree_data(node: Node, depth: int | None = None) -> dict:
    return {
        "title": node.title, "path": display_path(node_path(node)), "name": node.name,
        "directory": node.is_directory, "printed_page": node.start_page,
        "truncated": depth == 0 and bool(node.children),
        "children": [] if depth == 0 else [
            tree_data(child, None if depth is None else depth - 1) for child in node.children
        ],
    }


def run_workspace_management(args) -> int:
    """An exact delete request archives personal data; it never opens a book."""
    from sol.workspace.lifecycle import delete_workspace, list_workspaces
    from sol.workspace.reader import safe_output

    if args.workspace_list:
        rows = list_workspaces(args.workspace_dir)
        if args.json:
            emit_json(rows)
        elif rows:
            print("Local workspaces:")
            for row in rows:
                print(f"  {row['name']}  (schema {row['schema_version']})")
            print("\nRemove one recoverably: sol --workspace-delete NAME")
        else:
            print("No recognized local workspaces.")
        return 0
    result = delete_workspace(args.workspace_delete, args.workspace_dir)
    from sol.workspace.launch import forget_workspace
    try:
        forget_workspace(Path(result["path"]))
    except ValueError as error:
        # Removal has already succeeded. Report its recovery location even if
        # an unrelated damaged preferences file could not be cleaned up.
        result["preferences_warning"] = str(error)
        print("sol: workspace removed, but its launch preference could not be cleared: "
              + safe_output(str(error)), file=sys.stderr)
    if args.json:
        emit_json(result)
    else:
        print(f"Removed workspace: {result['name']}")
        print("Recoverable database: " + safe_output(result["recovery_path"]))
        print("Actor profiles and the canonical corpus were not changed.")
    return 0


def terminal_color() -> bool:
    return bool(sys.stdout.isatty() and "NO_COLOR" not in os.environ
                and os.environ.get("TERM") != "dumb")


def emit_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=True, indent=2))


def run_workspace_cli(book: Book, args, width: int, color: bool) -> int:
    """Named durable state, kept separate from corpus-only one-shot reading."""
    from sol.workspace.store import SCHEMA_VERSION, Workspace
    from sol.workspace.reader import WorkspaceReader, workspace_path

    identity = book.corpus_manifest.get("corpus_id")
    if not identity:
        directory = shlex.quote(str(book.corpus_directory))
        raise ValueError("this corpus needs an explicit permanent identity before workspace use.\n"
                         f"Run once: sol-corpus-check {directory} --initialize-identity\n"
                         "This preserves canonical text and passage IDs; do not reconvert the PDF.")
    location = workspace_path(args.workspace, args.workspace_dir)
    if (args.resume or args.workspace_export or args.workspace_check or args.workspace_backup is not None
            or args.workspace_upgrade is not None
            or args.review_queue) and not location.exists():
        raise ValueError(f"workspace does not exist: {args.workspace}; start reading with sol --workspace NAME")
    provenance = {"edition": book.corpus_manifest["edition"], "source": book.corpus_manifest["source"]}
    with Workspace(location, identity, provenance, actor=args.actor or "Reader") as store:
        reader = WorkspaceReader(book, store, args.actor, resolve_path, display_path,
                                 render_passage, width, args.plain, color)
        if args.workspace_export:
            print(display_text(reader.export_text(args.export_format or 'json', include_passages=args.include_passages)))
            return 0
        if args.workspace_check:
            report = reader.health()
            if args.json:
                emit_json(report)
            else:
                print(reader.render_health(report))
            return 0
        if args.review_queue:
            within = None if args.within is None else resolve_path(args.within, (), book.root)[1]
            rows = reader.queue(within, 20 if args.limit is None else args.limit)
            if args.json:
                emit_json(rows)
            else:
                print(reader.render_queue(rows))
            return 0
        if args.workspace_backup is not None:
            destination = store.backup(args.workspace_backup)
            if args.json:
                emit_json({"backup": str(destination), "corpus_id": identity})
            else:
                print(display_text(f"Verified workspace backup: {destination}"))
            return 0
        if args.workspace_upgrade is not None:
            reader.ensure_corpus_current()
            requested = args.workspace_upgrade.expanduser().absolute()
            if requested.name != workspace_path(requested.stem, requested.parent).name:
                raise ValueError("an upgraded workspace filename must end in lowercase .sqlite3 "
                                 "so reopening its workspace name selects the same file")
            destination = store.upgrade_copy(requested)
            result = {"upgraded_copy": str(destination), "source_workspace": str(store.path),
                      "schema_version": SCHEMA_VERSION, "corpus_id": identity}
            if args.json:
                emit_json(result)
            else:
                print(display_text(f"Verified upgraded copy: {destination}\nOriginal workspace retained.\n"
                      f"Open with: sol --workspace {shlex.quote(destination.stem)} "
                      f"--workspace-dir {shlex.quote(str(destination.parent))}"))
            return 0
        if args.reader:
            # Personal launch preferences are separate from the workspace
            # schema and are saved only after the selected store/service have
            # validated. One-shot inspection never changes the next author.
            from sol.workspace.launch import remember_launch
            from sol.workspace.profiles import register_actor
            register_actor(args.actor)
            remember_launch(args.actor, store.path, identity, book.corpus_manifest['source']['sha256'])
            return run_reader(book, reader, width=args.width or DEFAULT_READER_WIDTH,
                              emphasis=args.emphasis or "auto", theme=args.theme)
        actions = ReaderActions(book, reader, session=ReadingSession(book))
        if args.resume:
            passage, message = actions.restore(args.resume_revision)
            if message:
                print(message, file=sys.stderr)
            # Latest resume is inspection; a historical resume appends a new visit.
        elif args.passage is not None:
            passage = actions.open(args.passage)
        else:
            value = args.first if args.first is not None else args.read
            _, path = actions.locate(value)
            passage = actions.read(path, args.first is not None)
        if args.json:
            data = passage_data(passage, book)
            data["workspace"] = {"name": args.workspace, "corpus_id": identity,
                                 "revision": reader.revision,
                                 "requested_id": reader.resumed_reference.requested_id
                                 if reader.resumed_reference else passage.identifier}
            emit_json(data)
        else:
            print(render_passage(passage, width, args.plain, color))
        return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "essence":
        from sol.essence.cli import main as analyze_main
        return analyze_main(arguments[1:])
    if arguments and arguments[0] == "reference":
        from sol.terminal.reference import main as reference_main
        return reference_main(arguments[1:])
    if arguments and arguments[0] == "read":
        from sol.terminal.commands import main as command_main
        return command_main(arguments)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        mode = validate_options(args)
        validate_workspace_management(args)
        if mode in (ExecutionMode.WORKSPACE_LIST, ExecutionMode.WORKSPACE_DELETE):
            return run_workspace_management(args)
        if mode in (ExecutionMode.READER, ExecutionMode.DYNAMIC_STRUCTURE):
            # Refuse an unavailable view before corpus discovery, onboarding,
            # actor registration or opening/creating a personal workspace.
            from sol.terminal.neovim import validate_environment
            validate_environment(args.width or DEFAULT_READER_WIDTH)
            args.theme = args.theme or configured_theme(READER_THEMES, LEGACY_READER_THEMES) or DEFAULT_READER_THEME
            # The opening screen covers loading; it steps aside for any prompt.
            from sol.terminal import splash
            splash.start(args.theme)
        if mode is ExecutionMode.SET_THEME:
            configuration = save_theme(args.set_theme, READER_THEMES)
            if args.json:
                emit_json({"theme": args.set_theme, "configuration": str(configuration)})
            else:
                print(display_text(f"Reader theme: {args.set_theme}\nSaved in: {configuration}"))
            return 0
        if mode is ExecutionMode.SET_CORPUS:
            corpus, configuration = save_corpus(args.set_corpus)
            if args.json:
                emit_json({"corpus": str(corpus), "configuration": str(configuration)})
            else:
                print(display_text(f"Default corpus: {corpus}\nSaved in: {configuration}"))
            return 0
        width = sensible_width(args.width)
        color = terminal_color() and not args.plain and not args.json
        if mode is ExecutionMode.GUIDE and args.corpus is None:
            # The guide must still explain setup when an automatic source is broken.
            try:
                corpus = discover_corpus()
                book = load_corpus_book(corpus) if corpus is not None else None
            except ValueError as error:
                print(f"sol: {error}\nShowing the abbreviated visual guide.", file=sys.stderr)
                book = None
            print(render_guide(book, width, 1 if args.depth is None else args.depth))
            return 0
        corpus = discover_corpus(args.corpus)
        if corpus is not None:
            book = load_corpus_book(corpus)
        else:
            if mode is ExecutionMode.GUIDE:
                print(render_guide(width=width, depth=1 if args.depth is None else args.depth))
                return 0
            if mode is ExecutionMode.STRUCTURE:
                if args.json:
                    emit_json({"outline": tree_data(ROOT, args.depth), "abbreviated": True})
                else:
                    print(render_tree(depth=args.depth))
                    print("\nAbbreviated outline. Select a corpus with --set-corpus DIRECTORY for subdivisions.")
                return 0
            if mode.interactive:
                from sol.reader.onboarding import prepare_first_corpus
                _close_splash()
                book = prepare_first_corpus()
            else:
                raise ValueError(f"No local corpus found. Run sol in a terminal to import the supported {PDF_FILENAME}, "
                                 "or select an existing corpus with sol --set-corpus DIRECTORY.")
        if mode.personal and not args.none:
            shell_identity(book, args)
        if args.workspace is not None:
            return run_workspace_cli(book, args, width, color)
        if mode is ExecutionMode.SET_SOURCE_PDF:
            from sol.terminal.source import SourceService
            location = SourceService(book).set_pdf(args.set_source_pdf)
            if args.json:
                emit_json({"source_pdf": str(location)})
            else:
                print(display_text(f"Source PDF verified and remembered: {location}\n"
                                   "Press s in the reader to see a passage's printed source."))
            return 0
        if mode is ExecutionMode.REVIEW_QUEUE:
            from sol.workspace.diagnostics import review_queue
            from sol.workspace.reader import render_review_queue
            within = None if args.within is None else resolve_path(args.within, (), book.root)[1]
            rows = review_queue(book, {"reviews": []}, within, 20 if args.limit is None else args.limit)
            if args.json:
                emit_json(rows)
            else:
                print(render_review_queue(rows, width))
            return 0
        if mode is ExecutionMode.STRUCTURE:
            if args.json:
                emit_json({"outline": tree_data(book.root, args.depth), "abbreviated": False})
            else:
                print(render_tree(book.root, depth=args.depth))
        elif mode is ExecutionMode.DYNAMIC_STRUCTURE:
            from sol.terminal.neovim_reader import run_reader as run_native_reader
            return run_native_reader(book, width=args.width or DEFAULT_READER_WIDTH,
                                     start_tree=True, tree_depth=args.depth or 2, theme=args.theme)
        elif mode is ExecutionMode.GUIDE:
            print(render_guide(book, width, 1 if args.depth is None else args.depth))
        elif mode is ExecutionMode.READER:
            return run_reader(book, width=args.width or DEFAULT_READER_WIDTH, emphasis=args.emphasis or "auto",
                              theme=args.theme)
        elif mode is ExecutionMode.SHELL:
            return run_shell(book, width, args.plain, color, auto_width=args.width is None)
        elif mode is ExecutionMode.SEARCH:
            _, path = resolve_path(args.within, (), book.root)
            passages = book.search(args.search, path, args.word,
                                   20 if args.limit is None else args.limit)
            if args.json:
                emit_json([passage_data(passage, book) for passage in passages])
            elif args.plain:
                print("\n\n".join(render_passage(passage, width, plain=True) for passage in passages))
            else:
                print(render_search_results(passages, args.search, width, args.word))
        elif mode is ExecutionMode.INFO:
            node, path = resolve_path(args.info, (), book.root)
            if args.json:
                emit_json(location_data(book, node, path))
            else:
                print(render_info(book, node, path, width))
        elif mode is ExecutionMode.PASSAGE:
            passage = book.find_passage(args.passage)
            if args.context is not None:
                if args.json:
                    emit_json([passage_data(item, book) for item in context_passages(book, passage, args.context)])
                else:
                    print(render_context(book, passage, args.context, width, args.plain, color))
            elif args.json:
                emit_json(passage_data(passage, book))
            else:
                print(render_passage(passage, width, args.plain, color))
        elif mode is ExecutionMode.CAT:
            node, path = resolve_path(args.cat, (), book.root)
            if node.is_directory:
                raise ValueError("--cat takes a virtual file")
            if args.json:
                emit_json([passage_data(passage, book) for passage in book.selection(path)])
            else:
                for passage in book.selection(path):
                    print(render_passage(passage, width, args.plain, color), end="\n\n")
        else:
            value = args.first if args.first is not None else args.read
            _, path = resolve_path(value, (), book.root)
            passage = ReaderActions(book, session=ReadingSession(book)).read(path, args.first is not None)
            if args.json:
                emit_json(passage_data(passage, book))
            else:
                print(render_passage(passage, width, args.plain, color))
        return 0
    except ValueError as error:
        _close_splash()
        print("sol: " + safe_output(error), file=sys.stderr)
        return 2
    except RuntimeError as error:
        _close_splash()
        print("sol: " + safe_output(error), file=sys.stderr)
        return 1
    except EOFError:
        _close_splash()
        print("\nsol: setup cancelled; no workspace or actor was created", file=sys.stderr)
        return 0


def cli(argv: list[str] | None = None) -> int:
    """Console entry shared by pipx and direct script execution."""
    try:
        status = main(argv)
        sys.stdout.flush()
        return status
    except KeyboardInterrupt:
        _close_splash()
        print("\nsol: interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:
        # Avoid a second broken-pipe error while Python flushes at shutdown.
        try:
            with open(os.devnull, "w") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        except (OSError, AttributeError, ValueError):
            pass
        return 0
    finally:
        _close_splash()


def _close_splash():
    """A refusal or error before Neovim starts must not leave the opening
    screen up; once Neovim has drawn it is already gone and this does nothing."""
    if "sol.terminal.splash" in sys.modules:
        sys.modules["sol.terminal.splash"].stop()


if __name__ == "__main__":
    raise SystemExit(cli())
