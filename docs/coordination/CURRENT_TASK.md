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

## Claude Code: ESSENCE workspace

**Status:** In review
**Branch:** `claude/essence-workspace` (stacked on #118)
**Requested:** 24 October 2026, by the maintainer, after the ESSENCE visual
audit: "work on it", approving all five decisions (now in
[ESSENCE §4](../ESSENCE.md#4-interaction-model-and-inquiry-contract)).
**Scope:** `sol/essence/tui/` and its tests: a result-first workspace, a
one-key study menu, drawn results (bars, concordance, dispersion), the
catalogs as reference, vim motions and a command palette, the function-word
display switch (list from Codex A, #119) and following the reader (position
file from Codex B, #120). No engine, artifact, export or dependency change.

## Codex A: ESSENCE catalog navigation

**Status:** In review (local; publication blocked by GitHub access)
**Branch:** `codex/essence-catalog-navigation`
**Requested:** 24 October 2026, directly by the maintainer: keep improving the interface
**Scope:** searchable Encyclopedia/Methods catalogs with explicit empty states
and correct filtered entry/actions; a compact horizontal study selector to give
source settings more room in reader splits. Follow
[ESSENCE §4](../ESSENCE.md#4-interaction-model-and-inquiry-contract), retaining the
accepted rounded style. Install the verified result automatically under
[CONTRIBUTING](../../CONTRIBUTING.md#install-verified-changes-for-the-maintainer).
**Constraints:** preserve study engines, full catalog content, genealogy links,
source-return guards, persistence, dependencies and active sessions; other
lanes' slots unchanged; do not merge own PR.
**Acceptance:** keyboard/filter/method mapping and resize regression checks,
synthetic previews in wide and narrow windows, full suite and docs check;
verify the installed wheel/UI outside the checkout. Stacked on `f604538`;
publication remains subject to the existing GitHub access restriction.
## Claude Code: measure reader latency on screen

**Status:** Done (#115)
**Branch:** `claude/section-keys-use-channel`
**Scope:** reader backlog item "measured navigation latency": time from key to
readable text in a real terminal. The measurement found `]c`/`[c` restarting
Neovim for every section; fixed. Previous task (sections prepared ahead) done: #112.

## Codex A: declared English function words

**Status:** In review
**Branch:** `codex/function-words`
**Requested:** 24 October 2026, by the maintainer
**Scope:** [ESSENCE §3](../ESSENCE.md#3-proper-model-inputs-projections-not-destructive-cleaning):
bundle the original, categorized `english-closed-class-v1` list and a standard-library
loader for the optional, off-by-default, display-only hide-function-words method
choice. Declare inclusion criteria and the treatment of be/have forms, keeping
`being` out. Claude wires the switch during the interface redesign.
**Constraints:** no edits to `sol/essence/tui/` or `tests/test_essence_*.py`;
no dependencies, changed engine counts/denominators, artifacts or exports; other
lanes' slots unchanged; do not merge own PR.
**Acceptance:** token validity, category uniqueness/order, stable identity and
installed-wheel tests; ESSENCE and CHANGELOG; docs check and full suite; commit,
push, PR and HANDOFF report.
## Codex A: narrow reader layout bugs
## Codex A: ESSENCE resize focus from the reader
## Codex A: reader / ESSENCE handoff bug hunt (round 2)
## Codex A: note editor resize returns to normal reading (round 2)
## Codex A: background ESSENCE exit preserves reader panel focus (round 2)
## Codex A: reader launcher and opening failures
## Codex A: equivalent reader key remappings

**Status:** In review
**Branch:** `codex/reader-key-alias-conflicts`
**Requested:** 25 October 2026, by the maintainer
**Scope:** Reader key remappings under [BEING §4](../BEING.md#4-theming-and-typography-next-bounded-task):
prevent equivalent source/destination key names from crashing startup or silently
overwriting each other. Keep the keys.json format and default controls.
Prior batches: [#124](https://github.com/dialectmaterial/SOL/pull/124),
[#126](https://github.com/dialectmaterial/SOL/pull/126),
[#127](https://github.com/dialectmaterial/SOL/pull/127).
**Constraints:** lane A; no private text/PDF/workspaces/exports, dependencies,
palette/public-contract changes, sol/essence or SPECULATIVE edits.
**Acceptance:** native regressions fail first; manual tmux reproduction/recheck,
full suite and docs check; commit, push, PR and HANDOFF; no self-merge.

**Status:** In review
**Branch:** `codex/launcher-startup-errors`
**Requested:** 25 October 2026, by the maintainer
**Scope:** [BEING §2](../BEING.md#2-what-is-implemented): clean refusals for
unusable Neovim/runtime and sol-window font-cache/process failures, a valid
sol-window help example, and an opening animation that fits 40 columns.
Prior batches: [#124](https://github.com/dialectmaterial/SOL/pull/124),
[#126](https://github.com/dialectmaterial/SOL/pull/126).
**Constraints:** lane A only; no dependencies, palette/public-contract changes,
private corpus text/PDF/workspaces/exports, sol/essence or SPECULATIVE edits.
**Acceptance:** regression failures first; manual tmux reproductions and rechecks,
full suite, docs check; commit, push, PR and HANDOFF; no self-merge.

**Status:** In review
**Branch:** `codex/reader-essence-close-focus`
**Requested:** 25 October 2026, by the maintainer
**Scope:** Reader-owned ESSENCE lifecycle under [BEING §2](../BEING.md#2-what-is-implemented).
After Alt-R, a delayed ESSENCE exit must preserve visible reader panels and typing.
**Base:** `codex/reader-note-resize-mode` ([PR #138](https://github.com/dialectmaterial/SOL/pull/138)), including #135/#126 host fixes and event-loop test support.
**Constraints:** no sol/essence, private corpus data, palette, dependencies,
public contracts or SPECULATIVE edits; other lanes unchanged.
**Acceptance:** failing regressions first; real-corpus tmux close/Alt-R/context
checks; full suite and docs check; commit, push, PR and HANDOFF; no self-merge.

**Status:** In review
**Branch:** `codex/reader-panel-resize`
**Requested:** 25 October 2026, by the maintainer
**Scope:** Hunt reader/launcher bugs under [BEING §2](../BEING.md#2-what-is-implemented).
This batch fixes help continuation alignment and clipped status information in
small terminals. Use the configured corpus read-only in tmux at 86×48, 190×50,
80×24 and 40×24; regressions use invented text only.
**Constraints:** reader/launcher lane only; no ESSENCE code, palette changes,
public-contract changes, dependencies or private data in Git; never edit SPECULATIVE.
**Acceptance:** failing regressions first, focused and full suite, docs check,
manual tmux recheck; commit, push, PR and short HANDOFF; do not merge own PR.

## Codex B: ESSENCE follows the reader

**Status:** In review
**Branch:** `codex/essence-follows-reader`
**Requested:** 24 October 2026, by the maintainer

### Goal

While ESSENCE is open, follow the reader's current passage and codepoint position
([BEING §6](../BEING.md#6-being--essence-without-terminal-dogma),
[ESSENCE §4](../ESSENCE.md#4-interaction-model-and-inquiry-contract)).

### Scope

Add the version-1 private atomic position exchange in `sol/interchange/essence.py`,
fresh CORE capture through the reader action channel and Lua follow lifecycle,
exchange/reader tests, BEING §6, ESSENCE §4 and CHANGELOG.

### Constraints

Do not touch `sol/essence/tui/` or `tests/test_essence_*.py` (Claude's workspace
redesign). No passage text in the exchange; failures must not block reading.
This PR must merge **after Claude's ESSENCE workspace PR**, which adds
`--position-file`. Other lanes' slots stay unchanged. Do not merge own PR.

### Acceptance

Exchange validation, round trip, atomicity and permissions; reader passage changes
and capture failure; docs check and full suite; commit, push, PR and HANDOFF.

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
