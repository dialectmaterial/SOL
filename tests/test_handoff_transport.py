"""One-shot, correlated private transport with no personal-state authority."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from sol import core
from sol.corpus import contract
from sol.terminal import handoff
from sol.terminal.essence import _sol_shim
from test_packaging import write_runtime_corpus


class HandoffTransportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-transport-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "corpus"
        self.identifier, _ = write_runtime_corpus(self.corpus)
        contract.initialize_corpus_identity(self.corpus)
        self.snapshot = core.load_snapshot(self.corpus)
        self.packet = core.capture_reference(self.snapshot, self.identifier)
        self.sessions = []

    def session(self):
        session = handoff.HandoffSession.create(self.packet)
        self.sessions.append(session)
        return session

    def tearDown(self):
        for session in self.sessions:
            if session.directory.exists():
                try:
                    session.close()
                except (ValueError, OSError):
                    # Tests restore/move deliberate unexpected data into their
                    # own temporary root before this cleanup path.
                    pass

    def test_create_load_propose_read_close_are_private_and_one_shot(self):
        before = {path.name: path.read_bytes() for path in self.corpus.iterdir() if path.is_file()}
        session = self.session()
        self.assertEqual(stat.S_IMODE(session.directory.stat().st_mode), 0o700)
        for name in ("session.json", "outgoing.json"):
            self.assertEqual(stat.S_IMODE((session.directory / name).stat().st_mode), 0o600)
        packet, metadata = handoff.load_handoff(session.directory)
        self.assertEqual(packet, self.packet)
        self.assertEqual(metadata, session.metadata)
        result = handoff.submit_return(session.directory, self.snapshot)
        self.assertEqual(result["status"], "proposed")
        self.assertEqual(core.check_reference(self.snapshot, session.read_return()).requested_id, self.identifier)
        original = (session.directory / "returned.json").read_bytes()
        with self.assertRaisesRegex(handoff.HandoffError, "already present"):
            handoff.submit_return(session.directory, self.snapshot)
        self.assertEqual((session.directory / "returned.json").read_bytes(), original)
        session.close()
        session.close()
        self.assertFalse(session.directory.exists())
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.corpus.iterdir() if path.is_file()})

    def test_absent_return_is_not_an_implicit_navigation_request(self):
        session = self.session()
        with self.assertRaisesRegex(handoff.HandoffError, "No return is ready"):
            session.read_return()

    def test_failure_after_private_bin_creation_removes_only_the_new_exchange(self):
        real_stat = os.stat
        real_mkdtemp = handoff.tempfile.mkdtemp
        created = []

        def remember(*args, **kwargs):
            directory = real_mkdtemp(*args, **kwargs)
            created.append(Path(directory))
            return directory

        def fail_bin(path, *args, **kwargs):
            if path == "bin" and "dir_fd" in kwargs:
                raise OSError("Invented failure after creating the private bin directory")
            return real_stat(path, *args, **kwargs)

        with patch.object(handoff.tempfile, "mkdtemp", side_effect=remember), \
                patch.object(handoff.os, "stat", side_effect=fail_bin), \
                self.assertRaisesRegex(OSError, "Invented failure"):
            handoff.HandoffSession.create(self.packet)
        self.assertEqual(len(created), 1)
        self.assertFalse(created[0].exists())

    def test_explicit_empty_id_does_not_default_to_the_origin(self):
        session = self.session()
        with self.assertRaises(core.ProtocolError):
            handoff.submit_return(session.directory, self.snapshot, "")
        self.assertFalse((session.directory / "returned.json").exists())

    def test_response_cannot_be_replayed_into_another_exchange(self):
        first, second = self.session(), self.session()
        handoff.submit_return(first.directory, self.snapshot)
        other = second.directory / "returned.json"
        other.write_bytes((first.directory / "returned.json").read_bytes())
        other.chmod(0o600)
        with self.assertRaisesRegex(handoff.HandoffError, "another exchange"):
            second.read_return()

    def test_unknown_metadata_wrapper_fields_and_nonfinite_values_are_rejected(self):
        session = self.session()
        handoff.submit_return(session.directory, self.snapshot)
        path = session.directory / "returned.json"
        original = path.read_bytes()
        value = json.loads(original)
        value["command"] = "Never execute"
        path.write_text(json.dumps(value))
        with self.assertRaises(handoff.HandoffError):
            session.read_return()
        path.write_bytes(b'{"x":NaN}')
        with self.assertRaises(handoff.HandoffError):
            session.read_return()
        path.write_bytes(original)

    def test_core_packet_tampering_is_not_accepted_as_new_local_truth(self):
        session = self.session()
        handoff.submit_return(session.directory, self.snapshot)
        path = session.directory / "returned.json"
        value = json.loads(path.read_text())
        value["reference"]["reference"]["content_sha256"] = "0" * 64
        path.write_text(json.dumps(value))
        packet = session.read_return()  # Transport correlation is not semantic acceptance.
        with self.assertRaises(core.ProtocolError):
            core.check_reference(self.snapshot, packet)

    def test_origin_digest_changes_and_session_metadata_changes_are_refused(self):
        session = self.session()
        path = session.outgoing_file
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        with self.assertRaisesRegex(handoff.HandoffError, "fingerprint"):
            handoff.load_handoff(session.directory)
        path.write_bytes(original)
        handoff.submit_return(session.directory, self.snapshot)
        meta = deepcopy(session.metadata)
        meta["session_nonce"] = "0" * 64
        (session.directory / "session.json").write_text(json.dumps(meta))
        with self.assertRaisesRegex(handoff.HandoffError, "altered"):
            session.read_return()

    def test_private_permissions_symlinks_and_hardlinks_are_required(self):
        session = self.session()
        session.directory.chmod(0o755)
        with self.assertRaises(handoff.HandoffError):
            handoff.load_handoff(session.directory)
        session.directory.chmod(0o700)
        session.outgoing_file.chmod(0o644)
        with self.assertRaises(handoff.HandoffError):
            handoff.load_handoff(session.directory)
        session.outgoing_file.chmod(0o600)
        alias = self.root / "alias"
        alias.symlink_to(session.directory, target_is_directory=True)
        with self.assertRaises(handoff.HandoffError):
            handoff.load_handoff(alias)
        linked = self.root / "linked"
        os.link(session.outgoing_file, linked)
        with self.assertRaises(handoff.HandoffError):
            handoff.load_handoff(session.directory)
        linked.unlink()

    def test_fifo_and_oversized_return_are_rejected_without_blocking(self):
        session = self.session()
        response = session.directory / "returned.json"
        os.mkfifo(response, 0o600)
        with self.assertRaises(handoff.HandoffError):
            session.read_return()
        response.unlink()
        response.write_bytes(b"x" * (handoff.MAX_HANDOFF_BYTES + 1))
        response.chmod(0o600)
        with self.assertRaises(handoff.HandoffError):
            session.read_return()

    def test_competing_publication_preserves_existing_destination(self):
        session = self.session()
        real = os.link

        def competing(source, destination, **kwargs):
            if destination == "returned.json":
                (session.directory / destination).write_bytes(b"Competing response")
            return real(source, destination, **kwargs)

        with patch.object(handoff.os, "link", side_effect=competing), self.assertRaises(handoff.HandoffError):
            handoff.submit_return(session.directory, self.snapshot)
        self.assertEqual((session.directory / "returned.json").read_bytes(), b"Competing response")
        self.assertFalse(list(session.directory.glob(".sol-return-building-*")))

    def test_unknown_work_is_preserved_when_closing_known_transport(self):
        session = self.session()
        work = session.directory / "personal.txt"
        work.write_text("Preserve this invented personal work")
        with self.assertRaises(handoff.HandoffError):
            session.close()
        self.assertEqual(work.read_text(), "Preserve this invented personal work")
        self.assertFalse(session.outgoing_file.exists())
        work.rename(self.root / "retained.txt")
        session.close()

    def test_unexpected_or_replaced_shim_is_not_deleted(self):
        session = self.session()
        wrapper = session.directory / "bin" / "sol"
        wrapper.write_bytes(b"Invented personal script")
        wrapper.chmod(0o700)
        with self.assertRaisesRegex(handoff.HandoffError, "retained"):
            session.close()
        self.assertEqual(wrapper.read_bytes(), b"Invented personal script")
        wrapper.rename(self.root / "retained-script")
        session.close()
        other = self.session()
        original_bin = self.root / "original-bin"
        (other.directory / "bin").rename(original_bin)
        (other.directory / "bin").mkdir(mode=0o700)
        replacement = other.directory / "bin" / "sol"
        replacement.write_bytes(b"Another personal script")
        replacement.chmod(0o700)
        with self.assertRaisesRegex(handoff.HandoffError, "replaced"):
            other.close()
        self.assertTrue(replacement.exists())
        (other.directory / "bin").rename(self.root / "retained-bin")
        original_bin.rename(other.directory / "bin")
        other.close()

    def test_known_fixed_shim_can_be_cleaned_without_touching_other_files(self):
        session = self.session()
        _sol_shim(session.directory, session._identity, session._bin_identity)
        session.close()
        self.assertFalse(session.directory.exists())

    def test_opened_directory_permissions_are_rechecked(self):
        session = self.session()
        real = os.open

        def changed(path, flags, *args, **kwargs):
            descriptor = real(path, flags, *args, **kwargs)
            if Path(path) == session.directory:
                session.directory.chmod(0o755)
            return descriptor

        with patch.object(handoff.os, "open", side_effect=changed), self.assertRaises(handoff.HandoffError):
            handoff.load_handoff(session.directory)
        session.directory.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
