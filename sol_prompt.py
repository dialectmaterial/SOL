"""Optional input ergonomics, with no command execution or workspace writes.

Importing this module needs only the standard library. The factory returns None
for the existing basic shell; prompt_toolkit is imported only for an eligible
interactive terminal. Private drafting never uses command or file history.
"""
from __future__ import annotations

import os
import re
import shlex
import sys
import unicodedata


_COMMANDS = (
    "ls", "cd", "up", "pwd", "tree", "read", "first", "next", "previous", "prev",
    "cat", "search", "open", "context", "info", "where",
    "neofetch", "guide", "help", "exit", "quit",
)
_SUBCOMMANDS = {
    "workspace": ("export", "check", "backup", "upgrade", "history"),
    "bookmark": ("add", "set", "list", "open", "remove"),
    "note": ("add", "draft", "list", "show", "edit", "history"),
    "compare": ("save", "list", "show"),
    "review": ("show", "record", "list", "queue"),
    "relate": ("add", "list"),
}
_WORKSPACE_COMMANDS = (*_SUBCOMMANDS, "resume")


def _literal(value: str) -> str:
    return "".join(
        f"\\u{ord(character):04x}" if unicodedata.category(character) in {"Cc", "Cs"}
        or unicodedata.bidirectional(character) in {
            "LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI"}
        else character for character in value
    )


def _prefix(text: str) -> tuple[list[str], str, str]:
    """Tolerate unfinished quoting while preserving one replacement token."""
    words, current = [], []
    quote = None
    escaped = False
    start = 0
    active = False
    for index, character in enumerate(text):
        if not active and not character.isspace():
            start, active = index, True
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\" and quote != "'":
            # Match shlex's quoted escapes: inside double quotes a backslash
            # only removes itself before another backslash or double quote.
            if quote == '"' and index + 1 < len(text) and text[index + 1] not in {'"', "\\"}:
                current.append(character)
            else:
                escaped = True
        elif quote:
            if character == quote:
                quote = None
            else:
                current.append(character)
        elif character in {"'", '"'}:
            quote = character
        elif character.isspace():
            if active:
                words.append("".join(current))
                current = []
            active, start = False, index + 1
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    return words, "".join(current), text[start:] if active else ""


def _alias(name: str) -> str:
    return re.sub(r"^(?:\d+|[a-d]|[ivxlcdm]+|[αβγ])-", "",
                  name.removesuffix(".txt").casefold())


