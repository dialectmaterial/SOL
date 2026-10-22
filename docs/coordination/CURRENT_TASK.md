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

## Codex A: stage F E2 sensitivity

**Status:** In review
**Branch:** `codex/e2-sensitivity`
**Requested:** 22 October 2026, by the maintainer
**Scope:** [E2 sensitivity study](restructuring/E2_SENSITIVITY.md), following
READING_BEING §§8.2/9 and REEVALUATION §3.3: vary supported document units,
reference populations and TF-IDF top_n on the real private corpus through
existing public providers. State screening thresholds before results; report
isolated words, counts and statistics only, including negative evidence.
**Constraints:** research only; no ESSENCE method, schema, register or placement
change. Corpus remains read-only; no private text, PDFs, workspaces or exports
are committed. Task-specific analysis scripts stay outside Git.
**Acceptance:** full suite and `scripts/check_docs.py`; study linked from
READING_BEING §9 and HANDOFF; commit, push and open a PR against main. Do not
merge. Previous stage E re-evaluation is done (#102).

## Codex B: architecture guard

**Status:** Done (#101)
**Branch:** `codex/architecture-guard`
**Requested:** 22 October 2026, by Claude for the maintainer

### Goal

Protect stage D's dependency directions with a static AST test, so new edges
cannot silently couple the divisions or restore removed packages.

### Scope

`tests/test_architecture.py`, a short pointer in [Architecture §2](../ARCHITECTURE.md#2-logical-divisions-and-component-responsibilities),
and coordination reports. Authority: Architecture §§2/9, CORE §§4/8 and the
stage D rules above. CORE includes `sol.core` and `sol.corpus`; composition,
presentation and interchange stay outside the logical hierarchy.

### Constraints

Execute no inspected imports. Include function-local imports, document exact
justified exceptions, and report actual rule violations. Poll #99 and #100;
after both merge, merge `origin/main` and verify against the real relocated code.
Do not change runtime behavior, public contracts or private corpus material.

### Acceptance

Readable file:line failures for forbidden imports; assert `sol.reader` and
`sol.terminal` are absent. Full suite and docs check pass; HANDOFF records the
rules, exceptions, evidence and limits. Commit, push and open a PR against main;
the author does not merge.

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
