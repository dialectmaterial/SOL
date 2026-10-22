"""Package responsibilities and safe source-checkout corpus discovery."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.core import config


class PackageBoundaryTests(unittest.TestCase):
    def imported_modules(self, statement: str) -> set[str]:
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-B", "-c",
             "import json, sys; " + statement + "; print(json.dumps(sorted(sys.modules)))"],
            cwd=root, text=True, capture_output=True, check=True,
        )
        return set(json.loads(result.stdout))

    def test_public_package_import_does_not_load_the_application(self):
        modules = self.imported_modules("import sol")
        self.assertNotIn("sol.app.main", modules)
        self.assertFalse(any(name.startswith(("sol.being.", "sol.presentation.")) for name in modules))

    def test_workspace_services_do_not_load_command_parser_adapter(self):
        modules = self.imported_modules("import sol.being.workspace.reader")
        self.assertNotIn("sol.being.workspace.commands", modules)

    def test_logical_divisions_import_without_loading_any_component(self):
        modules = self.imported_modules(
            "import sol.being.quality, sol.being.quantity, sol.being.measure, sol.concept, "
            "sol.essence.essence_as_reflection_within_itself, sol.essence.appearance, sol.essence.actuality")
        for name in ("sol.app.main", "sol.being.neovim.host", "sol.being.workspace.store", "sol.corpus.contract",
                     "sol.essence.essence_as_reflection_within_itself.words", "textual"):
            with self.subTest(module=name):
                self.assertNotIn(name, modules)

    def test_reader_import_does_not_load_pdf_conversion_or_optional_ui(self):
        modules = self.imported_modules("from sol.app import main as app; app.build_parser()")
        for name in ("sol.corpus.layout", "sol.corpus.convert", "sol.being.shell",
                     "sol.core.source", "markdown_it", "textual"):
            with self.subTest(module=name):
                self.assertNotIn(name, modules)

    def test_converter_does_not_import_the_reader_application(self):
        modules = self.imported_modules("import sol.corpus.convert")
        self.assertNotIn("sol.app.main", modules)
        self.assertNotIn("sol.reader.legacy_pdf", modules)
        self.assertFalse(any(name.startswith(("sol.being.", "sol.presentation.")) for name in modules))

    def test_config_import_has_no_reader_corpus_or_interface_dependency(self):
        modules = self.imported_modules("import sol.core.config")
        self.assertFalse(any(name.startswith("sol.app.") for name in modules))
        self.assertFalse(any(name.startswith(("sol.being.", "sol.presentation.")) for name in modules))
        self.assertNotIn("sol.core.corpus", modules)
        self.assertNotIn("sol.corpus.contract", modules)

    def test_options_parser_does_not_import_the_reader_application(self):
        modules = self.imported_modules("from sol.app.options import build_parser; build_parser()")
        self.assertNotIn("sol.app.main", modules)
        self.assertNotIn("sol.core.corpus", modules)
        self.assertFalse(any(name.startswith("sol.being.") for name in modules))

    def test_essence_theme_selection_does_not_import_reader_options(self):
        modules = self.imported_modules("import sol.essence.tui.__main__")
        self.assertIn("sol.presentation.theme", modules)
        for prefix in ("sol.app", "sol.being"):
            self.assertFalse(any(name == prefix or name.startswith(prefix + ".") for name in modules))


class SourceCheckoutDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sol-source-discovery-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.checkout = self.directory / "checkout"
        self.module = self.checkout / "sol" / "core" / "config.py"
        self.module.parent.mkdir(parents=True)
        self.module.write_text("# Synthetic package source\n", encoding="utf-8")
        self.metadata = self.checkout / "pyproject.toml"
        self.metadata.write_text('[project]\nname = "sol-organizes-logic"\n', encoding="utf-8")
        self.corpus = self.checkout / "local-corpus"
        self.corpus.mkdir()
        (self.corpus / "corpus.json").write_text("{}\n", encoding="utf-8")

    def discover(self):
        with patch.object(config, "__file__", str(self.module)), \
                patch.object(config.Path, "cwd", return_value=self.directory), \
                patch.object(config, "installed_project_directory", return_value=None), \
                patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.directory / "config")}, clear=True):
            return config.discover_corpus()

    def test_recognized_checkout_finds_root_corpus_from_elsewhere(self):
        self.assertEqual(self.discover(), self.corpus)

    def test_missing_project_metadata_does_not_guess_from_package_location(self):
        self.metadata.unlink()
        self.assertIsNone(self.discover())

    def test_checkout_marker_tolerates_indentation_comments_and_crlf(self):
        self.metadata.write_bytes(
            b"  [project] # Project identity\r\n  name = 'sol-organizes-logic' # SOL\r\n"
        )
        self.assertEqual(self.discover(), self.corpus)

    def test_different_project_name_does_not_select_its_corpus(self):
        self.metadata.write_text('[project]\nname = "another-project"\n', encoding="utf-8")
        self.assertIsNone(self.discover())

    def test_matching_name_outside_project_table_is_not_identity(self):
        self.metadata.write_text('[tool.example]\nname = "sol-organizes-logic"\n', encoding="utf-8")
        self.assertIsNone(self.discover())

    def test_unreadable_project_metadata_is_not_an_automatic_source(self):
        self.metadata.write_bytes(b"\xff\xfe")
        self.assertIsNone(self.discover())

    def test_saved_choice_has_precedence_over_checkout_fallback(self):
        selected = self.directory / "selected-corpus"
        with patch.object(config, "configured_corpus", return_value=selected):
            self.assertEqual(self.discover(), selected)


if __name__ == "__main__":
    unittest.main()
