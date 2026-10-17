"""Optional book command interface and its terminal integrations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex

from sol.core.models import Book, Node
from sol.core.paths import display_path, resolve_path
from sol.reader.actions import ReaderActions, ReadingSession
from sol.terminal.text import display_text, safe_output
from sol.reader.render import (render_guide, render_info, render_listing, render_neofetch,
                               render_passage, render_search_results, render_tree, sensible_width)


def install_completion(root: Node, get_cwd, workspace: bool = False):
    """Optional standard-library tab completion; safe on systems without readline."""
    try:
        import readline
    except ImportError:
        return lambda: None
    old_completer = readline.get_completer()
    old_delimiters = readline.get_completer_delims()
    commands = ("ls", "cd", "up", "pwd", "tree", "read", "first", "next", "previous",
                "cat", "search", "open", "context", "info", "where", "guide", "neofetch", "source", "essence", "help", "exit")
    if workspace:
        commands += ("workspace", "resume", "bookmark", "note", "compare", "review", "relate")
    def complete(text: str, state: int):
        try:
            buffer = readline.get_line_buffer()
            if " " not in buffer:
                choices = [command for command in commands if command.startswith(text)]
            elif buffer.startswith("source "):
                choices = [action for action in ("show", "close", "set-pdf", "info")
                           if action.startswith(text)] if buffer.count(" ") == 1 else []
            elif buffer.startswith("essence "):
                choices = [action for action in ("open", "check", "return", "close")
                           if action.startswith(text)] if buffer.count(" ") == 1 else []
            else:
                parent, _, fragment = text.rpartition("/")
                node, _ = resolve_path(parent + "/" if "/" in text else None, get_cwd(), root)
                choices = [
                    (parent + "/" if "/" in text else "") + child.name
                    + ("/" if child.is_directory else "")
                    for child in node.children if child.name.casefold().startswith(fragment.casefold())
                ]
            return choices[state] if state < len(choices) else None
        except (ValueError, IndexError):
            return None
    readline.set_completer_delims(" \t\n")
    readline.set_completer(complete)
    readline.parse_and_bind("tab: complete")
    def restore():
        readline.set_completer(old_completer)
        readline.set_completer_delims(old_delimiters)
    return restore


SHELL_HELP = """ls [PATH]                         list files and divisions
cd [PATH]                         navigate (/ root; .. parent; - previous)
up                                move to the parent directory
pwd                               print the current directory
tree [PATH] --depth N              show the outline; default is the full tree
read [PATH]                        read randomly and set the reading cursor
first [PATH]                       start the selection in book order
next / previous                   move within the reading selection
cat FILE                          display the complete file in book order
search QUERY [PATH] --word --limit N
                                  literal search (default: current subtree)
