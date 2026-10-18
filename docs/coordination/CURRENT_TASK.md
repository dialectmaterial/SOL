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

## Claude Code: Remember validated corpus generations on disk

**Status:** In progress
**Branch:** `claude/faster-startup` (PR #27)
**Requested:** 19 October 2026, by the maintainer

### Goal

`sol` starts faster by not re-validating every corpus record when the exact
same files were already fully validated by the same validator code.

### Scope

`sol/corpus/contract.py` and `sol/core/` (internals), tests, CORE and
CHANGELOG. A private cache file keyed by the SHA-256 of every corpus file and
by the validator code; then, after this, ESSENCE stage 3's interface side.

### Constraints

**Approved by the maintainer on 19 October 2026 (reserved):** trusting a
previous full validation of byte-identical files across starts. File
fingerprints are still read and checked on every start; any change, or a
different validator version, means full validation. The cache holds hashes
only, owner-only. Do not touch `sol/essence/` outside `sol/essence/tui/`.

### Acceptance

Start-up measured before and after; a changed byte, a changed validator, a
missing or corrupt cache and a cache written by someone else each lead to full
validation. Documentation check and full suite pass.

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
