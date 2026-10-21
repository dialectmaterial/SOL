# Restructuring stage A — inventory of the BEING side

**Prepared:** 21 October 2026, by Claude Code, against `main` at `c0f4697` (after the cleanup).
**Scope:** `sol/__init__.py`, `sol/__main__.py`, `sol/reader/`, `sol/terminal/`, `sol/workspace/`, entry points.
**Method:** import edges were extracted mechanically from every `import` and `from … import` in the package (including imports inside functions), with relative imports resolved; "tests" lists the test modules that import or patch the module by name. Responsibilities are read from the code, not the module names. Companion: `INVENTORY_ESSENCE_CORE.md` (Codex).

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
| `tty` | 84 | POSIX terminal primitives | **nothing** | **none** — dead since the comparison viewer was removed |

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

- **Dead code:** `sol.terminal.tty` has no importers and no tests.
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
