"""sol read's path choices: complete ordered canonical text, never arbitrary files."""
from pathlib import Path
import unittest
from unittest.mock import patch

from sol.core.files import resolve_file_path
from test_workspace_reader import invented_book, IDS


class ReadPathTests(unittest.TestCase):
    def setUp(self):
        self.book = invented_book()
        self.book.corpus_manifest["documents"] = ["sample.md", "editorial.md"]
        self.book.canonical_records[IDS[3]]["document"] = "editorial.md"

    def test_virtual_file_is_complete_and_ordered(self):
        selection = resolve_file_path(self.book, "/being/quality")
        self.assertEqual(selection["target_ids"], IDS[:2])
        self.assertEqual(selection["path"], "/BEING/01-quality.txt")
        self.assertEqual(selection["kind"], "reader_path")

    def test_relative_alias_paths_resolve_from_the_given_directory(self):
        self.assertEqual(resolve_file_path(self.book, "quality", ("BEING",))["path"], "/BEING/01-quality.txt")
        self.assertEqual(resolve_file_path(self.book, "../essence/ground", ("BEING",))["path"],
                         "/ESSENCE/01-ground.txt")

    def test_directory_scope_preserves_book_order(self):
        self.assertEqual(resolve_file_path(self.book, "/being")["target_ids"], IDS[:2])
        self.assertEqual(resolve_file_path(self.book, "/BEING")["target_ids"], IDS[:2])

    def test_canonical_markdown_accepts_relative_absolute_and_corpus_prefix(self):
        for path in ("sample.md", "/invented/corpus/sample.md", "corpus/sample.md", "./sample.md"):
            with self.subTest(path=path):
                selection = resolve_file_path(self.book, path)
                self.assertEqual(selection["target_ids"], IDS[:3])
                self.assertEqual(selection["path"], "/invented/corpus/sample.md")
                self.assertEqual(selection["kind"], "markdown_file")
        self.assertEqual(resolve_file_path(self.book, "editorial.md")["target_ids"], [IDS[3]])

    def test_outside_and_unlisted_markdown_are_refused_without_reading_files(self):
        for path in ("/tmp/arbitrary.md", "../arbitrary.md", "not-indexed.md", "/invented/corpus/unlisted.md"):
            with self.subTest(path=path), \
                    patch.object(Path, "read_text", side_effect=AssertionError("no arbitrary file read")), \
                    self.assertRaises(ValueError):
                resolve_file_path(self.book, path)
        with self.assertRaisesRegex(ValueError, "no such path"):
            resolve_file_path(self.book, "/missing.txt")


if __name__ == "__main__":
    unittest.main()
