"""Bounded, read-only reference exchange between independent local processes."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from hashlib import sha256
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.corpus import contract
from sol.core import reference_cli as reference


class ReferenceCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-reference-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "editorial corpus"
        self.corpus.mkdir()
        self.section_id = "aaaaaaaa-0000-4000-8000-000000000001"
        self.identifier = "bbbbbbbb-0000-4000-8000-000000000002"
        self.retired_id = "cccccccc-0000-4000-8000-000000000003"
        self.body = "An invented editorial passage, outside the Hegel reader projection."
        common = {
            "sources": [{"pdf_page": 1, "printed_page": "i", "bbox": [1, 2, 30, 40],
                         "private_path": "/private/evidence.pdf"}],
            "attribution": {"author": "Invented editor", "status": "confirmed",
                            "role": "editorial_note", "private_email": "private@example.invalid"},
        }
        metadata = [
            {**deepcopy(common), "id": self.section_id, "type": "section", "parent_id": None,
             "order": 0, "title": "Invented editorial heading", "path": "/editorial"},
            {**deepcopy(common), "id": self.identifier, "type": "paragraph",
             "parent_id": self.section_id, "order": 1},
            {**deepcopy(common), "id": self.retired_id, "type": "retired_record",
             "parent_id": self.section_id, "order": 2, "redirect_id": self.identifier},
        ]
        self.records = []
        for item, text in zip(metadata, ("# Invented editorial heading", self.body, "Retired editorial record.")):
            self.records.append({**item, "markdown": text, "plain_text": text.lstrip("# "),
                                 "content_sha256": sha256(text.encode()).hexdigest(),
                                 "document": "editorial.md", "context": []})
        self.manifest = {
            "contract_version": 1,
            "edition": {"title": "Invented edition", "private_path": "/private/edition"},
            "source": {"filename": "absent.pdf", "sha256": "0" * 64, "pdf_pages": 1},
            "documents": ["editorial.md"],
            "page_inventory": [{"pdf_page": 1, "printed_page": "i", "disposition": "records"}],
        }
        self.write_generation()
        # Identity creation is a deliberate fixture setup, never part of exchange.
        contract.initialize_corpus_identity(self.corpus)
        self.manifest = json.loads((self.corpus / "corpus.json").read_text())
        self.env = {**os.environ, "SOL_CORPUS": str(self.corpus),
                    "XDG_CONFIG_HOME": str(self.root / "config"),
                    "XDG_DATA_HOME": str(self.root / "data"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(Path(__file__).resolve().parents[1])}

    def write_generation(self):
        markdown = "\n".join(contract.render_record(
            {key: value for key, value in item.items()
             if key not in {"markdown", "plain_text", "content_sha256", "document", "context"}},
            item["markdown"],
        ) for item in self.records).encode()
        manifest = json.dumps(self.manifest, ensure_ascii=False).encode()
        index = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in self.records).encode()
        (self.corpus / "editorial.md").write_bytes(markdown)
        (self.corpus / "corpus.json").write_bytes(manifest)
        (self.corpus / "index.jsonl").write_bytes(index)
        metadata = {
            "contract_version": 1, "manifest_sha256": sha256(manifest).hexdigest(),
            "source_sha256": self.manifest["source"]["sha256"],
            "documents": {"editorial.md": sha256(markdown).hexdigest()},
            "index_sha256": sha256(index).hexdigest(), "record_count": len(self.records),
        }
        (self.corpus / "index.meta.json").write_text(json.dumps(metadata), encoding="utf-8")

    def run_cli(self, arguments, content=None, env=None):
        return subprocess.run([sys.executable, "-B", "-m", "sol", "reference", *arguments],
                              cwd=self.root, env=env or self.env, input=content,
                              capture_output=True, timeout=10)

    def capture(self, identifier=None):
        result = self.run_cli(["capture", identifier or self.identifier])
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def call(self, arguments, stdin=None):
        output, error = StringIO(), StringIO()
        with patch.dict(os.environ, self.env), redirect_stdout(output), redirect_stderr(error):
            if stdin is None:
                status = reference.main(arguments)
            else:
                with patch.object(sys, "stdin", stdin):
                    status = reference.main(arguments)
        return status, output.getvalue(), error.getvalue()

    def files(self):
        return {path.relative_to(self.root): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_two_process_round_trip_preserves_identity_and_projected_provenance(self):
        before = self.files()
        capture = self.capture()
        payload = json.loads(capture)
        result = self.run_cli(["check", "-"], capture)
        self.assertEqual(result.returncode, 0, result.stderr)
        checked = json.loads(result.stdout)
        self.assertEqual(checked["status"], "current")
        self.assertEqual(checked["corpus_id"], payload["corpus"]["id"])
        self.assertEqual(checked["generation"], payload["generation"])
        self.assertEqual(checked["requested_id"], self.identifier)
        self.assertEqual(checked["target_id"], self.identifier)
        self.assertEqual(checked["chain"], [self.identifier])
        self.assertEqual(checked["content_sha256"], self.records[1]["content_sha256"])
        self.assertEqual(checked["sources"], payload["reference"]["sources"])
        self.assertEqual(checked["attribution"], {"author": "Invented editor", "role": "editorial_note",
                                               "status": "confirmed"})
        for secret in (self.body.encode(), b"private_path", b"private_email", b"/private", b"absent.pdf"):
            self.assertNotIn(secret, capture + result.stdout)
        self.assertEqual(self.files(), before)

    def test_regular_file_and_default_stdin_have_identical_results(self):
        capture = self.capture()
        file = self.root / "reference.json"
        file.write_bytes(capture)
        from_file = self.run_cli(["check", str(file)])
        piped = self.run_cli(["check"], capture)
        self.assertEqual(from_file.returncode, 0, from_file.stderr)
        self.assertEqual(from_file.stdout, piped.stdout)

    def test_text_only_stdin_fallback_supports_test_and_embedding_streams(self):
        status, output, error = self.call(["check"], StringIO(self.capture().decode()))
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output)["status"], "current")

    def test_binary_stdin_is_preferred_and_read_is_bounded(self):
        from sol.core import MAX_REFERENCE_BYTES

        class Stream:
            buffer = BytesIO(self.capture())
            def isatty(self):
                return False
            def read(self, size):
                raise AssertionError("Use the binary stream")

        with patch.object(Stream.buffer, "read", wraps=Stream.buffer.read) as read:
            status, output, error = self.call(["check"], Stream())
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output)["status"], "current")
        read.assert_called_once_with(MAX_REFERENCE_BYTES + 1)

    def test_explicit_corpus_overrides_discovery_and_has_no_reader_projection(self):
        env = {**self.env, "SOL_CORPUS": str(self.root / "missing")}
        result = self.run_cli(["capture", self.identifier, "--corpus", str(self.corpus)], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["reference"]["type"], "paragraph")

    def test_prefix_capture_and_retirement_chain(self):
        payload = json.loads(self.capture("cccccccc"))
        self.assertEqual(payload["reference"]["requested_id"], self.retired_id)
        result = self.run_cli(["check"], json.dumps(payload).encode())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["chain"], [self.retired_id, self.identifier])

    def test_capture_unknown_identifier_returns_error_without_payload(self):
        before = self.files()
        result = self.run_cli(["capture", "eeeeeeee"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"unresolved", result.stderr.lower())
        self.assertFalse(result.stdout)
        self.assertEqual(self.files(), before)

    def test_capture_needs_explicit_identity_initialization(self):
        self.manifest.pop("corpus_id")
        self.write_generation()
        before = self.files()
        result = self.run_cli(["capture", self.identifier])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"--initialize-identity", result.stderr)
        self.assertFalse(result.stdout)
        self.assertEqual(self.files(), before)

    def test_copy_and_move_preserve_a_current_reference(self):
        payload = self.capture()
        copy = self.root / "copy"
        shutil.copytree(self.corpus, copy)
        moved = self.root / "moved"
        self.corpus.rename(moved)
        for selected in (copy, moved):
            with self.subTest(corpus=selected):
                result = self.run_cli(["check", "--corpus", str(selected)], payload)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_corpus_fails_even_when_source_and_record_ids_match(self):
        payload = self.capture()
        self.manifest["corpus_id"] = "dddddddd-0000-4000-8000-000000000004"
        self.write_generation()
        before = self.files()
        result = self.run_cli(["check"], payload)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], "mismatch")
        self.assertIn("code", json.loads(result.stdout))
        self.assertEqual(self.files(), before)

    def test_valid_new_generation_is_stale_even_when_target_text_is_unchanged(self):
        payload = self.capture()
        self.manifest["edition"]["title"] = "Revised invented edition"
        self.write_generation()
        before = self.files()
        result = self.run_cli(["check"], payload)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(json.loads(result.stdout)["status"], {"stale", "mismatch"})
        self.assertEqual(self.files(), before)

    def test_changed_target_digest_in_valid_generation_refuses_old_capture(self):
        payload = self.capture()
        record = self.records[1]
        record["markdown"] = record["plain_text"] = "A newly corrected invented editorial passage."
        record["content_sha256"] = sha256(record["markdown"].encode()).hexdigest()
        self.write_generation()
        result = self.run_cli(["check"], payload)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["status"], "stale")

    def test_unindexed_edit_fails_without_repairing_the_corpus(self):
        payload = self.capture()
        file = self.corpus / "editorial.md"
        file.write_bytes(file.read_bytes() + b"\n")
        before = self.files()
        result = self.run_cli(["check"], payload)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"reindex", result.stderr)
        self.assertEqual(self.files(), before)

    def test_bad_json_is_rejected_before_corpus_discovery(self):
        for content in (b"", b"[]", b"{", b"\xff", b"{} {}", b'{"version":1,"version":1}',
                        b'{"version":NaN}', b'{"version":1e400}'):
            with self.subTest(content=content), \
                    patch("sol.core.discover_corpus", side_effect=AssertionError("Do not inspect corpus")):
                status, output, error = self.call(["check"], BytesStream(content))
                self.assertNotEqual(status, 0)
                self.assertEqual(json.loads(output)["status"], "invalid")
                self.assertTrue(error)

    def test_payload_paths_commands_and_unknown_nested_fields_are_refused(self):
        original = json.loads(self.capture())
        before = self.files()
        for path, key, value in (((), "corpus_path", "/private/other-corpus"),
                                 ((), "command", "touch /tmp/never-executed"),
                                 (("corpus",), "directory", "/private/other-corpus"),
                                 (("reference",), "path", "../../other-file")):
            payload = deepcopy(original)
            target = payload
            for field in path:
                target = target[field]
            target[key] = value
            with self.subTest(field=key):
                result = self.run_cli(["check"], json.dumps(payload).encode())
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["status"], "invalid")
        self.assertEqual(self.files(), before)

    def test_oversize_file_and_stream_are_rejected_before_corpus_selection(self):
        from sol.core import MAX_REFERENCE_BYTES

        content = b" " * (MAX_REFERENCE_BYTES + 1)
        file = self.root / "too-large.json"
        file.write_bytes(content)
        for args, stream in ((["check", str(file)], None), (["check"], BytesStream(content)),
                             (["check"], StringIO("é" * (MAX_REFERENCE_BYTES // 2 + 1)))):
            with self.subTest(args=args, stream=type(stream).__name__), \
                    patch("sol.core.discover_corpus", side_effect=AssertionError("Do not inspect corpus")):
                status, output, error = self.call(args, stream)
                self.assertNotEqual(status, 0)
                self.assertIn("exceeds", error)
                self.assertEqual(json.loads(output)["status"], "invalid")

    def test_file_symlink_directory_fifo_and_missing_input_fail_promptly(self):
        regular = self.root / "reference.json"
        regular.write_bytes(self.capture())
        symlink = self.root / "link.json"
        symlink.symlink_to(regular)
        inputs = [symlink, self.root, self.root / "missing.json"]
        if hasattr(os, "mkfifo"):
            fifo = self.root / "pipe.json"
            os.mkfifo(fifo)
            inputs.append(fifo)
        for file in inputs:
            with self.subTest(file=file):
                result = self.run_cli(["check", str(file)])
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["status"], "invalid")

    def test_interactive_stdin_is_refused_without_reading(self):
        stream = StringIO("unread")
        with patch.object(stream, "isatty", return_value=True), \
                patch.object(stream, "read", side_effect=AssertionError("Do not read interactive input")):
            for args in (["check"], ["check", "-"]):
                status, output, error = self.call(args, stream)
                self.assertNotEqual(status, 0)
                self.assertIn("JSON FILE or piped input", error)
                self.assertEqual(json.loads(output)["status"], "invalid")

    def test_file_change_or_replacement_during_read_is_refused(self):
        payload = self.capture()
        file = self.root / "reference.json"
        original_fstat = os.fstat
        for mutation in ("edit", "replace", "symlink"):
            if file.is_symlink():
                file.unlink()
            file.write_bytes(payload)
            calls = 0

            def raced_fstat(descriptor):
                nonlocal calls
                calls += 1
                if calls == 2:
                    if mutation == "edit":
                        file.write_bytes(payload + b" ")
                    else:
                        previous = self.root / ("original-" + mutation + ".json")
                        file.rename(previous)
                        if mutation == "replace":
                            file.write_bytes(payload)
                        else:
                            file.symlink_to(previous)
                return original_fstat(descriptor)

            with self.subTest(mutation=mutation), patch("sol.core.wire.os.fstat", side_effect=raced_fstat), \
                    patch("sol.core.discover_corpus", side_effect=AssertionError("Unstable input must fail first")):
                status, output, error = self.call(["check", str(file)])
                self.assertNotEqual(status, 0)
                self.assertIn("changed while reading", error)
                self.assertEqual(json.loads(output)["status"], "invalid")

    def test_missing_corpus_is_not_created(self):
        missing = self.root / "unconfigured"
        for action in (["capture", self.identifier], ["check"]):
            content = self.capture() if action[0] == "check" else None
            result = self.run_cli([*action, "--corpus", str(missing)], content)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(missing.exists())
        self.assertFalse((self.root / "config").exists())
        self.assertFalse((self.root / "data").exists())

    def test_help_performs_no_corpus_discovery_or_loading(self):
        for args in (["--help"], ["capture", "--help"], ["check", "--help"]):
            output = StringIO()
            with self.subTest(args=args), redirect_stdout(output), \
                    patch("sol.core.discover_corpus", side_effect=AssertionError("Help must not discover")), \
                    patch("sol.core.load_snapshot", side_effect=AssertionError("Help must not load")):
                with self.assertRaises(SystemExit) as result:
                    reference.main(args)
                self.assertEqual(result.exception.code, 0)
                self.assertIn("usage: sol reference", output.getvalue())

    def test_fresh_process_capture_and_check_import_no_optional_ui_or_extraction(self):
        script = """
