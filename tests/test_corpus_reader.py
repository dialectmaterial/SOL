"""Corpus reader integration, using only synthetic redistributable prose."""

from __future__ import annotations

import builtins
import contextlib
import io
import json
from pathlib import Path
import tempfile
from contextlib import nullcontext
import unittest
from unittest.mock import patch

import sol.reader.app as sol
import sol.corpus.contract as contract
from sol.core import config


class CorpusReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cwd = Path(self.temporary.name)
        environment = patch.dict("os.environ", {"XDG_CONFIG_HOME": str(self.cwd / "config")}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        origin = patch("sol.core.config.installed_project_directory", return_value=None)
        origin.start()
        self.addCleanup(origin.stop)
        script = patch("sol.core.config.__file__", str(self.cwd / "not-a-checkout" / "sol" / "core" / "config.py"))
        script.start()
        self.addCleanup(script.stop)
        self.corpus = self.cwd / "local-corpus"
        self.corpus.mkdir()
        self.ids = [contract.new_id() for _ in range(11)]
        self.pairs = [
            (self.record(0, "section", None, reader_path="/BEING", title="Doctrine of Being"), "# Doctrine of Being"),
            (self.record(1, "section", 0, reader_path="/BEING/01-sample", title="Sample chapter"), "## Sample chapter"),
            (self.record(2, "paragraph", 1, reader_path="/BEING/01-sample/00-introduction.txt", reader_title="Introduction — Sample chapter"), "This is a synthetic introductory paragraph with enough ordinary prose words for a random reader."),
            (self.record(3, "section", 1, reader_path="/BEING/01-sample/A-sample-leaf.txt", title="Sample leaf", label="A"), "### Sample leaf"),
            (self.record(4, "paragraph", 3, reader_path="/BEING/01-sample/A-sample-leaf.txt", reader_title="Sample leaf", sources=[{"pdf_page": 80, "printed_page": "7"}, {"pdf_page": 81, "printed_page": "8"}], note_ids=[self.ids[6]]), "A *synthetic* paragraph spans two source pages while preserving its opaque identifier and semantic context."),
            (self.record(5, "formula", 3, reader_path="/BEING/01-sample/A-sample-leaf.txt", reader_title="Sample leaf"), "x = α / β. This formula's approximate description contains enough words but is never randomly selected."),
            (self.record(6, "note", 3, backlinks=[self.ids[4]], attribution={"author": None, "status": "unresolved", "role": "editorial_note"}), "A synthetic note is retained in the canonical corpus but not mixed into default quotations."),
            (self.record(7, "paragraph", 3, reader_path="/BEING/01-sample/A-sample-leaf.txt", reader_title="Sample leaf", attribution={"author": "Synthetic Editor", "status": "confirmed", "role": "editorial"}), "An editorial paragraph must not become Hegel's main prose in the reader."),
            (self.record(8, "reference", 3), "A synthetic bibliographic reference."),
            (self.record(9, "section", None, reader_path="/ESSENCE", title="Doctrine of Essence"), "# Doctrine of Essence"),
            (self.record(10, "section", None, reader_path="/CONCEPT", title="Doctrine of the Concept"), "# Doctrine of the Concept"),
        ]
        self.write_corpus()

    def record(self, index: int, kind: str, parent: int | None, **extra) -> dict:
        return {
            "id": self.ids[index], "type": kind, "parent_id": self.ids[parent] if parent is not None else None,
            "order": index, "sources": [{"pdf_page": 80, "printed_page": "7"}],
            "attribution": {"author": "G. W. F. Hegel", "status": "confirmed", "role": "main_text"},
            **extra,
        }

    def write_corpus(self) -> None:
        manifest = {
            "contract_version": 1, "edition": {"title": "Synthetic reader edition"},
            "source": {"filename": "nonexistent.pdf", "sha256": "0" * 64, "pdf_pages": 81},
            "documents": ["sample.md"],
            "page_inventory": [
                {"pdf_page": page, "printed_page": None, "disposition": "blank", "reason": "Synthetic blank page"}
                for page in range(1, 80)
            ] + [
                {"pdf_page": 80, "printed_page": "7", "disposition": "records"},
                {"pdf_page": 81, "printed_page": "8", "disposition": "records"},
            ],
        }
        (self.corpus / "corpus.json").write_text(json.dumps(manifest), encoding="utf-8")
        (self.corpus / "sample.md").write_text("\n".join(contract.render_record(metadata, body) for metadata, body in self.pairs), encoding="utf-8")
        contract.reindex(self.corpus)

    def run_main(self, arguments: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), patch("sol.reader.app.Path.cwd", return_value=cwd or self.cwd):
            status = sol.main(arguments)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_loads_main_prose_and_formula_but_excludes_notes_editor_and_references(self) -> None:
        book = sol.load_corpus_book(self.corpus)
        self.assertEqual([passage.identifier for passage in book.passages], [self.ids[2], self.ids[4], self.ids[5]])
        self.assertEqual([child.name for child in book.root.children], ["BEING", "ESSENCE", "CONCEPT"])
        self.assertEqual(book.passages[1].text, "A synthetic paragraph spans two source pages while preserving its opaque identifier and semantic context.")
        self.assertEqual(book.passages[2].kind, "formula")

    def test_paths_parent_links_aliases_and_introductions(self) -> None:
        book = sol.load_corpus_book(self.corpus)
        chapter, chapter_path = sol.resolve_path("/being/sample", (), book.root)
        self.assertTrue(chapter.is_directory)
        self.assertEqual(chapter.children[0].name, "00-introduction.txt")
        leaf, leaf_path = sol.resolve_path("sample-leaf", chapter_path, book.root)
        self.assertFalse(leaf.is_directory)
        self.assertEqual(sol.node_path(leaf), leaf_path)
        parent, parent_path = sol.resolve_path("..", chapter_path, book.root)
        self.assertEqual(parent.name, "BEING")
        self.assertEqual(parent_path, ("BEING",))

    def test_uuid_page_ranges_and_folding(self) -> None:
        passage = sol.load_corpus_book(self.corpus).passages[1]
        rendered = sol.render_passage(passage, 40)
        self.assertEqual((passage.pdf_page, passage.end_pdf_page, passage.printed_page, passage.end_printed_page), (80, 81, 7, 8))
        self.assertIn("Book pp. 7–8", rendered)
        self.assertIn("PDF pp. 80–81", rendered)
        self.assertIn(self.ids[4], rendered)
        self.assertTrue(all(len(line) <= 40 for line in rendered.splitlines()))

    def test_reader_retains_full_canonical_records_and_note_attribution(self) -> None:
        book = sol.load_corpus_book(self.corpus)
        self.assertEqual(book.corpus_directory, self.corpus.resolve())
        self.assertEqual(len(book.canonical_records), len(self.pairs))
        passage = book.canonical_records[self.ids[4]]
        self.assertIn("*synthetic*", passage["markdown"])
        self.assertEqual(passage["parent_id"], self.ids[3])
        self.assertEqual(passage["note_ids"], [self.ids[6]])
        self.assertEqual(book.canonical_records[self.ids[6]]["attribution"]["role"], "editorial_note")

    def test_json_exposes_canonical_metadata_without_mutating_the_book(self) -> None:
        status, stdout, stderr = self.run_main(["--passage", self.ids[4], "--json"])
        self.assertEqual(status, 0, stderr)
        canonical = json.loads(stdout)["canonical"]
        self.assertEqual(canonical["id"], self.ids[4])
        self.assertIn("*synthetic*", canonical["markdown"])
        self.assertEqual(canonical["document"], "sample.md")
        self.assertEqual(len(canonical["sources"]), 2)
        self.assertEqual(canonical["attribution"]["author"], "G. W. F. Hegel")
        book = sol.load_corpus_book(self.corpus)
        exported = sol.passage_data(book.passages[1], book)
        exported["canonical"]["attribution"]["author"] = "Changed only in exported data"
        self.assertEqual(book.canonical_records[self.ids[4]]["attribution"]["author"], "G. W. F. Hegel")

    def test_sequential_navigation_includes_formula_and_random_does_not(self) -> None:
        book = sol.load_corpus_book(self.corpus)
        _, path = sol.resolve_path("/being/sample/sample-leaf", (), book.root)
        session = sol.ReadingSession(book)
        self.assertEqual(session.read(path, first=True).identifier, self.ids[4])
        self.assertEqual(session.move(1).identifier, self.ids[5])
        self.assertEqual(session.move(-1).identifier, self.ids[4])
        with patch("sol.being.actions.random.choice", side_effect=lambda values: values[-1]):
            self.assertEqual(session.read(path).identifier, self.ids[4])

    def test_default_corpus_never_uses_pdf_or_markdown_parser(self) -> None:
        original = builtins.__import__

        def block_parser(name, *args, **kwargs):
            if name.startswith("markdown_it"):
                raise ImportError("Parser deliberately unavailable")
            return original(name, *args, **kwargs)

        with nullcontext(), patch("builtins.__import__", side_effect=block_parser):
            status, stdout, stderr = self.run_main(["--first", "/being/sample"])
        self.assertEqual(status, 0, stderr)
        self.assertIn(self.ids[2], stdout)

    def test_structure_prefers_corpus_and_cat_is_complete_source_order(self) -> None:
        with nullcontext():
            status, stdout, stderr = self.run_main(["--structure"])
            self.assertEqual(status, 0, stderr)
            self.assertIn("A-sample-leaf.txt", stdout)
            status, stdout, stderr = self.run_main(["--cat", "/being/sample/sample-leaf"])
        self.assertEqual(status, 0, stderr)
        self.assertLess(stdout.index(self.ids[4]), stdout.index(self.ids[5]))
        self.assertNotIn(self.ids[6], stdout)

    def test_explicit_missing_corpus_never_silently_falls_back(self) -> None:
        with nullcontext():
            status, _, stderr = self.run_main(["--corpus", str(self.cwd / "missing"), "--structure"])
        self.assertEqual(status, 2)
        self.assertIn("Cannot use local corpus", stderr)

    def test_stale_default_corpus_reports_reindex_instead_of_pdf_fallback(self) -> None:
        path = self.corpus / "sample.md"
        path.write_text(path.read_text(encoding="utf-8").replace("synthetic introductory", "corrected introductory"), encoding="utf-8")
        with nullcontext():
            status, _, stderr = self.run_main(["-r"])
        self.assertEqual(status, 2)
        self.assertIn("rebuild the index", stderr)
        self.assertIn("-m sol.corpus.contract", stderr)

    def test_saved_corpus_and_uuid_work_from_another_directory_without_pdf(self) -> None:
        with nullcontext():
            status, _, stderr = self.run_main(["--set-corpus", str(self.corpus)])
            self.assertEqual(status, 0, stderr)
            status, stdout, stderr = self.run_main(
                ["--passage", self.ids[4], "--context", "1", "--json"], cwd=self.cwd / "elsewhere")
        self.assertEqual(status, 0, stderr)
        self.assertEqual([row["id"] for row in json.loads(stdout)], [self.ids[2], self.ids[4], self.ids[5]])
        saved = json.loads(config.config_path().read_text(encoding="utf-8"))
        self.assertEqual(saved["corpus"], str(self.corpus.resolve()))

    def test_relative_set_corpus_is_resolved_when_saved(self) -> None:
        # Path.resolve delegates to os.getcwd for relative inputs.
        with patch("os.getcwd", return_value=str(self.cwd)):
            status, stdout, stderr = self.run_main(["--set-corpus", "local-corpus", "--json"])
        self.assertEqual(status, 0, stderr)
        self.assertEqual(json.loads(stdout)["corpus"], str(self.corpus))
        status, stdout, stderr = self.run_main(["--passage", self.ids[2], "--json"], cwd=self.cwd / "elsewhere")
        self.assertEqual(status, 0, stderr)
        self.assertEqual(json.loads(stdout)["id"], self.ids[2])

    def test_invalid_set_corpus_preserves_previous_setting(self) -> None:
        status, _, stderr = self.run_main(["--set-corpus", str(self.corpus)])
        self.assertEqual(status, 0, stderr)
        original = config.config_path().read_bytes()
        status, _, stderr = self.run_main(["--set-corpus", str(self.cwd / "missing")])
        self.assertEqual(status, 2)
        self.assertIn("Cannot use local corpus", stderr)
        self.assertEqual(config.config_path().read_bytes(), original)

    def test_missing_saved_corpus_errors_without_install_or_pdf_fallback(self) -> None:
        configuration = config.config_path()
        configuration.parent.mkdir(parents=True)
        configuration.write_text(json.dumps({"corpus": str(self.cwd / "missing")}), encoding="utf-8")
        with nullcontext(), \
                patch("sol.core.config.installed_project_directory", side_effect=AssertionError("No source substitution")):
            status, _, stderr = self.run_main(["-r"], cwd=self.cwd / "elsewhere")
        self.assertEqual(status, 2)
        self.assertIn(str(self.cwd / "missing"), stderr)
        self.assertIn("--set-corpus", stderr)

    def test_guide_survives_broken_automatic_configuration(self) -> None:
        configuration = config.config_path()
        configuration.parent.mkdir(parents=True)
        for content in ("{broken", json.dumps({"corpus": str(self.cwd / "missing")})):
            with self.subTest(content=content), \
                    nullcontext():
                configuration.write_text(content, encoding="utf-8")
                status, stdout, stderr = self.run_main(["guide"], cwd=self.cwd / "elsewhere")
                self.assertEqual(status, 0, stderr)
                self.assertIn("BEING", stdout)
                self.assertIn("abbreviated visual guide", stderr)
        status, _, stderr = self.run_main(["guide", "--corpus", str(self.cwd / "missing")])
        self.assertEqual(status, 2)
        self.assertIn("Cannot use local corpus", stderr)

    def test_environment_override_and_explicit_override_precedence(self) -> None:
        with patch.dict("os.environ", {"SOL_CORPUS": str(self.cwd / "missing")}):
            status, _, stderr = self.run_main(["-r"])
            self.assertEqual(status, 2)
            self.assertIn(str(self.cwd / "missing"), stderr)
            status, stdout, stderr = self.run_main(["--corpus", str(self.corpus), "--passage", self.ids[2]])
            self.assertEqual(status, 0, stderr)
            self.assertIn(self.ids[2], stdout)
        with patch.dict("os.environ", {"SOL_CORPUS": str(self.corpus)}):
            status, stdout, stderr = self.run_main(["--passage", self.ids[2]], cwd=self.cwd / "elsewhere")
        self.assertEqual(status, 0, stderr)
        self.assertIn(self.ids[2], stdout)

    def test_cwd_corpus_precedes_saved_default(self) -> None:
        configuration = config.config_path()
        configuration.parent.mkdir(parents=True)
        configuration.write_text(json.dumps({"corpus": str(self.cwd / "missing")}), encoding="utf-8")
        status, stdout, stderr = self.run_main(["--passage", self.ids[2]])
        self.assertEqual(status, 0, stderr)
        self.assertIn(self.ids[2], stdout)

    def test_corpus_absence_never_automatically_extracts_present_pdf(self) -> None:
        elsewhere = self.cwd / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / sol.PDF_FILENAME).write_bytes(b"Synthetic PDF placeholder")
        with nullcontext():
            status, _, stderr = self.run_main(["-r"], cwd=elsewhere)
            self.assertEqual(status, 2)
            self.assertIn("--set-corpus", stderr)
            status, stdout, stderr = self.run_main(["--structure", "--json"], cwd=elsewhere)
        self.assertEqual(status, 0, stderr)
        self.assertTrue(json.loads(stdout)["abbreviated"])

    def test_malformed_and_relative_configuration_are_actionable(self) -> None:
        configuration = config.config_path()
        configuration.parent.mkdir(parents=True)
        for content in ("{broken", "[]", '{"corpus":"local-corpus"}'):
            with self.subTest(content=content):
                configuration.write_text(content, encoding="utf-8")
                status, _, stderr = self.run_main(["-r"], cwd=self.cwd / "elsewhere")
                self.assertEqual(status, 2)
                self.assertIn("--set-corpus", stderr)
                status, _, stderr = self.run_main(["--corpus", str(self.corpus), "-r"])
                self.assertEqual(status, 0, stderr)

    def test_configuration_write_error_is_actionable(self) -> None:
        with patch("sol.reader.app.Path.mkdir", side_effect=PermissionError("Synthetic permission failure")):
            status, _, stderr = self.run_main(["--set-corpus", str(self.corpus)])
        self.assertEqual(status, 2)
        self.assertIn("Cannot save SOL configuration", stderr)

    def test_source_checkout_corpus_is_discovered_from_another_directory(self) -> None:
        (self.cwd / "pyproject.toml").write_text(
            '[project]\nname = "sol-organizes-logic"\n', encoding="utf-8")
        with patch("sol.core.config.__file__", str(self.cwd / "sol" / "core" / "config.py")), \
                nullcontext():
            status, stdout, stderr = self.run_main(["--passage", self.ids[2]], cwd=self.cwd / "elsewhere")
        self.assertEqual(status, 0, stderr)
        self.assertIn(self.ids[2], stdout)

    def test_invalid_reader_path_is_rejected(self) -> None:
        self.pairs[2][0]["reader_path"] = "/BEING/../wrong.txt"
        self.write_corpus()
        with self.assertRaisesRegex(ValueError, "Invalid corpus reader_path"):
            sol.load_corpus_book(self.corpus)

    def test_virtual_file_start_page_is_its_first_paragraph(self) -> None:
        self.pairs[5][0]["sources"] = [{"pdf_page": 81, "printed_page": "8"}]
        self.write_corpus()
        book = sol.load_corpus_book(self.corpus)
        self.assertEqual(book.passages[1].node.start_page, 7)

    def test_review_pending_mixed_math_paragraph_is_ordered_but_not_random(self) -> None:
        self.pairs[4][0].update(contains_math=True, random_eligible=False, transcription_status="needs_visual_review")
        self.write_corpus()
        book = sol.load_corpus_book(self.corpus)
        pending = book.passages[1]
        self.assertEqual(pending.kind, "paragraph")
        self.assertFalse(pending.random_eligible)
        session = sol.ReadingSession(book)
        with patch("sol.being.actions.random.choice", side_effect=lambda values: values[-1]):
            self.assertEqual(session.read(()).identifier, self.ids[2])
        self.assertEqual(session.read(pending.path, first=True).identifier, self.ids[4])
        self.assertEqual(session.move(1).identifier, self.ids[5])
        with self.assertRaisesRegex(ValueError, "no suitable random prose"):
            session.read(pending.path)
        status, stdout, stderr = self.run_main(["--cat", "/being/sample/sample-leaf"])
        self.assertEqual(status, 0, stderr)
        self.assertIn(self.ids[4], stdout)
        self.assertIn(self.ids[5], stdout)

    def test_reader_rejects_non_boolean_random_eligibility(self) -> None:
        snapshot = contract.load_snapshot(self.corpus)
        records = snapshot.records
        next(record for record in records if record["id"] == self.ids[4])["random_eligible"] = "false"
        with patch("sol.corpus.contract.load_snapshot", return_value=snapshot):
            with self.assertRaisesRegex(ValueError, "random_eligible.*bool|boolean.*random_eligible"):
                sol.load_corpus_book(self.corpus)


if __name__ == "__main__":
    unittest.main()
