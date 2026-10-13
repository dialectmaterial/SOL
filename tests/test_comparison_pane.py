"""Read-only comparison presentation and owned terminal lifecycle."""
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch

from sol.terminal import kitty
from sol.terminal.comparison import ComparisonView, card_text, cell_width, key_action, wrap_text


IDS = [f'aaaaaaaa-0000-4000-8000-{i:012d}' for i in range(1, 5)]
SESSION = {'SOL_KITTY_SESSION': '1', 'KITTY_RC_PASSWORD': 'test-token', 'KITTY_WINDOW_ID': '19'}


def snapshot():
    records = []
    for i, identifier in enumerate(IDS):
        note = {'id': f'bbbbbbbb-0000-4000-8000-{i:012d}', 'actor': 'Ada',
                'body': f'Personal observation {i + 1}.', 'target_id': identifier,
                'revision': 1, 'status': 'matching', 'status_reason': 'Text digest matches.'}
        records.append({'position': i, 'requested_id': identifier, 'target_id': identifier,
                        'state': 'live', 'title': f'Argument {i + 1}', 'path': f'/logic/argument-{i+1}',
                        'plain_text': f'Passage body {i + 1} presents an invented argument. ' * 8,
                        'attribution': {'author': 'Invented philosopher', 'role': 'main_text'},
                        'sources': [{'pdf_page': i + 8, 'printed_page': str(i + 1)}],
                        'notes': [note], 'transcription_status': 'needs_visual_review' if i == 1 else None})
    return {'version': 1, 'kind': 'comparison', 'captured_at': '2026-10-13T08:00:00Z',
            'comparison': {'name': 'study', 'question': 'How do these arguments differ?', 'actor': 'Ada'},
            'workspace': {'name': 'study'}, 'corpus': {'generation': {'state': 'current'}},
            'records': records}


def file_snapshot(with_notes=False):
    value = snapshot()
    value['comparison'] = {'name': 'File comparison', 'question': '', 'actor': ''}
    value['workspace']['name'] = ''
    value['refresh_command'] = 'compare open'
    value['reopen_command'] = "compare open '/Logic/Being and Becoming.md' '/Logic/Form and Essence.md'"
    groups = []
    for i, title in enumerate(('Being and Becoming', 'Form and Essence')):
        members = deepcopy(value['records'][i * 2:i * 2 + 2])
        for j, member in enumerate(members):
            member['plain_text'] = f'{title} passage {j + 1}. ' * 100 + f'FINAL MEMBER {i}-{j}'
        notes = deepcopy(members[0]['notes']) if with_notes else []
        for note in notes:
            note['target_heading'] = 'An identifiable heading'
            note['target_path'] = f'/Logic/{title}.md'
        sources = [{'pdf_page': page, 'printed_page': str(page - 2)} for page in range(10 + i * 100, 90 + i * 100)]
        groups.append({'type': 'file_selection', 'position': i, 'requested_id': f'/Logic/{title}.md',
                       'path': f'/Logic/{title}.md', 'target_id': None, 'state': 'live', 'title': title,
                       'members': members, 'notes': notes,
                       'plain_text': '\n\n'.join(member['plain_text'] for member in members),
                       'attribution': {'author': 'Hegel', 'role': 'main_text'}, 'sources': sources})
    value['records'] = groups
    return value


