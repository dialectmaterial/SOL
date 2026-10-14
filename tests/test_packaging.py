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


PACKAGE_FILES = {
    "sol/__init__.py", "sol/__main__.py",
    "sol/core/__init__.py", "sol/core/config.py", "sol/core/corpus.py",
    "sol/core/models.py", "sol/core/paths.py", "sol/core/references.py", "sol/core/protocol.py", "sol/core/wire.py",
    "sol/essence/__init__.py", "sol/essence/terms.py", "sol/essence/cli.py",
    "sol/reader/__init__.py", "sol/reader/app.py", "sol/reader/models.py", "sol/reader/legacy_pdf.py",
    "sol/reader/options.py", "sol/reader/actions.py", "sol/reader/navigation.py", "sol/reader/typography.py",
    "sol/reader/search.py",
    "sol/corpus/__init__.py", "sol/corpus/convert.py", "sol/corpus/contract.py", "sol/corpus/notes.py",
    "sol/corpus/references.py", "sol/corpus/structure.py", "sol/corpus/layout.py", "sol/corpus/edition.py",
    "sol/corpus/extraction.py", "sol/corpus/ingest.py",
    "sol/corpus/backends/__init__.py", "sol/corpus/backends/opendataloader.py",
    "sol/workspace/__init__.py", "sol/workspace/store.py", "sol/workspace/reader.py",
    "sol/workspace/diagnostics.py", "sol/workspace/catalog.py", "sol/workspace/export.py",
    "sol/workspace/profiles.py", "sol/workspace/comparison.py", "sol/terminal/__init__.py", "sol/terminal/prompt.py",
    "sol/terminal/source.py", "sol/terminal/kitty.py", "sol/terminal/comparison.py", "sol/terminal/commands.py",
    "sol/terminal/reference.py", "sol/terminal/handoff.py", "sol/terminal/essence.py", "sol/terminal/reader.py",
    "sol/terminal/reading_layout.py",
}
ENTRY_POINTS = {
    "sol": "sol:cli",
    "sol-kitty": "sol.terminal.kitty:main",
    "sol-corpus": "sol.corpus.convert:main",
    "sol-corpus-check": "sol.corpus.contract:main",
}
PUBLIC_FILES = {
    "pyproject.toml", "MANIFEST.in", "README.md", "docs/CORPUS.md", "docs/USAGE.md",
    "docs/WORKSPACE_PLAN.md", "docs/WORKSPACE_EXPORT.md", "docs/MODULARITY.md", "docs/EXTRACTION.md",
    "docs/READER_ACTIONS.md",
    "docs/REFERENCE_PROTOCOL.md",
    "docs/HANDOFF.md",
    "docs/TERM_STUDY.md",
    "docs/READER_VIEW.md",
    "docs/READER_ACCEPTANCE.md",
    "docs/research/INTERFACE_RESEARCH.md", "docs/research/OPENDATALOADER_RESEARCH.md",
} | PACKAGE_FILES


