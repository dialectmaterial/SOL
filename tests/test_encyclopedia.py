"""The shipped reading list and its keyboard browser, using no real corpus."""
from copy import deepcopy
from datetime import date
import unittest

from fixtures_async import UIEventLoop

from sol.essence.encyclopedia import entry_markdown, load_catalog
from sol.interchange.essence import textual_available


class CatalogTests(unittest.TestCase):
    def test_every_entry_has_a_short_attributed_quote_and_further_reading(self):
        catalog = load_catalog()
        self.assertEqual(catalog['attribution'], 'Wikipedia contributors')
        self.assertEqual(catalog['license'], 'CC BY-SA 4.0')
        self.assertEqual(catalog['license_url'], 'https://creativecommons.org/licenses/by-sa/4.0/')
        date.fromisoformat(catalog['accessed'])
        entries = catalog['entries']
        self.assertEqual(len({e['id'] for e in entries}), len(entries))
        self.assertEqual({e['id'] for e in entries}, {
            'word-counts', 'tokenization', 'frequency-comparison', 'sentences',
            'concordance', 'prose', 'tf-idf', 'word-vectors', 'transformers'})
        for entry in entries:
            with self.subTest(entry=entry['id']):
                self.assertTrue(0 < len(entry['quote'].split()) <= 25)
                self.assertTrue(entry['article_url'].startswith('https://en.wikipedia.org/wiki/'))
                self.assertIn(len(entry['further']), (1, 2))
                for link in entry['further']:
                    self.assertTrue(link['title'])
                    self.assertTrue(link['url'].startswith('https://'))
                rendered = entry_markdown(catalog, entry)
                for value in (entry['quote'], entry['article_title'], entry['article_url'],
                              entry['essence'], catalog['accessed'], catalog['attribution'],
                              catalog['license'], catalog['license_url'], '?action=history'):
                    self.assertIn(value, rendered)
                for link in entry['further']:
                    self.assertIn(link['url'], rendered)

    def test_mid_sentence_quotes_show_an_editorial_ellipsis_without_mutating_data(self):
        catalog = load_catalog()
        original = deepcopy(catalog)
        fragments = {'sentences', 'concordance', 'prose', 'transformers'}
        for entry in catalog['entries']:
            with self.subTest(entry=entry['id']):
                self.assertEqual(entry.get('quote_starts_mid_sentence', False),
                                 entry['id'] in fragments)
                leading = '… ' if entry['id'] in fragments else ''
                self.assertIn(f"> {leading}{entry['quote']}\n", entry_markdown(catalog, entry))
        self.assertEqual(catalog, original)

    def test_omission_marker_uses_source_metadata_rather_than_capitalization(self):
        catalog = load_catalog()
        entry = dict(catalog['entries'][0], quote='SOL appears mid-sentence.',
                     quote_starts_mid_sentence=True)
        self.assertIn('> … SOL appears mid-sentence.\n', entry_markdown(catalog, entry))
        self.assertEqual(entry['quote'], 'SOL appears mid-sentence.')

    def test_reading_topics_do_not_claim_runnable_adapters(self):
        for entry in load_catalog()['entries']:
            if entry['id'] in {'word-vectors', 'transformers'}:
                self.assertIn('Reading topic;', entry['essence'])
                self.assertIn('no ', entry['essence'])
            else:
                self.assertTrue(entry['essence'].startswith('Runs in ESSENCE:'))


