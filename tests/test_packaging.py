"""Build and inspect distributable archives using only public project files."""
from __future__ import annotations

import configparser
from email.parser import Parser
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import venv
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILES = {path.relative_to(ROOT).as_posix() for path in (ROOT / "sol").rglob("*.py")}
PACKAGE_ASSETS = {path.relative_to(ROOT).as_posix() for path in (ROOT / "sol" / "terminal").glob("*.lua")}
PACKAGE_ASSETS.update({"sol/essence/encyclopedia.json", "sol/essence/methods.json",
                       "sol/terminal/fonts/LibertinusMono-Regular.ttf", "sol/terminal/fonts/OFL.txt"})
ENTRY_POINTS = {
    "sol": "sol:cli",
    "sol-window": "sol.terminal.window:main",
    "sol-corpus": "sol.corpus.convert:main",
    "sol-corpus-check": "sol.corpus.contract:main",
}
PUBLIC_FILES = {"pyproject.toml", "MANIFEST.in", "README.md", "CONTRIBUTING.md", "CHANGELOG.md",
                "LICENSE"} | PACKAGE_FILES | PACKAGE_ASSETS
for directory, suffixes in (("docs", {".md"}), ("tests", {".py"}),
                            ("scripts", {".py"})):
    PUBLIC_FILES.update(path.relative_to(ROOT).as_posix()
                        for path in (ROOT / directory).rglob("*")
                        if path.is_file() and path.suffix in suffixes)

