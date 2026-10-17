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

## Claude Code: Keep dismissed marks dismissed and study the live paragraph

**Status:** Ready
**Branch:** `claude/transient-reader-state`
**Requested:** 18 October 2026, by the maintainer

### Goal

What the reader dismisses stays dismissed until a deliberate new result, and
selections copy exact source text in every layout. `S` measures from the
paragraph the cursor is actually in.

### Scope

[Proposal stage 2](proposals/CODEX_READER_WORKSPACE_PLAN.md#2-stabilize-transient-reader-state)
and the live-origin defect of [stage 7](proposals/CODEX_READER_WORKSPACE_PLAN.md#7-build-the-first-terminal-independent-essence-round-trip):
`sol/terminal/neovim.lua`, `sol/terminal/neovim.py`, `sol/terminal/neovim_reader.py`,
`sol/reader/` where needed, their tests, BEING and CHANGELOG. Authority: BEING
§§2, 4, 8; CORE §5.

### Constraints

Dismissal state stays transient (no workspace fields); canonical strings,
offsets and the sentence-study artifact format are unchanged. Running `S` saves
no visit. Do not touch `sol/essence/` (Codex's task).

### Acceptance

Esc, then `p`, `f`, a resize or `T` cannot bring dismissed marks back; opening a
new search result shows them again. Forward and reverse selection and `y` return
exact source slices around footnote callouts, multibyte and combining
characters and wrapped emphasis, in both reading modes and after reopening at
another width. After moving natively to another paragraph, `S` names that
paragraph as its origin, and Alt-Left from a result returns there. Focused tests
and the normal checks pass; the handoff says which terminal checks ran.

## Codex: Make sentence marking practical by hand

**Status:** In review
**Branch:** `codex/segmentation-marking-form`
**Requested:** 18 October 2026, by the maintainer

### Goal

The maintainer can mark a segmentation sample in an ordinary text editor by
pressing Enter after each sentence, instead of editing JSON, and turn the result
back into a review file that `sol analyze segmentation-check` scores.

### Scope

`sol/essence/` (`segmentation_check.py`, `cli.py`), its tests, ESSENCE and
CHANGELOG: an export of an unmarked sample to a plain-text marking form (one
block per passage, clearly separated, its text unsplit, a place to write an
exclusion reason) and an import that fills `gold_sentences` or
`exclude_reason`. Authority: ESSENCE §§3–5, 8.

### Constraints

Blind: the form never shows the segmenter's boundaries. The import refuses any
change other than added line breaks (and exclusion lines), names the passage and
place of a mismatch, and writes a new owner-only file outside Git without
overwriting. Sample size, seed and targets stay the maintainer's decision.
`punctuation-rules-v1`, its artifacts, the protocol and dependencies are
unchanged. Do not touch `sol/terminal/` or `sol/reader/` (Claude Code's task).

### Acceptance

Synthetic round trips (export, add line breaks, import, check) give the expected
scores; edited words, a dropped passage, a changed sample or an existing output
file are refused. The documentation check and the full suite pass. ESSENCE
describes the procedure in a few steps a non-programmer can follow.

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
