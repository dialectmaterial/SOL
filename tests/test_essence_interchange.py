"""Invented context transport: bounded files, strict versions and clean failures."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sol.interchange.essence import MAX_CONTEXT_BYTES, check_context, read_context, write_context


def context():
    return {"version": 1, "reference": {"reference": {"target_id": "invented-record"}},
            "cursor_offset": 0, "selection": None, "label": "Invented context",
            "corpus": "/invented", "state_file": None}


class ContextTransportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-context-transport-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def fields(self):
        return {key: value for key, value in context().items() if key != "version"}

    def test_versions_require_an_integer_not_a_boolean_or_float(self):
        for version in (True, 1.0):
            with self.subTest(version=version), self.assertRaises(ValueError):
                check_context({**context(), "version": version})

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires FIFOs")
    def test_fifo_is_refused_without_waiting_for_a_writer(self):
        path = self.root / "fifo"
        os.mkfifo(path)
        code = '''
from sol.interchange.essence import read_context
import sys
try:
    read_context(sys.argv[1])
except ValueError:
    sys.exit(0)
sys.exit(1)
'''
        run = subprocess.run([sys.executable, "-B", "-c", code, str(path)],
                             capture_output=True, timeout=2)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_writer_refuses_oversized_utf8_before_creating_a_file(self):
        fields = {**self.fields(), "label": "α" * (MAX_CONTEXT_BYTES // 2)}
        with self.assertRaises(ValueError):
            write_context(self.root, **fields)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_context_at_the_exact_utf8_limit_still_round_trips(self):
        fields = {**self.fields(), "label": ""}
        overhead = len(json.dumps({"version": 1, **fields}, ensure_ascii=False).encode("utf-8"))
        available = MAX_CONTEXT_BYTES - overhead
        fields["label"] = "α" * (available // 2) + "x" * (available % 2)
        path = write_context(self.root, **fields)
        self.assertEqual(path.stat().st_size, MAX_CONTEXT_BYTES)
        self.assertEqual(read_context(path), {"version": 1, **fields})

    def test_reader_checks_actual_bytes_even_if_stat_reports_a_small_file(self):
        path = self.root / "grown.json"
        path.write_bytes(json.dumps(context()).encode() + b" " * MAX_CONTEXT_BYTES)
        info = SimpleNamespace(st_mode=stat.S_IFREG, st_size=0)
        with patch("sol.interchange.essence.os.fstat", return_value=info), self.assertRaises(ValueError):
            read_context(path)

    def test_failed_write_removes_the_partial_context(self):
        fdopen = os.fdopen

        @contextmanager
        def interrupted(descriptor, *args):
            with fdopen(descriptor, *args) as stream:
                def write(data):
                    stream.write(data[:7])
                    raise OSError("invented interrupted write")
                yield SimpleNamespace(write=write)

        with patch("sol.interchange.essence.os.fdopen", side_effect=interrupted), self.assertRaises(OSError):
            write_context(self.root, **self.fields())
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