from fixtures_corpus import write_runtime_corpus


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
        self.assertTrue(PACKAGE_ASSETS <= set(names))
        self.assertTrue(all(name in PACKAGE_FILES | PACKAGE_ASSETS
                            or ".dist-info/" in name for name in names))

    def test_installed_encyclopedia_loads_offline_without_optional_dependencies(self):
        installed = Path(self.temporary.name) / "installed-encyclopedia"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        program = """
import builtins, socket, sys
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(('sol.core', 'sol.corpus', 'textual', 'torch', 'transformers')):
        raise AssertionError(name)
    return original_import(name, *args, **kwargs)
def no_network(*args, **kwargs):
    raise AssertionError('network access')
builtins.__import__ = guarded
socket.create_connection = no_network
socket.socket.connect = no_network
from sol.essence.encyclopedia import load_catalog, entry_markdown
catalog = load_catalog()
assert len(catalog['entries']) == 9
for entry in catalog['entries']:
    assert entry['quote'] in entry_markdown(catalog, entry)
from sol.essence.methods import load_methods, method_markdown
methods = load_methods()
assert {entry['id'] for entry in methods['entries']} == {'words', 'word-comparison', 'tfidf', 'sentences', 'prose', 'check'}
assert any(method['id'] == 'tfidf' for method in methods['entries'])
from sol.essence import analyze_tfidf
assert callable(analyze_tfidf)
for method in methods['entries']:
    assert method['summary'] in method_markdown(method)
print(catalog['license'])
"""
        result = subprocess.run([sys.executable, "-I", "-c", program, str(installed)],
                                cwd=self.temporary.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "CC BY-SA 4.0")

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
        self.assertEqual(metadata["License-Expression"], "GPL-3.0-or-later")
        self.assertEqual(metadata.get_all("License-File"), ["LICENSE"])
        with zipfile.ZipFile(self.wheel) as archive:
            self.assertEqual(archive.read(info + "/licenses/LICENSE"),
                             (ROOT / "LICENSE").read_bytes())
        self.assertEqual(dict(entry_points["console_scripts"]), ENTRY_POINTS)
        requirements = metadata.get_all("Requires-Dist") or []
        self.assertEqual(set(metadata.get_all("Provides-Extra") or []), {"essence"})
        self.assertEqual(len(requirements), 3)
        # ESSENCE's interface is the only optional dependency, and never a base one.
        essence = [requirement for requirement in requirements if 'extra == "essence"' in requirement]
        self.assertEqual([requirement.split(";")[0].strip() for requirement in essence], ["textual<9,>=8"])
        base = [requirement for requirement in requirements if ";" not in requirement]
        self.assertEqual(set(base), {"markdown-it-py<4,>=3", "opendataloader-pdf==2.5.13"})

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

    def test_wheel_contains_one_reader_and_no_historical_fullscreen_engine(self):
        with zipfile.ZipFile(self.wheel) as archive:
            names = set(archive.namelist())
        self.assertIn("sol/terminal/neovim_reader.py", names)
        self.assertNotIn("sol/terminal/reader.py", names)
        self.assertNotIn("sol/terminal/reading_layout.py", names)
        self.assertFalse(any(name.startswith("experiments/") for name in names))

    def test_source_archive_runs_its_reader_source_guard_checks(self):
        destination = Path(self.temporary.name) / "source-archive-check"
        with tarfile.open(self.sdist) as archive:
            # This archive was just built from our disposable source fixture.
            archive.extractall(destination)
        source = next(destination.iterdir())
        self.assertTrue((source / "sol" / "terminal" / "neovim.lua").is_file())
        self.assertFalse((source / "experiments").exists())
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
             "-p", "test_reader_surface_export_guards.py"],
            cwd=source, env=environment, text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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

    def test_installed_reader_help_and_guide_do_not_import_presentation_dependencies(self):
        installed = Path(self.temporary.name) / "reader-help-wheel"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        program = """
import builtins, importlib, sys
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def guard(name, *args, **kwargs):
    if (name.split('.')[0] in {'markdown_it', 'opendataloader_pdf'}
            or name in {'experiments.reader_surfaces.baseline', 'sol.workspace.launch', 'sol.workspace.profiles'}):
        raise AssertionError('Help imported a runtime reader component ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard
app = importlib.import_module('sol.reader.app')
app.discover_corpus = lambda *args, **kwargs: None
raise SystemExit(app.cli(sys.argv[2:]))
"""
        for arguments in (["--help"], ["--guide"], ["guide"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", program, str(installed), *arguments],
                    cwd=self.temporary.name, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("reader", result.stdout.lower())

    def test_built_wheel_neovim_backend_has_no_checkout_import_dependency(self):
        installed = Path(self.temporary.name) / "neovim-reader-wheel"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        corpus = Path(self.temporary.name) / "neovim-reader-corpus"
        write_runtime_corpus(corpus)
        from sol.corpus.contract import initialize_corpus_identity
        initialize_corpus_identity(corpus)
        program = """
import builtins, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def guard(name, *args, **kwargs):
    if name == 'experiments' or name.startswith('experiments.'):
        raise AssertionError('Installed reader depends on checkout research code ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard
from sol.reader import app
from sol.terminal import neovim
assert Path(neovim.__file__).with_name('neovim.lua').is_file()
neovim.validate_environment = lambda width: '/invented/nvim'
def native(payload, executable, **options):
    assert payload['records'] and payload['restore']['cursor_offset'] == 0
    return 0, {'action': 'quit', 'packet': payload['restore']}
neovim.launch_payload = native
raise SystemExit(app.main(['being', '-n', '--corpus', sys.argv[2]]))
"""
        result = subprocess.run([sys.executable, "-I", "-B", "-c", program, str(installed), str(corpus)],
                                cwd=self.temporary.name, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("nvim"), "installed Neovim is required for the wheel module smoke test")
    def test_installed_wheel_opens_headlessly_without_user_lua_modules(self):
        """Run all packaged Lua modules, not a mocked native launch boundary."""
        from sol.terminal import neovim
        version_root = Path(self.temporary.name) / "lua-wheel-version"
        version_root.mkdir()
        version_env = neovim._isolated_environment(version_root, version_root / "input", version_root / "output")
        version = subprocess.run([shutil.which("nvim"), "--version"], env=version_env,
                                 capture_output=True, text=True, timeout=10)
        match = re.match(r"NVIM v(\d+)\.(\d+)", version.stdout)
        if version.returncode or match is None or tuple(map(int, match.groups())) < (0, 11):
            self.skipTest("Neovim 0.11 or newer is required")
        directory = Path(self.temporary.name) / "lua-wheel-headless"
        directory.mkdir()
        environment = directory / "environment"
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
        python = environment / "bin" / "python"
        install = subprocess.run([str(python), "-I", "-m", "pip", "install", "--no-index", "--no-deps",
                                  "--no-compile", "--ignore-installed", str(self.wheel)],
                                 capture_output=True, text=True, timeout=60)
        self.assertEqual(install.returncode, 0, install.stdout + install.stderr)
        corpus = directory / "corpus"
        write_runtime_corpus(corpus)
        from sol.corpus.contract import initialize_corpus_identity
        initialize_corpus_identity(corpus)
        program = r'''
import json, os, subprocess, sys
from pathlib import Path
import sol
from sol import core
from sol.reader.surface import sample_from_book
from sol.terminal import neovim
root = Path(sys.argv[1])
assert Path(sol.__file__).is_relative_to(Path(sys.prefix)), 'reader came from outside the installed wheel'
book = core.load_corpus_book(root / 'corpus')
payload = neovim.build_payload(sample_from_book(book, count=1))
payload.update(navigation={'previous': False, 'next': False}, notice='')
input_path, output_path = root / 'input.json', root / 'output.json'
input_path.write_text(json.dumps(payload), encoding='utf-8')
env = neovim._isolated_environment(root, input_path, output_path)
module_directory = Path(neovim.__file__).parent
fake = root / 'untrusted'
fake.mkdir()
for module in module_directory.glob('neovim_*.lua'):
    (fake / module.name).write_text("error('loaded untrusted user Lua module')\n")
env['SOL_FAKE_LUA'] = str(fake)
scenario = root / 'headless.lua'
scenario.write_text(r"""
local fake = assert(vim.env.SOL_FAKE_LUA)
vim.opt.runtimepath:prepend(fake)
package.path = fake .. '/?.lua;' .. package.path
for _, name in ipairs({'neovim_text', 'neovim_view', 'neovim_panels', 'neovim_requests',
  'neovim_footnotes', 'neovim_notes', 'neovim_controls', 'neovim_tree'}) do
  package.preload[name] = function() error('loaded user package.preload') end
end
dofile(vim.env.SOL_NVIM_ADAPTER)
local reader = assert(SOLNvimReader)
assert(#reader.records == 1)
assert(reader.capture().reference.reference.target_id == reader.records[1].id)
local expected = vim.fn.fnamemodify(vim.env.SOL_NVIM_ADAPTER, ':h') .. '/neovim_view.lua'
assert(debug.getinfo(reader.capture, 'S').source == '@' .. expected)
reader.context()
vim.api.nvim_feedkeys(vim.keycode('<Esc>'), 'xt', false)
reader.export()
-- A missing package module fails instead of falling back to any user loader.
assert(os.rename(expected, expected .. '.saved'))
local ok, problem = pcall(dofile, vim.env.SOL_NVIM_ADAPTER)
assert(os.rename(expected .. '.saved', expected))
assert(not ok and tostring(problem):find('neovim_view.lua', 1, true))
assert(not tostring(problem):find('untrusted', 1, true))
vim.cmd('qa!')
""", encoding='utf-8')
result = subprocess.run([sys.argv[2], '-u', 'NONE', '--noplugin', '-i', 'NONE', '-n', '--headless', '-l', str(scenario)],
                        cwd=root, env=env, capture_output=True, text=True, timeout=15)
assert result.returncode == 0, result.stdout + result.stderr
assert json.loads(output_path.read_text())['packet']['reference']['reference']['target_id'] == book.passages[0].identifier
'''
        result = subprocess.run([str(python), "-I", "-B", "-c", program, str(directory), shutil.which("nvim")],
                                cwd=directory, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_installed_default_reader_and_temporary_reader_route_without_a_tui(self):
        """Exercise the built artifact's routing, not an interactive display."""
        installed = Path(self.temporary.name) / "reader-routing-wheel"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        corpus = Path(self.temporary.name) / "reader-routing-corpus"
        passage_id, _ = write_runtime_corpus(corpus)
        from sol.corpus.contract import initialize_corpus_identity
        initialize_corpus_identity(corpus)
        program = """
import builtins, importlib, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def guard(name, *args, **kwargs):
    if name.split('.')[0] in {'markdown_it', 'opendataloader_pdf'}:
        raise AssertionError('Routing fixture imported a live presentation dependency ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard
app = importlib.import_module('sol.reader.app')
view = importlib.import_module('sol.terminal.neovim')
events = []
def validate(*args):
    events.append('terminal')
view.validate_environment = validate
def identity(book, args):
    assert events == ['terminal']
    events.append('identity')
    args.workspace = 'installed-reading'
    args.actor = 'Installed reader'
    args.workspace_dir = Path(sys.argv[3])
app.shell_identity = identity
def read(book, workspace_reader=None, **options):
    events.append('reader')
    assert book.find_passage(sys.argv[4]).identifier == sys.argv[4]
    assert bool(workspace_reader) == ('-n' not in sys.argv[5:])
    return 0
app.run_reader = read
def reject_shell(*args, **kwargs):
    raise AssertionError('Normal launch must not open the command interface')
app.run_shell = reject_shell
assert app.cli(['--corpus', sys.argv[2], *sys.argv[5:]]) == 0
assert events == (['terminal', 'reader'] if '-n' in sys.argv[5:]
                  else ['terminal', 'identity', 'reader'])
print(json.dumps(events))
"""
        for number, arguments in enumerate(([], ["-n"], ["being"])):
            with self.subTest(arguments=arguments):
                private = Path(self.temporary.name) / f"reader-routing-private-{number}"
                environment = os.environ.copy()
                environment.pop("SOL_CORPUS", None)
                environment["XDG_CONFIG_HOME"] = str(private / "config")
                environment["XDG_DATA_HOME"] = str(private / "data")
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", program, str(installed), str(corpus),
                     str(private / "workspaces"), passage_id, *arguments],
                    cwd=self.temporary.name, env=environment, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                if "-n" in arguments:
                    self.assertFalse(private.exists(), "Temporary reading must create no private storage")
                else:
                    self.assertTrue((private / "workspaces" / "installed-reading.sqlite3").is_file())

    def test_installed_default_reader_checks_terminal_before_source_or_storage(self):
        installed = Path(self.temporary.name) / "reader-preflight-wheel"
        with zipfile.ZipFile(self.wheel) as archive:
            archive.extractall(installed)
        private = Path(self.temporary.name) / "reader-preflight-private"
        environment = os.environ.copy()
        environment["XDG_CONFIG_HOME"] = str(private / "config")
        environment["XDG_DATA_HOME"] = str(private / "data")
        program = """
import importlib, sys
sys.path.insert(0, sys.argv[1])
app = importlib.import_module('sol.reader.app')
view = importlib.import_module('sol.terminal.neovim')
def unavailable(*args):
    raise ValueError('Invented unavailable terminal')
def forbidden(*args, **kwargs):
    raise AssertionError('Rejected terminal must not discover a source or onboard')
view.validate_environment = unavailable
app.discover_corpus = app.load_corpus_book = app.shell_identity = forbidden
assert app.cli(sys.argv[2:]) == 2
"""
        for arguments in ([], ["-n"], ["being"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", program, str(installed), *arguments],
                    cwd=self.temporary.name, env=environment, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Invented unavailable terminal", result.stderr)
                self.assertFalse(private.exists())

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
        installed = Path(self.temporary.name) / "sentence-study-wheel"
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
forbidden = ('sol.reader', 'sol.workspace', 'sol.terminal',
             'markdown_it', 'rich', 'textual', 'openai', 'pypdf', 'pdfplumber',
             'sol.corpus.convert', 'sol.corpus.extraction', 'opendataloader_pdf')
original_import = builtins.__import__
def guard(name, *args, **kwargs):
    if any(name == prefix or name.startswith(prefix + '.') for prefix in forbidden):
        raise AssertionError('Experiment imported unrelated component ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guard
from sol.essence.cli import main
from sol.essence.sentences import check_sentence_result
from sol.core import load_snapshot
output = io.StringIO()
with contextlib.redirect_stdout(output):
    assert main(['sentences', '--corpus', sys.argv[2], '--json']) == 0
result = json.loads(output.getvalue())
assert result['summary']['sentences'] == 1
assert check_sentence_result(load_snapshot(sys.argv[2]), result) == result
assert not any(name == prefix or name.startswith(prefix + '.')
               for name in sys.modules for prefix in forbidden)
print(json.dumps({'sentences': result['summary']['sentences']}))
"""
        completed = subprocess.run([sys.executable, "-I", "-B", "-c", program, str(installed), str(corpus)],
                                   cwd=self.temporary.name, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"sentences": 1})
        self.assertEqual(before, {path.name: path.read_bytes() for path in corpus.iterdir()})

    def test_core_only_wheel_proves_interface_dependency_boundary(self):
        """Release-gate fixture only: this is not another installable SOL product."""
        fixture = Path(self.temporary.name) / "core-only-release-gate"
        stage, destination = fixture / "source", fixture / "dist"
        stage.mkdir(parents=True)
        destination.mkdir()
        root = Path(__file__).resolve().parents[1]
        selected = {"sol/__init__.py", "sol/corpus/__init__.py", "sol/corpus/contract.py",
                    "sol/corpus/errors.py", "sol/corpus/markdown.py"}
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
             'rich', 'textual', 'pypdf', 'pdfplumber')
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
    if (name.split('.')[0] in {'markdown_it', 'rich', 'textual', 'opendataloader_pdf'}
            or name in {'sol.workspace.profiles', 'sol.workspace.catalog'}):
        raise AssertionError('Temporary/one-shot reader imported ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_optional_and_profiles
sol = importlib.import_module('sol.reader.app')
if sys.argv[2:] == ['guide']:
    def block_book(*args, **kwargs):
        raise AssertionError('Source-free guide must not load a corpus')
    sol.load_corpus_book = block_book
raise SystemExit(sol.cli(sys.argv[2:]))
"""
        cases = [
            (["--corpus", str(corpus), "--shell"], "first /being\nexit\n"),
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
                elif "--shell" in arguments:
                    self.assertIn(body, " ".join(result.stdout.split()))
                else:
                    self.assertIn("START READING", result.stdout)
                    self.assertIn("sol -n", result.stdout)
                    self.assertIn("sol -r", result.stdout)

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
    if name.split('.')[0] in {'markdown_it', 'rich', 'textual', 'opendataloader_pdf'}:
        raise AssertionError('Installed upgrade imported optional dependency ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_optional
module = importlib.import_module(sys.argv[2])
if sys.argv[2] == 'sol.reader.app':
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
    if name.split(".")[0] in {"markdown_it", "rich", "textual", "opendataloader_pdf"}:
        raise AssertionError("Installed workspace must not import optional dependency " + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_optional
module = importlib.import_module(sys.argv[2])
if sys.argv[2] == "sol.reader.app":
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
    if (name.split('.')[0] in {'markdown_it', 'rich', 'textual', 'opendataloader_pdf', 'requests', 'httpx'}
            or name in {'sol.workspace.profiles', 'sol.workspace.catalog', 'sol.core.source'}):
        raise AssertionError('Inquiry export imported unrelated dependency ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = block_optional
module = importlib.import_module(sys.argv[2])
if sys.argv[2] == 'sol.reader.app':
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