class ComparisonPresentationTests(unittest.TestCase):
    def test_wide_and_stacked_frames_keep_both_identities_and_note_previews_visible(self):
        for width in (140, 68):
            with self.subTest(width=width):
                view = ComparisonView(snapshot())
                frame = view.frame(width, 42)
                text = '\n'.join(frame)
                for value in (IDS[0], IDS[1], 'Personal observation 1.', 'Personal observation 2.',
                              'How do these arguments differ?', 'by Ada'):
                    self.assertIn(value, text)
                self.assertLessEqual(len(frame), 42)
                self.assertTrue(all(cell_width(line) <= width - 1 for line in frame))
                self.assertIn('│' if width == 140 else '─', text)

    def test_full_text_and_annotation_details_remain_scrollable(self):
        view = ComparisonView(snapshot())
        view.frame(140, 42)
        view.action('end')
        view.action('select_b')
        view.action('end')
        text = '\n'.join(view.frame(140, 42))
        self.assertIn('Location /logic/argument-1', text)
        self.assertIn('needs_visual_review', text)
        view.action('toggle')
        text = '\n'.join(view.frame(140, 42))
        self.assertIn('Personal observation 1.', text)
        self.assertIn('revision 1', text)
        self.assertIn('MATCHING', text)

    def test_long_question_has_a_full_scrollable_view(self):
        value = snapshot()
        value['comparison']['question'] = ('An extended inquiry keeps its full wording. ' * 100) + 'FINAL QUESTION WORDS'
        view = ComparisonView(value)
        self.assertIn('Tab: full saved question', '\n'.join(view.frame(100, 42)))
        view.action('toggle')
        view.action('toggle')
        view.frame(100, 42)
        view.action('end')
        text = '\n'.join(view.frame(100, 42))
        self.assertIn('FINAL QUESTION WORDS', text)
        self.assertIn('not historical excerpts', ' '.join(text.split()))
        self.assertIn(IDS[0], text)

    def test_ordered_pairs_and_single_last_record_are_accessible(self):
        value = snapshot()
        value['records'] = value['records'][:3]
        view = ComparisonView(value)
        view.action('next')
        text = '\n'.join(view.frame(100, 42))
        self.assertIn(IDS[2], text)
        self.assertNotIn(IDS[0], text)
        self.assertIn('Pair 2/2', text)
        view.action('next')
        self.assertEqual(view.pair, 1)
        view.action('previous')
        self.assertEqual(view.pair, 0)

    def test_view_keeps_an_independent_pinned_snapshot(self):
        value = snapshot()
        view = ComparisonView(value)
        value['records'][0]['notes'][0]['body'] = 'An external edit must not silently appear.'
        value['comparison']['question'] = 'A replaced question.'
        text = '\n'.join(view.frame(140, 42))
        self.assertIn('Personal observation 1.', text)
        self.assertNotIn('external edit', text)
        self.assertIn('How do these arguments differ?', text)

    def test_missing_retired_and_stale_bindings_are_not_presented_as_current(self):
        value = snapshot()
        value['records'][0].update(state='unresolved', target_id=None, plain_text='',
                                   reason='The canonical reference no longer resolves.')
        value['records'][1].update(state='retired', redirect_chain=[IDS[0], IDS[1]],
                                   reason='Explicit retirement redirect retained.')
        value['records'][1]['notes'][0].update(status='stale', status_reason='Original target retired.')
        view = ComparisonView(value)
        text = '\n'.join(view.frame(140, 42))
        self.assertIn('UNRESOLVED', text)
        self.assertIn('RETIRED', text)
        self.assertIn('STALE', text)
        self.assertIn('Original target retired.', card_text(value['records'][1], 'annotations'))

    def test_unicode_wrap_preserves_all_characters_and_escapes_control_text(self):
        value = 'Greek αβγ, café cafe\u0301, 中文 and averylongunbrokenword.'
        lines = wrap_text(value, 12)
        self.assertEqual(''.join(line.text for line in lines), value)
        self.assertTrue(all(cell_width(line.text) <= 12 for line in lines))
        self.assertTrue(all(not line.text.startswith('\u0301') for line in lines))
        malicious = snapshot()
        malicious['records'][0]['plain_text'] = 'Literal \x1b[2J text \u202e remains inert.'
        text = '\n'.join(ComparisonView(malicious).frame(140, 42))
        self.assertNotIn('\x1b', text)
        self.assertNotIn('\u202e', text)
        self.assertIn('\\u001b', text)

    def test_resize_keeps_scrolled_content_near_its_original_anchor(self):
        value = snapshot()
        value['records'][0]['plain_text'] = '\n'.join(f'Unique paragraph {i:03d}: some content.' for i in range(100))
        view = ComparisonView(value)
        view.frame(140, 42)
        for _ in range(8):
            view.action('page_down')
            view.frame(140, 42)
        before = view.offsets[('passages', 0, 0)]
        frame = view.frame(110, 42)
        self.assertGreater(before, 0)
        self.assertGreater(view.offsets[('passages', 0, 0)], 0)
        self.assertTrue(all(cell_width(line) <= 109 for line in frame))
        self.assertNotIn('Unique paragraph 000', '\n'.join(frame))

    def test_small_pane_gives_actionable_hint(self):
        self.assertIn('Enlarge', '\n'.join(ComparisonView(snapshot()).frame(20, 12)))

    def test_batched_fragmented_and_control_reply_keys_are_handled(self):
        actions, remaining = kitty.consume_keys(b'\t\x1b[', key_action)
        self.assertEqual(actions, ['toggle'])
        self.assertEqual(remaining, b'\x1b[')
        actions, remaining = kitty.consume_keys(remaining + b'6~n\x1b_Gi=1;OK\x1b\\q', key_action)
        self.assertEqual(actions, ['page_down', 'next', 'close'])
        self.assertFalse(remaining)

    def test_file_headers_use_paths_and_counts_instead_of_uuid_labels(self):
        value = file_snapshot()
        text = '\n'.join(ComparisonView(value).frame(140, 24))
        for path in (record['path'] for record in value['records']):
            self.assertIn(path, text)
            self.assertNotIn('UUID ' + path, text)
        self.assertIn('A | 2 records | Being and Becoming', text)
        self.assertIn('B | 2 records | Form and Essence', text)
        self.assertNotIn('Question:', text)
        self.assertNotIn('| by  |', text)
        self.assertNotIn('| workspace ', text)

    def test_eighty_columns_shows_both_texts_and_narrow_panes_focus_readable_text(self):
        for width in (80, 60):
            for with_notes in (False, True):
                with self.subTest(width=width, notes=with_notes):
                    view = ComparisonView(file_snapshot(with_notes=with_notes))
                    frame = view.frame(width, 24)
                    text = '\n'.join(frame)
                    self.assertIn('Being and Becoming passage 1.', text)
                    if width == 80:
                        self.assertIn('Form and Essence passage 1.', text)
                    else:
                        self.assertIn('B: /Logic/Form and Essence.md | b to read', text)
                        view.action('select_b')
                        changed = '\n'.join(view.frame(width, 24))
                        self.assertIn('Form and Essence passage 1.', changed)
                        self.assertIn('A: /Logic/Being and Becoming.md | a to read', changed)
                    self.assertNotIn('Enlarge', text)
                    self.assertNotIn('No saved annotations', text)
                    self.assertTrue(all(cell_width(line) <= width - 1 for line in frame))
                    self.assertEqual(len(frame), 24)

    def test_whole_file_prose_and_each_member_reference_are_retained(self):
        value = file_snapshot()
        text = card_text(value['records'][0], 'passages')
        for member in value['records'][0]['members']:
            self.assertIn(member['plain_text'], text)
            self.assertIn('Requested UUID ' + member['requested_id'], text)
            self.assertIn('Resolved UUID ' + member['target_id'], text)
            self.assertIn(member['path'], text)
        self.assertIn('File /Logic/Being and Becoming.md', text)
        self.assertIn('2 canonical records in corpus order', text)
        self.assertNotIn('Requested UUID /Logic/', text)
        self.assertIn('PDF 10–89 | printed 8–87', text)
        self.assertNotIn('PDF 10 (printed 8); PDF 11', text)

    def test_note_preview_and_full_notes_identify_the_related_passage(self):
        value = file_snapshot(with_notes=True)
        view = ComparisonView(value)
        text = '\n'.join(view.frame(140, 24))
        self.assertIn('Notes 1 | An identifiable heading', text)
        self.assertIn('Personal observation 1.', text)
        view.action('toggle')
        text = '\n'.join(view.frame(140, 24))
        self.assertIn('Passage: An identifiable heading', text)
        self.assertIn('File: /Logic/Being and Becoming.md', text)
        self.assertIn('revision 1', text)
        view.action('toggle')
        self.assertEqual(view.mode, 'passages')

    def test_selected_side_scrolls_independently_and_has_a_visible_marker(self):
        view = ComparisonView(file_snapshot())
        view.frame(80, 24)
        left, right = ('passages', 0, 0), ('passages', 0, 1)
        view.action('page_down')
        view.frame(80, 24)
        first_left = view.offsets[left]
        self.assertGreater(first_left, 0)
        self.assertEqual(view.offsets[right], 0)
        view.action('select_b')
        text = '\n'.join(view.frame(80, 24))
        self.assertIn('B selected', text)
        self.assertIn('> B | 2 records', text)
        view.action('page_down')
        view.frame(80, 24)
        self.assertEqual(view.offsets[left], first_left)
        self.assertGreater(view.offsets[right], 0)
        view.action('home')
        view.frame(80, 24)
        self.assertEqual(view.offsets[right], 0)
        self.assertEqual(view.offsets[left], first_left)

    def test_refresh_uses_supplied_command_and_quoted_reopen_remains_in_details(self):
        value = file_snapshot()
        view = ComparisonView(value)
        text = '\n'.join(view.frame(140, 24))
        self.assertIn('Refresh in reader: compare open', text)
        self.assertNotIn('compare open File comparison', text)
        view.action('end')
        text = ' '.join('\n'.join(view.frame(140, 24)).split())
        # The complete quoted invocation is retained even though the live footer is short.
        self.assertIn('Reopen in reader:', text)
        for argument in ("'/Logic/Being and Becoming.md'", "'/Logic/Form and Essence.md'"):
            self.assertIn(argument, text)
        value['refresh_command'] = value['reopen_command']
        text = ' '.join('\n'.join(ComparisonView(value).frame(140, 42)).split())
        self.assertIn('Refresh in reader: ' + value['reopen_command'], text)

    def test_comparison_keys_include_independent_side_selection(self):
        actions, remaining = kitty.consume_keys(b'abAB\x1b[B\x1b[5~', key_action)
        self.assertEqual(actions, ['select_a', 'select_b', 'select_a', 'select_b', 'down', 'page_up'])
        self.assertFalse(remaining)

    def test_long_file_path_is_short_in_header_and_complete_in_reference_details(self):
        value = file_snapshot()
        record = value['records'][0]
        path = '/Logic/' + 'a long directory name/' * 20 + 'Being and Becoming.md'
        record['path'] = record['requested_id'] = path
        view = ComparisonView(value)
        header = view._header(0, 38)
        self.assertTrue(header[1].startswith('…/'))
        self.assertIn('Being and Becoming.md', header[1])
        self.assertTrue(all(cell_width(line) <= 38 for line in header))
        self.assertIn('File ' + path, card_text(record, 'passages'))
        self.assertNotIn('Requested UUID ' + path, card_text(record, 'passages'))

    def test_non_numeric_printed_page_labels_survive_range_compression(self):
        value = file_snapshot()
        record = value['records'][0]
        record['sources'] = [{'pdf_page': 10, 'printed_page': 'Ⅳ'}, {'pdf_page': 11, 'printed_page': '²'}]
        text = card_text(record, 'passages')
        self.assertIn('PDF 10–11 | printed Ⅳ, ²', text)

    def test_actual_style_long_paths_keep_distinct_filenames_and_virtual_sections(self):
        value = file_snapshot()
        prefix = '/home/dima/.codex/.chatgpt-projects/g-p-6ac3fc82b07c8191990a11b451dcd626/local-corpus/contents/'
        value['records'][0]['path'] = value['records'][0]['requested_id'] = prefix + 'a. Being.md'
        value['records'][1]['path'] = value['records'][1]['requested_id'] = prefix + 'b. Nothing.md'
        view = ComparisonView(value)
        frame = view.frame(80, 24)
        self.assertIn('contents/a. Being.md', frame[3])
        self.assertIn('contents/b. Nothing.md', frame[3])
        self.assertTrue(view._header(0, 38)[1].startswith('…/'))
        self.assertTrue(view._header(1, 38)[1].startswith('…/'))
        for i, suffix in enumerate(('a. Being', 'b. Nothing')):
            value['records'][i]['path'] = value['records'][i]['requested_id'] = '/Science of Logic/Doctrine of Being/Quality/Being/' + suffix
        frame = ComparisonView(value).frame(80, 24)
        self.assertIn('…/Quality/Being/a. Being', frame[3])
        self.assertIn('…/Quality/Being/b. Nothing', frame[3])
        self.assertTrue(all(cell_width(line) <= 79 for line in frame))

    def test_corpus_relative_display_path_is_used_only_in_the_header(self):
        value = file_snapshot()
        record = value['records'][0]
        record['display_path'] = 'contents/a. Being.md'
        record['path'] = record['requested_id'] = '/long/original/corpus/path/contents/a. Being.md'
        view = ComparisonView(value)
        self.assertEqual(view._header(0, 38)[1], 'contents/a. Being.md')
        self.assertIn('File /long/original/corpus/path/contents/a. Being.md', card_text(record, 'passages'))

    def test_short_narrow_panes_show_realistic_section_and_argument_with_notes(self):
        value = file_snapshot(with_notes=True)
        for index, record in enumerate(value['records']):
            section = 'Being' if index == 0 else 'Nothing'
            argument = ('Being is pure indeterminate immediacy.' if index == 0
                        else 'Nothing is complete emptiness and the absence of determination.')
            record['members'][0]['plain_text'] = section
            record['members'][1]['plain_text'] = argument * 20
            record['plain_text'] = section + '\n\n' + record['members'][1]['plain_text']
        view = ComparisonView(value)
        for side, argument in (('select_a', 'Being is pure indeterminate immediacy.'),
                               ('select_b', 'Nothing is complete emptiness and the absence of determination.')):
            view.action(side)
            frame = view.frame(60, 18)
            text = ' '.join('\n'.join(frame).split())
            self.assertIn(argument, text)
            self.assertIn('to read', text)
            self.assertNotIn('Enlarge', text)
            self.assertEqual(len(frame), 18)
            self.assertTrue(all(cell_width(line) <= 59 for line in frame))

    def test_mixed_attribution_and_review_warnings_are_visible_before_their_text(self):
        value = file_snapshot()
        record = value['records'][0]
        record['mixed_attribution'] = True
        record['presentation_text'] = ('Text by Hegel\nCanonical argument.\n\n'
                                       'REVIEW: This transcription needs visual review.\n'
                                       'Editorial text by Translator\nTranslator commentary.')
        text = card_text(record, 'passages')
        self.assertTrue(text.startswith('Multiple contributors; authors identified below'))
        self.assertIn(record['presentation_text'], text)
        self.assertLess(text.index('REVIEW:'), text.index('Translator commentary.'))
        record['presentation_text'] = None
        with self.assertRaisesRegex(kitty.KittyError, 'display text'):
            ComparisonView(value)


