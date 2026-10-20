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

## Claude Code: Real-terminal check of the new reader features

**Status:** In review
**Branch:** `claude/reader-smoke`
**Requested:** 20 October 2026, by the maintainer via Claude (reader backlog)

### Goal

Drive the installed reader on the real book in a real terminal (tmux, a
temporary `-n` session) through `/` counts, `Ctrl-N`, `gp`, `M`/`L`, `S` and
`keys.json`, and fix what fails.

### Scope

Whatever the check shows, in `sol/terminal/`; BEING §7 records what was
exercised. No change to view preparation or `sol/reader/actions.py` (Codex).

### Acceptance

A reported session; fixes with regression tests; documentation check and full
suite.

## Codex: Faster section and outline moves

**Status:** Ready
**Branch:** `codex/section-latency`
**Requested:** 20 October 2026, by the maintainer via Claude (reader backlog, item 4)

### Goal

`j`/`k` across a section boundary, `b`/`n` and outline jumps take clearly less
than the measured ~1 s, measured with `scripts/reader_timings.py`.

### Scope

[BEING §2](../BEING.md#2-what-is-implemented), [CORE §§5–7](../CORE.md#5-source-bound-positions-and-typography):
view preparation in `sol/terminal/neovim_reader.py` and `sol/terminal/neovim.py`
payload building, `sol/reader/actions.py`, tests, BEING, CHANGELOG.

### Constraints

Do not relax or cache source verification: changing CORE's per-reference
fingerprint policy is a **reserved** decision; propose it in the handoff
instead. Keep the refused-move guarantees. No change to Lua key handling
(Claude's task).

### Acceptance

Before/after medians in the handoff; regression tests; documentation check and
full suite.

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
