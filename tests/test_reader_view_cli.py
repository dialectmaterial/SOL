"""Reader-view routing without implicit setup on unavailable terminals."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from sol.presentation.theme import DEFAULT_READER_WIDTH
from unittest.mock import patch

from sol.corpus import contract
from sol.app import main as app
from sol.app.options import build_parser
from fixtures_corpus import write_runtime_corpus


class ReaderViewCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-reader-cli-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.environment = patch.dict(os.environ, {"SOL_CORPUS": str(self.corpus),
                                      "XDG_CONFIG_HOME": str(self.root / "config"),
                                      "XDG_DATA_HOME": str(self.root / "data")})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def call(self, arguments):
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            status = app.main(arguments)
        return status, output.getvalue(), error.getvalue()

    def test_reader_is_default_and_explicit_shell_keeps_command_interface(self):
        for arguments, selected, temporary in (([], True, False), (["being"], True, False),
                                               (["-n"], True, True), (["--shell"], False, False),
                                               (["being", "-n"], True, True)):
            args = build_parser().parse_args(arguments)
            mode = app.validate_options(args)
            self.assertEqual(args.shell, not selected)
            self.assertEqual(mode.interactive, True)
            self.assertEqual(args.reader, selected)
            self.assertEqual(args.none, temporary)

    def test_set_source_pdf_verifies_through_the_source_service(self):
        with patch("sol.core.source.SourceService.set_pdf", return_value=Path("/invented/book.pdf")) as remember:
            status, output, error = self.call(["--set-source-pdf", "~/book.pdf"])
            self.assertEqual((status, error), (0, ""))
            self.assertIn("Source PDF verified and remembered: /invented/book.pdf", output)
            status, output, _ = self.call(["--set-source-pdf", "~/book.pdf", "--json"])
            self.assertEqual(json.loads(output), {"source_pdf": "/invented/book.pdf"})
        self.assertEqual(remember.call_args.args, (Path("~/book.pdf"),))
        for arguments in (["--set-source-pdf", "a.pdf", "--workspace", "study"],):
            with self.subTest(arguments=arguments):
                status, _, error = self.call(arguments)
                self.assertNotEqual(status, 0)
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["--set-source-pdf", "a.pdf", "--set-theme", "mocha"])

    def test_wrong_source_pdf_is_refused_and_not_remembered(self):
        wrong = self.root / "other.pdf"
        wrong.write_bytes(b"%PDF-1.4 a different book")
        with patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.root / "cache")}):
            status, _, error = self.call(["--set-source-pdf", str(wrong)])
        self.assertEqual(status, 2)
        self.assertIn("fingerprint mismatch", error)
        self.assertFalse((self.root / "config" / "sol" / "sources.json").exists())

    def test_unsupported_prototype_options_are_refused_before_loading_or_onboarding(self):
        for arguments in (["being", "--shell"], ["being", "-r"], ["being", "--search", "ground"],
                          ["being", "--json"], ["being", "--plain"], ["being", "--set-corpus", "absent"]):
            with self.subTest(arguments=arguments), \
                    patch.object(app, "discover_corpus", side_effect=AssertionError("No corpus I/O")), \
                    patch.object(app, "shell_identity", side_effect=AssertionError("No onboarding")):
                status, _, error = self.call(arguments)
                self.assertNotEqual(status, 0)
                self.assertIn("reader", error)
        self.assertFalse((self.root / "config").exists())
        self.assertFalse((self.root / "data").exists())

    def test_unavailable_view_fails_before_any_data_or_profile_access(self):
        with patch("sol.being.neovim.host.validate_environment", side_effect=ValueError("Invented unavailable view")), \
                patch.object(app, "discover_corpus", side_effect=AssertionError("No corpus I/O")), \
                patch.object(app, "shell_identity", side_effect=AssertionError("No onboarding")), \
                patch("sol.being.workspace.profiles.register_actor", side_effect=AssertionError("No profile write")):
            status, _, error = self.call([])
        self.assertNotEqual(status, 0)
        self.assertIn("Invented unavailable view", error)
        self.assertFalse((self.root / "config").exists())
        self.assertFalse((self.root / "data").exists())

    def test_nonpersistent_view_bypasses_actor_and_workspace_storage(self):
        with patch("sol.being.neovim.host.validate_environment"), \
                patch.object(app, "run_reader", return_value=0) as view, \
                patch.object(app, "shell_identity", side_effect=AssertionError("No onboarding")), \
                patch("sol.being.workspace.store.Workspace", side_effect=AssertionError("No workspace")), \
                patch("sol.being.workspace.profiles.register_actor", side_effect=AssertionError("No profile")):
            status, _, error = self.call(["-n"])
        self.assertEqual(status, 0, error)
        view.assert_called_once()
        self.assertEqual(len(view.call_args.args), 1)
        self.assertEqual(view.call_args.args[0].corpus_directory, self.corpus)
        self.assertFalse((self.root / "config").exists())
        self.assertFalse((self.root / "data").exists())

    def test_default_view_routes_after_existing_workspace_onboarding(self):
        def choose(book, args):
            args.workspace, args.actor = "reading", "Invented reader"
            args.workspace_dir = self.root / "workspaces"

        with patch("sol.being.neovim.host.validate_environment"), \
                patch.object(app, "shell_identity", side_effect=choose) as onboarding, \
                patch.object(app, "run_reader", return_value=0) as view:
            status, _, error = self.call([])
        self.assertEqual(status, 0, error)
        onboarding.assert_called_once()
        view.assert_called_once()
        book, reader = view.call_args.args
        self.assertIs(reader.book, book)
        self.assertEqual(reader.actor, "Invented reader")
        self.assertEqual(reader.store.path, self.root / "workspaces" / "reading.sqlite3")
        from sol.being.workspace.store import SCHEMA_VERSION
        self.assertEqual(reader.store.schema_version, SCHEMA_VERSION)

    def test_width_and_emphasis_are_forwarded_to_the_reader(self):
        with patch("sol.being.neovim.host.validate_environment"), \
                patch.object(app, "run_reader", return_value=0) as view:
            status, _, error = self.call(["being", "-n", "--width", "64", "--emphasis", "underline"])
        self.assertEqual(status, 0, error)
        self.assertEqual(view.call_args.kwargs, {"width": 64, "emphasis": "underline", "theme": "mocha"})

    def test_emphasis_is_reader_only_and_width_validation_precedes_data_access(self):
        for arguments in (["-r", "--emphasis", "italic"], ["being", "--width", "19"],
                          ["being", "--width", "241"]):
            with self.subTest(arguments=arguments), \
                    patch.object(app, "discover_corpus", side_effect=AssertionError("No source access")), \
                    patch("sol.being.neovim.host.validate_environment"):
                status, _, _ = self.call(arguments)
            self.assertNotEqual(status, 0)

    def test_explicit_workspace_injects_existing_service_without_prompting(self):
        with patch("sol.being.neovim.host.validate_environment"), \
                patch("builtins.input", side_effect=AssertionError("No prompt needed")), \
                patch.object(app, "run_reader", return_value=0) as view:
            status, _, error = self.call(["being", "--workspace", "reading", "--actor", "Invented reader",
                                           "--workspace-dir", str(self.root / "workspaces")])
        self.assertEqual(status, 0, error)
        self.assertEqual(view.call_args.args[1].actor, "Invented reader")

    def test_help_remains_source_and_optional_dependency_free(self):
        with patch.object(app, "discover_corpus", side_effect=AssertionError("No source")), \
                patch("sol.being.neovim.host.validate_environment", side_effect=AssertionError("No TTY needed")), \
                redirect_stdout(StringIO()) as output, self.assertRaises(SystemExit) as caught:
            app.main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("being", output.getvalue())
        for removed in ("--reader", "--engine", "--pdf", "--ui", "--editing-mode", "compare", "analyze"):
            self.assertNotIn(removed, output.getvalue())

    def test_first_interactive_launch_uses_guided_import_then_the_same_reader(self):
        book = app.load_corpus_book(self.corpus)
        with patch("sol.being.neovim.host.validate_environment"), \
                patch.object(app, "discover_corpus", return_value=None), \
                patch("sol.corpus.onboarding.prepare_first_corpus", return_value=book) as setup, \
                patch.object(app, "run_reader", return_value=0) as reader:
            status, _, error = self.call(["-n"])
        self.assertEqual(status, 0, error)
        setup.assert_called_once_with()
        self.assertIs(reader.call_args.args[0], book)

    def test_missing_corpus_in_one_shot_output_never_starts_import(self):
        with patch.object(app, "discover_corpus", return_value=None), \
                patch("sol.corpus.onboarding.prepare_first_corpus", side_effect=AssertionError("No import")):
            status, _, error = self.call(["-r"])
        self.assertEqual(status, 2)
        self.assertIn("import the supported Hegel-SOL.pdf", error)

    def test_neovim_preflight_precedes_corpus_and_actor_access(self):
        with patch("sol.being.neovim.host.validate_environment", side_effect=ValueError("Neovim unavailable")), \
                patch.object(app, "discover_corpus", side_effect=AssertionError("No source access")), \
                patch.object(app, "shell_identity", side_effect=AssertionError("No onboarding")):
            status, _, error = self.call(["being"])
        self.assertEqual(status, 2)
        self.assertIn("Neovim unavailable", error)
        self.assertFalse((self.root / "config").exists())
        self.assertFalse((self.root / "data").exists())

    def test_neovim_temporary_reader_does_not_require_builtin_frontend(self):
        with patch("sol.being.neovim.host.validate_environment"), \
                patch("sol.being.neovim.reader.run_reader", return_value=0) as reader, \
                patch.object(app, "shell_identity", side_effect=AssertionError("No onboarding")):
            status, _, error = self.call(["-n", "--width", "64", "--emphasis", "underline"])
        self.assertEqual(status, 0, error)
        reader.assert_called_once()
        self.assertEqual(reader.call_args.kwargs, {"width": 64, "emphasis": "underline", "theme": "mocha"})
        self.assertFalse((self.root / "data").exists())

    def test_dynamic_structure_launches_temporary_native_tree_without_onboarding(self):
        with patch("sol.being.neovim.host.validate_environment"), \
                patch("sol.being.neovim.reader.run_reader", return_value=0) as reader, \
                patch.object(app, "shell_identity", side_effect=AssertionError("No actor setup")):
            status, _, error = self.call(["--dynamic-structure", "--depth", "3"])
        self.assertEqual(status, 0, error)
        self.assertEqual(reader.call_args.kwargs, {"width": DEFAULT_READER_WIDTH, "start_tree": True, "tree_depth": 3, "theme": "mocha"})
        self.assertFalse((self.root / "data").exists())

    def test_dynamic_structure_refuses_workspace_and_noninteractive_output(self):
        for options in (["--workspace", "reading"], ["--actor", "Actor"], ["--json"], ["--plain"], ["--depth", "0"]):
            with self.subTest(options=options), \
                    patch.object(app, "discover_corpus", side_effect=AssertionError("No source access")):
                status, _, _ = self.call(["--dynamic-structure", *options])
            self.assertEqual(status, 2)

    def test_ordinary_random_output_does_not_import_the_reader_adapter(self):
        import subprocess
        import sys
        statement = '''
import builtins, sys
original = builtins.__import__
def guard(name, *args, **kwargs):
    if name == 'experiments.reader_surfaces.baseline' or name.startswith('prompt_toolkit'):
        raise AssertionError('Ordinary reading imported optional reader ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guard
from sol.app.main import main
assert main(['-r', '--json', '--corpus', sys.argv[1]]) == 0
'''
        result = subprocess.run([sys.executable, "-B", "-c", statement, str(self.corpus)],
                                cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("id", json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