class CompletionCatalog:
    """Pure keypress-time suggestions over captured book and saved names."""

    def __init__(self, book, workspace: bool = False):
        self.root = book.root
        self.workspace = workspace
        self.cwd: tuple[str, ...] = ()
        self.bookmarks: tuple[str, ...] = ()
        self.comparisons: tuple[str, ...] = ()
        self.annotations: tuple[str, ...] = ()
        self.record_ids = tuple(getattr(book, "canonical_records", {}) or
                                {p.identifier: None for p in book.passages if p.identifier})
        self.reader_ids = tuple(dict.fromkeys(
            [p.identifier for p in book.passages if p.identifier] +
            list(getattr(book, "redirects", {}))))

    def _node(self, path):
        node = self.root
        pieces = path.split("/")
        if not path.startswith("/"):
            pieces = [*self.cwd, *pieces]
        for piece in pieces:
            if piece in {"", "."}:
                continue
            if piece == "..":
                node = node.parent or self.root
                continue
            exact = [child for child in node.children if child.name == piece]
            if exact:
                node = exact[0]
                continue
            matches = [child for child in node.children if
                       child.name.casefold().removesuffix(".txt") == piece.casefold().removesuffix(".txt")
                       or _alias(child.name) == _alias(piece)]
            if len(matches) != 1:
                return None
            node = matches[0]
        return node

    def _paths(self, prefix, directories=False):
        parent, separator, fragment = prefix.rpartition("/")
        location = parent + "/" if separator else ""
        node = self._node(location)
        if node is None:
            return ()
        return tuple(
            location + child.name + ("/" if child.is_directory else "")
            for child in node.children if (not directories or child.is_directory)
            and (child.name.casefold().startswith(fragment.casefold())
                 or _alias(child.name).startswith(_alias(fragment)))
        )

    def suggestions(self, text: str) -> list[tuple[str, int]]:
        words, prefix, raw = _prefix(text)
        path_choices = False
        commands = _COMMANDS + (_WORKSPACE_COMMANDS if self.workspace else ())
        if not words:
            choices = commands
        else:
            verb = words[0]
            arguments = words[1:]
            previous = arguments[-1] if arguments else ""
            if self.workspace and verb in _SUBCOMMANDS and not arguments:
                choices = _SUBCOMMANDS[verb]
            elif previous == "--on":
                choices = self.record_ids
            elif previous == "--within":
                choices = self._paths(prefix)
                path_choices = True
            elif previous in {"--limit", "--depth", "--issue", "--question", "--reason", "--expect-revision"}:
                choices = ()
            elif verb in {"ls", "cd", "tree", "read", "first", "cat", "info", "guide"}:
                if prefix.startswith("--") and verb in {"tree", "guide"}:
                    choices = ("--depth",)
                else:
                    choices = self._paths(prefix, directories=verb == "cd")
                    path_choices = True
                    if verb == "cd":
                        choices += tuple(value for value in ("..", "-", "/") if value.startswith(prefix))
            elif verb == "open" and not arguments:
                choices = self.reader_ids
            elif verb == "search" and arguments:
                if prefix.startswith("--"):
                    choices = ("--word", "--limit")
                else:
                    choices = self._paths(prefix)
                    path_choices = True
            elif verb == "bookmark" and self.workspace and arguments:
                action = arguments[0]
                choices = (self.bookmarks if len(arguments) == 1 and action in {"open", "remove", "set"}
                           else self.reader_ids if len(arguments) == 2 and action in {"add", "set"} else ())
            elif verb == "compare" and self.workspace and arguments:
                choices = (self.comparisons if arguments[0] == "show" and len(arguments) == 1 else
                           ("--question",) if prefix.startswith("--") and arguments[0] == "save" else
                           self.record_ids if arguments[0] == "save" and len(arguments) >= 2
                           and "--question" not in arguments else ())
            elif verb == "note" and self.workspace and arguments:
                choices = (self.annotations if arguments[0] in {"show", "edit", "history"} and len(arguments) == 1 else
                           ("--expect-revision",) if arguments[0] == "edit" and prefix.startswith("--") else
                           ("--on",) if arguments[0] in {"add", "draft", "list"} and prefix.startswith("--") else ())
            elif verb == "review" and self.workspace and arguments:
                choices = (self.record_ids if arguments[0] == "show" else
                           ("inspected", "correction_needed", "verified")
                           if arguments == ["record"] else
                           ("--within", "--limit") if arguments[0] == "queue" else
                           ("--on", "--issue") if prefix.startswith("--") else ())
            elif verb == "relate" and self.workspace and arguments:
                choices = (self.record_ids if arguments[0] == "add" and len(arguments) in {1, 3} else
                           ("supports", "contrasts", "presupposes", "develops", "compares-with")
                           if arguments[0] == "add" and len(arguments) == 2 else
                           ("--on", "--reason") if prefix.startswith("--") else ())
            elif verb == "workspace" and self.workspace and arguments == ["history"]:
                choices = ("--limit",)
            else:
                choices = ()
        result = []
        for choice in dict.fromkeys(choices):
            if _literal(choice) != choice:
                continue
            # Virtual paths already matched their final component through aliases.
            if not path_choices and not choice.casefold().startswith(prefix.casefold()):
                continue
            result.append((shlex.quote(choice), -len(raw)))
            if len(result) == 100:
                break
        return result


def _load_toolkit():
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.history import DummyHistory, InMemoryHistory
    from prompt_toolkit.input import create_input
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.output import create_output
    return locals()