class GenealogyTests(unittest.TestCase):
    def test_every_entry_appears_once_and_every_date_has_a_source(self):
        from sol.essence.encyclopedia import genealogy_rows
        catalog = load_catalog()
        rows = genealogy_rows(catalog)
        self.assertCountEqual([row['entry'] for row in rows if row['entry']],
                              [entry['id'] for entry in catalog['entries']])
        for row in rows:
            if row['year']:
                self.assertTrue(row['source'].startswith('https://en.wikipedia.org/wiki/'), row)
        runs = {row['entry']: row['runs'] for row in rows if row['entry']}
        self.assertFalse(runs['word-vectors'] or runs['transformers'])
        self.assertTrue(runs['tf-idf'] and runs['word-counts'])

    def test_lines_of_descent_are_drawn_from_the_parents(self):
        from sol.essence.encyclopedia import genealogy_rows
        drawn = {row['label']: (row['year'], row['prefix']) for row in genealogy_rows(load_catalog())}
        self.assertEqual(drawn['Concordance'], ('1230', ''))
        self.assertEqual(drawn['TF-IDF'], ('1972', '│  └─ '))
        self.assertEqual(drawn['Transformers'], ('2017', '   └─ '))
        nodes = load_catalog()['genealogy']['nodes']
        ids = {node['id'] for node in nodes}
        self.assertTrue(all(node['parent'] is None or node['parent'] in ids for node in nodes))


@unittest.skipUnless(textual_available(), 'the essence extra is not installed')
class EncyclopediaBrowserTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def test_browse_read_scroll_and_return_at_terminal_sizes(self):
        from textual.widgets import Markdown, OptionList
        from sol.essence.tui.app import EssenceApp
        from test_essence_tui import context

        for size in ((60, 24), (120, 40)):
            with self.subTest(size=size):
                app = EssenceApp(context())
                async with app.run_test(size=size) as pilot:
                    await pilot.press('M')
                    await pilot.pause()
                    ref = app.screen
                    listing = ref.query_one('#encyclopedia-list', OptionList)
                    self.assertIs(app.focused, listing)
                    # The encyclopedia opens on its genealogy, then lists the entries.
                    self.assertEqual(listing.option_count, 10)
                    self.assertTrue(ref.query_one('#genealogy-map').display)
                    await pilot.press('down')
                    self.assertFalse(ref.query_one('#genealogy-map').display)
                    for entry in app.catalog['entries']:
                        await pilot.pause()
                        rendered = ref.query_one('#encyclopedia-entry', Markdown).source
                        self.assertIn(entry['quote'], rendered)
                        self.assertIn(entry['article_url'], rendered)
                        if entry is not app.catalog['entries'][-1]:
                            await pilot.press('down')
                    await pilot.press('enter', 'pagedown')
                    detail = ref.query_one('#encyclopedia-detail')
                    self.assertIs(app.focused, detail)
                    if size == (60, 24):
                        self.assertGreater(detail.scroll_y, 0)
                    await pilot.press('escape')
                    self.assertIs(app.focused, listing)
                    await pilot.press('2', '1')
                    self.assertIs(app.focused, listing)
                    self.assertEqual(listing.highlighted, 9)
                    await pilot.press('q')


@unittest.skipUnless(textual_available(), 'the essence extra is not installed')
class GenealogyBrowserTests(UIEventLoop, unittest.IsolatedAsyncioTestCase):
    async def test_enter_moves_into_the_map_and_opens_a_method(self):
        from textual.widgets import Markdown, OptionList
        from sol.essence.tui.app import EssenceApp
        from test_essence_tui import context
        app = EssenceApp(context())
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.press('M')
            await pilot.pause()
            await pilot.press('enter')
            app = app.screen  # The catalogs are a screen over the study.
            atlas = app.query_one('#genealogy-map', OptionList)
            self.assertIs(app.focused, atlas)
            # Ancestors without an entry are skipped; the first stop opens an entry.
            labels = [str(atlas.get_option_at_index(i).prompt) for i in range(atlas.option_count)]
            tfidf = next(i for i, label in enumerate(labels) if 'TF-IDF' in label)
            atlas.highlighted = tfidf
            await pilot.press('enter')
            await pilot.pause()
            ids = [entry['id'] for entry in app.app.catalog['entries']]
            self.assertEqual(app.query_one('#encyclopedia-list', OptionList).highlighted, ids.index('tf-idf') + 1)
            self.assertIn('TF-IDF', app.query_one('#encyclopedia-entry', Markdown).source)
            self.assertFalse(atlas.display)
            await pilot.press('escape')
            self.assertIs(app.focused, app.query_one('#encyclopedia-list'))
