# Working on SOL

The four human-facing design authorities are [Architecture](docs/ARCHITECTURE.md),
[BEING](docs/BEING.md), [ESSENCE](docs/ESSENCE.md), and [CORE](docs/CORE.md).
This contributor guide covers operational development procedures, not a separate
architecture. Earlier instructions are preserved in the [legacy archive](docs/legacy/README.md).

Use Python 3.10 or newer. From a checkout, prepare an isolated environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e . setuptools wheel
.venv/bin/python -B scripts/check_docs.py
.venv/bin/python -B -m unittest discover -s tests
```

The ordinary suite uses invented corpora and temporary workspaces. A private PDF,
model download, GUI terminal, personal workspace or actor profile is unnecessary.
Tests for external engines and real terminal windows skip unless their documented
requirements are available. GitHub Actions runs the public suite on Python 3.10
and 3.14. See [BEING acceptance](docs/BEING.md#8-acceptance-checklist-for-agents) for the additional
terminal checks; passing unit tests is not evidence of manual reading quality.

The Python 3.14 CI job also installs Zsh and ripgrep to exercise the native shell
pipeline. That external-tool check skips explicitly when those programs are absent.

## Branch and pull request workflow

For agent-assisted work in this repository, work on a branch, never directly on
`main`: commit completed, verified changes there, push the branch and open a pull
request against `main` for review. The maintainer merges. Review the diff and
stage only task-related files. Never include the private corpus, source PDF,
personal workspaces or unrelated local changes. If pushing requires resolving
divergent history or additional access, report that rather than force-pushing.

Claude Code tasks are coordinated through [CLAUDE.md](CLAUDE.md),
[the current task](docs/coordination/CURRENT_TASK.md) and
[handoff reports](docs/coordination/HANDOFF.md): one branch and pull request per
task, reviewed before merging.

## Where behavior belongs

| Area | Owner |
| --- | --- |
| Command syntax and execution mode | `sol/reader/options.py` |
| Startup and dispatch | `sol/reader/app.py` |
| First-run PDF import and actor/workspace selection | `sol/reader/onboarding.py`, `sol/reader/launch.py` |
| Optional book command interface | `sol/reader/shell.py` |
| One-shot and book-shell text rendering | `sol/reader/render.py` |
| Semantic reading cursor, selection and history | `sol/reader/actions.py` |
| Single fullscreen reader | `sol/terminal/neovim_reader.py`, `sol/terminal/neovim.py`, `sol/terminal/neovim.lua` |
| Reader outline | `sol/reader/structure.py`, `sol/terminal/neovim_tree.lua` |
| Verified source pages and formula crops | `sol/terminal/source.py` |
| Reader theme presets (presentation only) | `sol/terminal/theme.py`; names in `sol/reader/options.py` |
| Complete checkout installation | `scripts/install.py` |
| Checked read-only surface projections | `sol/reader/surface.py` |
| Generic terminal escaping and POSIX utilities | `sol/terminal/text.py`, `sol/terminal/tty.py` |
| Workspace operations and persistence guards | `sol/workspace/reader.py`, `sol/workspace/store.py` |
| Workspace command syntax and summaries | `sol/workspace/commands.py` |
| Verified corpus and portable references | `sol.core`, backed by `sol/corpus/contract.py` |
| Shared CommonMark visibility and plain-text projection | `sol/corpus/markdown.py` |

New interfaces should call workspace service methods rather than constructing
book-shell commands or writing workspace tables directly. Domain operations
retain author checks, source freshness and optimistic revision checks. Keep
source-codepoint positions separate from wrapped rows and UTF-8 byte columns.

Tests share corpus builders through `tests/fixtures_corpus.py`. Do not borrow a
different TestCase's setup methods. Patch the module that owns an operation;
historical re-exports from `reader.app` do not own those operations.

## Archives and optional experiments

The installed wheel contains `sol` and its subpackages. The source archive also
includes public documentation, tests and the reader experiments they exercise.
Packaging checks copy the actual source tree into a temporary build directory,
add synthetic private sentinels, inspect both archives and run checks from the
unpacked source archive. They do not copy the local book or personal databases.

Research adapters remain opt-in, checkout/source-archive tools. Their presence in
the source archive does not install them as reader commands. Keep engine adoption
dependent on the existing reading trials rather than adding more frontends.
The original Neovim experiment reuses the installed reader backend. Its Lua
assets are included in the wheel; the historical prompt_toolkit fullscreen
baseline and wrapping code remain research-only, outside the installed package.
Bare `sol` opens the Neovim-backed reader. See [BEING](docs/BEING.md#2-what-is-implemented)
for workspace boundaries, bounded section transitions, controls and acceptance checks.

## Scope of the cleanup

This pass preserves canonical identifiers, the reference protocol, workspace
schemas and installed commands. The redundant `shell`, `corpus` and `extraction` extras remain
compatibility aliases; the PDF compatibility reader remains explicit.

The deeper state-model work still needs a deliberate compatibility design:
`Book` and `CorpusSnapshot` expose caller-owned mutable collections. A frozen
dataclass does not freeze their contents. Do not cache trust or add persistent
lookup indexes over those collections without addressing invalidation. Bounded
batch reference operations avoid repeated verification while keeping strict
generation checks; they do not make snapshots immutable.

The single reader still needs actual human reading trials; automated terminal
checks alone do not establish usability. Persistent selected-span work requires
its own compatibility design. This consolidation does not migrate workspaces or
automatically ingest annotations.
