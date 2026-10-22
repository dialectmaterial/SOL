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

## Restructuring, stage C: interpretive mapping

Stages A (inventories in `docs/coordination/restructuring/`) and B (the empty
divisions) are done. Stage C reads before anything moves
([SPECULATIVE §§5, 7](../SPECULATIVE.md#52-required-reasoning-protocol)):

1. **Read** in the primary CORE edition (the local corpus; use `sol read`,
   `sol --info` or the reader) the doctrine's opening division and the openings
   and transitions of its three first-level divisions. German and other
   translations may be consulted as aids; name them.
2. **Write reading notes** in your file below: for each determination, its
   location (section path and printed pages) and what it is, in relation to its
   neighbours, in your own words. Separate the text from your interpretation.
   Quote at most a short phrase, attributed with its location: the translation
   is copyrighted. **No fabricated quotations, pages or evidence.**
3. **Propose** provisional placements for your side's cohesive groups from the
   stage A inventory, each with the alternatives considered, as rows for the
   [placement register](../ARCHITECTURE.md#9-placement-register) (status:
   provisional). Groups that belong to no determination (infrastructure,
   CORE's practical boundary) say so and why. Leave unresolved what the reading
   does not settle.
4. Move nothing yet: relocation is stage D.

## Claude Code: Reading the Doctrine of Being

**Status:** In review
**Branch:** `claude/reading-being`
**Scope:** the Doctrine of Being (its division; Quality, Quantity, Measure);
the BEING-side groups of `INVENTORY_BEING.md`; output
`docs/coordination/restructuring/READING_BEING.md` and proposed register rows
in `docs/ARCHITECTURE.md` §9 (Claude's rows only).

## Codex: Reading the Doctrine of Essence

**Status:** Ready
**Branch:** `codex/reading-essence`
**Scope:** the Doctrine of Essence (its division; Essence as Reflection within
Itself, Appearance, Actuality); the ESSENCE-side groups of
`INVENTORY_ESSENCE_CORE.md`, and whether CORE's practical exception holds for
each CORE group; output `docs/coordination/restructuring/READING_ESSENCE.md`.
Put proposed register rows in that file; Claude adds them to ARCHITECTURE §9
when merging, so the two branches never edit the same section.

### Acceptance (both)

Every claim about the text carries a location in the CORE edition; each
proposal names alternatives; documentation check passes; the other agent
reviews.

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
