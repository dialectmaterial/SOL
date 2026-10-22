"""keys.json: the reader's own key remappings, read as checked data."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol.being.neovim import host as neovim


class UserKeysTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-keys-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "keys.json"

    def write(self, value):
        self.path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")

    def test_missing_file_means_sol_defaults(self):
        self.assertEqual(neovim.user_keys(self.path), {})

    def test_remappings_are_read_from_the_config_directory(self):
        self.write({"version": 1, "keys": {"n": "J", "b": "K", "<C-n>": "<C-j>"}})
        self.assertEqual(neovim.user_keys(self.path), {"n": "J", "b": "K", "<C-n>": "<C-j>"})
        config = self.path.parent / "config"
        (config / "sol").mkdir(parents=True)
        (config / "sol" / "keys.json").write_text(self.path.read_text(), encoding="utf-8")
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}):
            self.assertEqual(neovim.user_keys()["n"], "J")

    def test_malformed_remappings_are_refused_with_the_path(self):
        for bad in ("{", [], {"keys": {"n": "J"}}, {"version": 2, "keys": {}},
                    {"version": 1, "keys": {"n": "J"}, "extra": 1}, {"version": 1, "keys": {"n": 1}},
                    {"version": 1, "keys": {"n": "J", "b": "J"}}, {"version": 1, "keys": {"n": "a b"}},
                    {"version": 1, "keys": {"n": "\x1b"}}, {"version": 1, "keys": {"n": "x" * 17}},
                    {"version": 1, "keys": {str(i): f"<F{i}>" for i in range(65)}}):
            with self.subTest(value=bad):
                self.write(bad)
                with self.assertRaisesRegex(ValueError, "keys.json"):
                    neovim.user_keys(self.path)


if __name__ == "__main__":
    unittest.main()
