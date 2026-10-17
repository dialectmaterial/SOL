"""Human path choices over loaded canonical text, never random selections."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from sol.reader import app
from sol.workspace.comparison import capture_paths, ComparisonError, resolve_comparison_path
from sol.workspace.reader import WorkspaceReader
from sol.workspace.store import Workspace
from test_workspace_reader import invented_book, CORPUS_ID, IDS


class ComparisonPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="sol-comparison-paths-")
        self.addCleanup(temporary.cleanup)
        self.book = invented_book()
        self.book.corpus_manifest["documents"] = ["sample.md", "editorial.md"]
        self.book.canonical_records[IDS[3]]["document"] = "editorial.md"
        self.store = Workspace(Path(temporary.name) / "reading.sqlite3", CORPUS_ID,
                               {k: self.book.corpus_manifest[k] for k in ("edition", "source")}, actor="Ada")
        self.addCleanup(self.store.close)
        self.reader = WorkspaceReader(self.book, self.store, "Ada", app.resolve_path,
                                      app.display_path, app.render_passage)
        self.note = self.store.add_annotation(IDS[1], "A note on the second paragraph.",
                                             self.book.canonical_records[IDS[1]]["content_sha256"])
        self.pane = Mock()

    def capture(self, paths=("/being/quality", "/essence/ground"), **kwargs):
        return capture_paths(self.book, paths, resolve_path=app.resolve_path,
                             workspace_reader=self.reader, **kwargs)

    def test_virtual_files_are_two_complete_ordered_sides(self):
        with patch("sol.reader.actions.random.choice", side_effect=AssertionError("no random sampling")), \
                patch.object(self.store, "export", wraps=self.store.export) as export:
            snapshot = self.capture()
        export.assert_called_once_with()
        self.assertEqual(len(snapshot["records"]), 2)
        first, second = snapshot["records"]
        self.assertEqual([m["target_id"] for m in first["members"]], IDS[:2])
        self.assertEqual([m["target_id"] for m in second["members"]], [IDS[2]])
        self.assertEqual(first["path"], "/BEING/01-quality.txt")
        self.assertEqual(first["plain_text"], "\n\n".join(self.book.canonical_records[i]["plain_text"] for i in IDS[:2]))
        self.assertEqual(first["notes"][0]["id"], self.note["id"])
        self.assertEqual(first["notes"][0]["target_heading"], "Quality")
        self.assertEqual(first["notes"][0]["target_id"], IDS[1])
        self.assertIn(self.book.canonical_records[IDS[1]]["content_sha256"], str(first["members"]))
        self.assertEqual(snapshot["refresh_command"], "compare open")
        self.assertIn("/BEING/01-quality.txt", snapshot["reopen_command"])

    def test_relative_alias_paths_resolve_from_browsing_directory(self):
        snapshot = self.capture(("quality", "../essence/ground"), cwd=("BEING",))
        self.assertEqual([r["path"] for r in snapshot["records"]],
                         ["/BEING/01-quality.txt", "/ESSENCE/01-ground.txt"])

    def test_directory_scope_preserves_book_order_and_duplicate_sides(self):
        snapshot = self.capture(("/being", "/BEING"))
        self.assertEqual([m["target_id"] for m in snapshot["records"][0]["members"]], IDS[:2])
        self.assertEqual(snapshot["records"][0]["plain_text"], snapshot["records"][1]["plain_text"])
        snapshot["records"][0]["members"][0]["plain_text"] = "mutated presentation"
        self.assertNotEqual(snapshot["records"][0]["members"][0]["plain_text"],
                            snapshot["records"][1]["members"][0]["plain_text"])
        self.assertNotEqual(self.book.canonical_records[IDS[0]]["plain_text"], "mutated presentation")

    def test_canonical_markdown_accepts_relative_absolute_and_corpus_prefix(self):
        for path in ("sample.md", "/invented/corpus/sample.md", "corpus/sample.md", "./sample.md"):
            with self.subTest(path=path):
                snapshot = self.capture((path, "editorial.md"))
                self.assertEqual([m["target_id"] for m in snapshot["records"][0]["members"]], IDS[:3])
                self.assertEqual(snapshot["records"][1]["members"][0]["target_id"], IDS[3])
                self.assertEqual(snapshot["records"][1]["attribution"]["author"], "Invented editor")
                self.assertEqual(snapshot["records"][0]["path"], "/invented/corpus/sample.md")

    def test_outside_and_unlisted_markdown_are_not_loaded(self):
        for path in ("/tmp/arbitrary.md", "../arbitrary.md", "not-indexed.md", "/invented/corpus/unlisted.md"):
            with self.subTest(path=path), patch.object(Path, "read_text", side_effect=AssertionError("no arbitrary file read")):
                with self.assertRaises(ComparisonError):
                    self.capture((path, "sample.md"))
        with self.assertRaisesRegex(ValueError, "no such path"):
            self.capture(("/missing.txt", "/being"))

    def test_capture_is_read_only_and_refreshes_only_the_snapshot(self):
        before = self.store.export()
        first = self.capture()
        self.store.add_annotation(IDS[0], "A later annotation.", self.book.canonical_records[IDS[0]]["content_sha256"])
        second = self.capture()
        self.assertEqual(len(first["records"][0]["notes"]), 1)
        self.assertEqual(len(second["records"][0]["notes"]), 2)
        after = self.store.export()
        for field in ("state", "history", "comparisons", "reviews", "relations"):
            self.assertEqual(before[field], after[field])

    def test_capture_without_workspace_has_no_notes_or_authored_write(self):
        snapshot = capture_paths(self.book, ["/being", "/essence"], resolve_path=app.resolve_path)
        self.assertEqual(snapshot["workspace"]["name"], "")
        self.assertEqual(snapshot["comparison"]["actor"], "")
        self.assertFalse(snapshot["records"][0]["notes"])
        self.assertFalse(self.store.list_comparisons())

    def test_markdown_group_preserves_mixed_authors_per_record(self):
        self.book.canonical_records[IDS[3]]["document"] = "sample.md"
        snapshot = self.capture(("sample.md", "/being"))
        self.assertIsNone(snapshot["records"][0]["attribution"]["author"])
        self.assertEqual(snapshot["records"][0]["attribution"]["role"], "mixed_attribution")
        self.assertEqual(next(m for m in snapshot["records"][0]["members"] if m["target_id"] == IDS[3])["attribution"]["author"], "Invented editor")

    def test_inline_attribution_and_review_warnings_preserve_literal_text(self):
        self.book.canonical_records[IDS[3]]["document"] = "sample.md"
        self.book.canonical_records[IDS[1]]["transcription_status"] = "needs_visual_review"
        group = self.capture(("sample.md", "/being"))["records"][0]
        self.assertIn("[Text by Invented editor | editorial note]", group["presentation_text"])
        self.assertIn("[Text by G. W. F. Hegel]", group["presentation_text"])
        self.assertIn("[Transcription needs source review]", group["presentation_text"])
        marker = group["presentation_text"].index("[Transcription needs source review]")
        self.assertLess(marker, group["presentation_text"].index(self.book.canonical_records[IDS[1]]["plain_text"]))
        self.assertNotIn("[Transcription needs source review]", group["plain_text"])
        for member in group["members"]:
            self.assertEqual(member["plain_text"], self.book.canonical_records[member["target_id"]]["plain_text"])

    def shell(self, commands, *, workspace=True):
        output = StringIO()
        iterator = iter(commands)
        with redirect_stdout(output), patch("sol.reader.shell.install_completion", return_value=lambda: None):
            result = app.run_shell(self.book, 80, workspace_reader=self.reader if workspace else None,
                                   read_command=lambda prompt: next(iterator), comparison_pane=self.pane)
        self.assertEqual(result, 0)
        return output.getvalue()

    def test_direct_open_and_refresh_retain_selection_after_cd(self):
        output = self.shell(["first /being", "cd /being", "compare quality ../essence/ground --question 'What changes?'",
                             "cd /essence", "compare open", "where", "compare close", "exit"])
        self.assertNotIn("sol: ", output)
        self.assertEqual(self.pane.show.call_count, 2)
        first, second = [c.args[0] for c in self.pane.show.call_args_list]
        self.assertEqual([r["path"] for r in first["records"]], [r["path"] for r in second["records"]])
        self.assertEqual(second["comparison"]["question"], "What changes?")
        self.assertEqual(len(self.store.export()["history"]), 3)  # first + two cd commands; comparisons add none
        self.assertIn(f"ID {IDS[0]}", output)
        self.assertEqual(self.store.get_state()["cwd"], "/ESSENCE")
        self.assertFalse(self.store.list_comparisons())
        self.pane.close.assert_called_once()

    def test_explicit_open_accepts_two_paths_without_workspace(self):
        output = self.shell(["compare open /being /essence", "compare open", "exit"], workspace=False)
        self.assertNotIn("sol: ", output)
        self.assertEqual(self.pane.show.call_count, 2)

    def test_failed_path_does_not_replace_last_selection(self):
        output = self.shell(["compare /being /essence", "compare /missing /being", "compare open", "exit"])
        self.assertIn("no such path", output)
        self.assertEqual(self.pane.show.call_count, 2)
        self.assertEqual(self.pane.show.call_args.args[0]["records"][0]["path"], "/BEING")

    def test_question_paths_with_spaces_remain_quoted_in_reopen_command(self):
        self.book.corpus_directory = Path("/invented/corpus with spaces")
        snapshot = self.capture(("sample.md", "editorial.md"), question="How does 'being' differ?")
        self.assertIn("'/invented/corpus with spaces/sample.md'", snapshot["reopen_command"])
        import shlex
        parts = shlex.split(snapshot["reopen_command"])
        self.assertEqual(parts[2], "/invented/corpus with spaces/sample.md")
        self.assertEqual(parts[-1], "How does 'being' differ?")


if __name__ == "__main__":
    unittest.main()
