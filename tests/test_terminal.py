"""Research reader workflows with invented text and no PDF dependency."""
from __future__ import annotations

import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import sol


def synthetic_book():
    root = sol.Node('', 'Synthetic book', 7)
    being = sol.Node('BEING', 'Being', 7, parent=root)
    chapter = sol.Node('01-quality', 'Quality', 7, parent=being)
    intro = sol.Node('00-introduction.txt', 'Quality introduction', 7, parent=chapter)
    leaf = sol.Node('A-ground.txt', 'Ground leaf', 8, parent=chapter)
    essence = sol.Node('ESSENCE', 'Essence', 12, parent=root)
    other = sol.Node('01-reflection.txt', 'Reflection', 12, parent=essence)
    concept = sol.Node('CONCEPT', 'Concept', 15, parent=root)
    root.children = (being, essence, concept)
    being.children = (chapter,)
    chapter.children = (intro, leaf)
    essence.children = (other,)
    rows = [
        (intro, 'A common ground supports this invented introductory passage for reader experiments.', 'aaaaaaaa-0000-4000-8000-000000000001', 7),
        (leaf, 'Grounding and grounded examples introduce different words to a synthetic reader.', 'aaaaaaaa-0000-4000-8000-000000000002', 8),
        (leaf, 'The ground, when searched exactly, belongs to this next invented paragraph.', 'bbbbbbbb-0000-4000-8000-000000000003', 9),
        (other, 'A shared ground connects another doctrine in this invented collection of examples.', 'cccccccc-0000-4000-8000-000000000004', 12),
    ]
    passages = [sol.Passage(text, page + 73, page, node, sol.node_path(node), page + 73, page, identifier, node.title)
                for node, text, identifier, page in rows]
    return sol.Book(root, passages)


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.book = synthetic_book()
        self.first, self.second, self.third, self.fourth = self.book.passages

    def run_main(self, arguments, allow_source=True):
        stdout, stderr = io.StringIO(), io.StringIO()
        effect = None if allow_source else AssertionError('No source should load')
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                patch('sol.Path.cwd', return_value=Path('/synthetic-missing-directory')), \
                patch('sol.load_corpus_book', return_value=self.book, side_effect=effect), \
                patch('sol.load_book', side_effect=AssertionError('PDF extraction forbidden')):
            try:
                status = sol.main(arguments)
            except SystemExit as error:
                status = error.code
        return status, stdout.getvalue(), stderr.getvalue()

    def run_shell(self, commands):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), patch('builtins.input', side_effect=commands), \
                patch('sol.install_completion', return_value=lambda: None):
            status = sol.run_shell(self.book, 80)
        return status, stdout.getvalue()

    def test_search_casefolds_and_preserves_source_order(self):
        self.assertEqual(self.book.search('GROUND'), self.book.passages)

    def test_whole_word_search_avoids_derivatives_and_accepts_punctuation(self):
        self.assertEqual(self.book.search('ground', whole_word=True), [self.first, self.third, self.fourth])

    def test_search_scope_and_limit(self):
        self.assertEqual(self.book.search('ground', ('BEING',), whole_word=True, limit=1), [self.first])
        self.assertEqual(self.book.search('ground', ('ESSENCE',)), [self.fourth])

    def test_search_is_literal_not_regular_expression(self):
        self.assertEqual(self.book.search('ground.*'), [])

    def test_search_preview_centers_unicode_casefold_and_normalized_match(self):
        prefix = 'Earlier invented material precedes the result. ' * 12
        passage = replace(self.first, text=prefix + 'Straße and cafe\u0301 occur near the end.')
        self.book.passages[0] = passage
        for query, displayed in [('STRASSE', 'Straße'), ('CAFÉ', 'café')]:
            with self.subTest(query=query):
                matches = self.book.search(query)
                self.assertEqual(matches, [passage])
                rendered = sol.render_search_results(matches, query, 80)
                self.assertIn(displayed, rendered)
                self.assertNotIn('Earlier invented material', rendered)

    def test_whole_word_preview_uses_the_whole_word_match(self):
        self.book.passages[0] = replace(self.first, text=(
            'Underground passages precede the exact term. ' * 12 + 'The ground is here.'))
        matches = self.book.search('ground', whole_word=True)
        rendered = sol.render_search_results([matches[0]], 'ground', 80, whole_word=True)
        self.assertIn('The ground is here.', rendered)

    def test_path_wrap_preserves_component_boundaries(self):
        path = ('ESSENCE', 'i-essence-as-reflection-within', '1-shine', 'c-reflection')
        rendered = sol.fold_path(path, 44)
        self.assertEqual(rendered.replace('\n  ', ''), sol.display_path(path))
        self.assertTrue(all(len(line) <= 44 for line in rendered.splitlines()))
        self.assertIn('\n  1-shine/', rendered)

    def test_search_rejects_empty_query_and_invalid_limit(self):
        for query, limit in [('', 20), ('   ', 20), ('ground', 0), ('ground', -1)]:
            with self.subTest(query=query, limit=limit), self.assertRaises(ValueError):
                self.book.search(query, limit=limit)

    def test_lookup_full_id_and_unique_prefix(self):
        self.assertIs(self.book.find_passage(self.second.identifier), self.second)
        self.assertIs(self.book.find_passage('bbbbbbbb'), self.third)

    def test_lookup_rejects_ambiguous_missing_and_empty_identifiers(self):
        for identifier in ('aaaaaaaa', 'dddddddd', ''):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.book.find_passage(identifier)

    def test_lookup_follows_retired_identifier_chain(self):
        self.book.redirects.update({
            'eeeeeeee-0000-4000-8000-000000000005': 'ffffffff-0000-4000-8000-000000000006',
            'ffffffff-0000-4000-8000-000000000006': self.third.identifier,
        })
        self.assertIs(self.book.find_passage('eeeeeeee-0000-4000-8000-000000000005'), self.third)

    def test_current_requires_reading_cursor(self):
        with self.assertRaises(ValueError):
            sol.ReadingSession(self.book).current()

    def test_open_preserves_containing_selection(self):
        session = sol.ReadingSession(self.book)
        session.read(('BEING',), first=True)
        self.assertIs(session.open(self.third.identifier), self.third)
        self.assertEqual(session.path, ('BEING',))
        self.assertIs(session.current(), self.third)
        self.assertIs(session.move(-1), self.second)

    def test_open_outside_selection_switches_to_target_file(self):
        session = sol.ReadingSession(self.book)
        session.read(('BEING',), first=True)
        self.assertIs(session.open(self.fourth.identifier), self.fourth)
        self.assertEqual(session.path, self.fourth.path)
        self.assertEqual(session.cursor, 0)

    def test_context_keeps_cursor_and_neighbor_order(self):
        session = sol.ReadingSession(self.book)
        session.read(('BEING',), first=True)
        session.open(self.second.identifier)
        before = (session.path, session.cursor)
        rendered = sol.render_context(self.book, session.current(), 1, 80)
        self.assertLess(rendered.index(self.first.identifier), rendered.index(self.second.identifier))
        self.assertLess(rendered.index(self.second.identifier), rendered.index(self.third.identifier))
        self.assertNotIn(self.fourth.identifier, rendered)
        self.assertEqual((session.path, session.cursor), before)

    def test_zero_context_plain_contains_only_current_text(self):
        rendered = sol.render_context(self.book, self.second, 0, 80, plain=True)
        self.assertIn('Grounding and grounded', rendered)
        self.assertNotIn(self.second.identifier, rendered)
        self.assertNotIn(self.first.text, rendered)

    def test_tree_depth_and_ascii(self):
        shallow = sol.render_tree(self.book.root, depth=1, ascii_only=True)
        self.assertIn('BEING', shallow)
        self.assertNotIn('01-quality', shallow)
        self.assertTrue(shallow.isascii())
        self.assertNotIn('BEING', sol.render_tree(self.book.root, depth=0, ascii_only=True))
        self.assertIn('A-ground.txt', sol.render_tree(self.book.root, depth=3, ascii_only=True))

    def test_zero_depth_tree_normalizes_non_ascii_titles(self):
        self.book.root.title = 'A synthetic α outline'
        self.assertTrue(sol.render_tree(self.book.root, depth=0, ascii_only=True).isascii())

    def test_visual_help_ascii_and_three_stage_roadmap(self):
        rendered = sol.render_visual_help(self.book, width=80, depth=2)
        self.assertTrue(rendered.isascii())
        self.assertIn('SOL: SOL Organizes Logic', rendered)
        for word in ('SOL', 'BEING', 'ESSENCE', 'CONCEPT', '01-quality'):
            self.assertIn(word, rendered)

    def test_plain_passage_body_only_and_wraps(self):
        rendered = sol.render_passage(self.first, 44, plain=True)
        self.assertEqual(' '.join(rendered.split()), self.first.text)
        self.assertNotIn(self.first.identifier, rendered)
        self.assertTrue(all(len(line) <= 44 for line in rendered.splitlines()))

    def test_presentation_preserves_lists_and_schema_lines(self):
        passage = sol.Passage('An invented list follows.\n\n1. First item.\n2. Second item.\n\nSubject    Predicate\nA          B',
                              82, 9, self.third.node, self.third.path, 82, 9, self.third.identifier)
        rendered = sol.render_passage(passage, 80, plain=True)
        self.assertIn('\n1. First item.\n2. Second item.\n', rendered)
        self.assertIn('Subject    Predicate\nA          B', rendered)

    def test_image_caption_is_excluded_only_when_markdown_identifies_facsimile(self):
        caption = 'Source facsimile, printed page 9'
        record = {
            'id': self.third.identifier, 'type': 'paragraph', 'order': 1,
            'sources': [{'pdf_page': 82, 'printed_page': '9'}],
            'attribution': {'author': 'G. W. F. Hegel', 'role': 'main_text'},
            'reader_path': '/BEING/01-quality/A-ground.txt', 'reader_title': 'Ground leaf',
            'plain_text': 'Invented reader prose.\n' + caption,
            'markdown': 'Invented reader prose.\n\n![' + caption + '](../assets/source.png)',
        }
        with patch('sol_corpus_contract.load_index', return_value=[record]):
            book = sol.load_corpus_book(Path('/synthetic'))
        passage = book.passages[0]
        self.assertIn(caption, passage.text)
        self.assertNotIn(caption, sol.render_passage(passage, 80))
        self.assertEqual(book.search('facsimile'), [])
        self.assertEqual(book.search('Invented reader prose'), [passage])
        record['markdown'] = record['plain_text']
        with patch('sol_corpus_contract.load_index', return_value=[record]):
            ordinary = sol.load_corpus_book(Path('/synthetic')).passages[0]
        self.assertIn(caption, sol.render_passage(ordinary, 80))

    def test_shell_up_and_previous_directory(self):
        status, output = self.run_shell(['cd /being/quality', 'pwd', 'up', 'pwd', 'cd -', 'pwd', 'exit'])
        self.assertEqual(status, 0)
        paths = [line for line in output.splitlines() if line.startswith('/')]
        self.assertEqual(paths, ['/BEING/01-quality', '/BEING', '/BEING/01-quality'])
        self.assertNotIn('sol: ', output)

    def test_shell_search_then_open_number_sets_cursor(self):
        status, output = self.run_shell(['search ground /being --word --limit 1', 'open 1', 'context 0', 'exit'])
        self.assertEqual(status, 0)
        self.assertIn(self.first.identifier, output)
        self.assertNotIn(self.fourth.identifier, output)
        self.assertNotIn('sol: ', output)

    def test_shell_context_without_cursor_continues_after_error(self):
        status, output = self.run_shell(['context 1', 'pwd', 'exit'])
        self.assertEqual(status, 0)
        self.assertIn('sol: ', output)
        self.assertIn('\n/\n', output)

    def test_shell_where_reports_position_without_moving_cursor(self):
        status, output = self.run_shell(['first /being', 'where', 'next', 'where', 'exit'])
        self.assertEqual(status, 0)
        self.assertIn('Position 1 of 3 in /BEING', output)
        self.assertIn('Position 2 of 3 in /BEING', output)
        self.assertIn(self.second.identifier, output)
        self.assertNotIn('sol: ', output)

    def test_cli_search_json_scope_and_limit(self):
        status, output, error = self.run_main(['--corpus', 'synthetic', '--search', 'ground', '--within', '/being',
                                               '--word', '--limit', '1', '--json'])
        self.assertEqual(status, 0, error)
        encoded = json.dumps(json.loads(output))
        self.assertIn(self.first.identifier, encoded)
        self.assertNotIn(self.fourth.identifier, encoded)
        self.assertNotIn('\x1b', output)

    def test_cli_passage_unique_prefix_complete_id(self):
        status, output, error = self.run_main(['--corpus', 'synthetic', '--passage', 'bbbbbbbb', '--context', '0'])
        self.assertEqual(status, 0, error)
        self.assertIn(self.third.identifier, output)
        self.assertNotIn(self.first.identifier, output)

    def test_cli_json_context_crosses_subdivisions_in_book_order(self):
        status, output, error = self.run_main(['--corpus', 'synthetic', '--passage', 'bbbbbbbb',
                                               '--context', '1', '--json'])
        self.assertEqual(status, 0, error)
        records = json.loads(output)
        self.assertEqual([item['id'] for item in records],
                         [self.second.identifier, self.third.identifier, self.fourth.identifier])
        self.assertEqual(records[-1]['path'], '/ESSENCE/01-reflection.txt')
        self.assertEqual(records[-1]['printed_page'], 12)

    def test_cli_info_json_summarizes_selected_subtree(self):
        status, output, error = self.run_main(['--corpus', 'synthetic', '--info', '/being', '--json'])
        self.assertEqual(status, 0, error)
        info = json.loads(output)
        self.assertEqual(info['passages'], 3)
        self.assertEqual((info['printed_page'], info['end_printed_page']), (7, 9))
        self.assertEqual(info['path'], '/BEING')

    def test_cli_visual_help_without_source(self):
        status, output, error = self.run_main(['visual-help', '--depth', '1'], allow_source=False)
        self.assertEqual(status, 0, error)
        self.assertIn('SOL', output)
        self.assertTrue(output.isascii())

    def test_cli_version_without_source(self):
        status, output, error = self.run_main(['--version'], allow_source=False)
        self.assertEqual(status, 0, error)
        self.assertIn('sol', output.lower())

    def test_cli_rejects_invalid_numbers_and_inapplicable_flags(self):
        invalid = [
            ['--search', 'ground', '--limit', '0'], ['--structure', '--depth', '-1'],
            ['--passage', 'bbbbbbbb', '--context', '-1'], ['--word'],
            ['--shell', '--json'], ['unknown-command'],
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                status, _, error = self.run_main(['--corpus', 'synthetic', *arguments])
                self.assertEqual(status, 2)
                self.assertTrue(error)


if __name__ == '__main__':
    unittest.main()
