# Current tasks

At most one task per implementing agent, each on its own branch, with scopes
that do not touch the same files. The maintainer (or ChatGPT, through the
maintainer) writes the tasks; each agent works only on the task assigned to it
and reports in [HANDOFF](HANDOFF.md). This file is coordination, not design
authority: a task must agree with [Architecture](../ARCHITECTURE.md),
[BEING](../BEING.md), [ESSENCE](../ESSENCE.md) and [CORE](../CORE.md), and cites
them rather than restating them. Backlog: the
[reader backlog](proposals/READER_GAPS_AFTER_ZATHURA.md).

Status moves `Ready` → `In progress` → `In review` → `Done`. When a task is done,
replace it with the agent's next one; Git history keeps the old ones.

## Restructuring, stage A: baseline and inventory

The maintainer's leading document, [SPECULATIVE](../SPECULATIVE.md), sets the
restructuring under BEING (Quality · Quantity · Measure), ESSENCE (Essence as
Reflection within Itself · Appearance · Actuality), a reserved CONCEPT and a
separate CORE ([§§4, 7](../SPECULATIVE.md#7-implementation-sequence)). Stage A
inventories what exists, **without proposing placements yet** and without
pretending the code is conceptually homogeneous. Each agent writes its own file
under `docs/coordination/restructuring/`; no product code changes.

For every module: what it actually does (from the code, not its name), what it
imports and what imports it, entry points and commands that reach it, the tests
that protect it, its present CORE/BEING/ESSENCE boundary, and cohesive groups of
related definitions that should move together. End with open questions the
stage C reading must answer (for example, where the workspace store and the word
tokenizer belong).

## Claude Code: Inventory of the BEING side

**Status:** Ready
**Branch:** `claude/inventory-being`
**Scope:** `sol/reader/`, `sol/terminal/`, `sol/workspace/`, `sol/__init__.py`,
`sol/__main__.py`, entry points in `pyproject.toml`; output
`docs/coordination/restructuring/INVENTORY_BEING.md`.

## Codex: Inventory of the ESSENCE and CORE side

**Status:** Ready
**Branch:** `codex/inventory-essence-core`
**Scope:** `sol/essence/`, `sol/corpus/`, `sol/core/`, `scripts/`; output
`docs/coordination/restructuring/INVENTORY_ESSENCE_CORE.md`.

### Acceptance (both)

Every module in scope listed; import edges checked mechanically, not guessed;
documentation check passes. Review each other's inventory before stage B.

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