class ComparisonOwnershipTests(unittest.TestCase):
    def test_comparison_launch_reuse_and_close_target_only_its_numeric_window(self):
        pane = kitty.ComparisonPane()
        self.addCleanup(pane._forget)
        inventory = json.dumps([{'tabs': [{'windows': [{'id': 43}]}]}])
        with patch.dict(os.environ, SESSION), patch('sol.terminal.kitty.shutil.which', return_value='/usr/bin/kitten'), \
                patch.object(pane, '_remote', side_effect=['43', inventory, '']) as remote:
            pane.show(snapshot())
            command = remote.call_args_list[0].args
            self.assertIn('--comparison-viewer', command)
            self.assertIn('window_id:19', command)
            self.assertIn('--env=KITTY_RC_PASSWORD', command)
            mailbox = pane.mailbox
            pane.show(snapshot())
            self.assertEqual(pane.mailbox, mailbox)
            pane.close()
            self.assertEqual(remote.call_args.args, ('close-window', '--match', 'id:43', '--ignore-no-match'))
            self.assertFalse(mailbox.exists())

    def test_manually_closed_comparison_reopens_without_owning_source_window(self):
        pane = kitty.ComparisonPane()
        source = kitty.SourcePane()
        source.window_id = 12
        self.addCleanup(pane._forget)
        with patch.dict(os.environ, SESSION), patch('sol.terminal.kitty.shutil.which', return_value='/usr/bin/kitten'), \
                patch.object(pane, '_remote', side_effect=['43', '[]', '44', '']):
            pane.show(snapshot())
            old = pane.mailbox
            pane.show(snapshot())
            self.assertEqual(pane.window_id, 44)
            self.assertFalse(old.exists())
            pane.close()
        self.assertEqual(source.window_id, 12)


