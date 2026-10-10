"""Build and inspect distributable archives using only public project files."""
from __future__ import annotations

import configparser
from email.parser import Parser
import importlib.util
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
    "requirements-corpus.txt",
} | {module + ".py" for module in MODULES}


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
        for relative in ("sources/source.pdf", "local-corpus/hegel/chapter.md",
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


if __name__ == "__main__":
    unittest.main()
