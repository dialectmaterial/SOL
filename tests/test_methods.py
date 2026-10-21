"""Methods describe the shipped CLI and render without any corpus or UI."""
from copy import deepcopy
import argparse
import shlex
import unittest

from sol.essence.cli import build_parser
from sol.essence.encyclopedia import load_catalog
from sol.essence.methods import load_methods, method_markdown


class MethodsTests(unittest.TestCase):
    def test_schema_and_encyclopedia_references(self):
        entries = load_methods()['entries']
        self.assertEqual(len({entry['id'] for entry in entries}), len(entries))
        topics = {entry['id'] for entry in load_catalog()['entries']}
        for entry in entries:
            with self.subTest(method=entry['id']):
                self.assertEqual(set(entry), {'id', 'title', 'summary', 'inputs',
                                             'settings', 'output', 'limits', 'cli', 'encyclopedia'})
                for key in ('id', 'title', 'summary', 'output', 'cli'):
                    self.assertIsInstance(entry[key], str)
                    self.assertTrue(entry[key].strip())
                for key in ('inputs', 'limits'):
                    self.assertIsInstance(entry[key], list)
                    self.assertTrue(entry[key])
                    self.assertTrue(all(isinstance(item, str) and item.strip() for item in entry[key]))
                self.assertTrue(entry['settings'])
                for setting in entry['settings']:
                    self.assertEqual(set(setting), {'name', 'meaning'})
                    self.assertTrue(all(isinstance(value, str) and value.strip() for value in setting.values()))
                if entry['encyclopedia'] is not None:
                    self.assertIn(entry['encyclopedia'], topics)

    def test_examples_parse_and_cover_every_analysis_operation(self):
        parser = build_parser()
        documented = set()
        for entry in load_methods()['entries']:
            command = shlex.split(entry['cli'])
            self.assertEqual(command[:2], ['sol', 'essence'])
            arguments = command[2:command.index('>')] if '>' in command else command[2:]
            with self.subTest(method=entry['id']):
                options = parser.parse_args(arguments)
                documented.add(options.action)
        actions = next(action for action in parser._actions
                       if isinstance(action, argparse._SubParsersAction))
        self.assertEqual(documented, set(actions.choices))

    def test_renderer_includes_all_content_without_mutation(self):
        catalog = load_methods()
        original = deepcopy(catalog)
        for entry in catalog['entries']:
            rendered = method_markdown(entry)
            with self.subTest(method=entry['id']):
                for key in ('title', 'summary', 'output', 'cli'):
                    self.assertIn(entry[key], rendered)
                for key in ('inputs', 'limits'):
                    for item in entry[key]:
                        self.assertIn(item, rendered)
                for setting in entry['settings']:
                    self.assertIn(setting['name'], rendered)
                    self.assertIn(setting['meaning'], rendered)
                self.assertIn('```sh\n' + entry['cli'] + '\n```', rendered)
                if entry['encyclopedia'] is None:
                    self.assertNotIn('### Encyclopedia', rendered)
                    self.assertNotIn('None', rendered)
                else:
                    self.assertIn(entry['encyclopedia'], rendered)
        self.assertEqual(catalog, original)

    def test_load_returns_fresh_data(self):
        catalog = load_methods()
        original = deepcopy(catalog)
        catalog['entries'][0]['settings'][0]['meaning'] = 'caller edit'
        catalog['entries'].clear()
        self.assertEqual(load_methods(), original)
