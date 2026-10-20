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

## Claude Code: The printed page in a zoomable PDF viewer

**Status:** In progress
**Branch:** `claude/pdf-companion`
**Requested:** 20 October 2026, by the maintainer (reader backlog, item 2)

### Goal

From the current passage, one key opens the verified PDF in a PDF viewer
(Zathura when installed) at the passage's physical page, so the printed page
can be zoomed and read in context; the crop popup of `s` stays.

### Scope

[BEING §5](../BEING.md#5-mathematical-notation-and-source-fidelity),
[reader backlog](proposals/READER_GAPS_AFTER_ZATHURA.md):
`sol/terminal/source.py`, the reader key and help in `sol/terminal/neovim_*.lua`
only where the source action lives, tests, BEING §5, CHANGELOG.

### Constraints

Opens the private, fingerprint-checked PDF snapshot, never an unverified file.
No new dependency; a viewer that is missing falls back to the crop. Does not
touch search (Codex's task).

### Acceptance

Unit tests for the viewer command and fallback; a real session on the book.
Documentation check and full suite pass.

## Codex: Complete reader search

**Status:** In progress
**Branch:** `codex/complete-search`
**Requested:** 20 October 2026, by the maintainer (reader backlog, item 1)

### Goal

`/` reaches every match in the book: occurrence-level next/previous, the total
count and the current position shown (for example "12 of 87"), and no
20-passage ceiling.

### Scope

[BEING §2](../BEING.md#2-what-is-implemented),
[reader backlog](proposals/READER_GAPS_AFTER_ZATHURA.md):
`sol/terminal/neovim_reader.py` search request, `sol/reader/actions.py` search
navigation, the Lua search display, tests, BEING, CHANGELOG.

### Constraints

Preserve canonical text, offsets, UUIDs and the refused-move guarantees.
Literal search semantics unchanged. No change to `sol/terminal/source.py`
(Claude's task).

### Acceptance

Tests for counts, occurrence stepping across passages and sections, and a
common word with more than 20 passages; documentation check and full suite.

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
