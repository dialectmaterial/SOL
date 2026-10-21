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

## Claude Code: ESSENCE interface, next improvements

**Status:** Ready
**Branch:** `claude/essence-ui-next`
**Requested:** 21 October 2026, by the maintainer ("First, we need to improve Essence's UI")

### Goal

Continue from the genealogy (#78) on the Encyclopedia and Methods screens, as
the maintainer directs.

### Scope

`sol/essence/tui/` Encyclopedia and Methods screens, `sol/essence/encyclopedia*`,
tests, ESSENCE §7, CHANGELOG. Not the Results screen (Codex).

## Codex: ESSENCE Results in small windows

**Status:** Ready
**Branch:** `codex/essence-results-small`
**Requested:** 21 October 2026, by the maintainer via Claude ("First, we need to improve Essence's UI")

### Goal

The Results screen works beside the reader at 80×24: a word's occurrences are
visible without a taller window, and the word table's columns fit without
sideways scrolling, for word frequencies (with and without a reference),
sentence lengths and TF-IDF. The stage 5 proposal (#76) is deferred by the
maintainer.

### Scope

[ESSENCE §4](../ESSENCE.md#4-interaction-model-and-inquiry-contract): the Results
screen in `sol/essence/tui/app.py` and its helpers in `sol/essence/tui/`, tests,
ESSENCE §4, CHANGELOG. Not the Encyclopedia or Methods screens (Claude).

### Constraints

Presentation only: engines, artifacts and exports unchanged. Keep keyboard flow
(arrows, Enter to sources, Escape back) and every theme readable.

### Acceptance

Textual pilot tests at 80×24 and 120×40; renders before and after in the
handoff (Textual screenshots misplace spaces next to bold text: check text in
a terminal); documentation check and full suite.

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
