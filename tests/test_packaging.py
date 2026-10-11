"""Build and inspect distributable archives using only public project files."""
from __future__ import annotations

import configparser
from email.parser import Parser
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile


MODULES = {
    "sol", "sol_corpus", "sol_corpus_contract", "sol_corpus_notes",
    "sol_corpus_references", "sol_corpus_structure",
}
ENTRY_POINTS = {
    "sol": "sol:cli",
    "sol-corpus": "sol_corpus:main",
    "sol-corpus-check": "sol_corpus_contract:main",
}
PUBLIC_FILES = {
    "pyproject.toml", "MANIFEST.in", "README.md", "CORPUS.md",
    "INTERFACE_RESEARCH.md", "WORKSPACE_PLAN.md",
    "requirements-corpus.txt",
} | {module + ".py" for module in MODULES}


def write_runtime_corpus(directory):
    """Create a valid tiny index using stdlib only, without a source PDF."""
    import sol_corpus_contract as contract

    directory.mkdir(parents=True)
    section_id = "aaaaaaaa-0000-4000-8000-000000000001"
    passage_id = "bbbbbbbb-0000-4000-8000-000000000002"
    body = "An invented passage makes this installed research reader useful without extracting any PDF."
    common = {
        "sources": [{"pdf_page": 80, "printed_page": "7"}],
        "attribution": {"author": "G. W. F. Hegel", "role": "main_text", "status": "confirmed"},
        "reader_path": "/BEING/synthetic.txt", "reader_title": "Synthetic section",
    }
    section = {**common, "id": section_id, "type": "section", "parent_id": None,
               "order": 0, "title": "Synthetic section", "path": "/synthetic"}
    paragraph = {**common, "id": passage_id, "type": "paragraph",
                 "parent_id": section_id, "order": 1}
    markdown = "\n".join((
        contract.render_record(section, "# Synthetic section"),
        contract.render_record(paragraph, body),
    ))
    (directory / "sample.md").write_text(markdown, encoding="utf-8")
    manifest = {
        "contract_version": 1, "edition": {"title": "Synthetic installed reader edition"},
        "source": {"filename": "absent.pdf", "sha256": "0" * 64, "pdf_pages": 80},
        "documents": ["sample.md"],
        "page_inventory": [
            {"pdf_page": page, "printed_page": None, "disposition": "blank",
             "reason": "Invented blank page"}
            for page in range(1, 80)
        ] + [{"pdf_page": 80, "printed_page": "7", "disposition": "records"}],
    }
    encoded_manifest = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    (directory / "corpus.json").write_bytes(encoded_manifest)
    records = [
        {**section, "document": "sample.md", "markdown": "# Synthetic section",
         "plain_text": "Synthetic section", "context": []},
        {**paragraph, "document": "sample.md", "markdown": body, "plain_text": body,
         "context": [{"id": section_id, "type": "section", "title": "Synthetic section",
                      "path": "/synthetic"}]},
    ]
    for record in records:
        record["content_sha256"] = hashlib.sha256(record["markdown"].encode("utf-8")).hexdigest()
    payload = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                      for record in records).encode("utf-8")
    (directory / "index.jsonl").write_bytes(payload)
    metadata = {
        "contract_version": 1,
        "manifest_sha256": hashlib.sha256(encoded_manifest).hexdigest(),
        "source_sha256": "0" * 64,
        "documents": {"sample.md": hashlib.sha256(markdown.encode("utf-8")).hexdigest()},
        "index_sha256": hashlib.sha256(payload).hexdigest(),
        "record_count": len(records),
    }
    (directory / "index.meta.json").write_text(json.dumps(metadata), encoding="utf-8")
    return passage_id, body


