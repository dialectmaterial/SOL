"""Explicit real Chromium proof; no browser download or installation is automatic."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from sol.core.corpus import load_corpus_book
from sol.corpus import contract
from experiments.reader_surfaces.common import sample_from_book, validate_packet
from experiments.reader_surfaces.html import write_html
from fixtures_corpus import write_runtime_corpus


@unittest.skipUnless(os.environ.get("SOL_TEST_LIVE_SURFACE_BROWSER") == "1", "real browser proof is explicit opt-in")
@unittest.skipUnless(importlib.util.find_spec("markdown_it"), "optional CommonMark dependency is absent")
class ReaderSurfaceBrowserTests(unittest.TestCase):
    def test_actual_dom_selection_reflow_restore_download_and_python_validation(self):
        if not shutil.which("node") or not Path(os.environ.get("SOL_TEST_CHROMIUM", "/usr/bin/google-chrome")).exists():
            self.skipTest("provide Node, Playwright via SOL_PLAYWRIGHT_MODULE, and SOL_TEST_CHROMIUM")
        with tempfile.TemporaryDirectory(prefix="sol-typeset-browser-") as temporary:
            root = Path(temporary)
            corpus = root / "corpus"
            write_runtime_corpus(corpus)
            rows = [json.loads(line) for line in (corpus / "index.jsonl").read_text().splitlines()]
            rows[1]["markdown"] = "Lead 𝔸 *thought* e\u0301 and **ground**, Greek α, CJK 界, NBSP\u00a0kept. A repeated repeated tail."
            second = deepcopy(rows[1]); second.update(id="cccccccc-0000-4000-8000-000000000003", order=2,
                markdown="A following paragraph is continuously present without changing the earlier identity.")
            third = deepcopy(rows[1]); third.update(id="dddddddd-0000-4000-8000-000000000004", order=3,
                markdown='`<script>globalThis.sourceExecuted=true</script> & <img src="https://invalid.test/">`')
            rows.extend((second, third))
            generated = {"markdown", "plain_text", "document", "context", "content_sha256"}
            (corpus / "sample.md").write_text("\n".join(contract.render_record(
                {key:value for key,value in row.items() if key not in generated}, row["markdown"]) for row in rows), encoding="utf-8")
            contract.reindex(corpus); contract.initialize_corpus_identity(corpus)
            before = {file.name:file.read_bytes() for file in corpus.iterdir()}
            book = load_corpus_book(corpus)
            artifact, download = root / "reader.html", root / "selection.json"
            write_html(sample_from_book(book, count=3), artifact)
            runner = Path(__file__).resolve().parents[1] / "experiments/reader_surfaces/browser_acceptance.cjs"
            result = subprocess.run(["node", str(runner), str(artifact), str(download)],
                capture_output=True, text=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "passed")
            self.assertGreater(report["mapping_checks"], len(book.passages[0].text))
            selected = validate_packet(book, json.loads(download.read_text()))
            self.assertIn("thought", selected.text)
            self.assertIn("ground", selected.text)
            self.assertEqual(before, {file.name:file.read_bytes() for file in corpus.iterdir()})
            self.assertFalse(list(root.rglob("*.sqlite3")))
            print("Browser proof:", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
