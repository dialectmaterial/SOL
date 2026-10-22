"""Independent, bounded and read-only native ESSENCE experiment commands."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
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

    def test_word_study_and_check_are_read_only_across_processes(self):
        before = self.files()
        studied = self.run_cli(["words", "--json"])
        self.assertEqual(studied.returncode, 0, studied.stderr)
        checked = self.run_cli(["check", "-", "--json"], studied.stdout)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["status"], "current")
        self.assertEqual(self.files(), before)

    def test_retired_artifact_is_rejected_before_corpus_discovery(self):
        with patch("sol.core.discover_corpus", side_effect=AssertionError("No discovery")):
            status, output, error = self.call(["check", "-", "--json"],
                StringIO('{"protocol":"sol.term-study","version":1}'))
        self.assertEqual(status, 2)
        self.assertIn("Unsupported ESSENCE artifact", error)
        self.assertEqual(json.loads(output)["status"], "invalid")

    def test_essence_help_dispatch_is_independent_of_onboarding(self):
        from sol.app import main as app
        for args in (["essence", "--help"], ["essence", "words", "--help"],
                     ["essence", "check", "--help"]):
            output = StringIO()
            with patch("sol.core.discover_corpus", side_effect=AssertionError("No discovery")), \
                    patch("builtins.input", side_effect=AssertionError("No onboarding")), \
                    redirect_stdout(output), self.assertRaises(SystemExit) as caught:
                app.main(args)
            self.assertEqual(caught.exception.code, 0)
            self.assertIn("sol essence", output.getvalue())

    def test_old_namespace_and_removed_commands_are_rejected(self):
        from sol.app import main as app
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
            app.main(["analyze", "--help"])
        self.assertEqual(caught.exception.code, 2)
        for action in ("term", "segmentation-sample", "segmentation-export",
                       "segmentation-import", "segmentation-check"):
            with self.subTest(action=action), redirect_stderr(StringIO()), \
                    self.assertRaises(SystemExit) as caught:
                cli.main([action])
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
