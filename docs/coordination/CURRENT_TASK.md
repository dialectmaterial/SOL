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

## Claude Code: The guide and README describe today's reader

**Status:** In progress
**Branch:** `claude/guide-current`
**Requested:** 21 October 2026, by the maintainer via Claude

### Goal

`sol guide` and the README name the reader's keys and features as they are
now (complete search, `gp`, `s`/`S` with Zathura, `M`/`L`, notes, ESSENCE,
themes, `keys.json`, `sol-window`) and nothing that has changed.

### Scope

`sol/reader/render.py` (the guide), `README.md`, their tests, CHANGELOG. No
change to BEING (Codex).

### Acceptance

Tests for the guide text; documentation check and full suite.

## Codex: BEING describes the current reader, not its history

**Status:** Ready
**Branch:** `codex/being-current`
**Requested:** 21 October 2026, by the maintainer via Claude

### Goal

BEING §§2–7 read as the current state of the reader: dated "Implemented (17
October)" paragraphs become one present-tense description per feature, with
history left to CHANGELOG and Git. Every fact, limit and test claim survives.

### Scope

`docs/BEING.md` only (plus CHANGELOG if needed). No code.

### Constraints

**Decision** statements stay word for word (changing them is reserved). No
claim may be strengthened: what is untested or unseen stays so. Keep links
and anchors the documentation check verifies. No change to README or the
guide (Claude).

### Acceptance

Documentation check and full suite; the handoff lists anything removed as
obsolete and why.

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
