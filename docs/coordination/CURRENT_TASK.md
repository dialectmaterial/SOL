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

## Claude Code: Visual audit of the reader, as options for the maintainer

**Status:** In progress
**Branch:** `claude/visual-audit`
**Requested:** 21 October 2026, by the maintainer via Claude ([BEING §4](../BEING.md#4-theming-and-typography-next-bounded-task) "Not yet done")

### Goal

Rendered before/after comparisons of spacing, heading density, status-line
weight and popup intrusion on the real book, in each theme, as concrete options
the maintainer chooses from. Nothing changes the look until chosen.

### Scope

Audit tooling under `scripts/` if needed; no change to the reader's look in
this task.

### Acceptance

An options page for the maintainer; BEING §4 records that the audit was done.

## Codex: A faster full test suite

**Status:** Ready
**Branch:** `codex/test-speed`
**Requested:** 21 October 2026, by the maintainer via Claude

### Goal

`python -B -m unittest discover -s tests` takes clearly less than its current
~150 s on this machine, with the same tests and assertions.

### Scope

`tests/` (fixtures, shared setup, slow helpers), `CONTRIBUTING.md` if the
commands change, CHANGELOG. No product code unless a test-only seam is needed.

### Constraints

No test deleted, skipped or weakened; the same test count (1,807 now, plus
any added). No new dependency (no pytest-xdist). CI configuration unchanged
unless it gets faster too.

### Acceptance

Before/after wall-clock times in the handoff; the slowest tests listed;
documentation check and full suite.

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
