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

## Claude Code: Edit and review personal notes in the reader

**Status:** In review
**Branch:** `claude/reader-note-editing`
**Requested:** 18 October 2026, by the maintainer

### Goal

From `c`, the reader picks one of their notes on the passage, edits it in the
same editor as `a`, and sees its earlier versions, without the compatibility
shell.

### Scope

[Proposal stage 3](proposals/CODEX_READER_WORKSPACE_PLAN.md#3-complete-the-personal-note-workflow-inside-the-reader):
`sol/terminal/neovim.lua`, `sol/terminal/neovim_reader.py`, `sol/terminal/neovim.py`
where needed, their tests, BEING and CHANGELOG, using the existing
`WorkspaceReader.prepare_annotation_edit` / `save_annotation_edit` and
`list_annotation_history`. Authority: BEING §§3, 7–8; CORE §7.

### Constraints

`a` still adds a note; edits keep the note's ID, target and original source
digest. Only the original author may edit; a competing revision or changed
source is refused; a save that changes nothing adds no revision. Deleting,
hiding or retracting notes is a reserved decision and out of scope. No
workspace schema change. Temporary sessions refuse durable notes. Do not touch
`sol/essence/` or Codex's measurement files.

### Acceptance

Edit, history and refusals are covered by controller and headless Neovim
tests: another actor, a competing revision, a changed source, a no-op save and
a failed save that keeps the draft. Each note in `c` shows its author, revision
and whether its passage changed since it was written. The handoff lists the
key bindings chosen, as defaults the maintainer may overrule.

## Codex: Measure reader speed before optimising

**Status:** Ready
**Branch:** `codex/reader-timings`
**Requested:** 18 October 2026, by the maintainer

### Goal

Know how long the reader's main operations take, so that any later
optimisation is chosen from evidence ([CONTRIBUTING, scope of the cleanup](../../CONTRIBUTING.md#scope-of-the-cleanup);
[proposal cleanup](proposals/CODEX_READER_WORKSPACE_PLAN.md#cleanup-alongside-the-stages)).

### Scope

A measurement script under `scripts/` (or `experiments/`) and its tests:
corpus load and verification, building a view (`build_payload`) for an
ordinary and a footnote-heavy section, a section transition through the
controller, search, and `S` on a section. It reports medians and spread over
repeated runs, on a synthetic corpus by default and on a corpus given
explicitly by path. Results from the real book stay out of Git; the handoff
may quote the numbers.

### Constraints

Read and call the reader code; do not change `sol/terminal/`, `sol/reader/`,
`sol/core/` or `sol/workspace/` (Claude Code's lane and shared contracts). No
new dependency; use `time.perf_counter`. No personal workspace is opened;
temporary ones only.

### Acceptance

The script runs in the normal suite on the synthetic corpus within a few
seconds, with a test that it reports every operation. The handoff quotes
real-book timings on this machine and names the slowest operation, without
proposing a cache as decided.

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
