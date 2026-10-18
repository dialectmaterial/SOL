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

## Claude Code: Make start-up fast

**Status:** In progress
**Branch:** `claude/faster-startup` (PR #27)
**Requested:** 19 October 2026, by the maintainer

### Goal

`sol` opens noticeably faster in the maintainer's real use. Start from what
the maintainer actually experiences, not only the measured 0.86–0.95 s.

### Scope

`sol/core/`, `sol/corpus/`, `sol/reader/`, `sol/terminal/`, tests, CORE/BEING
and CHANGELOG. Measure the real launch path end to end (shell, Python start,
corpus, workspace, Neovim, first page) on this machine and remove waste.

### Constraints

Trusting an earlier validation across starts was considered and dropped on
19 October (it saves under 0.1 s). Any other relaxation of a check, or showing
text before it is verified, is a reserved decision. Do not touch `sol/essence/`
outside `sol/essence/tui/`.

### Acceptance

Before/after timings of the real launch in a terminal; existing refusal tests
unchanged. Documentation check and full suite pass. Then: ESSENCE stage 3's
interface side.

## Codex: ESSENCE stage 3 engine, comparison measures and export

**Status:** Ready
**Branch:** `codex/essence-comparison`
**Requested:** 19 October 2026, by the maintainer

### Goal

Comparing a target with a reference says more than two rates side by side:
per-word comparison measures with explicit denominators, and an export that
other tools can read, without book text.

### Scope

[ESSENCE §5 stage 3](../ESSENCE.md#5-prioritized-experiments): `sol/essence/`
except `sol/essence/tui/`, tests, ESSENCE §5 and CHANGELOG. Propose and
implement a small, documented set of measures (for example a rate difference
and a log ratio with a stated handling of zero counts; a keyness statistic
only with its formula and a note on what it does not show). Export the
frequency table and measures as CSV/TSV from the CLI. A Python function the
interface can call, documented in the handoff.

### Constraints

No change to the shape of `sol.word-frequencies` v1 without a new version;
existing artifacts still check. Measures never imply conceptual similarity or
significance beyond what their method states. No book text in exports beyond
the words themselves. No new dependency. Do not touch `sol/essence/tui/`,
`sol/terminal/`, `sol/core/` or `sol/corpus/` (Claude Code's tasks).

### Acceptance

Tests for each measure (including zero counts and unequal denominators), export
round trips, and refusal of stale inputs. Documentation check and full suite
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
