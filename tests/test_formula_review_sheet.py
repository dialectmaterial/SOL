"""Private source sheets over invented text and a three-page synthetic PDF."""
from copy import deepcopy
from contextlib import redirect_stdout
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch
from uuid import UUID

from fixtures_corpus import CorpusFixture
from test_source_viewer import tiny_pdf, tiny_png
from sol.terminal import source


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("formula_review_sheet", ROOT / "scripts/formula_review_sheet.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class SheetHTML(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.tags = []
        self.text = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, text):
        self.text.append(text)


class FormulaReviewSheetTests(CorpusFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.pdf = self.root / "synthetic.pdf"
        self.pdf.write_bytes(tiny_pdf())
        manifest_path = self.corpus / "corpus.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["source"] = {"filename": self.pdf.name, "sha256": hashlib.sha256(self.pdf.read_bytes()).hexdigest(), "pdf_pages": 3}
        manifest["page_inventory"] = [{"pdf_page": i, "printed_page": label, "disposition": "records"}
                                      for i, label in ((1, "7"), (2, "ii"), (3, "9"))]
        manifest_path.write_text(json.dumps(manifest))
        rows = [json.loads(line) for line in (self.corpus / "index.jsonl").read_text().splitlines()]
        for row in rows:
            row["sources"] = [{"pdf_page": 1, "printed_page": "7"}]
        passage = rows[1]
        passage.update(contains_math=True, transcription_status="needs_visual_review",
                       markdown="Retyped `<script>alert(1)</script>` α² = 𝔸 é.",
                       plain_text="Retyped <script>alert(1)</script> α² = 𝔸 é.",
                       sources=[{"pdf_page": 1, "printed_page": "7", "bbox": [20, 20, 140, 140]},
                                {"pdf_page": 3, "printed_page": "9"}])
        note = deepcopy(passage)
        note.update(id=str(UUID(int=900)), type="note", order=2, parent_id=passage["id"],
                    markdown="Note 1", plain_text="Note 1", contains_math=False,
                    backlinks=[passage["id"]], sources=[{"pdf_page": 2, "printed_page": "ii"}])
        passage["note_ids"] = [note["id"]]
        body = deepcopy(note)
        body.pop("backlinks")
        body.update(id=str(UUID(int=901)), type="note_paragraph", order=3, parent_id=note["id"],
                    markdown="An editor's formula: a².", plain_text="An editor's formula: a².", contains_math=True,
                    attribution={"author": "Invented editor", "status": "editorial", "role": "footnote"},
                    sources=[{"pdf_page": 2, "printed_page": "ii", "bbox": [10, 10, 100, 150]}])
        rows.extend([note, body])
        for number, math, status in ((902, False, "needs_visual_review"), (903, True, "reviewed")):
            extra = deepcopy(body)
            extra.update(id=str(UUID(int=number)), order=len(rows), contains_math=math, transcription_status=status)
            rows.append(extra)
        self.note_body = body["id"]
        self.write_records(rows)
        self.output = self.root / "private-review"
        self.before = self.corpus_files()

    def corpus_files(self):
        return {path.name: path.read_bytes() for path in self.corpus.iterdir() if path.is_file()}

    def fake_renderer(self, request, index, cache_dir):
        path = Path(cache_dir) / f'{request["target_id"]}-{index}.png'
        path.write_bytes(tiny_png())
        return path, "bbox" in request["sources"][index]

    def create(self, **kwargs):
        with patch.object(source, "render_region", side_effect=self.fake_renderer):
            return review.create_sheet(self.corpus, self.output, pdf=self.pdf, **kwargs)

    def test_sheet_has_every_eligible_record_source_page_and_exact_escaped_text(self):
        original_capture = source.SourceService.capture
        captures = []
        def capture(service, identifier):
            captures.append(identifier)
            return original_capture(service, identifier)
        with patch.object(source.SourceService, "capture", new=capture), \
                patch.object(source, "render_region", side_effect=self.fake_renderer) as renderer:
            review.create_sheet(self.corpus, self.output, pdf=self.pdf)
        self.assertEqual(captures, [self.identifier, self.note_body])
        self.assertEqual(renderer.call_count, 3)
        directory, sheet, fingerprint = review.load_sheet(self.output)
        self.assertEqual([row["id"] for row in sheet["records"]], captures)
        self.assertEqual(sheet["records"][0]["plain_text"], self.book.canonical_records[self.identifier]["plain_text"])
        self.assertEqual([page["cropped"] for page in sheet["records"][0]["pages"]], [True, False])
        self.assertEqual(sheet["records"][1]["attribution"]["author"], "Invented editor")
        parsed = SheetHTML((directory / "review.html").read_text())
        self.assertEqual(len([tag for tag, _ in parsed.tags if tag == "img"]), 3)
        self.assertNotIn("script", [tag for tag, _ in parsed.tags])
        self.assertIn("<script>alert(1)</script>", "".join(parsed.text))
        self.assertIn("whole page (no recorded bounding box)", "".join(parsed.text))
        self.assertIn("printed page ii", "".join(parsed.text))
        self.assertIn("No verdict has been inferred", "".join(parsed.text))
        self.assertEqual(review.check_sheet(directory, self.corpus),
                         {"items": 2, "events": 0, "confirmed": 0, "needs_correction": 0, "pending": 2})
        self.assertEqual((directory / "verdicts.jsonl").read_bytes(), b"")
        self.assertFalse(list(directory.rglob("*.pdf")))
        self.assertFalse(list(directory.glob("source-*")))
        for path in (directory, directory / "assets"):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        for path in directory.rglob("*"):
            if path.is_file():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(self.corpus_files(), self.before)

    def test_append_only_verdicts_bind_source_and_keep_earlier_testimony(self):
        self.create()
        first = review.record_verdict(self.output, "1", "confirmed", "Compared every symbol", "Invented reader")
        saved = (self.output / "verdicts.jsonl").read_bytes()
        second = review.record_verdict(self.output, self.identifier, "needs_correction", "Exponent differs", "Another reader")
        self.assertTrue((self.output / "verdicts.jsonl").read_bytes().startswith(saved))
        self.assertEqual(first["sheet_sha256"], second["sheet_sha256"])
        self.assertEqual(first["content_sha256"], self.book.canonical_records[self.identifier]["content_sha256"])
        self.assertEqual(review.check_sheet(self.output),
                         {"items": 2, "events": 2, "confirmed": 0, "needs_correction": 1, "pending": 1})
        self.assertEqual(self.corpus_files(), self.before)
        self.assertEqual(self.book.canonical_records[self.identifier]["transcription_status"], "needs_visual_review")

    def test_interactive_review_skips_quits_and_resumes_pending_items(self):
        self.create()
        with patch("builtins.input", side_effect=["s", "q"]), redirect_stdout(io.StringIO()):
            self.assertEqual(review.review_sheet(self.output, "Reader")["events"], 0)
        with patch("builtins.input", side_effect=["n", "A wrong exponent", "c", ""]), redirect_stdout(io.StringIO()):
            result = review.review_sheet(self.output, "Reader")
        self.assertEqual((result["needs_correction"], result["confirmed"], result["pending"]), (1, 1, 0))
        with patch("builtins.input", side_effect=AssertionError("completed entries prompted again")):
            self.assertEqual(review.review_sheet(self.output, "Reader")["events"], 2)

    def test_invalid_verdict_unknown_id_and_competing_writer_never_append(self):
        self.create()
        for identifier, verdict, note, actor in (("999", "confirmed", "", "Reader"),
                ("1", "reviewed", "", "Reader"), ("1", "needs_correction", "  ", "Reader"),
                ("1", "confirmed", "", ""), ("1", "confirmed", "x" * 20001, "Reader")):
            with self.subTest(verdict=verdict), self.assertRaises(ValueError):
                review.record_verdict(self.output, identifier, verdict, note, actor)
        with review._verdict_lock(self.output), self.assertRaisesRegex(ValueError, "writer"):
            review.record_verdict(self.output, "1", "confirmed", "", "Reader")
        self.assertEqual((self.output / "verdicts.jsonl").read_bytes(), b"")

    def test_output_is_outside_git_and_corpus_and_never_overwrites(self):
        for git_marker in ("ordinary", "worktree"):
            repository = self.root / git_marker
            repository.mkdir()
            if git_marker == "ordinary":
                (repository / ".git").mkdir()
                (repository / ".git" / "HEAD").write_text("ref: refs/heads/main")
            else:
                (repository / ".git").write_text("gitdir: /not-used")
            with self.assertRaisesRegex(ValueError, "outside every Git"):
                review.create_sheet(self.corpus, repository / "sheet", pdf=self.pdf)
            alias = self.root / (git_marker + "-alias")
            alias.symlink_to(repository, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "outside every Git"):
                review.create_sheet(self.corpus, alias / "sheet", pdf=self.pdf)
        with self.assertRaisesRegex(ValueError, "outside the canonical corpus"):
            review.create_sheet(self.corpus, self.corpus / "sheet", pdf=self.pdf)
        self.create()
        original = {path.relative_to(self.output): path.read_bytes() for path in self.output.rglob("*") if path.is_file()}
        with self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual(original, {path.relative_to(self.output): path.read_bytes() for path in self.output.rglob("*") if path.is_file()})
        with self.assertRaises(ValueError):
            review.create_sheet(self.corpus, self.root / "bad-selection", pdf=self.pdf, identifiers=[self.identifier, self.identifier])
        self.assertFalse((self.root / "bad-selection").exists())

    def test_source_failures_leave_no_sheet_and_changed_generation_is_disclosed(self):
        with self.assertRaises(source.SourceError):
            review.create_sheet(self.corpus, self.output, pdf=self.root / "missing.pdf")
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".sol-formula-sheet-*")))
        self.pdf.write_bytes(b"wrong original PDF")
        with self.assertRaises(source.SourceError):
            review.create_sheet(self.corpus, self.output, pdf=self.pdf)
        self.pdf.write_bytes(tiny_pdf())
        with patch.object(source, "render_region", side_effect=source.SourceError("Invented missing renderer")), self.assertRaises(source.SourceError):
            review.create_sheet(self.corpus, self.output, pdf=self.pdf)
        self.assertFalse(self.output.exists())
        self.create()
        original = (self.corpus / "sample.md").read_bytes()
        (self.corpus / "sample.md").write_bytes(original + b"\nChanged source.\n")
        with self.assertRaises(ValueError):
            review.check_sheet(self.output, self.corpus)
        # Historical testimony still binds to exactly the sheet that was seen.
        review.record_verdict(self.output, "1", "confirmed", "", "Reader")
        self.assertEqual(review.check_sheet(self.output)["confirmed"], 1)

    def test_source_changed_during_render_refuses_publication(self):
        document = self.corpus / "sample.md"
        original = document.read_bytes()
        def change_after_render(request, index, cache_dir):
            result = self.fake_renderer(request, index, cache_dir)
            document.write_bytes(original + b"\nChanged while rendering.\n")
            return result
        with patch.object(source, "render_region", side_effect=change_after_render), self.assertRaises(ValueError):
            review.create_sheet(self.corpus, self.output, pdf=self.pdf)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".sol-formula-sheet-*")))

    def test_changed_display_crop_or_verdict_binding_is_refused(self):
        self.create()
        html = self.output / "review.html"
        original = html.read_bytes()
        html.write_bytes(original + b"changed")
        with self.assertRaises(ValueError):
            review.record_verdict(self.output, "1", "confirmed", "", "Reader")
        html.write_bytes(original)
        image = next((self.output / "assets").iterdir())
        original_image = image.read_bytes()
        image.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            review.check_sheet(self.output)
        image.write_bytes(original_image)
        event = review.record_verdict(self.output, "1", "confirmed", "", "Reader")
        event["content_sha256"] = "0" * 64
        (self.output / "verdicts.jsonl").write_bytes(review._json(event) + b"\n")
        with self.assertRaises(ValueError):
            review.check_sheet(self.output)
        (self.output / "verdicts.jsonl").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "incomplete final line"):
            review.record_verdict(self.output, "1", "confirmed", "", "Reader")

    @unittest.skipUnless(shutil.which("pdftoppm"), "existing Poppler is required for real PDF rendering")
    def test_real_poppler_crop_and_full_page_and_cli_round_trip(self):
        command = [sys.executable, "-B", str(ROOT / "scripts/formula_review_sheet.py")]
        result = subprocess.run([*command, "create", "--corpus", str(self.corpus), "--pdf", str(self.pdf),
                                 "--output", str(self.output)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Retyped", result.stdout)
        _, sheet, _ = review.load_sheet(self.output)
        self.assertEqual(len(list((self.output / "assets").glob("*.png"))), 3)
        self.assertTrue(sheet["records"][0]["pages"][0]["cropped"])
        self.assertFalse(sheet["records"][0]["pages"][1]["cropped"])
        result = subprocess.run([*command, "record", "--sheet", str(self.output), "--record", "1", "--verdict", "confirmed",
                                 "--reviewer", "Invented reviewer"], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([*command, "check", "--sheet", str(self.output), "--corpus", str(self.corpus)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["confirmed"], 1)
        self.assertEqual(self.corpus_files(), self.before)
