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

## Claude Code: Finish the reader speed list

**Status:** Ready
**Branch:** `claude/reader-speed-list`
**Requested:** 19 October 2026, by the maintainer

### Goal

Bring a section move from about 0.68 s towards 0.5 s on the real book, by the
remaining items measured on 19 October.

### Scope

`sol/core/protocol.py`, `sol/core/models.py`, `sol/reader/actions.py`,
`sol/reader/surface.py`, their tests, CORE and CHANGELOG:
- a faster in-memory comparison in `_fresh_snapshot` (JSON text plus structural
  equality). **Approved by the maintainer on 19 October:** it may accept an
  in-memory value that is a subclass of `int` or `float` with the same value,
  which the current comparison refuses; record this in CORE §6;
- the deep copy of the section in `sol/reader/surface.py`;
- repeated passage lookups (`Book.selection`, `find_passage`,
  `ReadingSession.current`), with identical results.
Measure with `scripts/reader_timings.py`. Authority: CORE §§4–6.

### Constraints

File fingerprints are still checked on every call; no other relaxation. No
change to the CORE API, reference protocol, corpus contract or workspace
schema. Do not touch `sol/terminal/` (Codex's task).

### Acceptance

Before/after timings in the handoff; existing refusal tests unchanged; a test
for each relaxed or rewritten check showing what it still refuses. The
documentation check and the full suite pass.

## Codex: Formula review sheet

**Status:** In progress
**Branch:** `codex/formula-review-sheet`
**Requested:** 18 October 2026, by the maintainer in the Codex session

### Goal

Help the maintainer check 30 retyped formulas against the printed source.
Create a private review sheet for canonical records with `contains_math` and
`needs_visual_review`, and record human verdicts for a later application step.

### Scope

A checkout-only script under `scripts/`, its tests, BEING and CHANGELOG. Show
each record's ID, page labels, exact typed text and every printed-source crop,
calling the existing `sol/terminal/source.py` capture/render functions without
changing them. Authority: BEING §5; CORE §§2, 3, 5 and 7.

### Constraints

No new dependencies. Book text, crops and verdicts stay outside Git. The sheet
never marks a record reviewed: changing canonical `transcription_status` is a
separate human-approved step. Do not touch `sol/core/protocol.py`,
`sol/core/models.py`, `sol/reader/actions.py`, `sol/reader/surface.py`,
`sol/terminal/neovim.py` or `sol/terminal/neovim_reader.py` (Claude Code's speed
work), or `sol/terminal/source.py`.

### Acceptance

Synthetic end-to-end generation covers flagged math in main text and notes,
all source pages, crops and the explicit whole-page fallback. Verdicts record
`confirmed` or `needs correction` with a note, reviewer and source binding in
a private file. Test privacy, nonmutation, stale/missing source, invalid input
and refusal to overwrite an existing sheet. Documentation and full checks pass.

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