def write_runtime_corpus(directory, *, pending_review=False):
    """Create a valid tiny index using stdlib only, without a source PDF."""
    import sol.corpus.contract as contract

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
    if pending_review:
        paragraph["transcription_status"] = "needs_review"
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
            (cls.stage / filename).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / filename, cls.stage / filename)
        tests = cls.stage / "tests"
        tests.mkdir()
        for source in (root / "tests").glob("*.py"):
            shutil.copy2(source, tests / source.name)
        # Synthetic sentinels exercise archive exclusions without copying the book.
        for relative in ("Hegel-SOL.pdf", "sources/source.pdf", "local-corpus/hegel/chapter.md",
                         "local-corpus/index.jsonl", ".sol-corpus-work/layout.xml",
                         ".sol-extractions/candidate.json", ".sol-extractions/review.json",
                         ".sol-ingest-work/audit/ingestion.json", ".sol-ingest-work/doc.md",
                         "reading.sqlite3", "reading.sqlite3-wal", "reading.sqlite3-shm",
                         "tests/private-workspace/reading.sqlite3-journal",
                         "profiles.sqlite3", "tests/private-profile/profiles.sqlite3-wal",
                         "personal.sol-workspace.json", "personal.sol-analysis.json",
                         "tests/private-workspace/personal.sol-analysis.json",
                         "personal.sol-workspace.md", "tests/private-workspace/personal.sol-workspace.md",
                         "AGENTS.md"):
            sentinel = cls.stage / relative
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("Synthetic private fixture\n", encoding="utf-8")
        # Deliberately nominate the workspace sentinels before the real exclusions,
        # so this test exercises MANIFEST.in rather than an incidental omission.
        manifest = cls.stage / "MANIFEST.in"
        manifest.write_text("recursive-include . *.sqlite3 *.sqlite3-* *.sol-workspace.json *.sol-workspace.md *.sol-analysis.json\n"
                            "recursive-include .sol-extractions *\nrecursive-include .sol-ingest-work *\n"
                            + manifest.read_text(encoding="utf-8"), encoding="utf-8")
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
        actual_modules = {name for name in names if name.endswith(".py")}
        self.assertEqual(actual_modules, PACKAGE_FILES)
        self.assertTrue(all(name in PACKAGE_FILES
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
        self.assertEqual(set(metadata.get_all("Provides-Extra") or []), {"corpus", "shell", "extraction"})
        self.assertEqual(len(requirements), 4)
        corpus = [requirement for requirement in requirements if 'extra == "corpus"' in requirement]
        shell = [requirement for requirement in requirements if 'extra == "shell"' in requirement]
        extraction = [requirement for requirement in requirements if 'extra == "extraction"' in requirement]
        self.assertEqual(len(corpus), 1)
        self.assertEqual(len(shell), 2)
        self.assertEqual(len(extraction), 1)
        self.assertTrue(corpus[0].startswith("markdown-it-py<4,>=3;"))
        self.assertEqual({requirement.split(";")[0] for requirement in shell},
                         {"prompt-toolkit<4,>=3.0.52", "markdown-it-py<4,>=3"})
        self.assertTrue(extraction[0].startswith("opendataloader-pdf==2.5.13;"))

    def test_sdist_contains_sources_and_docs_without_local_material(self):
        with tarfile.open(self.sdist) as archive:
            names = {"/".join(Path(name).parts[1:]) for name in archive.getnames()}
        self.assertTrue(PUBLIC_FILES <= names)
        self.assertIn("tests/test_packaging.py", names)
        private_parts = {"sources", "local-corpus", ".sol-corpus-work", ".sol-extractions",
                         ".sol-ingest-work", "AGENTS.md"}
        for name in names:
            self.assertFalse(private_parts.intersection(Path(name).parts), name)
            self.assertFalse(name.endswith((".pdf", ".png", ".zip", ".jsonl", ".sol-workspace.json", ".sol-workspace.md",
                                           ".sol-analysis.json")), name)
            self.assertFalse(Path(name).name.endswith(".sqlite3")
                             or ".sqlite3-" in Path(name).name, name)

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

    def test_installed_extraction_help_does_not_require_extraction_or_corpus_extras(self):
        installed = Path(self.temporary.name) / "extraction-help-wheel"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        program = """
import builtins, sys
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def guard(name, *args, **kwargs):
    if name.split('.')[0] in {'markdown_it', 'opendataloader_pdf'} or name in {
        'sol.corpus.extraction', 'sol.corpus.ingest', 'sol.corpus.backends.opendataloader'}:
        raise AssertionError('Installed help imported optional operation ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard
from sol.corpus.convert import main
try:
    main(sys.argv[2:])
except SystemExit as error:
    assert error.code == 0
else:
    raise AssertionError('Help should exit without running an operation')
assert 'opendataloader_pdf' not in sys.modules
assert 'markdown_it' not in sys.modules
"""
        for action in ("extract", "normalize", "ingest"):
            with self.subTest(action=action):
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", program, str(installed), action, "--help"],
                    cwd=self.temporary.name, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("usage:", result.stdout)

    def test_installed_experiment_runs_without_reader_workspace_or_optional_libraries(self):
        installed = Path(self.temporary.name) / "term-study-wheel"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        corpus = Path(self.temporary.name) / "installed-experiment-corpus"
        write_runtime_corpus(corpus)
        from sol.corpus.contract import initialize_corpus_identity
        initialize_corpus_identity(corpus)
        before = {path.name: path.read_bytes() for path in corpus.iterdir()}
        program = """
import builtins, contextlib, io, json, sys
sys.path.insert(0, sys.argv[1])
forbidden = ('sol.reader', 'sol.workspace', 'sol.terminal', 'prompt_toolkit',
             'markdown_it', 'rich', 'textual', 'openai', 'pypdf', 'pdfplumber',
             'sol.corpus.convert', 'sol.corpus.extraction', 'opendataloader_pdf')
original_import = builtins.__import__
def guard(name, *args, **kwargs):
    if any(name == prefix or name.startswith(prefix + '.') for prefix in forbidden):
        raise AssertionError('Experiment imported unrelated component ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard
from sol.essence.cli import main
from sol.essence.terms import check_term_result
from sol.core import load_snapshot
output = io.StringIO()
with contextlib.redirect_stdout(output):
    assert main(['term', 'invented', '--corpus', sys.argv[2], '--json']) == 0
result = json.loads(output.getvalue())
assert result['totals']['occurrences'] == 1
assert check_term_result(load_snapshot(sys.argv[2]), result) == result
assert not any(name == prefix or name.startswith(prefix + '.')
               for name in sys.modules for prefix in forbidden)
print(json.dumps({'query': result['query'], 'occurrences': result['totals']['occurrences']}))
"""
        completed = subprocess.run([sys.executable, "-I", "-B", "-c", program, str(installed), str(corpus)],
                                   cwd=self.temporary.name, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"query": "invented", "occurrences": 1})
        self.assertEqual(before, {path.name: path.read_bytes() for path in corpus.iterdir()})

    def test_core_only_wheel_proves_interface_dependency_boundary(self):
        """Release-gate fixture only: this is not another installable SOL product."""
        fixture = Path(self.temporary.name) / "core-only-release-gate"
        stage, destination = fixture / "source", fixture / "dist"
        stage.mkdir(parents=True)
        destination.mkdir()
        root = Path(__file__).resolve().parents[1]
        selected = {"sol/__init__.py", "sol/corpus/__init__.py", "sol/corpus/contract.py"}
        selected.update(path for path in PACKAGE_FILES if path.startswith("sol/core/"))
        for filename in selected:
            target = stage / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / filename, target)
        (stage / "pyproject.toml").write_text(
            '[build-system]\nrequires = ["setuptools>=68"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            '[project]\nname = "sol-core-boundary-fixture"\nversion = "0.0.0"\n'
            'description = "Synthetic dependency-boundary release gate, not a SOL product"\n'
            'requires-python = ">=3.10"\ndependencies = []\n\n'
            '[tool.setuptools]\ninclude-package-data = false\n\n'
            '[tool.setuptools.packages.find]\nwhere = ["."]\n'
            'include = ["sol", "sol.core", "sol.corpus"]\nnamespaces = false\n',
            encoding="utf-8",
        )
        built = subprocess.run(
            [sys.executable, "-B", "-c",
             "import setuptools.build_meta as build, sys; build.build_wheel(sys.argv[1])",
             str(destination)],
            cwd=stage, text=True, capture_output=True,
        )
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        wheel = next(destination.glob("*.whl"))
        installed = fixture / "unpacked-core-only"
        with zipfile.ZipFile(wheel) as archive:
            members = archive.namelist()
            self.assertEqual({name for name in members if name.endswith(".py")}, selected)
            self.assertTrue(all(name in selected or ".dist-info/" in name for name in members))
            info = next(name for name in members if name.endswith("/METADATA"))
            metadata = Parser().parsestr(archive.read(info).decode("utf-8"))
            self.assertEqual(metadata["Name"], "sol-core-boundary-fixture")
            self.assertFalse(metadata.get_all("Requires-Dist"))
            self.assertFalse(any(name.endswith("/entry_points.txt") for name in members))
            archive.extractall(installed)
        for directory in ("reader", "workspace", "terminal"):
            self.assertFalse((installed / "sol" / directory).exists())
        corpus = fixture / "invented-corpus"
        passage_id, body = write_runtime_corpus(corpus)
        from sol.corpus.contract import initialize_corpus_identity
        initialize_corpus_identity(corpus)  # Explicit fixture setup, never automatic protocol behavior.
        fingerprints = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in corpus.iterdir() if path.is_file()}
        elsewhere = fixture / "outside-source-and-installation"
        elsewhere.mkdir()
        program = """
import builtins, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
forbidden = ('sol.reader', 'sol.workspace', 'sol.terminal', 'markdown_it',
             'sol.corpus.extraction', 'sol.corpus.ingest', 'sol.corpus.backends', 'opendataloader_pdf',
             'prompt_toolkit', 'rich', 'textual', 'pypdf', 'pdfplumber')
original_import = builtins.__import__
def guard(name, *args, **kwargs):
    if any(name == prefix or name.startswith(prefix + '.') for prefix in forbidden):
        raise AssertionError('Core-only fixture imported forbidden component ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard
from sol import core
assert Path(core.__file__).parents[2] == Path(sys.argv[1])
assert core.API_VERSION == 1
corpus = Path(sys.argv[2])
snapshot = core.load_snapshot(corpus)
assert isinstance(snapshot, core.CorpusSnapshot)
core.verify_snapshot_current(snapshot)
book = core.load_corpus_book(corpus)
assert isinstance(book, core.Book)
passage = book.find_passage(sys.argv[3])
assert isinstance(passage, core.Passage)
reference = core.resolve_reference(book, sys.argv[3])
assert isinstance(reference, core.Reference)
assert reference.requested_id == reference.target_id == passage.identifier
assert reference.chain == (passage.identifier,)
packet = core.capture_reference(snapshot, passage.identifier)
checked = core.check_reference(snapshot, core.decode_reference(core.encode_reference(packet)))
assert checked.requested_id == checked.target_id == passage.identifier
assert core.PROTOCOL_VERSION == packet['version'] == 1
node, path = core.resolve_path('/being/synthetic', (), book.root)
assert isinstance(node, core.Node)
assert core.child_by_name(book.root, 'being') is node.parent
assert core.node_path(node) == path == ('BEING', 'synthetic.txt')
assert core.alias('00-synthetic.txt') == 'synthetic'
assert core.presentation_text(passage.text) == sys.argv[4]
assert not any(name == prefix or name.startswith(prefix + '.')
               for name in sys.modules for prefix in forbidden)
print(json.dumps({'api_version': core.API_VERSION, 'id': reference.target_id,
                  'path': core.display_path(path), 'text': passage.text}))
"""
        environment = os.environ.copy()
        environment.pop("SOL_CORPUS", None)
        environment["XDG_CONFIG_HOME"] = str(fixture / "isolated-config")
        environment["XDG_DATA_HOME"] = str(fixture / "isolated-data")
        inspected = subprocess.run(
            [sys.executable, "-I", "-B", "-c", program, str(installed), str(corpus), passage_id, body],
            cwd=elsewhere, env=environment, text=True, capture_output=True,
        )
        self.assertEqual(inspected.returncode, 0, inspected.stdout + inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout), {
            "api_version": 1, "id": passage_id, "path": "/BEING/synthetic.txt", "text": body,
        })
        self.assertEqual({path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in corpus.iterdir() if path.is_file()}, fingerprints)
        self.assertFalse((fixture / "isolated-config").exists())
        self.assertFalse((fixture / "isolated-data").exists())

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
    if name.split('.')[0] in {'markdown_it', 'opendataloader_pdf'}:
        raise AssertionError("Installed reader must not import an extraction or Markdown backend")
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_parser
sol = importlib.import_module("sol.reader.app")
assert Path(sol.__file__).parents[2] == Path(sys.argv[1])
assert not (Path(sys.argv[1]) / "local-corpus").exists()
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
            for arguments in (["--passage", passage_id, "--json"], ["-r", "--json"]):
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

    def test_installed_temporary_shell_random_and_sourcefree_guide_create_no_private_storage(self):
        installed = Path(self.temporary.name) / "installed-launch-modes"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        corpus = Path(self.temporary.name) / "temporary-reader-corpus"
        passage_id, body = write_runtime_corpus(corpus)
        elsewhere = Path(self.temporary.name) / "launch-modes-outside-checkout"
        elsewhere.mkdir()
        data = Path(self.temporary.name) / "launch-modes-data"
        environment = os.environ.copy()
        environment.pop("SOL_CORPUS", None)
        environment["XDG_CONFIG_HOME"] = str(Path(self.temporary.name) / "launch-modes-config")
        environment["XDG_DATA_HOME"] = str(data)
        program = """
import builtins, importlib, sys
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def block_optional_and_profiles(name, *args, **kwargs):
    if (name.split('.')[0] in {'markdown_it', 'rich', 'textual', 'prompt_toolkit', 'opendataloader_pdf'}
            or name in {'sol.workspace.profiles', 'sol.workspace.catalog'}):
        raise AssertionError('Temporary/one-shot reader imported ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_optional_and_profiles
sol = importlib.import_module('sol.reader.app')
def block_pdf(*args, **kwargs):
    raise AssertionError('Installed reader must not extract a PDF')
sol.load_book = block_pdf
if sys.argv[2:] == ['guide']:
    def block_book(*args, **kwargs):
        raise AssertionError('Source-free guide must not load a corpus')
    sol.load_corpus_book = block_book
raise SystemExit(sol.cli(sys.argv[2:]))
"""
        cases = [
            (["--corpus", str(corpus), "-n", "--ui", "prompt"], "first /being\nexit\n"),
            (["--corpus", str(corpus), "-r", "--json"], ""),
            (["guide"], ""),
        ]
        for arguments, commands in cases:
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, "-I", "-c", program, str(installed), *arguments],
                    cwd=elsewhere, env=environment, input=commands,
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("\x1b", result.stdout)
                self.assertFalse(data.exists(), "Temporary and one-shot modes must create no private storage")
                if "-r" in arguments:
                    returned = json.loads(result.stdout)
                    self.assertEqual(returned["id"], passage_id)
                    self.assertEqual(returned["text"], body)
                elif "-n" in arguments:
                    self.assertIn(body, " ".join(result.stdout.split()))
                else:
                    self.assertIn("START IN YOUR TERMINAL", result.stdout)
                    self.assertIn("sol -n", result.stdout)
                    self.assertIn("sol -r", result.stdout)

    def test_installed_default_shell_requires_both_labels_and_resumes_attributed_work(self):
        installed = Path(self.temporary.name) / "installed-shell-onboarding"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        corpus = Path(self.temporary.name) / "shell-onboarding-corpus"
        passage_id, body = write_runtime_corpus(corpus)
        elsewhere = Path(self.temporary.name) / "shell-onboarding-outside-checkout"
        elsewhere.mkdir()
        data = Path(self.temporary.name) / "shell-onboarding-data"
        environment = os.environ.copy()
        environment.pop("SOL_CORPUS", None)
        environment["XDG_CONFIG_HOME"] = str(Path(self.temporary.name) / "shell-onboarding-config")
        environment["XDG_DATA_HOME"] = str(data)
        program = """
import builtins, importlib, sys
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def block_optional(name, *args, **kwargs):
    if name.split('.')[0] in {'markdown_it', 'rich', 'textual', 'prompt_toolkit', 'opendataloader_pdf'}:
        raise AssertionError('Installed basic reader imported optional dependency ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_optional
module = importlib.import_module(sys.argv[2])
if sys.argv[2] == 'sol.reader.app':
    def block_pdf(*args, **kwargs):
        raise AssertionError('Installed reader must not extract a PDF')
    module.load_book = block_pdf
    entry = module.cli
else:
    entry = module.main
status = entry(sys.argv[3:])
if status == 2:
    assert sys.stdin.read() == 'first /being\\nexit\\n', 'Setup consumed noninteractive commands'
raise SystemExit(status)
"""

        def run(module, arguments, *, commands="", expected_status=0):
            result = subprocess.run(
                [sys.executable, "-I", "-c", program, str(installed), module, *arguments],
                cwd=elsewhere, env=environment, input=commands,
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, expected_status, result.stdout + result.stderr)
            self.assertNotIn("\x1b", result.stdout)
            return result

        run("sol.corpus.contract", [str(corpus), "--initialize-identity"])
        base = ["--corpus", str(corpus)]
        for supplied in ([], ["--workspace", "installed-reading"], ["--actor", "Installed author"]):
            with self.subTest(supplied=supplied):
                result = run("sol.reader.app", [*base, *supplied], commands="first /being\nexit\n", expected_status=2)
                self.assertIn("--workspace NAME --actor NAME", result.stderr)
                self.assertIn("sol -n", result.stderr)
                self.assertIn("sol -r", result.stderr)
                self.assertFalse(data.exists(), "Rejected onboarding must not create private storage")
        selected = [*base, "--workspace", "installed-reading", "--actor", "Installed author"]
        opened = run("sol.reader.app", selected,
                     commands='first /being\nnote add "A private installed-reader question."\nexit\n')
        self.assertIn("Actor: Installed author", opened.stdout)
        self.assertTrue((data / "sol" / "profiles.sqlite3").is_file())
        self.assertTrue((data / "sol" / "workspaces" / "installed-reading.sqlite3").is_file())
        # Inspection remains one-shot and needs no actor; it must preserve the saved passage.
        inspection = [*base, "--workspace", "installed-reading"]
        resumed = json.loads(run("sol.reader.app", [*inspection, "--resume", "--json"]).stdout)
        self.assertEqual(resumed["id"], passage_id)
        self.assertEqual(resumed["text"], body)
        exported = json.loads(run("sol.reader.app", [*inspection, "--workspace-export"]).stdout)
        self.assertEqual(exported["schema_version"], 3)
        self.assertEqual(exported["state"]["current_id"], passage_id)
        self.assertEqual(len(exported["annotations"]), 1)
        self.assertEqual(exported["annotations"][0]["actor"], "Installed author")
        note = exported["annotations"][0]
        self.assertEqual(note["revision"], 1)
        self.assertEqual([row["kind"] for row in exported["annotation_history"]], ["created"])
        edited = run("sol.reader.app", selected, commands=(
            f'note edit {note["id"]} "A revised installed-reader question." --expect-revision 1\n'
            f'note history {note["id"]}\nexit\n'))
        self.assertIn("A revised installed-reader question.", edited.stdout)
        final = json.loads(run("sol.reader.app", [*inspection, "--workspace-export"]).stdout)
        self.assertEqual(final["annotations"][0]["revision"], 2)
        self.assertEqual(final["annotations"][0]["actor"], note["actor"])
        self.assertEqual(final["annotations"][0]["target_id"], note["target_id"])
        self.assertEqual(final["annotations"][0]["content_sha256"], note["content_sha256"])
        self.assertEqual(final["state"], exported["state"], "Editing must not create a reading checkpoint")
        self.assertEqual([row["kind"] for row in final["annotation_history"]], ["created", "edited"])

    def test_installed_explicit_upgrade_preserves_legacy_workspace_and_baseline(self):
        installed = Path(self.temporary.name) / "installed-upgrade"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        corpus = Path(self.temporary.name) / "upgrade-corpus"
        passage_id, body = write_runtime_corpus(corpus)
        storage = Path(self.temporary.name) / "upgrade-storage"
        storage.mkdir()
        elsewhere = Path(self.temporary.name) / "upgrade-outside-checkout"
        elsewhere.mkdir()
        environment = os.environ.copy()
        environment.pop("SOL_CORPUS", None)
        environment["XDG_CONFIG_HOME"] = str(Path(self.temporary.name) / "upgrade-config")
        environment["XDG_DATA_HOME"] = str(Path(self.temporary.name) / "upgrade-data")
        program = """
import builtins, importlib, sys
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def block_optional(name, *args, **kwargs):
    if name.split('.')[0] in {'markdown_it', 'rich', 'textual', 'prompt_toolkit', 'opendataloader_pdf'}:
        raise AssertionError('Installed upgrade imported optional dependency ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_optional
module = importlib.import_module(sys.argv[2])
if sys.argv[2] == 'sol.reader.app':
    def block_pdf(*args, **kwargs):
        raise AssertionError('Installed upgrade must not extract a PDF')
    module.load_book = block_pdf
    entry = module.cli
else:
    entry = module.main
raise SystemExit(entry(sys.argv[3:]))
"""

        def run(module, arguments, *, commands="", expected_status=0):
            result = subprocess.run(
                [sys.executable, "-I", "-c", program, str(installed), module, *arguments],
                cwd=elsewhere, env=environment, input=commands,
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, expected_status, result.stdout + result.stderr)
            self.assertNotIn("\x1b", result.stdout)
            return result

        run("sol.corpus.contract", [str(corpus), "--initialize-identity"])
        manifest = json.loads((corpus / "corpus.json").read_text(encoding="utf-8"))
        legacy = storage / "legacy.sqlite3"
        note_id = "cccccccc-0000-4000-8000-000000000003"
        timestamp = "2026-01-01T00:00:00Z"
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        # Frozen version-1 DDL is deliberately used rather than creating a new
        # current workspace and mutating it into an unrepresentative old database.
        fixture = """
from contextlib import closing
import json, sqlite3, sys
sys.path.insert(0, sys.argv[1])
from sol.workspace.store import APPLICATION_ID, _SCHEMA
with closing(sqlite3.connect(sys.argv[2])) as connection, connection:
    for statement in _SCHEMA:
        connection.execute(statement)
    connection.execute('PRAGMA application_id = ' + str(APPLICATION_ID))
    connection.execute('PRAGMA user_version = 1')
    manifest = json.loads(sys.argv[3])
    provenance = {'edition': manifest['edition'], 'source': manifest['source']}
    connection.execute('INSERT INTO workspace_metadata VALUES(1,1,?,?,?)',
                       (manifest['corpus_id'], json.dumps(provenance), sys.argv[6]))
    connection.execute('INSERT INTO annotations(id,target_id,body,actor,created_at,updated_at,content_sha256) '
                       'VALUES(?,?,?,?,?,?,?)',
                       (sys.argv[4], sys.argv[5], 'Legacy question without an invented history.',
                        'Installed legacy author', sys.argv[6], sys.argv[6], sys.argv[7]))
"""
        created = subprocess.run(
            [sys.executable, "-I", "-c", fixture, str(installed), str(legacy),
             json.dumps(manifest), note_id, passage_id, timestamp, digest],
            cwd=elsewhere, env=environment, capture_output=True, text=True,
        )
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        before_digest = hashlib.sha256(legacy.read_bytes()).hexdigest()
        arguments = ["--corpus", str(corpus), "--workspace", "legacy", "--workspace-dir", str(storage)]
        original = json.loads(run("sol.reader.app", [*arguments, "--workspace-export"]).stdout)
        self.assertEqual(original["schema_version"], 1)
        self.assertNotIn("annotation_history", original)
        self.assertIsNone(original["annotations"][0]["revision"])
        upgraded = storage / "legacy-v3.sqlite3"
        result = json.loads(run("sol.reader.app", [*arguments, "--workspace-upgrade", str(upgraded), "--json"]).stdout)
        self.assertEqual(result["upgraded_copy"], str(upgraded))
        self.assertEqual(result["source_workspace"], str(legacy))
        self.assertEqual(result["schema_version"], 3)
        self.assertEqual(hashlib.sha256(legacy.read_bytes()).hexdigest(), before_digest)
        if os.name == "posix":
            self.assertEqual(upgraded.stat().st_mode & 0o777, 0o600)
        copy_arguments = ["--corpus", str(corpus), "--workspace", "legacy-v3", "--workspace-dir", str(storage)]
        baseline = json.loads(run("sol.reader.app", [*copy_arguments, "--workspace-export"]).stdout)
        self.assertEqual(baseline["schema_version"], 3)
        self.assertEqual(len(baseline["annotation_history"]), 1)
        snapshot = baseline["annotation_history"][0]
        self.assertEqual(snapshot["kind"], "legacy_baseline")
        self.assertIsNone(snapshot["editor"])
        self.assertEqual(snapshot["created_at"], timestamp)
        self.assertEqual(snapshot["updated_at"], timestamp)
        self.assertNotEqual(snapshot["recorded_at"], timestamp)
        self.assertEqual(snapshot["actor"], "Installed legacy author")
        for key in ("id", "target_id", "body", "actor", "created_at", "updated_at", "content_sha256"):
            self.assertEqual(baseline["annotations"][0][key], original["annotations"][0][key])
        published_digest = hashlib.sha256(upgraded.read_bytes()).hexdigest()
        run("sol.reader.app", [*arguments, "--workspace-upgrade", str(upgraded)], expected_status=2)
        self.assertEqual(hashlib.sha256(upgraded.read_bytes()).hexdigest(), published_digest)
        edited = run("sol.reader.app", [*copy_arguments, "--actor", "Installed legacy author"], commands=(
            f'note edit {note_id} "An explicitly audited revision." --expect-revision 1\nexit\n'))
        self.assertIn("revision 2", edited.stdout)
        after = json.loads(run("sol.reader.app", [*copy_arguments, "--workspace-export"]).stdout)
        self.assertEqual(after["annotations"][0]["body"], "An explicitly audited revision.")
        self.assertEqual(after["annotations"][0]["revision"], 2)
        self.assertEqual(after["annotations"][0]["content_sha256"], digest)
        self.assertEqual([row["kind"] for row in after["annotation_history"]], ["legacy_baseline", "edited"])
        self.assertEqual(hashlib.sha256(legacy.read_bytes()).hexdigest(), before_digest)

    def test_installed_workspace_identity_resume_and_export_need_no_optional_dependencies(self):
        installed = Path(self.temporary.name) / "installed-workspace"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        corpus = Path(self.temporary.name) / "workspace-corpus"
        passage_id, body = write_runtime_corpus(corpus, pending_review=True)
        storage = Path(self.temporary.name) / "workspace-storage"
        elsewhere = Path(self.temporary.name) / "workspace-outside-checkout"
        elsewhere.mkdir()
        environment = os.environ.copy()
        environment.pop("SOL_CORPUS", None)
        environment["XDG_CONFIG_HOME"] = str(Path(self.temporary.name) / "workspace-config")
        environment["XDG_DATA_HOME"] = str(Path(self.temporary.name) / "workspace-data")
        program = """
import builtins
import importlib
import sys
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def block_optional(name, *args, **kwargs):
    if name.split(".")[0] in {"markdown_it", "rich", "textual", "prompt_toolkit", "opendataloader_pdf"}:
        raise AssertionError("Installed workspace must not import optional dependency " + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_optional
module = importlib.import_module(sys.argv[2])
if sys.argv[2] == "sol.reader.app":
    def block_pdf(*args, **kwargs):
        raise AssertionError("Installed workspace must not extract a PDF")
    module.load_book = block_pdf
    entry = module.cli
else:
    entry = module.main
raise SystemExit(entry(sys.argv[3:]))
"""

        def run(module, arguments, *, expected_status=0):
            result = subprocess.run(
                [sys.executable, "-I", "-c", program, str(installed), module, *arguments],
                cwd=elsewhere, env=environment, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, expected_status, result.stdout + result.stderr)
            self.assertNotIn("\x1b", result.stdout)
            return result.stdout

        initialized = run("sol.corpus.contract", [str(corpus), "--initialize-identity"])
        self.assertIn("Initialized corpus identity", initialized)
        identity = json.loads((corpus / "corpus.json").read_text(encoding="utf-8"))["corpus_id"]
        arguments = ["--corpus", str(corpus), "--workspace", "wheel-study",
                     "--workspace-dir", str(storage), "--actor", "Installed reader"]
        first = json.loads(run("sol.reader.app", [*arguments, "--first", "/being", "--json"]))
        self.assertEqual(first["id"], passage_id)
        self.assertEqual(first["workspace"]["corpus_id"], identity)
        resumed = json.loads(run("sol.reader.app", [*arguments, "--resume", "--json"]))
        self.assertEqual(resumed["id"], passage_id)
        self.assertEqual(resumed["workspace"]["revision"], first["workspace"]["revision"])
        plain = run("sol.reader.app", [*arguments, "--resume", "--plain"])
        self.assertEqual(" ".join(plain.split()), body)
        second = json.loads(run("sol.reader.app", [*arguments, "--first", "/being", "--json"]))
        historical = json.loads(run("sol.reader.app", [*arguments, "--resume", "--resume-revision",
                                             str(first["workspace"]["revision"]), "--json"]))
        self.assertEqual(historical["id"], passage_id)
        self.assertEqual(historical["workspace"]["revision"], second["workspace"]["revision"] + 1)
        health = json.loads(run("sol.reader.app", [*arguments, "--workspace-check", "--json"]))
        self.assertEqual(health["format"], "sol-workspace-health")
        self.assertEqual(health["status"], "no_workspace_issues_detected")
        self.assertEqual(health["corpus_freshness"]["state"], "current")
        self.assertEqual(health["counts"]["pending_source_review"], 1)
        self.assertEqual(health["review_provenance_binding"], "text_and_pdf_fingerprint_only")
        for scope in (["--corpus", str(corpus)], arguments):
            queue = json.loads(run("sol.reader.app", [*scope, "--review-queue", "--within", "/being",
                                          "--limit", "1", "--json"]))
            self.assertEqual([record["id"] for record in queue], [passage_id])
            self.assertEqual(queue[0]["transcription_status"], "needs_review")
        backup = storage / "wheel-study-backup.sqlite3"
        backed_up = json.loads(run("sol.reader.app", [*arguments, "--workspace-backup", str(backup), "--json"]))
        self.assertEqual(backed_up["backup"], str(backup))
        self.assertEqual(backed_up["corpus_id"], identity)
        if os.name == "posix":
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        backup_digest = hashlib.sha256(backup.read_bytes()).hexdigest()
        run("sol.reader.app", [*arguments, "--workspace-backup", str(backup)], expected_status=2)
        self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), backup_digest)
        backup_arguments = ["--corpus", str(corpus), "--workspace", "wheel-study-backup",
                            "--workspace-dir", str(storage)]
        restored_backup = json.loads(run("sol.reader.app", [*backup_arguments, "--resume", "--json"]))
        self.assertEqual(restored_backup["workspace"]["revision"], historical["workspace"]["revision"])
        backup_export = json.loads(run("sol.reader.app", [*backup_arguments, "--workspace-export"]))
        self.assertEqual(len(backup_export["history"]), 3)
        exported = json.loads(run("sol.reader.app", [*arguments, "--workspace-export"]))
        self.assertEqual(exported["format"], "sol-workspace")
        self.assertEqual(exported["corpus_id"], identity)
        self.assertEqual(exported["state"]["current_id"], passage_id)
        self.assertEqual(exported["history"][0]["actor"], "Installed reader")
        self.assertEqual(exported["history"], backup_export["history"])
        self.assertTrue((storage / "wheel-study.sqlite3").is_file())

    def test_installed_markdown_inquiry_export_preserves_json_and_private_state(self):
        installed = Path(self.temporary.name) / "installed-inquiry-export"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        corpus = Path(self.temporary.name) / "inquiry-export-corpus"
        passage_id, body = write_runtime_corpus(corpus)
        storage = Path(self.temporary.name) / "inquiry-export-storage"
        storage.mkdir()
        elsewhere = Path(self.temporary.name) / "inquiry-export-outside-checkout"
        elsewhere.mkdir()
        data = Path(self.temporary.name) / "inquiry-export-data"
        environment = os.environ.copy()
        environment.pop("SOL_CORPUS", None)
        environment["XDG_CONFIG_HOME"] = str(Path(self.temporary.name) / "inquiry-export-config")
        environment["XDG_DATA_HOME"] = str(data)
        program = """
import builtins, importlib, socket, sys, urllib.request
sys.path.insert(0, sys.argv[1])
def block_network(*args, **kwargs):
    raise AssertionError('Inquiry export must not access the network')
socket.socket.connect = block_network
socket.socket.connect_ex = block_network
socket.create_connection = block_network
urllib.request.urlopen = block_network
urllib.request.OpenerDirector.open = block_network
original_import = builtins.__import__
def block_optional(name, *args, **kwargs):
    if (name.split('.')[0] in {'markdown_it', 'rich', 'textual', 'prompt_toolkit', 'opendataloader_pdf', 'requests', 'httpx'}
            or name in {'sol.workspace.profiles', 'sol.workspace.catalog', 'sol.terminal.source', 'sol.terminal.kitty'}):
        raise AssertionError('Inquiry export imported unrelated dependency ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_optional
module = importlib.import_module(sys.argv[2])
if sys.argv[2] == 'sol.reader.app':
    def block_pdf(*args, **kwargs):
        raise AssertionError('Inquiry export must not extract a PDF')
    module.load_book = block_pdf
    entry = module.cli
else:
    entry = module.main
raise SystemExit(entry(sys.argv[3:]))
"""

        def run(module, arguments, expected_status=0):
            result = subprocess.run(
                [sys.executable, "-I", "-c", program, str(installed), module, *arguments],
                cwd=elsewhere, env=environment, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, expected_status, result.stdout + result.stderr)
            self.assertNotIn("\x1b", result.stdout)
            return result

        run("sol.corpus.contract", [str(corpus), "--initialize-identity"])
        original_note = '*Private question:* Does this determination presuppose another?\n```\nLiteral fence.\n```'
        revised_note = original_note + '\n![unfetched](https://example.invalid/private.png)'
        database = storage / "inquiry.sqlite3"
        fixture = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from sol.workspace.store import Workspace
