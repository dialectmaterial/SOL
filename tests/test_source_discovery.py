"""Source selection must work without bundling a private corpus or parsing PDF."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import sol.core.config as sol


class InstallationOriginTests(unittest.TestCase):
    def origin(self, content: str | None) -> Path | None:
        distribution = Mock()
        distribution.read_text.return_value = content
        with patch("sol.core.config.package_metadata.distribution", return_value=distribution):
            result = sol.installed_project_directory()
        distribution.read_text.assert_called_once_with("direct_url.json")
        return result

    def test_local_origin_decodes_spaces_and_unicode(self) -> None:
        project = Path("/tmp/SOL checkout with spaces/λογική")
        for info in ({}, {"editable": True}):
            with self.subTest(info=info):
                self.assertEqual(self.origin(json.dumps({"url": project.as_uri(), "dir_info": info})), project)

    def test_localhost_and_project_subdirectory(self) -> None:
        self.assertEqual(self.origin(json.dumps({
            "url": "file://localhost/tmp/SOL", "dir_info": {}, "subdirectory": "tools/reader",
        })), Path("/tmp/SOL/tools/reader"))

    def test_nonpersistent_or_malformed_origins_are_ignored(self) -> None:
        values = [None, "{broken", "[]", "null"]
        data = [
            {"url": "file:///tmp/sol.whl", "archive_info": {}},
            {"url": "https://github.com/example/SOL", "vcs_info": {"vcs": "git"}},
            {"url": "https://example.com/checkout", "dir_info": {}},
            {"url": "file://remote-host/tmp/SOL", "dir_info": {}},
            {"url": "file:relative/SOL", "dir_info": {}},
            {"url": "file:///tmp/SOL?unexpected=true", "dir_info": {}},
            {"url": "file:///tmp/SOL#fragment", "dir_info": {}},
            {"url": "file:///tmp/SOL", "dir_info": None},
            {"url": None, "dir_info": {}},
            {"url": "file:///tmp/SOL", "dir_info": {}, "archive_info": {}},
            {"url": "file:///tmp/SOL", "dir_info": {}, "subdirectory": "../escape"},
            {"url": "file:///tmp/SOL", "dir_info": {}, "subdirectory": "/elsewhere"},
            {"url": "file:///tmp/SOL", "dir_info": {}, "subdirectory": 1},
        ]
        for value in values + [json.dumps(item) for item in data]:
            with self.subTest(value=value):
                self.assertIsNone(self.origin(value))

    def test_missing_distribution_is_not_an_error_for_direct_script(self) -> None:
        with patch("sol.core.config.package_metadata.distribution", side_effect=sol.package_metadata.PackageNotFoundError):
            self.assertIsNone(sol.installed_project_directory())

    def test_local_install_corpus_is_found_outside_checkout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sol-origin-") as directory:
            root = Path(directory)
            corpus = root / "checkout" / "local-corpus"
            corpus.mkdir(parents=True)
            (corpus / "corpus.json").write_text("{}", encoding="utf-8")
            with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(root / "configuration")}, clear=True), \
                    patch("sol.core.config.Path.cwd", return_value=root / "elsewhere"), \
                    patch("sol.core.config.installed_project_directory", return_value=corpus.parent):
                self.assertEqual(sol.discover_corpus(), corpus)


class ConfigurationPathTests(unittest.TestCase):
    def test_xdg_directory_has_priority(self) -> None:
        with patch.dict("os.environ", {"XDG_CONFIG_HOME": "/tmp/sol-xdg-fixture"}, clear=True):
            self.assertEqual(sol.config_path(), Path("/tmp/sol-xdg-fixture/sol/config.json"))

    def test_default_config_uses_home(self) -> None:
        with patch.dict("os.environ", {}, clear=True), patch("sol.core.config.Path.home", return_value=Path("/tmp/sol-home-fixture")):
            self.assertEqual(sol.config_path(), Path("/tmp/sol-home-fixture/.config/sol/config.json"))

    def test_relative_xdg_home_is_rejected(self) -> None:
        with patch.dict("os.environ", {"XDG_CONFIG_HOME": "relative"}, clear=True):
            with self.assertRaisesRegex(ValueError, "XDG_CONFIG_HOME.*absolute"):
                sol.config_path()


if __name__ == "__main__":
    unittest.main()
