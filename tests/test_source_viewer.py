"""Source identity, pinned generation, and page-cache safety on invented text/PDFs."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

from sol.corpus.contract import load_snapshot, render_record
from sol.being import source_view as source_module
from sol.core.source import SourceError, SourceService, render_page, render_region
from sol.being.source_view import open_pdf, open_viewer


ROOT = "aaaaaaaa-0000-4000-8000-000000000001"
PASSAGE = "bbbbbbbb-0000-4000-8000-000000000002"
RETIRED = "cccccccc-0000-4000-8000-000000000003"
CORPUS = "dddddddd-0000-4000-8000-000000000004"


def tiny_pdf():
    """Three blank, colored synthetic pages; no external authoring dependency."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>"]
    for index in range(3):
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 240] /Contents {6 + index} 0 R >>".encode())
    for color in (b"1 0 0", b"0 1 0", b"0 0 1"):
        content = color + b" rg 20 20 120 120 re f\n"
        objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream")
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(data)


def tiny_png():
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


class SourceViewerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="sol-source-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.corpus = self.directory / "local-corpus"
        self.corpus.mkdir()
        self.pdf = self.directory / "Hegel-SOL.pdf"
        self.pdf.write_bytes(tiny_pdf())
        self.digest = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.cache = self.directory / "private-cache"
        environment = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.directory / "config"),
                                              "XDG_CACHE_HOME": str(self.directory / "cache")}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.records = []
        for identifier, kind, order, markdown, sources in [
            (ROOT, "section", 0, "# Invented source book", [{"pdf_page": 2, "printed_page": "ii"}]),
            (PASSAGE, "paragraph", 1, "A synthetic passage crosses nonconsecutive source pages.",
             [{"pdf_page": 1, "printed_page": "i", "bbox": [20, 20, 140, 140]},
              {"pdf_page": 3, "printed_page": None}]),
            (RETIRED, "retired_record", 2, "An invented retirement directs to the continuing passage.",
             [{"pdf_page": 2, "printed_page": "ii"}]),
        ]:
            metadata = {"id": identifier, "parent_id": None if identifier == ROOT else ROOT,
                        "type": kind, "order": order, "sources": sources,
                        "attribution": {"author": "Synthetic editor", "role": "editorial", "status": "confirmed"}}
            if identifier == ROOT:
                metadata["title"] = "Invented source book"
            if identifier == RETIRED:
                metadata["redirect_id"] = PASSAGE
            self.records.append({**metadata, "markdown": markdown, "plain_text": markdown.lstrip("# "),
                                 "document": "synthetic.md", "context": [],
                                 "content_sha256": hashlib.sha256(markdown.encode()).hexdigest()})
        self.write_generation()
        self.book = self.load_book()
        self.service = SourceService(self.book, cache_dir=self.cache)

    def write_generation(self):
        manifest = {"contract_version": 1, "corpus_id": CORPUS,
                    "edition": {"title": "Invented edition"},
                    "source": {"filename": "older-original-name.pdf", "sha256": self.digest, "pdf_pages": 3},
                    "documents": ["synthetic.md"],
                    "page_inventory": [{"pdf_page": i, "printed_page": label, "disposition": "records"}
                                       for i, label in [(1, "i"), (2, "ii"), (3, None)]]}
        document = "\n".join(render_record({k: v for k, v in record.items()
                                           if k not in {"markdown", "plain_text", "document", "context", "content_sha256"}},
                                          record["markdown"]) for record in self.records)
        manifest_bytes = json.dumps(manifest).encode()
        index_bytes = "".join(json.dumps(record) + "\n" for record in self.records).encode()
        (self.corpus / "synthetic.md").write_text(document)
        (self.corpus / "corpus.json").write_bytes(manifest_bytes)
        (self.corpus / "index.jsonl").write_bytes(index_bytes)
        metadata = {"contract_version": 1, "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                    "source_sha256": self.digest,
                    "documents": {"synthetic.md": hashlib.sha256(document.encode()).hexdigest()},
                    "index_sha256": hashlib.sha256(index_bytes).hexdigest(), "record_count": len(self.records)}
        (self.corpus / "index.meta.json").write_text(json.dumps(metadata))

    def load_book(self):
        snapshot = load_snapshot(self.corpus)
        return SimpleNamespace(corpus_snapshot=snapshot, corpus_directory=self.corpus,
                               corpus_manifest=snapshot.manifest,
                               canonical_records={r["id"]: r for r in snapshot.records})

    def renderer(self, arguments, **kwargs):
        if arguments[-1] == "-v":
            return subprocess.CompletedProcess(arguments, 0, b"", b"pdftoppm version synthetic-1\n")
        self.rendered.append(arguments)
        Path(arguments[-1]).with_suffix(".png").write_bytes(tiny_png())
        return subprocess.CompletedProcess(arguments, 0, b"", b"")

    def mock_render(self, request, index=0):
        self.rendered = []
        with patch("sol.core.source.shutil.which", return_value="/invented/pdftoppm"), \
                patch("sol.core.source.subprocess.run", side_effect=self.renderer):
            return render_page(request, index, cache_dir=self.cache)

    def test_capture_preserves_uuid_redirect_metadata_and_exact_sources(self):
        request = self.service.capture(RETIRED[:12])
        self.assertEqual(request["requested_id"], RETIRED)
        self.assertEqual(request["target_id"], PASSAGE)
        self.assertEqual(request["redirect_chain"], [RETIRED, PASSAGE])
        self.assertEqual(request["sources"], self.records[1]["sources"])
        self.assertEqual([s["pdf_page"] for s in request["sources"]], [1, 3])
        self.assertEqual([s["printed_page"] for s in request["sources"]], ["i", None])
        snapshot = Path(request["source"]["verified_pdf"])
        self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(), self.digest)
        self.assertFalse((self.directory / "config").exists())
        request["sources"][0]["printed_page"] = "modified copy"
        self.assertEqual(self.book.canonical_records[PASSAGE]["sources"][0]["printed_page"], "i")

    def test_new_capture_checks_original_even_when_verified_snapshot_exists(self):
        self.service.capture(PASSAGE)
        self.pdf.write_bytes(b"%PDF-1.4\nA different document")
        with self.assertRaisesRegex(SourceError, "fingerprint mismatch"):
            self.service.capture(PASSAGE)

    def test_render_stays_on_captured_pdf_after_original_is_replaced(self):
        request = self.service.capture(PASSAGE)
        self.pdf.write_bytes(b"a replaced original")
        result = self.mock_render(request, 1)
        self.assertTrue(result.is_file())
        arguments = self.rendered[0]
        self.assertEqual(arguments[arguments.index("-f") + 1], "3")
        self.assertEqual(arguments[arguments.index("-l") + 1], "3")
        self.assertFalse(any("shell" in argument for argument in arguments))

    def test_explicit_bad_source_does_not_use_automatic_good_source(self):
        wrong = self.directory / "wrong.pdf"
        wrong.write_bytes(b"another source")
        with self.assertRaisesRegex(SourceError, "fingerprint mismatch"):
            SourceService(self.book, source_pdf=wrong, cache_dir=self.cache).capture(PASSAGE)

    def test_environment_source_has_priority_and_is_not_silently_replaced(self):
        self.service.set_pdf(self.pdf)
        with patch.dict(os.environ, {"SOL_SOURCE_PDF": str(self.directory / "missing.pdf")}):
            with self.assertRaisesRegex(SourceError, "Cannot read or snapshot PDF"):
                SourceService(self.book, cache_dir=self.cache).capture(PASSAGE)

    def test_saved_source_is_explicit_and_missing_path_does_not_fall_back(self):
        saved = self.directory / "saved source.pdf"
        shutil.copyfile(self.pdf, saved)
        self.service.set_pdf(saved)
        saved.unlink()
        with self.assertRaisesRegex(SourceError, "Cannot read or snapshot PDF"):
            SourceService(self.book, cache_dir=self.cache).capture(PASSAGE)

    def test_set_pdf_retains_other_mapping_and_does_not_modify_corpus_or_reader_config(self):
        before = {p.name: p.read_bytes() for p in self.corpus.iterdir()}
        configuration = self.directory / "config" / "sol"
        configuration.mkdir(parents=True)
        reader_config = configuration / "config.json"
        reader_config.write_text('{"version":1,"corpus":"/preserved"}')
        registry = configuration / "sources.json"
        registry.write_text(json.dumps({"version": 1, "sources": {"0" * 64: "/other/pdf.pdf"}}))
        self.assertEqual(self.service.set_pdf(self.pdf), self.pdf.resolve())
        self.assertEqual(json.loads(registry.read_text())["sources"],
                         {"0" * 64: "/other/pdf.pdf", self.digest: str(self.pdf)})
        self.assertEqual(reader_config.read_text(), '{"version":1,"corpus":"/preserved"}')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.corpus.iterdir()})

    def test_metadata_change_invalidates_request_even_with_same_markdown(self):
        request = self.service.capture(PASSAGE)
        self.mock_render(request)
        self.records[1]["attribution"]["status"] = "unresolved"
        self.write_generation()
        with self.assertRaisesRegex(SourceError, "generation changed"):
            self.mock_render(request)
        with self.assertRaisesRegex(SourceError, "canonical corpus changed"):
            self.service.capture(PASSAGE)

    def test_request_cannot_retarget_pages_or_drop_metadata(self):
        request = self.service.capture(PASSAGE)
        request["sources"][0]["pdf_page"] = 2
        with self.assertRaisesRegex(SourceError, "page metadata changed"):
            self.mock_render(request)

    def test_bool_and_out_of_bounds_indexes_are_rejected(self):
        request = self.service.capture(PASSAGE)
        for index in (True, -1, 2, "1"):
            with self.subTest(index=index), self.assertRaisesRegex(SourceError, "source page index"):
                self.mock_render(request, index)

    def test_declared_physical_page_bounds_are_checked_on_capture(self):
        self.book.canonical_records[PASSAGE]["sources"][1]["pdf_page"] = 4
        with self.assertRaisesRegex(SourceError, "outside the declared"):
            self.service.capture(PASSAGE)

    def test_png_cache_hit_is_verified_and_corruption_is_rerendered(self):
        request = self.service.capture(PASSAGE)
        first = self.mock_render(request)
        self.assertEqual(len(self.rendered), 1)
        self.assertEqual(self.mock_render(request), first)
        self.assertEqual(self.rendered, [])
        first.write_bytes(b"corrupt PNG")
        self.assertEqual(self.mock_render(request), first)
        self.assertEqual(len(self.rendered), 1)
        self.assertEqual(first.read_bytes(), tiny_png())
        first.with_suffix(".json").write_text("{}")
        self.mock_render(request)
        self.assertEqual(len(self.rendered), 1)

    def test_corrupt_pdf_snapshot_is_rejected_even_with_png_cache_hit(self):
        request = self.service.capture(PASSAGE)
        self.mock_render(request)
        snapshot = Path(request["source"]["verified_pdf"])
        snapshot.chmod(0o600)
        snapshot.write_bytes(b"corrupt PDF")
        with self.assertRaisesRegex(SourceError, "PDF snapshot changed"):
            self.mock_render(request)

    def test_cache_must_remain_outside_canonical_corpus(self):
        with self.assertRaisesRegex(SourceError, "outside the canonical"):
            SourceService(self.book, cache_dir=self.corpus / "assets")

    def test_cache_child_symlink_cannot_send_writes_to_corpus(self):
        self.cache.mkdir()
        (self.cache / "pdf").symlink_to(self.corpus, target_is_directory=True)
        before = sorted(p.name for p in self.corpus.iterdir())
        with self.assertRaisesRegex(SourceError, "must not be a symbolic link"):
            self.service.capture(PASSAGE)
        self.assertEqual(before, sorted(p.name for p in self.corpus.iterdir()))

    def test_source_mapping_cannot_be_stored_inside_corpus(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.corpus)}):
            with self.assertRaisesRegex(SourceError, "mapping must be outside"):
                self.service.set_pdf(self.pdf)
        self.assertFalse((self.corpus / "sol").exists())

    def test_legacy_pdf_reader_gets_actionable_source_error(self):
        self.book.corpus_directory = None
        with self.assertRaisesRegex(SourceError, "requires a verified canonical corpus"):
            SourceService(self.book)

    def test_pdf_modified_during_copy_never_becomes_completed_snapshot(self):
        with patch("sol.core.source._stat_identity", side_effect=[(1,), (2,)]):
            with self.assertRaisesRegex(SourceError, "changed while being verified"):
                self.service.capture(PASSAGE)
        self.assertEqual(list((self.cache / "pdf").iterdir()), [])

    def test_renderer_failure_leaves_no_completed_png_or_metadata(self):
        request = self.service.capture(PASSAGE)
        def failed(arguments, **kwargs):
            if arguments[-1] == "-v":
                return subprocess.CompletedProcess(arguments, 0, b"", b"synthetic renderer")
            return subprocess.CompletedProcess(arguments, 1, b"", b"bad source page")
        with patch("sol.core.source.shutil.which", return_value="/invented/pdftoppm"), \
                patch("sol.core.source.subprocess.run", side_effect=failed):
            with self.assertRaisesRegex(SourceError, "could not render physical PDF page"):
                render_page(request, 0, cache_dir=self.cache)
        self.assertEqual(list((self.cache / "renders").iterdir()), [])

    @unittest.skipUnless(shutil.which("pdftoppm"), "Poppler not installed")
    def test_poppler_renders_actual_synthetic_noncontiguous_page(self):
        request = self.service.capture(PASSAGE)
        result = render_page(request, 1, cache_dir=self.cache)
        data = result.read_bytes()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", data[16:24])
        self.assertGreater(width, 200)
        self.assertGreater(height, 240)
        self.assertEqual(render_page(request, 1, cache_dir=self.cache), result)

    def test_region_crops_recorded_box_and_falls_back_to_the_whole_page(self):
        request = self.service.capture(PASSAGE)
        self.rendered = []
        with patch("sol.core.source.shutil.which", return_value="/invented/pdftoppm"), \
                patch("sol.core.source.subprocess.run", side_effect=self.renderer):
            crop, cropped = render_region(request, 0, cache_dir=self.cache)
            page, whole = render_region(request, 1, cache_dir=self.cache)
            full = render_page(request, 0, cache_dir=self.cache)
            self.assertEqual(page, render_page(request, 1, cache_dir=self.cache))
        self.assertTrue(cropped)
        self.assertFalse(whole)
        # 144 dpi doubles PDF points; a 6-point margin surrounds the 120-point box.
        arguments = self.rendered[0]
        self.assertEqual(arguments[arguments.index("-r") + 1], "144")
        self.assertEqual(arguments[arguments.index("-x"):arguments.index("-x") + 8],
                         ["-x", "28", "-y", "28", "-W", "264", "-H", "264"])
        self.assertNotIn("-x", self.rendered[1])
        self.assertEqual(self.rendered[1][self.rendered[1].index("-r") + 1], "120")
        self.assertNotEqual(crop, full)

    @unittest.skipUnless(shutil.which("pdftoppm"), "Poppler not installed")
    def test_poppler_crops_the_recorded_region(self):
        request = self.service.capture(PASSAGE)
        crop, cropped = render_region(request, 0, cache_dir=self.cache)
        self.assertTrue(cropped)
        self.assertEqual(struct.unpack(">II", crop.read_bytes()[16:24]), (264, 264))
        self.assertEqual(render_region(request, 0, cache_dir=self.cache), (crop, True))

    def test_viewer_is_detached_and_configurable(self):
        with patch.dict(os.environ, {"SOL_IMAGE_VIEWER": "invented-viewer --fit"}), \
                patch("sol.being.source_view.shutil.which", return_value="/bin/invented-viewer"), \
                patch("sol.being.source_view.subprocess.Popen") as popen:
            self.assertEqual(open_viewer(Path("/cache/crop.png")), "invented-viewer")
        self.assertEqual(popen.call_args.args[0], ["/bin/invented-viewer", "--fit", "/cache/crop.png"])
        options = popen.call_args.kwargs
        self.assertTrue(options["start_new_session"])
        self.assertTrue(all(options[name] is subprocess.DEVNULL for name in ("stdin", "stdout", "stderr")))

    def test_viewer_is_not_guessed_without_a_display_or_program(self):
        with patch("sol.being.source_view.sys.platform", "linux"), \
                patch("sol.being.source_view.subprocess.Popen") as popen:
            # setUp cleared DISPLAY and WAYLAND_DISPLAY: no text-mode fallback.
            self.assertIsNone(open_viewer(Path("/cache/crop.png")))
            with patch.dict(os.environ, {"DISPLAY": ":0"}), \
                    patch("sol.being.source_view.shutil.which", return_value=None):
                self.assertIsNone(open_viewer(Path("/cache/crop.png")))
        popen.assert_not_called()

    def test_pdf_viewer_opens_the_verified_snapshot_at_the_physical_page(self):
        request = self.service.capture(PASSAGE)
        snapshot = request["source"]["verified_pdf"]
        self.addCleanup(setattr, source_module, "_companion", None)
        found = {"zathura": "/bin/zathura", "gdbus": "/bin/gdbus"}
        with patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-1"}), \
                patch("sol.being.source_view.shutil.which", side_effect=found.get), \
                patch("sol.being.source_view.threading.Thread") as thread, \
                patch("sol.being.source_view.subprocess.Popen") as popen:
            self.assertEqual(open_pdf(request, 1), "zathura")
            self.assertEqual(popen.call_args.args[0], ["/bin/zathura", "--page=3", snapshot])
            self.assertTrue(popen.call_args.kwargs["start_new_session"])
            # The new window is highlighted once it is on D-Bus, in the background.
            self.assertEqual(thread.call_args.kwargs["args"], (popen.return_value, request, 1))
            thread.return_value.start.assert_called_once_with()
            # The window SOL opened is turned to the next page instead of duplicated.
            popen.return_value.poll.return_value = None
            popen.return_value.pid = 4242
            with patch("sol.being.source_view.subprocess.run",
                       return_value=SimpleNamespace(returncode=0, stdout=b"(true,)\n")) as run:
                self.assertEqual(open_pdf(request, 0), "zathura")
            self.assertEqual(popen.call_count, 1)
            turn, highlight = (call.args[0] for call in run.call_args_list)
            self.assertIn("org.pwmt.zathura.PID-4242", turn)
            self.assertEqual(turn[-2:], ["org.pwmt.zathura.GotoPage", "0"])
            # The passage's recorded box on that page, in PDF points from the top left.
            self.assertEqual(highlight[-4:], ["org.pwmt.zathura.HighlightRects", "0",
                                              "@a(dddd) [(20.0, 20.0, 140.0, 140.0)]", "@a(udddd) []"])
            # Once that window is closed, a new one opens.
            popen.return_value.poll.return_value = 0
            open_pdf(request, 0)
            self.assertEqual(popen.call_count, 2)
            self.assertEqual(popen.call_args.args[0], ["/bin/zathura", "--page=1", snapshot])

    def test_highlight_marks_the_box_on_its_page_and_on_the_passages_other_pages(self):
        request = {"sources": [{"pdf_page": 7, "bbox": [1, 2.5, 3, 4]}, {"pdf_page": 8, "bbox": [5, 6, 7, 8]},
                               {"pdf_page": 9}]}
        self.assertEqual(source_module._highlight_arguments(request, 0),
                         ["6", "@a(dddd) [(1.0, 2.5, 3.0, 4.0)]", "@a(udddd) [(uint32 7, 5.0, 6.0, 7.0, 8.0)]"])
        self.assertEqual(source_module._highlight_arguments(request, 2),
                         ["8", "@a(dddd) []", "@a(udddd) [(uint32 6, 1.0, 2.5, 3.0, 4.0), "
                                              "(uint32 7, 5.0, 6.0, 7.0, 8.0)]"])
        self.assertIsNone(source_module._highlight_arguments({"sources": [{"pdf_page": 3}]}, 0))

    def test_following_turns_only_a_window_sol_opened_and_never_opens_one(self):
        request = self.service.capture(PASSAGE)
        self.addCleanup(setattr, source_module, "_companion", None)
        found = {"gdbus": "/bin/gdbus"}
        ok = SimpleNamespace(returncode=0, stdout=b"(true,)\n")
        with patch("sol.being.source_view.shutil.which", side_effect=found.get), \
                patch("sol.being.source_view.subprocess.Popen") as popen, \
                patch("sol.being.source_view.subprocess.run", return_value=ok) as run:
            source_module._companion = None
            self.assertFalse(source_module.follow_pdf(request))
            window = SimpleNamespace(pid=77, poll=lambda: None)
            source_module._companion = (window, Path(request["source"]["verified_pdf"]))
            self.assertTrue(source_module.follow_pdf(request))
            self.assertEqual(run.call_count, 2)  # turn, then highlight
            closed = SimpleNamespace(pid=77, poll=lambda: 0)
            source_module._companion = (closed, Path(request["source"]["verified_pdf"]))
            self.assertFalse(source_module.follow_pdf(request))
            self.assertIsNone(source_module._companion)
        popen.assert_not_called()

    def test_pdf_viewer_is_configurable_and_never_guessed_without_a_display(self):
        request = self.service.capture(PASSAGE)
        with patch("sol.being.source_view.sys.platform", "linux"), \
                patch("sol.being.source_view.subprocess.Popen") as popen:
            self.assertIsNone(open_pdf(request, 0))
            with patch.dict(os.environ, {"DISPLAY": ":0"}), \
                    patch("sol.being.source_view.shutil.which", return_value=None):
                self.assertIsNone(open_pdf(request, 0))
            popen.assert_not_called()
            with patch.dict(os.environ, {"SOL_PDF_VIEWER": "invented-pdf -p {page} {file} --zoom"}), \
                    patch("sol.being.source_view.shutil.which", return_value="/bin/invented-pdf"):
                self.assertEqual(open_pdf(request, 1), "invented-pdf")
            self.assertEqual(popen.call_args.args[0],
                             ["/bin/invented-pdf", "-p", "3", request["source"]["verified_pdf"], "--zoom"])
            with self.assertRaises(SourceError):
                open_pdf(request, 2)

    def test_pdf_viewer_refuses_a_changed_snapshot(self):
        request = self.service.capture(PASSAGE)
        snapshot = Path(request["source"]["verified_pdf"])
        snapshot.chmod(0o600)
        snapshot.write_bytes(b"%PDF-1.4 altered")
        with patch.dict(os.environ, {"SOL_PDF_VIEWER": "invented-pdf"}), \
                patch("sol.being.source_view.subprocess.Popen") as popen, self.assertRaises(SourceError):
            open_pdf(request, 0)
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
