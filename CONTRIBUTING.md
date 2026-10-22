# Working on SOL

The five governing documents are [SPECULATIVE](docs/SPECULATIVE.md) (leading), [Architecture](docs/ARCHITECTURE.md),
[BEING](docs/BEING.md), [ESSENCE](docs/ESSENCE.md), and [CORE](docs/CORE.md).
This contributor guide covers operational development procedures, not a separate
architecture. Earlier instructions are in Git history.

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
request against `main` for review. The other agent reviews and merges, except
where a reserved decision waits for the maintainer ([CLAUDE.md](CLAUDE.md)).
Review the diff and stage only task-related files. Never include the private
corpus, source PDF, personal workspaces or unrelated local changes. If pushing
requires resolving divergent history or additional access, report that rather
than force-pushing.

Claude Code tasks are coordinated through [CLAUDE.md](CLAUDE.md),
[the current task](docs/coordination/CURRENT_TASK.md) and
[handoff reports](docs/coordination/HANDOFF.md): one branch and pull request per
task, reviewed before merging.

## Where behavior belongs

| Area | Owner |
| --- | --- |
| Command syntax and execution mode | `sol/app/options.py` |
| Startup and dispatch | `sol/app/main.py`; `sol read` printing in `sol/app/commands.py` |
| First-run PDF import and actor/workspace selection | `sol/corpus/onboarding.py`, `sol/app/launch.py` |
| Optional book command interface | `sol/being/shell.py` |
| One-shot and book-shell text rendering | `sol/being/render.py` |
| Semantic reading cursor, selection and history | `sol/being/actions.py`; layout geometry in `sol/being/quantity/navigation.py`; literal search in `sol/being/quality/search.py` |
| Single fullscreen reader | `sol/being/neovim/reader.py` (controller), `sol/being/neovim/host.py` (payload, launch), `sol/being/neovim/neovim.lua` |
| Reader outline | `sol/being/quality/structure.py`, `sol/being/neovim/neovim_tree.lua` |
| Verified source pages and formula crops | `sol/core/source.py` (capture/render); `sol/being/source_view.py` (viewers) |
| Reader theme presets (presentation only) | `sol/presentation/theme.py` (palettes, names and defaults) |
| Complete checkout installation | `scripts/install.py` |
| Checked read-only surface projections | `sol/being/surface.py`; typography in `sol/being/quality/typography.py` |
| Generic terminal escaping | `sol/presentation/text.py` |
| Workspace operations and persistence guards | `sol/being/workspace/reader.py`, `sol/being/workspace/store.py` |
| Verified corpus and portable references | `sol.core`, backed by `sol/corpus/contract.py` |
| Shared CommonMark visibility and plain-text projection | `sol/corpus/markdown.py` |

New interfaces should call workspace service methods (`WorkspaceReader`) rather
than writing workspace tables directly. Domain operations
retain author checks, source freshness and optimistic revision checks. Keep
source-codepoint positions separate from wrapped rows and UTF-8 byte columns.

UI behavior tests keep a fresh isolated asyncio loop per test, using the normal
application loop mode to avoid recording creation stacks for every UI task. For
asyncio creation-stack and slow-callback diagnostics, run the same suite with
`PYTHONASYNCIODEBUG=1 .venv/bin/python -B -m unittest discover -s tests`.
Assertions, worker synchronization and loop cleanup are the same in both modes.

Tests share corpus builders through `tests/fixtures_corpus.py`. Do not borrow a
different TestCase's setup methods. Patch the module that owns an operation;
historical re-exports from `sol.app.main` do not own those operations.

## Archives

The installed wheel contains `sol` and its subpackages. The source archive also
includes public documentation, scripts and tests.
Packaging checks copy the actual source tree into a temporary build directory,
add synthetic private sentinels, inspect both archives and run checks from the
unpacked source archive. They do not copy the local book or personal databases.

SOL has one reader, the Neovim-backed one; its Lua assets are included in the
wheel. Earlier reader experiments are in Git history; keep engine changes
dependent on reading trials rather than adding more frontends.
Bare `sol` opens the Neovim-backed reader. See [BEING](docs/BEING.md#2-what-is-implemented)
for workspace boundaries, bounded section transitions, controls and acceptance checks.

## Scope of the cleanup

The 21 October cleanup preserved canonical identifiers, the reference protocol
and workspace schemas; it removed `sol-kitty`, `sol compare`, the legacy PDF
reader and the empty `shell`, `corpus` and `extraction` extras (see CHANGELOG).
The only optional extra is `essence`.

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
