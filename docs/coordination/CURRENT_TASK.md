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

## Claude Code: stage F, comparison and Measure

**Status:** In review
**Branch:** `claude/measure-comparison`
**Scope:** read *Measure as a series* (p. 305), *Elective affinity* (p. 308) and
*Diversity* (pp. 362–365) against the two E2 engines, answering the question
READING_BEING §8.2 left for stage E. Docs only: [READING_BEING §9](restructuring/READING_BEING.md#9-comparison-series-and-elective-affinity-stage-f-22-october-2026).
No register, Decision or code change. The previous task (BEING relocation) is
done: #95, #99.

## Codex A: word-unit study

**Status:** In review
**Branch:** `codex/word-unit-study`
**Requested:** 22 October 2026, by the maintainer
**Authority:** [REEVALUATION §3.9](restructuring/REEVALUATION.md#39-the-tokenizers-unit-limit-discrete-magnitude-or-reflection),
READING_BEING, READING_ESSENCE; Architecture §2 dependency direction.
**Scope:** [WORD_UNIT](restructuring/WORD_UNIT.md): exact reader and tokenizer
definitions; read-only real-corpus disagreement counts by cause and individual
forms; user effects, tests, performance and ownership for four alternatives;
recommendation marked as a maintainer decision. Link from REEVALUATION and HANDOFF.
**Constraints:** research only, no behavior change. Throwaway script stays
outside Git; never commit private corpus, PDFs, workspaces or exports. No
fabricated quotations/page evidence or public-contract changes.
**Acceptance:** full test suite and `scripts/check_docs.py`; HANDOFF, commit,
push and PR against main. Do not merge. Prior stage E task completed in #102.

## Codex B: source-validation proposal

**Status:** In review
**Branch:** `codex/source-validation-proposal`
**Requested:** 22 October 2026, by the maintainer

### Goal

Design a public CORE source-request validation interface to replace BEING's
private `_request_current` / `_verify_file` imports, following
[REEVALUATION §3.6](restructuring/REEVALUATION.md#36-the-source-viewer-imports-private-core-helpers).

### Scope

`restructuring/SOURCE_VALIDATION.md`, linked from REEVALUATION and HANDOFF;
coordination status. Inventory every helper/source-pipeline caller, existing
guarantees/error types/tests; propose signatures, immutable results, exceptions,
lazy facade/version compatibility and exact tests (architecture and must-not-load
guards included). Compare alternatives. Authority: Architecture §§2/9,
CORE §§4/8, SPECULATIVE §5.3 and REEVALUATION §3.6.

### Constraints

Design proposal only: no code, tests, public API, Decision, dependency or schema
change. Interface choice is a maintainer decision (reserved: public contract).
Never commit corpus, PDFs, workspaces or generated test artifacts.

### Acceptance

Docs check and full test suite pass; HANDOFF records evidence, proposal limits
and reserved decisions. Commit, push and open a PR against main; do not merge.

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
