# Restructuring stage A — inventory of the BEING side

**Prepared:** 21 October 2026, by Claude Code, against `main` at `c0f4697` (after the cleanup); **refreshed** 22 October 2026 against `main` at `0f5156a`, which includes #86 (deletion of `sol/terminal/tty.py`) and the empty stage B division packages (#89).
**Scope:** `sol/__init__.py`, `sol/__main__.py`, `sol/reader/`, `sol/terminal/`, `sol/workspace/` (36 Python modules, package initializers included) and the Lua files under `sol/terminal/`, entry points. The empty stage B packages (`sol/being/`, `sol/concept/`, the ESSENCE subdivisions) hold only docstrings and import nothing; they are outside this inventory.
**Method:** import edges were extracted mechanically from every `import` and `from … import` (including imports inside functions), with relative imports resolved. The module tables summarise the product edges; the complete outgoing and reverse ledger, including scripts and tests, is in [§ Mechanical import ledger](#mechanical-import-ledger), with the script that regenerates it. The tables' "Tests" column also counts tests that patch a module by name, which the syntactic ledger does not see. Responsibilities are read from the code, not the module names. Companion: `INVENTORY_ESSENCE_CORE.md` (Codex).

This is a stage A inventory ([SPECULATIVE §7](../../SPECULATIVE.md#7-implementation-sequence)): it proposes **no placement** under Quality, Quantity or Measure. Where code already sits on the wrong side of the present CORE/BEING/ESSENCE boundary, that is recorded as a finding, not a decision.

## Entry points that reach this side

| Command | Entry | Path |
|---|---|---|
| `sol`, `sol being`, `sol guide`, one-shot flags, `--shell`, workspace commands | `sol:cli` | `sol/__init__.py` → `sol.reader.app.cli/main` |
| `sol read FILE` | dispatched in `sol.reader.app.main` | `sol.terminal.commands` |
| `sol reference capture|check` | dispatched in `sol.reader.app.main` | `sol.terminal.reference` |
| `sol essence …` | dispatched in `sol.reader.app.main` | `sol.essence.cli` (ESSENCE side) |
| `sol-window` | `sol.terminal.window:main` | opens a terminal running `python -m sol` |
| `python -m sol` | `sol/__main__.py` | same as `sol` |
| `scripts/install.py` | developer installer | imports `sol.terminal.runtime` for the pinned Neovim |

## Modules

### Package root and initializers

| Module | Lines | What it does | Imports | Imported by |
|---|---:|---|---|---|
| `sol` (`sol/__init__.py`) | 10 | Package docstring, `__version__`, and `cli()`, which imports `sol.reader.app` lazily so importing `sol` loads nothing else | `sol.reader.app` (inside `cli`) | `sol.__main__`; the `sol` console script; `reader.options` and `reader.render` (for `__version__`); several ESSENCE modules and `scripts.reader_timings` only as a package base (`from sol import core`) |
| `sol.__main__` | 6 | `python -m sol`: calls `cli()` | `sol` | — (run by the interpreter) |
| `sol.reader` (`__init__.py`) | 1 | Docstring-only package marker | — | package base of every `sol.reader.*` import |
| `sol.terminal` (`__init__.py`) | 1 | Docstring-only package marker | — | package base of every `sol.terminal.*` import |
| `sol.workspace` (`__init__.py`) | 1 | Docstring-only package marker | — | package base of every `sol.workspace.*` import |

### `sol.reader` — reading actions, CLI and text presentation

| Module | Lines | What it does | Imported by | Tests |
|---|---:|---|---|---|
| `actions` | 891 | `ReadingSession` and `ReaderActions`: the reading state machine (cursor, sections, selection, search results and occurrence visits, history trail, staged moves with rollback, checkpoints through a workspace reader, reference capture/check) | `app`, `render`, `shell`, `surface`, `terminal.neovim_reader` | `test_reader_actions`, `_cursor`, `_context`, `_flow_actions`, `_search_actions`, `_efficiency`, `test_neovim_reader*`, `test_corpus_reader`, `test_footnote_view`, `test_terminal` |
| `navigation` | 100 | Pure layout geometry: character cells, source layout, vertical offsets | `actions` | `test_reader_cursor`, `test_reader_flow_actions` |
| `search` | 176 | Literal search projection: NFC/casefold matching, occurrence spans in canonical text, facsimile-caption exclusion | `actions` | `test_reader_search_actions`, `test_reader_search_projection` |
| `surface` | 286 | `Sample`: a bounded, verified slice of passages with captured references for a view (export guards, detached-change refusal) | `terminal.neovim`, `terminal.neovim_reader` | `test_reader_surface_*`, `test_footnote_view`, `test_packaging` |
| `typography` | 206 | Maps canonical Markdown to styled spans in `plain_text` (emphasis, strong, code, footnote callout offsets) | `terminal.neovim` | `test_reader_typography`, `test_neovim_reader`, `test_reader_surface_neovim_host` |
| `structure` | 26 | Outline payload for the reader's tree (nodes, pages, current section) | `terminal.neovim_reader` | `test_reader_surface_neovim` |
| `render` | 304 | Plain-terminal rendering for one-shot output and the shell: passages, listings, trees, info, search results, the `sol guide` text | `app`, `shell` | `test_terminal_text`, `test_guide`, `test_terminal` |
| `shell` | 196 | The minimal browsing shell (`--shell`) on `input()`/readline | `app` | `test_terminal`, `test_shell_entry`, `test_package_boundaries` |
| `options` | 247 | CLI parser and option validation; **also** the reader theme list, default theme and width | `app`, `terminal.theme`, `terminal.window`, `essence.tui.app`, `essence.tui.__main__` | `test_reader_view_cli`, `test_reader_theme`, `test_package_boundaries` |
| `app` | 417 | CLI composition: corpus discovery, onboarding, workspace commands, one-shot output, dispatch of `read`/`reference`/`essence`, launching the reader or shell | `sol` | most CLI tests |
| `launch` | 103 | Interactive actor/workspace onboarding before the reader | `app` | `test_shell_entry`, `test_workspace_launch` |
| `onboarding` | 88 | First-run import of the audited PDF into a corpus | `app` | `test_first_run`, `test_reader_view_cli` |

### `sol.terminal` — the Neovim reader and terminal host

| Module | Lines | What it does | Imported by | Tests |
|---|---:|---|---|---|
| `neovim` | 415 | Builds the inert JSON payload for a view; launches the isolated Neovim; environment, clipboard and `keys.json` handling | `reader.app`, `neovim_reader` | `test_neovim_reader*`, `test_reader_surface_*`, `test_reader_theme`, `test_user_keys`, … |
| `neovim_reader` | 637 | The reader's controller loop: validates editor requests and runs navigation, search, notes, markers, landmarks, source views, ESSENCE launch and return | `reader.app` | `test_neovim_reader`, `test_reader_view_cli` (+ Lua tests) |
| `neovim*.lua` (10 files) | — | The reader frontend inside Neovim: view, controls, panels, tree, notes, footnotes, ESSENCE pane, requests | loaded by `neovim` | `test_reader_surface_neovim*` |
| `reader_channel` | 101 | Pipe protocol between Python and Neovim | `neovim` | `test_reader_channel`, `test_neovim_reader_alacritty` |
| `runtime` | 13 | Pinned/managed Neovim location | `neovim`, `scripts/install.py` | — |
| `theme` | 165 | Theme palettes as inert highlight data; colour-depth detection | `neovim`, `neovim_reader`, `splash`, `window` | `test_reader_theme` |
| `splash` | 219 | Opening screen while the reader loads | `reader.app`, `reader.launch`, `neovim` | `test_splash` |
| `window` | 109 | `sol-window`: a book-face terminal window | entry point | `test_window` |
| `source` | 627 | Verified PDF snapshot, source-page capture and crops, PDF viewer (Zathura highlight/follow) | `reader.app`, `reader.onboarding`, `neovim_reader` | `test_source_viewer`, `test_first_run`, … |
| `text` | 45 | Terminal-safe text: control escaping, emphasis fallback, `safe_label` | 7 modules incl. `workspace.reader` | `test_terminal_text` |
| `commands` | 139 | `sol read`: resolves a virtual or Markdown path to complete ordered canonical text and prints it | `reader.app` | `test_read_paths`, `test_native_commands` |
| `reference` | 83 | `sol reference capture|check` over the CORE protocol | `reader.app` | `test_reference_cli` |

### `sol.workspace` — personal research state

| Module | Lines | What it does | Imported by | Tests |
|---|---:|---|---|---|
| `store` | 1115 | SQLite workspace: schema 1–3, bookmarks, annotations and revisions, comparisons, reviews, relations, checkpoints, backup/upgrade copies, export snapshot | `reader.app`, `reader.launch`, `catalog`, `lifecycle`, `reader` | `test_workspace`, `test_annotation_revisions`, many reader tests |
| `reader` | 391 | `WorkspaceReader`: binds a store to the loaded book (resolve references, guarded authored writes, resume, render queue/health) | `reader.app`, `reader.launch` | `test_workspace_reader`, reader tests |
| `export` | 389 | JSON and Markdown workspace reports | `reader` | `test_workspace_export` |
| `diagnostics` | 280 | `--workspace-check` health and the review queue | `reader.app`, `reader` | `test_workspace_diagnostics` |
| `catalog` | 131 | Read-only discovery of workspaces for a corpus | `reader.launch`, `lifecycle` | `test_workspace_catalog` |
| `lifecycle` | 279 | `--workspace-list` and `--workspace-delete` (private trash, recovery path) | `reader.app` | `test_workspace_lifecycle`, `test_workspace_management_cli` |
| `profiles` | 122 | Actor-label registry | `reader.app`, `reader.launch`, `launch` | `test_workspace_launch`, … |
| `launch` | 166 | Remembered actor/workspace launch preferences | `reader.app`, `reader.launch` | `test_workspace_launch` |
| `time` | 19 | UTC timestamps | `store`, `catalog`, `diagnostics`, `profiles` | `test_workspace_time` |

## Cohesive groups (should move together)

1. **Reading state:** `reader.actions` with its pure helpers `navigation` and `search`.
2. **View preparation:** `reader.surface`, `reader.typography`, `reader.structure` and `terminal.neovim` (payload building).
3. **The Neovim reader:** `terminal.neovim_reader`, `neovim`, `reader_channel`, `runtime`, the Lua files, `theme`, `splash`, `window`.
4. **Printed source:** `terminal.source` (with the reader's `s`/`S` handling).
5. **Plain-terminal output:** `reader.render`, `reader.shell`, `terminal.text`, `terminal.commands`.
6. **CLI composition:** `reader.app`, `reader.options`, `reader.launch`, `reader.onboarding`, `terminal.reference`.
7. **Workspace:** all of `sol.workspace` (store at its centre; `export`, `diagnostics`, `catalog`, `lifecycle`, `profiles`, `launch`, `time` around it).

## Findings at the present boundaries

- **Dead code (historical):** at `c0f4697`, `sol.terminal.tty` (84 lines of POSIX terminal primitives) had no importers and no tests; #86 deleted it (`d93cc1a`). No module in scope is now without an importer except the entry points `sol.__main__` and `sol.terminal.window`.
- **Developer tooling reaches deep:** `scripts.reader_timings` imports `reader.actions`, `app`, `render`, `surface`, `typography`; `terminal.neovim`, `neovim_reader`, `splash`; and `workspace.reader`, `store`. Any relocation must update it with the product imports; `scripts.install` imports `terminal.runtime`.
- **Themes live in the CLI module:** `reader.options` holds the theme list, defaults and width, so `terminal.theme`, `terminal.window` and **ESSENCE's interface** (`essence.tui.app`, `__main__`) import the reader's option parser to learn the themes.
- **BEING imports ESSENCE directly:** `terminal.neovim_reader` imports `sol.essence.tui` and `sol.essence.tui.context` to open ESSENCE beside the reader; `reader.app` dispatches `sol essence`. The return path (ESSENCE → reader) goes through a terminal escape sequence, not an import.
- **CORE-like services inside BEING packages:** `terminal.source` (verified PDF snapshots and source-page capture), `reader.typography` (Markdown → styled spans, built on `corpus.markdown`), `reader.surface` (verified reference capture for a view) and `terminal.commands`' path resolver all work on canonical data rather than on the screen. `reader.onboarding` drives corpus conversion.
- **Workspace and the terminal:** `workspace.reader` imports `terminal.text` for safe labels, so persistent state depends on a terminal module.
- **Workspace and CORE:** SPECULATIVE gives "shared persistent research state" to CORE; `sol.workspace` is a separate package used only by BEING today, and CORE (§2) still treats workspaces as BEING's.

## Open questions for stage C (reading the *Science of Logic*)

1. Where does the **workspace** belong: CORE's shared persistent research state, or BEING's attributed reading work, or split (store in CORE, authoring in BEING)?
2. Do **reading state and navigation** (`actions`, `navigation`, `search`) correspond to a determination of Quality, Quantity or Measure, or are they the reading environment as such, outside the three?
3. The **printed source** relates the typed text to its physical page (exact correspondence of two forms of the same record): is that a BEING matter, or CORE's provenance?
4. **Typography and view preparation**: a projection of canonical text into what is shown; where does a projection belong?
5. **Plain-terminal output, CLI and shell**: are these presentation infrastructure (outside the hierarchy, like tests and packaging) or part of BEING?
6. The **word tokenizer** (ESSENCE side today): SPECULATIVE §6 notes it might belong under a BEING determination once justified.
7. Should **themes** become shared presentation data, read by both reader and ESSENCE, rather than CLI options?

## Mechanical import ledger

**Scope and reading:** generated from all repository `sol/**/*.py`, `scripts/*.py` and `tests/*.py` at `0f5156a`; rows are printed for the 36 modules in this inventory's scope. The method is Codex's from [INVENTORY_ESSENCE_CORE §9–10](INVENTORY_ESSENCE_CORE.md#9-mechanical-import-and-reverse-import-ledger), changed only in the scope filter, so the two ledgers can be joined. "Imports" lists every import-from base, standard library and third-party names included, with relative imports resolved; `from package import submodule` adds an edge to the submodule, and package-base edges are kept, so a module that imports `sol.x.y` may list `sol.x`. These are syntactic references, function-local imports included: not a runtime load order, not a transitive closure, and blind to string patch targets, subprocess module names and Lua. A dash means no syntactic reference found, not "unused".

| Module | Imports (AST) | Direct product/script importers (AST) | Direct test/fixture importers (AST) |
| --- | --- | --- | --- |
| `sol` | `sol.reader.app` | `scripts.reader_timings`, `sol.__main__`, `sol.essence.corpus_inputs`, `sol.essence.prose`, `sol.essence.sentence_inputs`, `sol.essence.sentences`, `sol.essence.tui.sentences`, `sol.essence.tui.tfidf`, `sol.essence.tui.words`, `sol.essence.word_cli`, `sol.reader.options`, `sol.reader.render` | `tests.fixtures_corpus`, `tests.test_core_protocol`, `tests.test_essence_tui`, `tests.test_footnote_view`, `tests.test_neovim_reader`, `tests.test_prose_inputs`, `tests.test_reader_surface_export_guards`, `tests.test_reader_surface_neovim_host`, `tests.test_sentence_providers`, `tests.test_sentence_study`, `tests.test_terminal`, `tests.test_word_frequencies` |
| `sol.__main__` | `sol` | — | — |
| `sol.reader` | — | `scripts.reader_timings` | `tests.test_analysis_cli`, `tests.test_first_run`, `tests.test_footnote_view`, `tests.test_native_commands`, `tests.test_neovim_reader`, `tests.test_neovim_reader_alacritty`, `tests.test_reader_actions`, `tests.test_reader_efficiency`, `tests.test_reader_surface_export_guards`, `tests.test_reader_theme`, `tests.test_reader_view_cli`, `tests.test_workspace_launch`, `tests.test_workspace_management_cli` |
| `sol.reader.actions` | `__future__`, `contextlib`, `dataclasses`, `hashlib`, `random`, `re`, `sol.core`, `sol.core.models`, `sol.core.paths`, `sol.core.references`, `sol.reader.navigation`, `sol.reader.search`, `unicodedata` | `scripts.reader_timings`, `sol.reader.app`, `sol.reader.render`, `sol.reader.shell`, `sol.reader.surface`, `sol.terminal.neovim_reader` | `tests.fixtures_corpus`, `tests.test_footnote_view`, `tests.test_neovim_reader`, `tests.test_neovim_reader_alacritty`, `tests.test_reader_actions`, `tests.test_reader_context`, `tests.test_reader_cursor`, `tests.test_reader_flow_actions`, `tests.test_reader_search_actions` |
| `sol.reader.app` | `__future__`, `json`, `os`, `pathlib`, `re`, `shlex`, `sol.core.config`, `sol.core.corpus`, `sol.core.models`, `sol.core.paths`, `sol.corpus.edition`, `sol.essence.cli`, `sol.reader.actions`, `sol.reader.launch`, `sol.reader.onboarding`, `sol.reader.options`, `sol.reader.render`, `sol.reader.shell`, `sol.terminal`, `sol.terminal.commands`, `sol.terminal.neovim`, `sol.terminal.neovim_reader`, `sol.terminal.reference`, `sol.terminal.source`, `sol.terminal.text`, `sol.workspace.diagnostics`, `sol.workspace.launch`, `sol.workspace.lifecycle`, `sol.workspace.profiles`, `sol.workspace.reader`, `sol.workspace.store`, `sys` | `scripts.reader_timings`, `sol` | `tests.test_analysis_cli`, `tests.test_corpus_reader`, `tests.test_footnote_view`, `tests.test_guide`, `tests.test_native_commands`, `tests.test_neovim_reader`, `tests.test_neovim_reader_alacritty`, `tests.test_reader_actions`, `tests.test_reader_efficiency`, `tests.test_reader_position`, `tests.test_reader_theme`, `tests.test_reader_view_cli`, `tests.test_shell_entry`, `tests.test_terminal`, `tests.test_workspace_export_cli`, `tests.test_workspace_launch`, `tests.test_workspace_management_cli`, `tests.test_workspace_reader` |
| `sol.reader.launch` | `__future__`, `pathlib`, `sol.core.models`, `sol.terminal`, `sol.workspace.catalog`, `sol.workspace.launch`, `sol.workspace.profiles`, `sol.workspace.reader`, `sol.workspace.store`, `sys` | `sol.reader.app` | — |
| `sol.reader.navigation` | `__future__`, `unicodedata` | `sol.reader.actions` | `tests.test_reader_cursor`, `tests.test_reader_flow_actions` |
| `sol.reader.onboarding` | `__future__`, `hashlib`, `os`, `pathlib`, `shutil`, `sol.core.config`, `sol.core.corpus`, `sol.corpus.convert`, `sol.terminal.source`, `sys`, `tempfile` | `sol.reader.app` | `tests.test_first_run` |
| `sol.reader.options` | `__future__`, `argparse`, `enum`, `pathlib`, `re`, `sol` | `sol.essence.tui.__main__`, `sol.essence.tui.app`, `sol.reader.app`, `sol.terminal.theme`, `sol.terminal.window` | `tests.test_reader_theme`, `tests.test_reader_view_cli` |
| `sol.reader.render` | `__future__`, `copy`, `re`, `shutil`, `sol`, `sol.core.models`, `sol.core.paths`, `sol.corpus.edition`, `sol.reader.actions`, `sol.terminal.text`, `textwrap`, `unicodedata` | `scripts.reader_timings`, `sol.reader.app`, `sol.reader.shell` | `tests.test_terminal_text` |
| `sol.reader.search` | `__future__`, `dataclasses`, `re`, `unicodedata` | `sol.reader.actions` | `tests.test_reader_search_actions`, `tests.test_reader_search_projection` |
| `sol.reader.shell` | `__future__`, `argparse`, `readline`, `shlex`, `sol.core.models`, `sol.core.paths`, `sol.reader.actions`, `sol.reader.render`, `sol.terminal.text` | `sol.reader.app` | `tests.test_terminal` |
| `sol.reader.structure` | `sol.core.models`, `sol.core.paths` | `sol.terminal.neovim_reader` | `tests.test_reader_surface_neovim` |
| `sol.reader.surface` | `__future__`, `copy`, `dataclasses`, `hashlib`, `json`, `sol.core.models`, `sol.core.protocol`, `sol.core.references`, `sol.corpus.contract`, `sol.reader.actions` | `scripts.reader_timings`, `sol.terminal.neovim`, `sol.terminal.neovim_reader` | `tests.test_footnote_view`, `tests.test_reader_surface_export_guards`, `tests.test_reader_surface_neovim`, `tests.test_reader_surface_neovim_alacritty`, `tests.test_reader_surface_neovim_host` |
| `sol.reader.typography` | `__future__`, `bisect`, `dataclasses`, `re`, `sol.corpus.errors`, `sol.corpus.markdown` | `scripts.reader_timings`, `sol.terminal.neovim` | `tests.test_neovim_reader`, `tests.test_reader_surface_neovim_host`, `tests.test_reader_typography` |
| `sol.terminal` | — | `scripts.reader_timings`, `sol.reader.app`, `sol.reader.launch`, `sol.terminal.neovim`, `sol.terminal.neovim_reader` | `tests.test_footnote_view`, `tests.test_neovim_reader`, `tests.test_packaging`, `tests.test_reader_surface_export_guards`, `tests.test_reader_surface_neovim`, `tests.test_reader_surface_neovim_host`, `tests.test_reader_theme`, `tests.test_reference_cli`, `tests.test_source_viewer`, `tests.test_splash`, `tests.test_user_keys`, `tests.test_window` |
| `sol.terminal.commands` | `__future__`, `argparse`, `copy`, `json`, `pathlib`, `posixpath`, `sol.core.config`, `sol.core.corpus`, `sol.core.paths`, `sol.terminal.text`, `sys` | `sol.reader.app` | `tests.test_read_paths` |
| `sol.terminal.neovim` | `__future__`, `copy`, `json`, `os`, `pathlib`, `re`, `shutil`, `sol.core.config`, `sol.reader.surface`, `sol.reader.typography`, `sol.terminal`, `sol.terminal.reader_channel`, `sol.terminal.runtime`, `sol.terminal.text`, `sol.terminal.theme`, `stat`, `subprocess`, `sys`, `tempfile`, `unicodedata` | `scripts.reader_timings`, `sol.reader.app`, `sol.terminal.neovim_reader` | `tests.test_footnote_view`, `tests.test_neovim_reader`, `tests.test_packaging`, `tests.test_reader_surface_export_guards`, `tests.test_reader_surface_neovim`, `tests.test_reader_surface_neovim_alacritty`, `tests.test_reader_surface_neovim_host`, `tests.test_splash`, `tests.test_user_keys` |
| `sol.terminal.neovim_reader` | `__future__`, `atexit`, `dataclasses`, `functools`, `os`, `pathlib`, `shutil`, `sol.core.protocol`, `sol.essence.tui`, `sol.essence.tui.context`, `sol.reader.actions`, `sol.reader.structure`, `sol.reader.surface`, `sol.terminal`, `sol.terminal.source`, `sol.terminal.text`, `sol.terminal.theme`, `sys`, `tempfile`, `unicodedata` | `scripts.reader_timings`, `sol.reader.app` | `tests.test_footnote_view`, `tests.test_neovim_reader` |
| `sol.terminal.reader_channel` | `contextlib`, `json`, `os`, `selectors`, `subprocess` | `sol.terminal.neovim` | `tests.test_reader_channel` |
| `sol.terminal.reference` | `__future__`, `argparse`, `json`, `pathlib`, `sol.core`, `sol.core.wire`, `sys` | `sol.reader.app` | `tests.test_reference_cli` |
| `sol.terminal.runtime` | `os`, `pathlib` | `scripts.install`, `sol.terminal.neovim` | — |
| `sol.terminal.source` | `__future__`, `contextlib`, `copy`, `hashlib`, `json`, `math`, `os`, `pathlib`, `re`, `shlex`, `shutil`, `sol.core.references`, `sol.corpus.contract`, `struct`, `subprocess`, `sys`, `tempfile`, `threading`, `time`, `zlib` | `sol.reader.app`, `sol.reader.onboarding`, `sol.terminal.neovim_reader` | `tests.test_first_run`, `tests.test_neovim_reader`, `tests.test_source_viewer` |
| `sol.terminal.splash` | `__future__`, `math`, `os`, `sol.terminal.theme`, `sys`, `termios`, `threading`, `time` | `scripts.reader_timings`, `sol.reader.app`, `sol.reader.launch`, `sol.terminal.neovim` | `tests.test_splash` |
| `sol.terminal.text` | `__future__`, `os`, `sys`, `unicodedata` | `sol.reader.app`, `sol.reader.render`, `sol.reader.shell`, `sol.terminal.commands`, `sol.terminal.neovim`, `sol.terminal.neovim_reader`, `sol.workspace.reader` | `tests.test_terminal_text` |
| `sol.terminal.theme` | `__future__`, `os`, `re`, `sol.reader.options` | `sol.terminal.neovim`, `sol.terminal.neovim_reader`, `sol.terminal.splash`, `sol.terminal.window` | `tests.test_neovim_reader`, `tests.test_reader_surface_neovim`, `tests.test_reader_theme` |
| `sol.terminal.window` | `__future__`, `argparse`, `os`, `pathlib`, `shutil`, `sol.reader.options`, `sol.terminal.theme`, `subprocess`, `sys` | — | `tests.test_window` |
| `sol.workspace` | — | — | `tests.test_core_models` |
| `sol.workspace.catalog` | `__future__`, `datetime`, `os`, `pathlib`, `re`, `sol.workspace.store`, `sol.workspace.time`, `sqlite3` | `sol.reader.launch`, `sol.workspace.lifecycle` | `tests.test_reader_position`, `tests.test_workspace_catalog` |
| `sol.workspace.diagnostics` | `__future__`, `copy`, `datetime`, `sol.core.references`, `sol.workspace.time` | `sol.reader.app`, `sol.workspace.reader` | `tests.test_workspace_diagnostics` |
| `sol.workspace.export` | `__future__`, `json`, `re`, `unicodedata` | `sol.workspace.reader` | `tests.test_workspace_export` |
| `sol.workspace.launch` | `__future__`, `os`, `pathlib`, `re`, `sol.workspace.profiles`, `sqlite3`, `uuid` | `sol.reader.app`, `sol.reader.launch` | `tests.test_workspace_launch`, `tests.test_workspace_management_cli` |
| `sol.workspace.lifecycle` | `__future__`, `contextlib`, `datetime`, `os`, `pathlib`, `sol.workspace.catalog`, `sol.workspace.store`, `sqlite3`, `stat`, `uuid` | `sol.reader.app` | `tests.test_workspace_lifecycle` |
| `sol.workspace.profiles` | `__future__`, `datetime`, `os`, `pathlib`, `sol.workspace.time`, `sqlite3`, `unicodedata`, `uuid` | `sol.reader.app`, `sol.reader.launch`, `sol.workspace.launch` | `tests.test_shell_entry`, `tests.test_workspace_launch`, `tests.test_workspace_management_cli` |
| `sol.workspace.reader` | `__future__`, `dataclasses`, `hashlib`, `json`, `os`, `pathlib`, `re`, `sol.core.references`, `sol.corpus.contract`, `sol.terminal.text`, `sol.workspace.diagnostics`, `sol.workspace.export`, `sol.workspace.store`, `textwrap` | `scripts.reader_timings`, `sol.reader.app`, `sol.reader.launch` | `tests.test_core_models`, `tests.test_footnote_view`, `tests.test_neovim_reader`, `tests.test_neovim_reader_alacritty`, `tests.test_reader_actions`, `tests.test_reader_context`, `tests.test_reader_position`, `tests.test_reader_search_actions`, `tests.test_workspace_export_cli`, `tests.test_workspace_reader` |
| `sol.workspace.store` | `__future__`, `contextlib`, `datetime`, `fcntl`, `json`, `math`, `os`, `pathlib`, `re`, `sol.workspace.time`, `sqlite3`, `tempfile`, `time`, `typing`, `unicodedata`, `uuid` | `scripts.reader_timings`, `sol.reader.app`, `sol.reader.launch`, `sol.workspace.catalog`, `sol.workspace.lifecycle`, `sol.workspace.reader` | `tests.test_annotation_revisions`, `tests.test_footnote_view`, `tests.test_neovim_reader`, `tests.test_neovim_reader_alacritty`, `tests.test_reader_actions`, `tests.test_reader_context`, `tests.test_reader_position`, `tests.test_reader_search_actions`, `tests.test_reader_view_cli`, `tests.test_shell_entry`, `tests.test_workspace`, `tests.test_workspace_catalog`, `tests.test_workspace_export_cli`, `tests.test_workspace_launch`, `tests.test_workspace_lifecycle`, `tests.test_workspace_management_cli`, `tests.test_workspace_reader` |
| `sol.workspace.time` | `datetime`, `re` | `sol.workspace.catalog`, `sol.workspace.diagnostics`, `sol.workspace.profiles`, `sol.workspace.store` | `tests.test_workspace_time` |

### Reproducing the ledger

Run from the repository root with the standard library only; it reads files and imports nothing from SOL.

```python
import ast
from pathlib import Path

paths = sorted([
    *Path("sol").rglob("*.py"),
    *Path("scripts").glob("*.py"),
    *Path("tests").glob("*.py"),
])
modules = {
    p: str(p.with_suffix("")).replace("/", ".").removesuffix(".__init__")
    for p in paths
}
known = set(modules.values())
edges, imports = {}, {}
for path, module in modules.items():
    deps, names = set(), set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for item in node.names:
                names.add(item.name)
                deps.add(item.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = module.split(".")
                if path.name != "__init__.py":
                    package = package[:-1]
                base = ".".join(
                    package[:len(package) - node.level + 1]
                    + ([base] if base else [])
                )
            names.add(base)
            if base in known:
                deps.add(base)
            for item in node.names:
                child = base + "." + item.name
                if child in known:
                    deps.add(child)
    edges[module], imports[module] = deps, names


def cell(values):
    return ", ".join("`" + v + "`" for v in sorted(values)) or "—"


for path, module in modules.items():
    if not str(path).startswith(("sol/__init__.py", "sol/__main__.py", "sol/reader/", "sol/terminal/", "sol/workspace/")):
        continue
    reverse = [name for name, deps in edges.items() if module in deps]
    product = [name for name in reverse if not name.startswith("tests.")]
    tests = [name for name in reverse if name.startswith("tests.")]
    print("|", cell([module]), "|", cell(imports[module]), "|",
          cell(product), "|", cell(tests), "|")
```
