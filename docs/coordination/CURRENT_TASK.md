# Current tasks

At most one task per implementing agent, each on its own branch, with scopes
that do not touch the same files. The maintainer (or ChatGPT, through the
maintainer) writes the tasks; each agent works only on the task assigned to it
and reports in [HANDOFF](HANDOFF.md). This file is coordination, not design
authority: a task must agree with [Architecture](../ARCHITECTURE.md),
[BEING](../BEING.md), [ESSENCE](../ESSENCE.md) and [CORE](../CORE.md), and cites
them rather than restating them. Backlog: the
[Codex reader and workspace proposal](proposals/CODEX_READER_WORKSPACE_PLAN.md).

Status moves `Ready` → `In progress` → `In review` → `Done`. When a task is done,
replace it with the agent's next one; Git history keeps the old ones.

## Claude Code: ESSENCE stage 3, the interface side

**Status:** In progress
**Branch:** `claude/essence-comparison-ui`
**Requested:** 18 October 2026, by the maintainer

### Goal

In ESSENCE, a target/reference count shows Codex's comparison measures, can be
exported as CSV or TSV, and a word's source passage opens in the reader;
returning to the earlier reading position stays a separate step. A long count
can be cancelled.

### Scope

[ESSENCE §4–§5 stage 3](../ESSENCE.md#5-prioritized-experiments),
[BEING §6](../BEING.md#6-being--essence-without-terminal-dogma):
`sol/essence/tui/`, `sol/terminal/` (the reader side of opening a source),
tests, ESSENCE §4, BEING §6 and CHANGELOG. Also the two stage 1 leftovers:
quitting the reader while ESSENCE is open saves ESSENCE's state, and reader
popups (`c`, search) centre in the reader's columns rather than over ESSENCE.

### Constraints

Call `sol.essence.compare_words` / `export_word_comparison` (PR #29) rather
than computing measures in the interface. Opening a source goes through the
reader's ordinary guarded navigation; an artifact's locations are never
authority to navigate without CORE's checks. No existing reader key remapped.
Do not touch `sol/essence/` outside `sol/essence/tui/` (Codex's task).

### Acceptance

Textual pilot and headless Neovim tests for the comparison table, export,
source opening and return, cancellation, quitting with ESSENCE open, and popup
placement; documentation check and full suite pass; a real-book run reported.

## Codex: ESSENCE sentence study without CORE

**Status:** Ready
**Branch:** `codex/sentence-file-provider`
**Requested:** 18 October 2026, by the maintainer

### Goal

The sentence study runs on an ordinary UTF-8 text file as well as on the CORE
corpus, through the same provider boundary as the word engine, so that `S` can
later move into the ESSENCE interface and ESSENCE §4 decision 7 (CORE optional)
holds for a second study.

### Scope

[ESSENCE §4 decision 7, §5 Experiment A](../ESSENCE.md#5-prioritized-experiments):
`sol/essence/` except `sol/essence/tui/`, tests, ESSENCE §2 and §5, and
CHANGELOG. Accept `CoreProvider`/`FileProvider` (and their scopes, including
spans) in the sentence study; `sol analyze sentences --file PATH [--span S E]`;
`sol analyze check` support with explicit file paths, as for words. A Python
function the interface can call, documented in the handoff.

### Constraints

`punctuation-rules-v1` and existing `sol.sentence-study` v1 artifacts are
unchanged and still check; a file result needs a new version or a separately
named method if its shape must differ. The reader's `S` keeps working
unchanged. File input stores no book text, only digests and offsets. No new
dependency. Do not touch `sol/essence/tui/`, `sol/terminal/`, `sol/core/`,
`sol/corpus/`, `sol/reader/` or `pyproject.toml` (Claude Code's task).

### Acceptance

Tests for both providers, spans that cut sentences, Unicode, empty input, a
changed file refused by `check`, CORE-free import for file input, and existing
sentence artifacts byte-for-byte unchanged. Documentation check and full suite
pass.

<!--
Template for a next task — copy into the agent's slot and fill in.

## <Agent>: <Task title>

**Status:** Ready
**Branch:** `<agent>/<short-task-name>`
**Requested:** <date>, by <who>

### Goal
<One or two sentences: the outcome, not the steps.>

### Scope
<What may change. Cite authority sections, e.g. BEING §5. Name the files or
packages, so that parallel tasks do not overlap.>

### Constraints
<What must not change; contracts to preserve; the other agent's files.>

### Acceptance
<Checks that decide "done": tests, a manual check, a document updated.>
-->