class PromptAdapter:
    """Input and drafting only; the caller owns parsing, validation and commits."""

    def __init__(self, toolkit, book, get_cwd, workspace_reader=None, *,
                 input_stream=None, output_stream=None, editing_mode="emacs",
                 prompt_input=None, prompt_output=None):
        self._toolkit, self._get_cwd, self._reader = toolkit, get_cwd, workspace_reader
        self._closed = False
        self.catalog = CompletionCatalog(book, workspace_reader is not None)
        self._owned_input = prompt_input is None
        self._input = (toolkit["create_input"](stdin=input_stream)
                       if prompt_input is None else prompt_input)
        self._editing_mode = toolkit["EditingMode"].VI if editing_mode == "vi" else toolkit["EditingMode"].EMACS
        adapter = self

        class CapturedCompleter(toolkit["Completer"]):
            def get_completions(self, document, complete_event):
                for text, start in adapter.catalog.suggestions(document.text_before_cursor):
                    yield toolkit["Completion"](text, start_position=start)

        bindings = toolkit["KeyBindings"]()

        @bindings.add("tab")
        def complete(event):
            buffer = event.current_buffer
            if buffer.complete_state:
                buffer.complete_next()
                return
            choices = adapter.catalog.suggestions(buffer.document.text_before_cursor)
            if len(choices) == 1:
                # All suggestions are captured local metadata. Apply a unique
                # match now: start_completion schedules an async task, so a fast
                # following Enter could otherwise accept the unfinished token.
                text, start = choices[0]
                buffer.apply_completion(toolkit["Completion"](text, start_position=start))
            elif choices:
                buffer.start_completion(select_first=False)

        self._status = ""
        try:
            self._output = (toolkit["create_output"](stdout=output_stream)
                            if prompt_output is None else prompt_output)
            self._session = toolkit["PromptSession"](
                history=toolkit["InMemoryHistory"](), completer=CapturedCompleter(),
                complete_while_typing=False, complete_in_thread=False,
                editing_mode=self._editing_mode, key_bindings=bindings,
                bottom_toolbar=lambda: self._status,
                input=self._input, output=self._output,
                enable_system_prompt=False, enable_suspend=False, enable_open_in_editor=False,
            )
        except BaseException:
            if self._owned_input:
                self._input.close()
            raise

    def _check_open(self):
        if self._closed:
            raise ValueError("prompt adapter is closed")

    def refresh(self):
        self._check_open()
        self.catalog.cwd = tuple(self._get_cwd())
        actor = None if self._reader is None else self._reader.actor
        self._status = _literal("/" + "/".join(self.catalog.cwd) + " | actor: " + (actor or "not set"))
        if self._reader is not None:
            # All SQLite access happens synchronously before the prompt's event
            # loop. Completion and toolbar callbacks only consult these tuples.
            store = self._reader.store
            self.catalog.bookmarks = tuple(row["name"] for row in store.list_bookmarks())
            self.catalog.comparisons = tuple(row["name"] for row in store.list_comparisons())
            self.catalog.annotations = tuple(row["id"] for row in store.list_annotations())

    def read_command(self, prompt: str) -> str:
        self.refresh()
        return self._session.prompt(_literal(prompt))

    def read_draft(self, prompt: str = "Personal note: ", default: str = "") -> str:
        self._check_open()
        if not isinstance(default, str):
            raise ValueError("draft default must be text")
        bindings = self._toolkit["KeyBindings"]()

        @bindings.add("c-s")
        def accept(event):
            event.app.exit(result=event.current_buffer.text)

        @bindings.add("c-c")
        def cancel(event):
            event.app.exit(exception=KeyboardInterrupt())

        draft = self._toolkit["PromptSession"](
            multiline=True, history=self._toolkit["DummyHistory"](),
            completer=None, complete_while_typing=False, complete_in_thread=False,
            editing_mode=self._editing_mode, key_bindings=bindings,
            bottom_toolbar="Ctrl-S: finish draft | Ctrl-C: cancel",
            input=self._input, output=self._output,
            enable_system_prompt=False, enable_suspend=False, enable_open_in_editor=False,
        )
        try:
            return draft.prompt(_literal(prompt), default=default)
        except EOFError as error:
            raise KeyboardInterrupt() from error
        finally:
            draft.default_buffer.reset()

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self._session.default_buffer.reset()
            finally:
                if self._owned_input:
                    self._input.close()


def create_adapter(book, get_cwd, workspace_reader=None, *, mode="auto", plain=False,
                   input_stream=None, output_stream=None, editing_mode="emacs",
                   prompt_input=None, prompt_output=None):
    """Return None for the basic shell without importing optional dependencies."""
    if mode not in {"auto", "basic", "prompt"}:
        raise ValueError("input mode must be auto, basic, or prompt")
    if editing_mode not in {"emacs", "vi"}:
        raise ValueError("editing mode must be emacs or vi")
    stdin = sys.stdin if input_stream is None else input_stream
    stdout = sys.stdout if output_stream is None else output_stream
    if (mode == "basic" or plain or os.environ.get("TERM") == "dumb"
            or not getattr(stdin, "isatty", lambda: False)()
            or not getattr(stdout, "isatty", lambda: False)()):
        return None
    try:
        toolkit = _load_toolkit()
    except ImportError as error:
        if mode == "auto":
            return None
        raise ValueError("the optional prompt interface needs prompt_toolkit; "
                         "from the SOL project run pipx install --force '.[shell]' "
                         "to install or refresh SOL with its shell extra") from error
    try:
        return PromptAdapter(toolkit, book, get_cwd, workspace_reader,
                             input_stream=stdin, output_stream=stdout, editing_mode=editing_mode,
                             prompt_input=prompt_input, prompt_output=prompt_output)
    except (OSError, EOFError) as error:
        if mode == "auto":
            return None
        raise ValueError(f"cannot initialize the optional prompt interface: {error}") from error
