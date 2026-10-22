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

## Claude Code: prepare reader sections ahead

**Status:** In review
**Branch:** `claude/prepare-sections-ahead`
**Scope:** maintainer request (23 October): make section crossings faster by
doing more work on the opening screen. The reader prepares neighbouring
sections at startup and while idle; CORE's checks are unchanged. Previous task
(word-unit docs) done: #109.

## Codex A: stage F E2 sensitivity

**Status:** Done (#108)
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
merge. Previous word-unit study is done (#105); stage E re-evaluation is
done (#102).

## Codex B: source-check coverage

**Status:** Done (#107)
**Branch:** `codex/source-check-coverage`
**Requested:** 22 October 2026, by the maintainer

### Goal

Pin existing source-request validation behavior and correct the missing-PDF
setup diagnostic, following [SOURCE_VALIDATION §2](restructuring/SOURCE_VALIDATION.md#2-existing-tests-and-uncovered-cases).

### Scope

`tests/test_source_viewer.py`: synthetic coverage of PDF final symlinks,
non-files/read races, stale/corrupt follow refusal before companion access,
post-PDF-check render freshness and generation/chain/digest tampering.
`sol/core/source.py`: replace the nonexistent shell setup command with the
supported app option, checked against app options and onboarding.
Coordination status and HANDOFF. Authority: Architecture §§2/9, CORE §§4/8.

### Constraints

Tests plus one diagnostic fix only; no public API, schema or other behavior
change. Record known validation gaps in clearly named tests or expected failures
and HANDOFF; do not fix them. Synthetic fixtures only, no corpus text, display,
network or committed generated artifacts. Other lanes' slots are unchanged.

### Acceptance

Full suite, `tests/test_architecture.py`, `scripts/check_docs.py`; HANDOFF lists
known gaps and evidence. Commit, push and open a PR against main; do not merge.
Prior source-validation proposal completed in #104.

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
