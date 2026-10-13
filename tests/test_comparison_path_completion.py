"""Comparison selection suggestions use only the captured corpus catalog."""
from pathlib import Path
import shlex
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sol.reader.models import Node
from sol.terminal.prompt import CompletionCatalog


A = "aaaaaaaa-0000-4000-8000-000000000001"
CORPUS = Path("/known/sol corpus/local-corpus")


def book():
    root = Node("", "Logic", 1)
    being = Node("BEING", "Being", 1, parent=root)
    chapter = Node("01-quality", "Quality", 1, parent=being)
    existence = Node("a-being.txt", "Being", 1, parent=chapter)
    nothing = Node("b-nothing.txt", "Nothing", 2, parent=chapter)
    essence = Node("ESSENCE", "Essence", 3, parent=root)
    form = Node("form and essence.txt", "Form and essence", 3, parent=essence)
    root.children = being, essence
    being.children = (chapter,)
    chapter.children = existence, nothing
    essence.children = (form,)
    return SimpleNamespace(
        root=root, passages=[SimpleNamespace(identifier=A)],
        canonical_records={A: {}}, redirects={}, corpus_directory=CORPUS,
        corpus_manifest={"documents": [
            "hegel/being/1-being.md", "hegel/being/2-existence.md",
            "hegel/essence/form and essence.md", "notes/being.md",
        ]},
    )


class ComparisonPathCompletionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = CompletionCatalog(book(), workspace=True)
        self.catalog.comparisons = ("Being versus Nothing", "Ground inquiry", "Ground/Essence")

    def choices(self, text):
        return {shlex.split(value)[0] for value, _ in self.catalog.suggestions(text)}

    def test_bare_comparison_and_open_offer_virtual_paths(self):
        self.assertEqual(self.choices("compare /bei"), {"/BEING/"})
        self.assertEqual(self.choices("compare open /ess"), {"/ESSENCE/"})
        self.assertTrue({"save", "open", "BEING/", "hegel/"}.issubset(self.choices("compare ")))

    def test_virtual_aliases_and_relative_second_operand(self):
        self.catalog.cwd = ("BEING", "01-quality")
        self.assertEqual(self.choices("compare bei"), {"a-being.txt"})
        self.assertEqual(self.choices("compare a-being.txt not"), {"b-nothing.txt", "notes/"})
        self.assertEqual(self.choices("compare open a-being.txt b-n"), {"b-nothing.txt"})
        self.assertEqual(self.choices("compare /being/quality/b"), {"/being/quality/a-being.txt", "/being/quality/b-nothing.txt"})

    def test_relative_canonical_documents_are_walked_by_component(self):
        self.assertEqual(self.choices("compare heg"), {"hegel/"})
        self.assertEqual(self.choices("compare hegel/"), {"hegel/being/", "hegel/essence/"})
        self.assertEqual(self.choices("compare open hegel/being/1"), {"hegel/being/1-being.md"})
        self.assertEqual(self.choices("compare hegel/being/1-being.md hegel/being/2"),
                         {"hegel/being/2-existence.md"})

    def test_explicit_relative_document_prefix_is_preserved(self):
        self.assertEqual(self.choices("compare ./hegel/bei"), {"./hegel/being/"})
        self.assertEqual(self.choices("compare open ./hegel/being/1"), {"./hegel/being/1-being.md"})

    def test_absolute_manifest_document_path_and_quoted_space(self):
        text = 'compare open "' + str(CORPUS) + '/hegel/essence/fo'
        suggestions = self.catalog.suggestions(text)
        expected = str(CORPUS / "hegel/essence/form and essence.md")
        self.assertEqual({shlex.split(value)[0] for value, _ in suggestions}, {expected})
        replacement, start = suggestions[0]
        self.assertEqual(shlex.split(text[:len(text) + start] + replacement), ["compare", "open", expected])

    def test_quoted_virtual_path_replaces_only_current_operand(self):
        text = 'compare a-being.txt "/ESSENCE/form '
        suggestions = self.catalog.suggestions(text)
        self.assertEqual(len(suggestions), 1)
        replacement, start = suggestions[0]
        self.assertEqual(shlex.split(text[:len(text) + start] + replacement),
                         ["compare", "a-being.txt", "/ESSENCE/form and essence.txt"])

    def test_saved_name_candidates_have_their_own_prefix_filter(self):
        self.assertEqual(self.choices("compare open Gro"), {"Ground inquiry", "Ground/Essence"})
        self.assertNotIn("Being versus Nothing", self.choices("compare open /BE"))
        self.assertEqual(self.choices("compare show Bei"), {"Being versus Nothing"})

    def test_flags_and_free_question_text_do_not_offer_paths(self):
        self.assertEqual(self.choices("compare a-being.txt b-nothing.txt "), {"--question"})
        self.assertEqual(self.choices("compare open a-being.txt b-nothing.txt --q"), {"--question"})
        for text in ("compare a-being.txt b-nothing.txt --question ",
                     'compare open a-being.txt b-nothing.txt --question "hegel/',
                     'compare a-being.txt b-nothing.txt --question "Why?" ',
                     "compare /BEING /ESSENCE --unknown"):
            with self.subTest(text=text):
                self.assertEqual(self.choices(text), set())

    def test_save_still_suggests_uuid_targets(self):
        self.assertEqual(self.choices("compare save inquiry aaaaa"), {A})
        self.assertEqual(self.choices("compare save inquiry " + A + " --q"), {"--question"})
        self.assertEqual(self.choices("compare save inquiry " + A + ' --question "Why'), set())

    def test_direct_paths_available_without_workspace(self):
        catalog = CompletionCatalog(book())
        self.assertEqual({shlex.split(value)[0] for value, _ in catalog.suggestions("comp")}, {"compare"})
        self.assertEqual({shlex.split(value)[0] for value, _ in catalog.suggestions("compare /bei")}, {"/BEING/"})
        self.assertNotIn("save", {shlex.split(value)[0] for value, _ in catalog.suggestions("compare ")})

    def test_unlisted_and_outside_paths_do_not_discover_host_files(self):
        with patch("builtins.open", side_effect=AssertionError("No keypress file reads")), \
             patch.object(Path, "iterdir", side_effect=AssertionError("No keypress listing")), \
             patch.object(Path, "read_text", side_effect=AssertionError("No keypress file reads")), \
             patch.object(Path, "exists", side_effect=AssertionError("No keypress stat")), \
             patch.object(Path, "resolve", side_effect=AssertionError("No keypress resolution")):
            for text in ("compare /outside/", "compare hegel/being/unlisted", "compare /etc/pass"):
                self.assertEqual(self.choices(text), set())
            self.assertEqual(self.choices("compare hegel/being/1"), {"hegel/being/1-being.md"})

    def test_catalog_captures_document_list_at_creation(self):
        corpus = book()
        catalog = CompletionCatalog(corpus, True)
        corpus.corpus_manifest["documents"].append("private/unlisted.md")
        corpus.corpus_directory = Path("/different")
        self.assertEqual(catalog.suggestions("compare private/"), [])
        self.assertEqual(catalog.suggestions("compare /different/"), [])
        self.assertEqual({shlex.split(value)[0] for value, _ in catalog.suggestions("compare hegel/being/1")},
                         {"hegel/being/1-being.md"})


if __name__ == "__main__":
    unittest.main()
