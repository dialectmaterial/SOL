"""Corpus configuration contracts using isolated synthetic directories only."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol.core import config


class CoreConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sol-core-config-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cwd = self.root / "cwd"
        self.cwd.mkdir()
        for guard in (
            patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "configuration")}, clear=True),
            patch.object(config.Path, "cwd", return_value=self.cwd),
            patch.object(config, "installed_project_directory", return_value=None),
            patch.object(config, "source_project_directory", return_value=None),
        ):
            guard.start()
            self.addCleanup(guard.stop)

    def saved(self, content):
        path = config.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_missing_configuration_is_read_only(self):
        self.assertIsNone(config.configured_corpus())
        self.assertIsNone(config.discover_corpus())
        self.assertFalse((self.root / "configuration").exists())

    def test_explicit_and_environment_choices_bypass_broken_saved_pointer(self):
        self.saved("{broken")
        explicit = self.root / "absent-explicit"
        selected = self.root / "absent-environment"
        with patch.dict(os.environ, {"SOL_CORPUS": str(selected)}):
            self.assertEqual(config.discover_corpus(explicit), explicit)
            self.assertEqual(config.discover_corpus(), selected)

    def test_cwd_manifest_precedes_saved_pointer(self):
        local = self.cwd / "local-corpus"
        local.mkdir()
        (local / "corpus.json").write_text("{}", encoding="utf-8")
        self.saved("{broken")
        self.assertEqual(config.discover_corpus(), local)

    def test_absent_saved_location_never_silently_changes_sources(self):
        selected = self.root / "absent-saved"
        self.saved(json.dumps({"version": 1, "corpus": str(selected)}))
        with patch.object(config, "installed_project_directory", side_effect=AssertionError("No fallback")):
            self.assertEqual(config.discover_corpus(), selected)

    def test_broken_saved_configuration_fails_before_fallback(self):
        for content in ("{broken", "[]", "null", '{"corpus":"relative"}', '{"corpus":42}'):
            self.saved(content)
            with self.subTest(content=content), patch.object(
                    config, "installed_project_directory", side_effect=AssertionError("No fallback")):
                with self.assertRaisesRegex(ValueError, "--set-corpus"):
                    config.discover_corpus()

    def test_local_install_precedes_checkout_and_requires_a_manifest(self):
        installed, checkout = self.root / "installed", self.root / "checkout"
        for project in (installed, checkout):
            local = project / "local-corpus"
            local.mkdir(parents=True)
            (local / "corpus.json").write_text("{}", encoding="utf-8")
        with patch.object(config, "installed_project_directory", return_value=installed), \
                patch.object(config, "source_project_directory", return_value=checkout):
            self.assertEqual(config.discover_corpus(), installed / "local-corpus")
            (installed / "local-corpus" / "corpus.json").unlink()
            self.assertEqual(config.discover_corpus(), checkout / "local-corpus")

    def test_save_validates_before_writing_and_stores_absolute_unicode_path(self):
        source = self.root / "corpus with spaces λ"
        source.mkdir()
        with patch("sol.core.corpus.load_corpus_book") as validate:
            returned, pointer = config.save_corpus(source)
        validate.assert_called_once_with(source.resolve())
        self.assertEqual(returned, source.resolve())
        self.assertEqual(pointer, config.config_path())
        self.assertEqual(json.loads(pointer.read_text(encoding="utf-8")),
                         {"version": 1, "corpus": str(source.resolve())})
        self.assertEqual(config.configured_corpus(), source.resolve())
        self.assertEqual(list(pointer.parent.glob(".config-*.tmp")), [])

    def test_invalid_corpus_never_creates_configuration(self):
        with patch("sol.core.corpus.load_corpus_book", side_effect=ValueError("Invalid synthetic corpus")):
            with self.assertRaisesRegex(ValueError, "Invalid synthetic corpus"):
                config.save_corpus(self.root / "invalid")
        self.assertFalse((self.root / "configuration").exists())

    def test_failed_replace_keeps_previous_pointer_and_removes_temporary(self):
        pointer = self.saved('{"corpus":"/previous/synthetic"}\n')
        before = pointer.read_bytes()
        with patch("sol.core.corpus.load_corpus_book"), \
                patch.object(config.Path, "replace", side_effect=PermissionError("Synthetic refusal")):
            with self.assertRaisesRegex(ValueError, "Cannot save SOL configuration"):
                config.save_corpus(self.root / "other")
        self.assertEqual(pointer.read_bytes(), before)
        self.assertEqual(list(pointer.parent.glob(".config-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
