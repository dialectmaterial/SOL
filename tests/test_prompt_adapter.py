"""Optional prompt behavior and private drafts, without a real terminal."""
from __future__ import annotations

import builtins
from collections import deque
import importlib.util
import io
import os
from pathlib import Path
import shlex
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import sol.reader.app as sol
import sol.terminal.prompt as sol_prompt


A = "aaaaaaaa-0000-4000-8000-000000000001"
B = "bbbbbbbb-0000-4000-8000-000000000002"
NOTE = "cccccccc-0000-4000-8000-000000000003"


class TTYStream(io.StringIO):
    def isatty(self):
        return True


def invented_book():
    root = sol.Node("", "Invented book", 1)
    being = sol.Node("BEING", "Being", 1, parent=root)
    chapter = sol.Node("01-quality", "Quality", 1, parent=being)
    leaf = sol.Node("00-introduction.txt", "Introduction", 1, parent=chapter)
    essence = sol.Node("ESSENCE", "Essence", 4, parent=root)
    root.children, being.children, chapter.children = (being, essence), (chapter,), (leaf,)
    return SimpleNamespace(
        root=root, passages=[SimpleNamespace(identifier=A)],
        canonical_records={A: {}, B: {}}, redirects={},
    )


class FakeMemoryHistory:
    def __init__(self):
        self.strings = []


class FakeDummyHistory:
    def __init__(self):
        self.strings = []


class FakeSession:
    instances = []
    answers = deque()

    def __init__(self, **options):
        self.options = options
        self.default_buffer = SimpleNamespace(text="", reset=Mock())
        self.instances.append(self)

    def prompt(self, message, **options):
        self.message, self.prompt_options = message, options
        answer = self.answers.popleft() if self.answers else "exit"
        if isinstance(answer, BaseException):
            raise answer
        self.default_buffer.text = answer
        if isinstance(self.options["history"], FakeMemoryHistory):
            self.options["history"].strings.append(answer)
        return answer


class FakeBindings:
    def __init__(self):
        self.callbacks = {}

    def add(self, key):
        def decorate(function):
            self.callbacks[key] = function
            return function
        return decorate


def mocked_modules():
    package = ModuleType("prompt_toolkit")
    package.__path__ = []
    package.PromptSession = FakeSession
    modules = {"prompt_toolkit": package}
    attributes = {
        "completion": {"Completer": type("FakeCompleter", (), {}),
                       "Completion": lambda text, start_position=0: SimpleNamespace(
                           text=text, start_position=start_position)},
        "enums": {"EditingMode": SimpleNamespace(EMACS="EMACS", VI="VI")},
        "history": {"InMemoryHistory": FakeMemoryHistory, "DummyHistory": FakeDummyHistory,
                    "FileHistory": Mock(side_effect=AssertionError("No persistent private history"))},
        "input": {"create_input": Mock(return_value=Mock(name="owned-input"))},
        "key_binding": {"KeyBindings": FakeBindings},
        "output": {"create_output": Mock(return_value=Mock(name="output"))},
    }
    for name, values in attributes.items():
        module = ModuleType("prompt_toolkit." + name)
        module.__dict__.update(values)
        modules[module.__name__] = module
    return modules


