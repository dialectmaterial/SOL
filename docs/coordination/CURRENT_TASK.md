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

## Codex A: ESSENCE study settings and comparison sorting

**Status:** Done (#114)
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

## Codex B: faster opening to readable text

**Status:** In progress
**Branch:** `codex/faster-opening`
**Requested:** 23 October 2026, by the maintainer

### Goal
Reduce launch-to-readable-text latency on the real book, following the reader
backlog's measured navigation latency and [BEING §2](../BEING.md#2-what-is-implemented)
“Measured on screen” evidence.

### Scope
Profile the whole opening with `scripts/reader_timings.py --startup-only` and
real-terminal tmux `sol --none` status-line polling. Measure imports, corpus and
snapshot loads/verification, workspace, first payload, neighbour preparation,
splash, Neovim startup and adapter. Keep only measured improvements; add tests
for changed behavior, update BEING's numbers and CHANGELOG.

### Constraints
Use `/home/dima/Projects/code/sol/local-corpus` read-only. Preserve all CORE §5
verification, public contracts, schemas and dependencies. Quantify any reserved
CORE cost in HANDOFF without changing it. Other lanes' slots stay unchanged.
Do not merge own PR.

### Acceptance
Before/after evidence for each change; full suite, `tests/test_architecture.py`,
`scripts/check_docs.py`; implementation commit, final HANDOFF commit, push,
PR against main and report its URL.

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
