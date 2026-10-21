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

## Claude Code: Visual audit of ESSENCE's screens

**Status:** In review
**Branch:** `claude/essence-audit`
**Requested:** 21 October 2026, by the maintainer via Claude

### Goal

Every ESSENCE screen (Encyclopedia, Methods, Experiment, each study's Results)
rendered at several terminal sizes and themes on the book; faults fixed, matters
of taste left for the maintainer.

### Scope

`sol/essence/tui/` presentation, its tests, ESSENCE §4, CHANGELOG. No change to
engines or artifacts, and nothing under `docs/coordination/proposals/` (Codex).

### Acceptance

Before/after renders of each fix; Textual pilot tests; documentation check and
full suite.

## Codex: Stage 5 design proposal (model adapters and Experiment B)

**Status:** Ready
**Branch:** `codex/stage5-proposal`
**Requested:** 21 October 2026, by the maintainer via Claude ([ESSENCE §5](../ESSENCE.md#5-prioritized-experiments), stage 5)

### Goal

A reviewable proposal for the capability registry, optional runtimes and the
first adapter-based experiment (Experiment B, embeddings for the TensorFlow
Embedding Projector): interfaces, artifacts, reproducibility records, what each
optional dependency would be, and the smallest first step.

### Scope

`docs/coordination/proposals/ESSENCE_STAGE5_PROPOSAL.md` only. No code.

### Constraints

New dependencies, artifact formats and changes to Decision statements are
**reserved**: name them as decisions for the maintainer, with options and a
recommendation. Follow ESSENCE §1's decision (orchestrate, never reimplement)
and §3 (projections, not destructive cleaning).

### Acceptance

Documentation check; the handoff lists every reserved decision.

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
