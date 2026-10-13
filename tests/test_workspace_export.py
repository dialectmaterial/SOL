"""Synthetic, pure Markdown inquiry exports; no private book or database."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sol.workspace.export as sol_workspace_export
from sol.workspace.export import render_workspace_markdown


CORPUS = "aaaaaaaa-0000-4000-8000-000000000001"
FIRST = "bbbbbbbb-0000-4000-8000-000000000001"
SECOND = "bbbbbbbb-0000-4000-8000-000000000002"
EDITORIAL = "bbbbbbbb-0000-4000-8000-000000000003"
RETIRED = "cccccccc-0000-4000-8000-000000000001"
RETIRED_AGAIN = "cccccccc-0000-4000-8000-000000000002"
MISSING = "dddddddd-0000-4000-8000-000000000001"
NOTE = "eeeeeeee-0000-4000-8000-000000000001"
SOURCE = "abcdef0123456789" * 4
WHEN = "2026-10-12T10:00:00Z"


def fixture(version=2):
    def record(identifier, body, author="Synthetic philosopher", role="main_text"):
        return {"id": identifier, "type": "paragraph", "parent_id": None, "order": 1,
                "reader_title": "Synthetic heading", "reader_path": "/BEING/quality.txt",
                "attribution": {"author": author, "role": role, "status": "confirmed"},
                "sources": [{"pdf_page": 80, "printed_page": "7", "bbox": [1, 2, 30, 40]},
                            {"pdf_page": 81, "printed_page": "8"}],
                "markdown": body, "plain_text": body, "document": "being.md",
                "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "transcription_status": "needs_visual_review"}
    records = {FIRST: record(FIRST, "Synthetic *being* α: a first paragraph.\n\nA second paragraph."),
               SECOND: record(SECOND, "UNREFERENCED BOOK BODY MUST NOT BE INCLUDED"),
               EDITORIAL: record(EDITORIAL, "Editorial *note*, not Hegel's prose.", "Synthetic editor", "editorial_note"),
               RETIRED: {"id": RETIRED, "type": "retired_record", "redirect_id": FIRST},
               RETIRED_AGAIN: {"id": RETIRED_AGAIN, "type": "retired_record", "redirect_id": RETIRED}}
    records[EDITORIAL]["type"] = "note"
    records[EDITORIAL].pop("reader_path")
    book = SimpleNamespace(canonical_records=records,
                           corpus_manifest={"corpus_id": CORPUS,
                                            "edition": {"title": "Synthetic edition", "translator": "Translator"},
                                            "source": {"filename": "Synthetic.pdf", "sha256": SOURCE}},
                           corpus_snapshot=SimpleNamespace(manifest_sha256="1" * 64,
                                                           index_sha256="2" * 64,
                                                           index_metadata_sha256="3" * 64,
                                                           documents={"being.md": "4" * 64}))
    annotation = {"id": NOTE, "target_id": FIRST, "body": "My *personal* thought α.\n\nIts continuation.",
                  "actor": "Ada", "attribution": {"role": "personal_note", "author": "Ada"},
                  "created_at": WHEN, "updated_at": WHEN,
                  "content_sha256": records[FIRST]["content_sha256"], "revision": 1 if version == 2 else None}
    snapshot = {"format": "sol-workspace", "schema_version": version, "corpus_id": CORPUS,
                "provenance": deepcopy({key: book.corpus_manifest[key] for key in ("edition", "source")}),
                "created_at": WHEN, "exported_at": WHEN,
                "state": {"cwd": "/BEING", "scope": "directory", "current_id": FIRST,
                          "previous_cwd": "/", "revision": 1},
                "history": [{"revision": 1, "cwd": "/BEING", "scope": "directory",
                             "current_id": FIRST, "previous_cwd": "/", "actor": "Ada", "created_at": WHEN}],
                "bookmarks": [{"name": "beginning", "target_id": FIRST, "actor": "Ada", "created_at": WHEN}],
                "annotations": [annotation], "comparisons": [], "reviews": [], "relations": []}
    if version == 2:
        snapshot["annotation_history"] = [{"annotation_id": NOTE, "revision": 1, "target_id": FIRST,
                                          "actor": "Ada", "created_at": WHEN, "updated_at": WHEN,
                                          "body": annotation["body"], "content_sha256": annotation["content_sha256"],
                                          "editor": "Ada", "recorded_at": WHEN, "kind": "created"}]
    return book, snapshot


class WorkspaceMarkdownTests(unittest.TestCase):
    def setUp(self):
        self.book, self.snapshot = fixture()

    def render(self, **options):
        return render_workspace_markdown(self.book, self.snapshot, workspace_name="study", **options)

    def test_default_report_is_derived_with_explicit_snapshot_basis(self):
        result = self.render()
        for text in ("Report format version: `1`", "not a backup", "authoritative machine-readable",
                     "one workspace export", WHEN, "PDF bytes are NOT verified", "manifest-declared", CORPUS):
            self.assertIn(text, result)
        self.assertIn("Loaded index sha256", result)
        self.assertNotIn(self.book.canonical_records[FIRST]["markdown"], result)
        self.assertNotIn(self.book.canonical_records[SECOND]["markdown"], result)

    def test_safe_unicode_personal_markdown_and_boundaries_exact(self):
        body = "α, ἰδέα, *italics*, **bold**.\n\n# Not a report heading\n![image](https://invalid.test/x)\n<script>opaque</script>\n<!-- sol:literal -->"
        self.snapshot["annotations"][0]["body"] = body
        result = self.render()
        self.assertIn("```markdown\n" + body + "\n```", result)
        self.assertIn("Current saved personal body:", result)

    def test_adaptive_fences_cannot_be_closed_by_untrusted_markdown(self):
        body = "before\n`````\n# forged report\n`````\nafter `code`"
        self.snapshot["annotations"][0]["body"] = body
        self.assertIn("``````markdown\n" + body + "\n``````", self.render())

    def test_metadata_neutralizes_markdown_html_newlines_and_terminal_controls(self):
        malicious = "\n# Forged\n![remote](https://invalid.test/img)<script>\x1b[31m\x85\u202e\ud800"
        self.snapshot["bookmarks"][0]["name"] = malicious
        self.book.corpus_manifest["edition"]["title"] = malicious
        self.book.canonical_records[FIRST]["reader_title"] = malicious
        self.book.canonical_records[FIRST]["attribution"]["author"] = malicious
        result = self.render()
        for unsafe in ("\n# Forged", "\x1b", "\x85", "\u202e", "\ud800"):
            self.assertNotIn(unsafe, result)
        self.assertIn('`\\n# Forged\\n![remote](https://invalid.test/img)<script>', result)
        self.assertIn(r"\x1b", result)
        self.assertIn(r"\u202e", result)

    def test_raw_body_controls_are_neutralized_before_fencing(self):
        self.snapshot["annotations"][0]["body"] = "α\x1b[31m\u202e\n\n*literal*"
        result = self.render()
        self.assertIn("```markdown\nα\\x1b[31m\\u202e\n\n*literal*\n```", result)
        self.assertNotIn("\x1b", result)
        self.assertNotIn("\u202e", result)

    def test_requested_metadata_deduplicates_but_keeps_all_pages_and_attribution(self):
        result = self.render()
        self.assertEqual(result.count("### Reference 1"), 1)
        self.assertNotIn("### Reference 2", result)
        self.assertIn("pdf_page", result)
        self.assertIn("80", result)
        self.assertIn("81", result)
        self.assertIn("printed_page", result)
        self.assertIn("Current attribution", result)
        self.assertIn(self.book.canonical_records[FIRST]["content_sha256"], result)
        self.assertIn("Canonical pending review: `True`", result)
        self.assertIn('Loaded canonical document SHA256: `' + '4' * 64 + '`', result)
        self.assertIn('Loaded corpus document count: `1`', result)

    def test_optional_excerpts_only_include_referenced_current_canonical_records(self):
        self.snapshot["bookmarks"].append({"name": "editorial", "target_id": EDITORIAL})
        result = self.render(include_passages=True)
        for identifier in (FIRST, EDITORIAL):
            self.assertIn("```markdown\n" + self.book.canonical_records[identifier]["markdown"] + "\n```", result)
        self.assertIn("editorial_note", result)
        self.assertNotIn(self.book.canonical_records[SECOND]["markdown"], result)
        self.assertIn("Not the historically inspected text", result)

    def test_full_redirect_chains_keep_alias_ids_and_excerpts_dedupe_resolved_id(self):
        self.snapshot["bookmarks"].extend([{"name": "retired", "target_id": RETIRED},
                                           {"name": "retired twice", "target_id": RETIRED_AGAIN}])
        result = self.render(include_passages=True)
        for identifier in (FIRST, RETIRED, RETIRED_AGAIN):
            self.assertIn(identifier, result)
        body = self.book.canonical_records[FIRST]["markdown"]
        self.assertEqual(result.count(body), 1)
        self.assertIn("Requested IDs resolving to this excerpt", result)
        self.assertIn("retired / explicitly redirected", result)
        self.assertIn("same ID", result)

    def test_missing_references_stay_visible_and_no_prefix_or_fuzzy_repair(self):
        self.snapshot["bookmarks"] = [{"name": "absent", "target_id": MISSING},
                                       {"name": "prefix", "target_id": FIRST[:8]}]
        self.snapshot["state"] = None
        self.snapshot["history"] = []
        self.snapshot["annotations"] = []
        self.snapshot["annotation_history"] = []
        result = self.render(include_passages=True)
        self.assertIn(MISSING, result)
        self.assertEqual(result.count("No exact canonical record with this ID"), 2)
        self.assertNotIn(self.book.canonical_records[FIRST]["markdown"], result)

    def test_retirement_missing_target_and_cycle_are_explicit(self):
        for target, label in ((MISSING, "unresolved explicit redirect"), (RETIRED, "cycle")):
            with self.subTest(target=target):
                self.book.canonical_records[RETIRED]["redirect_id"] = target
                self.snapshot["bookmarks"] = [{"name": "retired", "target_id": RETIRED}]
                self.assertIn(label, self.render())

    def test_v1_never_invents_history_or_editor(self):
        self.book, self.snapshot = fixture(1)
        result = self.render()
        self.assertIn("Version-1 workspace: no audited revision history exists", result)
        self.assertNotIn("Stored personal revision", result)
        self.assertNotIn("editor:", result)

    def test_v2_preserves_all_revision_snapshots_authorship_and_null_baseline_editor(self):
        initial = self.snapshot["annotation_history"][0]
        initial["body"], initial["editor"], initial["kind"] = "Legacy *body*.", None, "legacy_baseline"
        second = {**initial, "revision": 2, "body": "Revised *body*.", "editor": "Ada", "kind": "edited"}
        self.snapshot["annotation_history"].append(second)
        self.snapshot["annotations"][0]["body"] = second["body"]
        self.snapshot["annotations"][0]["revision"] = 2
        result = self.render()
        self.assertEqual(result.count("#### Stored personal revision"), 2)
        self.assertIn("Legacy *body*.", result)
        self.assertIn("editor: `null", result)
        self.assertIn("actor: `Ada`", result)
        self.assertLess(result.index("revision: `1`", result.index("#### Stored personal revision")),
                        result.index("revision: `2`", result.index("#### Stored personal revision")))

    def test_unmatched_supplied_audit_snapshots_are_not_dropped(self):
        self.snapshot["annotations"] = []
        result = self.render()
        self.assertIn("Unmatched stored personal revision", result)
        self.assertIn(self.snapshot["annotation_history"][0]["body"], result)

    def test_stale_and_retired_personal_bindings_do_not_reconstruct_old_source(self):
        self.snapshot["annotations"][0]["content_sha256"] = "0" * 64
        self.assertIn("STALE", self.render(include_passages=True))
        self.snapshot["annotations"][0]["target_id"] = RETIRED
        self.assertIn("RETIRED target", self.render(include_passages=True))

    def test_review_append_order_and_limited_current_binding_preserve_pending_flag(self):
        review = {"id": "review-first", "target_id": FIRST, "actor": "Ada", "outcome": "verified",
                  "issue": "Checked *formula*.\n\nStill a reader's testimony.", "created_at": "2030-01-01T00:00:00Z",
                  "content_sha256": self.book.canonical_records[FIRST]["content_sha256"], "source_sha256": SOURCE}
        self.snapshot["reviews"] = [review, {**review, "id": "review-second", "created_at": WHEN}]
        result = self.render()
        self.assertLess(result.index("review-first"), result.index("review-second"))
        self.assertIn("Same text/PDF fingerprints only", result)
        self.assertIn("metadata is not bound", result)
        self.assertIn("never clears canonical pending-review flags", result)
        self.assertIn("Canonical pending review: `True`", result)
        self.assertIn(review["issue"], result)

    def test_review_stale_unversioned_and_unresolved_remain_distinct(self):
        for digest, target, expected in (("0" * 64, FIRST, "STALE"),
                                          (None, FIRST, "UNVERSIONED"),
                                          ("0" * 64, MISSING, "UNRESOLVED")):
            with self.subTest(expected=expected):
                self.snapshot["reviews"] = [{"target_id": target, "content_sha256": digest,
                                            "source_sha256": SOURCE, "issue": "My inspection"}]
                self.assertIn(expected, self.render())

    def test_comparison_order_question_and_directed_relation_rationale_preserved(self):
        self.snapshot["comparisons"] = [{"name": "distance", "target_ids": [EDITORIAL, FIRST, EDITORIAL],
                                         "actor": "Ada", "question": "Which *difference*?\n\nWhy?"}]
        self.snapshot["relations"] = [{"id": "relation", "source_id": EDITORIAL, "target_id": FIRST,
                                       "kind": "contrasts_with", "actor": "Ada", "rationale": "My *directed* claim."}]
        result = self.render()
        begin = result.index("## Ordered comparisons")
        self.assertLess(result.index("Passage 1: `" + EDITORIAL, begin), result.index("Passage 2: `" + FIRST, begin))
        self.assertIn("Passage 3: `" + EDITORIAL, result)
        self.assertIn(self.snapshot["comparisons"][0]["question"], result)
        self.assertIn("source id: `" + EDITORIAL, result)
        self.assertIn("target id: `" + FIRST, result)
        self.assertIn(self.snapshot["relations"][0]["rationale"], result)

    def test_source_drift_is_warning_not_claim_of_pdf_verification(self):
        result = self.render(freshness={"state": "changed", "reason": "changed <manifest>"})
        self.assertIn("WARNING", result)
        self.assertIn("already loaded corpus snapshot", result)
        self.assertIn("changed <manifest>", result)
        self.assertIn("PDF bytes are NOT verified", result)

    def test_rejects_identity_missing_or_mismatched_before_rendering(self):
        for value in (None, "different"):
            with self.subTest(corpus=value):
                self.snapshot["corpus_id"] = value
                with self.assertRaisesRegex(ValueError, "corpus identities"):
                    self.render()
        self.snapshot["corpus_id"] = CORPUS
        self.snapshot["provenance"]["source"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source fingerprints"):
            self.render()

    def test_hex_source_case_normalized_and_direct_nested_conflict_rejected(self):
        self.snapshot["provenance"]["source"]["sha256"] = SOURCE.upper()
        self.snapshot["provenance"]["source_sha256"] = SOURCE
        self.render()
        self.snapshot["provenance"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source fingerprints"):
            self.render()
        self.snapshot["provenance"] = {"source_sha256": SOURCE.upper()}
        self.render()

    def test_deterministic_nonmutating_and_no_io(self):
        before_book, before_snapshot = deepcopy(self.book), deepcopy(self.snapshot)
        with patch("builtins.open", side_effect=AssertionError("no files")):
            first = self.render(include_passages=True)
            second = self.render(include_passages=True)
        self.assertEqual(first, second)
        self.assertEqual(self.book.__dict__, before_book.__dict__)
        self.assertEqual(self.snapshot, before_snapshot)

    def test_module_imports_only_pure_standard_library_helpers(self):
        source = Path(sol_workspace_export.__file__).read_text(encoding="utf-8")
        imports = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        self.assertEqual(imports, {"__future__", "json", "re", "unicodedata"})

    def test_invalid_snapshot_shape_option_and_v1_audit_refused(self):
        for options in ({"include_passages": 1}, {"freshness": "current"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.render(**options)
        self.snapshot["comparisons"] = "wrong"
        with self.assertRaisesRegex(ValueError, "list of records"):
            self.render()
        self.book, self.snapshot = fixture(1)
        self.snapshot["annotation_history"] = [{"body": "invented"}]
        with self.assertRaisesRegex(ValueError, "do not have audited"):
            self.render()


    @unittest.skipUnless(importlib.util.find_spec('markdown_it'), 'optional reference Markdown parser unavailable')
    def test_metadata_and_nested_fences_parse_as_literal_content_not_active_markup(self):
        from markdown_it import MarkdownIt
        parser = MarkdownIt('commonmark')
        payload = "`https://invalid.test/a` <script>alert(1)</script> ![img](https://invalid.test/b) [go](https://invalid.test/c) test@example.invalid"
        self.snapshot['bookmarks'][0]['name'] = payload
        self.snapshot['annotations'][0]['body'] = '```\n# Pretend report\n```\n' + payload
        report = self.render()
        tokens = parser.parse(report)
        flattened = [child for token in tokens for child in ([token] + list(token.children or []))]
        self.assertFalse(any(token.type in {'link_open', 'image', 'html_block', 'html_inline'} for token in flattened))
        self.assertTrue(any(token.type == 'code_inline' and token.content == payload for token in flattened))
        self.assertTrue(any(token.type == 'fence' and token.content.rstrip('\n') == self.snapshot['annotations'][0]['body']
                            for token in flattened))
        for metadata in [FIRST, WHEN, ' leading space', 'trailing space ', '`edge`', '``', '   ']:
            with self.subTest(metadata=metadata):
                inline = parser.parseInline(sol_workspace_export._code(metadata))[0].children
                self.assertEqual([(token.type, token.content) for token in inline], [('code_inline', metadata)])


if __name__ == "__main__":
    unittest.main()
