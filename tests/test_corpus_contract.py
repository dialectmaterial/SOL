"""Synthetic, redistributable tests: no passages from the source edition."""

from __future__ import annotations

import builtins
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sol_corpus_contract as contract


class CorpusContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.section_id = contract.new_id()
        self.paragraph_id = contract.new_id()
        self.note_id = contract.new_id()
        self.nested_id = contract.new_id()
        self.section = self.record(self.section_id, "section", None, 0, title="Synthetic section", path="/sample")
        self.paragraph = self.record(self.paragraph_id, "paragraph", self.section_id, 1)
        self.manifest = {
            "contract_version": 1,
            "edition": {"title": "Synthetic test edition", "completeness": "source_complete"},
            "source": {"filename": "nonexistent-private-source.pdf", "sha256": "0" * 64, "pdf_pages": 1},
            "documents": ["sample.md"],
            "page_inventory": [{"pdf_page": 1, "printed_page": "iv", "disposition": "records"}],
        }
        self.write_corpus([(self.section, "# Synthetic section"), (self.paragraph, "An *editable* paragraph.")])

    @staticmethod
    def record(identifier: str, kind: str, parent: str | None, order: int, **extra) -> dict:
        return {
            "id": identifier, "type": kind, "parent_id": parent, "order": order,
            "sources": [{"pdf_page": 1, "printed_page": "iv", "bbox": [10, 20, 100, 40]}],
            "attribution": {"author": None, "status": "unresolved", "role": "synthetic"},
            **extra,
        }

    def write_corpus(self, pairs: list[tuple[dict, str]], document: str = "sample.md") -> None:
        (self.root / "corpus.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        (self.root / document).write_text("\n".join(contract.render_record(meta, body) for meta, body in pairs), encoding="utf-8")

    def test_roundtrip_preserves_ids_unicode_markdown_and_metadata(self) -> None:
        body = 'A *cursive* αβγ sentence, **strong** text, “quotes”, and \n\n> a quotation.\n\n- a list item'
        encoded = contract.render_record(self.paragraph, body)
        parsed = contract.parse_document(encoded)[0]
        self.assertEqual(parsed["markdown"], body)
        self.assertEqual(parsed["id"], self.paragraph_id)
        metadata = {key: value for key, value in parsed.items() if key not in {"markdown", "plain_text", "document"}}
        self.assertEqual(contract.render_record(metadata, parsed["markdown"]), encoded)
        self.assertIn("αβγ", parsed["plain_text"])

    def test_text_and_heading_edit_do_not_allocate_ids(self) -> None:
        contract.reindex(self.root)
        before = contract.load_index(self.root)
        renamed = {**self.section, "title": "Revised heading"}
        self.write_corpus([(renamed, "# Revised *heading*"), (self.paragraph, "Corrected prose with **emphasis**.")])
        contract.reindex(self.root)
        after = contract.load_index(self.root)
        self.assertEqual([record["id"] for record in before], [record["id"] for record in after])
        self.assertEqual(after[1]["plain_text"], "Corrected prose with emphasis.")
        self.assertEqual(after[1]["context"][0]["title"], "Revised heading")

    def test_nested_notes_are_reciprocal_and_have_context(self) -> None:
        paragraph = {**self.paragraph, "note_ids": [self.note_id]}
        note = self.record(self.note_id, "note", self.section_id, 2, label="a", backlinks=[self.paragraph_id], note_ids=[self.nested_id])
        nested = self.record(self.nested_id, "note", self.note_id, 3, label="1", backlinks=[self.note_id])
        self.write_corpus([
            (self.section, "# Synthetic section"),
            (paragraph, f"Prose with a [note](#{self.note_id})."),
            (note, f"An editorial note with a [nested note](#{self.nested_id})."),
            (nested, "The nested note's content."),
        ])
        contract.reindex(self.root)
        records = contract.load_index(self.root)
        self.assertEqual(records[3]["parent_id"], self.note_id)
        self.assertEqual([context["id"] for context in records[3]["context"]], [self.section_id, self.note_id])

    def test_duplicate_ids_rejected_without_overwriting_previous_index(self) -> None:
        contract.reindex(self.root)
        original = (self.root / "index.jsonl").read_bytes()
        self.write_corpus([(self.section, "# Synthetic section"), ({**self.paragraph, "id": self.section_id}, "Duplicate ID.")])
        with self.assertRaisesRegex(contract.CorpusError, "Duplicate permanent ID"):
            contract.reindex(self.root)
        self.assertEqual((self.root / "index.jsonl").read_bytes(), original)

    def test_missing_parent_rejected(self) -> None:
        self.write_corpus([(self.section, "# Synthetic section"), ({**self.paragraph, "parent_id": contract.new_id()}, "Orphan.")])
        with self.assertRaisesRegex(contract.CorpusError, "Missing parent"):
            contract.reindex(self.root)

    def test_parent_cycle_rejected(self) -> None:
        self.write_corpus([({**self.section, "parent_id": self.paragraph_id}, "# Synthetic section"), (self.paragraph, "Cyclic prose.")])
        with self.assertRaisesRegex(contract.CorpusError, "Parent cycle"):
            contract.reindex(self.root)

    def test_broken_note_link_and_backlink_rejected(self) -> None:
        self.write_corpus([(self.section, "# Synthetic section"), ({**self.paragraph, "note_ids": [self.note_id]}, "Missing note.")])
        with self.assertRaisesRegex(contract.CorpusError, "Broken note link"):
            contract.reindex(self.root)
        note = self.record(self.note_id, "note", self.section_id, 2)
        self.write_corpus([(self.section, "# Synthetic section"), ({**self.paragraph, "note_ids": [self.note_id]}, "Missing backlink."), (note, "A note.")])
        with self.assertRaisesRegex(contract.CorpusError, "missing backlink"):
            contract.reindex(self.root)

    def test_duplicate_order_and_out_of_order_document_rejected(self) -> None:
        self.write_corpus([(self.section, "# Synthetic section"), ({**self.paragraph, "order": 0}, "Prose.")])
        with self.assertRaisesRegex(contract.CorpusError, "Duplicate global order"):
            contract.reindex(self.root)
        self.write_corpus([(self.paragraph, "Prose."), (self.section, "# Synthetic section")])
        with self.assertRaisesRegex(contract.CorpusError, "not in increasing"):
            contract.reindex(self.root)

    def test_printed_page_mismatch_rejected(self) -> None:
        changed = {**self.paragraph, "sources": [{"pdf_page": 1, "printed_page": "5"}]}
        self.write_corpus([(self.section, "# Synthetic section"), (changed, "Prose.")])
        with self.assertRaisesRegex(contract.CorpusError, "Printed-page provenance"):
            contract.reindex(self.root)

    def test_inventory_has_no_silent_unindexed_pages(self) -> None:
        self.manifest["source"]["pdf_pages"] = 2
        self.manifest["page_inventory"].append({"pdf_page": 2, "printed_page": "v", "disposition": "records"})
        self.write_corpus([(self.section, "# Synthetic section"), (self.paragraph, "Prose.")])
        with self.assertRaisesRegex(contract.CorpusError, "have no content"):
            contract.reindex(self.root)
        self.manifest["page_inventory"][1].update(disposition="blank", reason="Visually verified blank")
        self.write_corpus([(self.section, "# Synthetic section"), (self.paragraph, "Prose.")])
        self.assertEqual(contract.reindex(self.root)["records"], 2)

    def test_plain_text_commonmark_escapes_lists_links_and_code(self) -> None:
        markdown = r'\*literal\* and *italic* with **bold**, identifier_name, `a * b`, and [a **label**](https://example.invalid).' + '\n\n> quotation\n\n1. first\n2. second'
        text = contract.plain_text(markdown)
        self.assertIn("*literal* and italic with bold, identifier_name, a * b, and a label.", text)
        self.assertIn("quotation", text)
        self.assertIn("first\n", text)
        self.assertNotIn("example.invalid", text)
        self.assertNotIn("1.", text)

    def test_plain_text_entities_images_html_and_noncontent_anchors(self) -> None:
        text = contract.plain_text(f'<a id="{self.note_id}"></a>\n\nα &amp; β <sup>2</sup> and <em>HTML italic</em>.\n\n![diagram *description*](image.png)')
        self.assertIn("α & β 2 and HTML italic.", text)
        self.assertIn("diagram description", text)
        self.assertNotIn(self.note_id, text)
        self.assertNotIn("<sup>", text)
        self.assertEqual(contract.plain_text(r'\<literal\> &lt;literal&gt;'), "<literal> <literal>")

    def test_literal_fenced_code_retained(self) -> None:
        self.assertEqual(contract.plain_text('```text\n*not emphasis* &amp; α\n```'), '*not emphasis* &amp; α')
        self.assertEqual(contract.plain_text('Before.\n\n```\nx = 2\n```\n\nAfter.'), 'Before.\nx = 2\nAfter.')

    def test_inline_script_and_comments_do_not_become_classifier_text(self) -> None:
        self.assertEqual(contract.plain_text('Before <script>hidden()</script> after <!-- invisible -->.'), 'Before  after .')

    def test_sol_note_callouts_are_omitted_but_math_superscripts_remain(self) -> None:
        markdown = f'Introduction,<sup data-sol-note="{self.note_id}">[14](notes.md#{self.note_id})</sup> and x<sup>2</sup>.'
        self.assertEqual(contract.plain_text(markdown), 'Introduction, and x2.')
        self.assertEqual(contract.plain_text('A<sup data-sol-note="not-a-uuid">14</sup>.'), 'A14.')
        self.assertEqual(contract.plain_text(f'A<sup data-sol-note="{self.note_id}"><em>14</em><sup>2</sup></sup>B<sup>3</sup>'), 'AB3')

    def test_note_callout_markup_is_preserved_with_reciprocal_links(self) -> None:
        paragraph = {**self.paragraph, "note_ids": [self.note_id]}
        note = self.record(self.note_id, "note", self.paragraph_id, 2, label="14", backlinks=[self.paragraph_id])
        markdown = f'Ordinary prose<sup data-sol-note="{self.note_id}">[14](sample.md#{self.note_id})</sup> continues.'
        self.write_corpus([(self.section, '# Synthetic section'), (paragraph, markdown), (note, '#### Note 14')])
        contract.reindex(self.root)
        indexed = contract.load_index(self.root)
        self.assertEqual(indexed[1]['markdown'], markdown)
        self.assertEqual(indexed[1]['plain_text'], 'Ordinary prose continues.')
        self.assertEqual(indexed[1]['note_ids'], [self.note_id])
        self.assertEqual(indexed[2]['backlinks'], [self.paragraph_id])

    def test_missing_note_target_inside_annotated_superscript_is_rejected(self) -> None:
        paragraph = {**self.paragraph, 'note_ids': [self.note_id]}
        markdown = f'Prose<sup data-sol-note="{self.note_id}">[14](sample.md#{self.note_id})</sup>.'
        self.write_corpus([(self.section, '# Synthetic section'), (paragraph, markdown)])
        with self.assertRaisesRegex(contract.CorpusError, 'Broken note link'):
            contract.reindex(self.root)

    def test_annotated_callout_cannot_silently_redact_unregistered_content(self) -> None:
        markdown = f'Prose<sup data-sol-note="{self.note_id}">[14](sample.md#{self.note_id})</sup>.'
        with self.assertRaisesRegex(contract.CorpusError, 'absent from note_ids'):
            contract.parse_document(contract.render_record(self.paragraph, markdown))
        # Annotation-like text inside code is literal and has no link semantics.
        literal = f'`<sup data-sol-note="{self.note_id}">14</sup>`'
        parsed = contract.parse_document(contract.render_record(self.paragraph, literal))[0]
        self.assertEqual(parsed['plain_text'], f'<sup data-sol-note="{self.note_id}">14</sup>')

    def test_note_annotation_and_clickable_link_must_agree(self) -> None:
        metadata = {**self.paragraph, 'note_ids': [self.note_id]}
        mismatched = f'Prose<sup data-sol-note="{self.note_id}">[14](notes.md#{self.nested_id})</sup>.'
        with self.assertRaisesRegex(contract.CorpusError, 'mismatched link destination'):
            contract.parse_document(contract.render_record(metadata, mismatched))
        missing = f'Prose<sup data-sol-note="{self.note_id}">14</sup>.'
        with self.assertRaisesRegex(contract.CorpusError, 'matching CommonMark links'):
            contract.parse_document(contract.render_record(metadata, missing))
        unclosed = f'Prose<sup data-sol-note="{self.note_id}">[14](notes.md#{self.note_id}).'
        with self.assertRaisesRegex(contract.CorpusError, 'Unclosed SOL'):
            contract.parse_document(contract.render_record(metadata, unclosed))

    def test_optional_random_eligibility_is_an_actual_boolean(self) -> None:
        metadata = {**self.paragraph, 'random_eligible': False, 'contains_math': True}
        parsed = contract.parse_document(contract.render_record(metadata, 'A synthetic paragraph requiring visual review.'))[0]
        self.assertIs(parsed['random_eligible'], False)
        for malformed in ('false', 0, None):
            with self.subTest(value=malformed):
                with self.assertRaisesRegex(contract.CorpusError, 'random_eligible.*bool'):
                    contract.render_record({**self.paragraph, 'random_eligible': malformed}, 'Prose.')

    def test_retired_record_requires_valid_redirect_uuid(self) -> None:
        retired = {**self.paragraph, 'type': 'retired_record'}
        with self.assertRaisesRegex(contract.CorpusError, 'retired_record requires'):
            contract.render_record(retired, 'Synthetic retirement explanation.')
        for malformed in ('page-1', self.section_id.upper(), None):
            with self.subTest(value=malformed):
                with self.assertRaisesRegex(contract.CorpusError, 'redirect_id'):
                    contract.render_record({**retired, 'redirect_id': malformed}, 'Retired.')
        with self.assertRaisesRegex(contract.CorpusError, 'redirect_id'):
            contract.render_record({**self.paragraph, 'redirect_id': 'not-a-uuid'}, 'Prose.')

    def test_valid_retired_redirect_is_preserved_without_parser_on_read(self) -> None:
        retired = {**self.paragraph, 'type': 'retired_record', 'redirect_id': self.section_id}
        self.write_corpus([(self.section, '# Synthetic section'), (retired, 'Synthetic retirement explanation.')])
        contract.reindex(self.root)
        original_import = builtins.__import__

        def block_parser(name, *args, **kwargs):
            if name.startswith('markdown_it'):
                raise ImportError('Parser deliberately unavailable')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=block_parser):
            record = contract.load_index(self.root)[1]
        self.assertEqual(record['type'], 'retired_record')
        self.assertEqual(record['redirect_id'], self.section_id)
        self.assertEqual(record['id'], self.paragraph_id)

    def test_missing_redirect_and_self_redirect_rejected(self) -> None:
        for target, message in ((contract.new_id(), 'Missing redirect target'), (self.paragraph_id, 'self-redirect')):
            with self.subTest(target=target):
                retired = {**self.paragraph, 'type': 'retired_record', 'redirect_id': target}
                self.write_corpus([(self.section, '# Synthetic section'), (retired, 'Retired.')])
                with self.assertRaisesRegex(contract.CorpusError, message):
                    contract.reindex(self.root)

    def test_redirect_cycles_and_optional_redirect_targets_rejected(self) -> None:
        retired = {**self.paragraph, 'type': 'retired_record', 'redirect_id': self.note_id}
        second = self.record(self.note_id, 'paragraph', self.section_id, 2, redirect_id=self.paragraph_id)
        self.write_corpus([(self.section, '# Synthetic section'), (retired, 'Retired.'), (second, 'Second record.')])
        with self.assertRaisesRegex(contract.CorpusError, 'Redirect cycle'):
            contract.reindex(self.root)
        optional = {**self.paragraph, 'redirect_id': contract.new_id()}
        self.write_corpus([(self.section, '# Synthetic section'), (optional, 'Prose.')])
        with self.assertRaisesRegex(contract.CorpusError, 'Missing redirect target'):
            contract.reindex(self.root)

    def test_metadata_comment_delimiters_are_escaped(self) -> None:
        metadata = {**self.paragraph, "label": "A --> B -- C"}
        rendered = contract.render_record(metadata, "Prose.")
        self.assertNotIn("A -->", rendered)
        self.assertEqual(contract.parse_document(rendered)[0]["label"], metadata["label"])

    def test_malformed_ids_missing_anchor_and_delimiters_rejected(self) -> None:
        with self.assertRaises(contract.CorpusError):
            contract.render_record({**self.paragraph, "id": "p-123"}, "Prose.")
        rendered = contract.render_record(self.paragraph, "Prose.")
        with self.assertRaisesRegex(contract.CorpusError, "visible UUID anchor"):
            contract.parse_document(rendered.replace(f'<a id="{self.paragraph_id}"></a>\n', ""))
        with self.assertRaisesRegex(contract.CorpusError, "Missing closing"):
            contract.parse_document(rendered.replace("<!-- /sol -->", ""))
        with self.assertRaisesRegex(contract.CorpusError, "outside a SOL"):
            contract.parse_document("Unindexed text.\n" + rendered)

    def test_duplicate_json_keys_and_nonfinite_numbers_rejected(self) -> None:
        rendered = contract.render_record(self.paragraph, "Prose.")
        with self.assertRaisesRegex(contract.CorpusError, "Duplicate JSON key"):
            contract.parse_document(rendered.replace('"order":1', '"order":1,"order":2'))
        changed = copy.deepcopy(self.paragraph)
        changed["sources"][0]["bbox"][0] = float("nan")
        with self.assertRaises(contract.CorpusError):
            contract.render_record(changed, "Prose.")

    def test_stale_markdown_index_refused(self) -> None:
        contract.reindex(self.root)
        path = self.root / "sample.md"
        path.write_text(path.read_text(encoding="utf-8").replace("editable", "corrected"), encoding="utf-8")
        with self.assertRaisesRegex(contract.CorpusError, "Markdown or source fingerprint changed"):
            contract.load_index(self.root)
        contract.reindex(self.root)
        self.assertIn("corrected", contract.load_index(self.root)[1]["plain_text"])

    def test_stale_source_fingerprint_refused_without_reading_pdf(self) -> None:
        contract.reindex(self.root)
        self.manifest["source"]["sha256"] = "1" * 64
        (self.root / "corpus.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        with self.assertRaisesRegex(contract.CorpusError, "manifest changed"):
            contract.load_index(self.root)
        self.assertFalse((self.root / self.manifest["source"]["filename"]).exists())

    def test_manifest_file_list_removal_cannot_drop_content_silently(self) -> None:
        second = self.record(contract.new_id(), "paragraph", self.section_id, 2)
        self.manifest["documents"].append("second.md")
        self.write_corpus([(self.section, "# Synthetic section"), (self.paragraph, "Prose.")])
        self.write_corpus([(second, "A second document.")], "second.md")
        contract.reindex(self.root)
        self.manifest["documents"].remove("second.md")
        (self.root / "corpus.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        with self.assertRaisesRegex(contract.CorpusError, "missing from manifest"):
            contract.reindex(self.root)

    def test_path_traversal_and_symlinks_rejected(self) -> None:
        self.manifest["documents"] = ["../sample.md"]
        (self.root / "corpus.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        with self.assertRaisesRegex(contract.CorpusError, "Unsafe corpus path"):
            contract.read_manifest(self.root)
        self.manifest["documents"] = ["linked.md"]
        (self.root / "linked.md").symlink_to(self.root / "sample.md")
        (self.root / "corpus.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        with self.assertRaisesRegex(contract.CorpusError, "may not be symlinks"):
            contract.read_manifest(self.root)

    def test_index_tampering_detected(self) -> None:
        contract.reindex(self.root)
        index = self.root / "index.jsonl"
        index.write_text(index.read_text(encoding="utf-8").replace("editable", "tampered"), encoding="utf-8")
        with self.assertRaisesRegex(contract.CorpusError, "changed or incompletely written"):
            contract.load_index(self.root)

    def test_existing_index_load_needs_no_markdown_parser(self) -> None:
        contract.reindex(self.root)
        original_import = builtins.__import__

        def block_parser(name, *args, **kwargs):
            if name.startswith("markdown_it"):
                raise ImportError("Parser deliberately unavailable")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=block_parser):
            self.assertEqual(len(contract.load_index(self.root)), 2)
            with self.assertRaisesRegex(contract.CorpusError, "requires markdown-it-py"):
                contract.reindex(self.root)


if __name__ == "__main__":
    unittest.main()
