"""Private BEING -> ESSENCE positions contain no passage prose."""
from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch

from fixtures_corpus import CorpusFixture
from sol import core
from sol.interchange.essence import (MAX_CONTEXT_BYTES, POSITION_VERSION,
                                     check_position, read_position, write_position)


class PositionExchangeTests(CorpusFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.private = tempfile.TemporaryDirectory()
        self.addCleanup(self.private.cleanup)
        self.path = Path(self.private.name) / "context.json.position"
        self.fields = dict(reference=core.capture_reference(self.book.corpus_snapshot, self.book.passages[0].identifier),
                           cursor_offset=3, selection=None, label="Invented heading | p. 7")

    def test_round_trip_and_checked_reference(self):
        self.assertEqual(write_position(self.path, **self.fields), self.path)
        position = read_position(self.path)
        self.assertEqual(position, {"version": POSITION_VERSION, **self.fields})
        self.assertEqual(core.check_reference(self.book.corpus_snapshot, position["reference"]).target_id,
                         self.fields["reference"]["reference"]["target_id"])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertNotIn(self.book.passages[0].text, self.path.read_text())
        selected = {"start": 2, "end": 5, "content_sha256": "0" * 64}
        write_position(self.path, **{**self.fields, "selection": selected, "label": "Heading α"})
        self.assertEqual(read_position(self.path)["selection"], selected)

    def test_invalid_positions_and_size_are_refused_before_write(self):
        write_position(self.path, **self.fields)
        before = self.path.read_bytes()
        base = {"version": 1, **self.fields}
        for change in ({"version": True}, {"version": 2}, {"cursor_offset": True}, {"cursor_offset": -1},
                       {"cursor_offset": 1.5}, {"selection": "prose"}, {"selection": {"text": "prose"}}, {"label": None}, {"reference": {}},
                       {"extra": 1}, {"label": "x" * MAX_CONTEXT_BYTES},
                       {"reference": {**self.fields["reference"], "version": 2}},
                       {"reference": {**self.fields["reference"], "protocol": "untrusted"}}):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                check_position({**base, **change})
        for field in base:
            broken = deepcopy(base)
            del broken[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                check_position(broken)
        with self.assertRaises(ValueError):
            write_position(self.path, **{**self.fields, "cursor_offset": -1})
        self.assertEqual(self.path.read_bytes(), before)

    def test_replace_is_atomic_and_failed_replace_preserves_previous_file(self):
        write_position(self.path, **self.fields)
        before = read_position(self.path)
        replace = os.replace

        def publish(source, destination, **kwargs):
            self.assertEqual(read_position(self.path), before)
            pending = self.path.parent / source
            self.assertEqual(json.loads(pending.read_bytes())["cursor_offset"], 8)
            self.assertEqual(stat.S_IMODE(pending.stat().st_mode), 0o600)
            replace(source, destination, **kwargs)

        with patch("sol.interchange.essence.os.replace", side_effect=publish):
            write_position(self.path, **{**self.fields, "cursor_offset": 8})
        self.assertEqual(read_position(self.path)["cursor_offset"], 8)
        old_bytes = self.path.read_bytes()
        with patch("sol.interchange.essence.os.replace", side_effect=OSError("refused")), self.assertRaises(OSError):
            write_position(self.path, **self.fields)
        self.assertEqual(self.path.read_bytes(), old_bytes)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_temp_collision_never_removes_or_follows_an_existing_link(self):
        write_position(self.path, **self.fields)
        before = self.path.read_bytes()
        candidate = self.path.with_name(f".{self.path.name}.collision.tmp")
        candidate.symlink_to(self.path)
        with patch("sol.interchange.essence.secrets.token_hex", return_value="collision"), self.assertRaises(FileExistsError):
            write_position(self.path, **{**self.fields, "cursor_offset": 8})
        self.assertTrue(candidate.is_symlink())
        self.assertEqual(self.path.read_bytes(), before)

    def test_concurrent_readers_only_see_complete_files(self):
        write_position(self.path, **self.fields)
        errors = []
        done = threading.Event()

        def reader():
            while not done.is_set():
                try:
                    check_position(read_position(self.path))
                except BaseException as error:
                    errors.append(error)
                    break

        worker = threading.Thread(target=reader)
        worker.start()
        try:
            for offset in range(50):
                write_position(self.path, **{**self.fields, "cursor_offset": offset})
        finally:
            done.set()
            worker.join()
        self.assertEqual(errors, [])

    def test_links_permissions_wrong_owner_and_special_files_are_refused(self):
        write_position(self.path, **self.fields)
        link = self.path.with_name("link")
        link.symlink_to(self.path)
        before = self.path.read_bytes()
        with self.assertRaises(OSError):
            read_position(link)
        with self.assertRaises(ValueError):
            write_position(link, **self.fields)
        self.assertEqual(self.path.read_bytes(), before)
        self.path.chmod(0o644)
        for operation in (lambda: read_position(self.path), lambda: write_position(self.path, **self.fields)):
            with self.assertRaises(ValueError):
                operation()
        self.path.chmod(0o600)
        with patch("sol.interchange.essence.os.getuid", return_value=os.getuid() + 1):
            with self.assertRaises(ValueError):
                read_position(self.path)
            with self.assertRaises(ValueError):
                write_position(self.path, **self.fields)
        self.path.parent.chmod(0o755)
        with self.assertRaises(ValueError):
            write_position(self.path, **self.fields)
        self.path.parent.chmod(0o700)
        self.path.unlink()
        os.mkfifo(self.path, 0o600)
        with self.assertRaises(ValueError):
            read_position(self.path)  # Nonblocking open, even without a writer.
        with self.assertRaises(ValueError):
            write_position(self.path, **self.fields)

    def test_oversized_and_malformed_file_is_refused(self):
        for data in (b"x" * (MAX_CONTEXT_BYTES + 1), b"not json", b"\xff"):
            self.path.write_bytes(data)
            self.path.chmod(0o600)
            with self.assertRaises(ValueError):
                read_position(self.path)
