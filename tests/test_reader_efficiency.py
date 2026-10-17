"""Bounded reader operations preserve mutable-book semantics."""
from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

from sol.core import models
from sol.reader import app


def invented_book():
    root = models.Node('', 'Invented book', 7)
    leaf = models.Node('example.txt', 'Example', 7, parent=root)
    root.children = (leaf,)
    passages = [
        models.Passage('An invented ground supports this paragraph.', 80 + index,
                       7 + index, leaf, ('example.txt',), 80 + index, 7 + index,
                       f'aaaaaaaa-0000-4000-8000-{index + 1:012d}')
        for index in range(6)
    ]
    return models.Book(root, passages)


class TrackedIdentifier(str):
    prefix_checks = 0

    def casefold(self):
        return self

    def startswith(self, value, *arguments):
        type(self).prefix_checks += 1
        return super().startswith(value, *arguments)


class ReaderEfficiencyTests(unittest.TestCase):
    def test_search_stops_projecting_after_requested_number_of_matches(self):
        book = invented_book()
        with patch.object(models, 'presentation_text', wraps=models.presentation_text) as project:
            self.assertEqual(book.search('ground', limit=2), book.passages[:2])
        self.assertEqual(project.call_count, 2)

    def test_search_scans_nonmatches_and_preserves_order(self):
        book = invented_book()
        book.passages[0] = replace(book.passages[0], text='Another invented subject.')
        with patch.object(models, 'presentation_text', wraps=models.presentation_text) as project:
            self.assertEqual(book.search('ground', limit=2), book.passages[1:3])
        self.assertEqual(project.call_count, 3)

    def test_search_has_no_stale_cache_after_passage_replacement(self):
        book = invented_book()
        self.assertEqual(book.search('ground', limit=1), book.passages[:1])
        book.passages[0] = replace(book.passages[0], text='A different invented passage.')
        self.assertEqual(book.search('ground', limit=1), book.passages[1:2])

    def test_exact_id_and_exact_redirect_skip_prefix_scan(self):
        book = invented_book()
        book.passages = [replace(row, identifier=TrackedIdentifier(row.identifier))
                         for row in book.passages]
        retired = TrackedIdentifier('ffffffff-0000-4000-8000-000000000001')
        book.redirects[retired] = book.passages[0].identifier
        TrackedIdentifier.prefix_checks = 0
        self.assertIs(book.find_passage(str(book.passages[0].identifier)), book.passages[0])
        self.assertIs(book.find_passage(str(retired)), book.passages[0])
        self.assertEqual(TrackedIdentifier.prefix_checks, 0)

    def test_ambiguous_prefix_still_checks_candidates(self):
        book = invented_book()
        book.passages = [replace(row, identifier=TrackedIdentifier(row.identifier))
                         for row in book.passages]
        TrackedIdentifier.prefix_checks = 0
        with self.assertRaisesRegex(ValueError, 'ambiguous identifier'):
            book.find_passage('aaaaaaaa')
        self.assertEqual(TrackedIdentifier.prefix_checks, len(book.passages))

    def test_lookup_has_no_stale_cache_after_redirect_change(self):
        book = invented_book()
        retired = 'ffffffff-0000-4000-8000-000000000001'
        book.redirects[retired] = book.passages[0].identifier
        self.assertIs(book.find_passage(retired), book.passages[0])
        book.redirects[retired] = book.passages[1].identifier
        self.assertIs(book.find_passage(retired), book.passages[1])

    def test_first_read_does_not_compute_random_prose_eligibility(self):
        book = invented_book()
        book.passages[0] = replace(book.passages[0], text='x', kind='formula', random_eligible=False)
        session = app.ReadingSession(book)
        with patch.object(app.re, 'findall', side_effect=AssertionError('No random token scan')), \
                patch('sol.reader.actions.random.choice', side_effect=AssertionError('No random choice')):
            self.assertIs(session.read(('example.txt',), first=True), book.passages[0])
        self.assertEqual(session.path, ('example.txt',))
        self.assertEqual(session.cursor, 0)

    def test_empty_first_selection_remains_an_error(self):
        with self.assertRaisesRegex(ValueError, 'no prose'):
            app.ReadingSession(invented_book()).read(('missing.txt',), first=True)

if __name__ == '__main__':
    unittest.main()