import builtins, sys
from pathlib import Path
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(('markdown_it', 'prompt_toolkit', 'textual', 'rich', 'fitz',
                        'pypdf', 'pdfplumber', 'opendataloader', 'torch', 'tensorflow',
                        'sol.being.workspace', 'sol.reader.legacy_pdf', 'sol.corpus.extraction',
                        'sol.terminal.prompt', 'sol.terminal.comparison', 'sol.core.source')):
        raise AssertionError('Unexpected reference dependency: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
if '--help' in sys.argv:
    def no_data_io(*args, **kwargs):
        raise AssertionError('Reference help must not read or create application data')
    Path.read_text = no_data_io
    Path.read_bytes = no_data_io
    Path.mkdir = no_data_io
from sol.app.main import main
raise SystemExit(main(sys.argv[1:]))
"""
        cases = ((["capture", self.identifier], None), (["check"], self.capture()),
                 (["--help"], None), (["capture", "--help"], None), (["check", "--help"], None))
        for args, content in cases:
            result = subprocess.run([sys.executable, "-B", "-c", script, "reference", *args],
                                    cwd=self.root, env=self.env, input=content,
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)


class BytesStream:
    def __init__(self, content):
        self.buffer = BytesIO(content)

    def isatty(self):
        return False


if __name__ == "__main__":
    unittest.main()