class ComparisonTTYTests(unittest.TestCase):
    def test_real_viewer_restores_terminal_on_exit_and_accepts_view_keys(self):
        with tempfile.TemporaryDirectory(prefix='sol-comparison-tty-') as directory:
            mailbox = Path(directory) / 'selection.json'
            mailbox.write_text(json.dumps({'sequence': 1, 'request': snapshot()}))
            master, slave = pty.openpty()
            self.addCleanup(os.close, master)
            self.addCleanup(os.close, slave)
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 42, 140, 1400, 840))
            original = termios.tcgetattr(slave)
            process = subprocess.Popen([sys.executable, '-B', '-m', 'sol.terminal.kitty', '--comparison-viewer', str(mailbox)],
                                       stdin=slave, stdout=slave, stderr=slave, cwd=Path(__file__).resolve().parents[1])
            def reap():
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
            self.addCleanup(reap)
            output = bytearray()

            def wait_for(text):
                deadline = time.monotonic() + 5
                while text not in output:
                    if time.monotonic() >= deadline:
                        self.fail('Viewer did not show ' + text.decode() + ': ' + output.decode(errors='replace'))
                    ready, _, _ = select.select([master], [], [], .1)
                    if ready:
                        output.extend(os.read(master, 65536))

            wait_for(b'Personal observation 1.')
            os.write(master, b'\t')
            wait_for(b'annotations')
            os.write(master, b'n')
            wait_for(b'Pair 2/2')
            os.write(master, b'q')
            self.assertEqual(process.wait(timeout=5), 0)
            self.assertEqual(termios.tcgetattr(slave), original)


if __name__ == '__main__':
    unittest.main()
