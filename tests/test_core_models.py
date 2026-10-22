"""Shared book primitives remain usable without a reader or terminal adapter."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from sol.core import models, paths, references
from sol.being.workspace import reader as workspace_reader


def invented_tree():
    root = models.Node("", "Invented book", 1)
    being = models.Node("BEING", "Being", 1, parent=root)
    quality = models.Node("i-quality", "Quality", 2, parent=being)
    leaf = models.Node("a-being.txt", "Being", 3, parent=quality)
    other = models.Node("b-nothing.txt", "Nothing", 4, parent=quality)
    root.children = (being,)
    being.children = (quality,)
    quality.children = (leaf, other)
    return root, being, quality, leaf, other


class CoreModelTests(unittest.TestCase):
    def test_model_parent_paths_and_facsimile_projection_are_unchanged(self):
        _, _, _, leaf, _ = invented_tree()
        self.assertEqual(models.node_path(leaf), ("BEING", "i-quality", "a-being.txt"))
        self.assertEqual(models.presentation_text("One line.\n[Figure 1]\nAnother line.",
                                                 ("[Figure 1]",)),
                         "One line.\n\nAnother line.")

    def test_shared_modules_do_not_import_interfaces_or_workspace(self):
        checkout = Path(__file__).resolve().parents[1]
        probe = (
            "import json, sys; "
            "import sol.core.models, sol.core.paths, sol.core.references; "
            "print(json.dumps(sorted(name for name in sys.modules "
            "if name == 'sol.reader' or name.startswith('sol.reader.') "
            "or name == 'sol.being.workspace' or name.startswith('sol.being.workspace.') "
            "or name == 'sol.terminal' or name.startswith('sol.terminal.'))))"
        )
        result = subprocess.run([sys.executable, "-B", "-c", probe], cwd=checkout,
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), [])


class CorePathTests(unittest.TestCase):
    def setUp(self):
        self.root, self.being, self.quality, self.leaf, self.other = invented_tree()

    def test_absolute_aliases_and_optional_text_suffix_keep_canonical_path(self):
        node, path = paths.resolve_path("/being/quality/being", (), self.root)
        self.assertIs(node, self.leaf)
        self.assertEqual(path, ("BEING", "i-quality", "a-being.txt"))
        self.assertEqual(paths.display_path(path), "/BEING/i-quality/a-being.txt")

    def test_relative_paths_and_parent_navigation(self):
        node, path = paths.resolve_path("../quality/nothing.txt", ("BEING", "i-quality"), self.root)
        self.assertIs(node, self.other)
        self.assertEqual(path, ("BEING", "i-quality", "b-nothing.txt"))

    def test_above_root_stays_at_supplied_root(self):
        node, path = paths.resolve_path("../../..", (), self.root)
        self.assertIs(node, self.root)
        self.assertEqual(path, ())
        self.assertEqual(paths.display_path(path), "/")

    def test_empty_path_uses_current_directory(self):
        node, path = paths.resolve_path(None, ("BEING", "i-quality"), self.root)
        self.assertIs(node, self.quality)
        self.assertEqual(path, ("BEING", "i-quality"))

    def test_root_must_be_explicit(self):
        with self.assertRaises(TypeError):
            paths.resolve_path("/", ())

    def test_exact_name_wins_over_ambiguous_alias(self):
        exact = models.Node("quality", "Exact", 5, parent=self.being)
        self.being.children += (exact,)
        self.assertIs(paths.child_by_name(self.being, "quality"), exact)
        with self.assertRaisesRegex(ValueError, "ambiguous name"):
            paths.child_by_name(self.being, "QUALITY")

    def test_file_cannot_be_traversed_as_a_directory(self):
        with self.assertRaisesRegex(ValueError, "not a directory"):
            paths.resolve_path("/being/quality/being/..", (), self.root)

    def test_missing_current_and_requested_paths_remain_errors(self):
        with self.assertRaisesRegex(ValueError, "current path no longer exists"):
            paths.resolve_path(None, ("missing",), self.root)
        with self.assertRaisesRegex(ValueError, "no such path"):
            paths.resolve_path("/missing", (), self.root)


class CoreReferenceTests(unittest.TestCase):
    def setUp(self):
        self.live_id = "aaaaaaaa-0000-4000-8000-000000000001"
        self.retired_id = "bbbbbbbb-0000-4000-8000-000000000001"
        self.book = SimpleNamespace(canonical_records={
            self.live_id: {"id": self.live_id, "type": "paragraph", "plain_text": "Invented text."},
            self.retired_id: {"id": self.retired_id, "type": "retired_record", "redirect_id": self.live_id},
        })

    def test_workspace_compatibility_preserves_resolver_and_class_identity(self):
        self.assertIs(workspace_reader.Reference, references.Reference)
        self.assertIs(workspace_reader.resolve_reference, references.resolve_reference)

    def test_exact_and_prefix_references_resolve_to_original_record(self):
        for identifier in (self.live_id, "  AAAAAAAA  "):
            with self.subTest(identifier=identifier):
                reference = references.resolve_reference(self.book, identifier)
                self.assertEqual(reference.requested_id, self.live_id)
                self.assertEqual(reference.target_id, self.live_id)
                self.assertEqual(reference.chain, (self.live_id,))
                self.assertIs(reference.record, self.book.canonical_records[self.live_id])

    def test_retirement_retains_requested_identifier_and_explicit_chain(self):
        reference = references.resolve_reference(self.book, self.retired_id)
        self.assertEqual(reference.requested_id, self.retired_id)
        self.assertEqual(reference.target_id, self.live_id)
        self.assertEqual(reference.chain, (self.retired_id, self.live_id))
        with self.assertRaises(FrozenInstanceError):
            reference.target_id = self.retired_id

    def test_unknown_empty_and_ambiguous_references_remain_errors(self):
        self.book.canonical_records["aaaaaaaa-0000-4000-8000-000000000002"] = {"type": "paragraph"}
        for identifier, message in (("", "record ID is required"),
                                    ("cccccccc", "unresolved canonical record"),
                                    ("aaaaaaaa", "ambiguous record ID")):
            with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, message):
                references.resolve_reference(self.book, identifier)

    def test_missing_and_cyclic_retirement_targets_remain_errors(self):
        retired = self.book.canonical_records[self.retired_id]
        for target in ("cccccccc-0000-4000-8000-000000000001", self.retired_id):
            with self.subTest(target=target):
                retired["redirect_id"] = target
                with self.assertRaisesRegex(ValueError, "invalid canonical retirement redirect"):
                    references.resolve_reference(self.book, self.retired_id)


if __name__ == "__main__":
    unittest.main()
