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

## Claude Code: ESSENCE stage 1, the interface shell

**Status:** In review
**Branch:** `claude/essence-shell`
**Requested:** 18 October 2026, by the maintainer

### Goal

From the reader, `E` opens ESSENCE as a Textual application in a Neovim
terminal buffer beside the reader; a key toggles fullscreen and back without
restarting it; focus moves predictably; leaving ESSENCE ends its process and
restores the exact reading position. Screens are mock content for now.

### Scope

[ESSENCE §4–§5 stage 1](../ESSENCE.md#4-interaction-model-and-inquiry-contract),
[BEING §6](../BEING.md#6-being--essence-without-terminal-dogma): `sol/terminal/`
(Neovim side and controller), a new `sol/essence/tui/` package (the Textual app),
`pyproject.toml` (the `essence` optional extra), tests, BEING/ESSENCE §4 and
CHANGELOG.

### Constraints

Textual only as the optional extra; without it, `E` explains how to install
it and the reader is unaffected. No existing key remapped. No model imports.
Do not touch the rest of `sol/essence/` (Codex's task).

### Acceptance

Headless Neovim and Textual pilot tests for open, toggle, focus, close and
failure; the reader position survives; a manual check on a real terminal is
reported separately.

## Codex: ESSENCE stage 2 engine, word frequencies without an interface

**Status:** Ready (after #22 is merged)
**Branch:** `codex/essence-word-frequencies`
**Requested:** 18 October 2026, by the maintainer

### Goal

A headless, reproducible word-frequency analysis over a target scope and an
optional reference scope, from the CORE corpus or a plain-text file, which the
interface will later call.

### Scope

[ESSENCE §4–§5 stage 2](../ESSENCE.md#5-prioritized-experiments): `sol/essence/`
except `sol/essence/tui/`, tests, ESSENCE §5 and CHANGELOG. A provider boundary
(`core` | `file`); the term study's tokenizer, shared rather than copied; token
count, type count and a frequency table; absolute counts, rates and denominators
for target and reference; a `sol analyze words` CLI; a versioned artifact with
`sol analyze check` support, binding the CORE generation or the file digest.

### Constraints

No Textual import and no interface work; do not touch `sol/terminal/`,
`sol/essence/tui/` or `pyproject.toml` (Claude Code's task). Existing
`sol.term-study` and `sol.sentence-study` artifacts unchanged. File input is
UTF-8 text the user names explicitly; artifacts keep no book text. No new
dependency.

### Acceptance

Tests for both providers, unequal scopes (denominators shown, no false
comparability), a changed corpus or file refused by `check`, Unicode and empty
input. The handoff documents the Python function the interface will call.

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
