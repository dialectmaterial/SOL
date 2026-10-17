"""Independent, bounded and read-only native ESSENCE experiment commands."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from hashlib import sha256
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sol.corpus import contract
from sol.essence import cli


class BytesStream:
    def __init__(self, content):
        self.buffer = BytesIO(content)

    def isatty(self):
        return False


class AnalysisCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-analysis-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = self.root / "invented corpus with spaces"
        self.corpus.mkdir()
        self.records = []
        self.identifiers = {}
        examples = (("BEING", "7", "Ground and ground are lexical, not conceptual."),
                    ("ESSENCE", "337", "Ground remains a ground for grounds."),
                    ("CONCEPT", "507", "The concept contains no match."))
        for page, (doctrine, label, body) in enumerate(examples, 1):
            section = self.add_record("section", f"# {doctrine}", page, label, doctrine)
            paragraph = self.add_record("paragraph", body, page, label, doctrine, parent=section["id"])
            self.identifiers[doctrine] = paragraph["id"]
        self.add_record("paragraph", "Ground awaits transcription review.", 1, "7", "BEING",
                        parent=self.records[0]["id"], transcription_status="needs_review")
        editorial = self.add_record("paragraph", "An editorial ground.", 1, "7", "BEING",
                                    parent=self.records[0]["id"])
        editorial["attribution"] = {"author": "Invented editor", "role": "editorial_note", "status": "confirmed"}
        self.manifest = {
            "contract_version": 1, "edition": {"title": "Invented lexical experiment edition"},
            "source": {"filename": "absent.pdf", "sha256": "0" * 64, "pdf_pages": 3},
            "documents": ["sample.md"],
            "page_inventory": [{"pdf_page": page, "printed_page": label, "disposition": "records"}
                               for page, label in enumerate(("7", "337", "507"), 1)],
        }
        self.write_generation()
        contract.initialize_corpus_identity(self.corpus)
        self.manifest = json.loads((self.corpus / "corpus.json").read_text())
        self.env = {**os.environ, "SOL_CORPUS": str(self.corpus),
                    "XDG_CONFIG_HOME": str(self.root / "config"),
                    "XDG_DATA_HOME": str(self.root / "data"),
                    "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                    "PYTHONDONTWRITEBYTECODE": "1"}

    def add_record(self, kind, body, page, label, doctrine, parent=None, **extra):
        number = len(self.records) + 1
        record = {"id": f"{number:08x}-0000-4000-8000-{number:012x}", "type": kind,
                  "parent_id": parent, "order": number,
                  "sources": [{"pdf_page": page, "printed_page": label}],
                  "attribution": {"author": "G. W. F. Hegel", "role": "main_text", "status": "confirmed"},
                  "reader_path": f"/{doctrine}/synthetic.txt", "reader_title": doctrine,
                  "document": "sample.md", "markdown": body, "plain_text": body.lstrip("# "),
                  "content_sha256": sha256(body.encode()).hexdigest(), "context": [], **extra}
        if kind == "section":
            record.update(title=doctrine, path=f"/{doctrine}")
        self.records.append(record)
        return record

    def write_generation(self):
        generated = {"markdown", "plain_text", "content_sha256", "document", "context"}
        markdown = "\n".join(contract.render_record(
            {key: value for key, value in record.items() if key not in generated}, record["markdown"])
            for record in self.records).encode()
        manifest = json.dumps(self.manifest, ensure_ascii=False).encode()
        index = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in self.records).encode()
        (self.corpus / "sample.md").write_bytes(markdown)
        (self.corpus / "corpus.json").write_bytes(manifest)
        (self.corpus / "index.jsonl").write_bytes(index)
        (self.corpus / "index.meta.json").write_text(json.dumps({
            "contract_version": 1, "manifest_sha256": sha256(manifest).hexdigest(),
            "source_sha256": self.manifest["source"]["sha256"],
            "documents": {"sample.md": sha256(markdown).hexdigest()},
            "index_sha256": sha256(index).hexdigest(), "record_count": len(self.records),
        }), encoding="utf-8")

    def files(self):
        return {path.relative_to(self.root): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def call(self, arguments, stdin=None):
        output, error = StringIO(), StringIO()
        with patch.dict(os.environ, self.env), redirect_stdout(output), redirect_stderr(error):
            if stdin is None:
                status = cli.main(arguments)
            else:
                with patch.object(sys, "stdin", stdin):
                    status = cli.main(arguments)
        return status, output.getvalue(), error.getvalue()

    def run_cli(self, arguments, content=None, env=None):
        return subprocess.run([sys.executable, "-B", "-m", "sol.essence.cli", *arguments],
                              cwd=self.root, env=env or self.env, input=content,
                              capture_output=True, timeout=10)

    def result(self, *arguments):
        status, output, error = self.call(["term", "ground", "--json", *arguments])
        self.assertEqual(status, 0, error)
        return json.loads(output)

    def reference(self):
        from sol.core import capture_reference, encode_reference, load_snapshot

        return encode_reference(capture_reference(load_snapshot(self.corpus), self.identifiers["BEING"]))

    def test_two_process_analysis_and_check_without_mutations(self):
        before = self.files()
        analyzed = self.run_cli(["term", "ground", "--json"])
        self.assertEqual(analyzed.returncode, 0, analyzed.stderr)
        result = json.loads(analyzed.stdout)
        self.assertEqual(result["totals"]["occurrences"], 4)
        self.assertEqual(result["totals"]["matching_passages"], 2)
        verified = self.run_cli(["check", "-", "--json"], analyzed.stdout)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        receipt = json.loads(verified.stdout)
        self.assertEqual(receipt["status"], "current")
        self.assertEqual(receipt["query"], "ground")
        self.assertEqual(receipt["corpus_id"], result["corpus"]["id"])
        self.assertEqual(receipt["generation"], result["generation"])
        self.assertEqual(receipt["totals"], result["totals"])
        self.assertEqual(receipt["matched_ids"], [match["id"] for match in result["matches"]])
        self.assertNotIn("protocol", receipt)
        self.assertEqual(self.files(), before)

    def test_prose_export_has_only_body_features_and_keeps_source_metadata(self):
        before = self.files()
        exported = self.run_cli(["prose", "--json"])
        self.assertEqual(exported.returncode, 0, exported.stderr)
        result = json.loads(exported.stdout)
        self.assertEqual(result["format"], "sol.prose-input")
        self.assertEqual(len(result["passages"]), 3)
        self.assertEqual([row["text"] for row in result["passages"]],
                         [record["plain_text"] for record in self.records if record["id"] in self.identifiers.values()])
        self.assertEqual(result["passages"][0]["metadata"]["ancestry"][0]["title"], "BEING")
        self.assertEqual(self.files(), before)
        status, output, error = self.call(["prose"])
        self.assertEqual(status, 0, error)
        self.assertIn("3 prose passages", output)
        self.assertIn("headings and image labels excluded", output)

    def test_human_summary_explains_method_locations_review_and_context(self):
        status, output, error = self.call(["term", "GROUND", "--limit", "1"])
        self.assertEqual(status, 0, error)
        for text in ("Term: ground", "not conceptual similarity", "BEING", "ESSENCE", "CONCEPT",
                     "pending/unreviewed", "1 of 2", "/BEING/synthetic.txt", "printed 7 / PDF 1",
                     self.identifiers["BEING"], "[Ground]", "increase --limit"):
            self.assertIn(text, output)
        self.assertNotIn("\x1b", output)

    def test_explicit_doctrine_and_limit_are_respected(self):
        result = self.result("--doctrine", "essence", "--limit", "1")
        self.assertEqual(result["doctrine"], "ESSENCE")
        self.assertEqual(result["totals"]["occurrences"], 2)
        self.assertEqual([item["id"] for item in result["matches"]], [self.identifiers["ESSENCE"]])
        status, output, error = self.call(["term", "ground", "--doctrine", "essence"])
        self.assertEqual(status, 0, error)
        self.assertIn("Scope: ESSENCE", output)
        self.assertEqual(output.count("n/a (no included tokens)"), 2)

    def test_no_matches_has_valid_human_and_verified_output(self):
        status, output, error = self.call(["term", "absent"])
        self.assertEqual(status, 0, error)
        self.assertIn("0 occurrences", output)
        self.assertIn("Representative passages: 0 of 0", output)
        result = self.result("--limit", "1")
        status, output, error = self.call(["check", "-"], StringIO(json.dumps(result)))
        self.assertEqual(status, 0, error)
        self.assertIn("Verified against the current corpus generation.", output)
        self.assertIn("not conceptual similarity", output)

    def test_reference_is_an_anchor_not_an_implicit_scope(self):
        before = self.files()
        status, output, error = self.call(["term", "ground", "--reference", "-", "--json"],
                                          StringIO(self.reference()))
        self.assertEqual(status, 0, error)
        result = json.loads(output)
        self.assertEqual(result["origin"]["reference"]["target_id"], self.identifiers["BEING"])
        self.assertEqual(result["totals"]["occurrences"], 4)
        self.assertIsNone(result["doctrine"])
        self.assertEqual(self.files(), before)
        status, output, error = self.call(["term", "ground", "--reference", "-"], StringIO(self.reference()))
        self.assertEqual(status, 0, error)
        self.assertIn("does not restrict scope", output)

    def test_regular_files_with_spaces_and_text_only_piped_input(self):
        saved = self.root / "saved experiment.sol-analysis.json"
        saved.write_text(json.dumps(self.result()), encoding="utf-8")
        status, output, error = self.call(["check", str(saved), "--json"])
        self.assertEqual(status, 0, error)
        piped = self.call(["check", "-", "--json"], StringIO(saved.read_text()))
        self.assertEqual((status, output, error), piped)

    def test_binary_stdin_is_preferred_and_bounded(self):
        from sol.essence.terms import MAX_RESULT_BYTES

        stream = BytesStream(json.dumps(self.result()).encode())
        with patch.object(stream.buffer, "read", wraps=stream.buffer.read) as read:
            status, output, error = self.call(["check", "-", "--json"], stream)
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output)["status"], "current")
        read.assert_called_once_with(MAX_RESULT_BYTES + 1)

    def test_explicit_corpus_overrides_environment_discovery(self):
        env = {**self.env, "SOL_CORPUS": str(self.root / "missing")}
        result = self.run_cli(["term", "ground", "--json", "--corpus", str(self.corpus)], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["totals"]["occurrences"], 4)

    def test_missing_corpus_is_not_created(self):
        missing = self.root / "missing"
        result = self.run_cli(["term", "ground", "--corpus", str(missing)])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(result.stdout)
        self.assertFalse(missing.exists())
        self.assertFalse((self.root / "config").exists())
        self.assertFalse((self.root / "data").exists())

    def test_invalid_queries_and_limits_fail_without_result(self):
        for query in ("", "two words", "*"):
            with self.subTest(query=query):
                status, output, error = self.call(["term", query, "--json"])
                self.assertNotEqual(status, 0)
                self.assertEqual(json.loads(output)["status"], "invalid")
                self.assertTrue(error)
        for limit in ("-1", "1001"):
            with self.subTest(limit=limit):
                status, output, error = self.call(["term", "ground", "--limit", limit])
                self.assertNotEqual(status, 0)
                self.assertFalse(output)

    def test_malformed_input_is_rejected_before_discovery(self):
        for args in (["check", "-", "--json"], ["term", "ground", "--reference", "-", "--json"]):
            for content in (b"", b"[]", b"{", b"\xff", b"{} {}", b'{"version":1,"version":1}'):
                with self.subTest(args=args, content=content), \
                        patch("sol.core.discover_corpus", side_effect=AssertionError("No discovery")):
                    status, output, error = self.call(args, BytesStream(content))
                self.assertNotEqual(status, 0)
                self.assertEqual(json.loads(output)["status"], "invalid")
                self.assertTrue(error)

    def test_oversize_results_and_references_are_bounded_before_discovery(self):
        from sol.core import MAX_REFERENCE_BYTES
        from sol.essence.terms import MAX_RESULT_BYTES

        for args, maximum in ((["check", "-", "--json"], MAX_RESULT_BYTES),
                              (["term", "ground", "--reference", "-", "--json"], MAX_REFERENCE_BYTES)):
            with self.subTest(args=args), patch("sol.core.discover_corpus", side_effect=AssertionError("No discovery")):
                status, output, error = self.call(args, BytesStream(b" " * (maximum + 1)))
            self.assertNotEqual(status, 0)
            self.assertIn("exceeds", error)
            self.assertEqual(json.loads(output)["status"], "invalid")
        file = self.root / "oversize.json"
        file.write_bytes(b" " * (MAX_RESULT_BYTES + 1))
        status, output, error = self.call(["check", str(file), "--json"])
        self.assertNotEqual(status, 0)
        self.assertIn("exceeds", error)

    def test_symlink_directory_fifo_and_missing_files_fail_promptly(self):
        regular = self.root / "result.json"
        regular.write_text(json.dumps(self.result()))
        symlink = self.root / "link.json"
        symlink.symlink_to(regular)
        paths = [symlink, self.root, self.root / "missing.json"]
        if hasattr(os, "mkfifo"):
            fifo = self.root / "pipe.json"
            os.mkfifo(fifo)
            paths.append(fifo)
        for path in paths:
            with self.subTest(path=path):
                result = self.run_cli(["check", str(path), "--json"])
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout)["status"], "invalid")

    def test_interactive_stdin_is_refused_without_reading(self):
        stream = StringIO("unread")
        with patch.object(stream, "isatty", return_value=True), \
                patch.object(stream, "read", side_effect=AssertionError("No interactive read")):
            for args in (["check", "-"], ["term", "ground", "--reference", "-"]):
                status, output, error = self.call(args, stream)
                self.assertNotEqual(status, 0)
                self.assertFalse(output)
                self.assertIn("interactive stdin", error)

    def test_file_replacement_during_read_is_refused(self):
        saved = self.root / "result.json"
        payload = json.dumps(self.result()).encode()
        saved.write_bytes(payload)
        original_fstat = os.fstat
        calls = 0

        def raced(descriptor):
            nonlocal calls
            calls += 1
            if calls == 2:
                saved.rename(self.root / "previous.json")
                saved.write_bytes(payload)
            return original_fstat(descriptor)

        with patch("sol.core.wire.os.fstat", side_effect=raced), \
                patch("sol.core.discover_corpus", side_effect=AssertionError("No discovery")):
            status, output, error = self.call(["check", str(saved), "--json"])
        self.assertNotEqual(status, 0)
        self.assertIn("changed while reading", error)
        self.assertEqual(json.loads(output)["status"], "invalid")

    def test_stale_result_and_foreign_corpus_are_not_repaired(self):
        result = self.result()
        record = self.records[5]
        record["markdown"] = record["plain_text"] = "A newly corrected concept passage."
        record["content_sha256"] = sha256(record["markdown"].encode()).hexdigest()
        self.write_generation()
        before = self.files()
        status, output, error = self.call(["check", "-", "--json"], StringIO(json.dumps(result)))
        self.assertNotEqual(status, 0)
        self.assertEqual(json.loads(output)["status"], "stale")
        self.assertEqual(self.files(), before)
        self.manifest["corpus_id"] = "ffffffff-0000-4000-8000-000000000001"
        self.write_generation()
        status, output, error = self.call(["check", "-", "--json"], StringIO(json.dumps(result)))
        self.assertNotEqual(status, 0)
        self.assertEqual(json.loads(output)["status"], "mismatch")

    def test_forged_match_ids_counts_and_payload_paths_fail(self):
        original = self.result()
        for change in ("id", "count", "path"):
            result = deepcopy(original)
            if change == "id":
                result["matches"][0]["id"] = "eeeeeeee-0000-4000-8000-000000000001"
            elif change == "count":
                result["totals"]["occurrences"] += 1
            else:
                result["corpus_path"] = "/private/never-discovered"
            with self.subTest(change=change):
                status, output, error = self.call(["check", "-", "--json"], StringIO(json.dumps(result)))
                self.assertNotEqual(status, 0)
                self.assertIn("code", json.loads(output))

    def test_unresolved_and_stale_reference_anchors_are_refused(self):
        origin = json.loads(self.reference())
        for key in ("requested_id", "target_id"):
            origin["reference"][key] = "eeeeeeee-0000-4000-8000-000000000001"
        origin["reference"]["chain"] = [origin["reference"]["target_id"]]
        status, output, error = self.call(["term", "ground", "--reference", "-", "--json"],
                                          StringIO(json.dumps(origin)))
        self.assertNotEqual(status, 0)
        self.assertEqual(json.loads(output)["status"], "unresolved")
        origin = self.reference()
        record = self.records[5]
        record["markdown"] = record["plain_text"] = "Another corrected concept passage."
        record["content_sha256"] = sha256(record["markdown"].encode()).hexdigest()
        self.write_generation()
        status, output, error = self.call(["term", "ground", "--reference", "-", "--json"], StringIO(origin))
        self.assertNotEqual(status, 0)
        self.assertEqual(json.loads(output)["status"], "stale")

    def test_human_errors_escape_terminal_and_bidi_controls(self):
        unsafe = "unsafe\x1b[31m\x08\u202e.json"
        status, output, error = self.call(["check", str(self.root / unsafe), "--json"])
        self.assertNotEqual(status, 0)
        for control in ("\x1b", "\x08", "\u202e"):
            self.assertNotIn(control, output + error)
        self.assertTrue("\\u001b" in error or "\\x1b" in error)
        self.assertIn("\\u202e", error)
        self.assertEqual(cli._safe("line\n\r\t\x7f\x9b\u2066"),
                         "line\\u000a\\u000d\\u0009\\u007f\\u009b\\u2066")

    def test_human_source_contexts_paths_and_labels_are_safely_rendered(self):
        result = self.result()
        match = result["matches"][0]
        match["reader_path"] += "\x1b[31m\u202e"
        match["sources"][0]["printed_page"] += "\x08"
        match["first_match"]["context"] += "\x1b]0;title\x07"
        rendered = cli.render_result(result)
        for control in ("\x1b", "\x08", "\x07", "\u202e"):
            self.assertNotIn(control, rendered)
        self.assertIn("\\u001b", rendered)

    def test_context_is_folded_to_terminal_width_without_wrapping_identifiers(self):
        result = self.result()
        with patch("sol.essence.cli.shutil.get_terminal_size", return_value=os.terminal_size((44, 24))):
            rendered = cli.render_result(result)
        context_lines = [line for line in rendered.splitlines() if line.startswith("  ")
                         and not any(doctrine in line for doctrine in ("BEING", "ESSENCE", "CONCEPT"))]
        self.assertGreater(len(context_lines), 2)
        self.assertTrue(all(len(line) <= 44 for line in context_lines))
        self.assertIn(self.identifiers["BEING"], rendered)

    def test_help_never_discovers_or_opens_application_data(self):
        for arguments in (["--help"], ["term", "--help"], ["check", "--help"], ["prose", "--help"]):
            with self.subTest(arguments=arguments), \
                    patch("sol.core.discover_corpus", side_effect=AssertionError("No discovery")), \
                    patch("sol.core.load_snapshot", side_effect=AssertionError("No load")), \
                    redirect_stdout(StringIO()), self.assertRaises(SystemExit) as caught:
                cli.main(arguments)
            self.assertEqual(caught.exception.code, 0)

    def test_module_help_has_no_reader_workspace_or_terminal_imports(self):
        script = ("import contextlib,io,sys; from sol.essence import cli; "
                  "stream=io.StringIO(); "
                  "\nwith contextlib.redirect_stdout(stream):\n"
                  " try: cli.main(['term','--help'])\n except SystemExit: pass\n"
                  "bad=[name for name in sys.modules if name.startswith(('sol.reader','sol.workspace',"
                  "'sol.terminal','prompt_toolkit','rich','textual','fitz'))]; "
                  "assert not bad,bad")
        result = subprocess.run([sys.executable, "-B", "-c", script], cwd=self.root,
                                env=self.env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
