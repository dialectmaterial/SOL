# Current task

One task at a time. The maintainer (or ChatGPT, through the maintainer) writes
it; Claude Code works only on it and reports in [HANDOFF](HANDOFF.md). This file
is coordination, not design authority: the task must agree with
[Architecture](../ARCHITECTURE.md), [BEING](../BEING.md), [ESSENCE](../ESSENCE.md)
and [CORE](../CORE.md), and cites them rather than restating them.

Status moves `Ready` → `In progress` → `In review` → `Done`. When a task is done,
replace this file's task with the next one; Git history keeps the old ones.

## Coordination workflow between Claude Code and ChatGPT

**Status:** In review
**Branch:** `claude/coordination-workflow`
**Requested:** 17 October 2026, by the maintainer

### Goal

Let ChatGPT review Claude Code's work through GitHub, without conversation
transcripts: each completed task leaves a concise report with commit SHA,
changed files, tests performed, outstanding issues and architectural decisions
requiring approval.

### Scope

- `CLAUDE.md` with Claude Code's working rules.
- `docs/coordination/CURRENT_TASK.md` (this file) and `docs/coordination/HANDOFF.md`.
- A separate branch and a pull request for review.

### Constraints

- Preserve the documentation hierarchy: the four authorities stay the only
  design documents; `docs/legacy/` is untouched.
- No change to SOL's application code.

### Acceptance

- The documentation check and the full test suite pass.
- The first handoff report follows the template and covers this task.

<!--
Template for the next task — copy below the introduction and fill in.

## <Task title>

**Status:** Ready
**Branch:** `claude/<short-task-name>`
**Requested:** <date>, by <who>

### Goal
<One or two sentences: the outcome, not the steps.>

### Scope
<What may change. Cite authority sections, e.g. BEING §5.>

### Constraints
<What must not change; contracts to preserve.>

### Acceptance
<Checks that decide "done": tests, a manual check, a document updated.>
-->
