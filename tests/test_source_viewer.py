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
from unittest.mock import Mock, mock_open, patch
import zlib

from sol.corpus.contract import CorpusError, load_snapshot, render_record
from sol.being import source_view as source_module
from sol.core import source as core_source
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

    def request_consumers(self, page_index=0):
        return (("page", lambda request: render_page(request, page_index, cache_dir=self.cache)),
                ("region", lambda request: render_region(request, page_index, cache_dir=self.cache)),
                ("open", lambda request: open_pdf(request, page_index)),
                ("follow", lambda request: source_module.follow_pdf(request, page_index)))

    def change_generation(self):
        attribution = self.records[1]["attribution"]
        attribution["status"] = "unresolved" if attribution["status"] == "confirmed" else "confirmed"
        self.write_generation()

    def verify_then_change_generation(self):
        verify = core_source._verify_file

        def changed(path, expected):
            verify(path, expected)
            self.change_generation()

        return changed

    def test_missing_pdf_diagnostic_names_the_supported_app_option(self):
        self.pdf.unlink()
        with self.assertRaises(SourceError) as caught:
            self.service.capture(PASSAGE)
        self.assertEqual(str(caught.exception),
                         "Source PDF not found. Remember it once with sol --set-source-pdf PATH.")
        self.assertFalse(self.cache.exists())
        self.assertFalse((self.directory / "config").exists())

    def test_verified_file_rejects_final_symlink_even_to_matching_pdf(self):
        link = self.directory / "linked.pdf"
        link.symlink_to(self.pdf)
        with self.assertRaisesRegex(SourceError, "must not be a symbolic link"):
            core_source._verify_file(link, self.digest)

    def test_verified_file_rejects_missing_path_and_directory(self):
        for path in (self.directory / "missing.pdf", self.directory):
            with self.subTest(path=path), self.assertRaisesRegex(SourceError, "Cannot read verified PDF snapshot"):
                core_source._verify_file(path, self.digest)

    def test_verified_file_rejects_opened_file_identity_race_with_matching_digest(self):
        # Hash real matching bytes, but simulate an identity change during that read.
        with patch("sol.core.source._stat_identity", side_effect=[(1,), (2,)]) as identity:
            with self.assertRaisesRegex(SourceError, "Verified PDF snapshot changed"):
                core_source._verify_file(self.pdf, self.digest)
        self.assertEqual(identity.call_count, 2)
        self.assertEqual(hashlib.sha256(self.pdf.read_bytes()).hexdigest(), self.digest)

    def test_verified_file_wraps_open_and_read_oserrors(self):
        error = OSError("synthetic PDF I/O failure")
        with patch.object(Path, "open", side_effect=error):
            with self.assertRaisesRegex(SourceError, "Cannot read verified PDF snapshot") as caught:
                core_source._verify_file(self.pdf, self.digest)
        self.assertIs(caught.exception.__cause__, error)
        opened = mock_open()
        opened.return_value.read.side_effect = error
        with patch.object(Path, "open", opened), patch("sol.core.source.os.fstat", return_value=self.pdf.stat()):
            with self.assertRaisesRegex(SourceError, "Cannot read verified PDF snapshot") as caught:
                core_source._verify_file(self.pdf, self.digest)
        self.assertIs(caught.exception.__cause__, error)

    def test_consumers_refuse_generation_chain_and_digest_tampering_before_external_access(self):
        original = self.service.capture(RETIRED)
        cases = [
            (("corpus", "id"), ROOT, "generation changed"),
            (("corpus", "directory"), str(self.corpus) + "/.", "generation changed"),
            *((("corpus", field), "0" * 64, "generation changed")
              for field in ("manifest_sha256", "index_sha256", "index_metadata_sha256")),
            (("requested_id",), PASSAGE, "record or its page metadata changed"),
            (("target_id",), ROOT, "record or its page metadata changed"),
            (("redirect_chain",), [PASSAGE], "record or its page metadata changed"),
            (("redirect_chain",), [PASSAGE, RETIRED], "record or its page metadata changed"),
            (("metadata_sha256",), "0" * 64, "record or its page metadata changed"),
            (("content_sha256",), "0" * 64, "record or its page metadata changed"),
            (("sources",), list(reversed(original["sources"])), "record or its page metadata changed"),
            (("source", "sha256"), "0" * 64, "PDF source binding changed"),
            (("source", "pdf_pages"), 4, "PDF source binding changed"),
        ]
        for keys, value, message in cases:
            for name, consume in self.request_consumers():
                request = deepcopy(original)
                field = request
                for key in keys[:-1]:
                    field = field[key]
                field[keys[-1]] = value
                with self.subTest(field=keys, value=value, consumer=name), \
                        patch("sol.core.source._verify_file") as verify, \
                        patch("sol.being.source_view._show_on_companion") as companion, \
                        patch("sol.core.source.shutil.which") as which, \
                        patch("sol.core.source.subprocess.run") as run, \
                        patch("sol.being.source_view.subprocess.Popen") as popen:
                    with self.assertRaisesRegex(SourceError, message):
                        consume(request)
                    verify.assert_not_called()
                    companion.assert_not_called()
                    which.assert_not_called()
                    run.assert_not_called()
                    popen.assert_not_called()
        self.assertFalse((self.cache / "renders").exists())

    def test_request_validation_refuses_bad_versions_and_missing_owned_fields(self):
        original = self.service.capture(RETIRED)
        invalid = [None, [], {}, *({**original, "version": value} for value in (True, False, 0, 2, "1", None))]
        for key in original:
            if key in {"version", "corpus", "requested_id", "target_id", "redirect_chain",
                       "metadata_sha256", "content_sha256", "sources", "source"}:
                request = deepcopy(original)
                del request[key]
                invalid.append(request)
        for container, keys in (("corpus", ("id", "directory", "manifest_sha256", "index_sha256",
                                            "index_metadata_sha256")),
                                ("source", ("sha256", "pdf_pages", "verified_pdf"))):
            for key in keys:
                request = deepcopy(original)
                del request[container][key]
                invalid.append(request)
        for index, request in enumerate(invalid):
            for name, consume in (("private", core_source._request_current), *self.request_consumers()):
                with self.subTest(case=index, consumer=name), self.assertRaises(SourceError) as caught:
                    consume(request)
                self.assertIsNotNone(caught.exception.__cause__)

    def test_bad_requested_ids_raise_source_errors_with_chained_causes(self):
        original = self.service.capture(PASSAGE)
        for value in ("", "unknown-synthetic-id", None, 42, {}, [], True):
            for name, consume in self.request_consumers():
                request = {**original, "requested_id": value}
                with self.subTest(value=value, consumer=name), self.assertRaises(SourceError) as caught:
                    consume(request)
                self.assertIs(type(caught.exception), SourceError)
                self.assertIsInstance(caught.exception.__cause__, (TypeError, ValueError))

    def test_ambiguous_requested_id_is_wrapped_without_changing_prefix_resolution(self):
        original = self.service.capture(PASSAGE)
        request = {**original, "requested_id": PASSAGE[:12]}
        self.assertIsNotNone(core_source._request_current(request))
        # A second canonical ID shares this prefix; all four consumers must wrap
        # the resolver's ambiguity rather than exposing its plain ValueError.
        self.records[0]["id"] = PASSAGE[:8] + ROOT[8:]
        for record in self.records[1:]:
            record["parent_id"] = self.records[0]["id"]
        self.write_generation()
        original = SourceService(self.load_book(), cache_dir=self.cache).capture(PASSAGE)
        for name, consume in self.request_consumers():
            with self.subTest(consumer=name), self.assertRaisesRegex(SourceError, "ambiguous") as caught:
                consume({**original, "requested_id": PASSAGE[:8]})
            self.assertIs(type(caught.exception.__cause__), ValueError)

    def test_region_validates_request_before_reading_sources_or_bbox(self):
        for request in ({}, {"sources": [None]}):
            error = SourceError("synthetic invalid request")
            with self.subTest(request=request), \
                    patch("sol.core.source._request_current", side_effect=error) as validate, \
                    patch("sol.core.source._render") as render:
                with self.assertRaises(SourceError) as caught:
                    render_region(request, 0, cache_dir=self.cache)
                self.assertIs(caught.exception, error)
                validate.assert_called_once_with(request)
                render.assert_not_called()

    def test_malformed_request_shapes_are_refused_before_pdf_or_external_access(self):
        original = self.service.capture(PASSAGE)
        invalid = [None, [], {}, {"sources": [None]}]
        cases = [
            (("corpus",), None), (("corpus",), []),
            (("corpus", "id"), []), (("corpus", "directory"), None), (("corpus", "directory"), "bad\0path"),
            (("source",), None), (("source",), []),
            (("source", "verified_pdf"), None), (("source", "verified_pdf"), []),
            (("source", "verified_pdf"), ""), (("source", "verified_pdf"), "bad\0path"),
            (("source", "pdf_pages"), True), (("source", "sha256"), None),
            (("sources",), None), (("sources",), {}), (("sources",), []),
            (("sources",), [None]), (("sources",), [{"pdf_page": 1}]),
            (("sources",), [{"pdf_page": True, "printed_page": None}]),
            (("sources",), [{"pdf_page": 1, "printed_page": 3}]),
            (("target_id",), []), (("redirect_chain",), None), (("redirect_chain",), [None]),
            (("metadata_sha256",), []), (("content_sha256",), "bad-digest"),
        ]
        for keys, value in cases:
            request = deepcopy(original)
            field = request
            for key in keys[:-1]:
                field = field[key]
            field[keys[-1]] = value
            invalid.append(request)
        missing_pdf = deepcopy(original)
        del missing_pdf["source"]["verified_pdf"]
        invalid.append(missing_pdf)
        for box in (None, 42, {}, [1, 2, 3], [True, 20, 140, 140],
                    [20, 20, float("inf"), 140], [20, 20, float("nan"), 140],
                    [-1, 20, 140, 140], [140, 20, 20, 140], [0, 0, 10**1000, 140]):
            request = deepcopy(original)
            request["sources"][0]["bbox"] = box
            invalid.append(request)
        for index, request in enumerate(invalid):
            for name, consume in self.request_consumers():
                with self.subTest(case=index, consumer=name), \
                        patch("sol.core.source._verify_file") as core_verify, \
                        patch("sol.being.source_view._verify_file") as viewer_verify, \
                        patch("sol.being.source_view._show_on_companion") as show, \
                        patch("sol.core.source.shutil.which") as which, \
                        patch("sol.core.source.subprocess.run") as run, \
                        patch("sol.being.source_view.subprocess.Popen") as popen:
                    with self.assertRaises(SourceError) as caught:
                        consume(request)
                    self.assertIsNotNone(caught.exception.__cause__)
                    core_verify.assert_not_called()
                    viewer_verify.assert_not_called()
                    show.assert_not_called()
                    which.assert_not_called()
                    run.assert_not_called()
                    popen.assert_not_called()
        self.assertFalse((self.cache / "renders").exists())

    def test_follow_refuses_stale_request_before_companion_or_dbus_access(self):
        request = self.service.capture(PASSAGE)
        self.change_generation()
        self.assert_follow_refused_before_external_access(request, "generation changed")

    def test_follow_refuses_corrupt_pdf_before_companion_or_dbus_access(self):
        request = self.service.capture(PASSAGE)
        snapshot = Path(request["source"]["verified_pdf"])
        snapshot.chmod(0o600)
        snapshot.write_bytes(b"synthetic corrupt snapshot")
        self.assert_follow_refused_before_external_access(request, "Verified PDF snapshot changed")

    def assert_follow_refused_before_external_access(self, request, message):
        process = Mock()
        companion = (process, Path(request["source"]["verified_pdf"]))
        with patch.object(source_module, "_companion", companion), \
                patch("sol.being.source_view._show_on_companion") as show, \
                patch("sol.being.source_view.shutil.which") as which, \
                patch("sol.being.source_view.subprocess.run") as run, \
                patch("sol.being.source_view.subprocess.Popen") as popen:
            with self.assertRaisesRegex(SourceError, message):
                source_module.follow_pdf(request)
            self.assertIs(source_module._companion, companion)
            self.assertEqual(process.mock_calls, [])
            show.assert_not_called()
            which.assert_not_called()
            run.assert_not_called()
            popen.assert_not_called()

    def test_render_paths_refuse_corpus_change_after_pdf_check_on_miss_and_hit(self):
        for render, index in ((render_page, 0), (render_region, 0), (render_region, 1)):
            for cached in (False, True):
                with self.subTest(render=render.__name__, index=index, cached=cached):
                    shutil.rmtree(self.cache / "renders", ignore_errors=True)
                    request = SourceService(self.load_book(), cache_dir=self.cache).capture(PASSAGE)
                    self.rendered = []
                    with patch("sol.core.source.shutil.which", return_value="/invented/pdftoppm"), \
                            patch("sol.core.source.subprocess.run", side_effect=self.renderer):
                        if cached:
                            render(request, index, cache_dir=self.cache)
                        before = {p.name: p.read_bytes() for p in (self.cache / "renders").glob("*")}
                        with patch("sol.core.source._verify_file", side_effect=self.verify_then_change_generation()):
                            with self.assertRaisesRegex(SourceError, "generation changed"):
                                render(request, index, cache_dir=self.cache)
                    after = {p.name: p.read_bytes() for p in (self.cache / "renders").glob("*")}
                    self.assertEqual(after, before)  # No stale PNG/sidecar publication or temporary files.

    def test_render_paths_refuse_corpus_change_during_render_before_publication(self):
        for render, index in ((render_page, 0), (render_region, 0), (render_region, 1)):
            with self.subTest(render=render.__name__, index=index):
                shutil.rmtree(self.cache / "renders", ignore_errors=True)
                request = SourceService(self.load_book(), cache_dir=self.cache).capture(PASSAGE)
                self.rendered = []

                def changed(arguments, **kwargs):
                    result = self.renderer(arguments, **kwargs)
                    if arguments[-1] != "-v":
                        self.change_generation()
                    return result

                with patch("sol.core.source.shutil.which", return_value="/invented/pdftoppm"), \
                        patch("sol.core.source.subprocess.run", side_effect=changed):
                    with self.assertRaisesRegex(SourceError, "generation changed"):
                        render(request, index, cache_dir=self.cache)
                self.assertEqual(len(self.rendered), 1)
                self.assertEqual(list((self.cache / "renders").iterdir()), [])

    def test_viewers_refuse_corpus_change_after_pdf_check_before_external_access(self):
        for follow in (False, True):
            with self.subTest(follow=follow):
                request = SourceService(self.load_book(), cache_dir=self.cache).capture(PASSAGE)
                process = Mock()
                companion = (process, Path(request["source"]["verified_pdf"]))
                with patch("sol.being.source_view._verify_file", side_effect=self.verify_then_change_generation()), \
                        patch.object(source_module, "_companion", companion), \
                        patch.dict(os.environ, {"SOL_PDF_VIEWER": "invented-pdf"}), \
                        patch("sol.being.source_view.shutil.which") as which, \
                        patch("sol.being.source_view.subprocess.run") as run, \
                        patch("sol.being.source_view.subprocess.Popen") as popen, \
                        patch("sol.being.source_view._show_on_companion") as show:
                    with self.assertRaisesRegex(SourceError, "generation changed") as caught:
                        (source_module.follow_pdf if follow else open_pdf)(request, 0)
                    self.assertIsInstance(caught.exception.__cause__, CorpusError)
                    self.assertIs(source_module._companion, companion)
                    self.assertEqual(process.mock_calls, [])
                    which.assert_not_called()
                    run.assert_not_called()
                    popen.assert_not_called()
                    show.assert_not_called()

    def test_viewers_refuse_corpus_change_while_pdf_bytes_are_hashed(self):
        for follow in (False, True):
            with self.subTest(follow=follow):
                request = SourceService(self.load_book(), cache_dir=self.cache).capture(PASSAGE)
                identity = core_source._stat_identity
                calls = []

                def changed(stat):
                    calls.append(stat)
                    if len(calls) == 2:
                        self.change_generation()
                    return identity(stat)

                with patch("sol.core.source._stat_identity", side_effect=changed), \
                        patch("sol.core.source.verify_snapshot_current", wraps=core_source.verify_snapshot_current) as final, \
                        patch("sol.being.source_view._show_on_companion") as show, \
                        patch("sol.being.source_view.shutil.which") as which, \
                        patch("sol.being.source_view.subprocess.Popen") as popen:
                    with self.assertRaisesRegex(SourceError, "generation changed") as caught:
                        (source_module.follow_pdf if follow else open_pdf)(request, 0)
                    self.assertIsInstance(caught.exception.__cause__, CorpusError)
                    final.assert_called_once()
                    self.assertEqual(len(calls), 2)
                    show.assert_not_called()
                    which.assert_not_called()
                    popen.assert_not_called()

    def test_viewers_final_check_uses_the_fresh_snapshot_after_pdf_hashing(self):
        request = self.service.capture(PASSAGE)
        for follow in (False, True):
            with self.subTest(follow=follow):
                order = []
                current = core_source._request_current
                verify = core_source._verify_file
                final = core_source.verify_snapshot_current
                snapshots = []

                def load(value):
                    snapshots.append(current(value))
                    order.append("request")
                    return snapshots[-1]

                def hashed(path, digest):
                    verify(path, digest)
                    order.append("pdf")

                def checked(snapshot):
                    self.assertIs(snapshot, snapshots[-1])
                    order.append("final")
                    final(snapshot)

                with patch("sol.being.source_view._request_current", side_effect=load), \
                        patch("sol.being.source_view._verify_file", side_effect=hashed), \
                        patch("sol.core.source.verify_snapshot_current", side_effect=checked):
                    result = (source_module.follow_pdf if follow else open_pdf)(request, 0)
                self.assertEqual(result, False if follow else None)
                self.assertEqual(order, ["request", "pdf", "final"])

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
            for name, consume in self.request_consumers(index):
                with self.subTest(index=index, consumer=name), \
                        patch("sol.core.source._verify_file") as core_verify, \
                        patch("sol.being.source_view._verify_file") as viewer_verify:
                    with self.assertRaisesRegex(SourceError, "source page index"):
                        consume(request)
                    core_verify.assert_not_called()
                    viewer_verify.assert_not_called()

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
