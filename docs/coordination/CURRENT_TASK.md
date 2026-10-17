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

## Claude Code: Preserve reading state when navigation is refused

**Status:** Ready
**Branch:** `claude/navigation-failure-recovery`
**Requested:** 18 October 2026, by the maintainer

### Goal

An unsuccessful destination preparation or guarded save leaves a coherent
current screen, saved reading position and return history.

### Scope

[Proposal stage 1](proposals/CODEX_READER_WORKSPACE_PLAN.md#1-fix-navigation-failure-recovery-first):
`sol/terminal/neovim_reader.py`, `sol/reader/actions.py` where the action
boundary needs support, their tests, and the BEING/CHANGELOG updates describing
verified outcomes. Include `study_open` among the navigation routes. Authority:
BEING §§2–3, 8; CORE §§5–7.

### Constraints

Canonical text, source offsets, UUIDs, CORE/reference v1, workspace schemas,
actor/revision guards, 64-record loading and the single Neovim frontend stay
unchanged. No force-saving, automatic reconversion or rollback of another
session's work. Do not touch `sol/essence/` (Codex's task).

### Acceptance

Reproduce the injected next-payload failure before fixing it; then cover
preparation failure, stale generation, competing workspace save, successful
retry, history return and reopen. Focused tests and the normal checks pass. The
handoff states which real-terminal checks ran and which remain outstanding.

## Codex: Measure sentence-segmentation error

**Status:** In review
**Branch:** `codex/sentence-segmentation-check`
**Requested:** 18 October 2026, by the maintainer

### Goal

Know how often `punctuation-rules-v1` splits sentences wrongly, before anyone
decides whether to change the method or adopt an external segmenter.

### Scope

[Proposal stage 7](proposals/CODEX_READER_WORKSPACE_PLAN.md#7-build-the-first-terminal-independent-essence-round-trip),
validation only, within `sol/essence/`, `tests/` and ESSENCE/CHANGELOG: a way to
compare the segmenter's boundaries with a hand-marked sample and report misses
and false splits; synthetic test fixtures covering known hard cases, including
the sentence inside a parenthesis opened mid-sentence; and a procedure for the
maintainer to mark a real sample privately. Authority: ESSENCE §§3–5, 8.

### Constraints

Do not change `punctuation-rules-v1`'s output, its artifacts or the protocol; a
method change is a decision for approval. No new dependency. Real-book samples
and their markings stay outside Git. Do not touch `sol/terminal/` or
`sol/reader/` (Claude Code's task).

### Acceptance

The comparison is tested on synthetic fixtures; the known misses are recorded
as expected failures, not fixed silently. The documentation check and the full
suite pass. The handoff proposes a sample size and an error tolerance for the
maintainer to approve.

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