class PromptAdapterTests(unittest.TestCase):
    def setUp(self):
        FakeSession.instances, FakeSession.answers = [], deque()
        self.book = invented_book()
        self.cwd = [()]
        self.stdin, self.stdout = TTYStream(), TTYStream()
        self.modules = mocked_modules()
        self.reader = SimpleNamespace(actor="Ada", store=Mock())
        self.reader.store.list_bookmarks.return_value = [{"name": "Ground notes"}]
        self.reader.store.list_comparisons.return_value = [{"name": "Being and Essence"}]
        self.reader.store.list_annotations.return_value = [{"id": NOTE}]
        self.environ = patch.dict(os.environ, {"TERM": "xterm-256color"})
        self.environ.start()
        self.addCleanup(self.environ.stop)

    def adapter(self, **options):
        with patch.dict(sys.modules, self.modules):
            adapter = sol_prompt.create_adapter(
                self.book, lambda: self.cwd[0], self.reader,
                input_stream=self.stdin, output_stream=self.stdout, **options)
        self.addCleanup(adapter.close)
        return adapter

    def test_module_import_never_imports_optional_library(self):
        root = str(Path(sol_prompt.__file__).resolve().parents[2])
        script = """
import builtins, sys
original = builtins.__import__
def guarded(name, *arguments, **options):
    if name.startswith('prompt_toolkit'):
        raise AssertionError('optional library imported')
    return original(name, *arguments, **options)
builtins.__import__ = guarded
sys.path.insert(0, sys.argv[1])
import sol.terminal.prompt as sol_prompt
"""
        result = subprocess.run([sys.executable, "-I", "-c", script, root],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_basic_plain_non_tty_and_dumb_modes_do_not_import_optional_library(self):
        cases = [
            {"mode": "basic"}, {"mode": "prompt", "plain": True},
            {"mode": "auto", "input_stream": io.StringIO()},
            {"mode": "prompt", "output_stream": io.StringIO()},
        ]
        for options in cases:
            arguments = {"input_stream": self.stdin, "output_stream": self.stdout, **options}
            with self.subTest(options=options), patch(
                    "sol.terminal.prompt._load_toolkit", side_effect=AssertionError("No optional imports")):
                self.assertIsNone(sol_prompt.create_adapter(self.book, lambda: (), **arguments))
        with patch.dict(os.environ, {"TERM": "dumb"}), patch(
                "sol.terminal.prompt._load_toolkit", side_effect=AssertionError("No optional imports")):
            self.assertIsNone(sol_prompt.create_adapter(self.book, lambda: (), mode="prompt",
                                                        input_stream=self.stdin, output_stream=self.stdout))

    def test_auto_missing_library_falls_back_and_explicit_mode_explains_extra(self):
        with patch("sol.terminal.prompt._load_toolkit", side_effect=ImportError("missing")):
            self.assertIsNone(sol_prompt.create_adapter(self.book, lambda: (), mode="auto",
                                                        input_stream=self.stdin, output_stream=self.stdout))
            with self.assertRaisesRegex(ValueError, r"\.\[shell\]"):
                sol_prompt.create_adapter(self.book, lambda: (), mode="prompt",
                                          input_stream=self.stdin, output_stream=self.stdout)

    def test_modes_are_validated_before_optional_imports(self):
        for options in ({"mode": "unknown"}, {"editing_mode": "unknown"}):
            with self.subTest(options=options), patch(
                    "sol.terminal.prompt._load_toolkit", side_effect=AssertionError("No imports")), \
                    self.assertRaises(ValueError):
                sol_prompt.create_adapter(self.book, lambda: (), **options)

    def test_prompt_session_has_ephemeral_history_and_no_external_facilities(self):
        adapter = self.adapter()
        options = adapter._session.options
        self.assertIsInstance(options["history"], FakeMemoryHistory)
        self.assertEqual(options["editing_mode"], "EMACS")
        for field in ("enable_system_prompt", "enable_suspend", "enable_open_in_editor",
                      "complete_in_thread", "complete_while_typing"):
            self.assertIs(options[field], False)
        self.modules["prompt_toolkit.history"].FileHistory.assert_not_called()

    def test_vi_mode_is_optional_and_close_is_idempotent(self):
        adapter = self.adapter(editing_mode="vi")
        self.assertEqual(adapter._session.options["editing_mode"], "VI")
        owned = adapter._input
        adapter.close()
        adapter.close()
        owned.close.assert_called_once()
        with self.assertRaisesRegex(ValueError, "closed"):
            adapter.read_command("> ")
        with self.assertRaisesRegex(ValueError, "closed"):
            adapter.read_draft()

    def test_injected_input_is_not_closed_by_adapter(self):
        provided = Mock(name="external-input")
        adapter = self.adapter(prompt_input=provided, prompt_output=Mock())
        adapter.close()
        provided.close.assert_not_called()
        self.modules["prompt_toolkit.input"].create_input.assert_not_called()

    def test_failed_initialization_closes_owned_input(self):
        self.modules["prompt_toolkit.output"].create_output.side_effect = OSError("synthetic output error")
        with patch.dict(sys.modules, self.modules):
            self.assertIsNone(sol_prompt.create_adapter(
                self.book, lambda: (), mode="auto", input_stream=self.stdin, output_stream=self.stdout))
        self.modules["prompt_toolkit.input"].create_input.return_value.close.assert_called_once()

    def test_prompt_boundary_refreshes_readonly_names_and_toolbar_without_callback_sql(self):
        adapter = self.adapter()
        self.cwd[0] = ("BEING",)
        self.assertEqual(adapter.read_command("> "), "exit")
        for method in ("list_bookmarks", "list_comparisons", "list_annotations"):
            getattr(self.reader.store, method).assert_called_once_with()
            getattr(self.reader.store, method).side_effect = AssertionError("No callback SQL")
        completer = adapter._session.options["completer"]
        results = list(completer.get_completions(SimpleNamespace(text_before_cursor="bookmark open Gro"), None))
        self.assertEqual([shlex.split(item.text)[0] for item in results], ["Ground notes"])
        self.assertEqual(adapter._session.options["bottom_toolbar"](), "/BEING | actor: Ada")
        self.reader.store.set_bookmark.assert_not_called()
        self.reader.store.save_state.assert_not_called()

    def test_saved_name_refresh_observes_later_prompt_boundary(self):
        adapter = self.adapter()
        adapter.read_command("> ")
        self.reader.store.list_bookmarks.return_value = [{"name": "Later bookmark"}]
        adapter.read_command("> ")
        self.assertEqual(adapter.catalog.bookmarks, ("Later bookmark",))

    def test_tab_unique_match_is_applied_synchronously_without_callback_sql(self):
        adapter = self.adapter()
        adapter.refresh()
        for method in ("list_bookmarks", "list_comparisons", "list_annotations"):
            getattr(self.reader.store, method).side_effect = AssertionError("No callback SQL")
        buffer = SimpleNamespace(
            complete_state=None, document=SimpleNamespace(text_before_cursor="neo"),
            apply_completion=Mock(), start_completion=Mock(), complete_next=Mock(),
        )
        adapter._session.options["key_bindings"].callbacks["tab"](
            SimpleNamespace(current_buffer=buffer))
        completion = buffer.apply_completion.call_args.args[0]
        self.assertEqual((completion.text, completion.start_position), ("neofetch", -3))
        buffer.start_completion.assert_not_called()
        buffer.complete_next.assert_not_called()

    def test_tab_multiple_matches_opens_menu_and_existing_menu_cycles(self):
        adapter = self.adapter()
        buffer = SimpleNamespace(
            complete_state=None, document=SimpleNamespace(text_before_cursor="c"),
            apply_completion=Mock(), start_completion=Mock(), complete_next=Mock(),
        )
        complete = adapter._session.options["key_bindings"].callbacks["tab"]
        complete(SimpleNamespace(current_buffer=buffer))
        buffer.start_completion.assert_called_once_with(select_first=False)
        buffer.apply_completion.assert_not_called()
        buffer.complete_state = object()
        complete(SimpleNamespace(current_buffer=buffer))
        buffer.complete_next.assert_called_once_with()

    def test_contextual_completion_paths_subcommands_ids_and_quoted_names(self):
        adapter = self.adapter()
        adapter.refresh()
        self.cwd[0] = ("BEING",)
        adapter.refresh()
        cases = {
            "neo": {"neofetch"}, "gui": {"guide"}, "note d": {"draft"},
            "cd qual": {"01-quality/"}, "cd /bei": {"/BEING/"},
            "read /being/quality/": {"/being/quality/00-introduction.txt"},
            "open aaaaaaaa": {A}, "review show bbbbbbbb": {B},
            "note show cccccccc": {NOTE},
            "note edit cccccccc": {NOTE}, "note history cccccccc": {NOTE},
            "note edit " + NOTE + ' "Text" --ex': {"--expect-revision"},
            "workspace up": {"upgrade"},
            "workspace export --f": {"--format"},
            "workspace export --format mar": {"markdown"},
            "workspace export --format markdown --in": {"--include-passages"},
            "note draft --on bbbbbbbb": {B},
            "compare show Being": {"Being and Essence"},
            'bookmark open "Ground n': {"Ground notes"},
            "review record cor": {"correction_needed"},
            "relate add " + A + " pres": {"presupposes"},
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                suggestions = adapter.catalog.suggestions(text)
                self.assertEqual({shlex.split(value)[0] for value, _ in suggestions}, expected)
                for value, start in suggestions:
                    applied = text[:len(text) + start] + value
                    self.assertTrue(shlex.split(applied))

    def test_completion_never_treats_unfinished_note_body_as_commands(self):
        catalog = sol_prompt.CompletionCatalog(self.book, workspace=True)
        for text in ("note add 'private unfinished", "note edit " + NOTE + " 'private unfinished",
                     "compare save pair " + A + " --question 'why",
                     "review record inspected --issue \"unfinished", "relate add " + A +
                     " supports " + B + " --reason 'unfinished"):
            with self.subTest(text=text):
                self.assertEqual(catalog.suggestions(text), [])
        for text in ("'", '"', "\\", "cd '", 'bookmark open "'):
            with self.subTest(text=text):
                catalog.suggestions(text)

    def test_completion_filters_names_containing_slashes_and_preserves_exact_paths(self):
        catalog = sol_prompt.CompletionCatalog(self.book, workspace=True)
        catalog.bookmarks = ("Being/Essence", "Ground notes")
        self.assertEqual([shlex.split(value)[0] for value, _ in catalog.suggestions(
            "bookmark open Gro")], ["Ground notes"])
        being = self.book.root.children[0]
        duplicate = sol.Node("02-quality", "Other quality", 2, parent=being)
        being.children += (duplicate,)
        self.assertEqual([shlex.split(value)[0] for value, _ in catalog.suggestions(
            "read /BEING/01-quality/")], ["/BEING/01-quality/00-introduction.txt"])
        self.assertEqual(catalog.suggestions("read /BEING/quality/"), [])

    def test_quoted_completion_preserves_literal_backslashes_like_shell_parser(self):
        catalog = sol_prompt.CompletionCatalog(self.book, workspace=True)
        catalog.bookmarks = (r"Ground\notes", "Groundnotes")
        text = 'bookmark open "Ground\\n'
        suggestions = catalog.suggestions(text)
        self.assertEqual([shlex.split(value)[0] for value, _ in suggestions], [r"Ground\notes"])
        value, start = suggestions[0]
        self.assertEqual(shlex.split(text[:len(text) + start] + value)[-1], r"Ground\notes")

    def test_draft_is_multiline_without_body_history_or_commits(self):
        adapter = self.adapter()
        body = "A personal first line.\n\nA second paragraph."
        FakeSession.answers.append(body)
        self.assertEqual(adapter.read_draft(default="Seed"), body)
        draft = FakeSession.instances[-1]
        self.assertTrue(draft.options["multiline"])
        self.assertIsInstance(draft.options["history"], FakeDummyHistory)
        self.assertEqual(draft.options["history"].strings, [])
        self.assertEqual(adapter._session.options["history"].strings, [])
        self.assertEqual(draft.prompt_options["default"], "Seed")
        draft.default_buffer.reset.assert_called_once()
        self.reader.store.add_annotation.assert_not_called()

    def test_draft_save_and_cancel_bindings_have_explicit_results(self):
        adapter = self.adapter()
        adapter.read_draft()
        bindings = FakeSession.instances[-1].options["key_bindings"].callbacks
        event = SimpleNamespace(app=Mock(), current_buffer=SimpleNamespace(text="Private body"))
        bindings["c-s"](event)
        event.app.exit.assert_called_with(result="Private body")
        bindings["c-c"](event)
        self.assertIsInstance(event.app.exit.call_args.kwargs["exception"], KeyboardInterrupt)

    def test_draft_interrupt_and_eof_cancel_and_clear_buffer(self):
        adapter = self.adapter()
        for exception in (KeyboardInterrupt(), EOFError()):
            FakeSession.answers.append(exception)
            with self.subTest(exception=type(exception).__name__), self.assertRaises(KeyboardInterrupt):
                adapter.read_draft()
            FakeSession.instances[-1].default_buffer.reset.assert_called_once()
        self.reader.store.add_annotation.assert_not_called()

    def test_command_interrupt_and_eof_propagate_to_shell(self):
        adapter = self.adapter()
        for exception in (KeyboardInterrupt(), EOFError()):
            FakeSession.answers.append(exception)
            with self.subTest(exception=type(exception).__name__), self.assertRaises(type(exception)):
                adapter.read_command("> ")


@unittest.skipUnless(importlib.util.find_spec("prompt_toolkit"), "optional prompt_toolkit is not installed")
class ActualPromptTests(unittest.TestCase):
    def actual_adapter(self, pipe):
        from prompt_toolkit.output import DummyOutput
        with patch.dict(os.environ, {"TERM": "xterm-256color"}):
            adapter = sol_prompt.create_adapter(
                invented_book(), lambda: (), mode="prompt", input_stream=TTYStream(),
                output_stream=TTYStream(), prompt_input=pipe, prompt_output=DummyOutput())
        self.addCleanup(adapter.close)
        return adapter

    def test_pipe_input_command_tab_completion_and_eof(self):
        from prompt_toolkit.input import create_pipe_input
        with create_pipe_input() as pipe:
            adapter = self.actual_adapter(pipe)
            for enter in ("\n", "\r"):
                with self.subTest(enter=repr(enter)):
                    pipe.send_text("neo\t" + enter)
                    self.assertEqual(adapter.read_command("> "), "neofetch")
            pipe.send_text("\x04")
            with self.assertRaises(EOFError):
                adapter.read_command("> ")

    def test_pipe_input_multiline_draft_and_cancel_never_enter_history(self):
        from prompt_toolkit.input import create_pipe_input
        with create_pipe_input() as pipe:
            adapter = self.actual_adapter(pipe)
            pipe.send_text("First paragraph.\nSecond paragraph.\x13")
            self.assertEqual(adapter.read_draft(), "First paragraph.\nSecond paragraph.")
            self.assertEqual(adapter._session.history.get_strings(), [])
            pipe.send_text("Canceled private body\x03")
            with self.assertRaises(KeyboardInterrupt):
                adapter.read_draft()
            self.assertEqual(adapter._session.history.get_strings(), [])


if __name__ == "__main__":
    unittest.main()
