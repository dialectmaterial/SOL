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

## Claude Code: The sentence study in ESSENCE

**Status:** Ready
**Branch:** `claude/essence-sentences-ui`
**Requested:** 19 October 2026, by the maintainer

### Goal

The sentence-length study, removed from the reader as `S`, runs from ESSENCE's
Experiment screen beside word frequencies, on a passage, section, the whole
book or a text file, and a listed sentence opens in the reader.

### Scope

[ESSENCE §4–§5, Experiment A](../ESSENCE.md#experiment-a--syntax-and-positionality-highest-priority),
[BEING §6](../BEING.md#6-being--essence-without-terminal-dogma): `sol/essence/tui/`,
`sol/terminal/` only if opening a sentence needs it, tests, ESSENCE §4 and CHANGELOG.
Call `sol.essence.sentences.analyze_sentences` with the v2 providers (#31);
Results shows counts, the histogram, means by place in the paragraph and the
longest sentences; Enter opens one through the reader's `essence_source`.

### Constraints

No change to `sol/essence/` outside `sol/essence/tui/` (Codex's lane) and no
change to the v1/v2 artifacts. Workspace sessions save the artifact; temporary
sessions save nothing. No new dependency.

### Acceptance

Textual pilot tests for choices, results, saving and opening a sentence; the
real-engine test; a real session on the book reported. Documentation check and
full suite pass.

## Codex: Preserve reading state when navigation is refused (stage 1)

**Status:** In review
**Branch:** `codex/navigation-refusal`
**Requested:** 20 October 2026, by the maintainer via Claude

### Goal

An unsuccessful destination preparation or guarded save leaves a coherent
current screen, saved reading position and return history. Reconcile the
[assigned candidate task](proposals/CODEX_READER_WORKSPACE_PLAN.md#candidate-first-task-for-maintainer-assignment)
with current main before changing code.

### Scope

[BEING §§2–3, 8](../BEING.md#2-what-is-implemented),
[CORE §§5–7](../CORE.md#5-source-bound-positions-and-typography):
`sol/terminal/neovim_reader.py`, `sol/reader/actions.py` only if necessary,
focused regression tests, BEING, CHANGELOG and the handoff.

### Constraints

Preserve canonical text, source offsets, UUIDs, CORE/reference v1, workspace
schemas, actor/revision guards, 64-record loading and the single Neovim
frontend. No force-save, automatic reconversion or rollback of another
session's work. Skip removed `S`/`study_open`; exercise `essence_source`.

### Acceptance

First run the injected next-payload failure against current main; report
whether it still reproduces. Cover preparation failure, stale generation,
competing save, successful retry, history return and reopen. Run focused
tests, documentation check and full suite. Describe recovery after editor
publication failure and distinguish automated checks from real-terminal
acceptance. Open a PR; completion remains with the maintainer.

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