manifest = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
provenance = {key: manifest[key] for key in ('edition', 'source')}
with Workspace(Path(sys.argv[3]), manifest['corpus_id'], provenance, actor='Invented reader') as store:
    store.save_state({'cwd': '/BEING', 'scope': '/BEING', 'current_id': sys.argv[4], 'previous_cwd': None})
    store.set_bookmark('beginning', sys.argv[4])
    note = store.add_annotation(sys.argv[4], sys.argv[5], sys.argv[7])
    store.update_annotation(note['id'], sys.argv[6], expected_revision=1)
    store.save_comparison('determinations', [sys.argv[4], 'aaaaaaaa-0000-4000-8000-000000000001'], 'How do they differ?')
    store.add_review(sys.argv[4], 'inspected', 'No PDF was opened.', sys.argv[7], '0' * 64)
    store.add_relation(sys.argv[4], 'aaaaaaaa-0000-4000-8000-000000000001', 'compares-with', 'A reader assertion.')
"""
        seeded = subprocess.run(
            [sys.executable, "-I", "-c", fixture, str(installed), str(corpus / "corpus.json"),
             str(database), passage_id, original_note, revised_note,
             hashlib.sha256(body.encode("utf-8")).hexdigest()],
            cwd=elsewhere, env=environment, capture_output=True, text=True,
        )
        self.assertEqual(seeded.returncode, 0, seeded.stdout + seeded.stderr)
        before_database = hashlib.sha256(database.read_bytes()).hexdigest()
        before_corpus = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in corpus.iterdir() if path.is_file()}
        arguments = ["--corpus", str(corpus), "--workspace", "inquiry",
                     "--workspace-dir", str(storage), "--workspace-export"]
        before_json = json.loads(run("sol.reader.app", arguments).stdout)
        report = run("sol.reader.app", [*arguments, "--export-format", "markdown"]).stdout
        self.assertTrue(report.startswith("# "))
        self.assertIn(passage_id, report)
        self.assertIn(original_note, report)
        self.assertIn(revised_note, report)
        self.assertNotIn(body, report, "Canonical text must be opt-in")
        included = run("sol.reader.app", [*arguments, "--export-format", "markdown", "--include-passages"]).stdout
        self.assertIn(body, included)
        self.assertIn("Invented reader", included)
        self.assertIn("How do they differ?", included)
        self.assertIn("No PDF was opened.", included)
        self.assertIn("A reader assertion.", included)
        after_json = json.loads(run("sol.reader.app", [*arguments, "--export-format", "json"]).stdout)
        before_json.pop("exported_at")
        after_json.pop("exported_at")
        self.assertEqual(before_json, after_json, "Markdown inspection must preserve JSON export data")
        self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before_database)
        self.assertEqual({path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in corpus.iterdir() if path.is_file()}, before_corpus)
        self.assertFalse(data.exists(), "Read-only export must create no actor registry or default workspace")
        self.assertFalse(list(elsewhere.glob("*.sol-workspace.*")), "No automatic report file may be created")
        run("sol.reader.app", [*arguments, "--include-passages"], expected_status=2)
        run("sol.reader.app", ["--corpus", str(corpus), "-r", "--export-format", "markdown"], expected_status=2)


if __name__ == "__main__":
    unittest.main()
