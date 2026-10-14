"""One bounded input boundary for independently decoded reference/result JSON."""
from io import StringIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sol.core.wire import read_json_input


class WireInputTests(unittest.TestCase):
    def test_byte_limits_are_positive_integers_not_boolean_flags(self):
        for limit in (True, False, 0, -1, None, "10", 10.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                read_json_input("-", limit)

    def test_utf8_text_stream_limit_counts_bytes_not_characters(self):
        with patch("sys.stdin", StringIO("éé")):
            self.assertEqual(read_json_input("-", 4), "éé")
        with patch("sys.stdin", StringIO("éé")), self.assertRaisesRegex(ValueError, "exceeds"):
            read_json_input("-", 3)

    def test_interactive_input_is_refused_before_any_read(self):
        stream = StringIO("unread")
        with patch("sys.stdin", stream), patch.object(stream, "isatty", return_value=True), \
                patch.object(stream, "read", side_effect=AssertionError("Never read a terminal")), \
                self.assertRaisesRegex(ValueError, "piped input"):
            read_json_input("-", 10)

    def test_regular_file_is_read_without_decoding_or_mutation(self):
        with tempfile.TemporaryDirectory(prefix="sol-wire-test-") as temporary:
            path = Path(temporary) / "literal.json"
            path.write_bytes(b"\xff literal input is for the caller to decode")
            self.assertEqual(read_json_input(str(path), 100), path.read_bytes())

    def test_directory_symlink_fifo_and_large_file_are_refused(self):
        with tempfile.TemporaryDirectory(prefix="sol-wire-test-") as temporary:
            root = Path(temporary)
            regular = root / "regular"
            regular.write_bytes(b"{}")
            link = root / "link"
            link.symlink_to(regular)
            fifo = root / "fifo"
            os.mkfifo(fifo)
            for path in (root, link, fifo):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    read_json_input(str(path), 10)
            with self.assertRaisesRegex(ValueError, "exceeds"):
                read_json_input(str(regular), 1)


if __name__ == "__main__":
    unittest.main()
