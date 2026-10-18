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

## Claude Code: Make reader moves fast without weakening checks

**Status:** Ready
**Branch:** `claude/fast-reader-moves`
**Requested:** 19 October 2026, by the maintainer

### Goal

A section move, search-result open or history step takes well under half a
second on the real book (now about 2.3–2.9 s; see the
[reader speed baseline](https://github.com/dialectmaterial/SOL/blob/c2eb068/docs/coordination/HANDOFF.md#reader-speed-baseline--18-october-2026)),
with every corpus-freshness, reference and workspace guard still in force.

### Scope

`sol/core/protocol.py` (internals only), `sol/reader/actions.py`,
`sol/terminal/neovim_reader.py`, their tests, CORE/BEING and CHANGELOG.
Profiling shows about nine full corpus reloads and revalidations per move
(`_fresh_snapshot`, about 0.65 s each), where `verify_snapshot_current` checks
the same generation in about 14 ms. Measure with `scripts/reader_timings.py`.
Authority: CORE §§5–7; Architecture §6.

### Constraints

No change to the CORE API, the reference protocol, the corpus contract or the
workspace schema. A changed corpus is still refused on every request that reads
or saves. No trust is cached across requests over caller-mutable collections.
If a cheaper check would accept anything the full reload refuses, stop and list
it as a reserved decision. Do not touch `sol/reader/surface.py`,
`sol/reader/typography.py`, `sol/terminal/neovim.py` or `sol/terminal/neovim.lua`
(Codex's task).

### Acceptance

Before/after timings from `scripts/reader_timings.py` on the real book in the
handoff. Existing changed-corpus, stale-reference and conflict tests pass
unchanged, and a new test shows a corpus changed between two requests is still
refused. The documentation check and the full suite pass.

## Codex: Footnote reading view

**Status:** In review
**Branch:** `codex/footnote-view`
**Requested:** 19 October 2026, by the maintainer

### Goal

From `c`, the reader opens a single footnote in its own calm view, follows a
note's own note links, and returns to the exact cursor and selection.

### Scope

[Proposal stage 4](proposals/CODEX_READER_WORKSPACE_PLAN.md#4-give-book-footnotes-a-proper-reading-view):
`sol/reader/surface.py`, `sol/reader/typography.py`, `sol/terminal/neovim.py`,
`sol/terminal/neovim.lua`, their tests, BEING and CHANGELOG. Start after PR #13
is merged; it changed the `c` popup. Authority: BEING §§2, 4, 7; CORE §§2, 5.

### Constraints

Reuse the canonical `note_paragraph` records ordered by `order` and their
existing IDs; callouts stay display marks; emphasis, attribution and review
warnings are kept. Nested or unresolved links have explicit bounds and cycle
handling. Book footnotes, personal notes and technical context stay visibly
separate. No new IDs, no generated text. Do not touch `sol/core/`,
`sol/reader/actions.py` or `sol/terminal/neovim_reader.py` beyond what a new
panel request strictly needs (Claude Code's task); coordinate in the PR if so.

### Acceptance

Multi-paragraph footnotes keep style offsets, numbering, attribution and
warnings; nested and unresolved links have clear outcomes; opening and closing
a footnote restores cursor, selection and reading mode, including at narrow
widths. Headless Neovim and controller tests; the documentation check and the
full suite pass.

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
