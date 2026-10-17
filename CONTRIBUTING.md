# Working on SOL

Use Python 3.10 or newer. From a checkout, prepare an isolated environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e . setuptools wheel
.venv/bin/python -B -m unittest discover -s tests
```

The ordinary suite uses invented corpora and temporary workspaces. A private PDF,
model download, GUI terminal, personal workspace or actor profile is unnecessary.
Tests for external engines and real terminal windows skip unless their documented
requirements are available. GitHub Actions runs the public suite on Python 3.10
and 3.14. See [reader acceptance](docs/READER_ACCEPTANCE.md) for the additional
terminal checks; passing unit tests is not evidence of manual reading quality.

## Where behavior belongs

| Area | Owner |
| --- | --- |
| Command syntax and execution mode | `sol/reader/options.py` |
| Startup and dispatch | `sol/reader/app.py` |
| Interactive actor/workspace selection | `sol/reader/launch.py` |
| Optional book command interface | `sol/reader/shell.py` |
| One-shot and book-shell text rendering | `sol/reader/render.py` |
| Semantic reading cursor, selection and history | `sol/reader/actions.py` |
| Fullscreen presentation | `sol/terminal/reader.py` |
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

## Scope of the cleanup

This pass preserves canonical identifiers, the reference protocol, workspace
schemas and installed commands. The redundant `shell` and `corpus` extras remain
compatibility aliases; the PDF compatibility reader remains explicit.

The deeper state-model work still needs a deliberate compatibility design:
`Book` and `CorpusSnapshot` expose caller-owned mutable collections. A frozen
dataclass does not freeze their contents. Do not cache trust or add persistent
lookup indexes over those collections without addressing invalidation. Bounded
batch reference operations avoid repeated verification while keeping strict
generation checks; they do not make snapshots immutable.

Likewise, the reader engine decision remains subject to actual reading trials.
That decision and changes to persistent selected-span work are separate from
mechanical cleanup. No workspace migration or automatic annotation ingestion is
part of this pass.
