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

## Codex A: ESSENCE study settings and comparison sorting

**Status:** In review
**Branch:** `codex/essence-study-settings`
**Requested:** 23 October 2026, by the maintainer
**Scope:** [ESSENCE §4](../ESSENCE.md#4-interaction-model-and-inquiry-contract):
add a bounded TF-IDF top_n choice before running, show it in the results header;
inspect existing investigation state and retain study choices only if already
recorded there. Add keyboard sorting by every displayed word-comparison column,
both directions, stable ties and undefined values last with visible status;
default and exports retain engine order. Update in-app help, ESSENCE's implemented
section and CHANGELOG.
**Constraints:** interface only (`sol/essence/tui/`); no engine, artifact schema,
method ID, dependency or new persistent-format change. Synthetic test files only;
other lanes' slots unchanged. Do not merge own PR.
**Acceptance:** Textual pilot tests cover choices reaching analyze_tfidf, header,
invalid values, sorting/nulls/ties and unchanged export. Full suite and
`scripts/check_docs.py`; commit, push, PR against main and HANDOFF report.

## Codex B: private source-request hardening

**Status:** Done (#110)
**Branch:** `codex/source-gap-fixes`
**Requested:** 23 October 2026, by the maintainer

### Goal

Close the three known gaps pinned in #107, applying
[SOURCE_VALIDATION §3.2](restructuring/SOURCE_VALIDATION.md#32-required-behavior-and-ordering)
inside CORE's private source implementation. Authority: Architecture §§2/9,
CORE §§4/8; the public-interface decision in #104 stays pending.

### Scope

Normalize malformed requested IDs and request shapes to chained `SourceError`;
validate `render_region` before source/bbox access; refuse corpus changes during
or after viewer PDF hashing with a final `verify_snapshot_current` check before
viewer/companion/D-Bus access. Convert the three known-gap tests and add
synthetic regressions for every consumer. Update SOURCE_VALIDATION and HANDOFF.

### Constraints

No new public names, validator, facade/API_VERSION or request-format changes.
Preserve capture output, rendering, caching and viewer launching. Existing
private CORE imports in `source_view` may remain. No private corpus or generated
artifacts; other lanes' slots stay unchanged. Do not merge.

### Acceptance

Full suite, `tests/test_architecture.py`, `scripts/check_docs.py`; commit, push
and open a PR against main. Prior source-check coverage completed in #107;
the source-validation public proposal remains pending in #104.

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