open ID|RESULT                    open a passage or latest search result
context [N]                       neighbors in book order (default 1; maximum 10)
where                             show current passage and reading position
info [PATH]                       title, pages, counts, and pending review
essence [open|check|return|close]   explicit reference handoff to a real zsh pane
essence return --accept-move       accept after deliberately changing reading position
compare PATH_A PATH_B              open complete files together in kitty
compare open / close              refresh the last desk / close it
guide [PATH] --depth N             beginner guide and book tree (default depth 1)
neofetch                          ASCII Hegel and SOL's concept-preview identity
help / exit                       show commands / leave SOL
Search does not move the reading cursor. Context can cross file boundaries.
Quote multiword queries. Paths accept aliases; Tab completes full names.
This is a book-navigation shell: type one command per line."""


class ShellParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def shell_options(verb: str, arguments: list[str]) -> argparse.Namespace:
    parser = ShellParser(prog=verb, add_help=False)
    if verb == "search":
        parser.add_argument("query")
        parser.add_argument("path", nargs="?")
        parser.add_argument("--word", action="store_true")
        parser.add_argument("--limit", type=int, default=20)
    else:
        parser.add_argument("path", nargs="?")
        parser.add_argument("--depth", type=int, default=1 if verb == "guide" else None)
    return parser.parse_args(arguments)


def run_shell(book: Book, width: int, plain: bool = False, color: bool = False,
              workspace_reader=None, read_command=None, write_output=None,
              ui_mode="basic", editing_mode="emacs", draft_reader=None,
              source_pdf=None, source_pane=None, auto_width=False, comparison_pane=None,
              essence_pane=None) -> int:
    """Run the linear shell through replaceable, synchronous input/output seams.

    The optional adapter owns completion and accepts one command at a time;
    workspace operations remain unchanged. No third-party UI is required here.
    write_output follows print's calling convention, including end= for cat.
    """
    actions = ReaderActions(book, workspace_reader, session=ReadingSession(book))
    session = actions.session
    emit = write_output if write_output is not None else print
    restore = lambda: None
    adapter = None
    source_service = None
    last_comparison = None
    handoff = None
    handoff_origin = None
    handoff_accepted = False

    def reader_position():
        try:
            identifier = actions.current_reference_id()
        except ValueError:
            identifier = None
        return actions.cwd, actions.previous_cwd, session.path, session.cursor, identifier

    def reflow_current():
        nonlocal width
        if not auto_width:
            return
        current_width = sensible_width(None)
        if current_width == width:
            return
        width = current_width
        if workspace_reader is not None:
            workspace_reader.width = width
        try:
            current = session.current()
        except ValueError:
            return
        emit(render_passage(current, width, plain, color))

    try:
        emit("SOL. Type 'guide' to get started; 'help' for commands.")
        if workspace_reader is not None:
            emit(f"Workspace: {workspace_reader.store.path.stem}")
            emit("Actor: " + safe_output(workspace_reader.actor) if workspace_reader.actor else
                 "No actor selected; authored writes require --actor NAME.")
            if workspace_reader.store.get_state() is not None:
                try:
                    passage, message = actions.restore()
                    if message:
                        emit(message)
                    emit(render_passage(passage, width, plain, color))
                except ValueError as error:
                    emit(f"sol: saved position not restored: {safe_output(error)}\n"
                         "The reference is retained. Inspect the workspace or deliberately start another reading.")
        if read_command is None and ui_mode != "basic":
            from sol.terminal.prompt import create_adapter
            adapter = create_adapter(book, lambda: actions.cwd, workspace_reader, mode=ui_mode,
                                     plain=plain, editing_mode=editing_mode)
            if adapter is not None:
                read_command = adapter.read_command
                draft_reader = adapter.read_draft
        if read_command is None:
            restore = install_completion(book.root, lambda: actions.cwd, workspace=workspace_reader is not None)
        while True:
            try:
                command = (read_command if read_command is not None else input)(f"sol:{display_path(actions.cwd)}$ ")
            except EOFError:
                emit()
                return 0
            except KeyboardInterrupt:
                emit("\nType 'exit' to leave.")
                continue
            try:
                if not isinstance(command, str):
                    raise ValueError("command input must be text; adapters must signal cancellation or EOF explicitly")
                parts = shlex.split(command)
                if not parts:
                    continue
                verb, arguments = parts[0], parts[1:]
                if auto_width:
                    width = sensible_width(None)
                    if workspace_reader is not None:
                        workspace_reader.width = width
                if verb == "essence":
                    action = arguments[0] if arguments else "open"
                    if action not in {"open", "check", "return", "close"}:
                        raise ValueError("use essence open, essence check, essence return [--accept-move], or essence close")
                    extra = arguments[1:]
                    accept_move = extra == ["--accept-move"]
                    if extra and not (action == "return" and accept_move):
                        raise ValueError(f"essence {action}: unexpected arguments")
                    if action == "close":
                        if essence_pane is not None:
                            essence_pane.close()
                        try:
                            if handoff is not None:
                                handoff.close()
                        except (ValueError, OSError) as error:
                            raise ValueError(f"ESSENCE cleanup incomplete; data retained at {handoff.directory}: {error}") from error
                        finally:
                            handoff = handoff_origin = None
                            handoff_accepted = False
                        reflow_current()
                        emit("ESSENCE pane closed; its temporary reference exchange ended.")
                    elif action == "open":
                        if handoff is not None:
                            raise ValueError("An ESSENCE exchange is already active; close it before opening another")
                        from sol.terminal.handoff import HandoffSession
                        packet = actions.capture_active_reference()
                        if essence_pane is None:
                            from sol.terminal.kitty import EssencePane
                            essence_pane = EssencePane()
                        candidate = HandoffSession.create(packet)
                        try:
                            essence_pane.show(candidate.directory, book.corpus_directory)
                        except (ValueError, RuntimeError, OSError):
                            candidate.close()
                            raise
                        handoff, handoff_origin = candidate, reader_position()
                        handoff_accepted = False
                        reflow_current()
                        emit(f"ESSENCE opened for {packet['reference']['requested_id']}.\n"
                             "Switch to its zsh pane. Use sol reference return [ID] to propose a return.\n"
                             "Back here, use essence check, then essence return. No reading visit was saved.")
                    else:
                        if handoff is None:
                            raise ValueError("No ESSENCE exchange is active; read a passage and use essence first")
                        packet = handoff.read_return()
                        reference = actions.check_return_reference(packet)
                        if action == "check":
                            current = {"status": "accepted" if handoff_accepted else "ready",
                                       "requested_id": reference.requested_id, "target_id": reference.target_id,
                                       "sources": packet["reference"]["sources"],
                                       "reader_position_changed": reader_position() != handoff_origin}
                            emit(safe_output(json.dumps(current, ensure_ascii=True, indent=2)))
                            emit("Inspection only; no navigation or visit. " +
                                 ("Already accepted; finish native work before essence close." if handoff_accepted else
                                  "Use essence return to accept."))
                        else:
                            if handoff_accepted:
                                raise ValueError("This return was already accepted; close and reopen for another exchange")
                            if reader_position() != handoff_origin and not accept_move:
                                raise ValueError("Your reading position changed after this handoff. Inspect essence check, "
                                                 "then use essence return --accept-move to navigate deliberately")
                            passage = actions.accept_return_reference(packet)
                            handoff_accepted = True
                            emit(render_passage(passage, width, plain, color))
                            emit("Return accepted. The zsh pane remains open; finish its work before essence close.")
                    continue
                if verb == "compare" and (not arguments or arguments[0] not in {"save", "list", "show"}):
                    from sol.workspace.comparison import capture_comparison, capture_paths
                    action = arguments[0] if arguments else ""
                    if action == "close":
                        if len(arguments) != 1:
                            raise ValueError("compare close does not take a name")
                        if comparison_pane is not None:
                            comparison_pane.close()
                        reflow_current()
                        emit("Comparison desk closed.")
                        continue
                    operands = arguments[1:] if action == "open" else arguments
                    parser = ShellParser(prog="compare", add_help=False)
                    parser.add_argument("paths", nargs="*")
                    parser.add_argument("--question", default=None)
                    options = parser.parse_intermixed_args(operands)
                    if not options.paths and action == "open" and options.question is None:
                        if last_comparison is None:
                            raise ValueError("Choose two paths: compare PATH_A PATH_B. "
                                             "Or use compare open NAME for a saved comparison.")
                        kind, targets, question = last_comparison
                    elif action == "open" and len(options.paths) == 1 and options.question is None:
                        kind, targets, question = "saved", options.paths[0], ""
                    elif len(options.paths) == 2:
                        kind, targets, question = "paths", options.paths, options.question or ""
                    else:
                        raise ValueError("Choose two paths: compare PATH_A PATH_B [--question TEXT]. "
                                         "Use compare open NAME for a saved comparison.")
                    if kind == "saved":
                        if workspace_reader is None:
                            raise ValueError("compare open NAME requires a reading workspace; start with sol-kitty")
                        captured = capture_comparison(workspace_reader, targets)
                        remembered = (kind, targets, question)
                        captured["refresh_command"] = "compare open"
                    else:
                        captured = capture_paths(book, targets, cwd=actions.cwd, resolve_path=resolve_path,
                                                 workspace_reader=workspace_reader, question=question)
                        remembered = (kind, [s["path"] for s in captured["selections"]], question)
                    if comparison_pane is None:
                        from sol.terminal.kitty import ComparisonPane
                        comparison_pane = ComparisonPane()
                    comparison_pane.show(captured)
                    last_comparison = remembered
                    reflow_current()
                    if kind == "paths":
                        lines = ["Comparison desk opened."]
                        for label, card in zip(("A", "B"), captured["records"]):
                            lines.append(f"{label}: {card.get('display_path') or card['path']} ({len(card['members'])} text records)")
                        emit(safe_output("\n".join(lines)))
                    else:
                        emit(safe_output(f"Comparison desk: {captured['comparison']['name']}"))
                    emit("Select A or B in the desk to scroll that text. "
                         "Use compare open to refresh; compare close to close.")
                    continue
                if verb == "source":
                    from sol.terminal.source import SourceService
                    action = arguments[0] if arguments else "show"
                    targets = arguments[1:]
                    if action not in {"show", "close", "set-pdf", "info"}:
                        raise ValueError("use source show [UUID], source close, source set-pdf PATH, or source info")
                    if len(targets) > 1 or (action in {"close", "info"} and targets):
                        raise ValueError(f"source {action}: unexpected arguments")
                    if action == "close":
                        if source_pane is not None:
                            source_pane.close()
                        reflow_current()
                        emit("Source pane closed.")
                        continue
                    if source_service is None:
                        source_service = SourceService(book, source_pdf=source_pdf)
                    if action == "set-pdf":
                        if not targets:
                            raise ValueError("source set-pdf requires a local PDF path")
                        location = source_service.set_pdf(Path(targets[0]))
                        emit(safe_output(f"Verified source PDF remembered: {location}"))
                    elif action == "info":
                        emit(safe_output(json.dumps(source_service.inspect_info(), ensure_ascii=False, indent=2)))
                    else:
                        if source_pane is None:
                            from sol.terminal.kitty import SourcePane
                            source_pane = SourcePane()
                        identifier = targets[0] if targets else session.current().identifier
                        request = source_service.capture(identifier)
                        source_pane.show(request)
                        reflow_current()
                        emit(f"Source PDF verified; {len(request['sources'])} source page(s).\n"
                             f"Pinned source: {request['target_id']}\n"
                             "Use source show to refresh.")
                    continue
                if verb == "note" and arguments and arguments[0] == "edit" and len(arguments) == 2:
                    if workspace_reader is None:
                        raise ValueError("note edit requires a workspace and actor")
                    if draft_reader is None:
                        raise ValueError("multiline note editing requires the enhanced prompt; "
                                         "use note edit NOTE_ID \"TEXT\" --expect-revision N for basic input")
                    captured = workspace_reader.prepare_annotation_edit(arguments[1])
                    emit(f"Editing your annotation {captured.identifier} at revision {captured.revision}.\n"
                         "Ctrl-S saves; Ctrl-C cancels. Earlier revisions and original source binding are retained.")
                    try:
                        body = draft_reader("Edit personal note: ", default=captured.body)
                    except (KeyboardInterrupt, EOFError):
                        emit("Edit cancelled; nothing was saved.")
                        continue
                    record = workspace_reader.save_annotation_edit(captured, body)
                    emit(workspace_reader.annotation_edit_result(captured.revision, record))
                    continue
                if verb == "note" and arguments and arguments[0] == "draft":
                    if workspace_reader is None:
                        raise ValueError("note draft requires a workspace and actor")
                    if draft_reader is None:
                        raise ValueError("note draft requires the enhanced prompt in an interactive terminal; "
                                         "install .[shell] or use note add \"TEXT\"")
                    draft_options = ShellParser(prog="note draft", add_help=False)
                    draft_options.add_argument("--on", dest="identifier")
                    options = draft_options.parse_args(arguments[1:])
                    workspace_reader.require_author()
                    reference = workspace_reader.current_reference(session, options.identifier)
                    inspected_digest = reference.record['content_sha256']
                    inspected_target = reference.target_id
                    draft_actor = workspace_reader.actor
                    emit("Personal annotation draft. Ctrl-S saves; Ctrl-C cancels. Drafts are not stored in history.")
                    try:
                        body = draft_reader("Personal note: ")
                    except (KeyboardInterrupt, EOFError):
                        emit("Draft cancelled; nothing was saved.")
                        continue
                    workspace_reader.require_author()
                    if workspace_reader.actor != draft_actor or workspace_reader.store.actor != draft_actor:
                        raise ValueError("annotation actor changed during drafting; nothing was saved")
                    accepted = workspace_reader.current_reference(session, reference.requested_id)
                    if accepted.target_id != inspected_target or accepted.record['content_sha256'] != inspected_digest:
                        raise ValueError("annotation target changed during drafting; nothing was saved")
                    record = workspace_reader.store.add_annotation(reference.requested_id, body, inspected_digest)
                    emit(f"Personal annotation saved: {record['id']}\n{workspace_reader.authored(record)}")
                    continue
                if verb == "resume":
                    if len(arguments) > 1:
                        raise ValueError("resume takes at most one checkpoint revision")
                    if workspace_reader is None:
                        raise ValueError("resume requires starting SOL with --workspace NAME")
                    revision = int(arguments[0]) if arguments else None
                    passage, message = actions.restore(revision)
                    if message:
                        emit(message)
                    emit(render_passage(passage, width, plain, color))
                    continue
                if verb in {"workspace", "bookmark", "note", "compare", "review", "relate"}:
                    if workspace_reader is None:
                        raise ValueError(f"{verb} requires starting SOL with --workspace NAME")
                    outcome = workspace_reader.execute(verb, arguments, session)
                    if outcome.open_id:
                        passage = actions.open(outcome.open_id)
                        emit(render_passage(passage, width, plain, color))
                    if outcome.text:
                        emit(safe_output(outcome.text))
                    continue
                if verb in {"search", "tree", "guide"}:
                    options = shell_options(verb, arguments)
                    node, path = actions.locate(options.path)
                    if verb == "search":
                        matches = actions.search(options.query, path, options.word, options.limit)
                        emit(render_search_results(matches, options.query, width, options.word))
                    elif verb == "tree":
                        emit(render_tree(node, depth=options.depth))
                    else:
                        emit(render_guide(book, width, options.depth, node))
                    continue
                if len(arguments) > 1:
                    raise ValueError(f"{verb} expects at most one argument")
                argument = arguments[0] if arguments else None
                if verb in {"exit", "quit"}:
                    if argument is not None:
                        raise ValueError(f"{verb} does not take an argument")
                    return 0
                if verb == "help":
                    if argument is not None:
                        raise ValueError("help does not take an argument")
                    emit(SHELL_HELP)
                    emit("\nsource show [UUID]   view verified source pages in the SOL kitty desk\n"
                         "source close         close the source pane\n"
                         "source set-pdf PATH  verify and remember this edition's local PDF\n"
                         "source info          inspect the source-file association")
                    if workspace_reader is not None:
                        from sol.workspace.commands import WORKSPACE_HELP
                        emit("\n" + WORKSPACE_HELP)
                elif verb == "neofetch":
                    if argument is not None:
                        raise ValueError("neofetch does not take an argument")
                    emit(render_neofetch(book, actions.cwd, width, color and not plain))
                elif verb == "pwd":
                    if argument is not None:
                        raise ValueError("pwd does not take an argument")
                    emit(display_text(display_path(actions.cwd)))
                elif verb in {"next", "previous", "prev"}:
                    if argument is not None:
                        raise ValueError(f"{verb} does not take a path")
                    passage = actions.move(1 if verb == "next" else -1)
                    emit(render_passage(passage, width, plain, color))
                elif verb in {"cd", "up"}:
                    if verb == "up" and argument is not None:
                        raise ValueError("up does not take an argument")
                    if verb == "cd" and argument == "-":
                        actions.back()
                    else:
                        if verb == "up":
                            actions.up()
                        else:
                            _, path = actions.locate(argument or "/")
                            actions.browse(path)
                elif verb == "open":
                    if argument is None:
                        raise ValueError("open requires a passage ID or search result number")
                    if argument.isdecimal():
                        passage = actions.open_result(int(argument))
                    else:
                        passage = actions.open(argument)
                    emit(render_passage(passage, width, plain, color))
                elif verb == "context":
                    radius = 1 if argument is None else int(argument)
                    emit("\n\n".join(render_passage(item, width, plain, color)
                                     for item in actions.context(radius)))
                elif verb == "where":
                    if argument is not None:
                        raise ValueError("where does not take an argument")
                    current = session.current()
                    emit(render_info(book, current.node, current.path, width))
                    emit(f"ID {current.identifier}")
                    emit(f"Position {session.cursor + 1} of {len(book.selection(session.path))} "
                          f"in {display_path(session.path)}")
                elif verb in {"ls", "read", "first", "cat", "info"}:
                    node, path = actions.locate(argument)
                    if verb == "ls":
                        emit(render_listing(node))
                    elif verb == "info":
                        emit(render_info(book, node, path, width))
                    elif verb in {"read", "first"}:
                        passage = actions.read(path, verb == "first")
                        emit(render_passage(passage, width, plain, color))
                    else:
                        if node.is_directory:
                            raise ValueError("cat takes a file; use first or read for a directory")
                        for passage in book.selection(path):
                            emit(render_passage(passage, width, plain, color), end="\n\n")
                else:
                    raise ValueError(f"unknown command: {verb}; type help")
            except KeyboardInterrupt:
                emit("Command cancelled.")
            except (ValueError, RuntimeError) as error:
                emit("sol: " + safe_output(error))
    finally:
        restore()
        if adapter is not None:
            adapter.close()
        if source_pane is not None:
            source_pane.cleanup()
        if comparison_pane is not None:
            comparison_pane.cleanup()
        if essence_pane is not None:
            essence_pane.cleanup()
        if handoff is not None:
            try:
                handoff.close()
            except (ValueError, OSError) as error:
                emit(f"sol: temporary ESSENCE cleanup incomplete; data retained at {handoff.directory}: {error}")
