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

## Codex A: sentence segmentation audit (ESSENCE Experiment A)

**Status:** In review
**Branch:** `codex/sentence-segmentation-audit`
**Requested:** 23 October 2026, by the maintainer
**Scope:** [ESSENCE Experiment A](../ESSENCE.md#experiment-a--syntax-and-positionality-highest-priority):
audit `punctuation-rules-v1` against every boundary in 60 reproducibly sampled
private-corpus passages, read-only; state hand-check rules, boundary precision/
recall and errors by type. Publish counts and abbreviation strings, no corpus
sentences/passages. If material, add separately named `punctuation-rules-v2`,
keep v1 selectable/checkable and existing artifacts valid, test with invented
text, and remeasure the same sample. Document any interface default choice.
**Constraints:** no dependencies, canonical edits or private text in Git; other
lanes' slots unchanged; do not merge own PR.
**Acceptance:** `restructuring/SENTENCE_AUDIT.md`, ESSENCE and CHANGELOG; full
suite and `scripts/check_docs.py`; commit, push, PR and HANDOFF report.

## Codex B: ESSENCE context transport

**Status:** In review
**Branch:** `codex/essence-context-transport` · [PR #125](https://github.com/dialectmaterial/SOL/pull/125)
**Requested:** 25 October 2026, by the maintainer
**Scope:** `sol/interchange/essence.py` and invented context regression tests:
nonblocking special-file refusal, consistent byte limits, strict integer versions
and cleanup after interrupted writes. Authority: [ESSENCE §8](../ESSENCE.md#8-developer-acceptance-and-prohibitions).
**Constraints:** No private text, dependencies, schema changes, TUI or SPECULATIVE edits.
Base `origin/main`; do not merge own PR.
**Acceptance:** Red/green regressions; real tmux use; full suite and docs check;
commit, push, PR and HANDOFF. Prior batch: [#123](https://github.com/dialectmaterial/SOL/pull/123).

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
