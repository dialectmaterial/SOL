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

## Claude Code: Named landmarks in the reader

**Status:** In review
**Branch:** `claude/landmarks`
**Requested:** 20 October 2026, by the maintainer (reader backlog, item 5)

### Goal

Beside the three quick markers, the reader can name the current place, list
the named places and open one, through the workspace's existing named
bookmarks.

### Scope

[BEING §2–3](../BEING.md#2-what-is-implemented),
[reader backlog](proposals/READER_GAPS_AFTER_ZATHURA.md): the marker panel in
`sol/terminal/neovim_reader.py`, `sol/terminal/neovim_controls.lua` and
`neovim_panels.lua` (a list panel), tests, BEING, CHANGELOG.

### Constraints

No workspace schema change; temporary sessions keep landmarks for the session
only, like markers. No change to `sol/reader/actions.py` navigation (Codex's
task).

### Acceptance

Controller and headless Neovim tests; documentation check and full suite.

## Codex: Measure and cut reader navigation latency

**Status:** Ready
**Branch:** `codex/navigation-latency`
**Requested:** 20 October 2026, by the maintainer via Claude (reader backlog, item 4)

### Goal

Measured, smaller delays for the moves a reader makes most: `Ctrl-N`/`Ctrl-P`
between occurrences in the passage already shown (now a full view reload,
about 0.9 s), `j`/`k` across a section boundary, `b`/`n`, and the outline.

### Scope

[BEING §2](../BEING.md#2-what-is-implemented), [CORE §§5–7](../CORE.md#5-source-bound-positions-and-typography):
`sol/reader/actions.py`, `sol/terminal/neovim_reader.py` view preparation,
`sol/terminal/neovim_requests.lua`/`neovim_view.lua` if a move can stay in
Neovim, `scripts/reader_timings.py`, tests, BEING, CHANGELOG.

### Constraints

Keep source verification before anything is saved and the refused-move
guarantees. Record before/after medians on the real book in the handoff, without
private text. No change to the marker panel or landmark UI (Claude's task).

### Acceptance

Timings before and after; regression tests for any fast path; documentation
check and full suite.

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
