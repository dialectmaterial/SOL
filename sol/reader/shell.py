"""A minimal book command interface: browse, read and search the canonical book.

It uses no workspace, actor or terminal integration: positions are not saved
and nothing is written. Input is plain `input()` with optional standard-library
readline completion.
"""
from __future__ import annotations

import argparse
import shlex

from sol.core.models import Book, Node
from sol.core.paths import display_path, resolve_path
from sol.reader.actions import ReaderActions, ReadingSession
from sol.presentation.text import display_text, safe_output
from sol.reader.render import (render_guide, render_info, render_listing, render_passage,
                               render_search_results, render_tree, sensible_width)

COMMANDS = ("ls", "cd", "up", "pwd", "tree", "read", "first", "next", "previous",
            "cat", "search", "open", "context", "info", "where", "guide", "help", "exit")


def install_completion(root: Node, get_cwd):
    """Optional standard-library tab completion; safe on systems without readline."""
    try:
        import readline
    except ImportError:
        return lambda: None
    old_completer = readline.get_completer()
    old_delimiters = readline.get_completer_delims()

    def complete(text: str, state: int):
        try:
            if " " not in readline.get_line_buffer():
                choices = [command for command in COMMANDS if command.startswith(text)]
            else:
                parent, _, fragment = text.rpartition("/")
                node, _ = resolve_path(parent + "/" if "/" in text else None, get_cwd(), root)
                choices = [(parent + "/" if "/" in text else "") + child.name + ("/" if child.is_directory else "")
                           for child in node.children if child.name.casefold().startswith(fragment.casefold())]
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
tree [PATH] --depth N             show the outline; default is the full tree
read [PATH]                       read a random passage and set the reading cursor
first [PATH]                      start the selection in book order
next / previous                   move within the reading selection
cat FILE                          display the complete file in book order
search QUERY [PATH] --word --limit N
                                  literal search (default: current subtree)
open ID|RESULT                    open a passage or latest search result
context [N]                       neighbors in book order (default 1; maximum 10)
where                             show current passage and reading position
info [PATH]                       title, pages, counts, and pending review
guide [PATH] --depth N            beginner guide and book tree (default depth 1)
help / exit                       show commands / leave
Search does not move the reading cursor. Context can cross file boundaries.
Quote multiword queries. Paths accept aliases; Tab completes full names.
Nothing is saved here; read with sol for notes, markers and your position."""


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
              read_command=None, write_output=None, auto_width=False) -> int:
    """Run the shell through replaceable input/output seams (print's calling convention)."""
    actions = ReaderActions(book, session=ReadingSession(book))
    session = actions.session
    emit = write_output if write_output is not None else print
    restore = install_completion(book.root, lambda: actions.cwd) if read_command is None else (lambda: None)
    try:
        emit("SOL. Type 'guide' to get started; 'help' for commands.")
        while True:
            try:
                command = (read_command or input)(f"sol:{display_path(actions.cwd)}$ ")
            except EOFError:
                emit()
                return 0
            except KeyboardInterrupt:
                emit("\nType 'exit' to leave.")
                continue
            try:
                if not isinstance(command, str):
                    raise ValueError("command input must be text")
                parts = shlex.split(command)
                if not parts:
                    continue
                verb, arguments = parts[0], parts[1:]
                if auto_width:
                    width = sensible_width(None)
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
                elif verb == "pwd":
                    if argument is not None:
                        raise ValueError("pwd does not take an argument")
                    emit(display_text(display_path(actions.cwd)))
                elif verb in {"next", "previous", "prev"}:
                    if argument is not None:
                        raise ValueError(f"{verb} does not take a path")
                    emit(render_passage(actions.move(1 if verb == "next" else -1), width, plain, color))
                elif verb in {"cd", "up"}:
                    if verb == "up" and argument is not None:
                        raise ValueError("up does not take an argument")
                    if verb == "cd" and argument == "-":
                        actions.back()
                    elif verb == "up":
                        actions.up()
                    else:
                        actions.browse(actions.locate(argument or "/")[1])
                elif verb == "open":
                    if argument is None:
                        raise ValueError("open requires a passage ID or search result number")
                    passage = actions.open_result(int(argument)) if argument.isdecimal() else actions.open(argument)
                    emit(render_passage(passage, width, plain, color))
                elif verb == "context":
                    radius = 1 if argument is None else int(argument)
                    emit("\n\n".join(render_passage(item, width, plain, color) for item in actions.context(radius)))
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
                        emit(render_passage(actions.read(path, verb == "first"), width, plain, color))
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