@unittest.skipUnless(importlib.util.find_spec("setuptools"), "setuptools is needed to build archives")
class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="sol-package-test-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.stage = Path(cls.temporary.name) / "source"
        cls.stage.mkdir()
        root = Path(__file__).resolve().parents[1]
        for filename in PUBLIC_FILES:
            shutil.copy2(root / filename, cls.stage / filename)
        tests = cls.stage / "tests"
        tests.mkdir()
        for source in (root / "tests").glob("*.py"):
            shutil.copy2(source, tests / source.name)
        # Synthetic sentinels exercise archive exclusions without copying the book.
        for relative in ("Hegel-SOL.pdf", "sources/source.pdf", "local-corpus/hegel/chapter.md",
                         "local-corpus/index.jsonl", ".sol-corpus-work/layout.xml",
                         "AGENTS.md"):
            sentinel = cls.stage / relative
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("Synthetic private fixture\n", encoding="utf-8")
        cls.dist = Path(cls.temporary.name) / "dist"
        cls.dist.mkdir()
        # Direct backend calls require no network, frontend or isolated build download.
        result = subprocess.run(
            [sys.executable, "-c",
             "import setuptools.build_meta as build; import sys; destination = sys.argv[1]; "
             "build.build_wheel(destination); build.build_sdist(destination)",
             str(cls.dist)],
            cwd=cls.stage, text=True, capture_output=True,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.wheel = next(cls.dist.glob("*.whl"))
        cls.sdist = next(cls.dist.glob("*.tar.gz"))

    def test_wheel_contains_only_public_modules_and_metadata(self):
        with zipfile.ZipFile(self.wheel) as archive:
            names = archive.namelist()
        actual_modules = {name[:-3] for name in names if "/" not in name and name.endswith(".py")}
        self.assertEqual(actual_modules, MODULES)
        self.assertTrue(all(name in {module + ".py" for module in MODULES}
                            or ".dist-info/" in name for name in names))

    def test_metadata_and_console_entry_points(self):
        with zipfile.ZipFile(self.wheel) as archive:
            info = next(name.rsplit("/", 1)[0] for name in archive.namelist()
                        if name.endswith("/METADATA"))
            metadata = Parser().parsestr(archive.read(info + "/METADATA").decode())
            entry_points = configparser.ConfigParser()
            entry_points.read_string(archive.read(info + "/entry_points.txt").decode())
        self.assertEqual(metadata["Name"], "sol-organizes-logic")
        self.assertEqual(metadata["Version"], "0.1.0")
        self.assertEqual(metadata["Requires-Python"], ">=3.10")
        self.assertEqual(dict(entry_points["console_scripts"]), ENTRY_POINTS)
        requirements = metadata.get_all("Requires-Dist") or []
        self.assertEqual(len(requirements), 1)
        self.assertTrue(requirements[0].startswith("markdown-it-py<4,>=3;"))
        self.assertIn('extra == "corpus"', requirements[0])

    def test_sdist_contains_sources_and_docs_without_local_material(self):
        with tarfile.open(self.sdist) as archive:
            names = {"/".join(Path(name).parts[1:]) for name in archive.getnames()}
        self.assertTrue(PUBLIC_FILES <= names)
        self.assertIn("tests/test_packaging.py", names)
        private_parts = {"sources", "local-corpus", ".sol-corpus-work", "AGENTS.md"}
        for name in names:
            self.assertFalse(private_parts.intersection(Path(name).parts), name)
            self.assertFalse(name.endswith((".pdf", ".png", ".zip", ".jsonl")), name)

    def test_built_wheel_entry_points_import_and_display_help(self):
        unpacked = Path(self.temporary.name) / "wheel"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(unpacked)
        for entry in ENTRY_POINTS.values():
            module, function = entry.split(":")
            result = subprocess.run(
                [sys.executable, "-I", "-c",
                 "import sys, importlib; sys.path.insert(0, sys.argv[1]); "
                 "module = importlib.import_module(sys.argv[2]); "
                 "entry = getattr(module, sys.argv[3]); "
                 "sys.argv = [sys.argv[2], '--help']; "
                 "entry()",
                 str(unpacked), module, function],
                cwd=self.temporary.name, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("usage:", result.stdout)

    def test_installed_local_origin_finds_corpus_outside_checkout_without_pdf_or_parser(self):
        # A source-directory pip install builds a wheel and then records dir_info.
        # Use actual dist-info files so importlib.metadata discovery is exercised.
        origin = Path(self.temporary.name) / "checkout with spaces"
        passage_id, body = write_runtime_corpus(origin / "local-corpus")
        elsewhere = Path(self.temporary.name) / "outside-checkout"
        elsewhere.mkdir()
        (elsewhere / "Hegel-SOL.pdf").write_bytes(b"PDF extraction must never run")
        environment = os.environ.copy()
        environment.pop("SOL_CORPUS", None)
        environment["XDG_CONFIG_HOME"] = str(Path(self.temporary.name) / "isolated-config")
        program = """
import builtins
import importlib
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def block_parser(name, *args, **kwargs):
    if name.startswith("markdown_it"):
        raise AssertionError("Installed reader must not import the Markdown parser")
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_parser
sol = importlib.import_module("sol")
assert Path(sol.__file__).parent == Path(sys.argv[1])
assert not (Path(sol.__file__).parent / "local-corpus").exists()
def block_pdf(*args, **kwargs):
    raise AssertionError("Installed reader must not extract the PDF")
sol.load_book = block_pdf
raise SystemExit(sol.cli(sys.argv[2:]))
"""
        for editable in (False, True):
            installed = Path(self.temporary.name) / f"installed-origin-{editable}"
            with zipfile.ZipFile(self.wheel) as archive:
                archive.extractall(installed)
            info = next(installed.glob("*.dist-info"))
            (info / "direct_url.json").write_text(json.dumps({
                "url": origin.as_uri(),
                "dir_info": {"editable": True} if editable else {},
            }), encoding="utf-8")
            for arguments in (["--passage", passage_id, "--json"], ["--json"]):
                with self.subTest(editable=editable, arguments=arguments):
                    result = subprocess.run(
                        [sys.executable, "-I", "-c", program, str(installed), *arguments],
                        cwd=elsewhere, env=environment, capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    returned = json.loads(result.stdout)
                    self.assertEqual(returned["id"], passage_id)
                    self.assertEqual(returned["text"], body)
                    self.assertEqual(returned["path"], "/BEING/synthetic.txt")


if __name__ == "__main__":
    unittest.main()
