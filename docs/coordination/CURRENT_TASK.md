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

## Restructuring, stage D: relocation

Stage C is done: the placements are in the
[placement register](../ARCHITECTURE.md#9-placement-register), argued in
`restructuring/READING_BEING.md` and `READING_ESSENCE.md`. Stage D moves code
to them ([SPECULATIVE §5.2](../SPECULATIVE.md#52-required-reasoning-protocol),
steps 5–7). Rules for all three lanes:

1. **Move, do not rewrite.** Keep function bodies, names and behaviour; change
   imports, string patch targets in tests, package data and entry-point targets.
   Renaming a module is allowed only where its new package makes the old name
   redundant (for example `neovim_reader` inside a `neovim` package).
2. **No compatibility shims** at old paths, unless a path is a public contract
   (the `sol.core` API, `python -m sol.essence.cli`, installed commands
   `sol`, `sol-window`, `sol-corpus`, `sol-corpus-check`): those keep working.
3. **Imports in another lane's files:** you may edit only the import lines and
   string patch targets that point at modules you move. Whoever merges second
   resolves the conflict.
4. **Verify:** full suite, docs check, `python -m sol --help`, `sol essence --help`
   and an import of every moved module from an installed wheel
   (`tests/test_packaging.py` covers package data). Grep for every old dotted
   path and file path (tests, scripts, docs, Lua, pyproject) before the PR.
5. **Record:** set your register rows' status to *Implemented (stage D)* with
   the PR, update module paths in ARCHITECTURE §2 and the component document,
   and add a CHANGELOG line.

## Claude Code: measure reader latency on screen

**Status:** Done (#115)
**Branch:** `claude/section-keys-use-channel`
**Scope:** reader backlog item "measured navigation latency": time from key to
readable text in a real terminal. The measurement found `]c`/`[c` restarting
Neovim for every section; fixed. Previous task (sections prepared ahead) done: #112.

## Codex A: C3 projection-boundary proposal

**Status:** Done (#111)
**Branch:** `codex/c3-projection-proposal`
**Requested:** 23 October 2026, by the maintainer
**Scope:** [Projection boundary](restructuring/PROJECTION_BOUNDARY.md), following
[REEVALUATION §3.5](restructuring/REEVALUATION.md#35-cores-edition-shaped-projection-c3)
and [Architecture §9 C3](../ARCHITECTURE.md#9-placement-register): inventory
edition assumptions and consumers, distinguish verified corpus custody from
reader projection, propose an explicit description and compatibility seam,
compare alternatives and state exact migration tests. Link from REEVALUATION
and HANDOFF; update only Codex A's slot.
**Constraints:** design and documentation only; no runtime, API, version,
corpus-contract, workspace-schema or reference-protocol change. No private
corpus text, PDFs, workspaces or generated exports. Hegel-placement remarks
use existing READING documents only; recommendation is a maintainer decision
(reserved: public contract).
**Acceptance:** `scripts/check_docs.py` and full suite; commit, push and open a
PR against main; report its URL and do not merge. Previous E2 study done (#108).

## Codex B: landmark management

**Status:** Done (#113)
**Branch:** `codex/landmark-management`
**Requested:** 23 October 2026, by the maintainer

### Goal

Close the named-landmark rename and ordering limitation in
[BEING §7](../BEING.md#7-boundaries-and-known-limitations).

### Scope

Add atomic rename with the existing name rules to the Neovim reader's `L`
panel; preserve the saved target and metadata on success, and the old landmark
on failure. Add a session-only toggle between name and whole-book passage
order, with unavailable passages last. Update panel hints, `?` help, BEING and
CHANGELOG. Cover workspace transactions, conflicts and unavailable targets,
controller behavior and headless Neovim controls.

### Constraints

No workspace schema change or new persisted settings. Keep the three reader
markers and other lanes' slots unchanged. Branch from `origin/main`; open a PR
and do not merge it.

### Acceptance

Full suite, `tests/test_architecture.py`, `scripts/check_docs.py`; commit, push,
open a PR against main, and record a HANDOFF report and PR URL.

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
