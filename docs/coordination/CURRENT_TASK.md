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

## Claude Code: The passage highlighted in Zathura, which follows the reader

**Status:** In review
**Branch:** `claude/pdf-follow`
**Requested:** 21 October 2026, by the maintainer via Claude (reader backlog, item 2)

### Goal

`S` highlights the passage's recorded region on the printed page (and its
continuation on the next page), and while that Zathura window is open it turns
to and highlights whichever passage the reader rests on.

### Scope

[BEING §5](../BEING.md#5-mathematical-notation-and-source-fidelity):
`sol/terminal/source.py`, the source requests in `sol/terminal/neovim_reader.py`,
`sol/terminal/neovim_panels.lua`/`neovim_controls.lua`/`neovim_requests.lua`,
tests, BEING §5, CHANGELOG.

### Constraints

Only the verified snapshot and recorded boxes; following never moves the
reader, never blocks a key and stops when Zathura closes. No change to startup
or payload building (Codex).

### Acceptance

Unit and headless Neovim tests; a real Zathura check by D-Bus; documentation
check and full suite.

## Codex: Faster startup to readable text

**Status:** Ready
**Branch:** `codex/startup-time`
**Requested:** 21 October 2026, by the maintainer via Claude (reader backlog, item 4)

### Goal

Measured, smaller time from `sol` to readable text (about 1.2 s to the first
payload today), behind the opening screen.

### Scope

[BEING §2](../BEING.md#2-what-is-implemented): `sol/reader/app.py`,
`sol/reader/launch.py`, corpus loading and imports on the startup path,
`sol/terminal/neovim.py` payload building, `scripts/reader_timings.py`, tests,
BEING, CHANGELOG.

### Constraints

Do not relax or cache source verification (reserved, see #64's proposal).
No change to `sol/terminal/source.py` or the source requests (Claude).

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
