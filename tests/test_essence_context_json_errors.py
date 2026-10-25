"""Malformed private launch JSON must remain a clean input refusal."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol.interchange.essence import read_context, write_context


class ContextJSONErrorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-context-json-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.fields = {"reference": {"reference": {"target_id": "invented"}},
                       "cursor_offset": 0, "selection": None, "label": "Invented",
                       "corpus": "/invented", "state_file": None}

    def deep_file(self):
        path = self.root / "deep.json"
        path.write_text("[" * 100000 + "0" + "]" * 100000)
        return path

    def test_excessive_json_nesting_is_a_value_error(self):
        with self.assertRaises(ValueError):
            read_context(self.deep_file())

    def test_launcher_reports_deep_context_without_a_traceback(self):
        from sol.essence.tui.__main__ import main

        out, err = StringIO(), StringIO()
        with patch("sol.essence.tui.__main__.textual_available", return_value=True), \
                redirect_stdout(out), redirect_stderr(err):
            status = main(["--context", str(self.deep_file())])
        self.assertEqual((status, out.getvalue()), (2, ""))
        self.assertIn("cannot open ESSENCE", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_encoding_failures_are_value_errors_before_creating_a_file(self):
        directory = self.root / "contexts"
        for failure in (RecursionError("invented deep context"), TypeError("invented non-JSON value")):
            with self.subTest(failure=type(failure).__name__), \
                    patch("sol.interchange.essence.json.dumps", side_effect=failure):
                with self.assertRaises(ValueError):
                    write_context(directory, **self.fields)
                self.assertFalse(directory.exists())

    def test_reader_rejects_values_that_cannot_round_trip_as_finite_utf8(self):
        path = self.root / "invalid-values.json"
        for invalid in (float("nan"), float("inf"), "\ud800"):
            context = {"version": 1, **self.fields, "selection": {"value": invalid}}
            path.write_text(json.dumps(context), encoding="utf-8")
            with self.subTest(invalid=repr(invalid)), self.assertRaises(ValueError):
                read_context(path)
        path.write_text(json.dumps({"version": 1, **self.fields, "selection": {"value": 1.5}})
                        .replace("1.5", "1e999"), encoding="utf-8")
        with self.assertRaises(ValueError):
            read_context(path)

    def test_valid_context_keeps_its_round_trip_and_permissions(self):
        path = write_context(self.root, **self.fields)
        self.assertEqual(read_context(path), {"version": 1, **self.fields})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
