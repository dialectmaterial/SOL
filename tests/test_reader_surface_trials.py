"""Named trials use supplied structure, not private UUIDs or prose guesses."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from experiments.reader_surfaces.trials import select_trial
from sol.core.models import Book, Node, Passage


def trial_book(opening_counts=(1, 1, 1), remark_count=2):
    """Invented graph mirrors edition headings, never its paragraphs or IDs."""
    root = Node("", "Invented trial edition", 1)
    nodes = {(): root}
    records, named, passages = {}, {}, []
    next_id = 1

    def identifier():
        nonlocal next_id
        value = f"dddddddd-0000-4000-8000-{next_id:012d}"
        next_id += 1
        return value

    def ensure_node(path, title):
        for length in range(1, len(path) + 1):
            prefix = path[:length]
            if prefix not in nodes:
                node = Node(prefix[-1], title if length == len(path) else prefix[-1],
                            1, parent=nodes[prefix[:-1]])
                nodes[prefix] = node
                nodes[prefix[:-1]].children += (node,)
        return nodes[path]

    def section(key, parent, title, label, path):
        rid = identifier()
        record = {"id": rid, "parent_id": None if parent is None else named[parent]["id"],
                  "type": "section", "order": len(records), "title": title,
                  "reader_title": title, "label": label, "reader_path": path,
                  "plain_text": title, "markdown": title,
                  "sources": [{"pdf_page": 110, "printed_page": "10"}]}
        records[rid] = named[key] = record
        return record

    def prose(key, parent, count=1, *, path=None):
        owner = named[parent]
        path = owner["reader_path"] if path is None else path
        if not path.endswith(".txt"):
            path += "/00-introduction.txt"
        parts = tuple(path.strip("/").split("/"))
        node = ensure_node(parts, owner["title"])
        for index in range(count):
            rid = identifier()
            text = f"Invented {key} paragraph {index + 1} keeps its own exact source."
            page = 10 + len(passages)
            record = {"id": rid, "parent_id": owner["id"], "type": "paragraph",
                      "order": len(records), "plain_text": text, "markdown": text,
                      "heading": owner["title"], "reader_title": owner["title"],
                      "reader_path": path, "note_ids": [],
                      "content_sha256": sha256(text.encode()).hexdigest(),
                      "attribution": {"author": "G. W. F. Hegel", "role": "main_text", "status": "original"},
                      "sources": [{"pdf_page": page + 100, "printed_page": str(page)}]}
            records[rid] = record
            named[f"{key}-{index}"] = record
            passages.append(Passage(text, page + 100, page, node, parts,
                                    page + 100, page, rid, owner["title"]))

    section("edition", None, "The Science of Logic", "", "/")
    section("objective", "edition", "The Objective Logic", "One", "/BEING")
    section("doctrine", "objective", "The Doctrine of Being", "One", "/BEING")
    quality = "/BEING/i-determinateness-quality"
    chapter = quality + "/1-being"
    becoming = chapter + "/c-becoming"
    unity = becoming + "/1-unity-of-being-and-nothing"
    section("quality", "doctrine", "Determinateness (Quality)", "I", quality)
    prose("before", "quality")
    section("chapter", "quality", "Being", "1", chapter)
    section("a", "chapter", "Being", "A", chapter + "/a-being.txt")
    prose("a", "a", opening_counts[0])
    section("b", "chapter", "Nothing", "B", chapter + "/b-nothing.txt")
    prose("b", "b", opening_counts[1])
    section("c", "chapter", "Becoming", "C", becoming)
    section("unity", "c", "Unity of being and nothing", "1", unity)
    prose("unity", "unity", opening_counts[2])
    section("remark1", "unity", "Remark 1", "1", unity + "/1-remark-1.txt")
    prose("remark1", "remark1", remark_count)
    if remark_count:
        note_id = identifier()
        note = {"id": note_id, "parent_id": named["remark1-0"]["id"], "type": "note",
                "order": len(records), "plain_text": "An invented attributed note.",
                "markdown": "An invented attributed note.",
                "attribution": {"author": "Invented translator", "role": "footnote", "status": "editorial"},
                "sources": [{"pdf_page": 114, "printed_page": "14"}]}
        records[note_id] = named["note"] = note
        named["remark1-0"]["note_ids"].append(note_id)
    section("remark2", "unity", "Remark 2", "2", unity + "/2-remark-2.txt")
    prose("remark2", "remark2")
    section("moments", "c", "The moments of becoming", "2", becoming + "/2-the-moments-of-becoming.txt")
    prose("moments", "moments")
    section("sublation", "c", "Sublation of becoming", "3", becoming + "/3-sublation-of-becoming")
    prose("sublation", "sublation")
    section("final-remark", "sublation", "Remark", "", becoming + "/3-sublation-of-becoming/remark.txt")
    prose("final-remark", "final-remark")
    section("next-chapter", "quality", "Existence", "2", quality + "/2-existence")
    prose("after", "next-chapter")
    return Book(root, passages, canonical_records=records), named


class ReaderSurfaceTrialTests(unittest.TestCase):
    def test_opening_is_the_three_adjacent_supplied_groups_before_first_remark(self):
        book, named = trial_book()
        trial = select_trial(book, "opening")
        self.assertEqual([p.identifier for p in trial.sample.passages],
                         [named[key]["id"] for key in ("a-0", "b-0", "unity-0")])
        self.assertIs(trial.sample.book, book)
        self.assertEqual(trial.sample.actions.snapshot().scope, ())
        self.assertIs(trial.sample.actions.snapshot().current, book.passages[1])
        self.assertIsNone(trial.sample.actions.workspace_reader)

    def test_counts_are_derived_and_paragraphs_are_never_combined_or_assigned_ids(self):
        book, named = trial_book(opening_counts=(2, 3, 2))
        trial = select_trial(book, "opening")
        expected = book.passages[1:8]
        self.assertEqual(len(trial.sample.passages), 7)
        for actual, original in zip(trial.sample.passages, expected):
            self.assertIs(actual, original)
            self.assertEqual(actual.text, book.canonical_records[actual.identifier]["plain_text"])

    def test_beginning_includes_all_remarks_but_neither_preface_nor_next_chapter(self):
        book, named = trial_book()
        trial = select_trial(book, "beginning")
        self.assertEqual(trial.sample.passages, tuple(book.passages[1:-1]))
        identifiers = {p.identifier for p in trial.sample.passages}
        self.assertIn(named["remark1-0"]["id"], identifiers)
        self.assertIn(named["final-remark-0"]["id"], identifiers)
        self.assertNotIn(named["before-0"]["id"], identifiers)
        self.assertNotIn(named["after-0"]["id"], identifiers)
        self.assertNotIn(named["note"]["id"], identifiers)

    def test_metadata_is_safe_inventory_not_a_copy_of_canonical_prose(self):
        book, named = trial_book()
        for preset in ("opening", "beginning"):
            with self.subTest(preset=preset):
                trial = select_trial(book, preset)
                self.assertIsInstance(trial.metadata, dict)
                info = trial.metadata
                self.assertEqual(info["name"], preset)
                self.assertEqual(info["source_section_id"], named["chapter"]["id"])
                self.assertEqual(info["start"], trial.sample.passages[0].identifier)
                self.assertEqual(info["end"], trial.sample.passages[-1].identifier)
                self.assertEqual(info["sample_passages"], len(trial.sample.passages))
                self.assertEqual(info["printed_pages"], [trial.sample.passages[0].printed_page,
                                                        trial.sample.passages[-1].end_printed_page])
                self.assertEqual(info["pdf_pages"], [trial.sample.passages[0].pdf_page,
                                                    trial.sample.passages[-1].end_pdf_page])
                self.assertEqual(info["linked_notes"], 0 if preset == "opening" else 1)
                self.assertEqual(info["includes_remarks"], preset == "beginning")
                self.assertIsNone(info["generation"])
                encoded = json.dumps(trial.metadata, ensure_ascii=False)
                for passage in book.passages:
                    self.assertNotIn(passage.text, encoded)
                self.assertNotIn(named["note"]["plain_text"], encoded)

    def test_inventory_is_a_defensive_copy_not_a_mutable_selection_control(self):
        book, _ = trial_book()
        trial = select_trial(book, "opening")
        before = deepcopy(trial.metadata)
        exposed = trial.metadata
        exposed["name"] = "different"
        exposed["printed_pages"][0] = 99999
        self.assertEqual(trial.metadata, before)

    def test_trial_selection_does_not_discover_pdf_or_open_files(self):
        book, _ = trial_book()
        with patch("builtins.open", side_effect=AssertionError("no file discovery")), \
                patch("pathlib.Path.open", side_effect=AssertionError("no source-file opening")):
            trial = select_trial(book, "beginning")
        self.assertEqual(trial.sample.passages, tuple(book.passages[1:-1]))

    def test_selector_does_not_mutate_corpus_graph_book_order_or_other_reader(self):
        from sol.reader.actions import ReaderActions
        book, named = trial_book()
        prior = ReaderActions(book)
        prior.read(path=(), first=True)
        prior.set_cursor(5)
        before_state = prior.snapshot()
        before_records = deepcopy(book.canonical_records)
        before_passages = tuple(book.passages)
        select_trial(book, "opening")
        select_trial(book, "beginning")
        self.assertEqual(book.canonical_records, before_records)
        self.assertEqual(tuple(book.passages), before_passages)
        self.assertEqual(prior.snapshot(), before_state)
        self.assertIsNone(book.corpus_directory)
        self.assertIsNone(book.corpus_snapshot)

    def test_selected_text_uses_the_existing_source_bound_action_model(self):
        book, named = trial_book()
        trial = select_trial(book, "opening")
        selected = trial.sample.actions.select_span(2, 12)
        self.assertEqual(selected.target_id, named["a-0"]["id"])
        self.assertEqual(selected.requested_id, named["a-0"]["id"])
        self.assertEqual(selected.text, named["a-0"]["plain_text"][2:12])
        self.assertEqual((selected.start, selected.end), (2, 12))
        self.assertEqual(trial.sample.actions.snapshot().scope, ())

    def test_review_count_comes_from_selected_passages_not_the_whole_corpus(self):
        book, named = trial_book()
        index = next(i for i, passage in enumerate(book.passages)
                     if passage.identifier == named["remark1-0"]["id"])
        book.passages[index] = replace(book.passages[index], transcription_status="needs_visual_review")
        named["remark1-0"]["transcription_status"] = "needs_visual_review"
        self.assertEqual(select_trial(book, "opening").metadata["source_review_passages"], 0)
        self.assertEqual(select_trial(book, "beginning").metadata["source_review_passages"], 1)

    def test_unknown_or_mistyped_trial_names_are_refused_without_fallback(self):
        book, _ = trial_book()
        for name in ("missing", "", "Being", "OPENING", None, True, 1):
            with self.subTest(name=name), self.assertRaises(ValueError):
                select_trial(book, name)

    def test_unverified_structure_is_not_guessed_from_paragraph_heading_or_text(self):
        book, _ = trial_book()
        book.canonical_records = {}
        with self.assertRaises(ValueError):
            select_trial(book, "opening")

    def test_missing_required_section_is_refused(self):
        for key in ("doctrine", "quality", "chapter", "a", "b", "c", "unity", "remark1", "next-chapter"):
            for preset in ("opening", "beginning"):
                with self.subTest(section=key, preset=preset):
                    book, named = trial_book()
                    del book.canonical_records[named[key]["id"]]
                    with self.assertRaises(ValueError):
                        select_trial(book, preset)

    def test_duplicate_matching_section_is_refused_even_if_virtual_path_matches(self):
        for key in ("doctrine", "quality", "chapter", "a", "b", "c", "unity", "remark1", "next-chapter"):
            with self.subTest(section=key):
                book, named = trial_book()
                duplicate = deepcopy(named[key])
                duplicate["id"] = "dddddddd-0000-4000-8000-999999999999"
                book.canonical_records[duplicate["id"]] = duplicate
                with self.assertRaises(ValueError):
                    select_trial(book, "opening")

    def test_same_named_section_under_wrong_parent_is_not_an_alternative_match(self):
        for key, parent in (("a", "quality"), ("b", "a"), ("c", "unity"),
                            ("unity", "chapter"), ("remark1", "c"), ("next-chapter", "c")):
            with self.subTest(section=key):
                book, named = trial_book()
                named[key]["parent_id"] = named[parent]["id"]
                with self.assertRaises(ValueError):
                    select_trial(book, "opening")

    def test_changed_labels_or_titles_are_refused_instead_of_fuzzy_matching(self):
        for key, field, value in (("a", "label", "a"), ("b", "title", "Not quite Nothing"),
                                  ("c", "title", "becoming"), ("unity", "label", "i"),
                                  ("remark1", "title", "First remark")):
            with self.subTest(section=key, field=field):
                book, named = trial_book()
                named[key][field] = value
                with self.assertRaises(ValueError):
                    select_trial(book, "opening")

    def test_each_opening_group_must_contain_actual_reader_passages(self):
        for counts in ((0, 1, 1), (1, 0, 1), (1, 1, 0)):
            with self.subTest(counts=counts):
                book, _ = trial_book(opening_counts=counts)
                with self.assertRaises(ValueError):
                    select_trial(book, "opening")

    def test_reordered_book_passages_are_not_silently_resorted(self):
        book, _ = trial_book()
        book.passages[1], book.passages[2] = book.passages[2], book.passages[1]
        with self.assertRaises(ValueError):
            select_trial(book, "opening")

    def test_reordered_section_boundaries_are_refused(self):
        book, named = trial_book()
        named["a"]["order"], named["b"]["order"] = named["b"]["order"], named["a"]["order"]
        with self.assertRaises(ValueError):
            select_trial(book, "opening")

    def test_duplicate_source_orders_cannot_define_a_chapter_sequence(self):
        book, named = trial_book(opening_counts=(2, 1, 1))
        named["a-1"]["order"] = named["a-0"]["order"]
        with self.assertRaises(ValueError):
            select_trial(book, "beginning")

    def test_foreign_paragraph_inside_trial_cannot_be_skipped_to_form_a_splice(self):
        book, named = trial_book()
        foreign = book.passages.pop(0)
        # Keep the explicit order consistent with this surprising interleaving.
        for record in book.canonical_records.values():
            record["order"] *= 2
        named["before-0"]["order"] = named["a-0"]["order"] + 1
        book.passages.insert(1, foreign)
        with self.assertRaises(ValueError):
            select_trial(book, "opening")

    def test_missing_reader_projection_is_refused_not_silently_omitted(self):
        book, _ = trial_book(opening_counts=(2, 1, 1))
        book.passages.pop(2)
        with self.assertRaises(ValueError):
            select_trial(book, "opening")

    def test_detached_passage_text_disagrees_with_the_canonical_record(self):
        book, _ = trial_book()
        book.passages[1] = replace(book.passages[1], text="Changed presentation cannot override source text.")
        with self.assertRaises(ValueError):
            select_trial(book, "opening")

    def test_existing_budget_is_enforced_without_truncating_a_complete_trial(self):
        for preset, kwargs in (("opening", {"opening_counts": (22, 22, 21)}),
                               ("beginning", {"remark_count": 65})):
            with self.subTest(preset=preset):
                book, _ = trial_book(**kwargs)
                with self.assertRaises(ValueError):
                    select_trial(book, preset)

    def test_full_existing_budget_is_allowed_for_the_selected_preset(self):
        for preset, kwargs in (("opening", {"opening_counts": (22, 21, 21)}),
                               ("beginning", {"remark_count": 57})):
            with self.subTest(preset=preset):
                book, _ = trial_book(**kwargs)
                self.assertEqual(len(select_trial(book, preset).sample.passages), 64)


if __name__ == "__main__":
    unittest.main()
