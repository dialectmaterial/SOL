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

## Cleanup plan (maintainer, 21 October 2026)

The maintainer approved removing what the project's history left behind:

1. **Shell:** `--shell` stays but minimal: book browsing only (`ls`, `cd`,
   `tree`, `read`, `cat`, `search`, `open`, `context`, `info`, `guide`, `help`,
   `exit`) on plain `input()`/readline. Removed: Kitty (`sol-kitty`, panes,
   comparison and ESSENCE panes), the private handoff transport and Zsh
   launcher, workspace commands in the shell, `--ui`/`--editing-mode`, and the
   `prompt-toolkit` dependency. **`sol compare` is removed.** Review and relate
   commands go; data already stored in workspaces stays readable and exportable
   (no schema change or migration).
2. **Experiments:** `experiments/reader_surfaces/` and the Neovim research-export
   mode (`neovim.run`, `:SOLExport`, the non-integrated Lua paths) are removed;
   the reader keeps only its integrated mode.
3. **Leftovers:** `--pdf` (`legacy_pdf.py`), hidden `--engine`, empty extras
   (`corpus`, `shell`, `extraction`), unreachable modules.
4. **Documents:** anything still useful in `docs/legacy/` moves into the four
   authorities, CONTRIBUTING or README; then `docs/legacy/` is deleted (Git keeps
   it). Finished proposals go; HANDOFF keeps only recent reports.
5. **ESSENCE tools:** `sol analyze term` (its tokenizer moves to
   `sol/essence/tokenization.py`), the segmentation-pilot commands and
   `scripts/formula_review_sheet.py` are removed.
6. **Names:** `sol analyze` becomes **`sol essence`**; `sol --reader` becomes
   **`sol being`**; bare `sol` still opens the reader (`sol being`).

Every step passes the documentation check and full suite; removal PRs are
reviewed by the other agent before merging.

## Claude Code: Fold the legacy documents in, then remove them (step 4)

**Status:** In review
**Branch:** `claude/legacy-docs`

### Scope

`docs/legacy/`, `docs/coordination/` (old proposals, HANDOFF), the four
authorities, README, CONTRIBUTING, CLAUDE.md, `scripts/check_docs.py` and its
test. No code. Next: steps 1, 3 and 6's `sol being` (app, options, shell,
`sol/terminal/` except the Lua reader, packaging).

## Codex: Remove the experiments and the research-export mode (step 2)

**Status:** In review
**Branch:** `codex/remove-experiments`

### Scope

`experiments/`, `neovim.run` and research export in `sol/terminal/neovim.py`,
the non-integrated paths in `sol/terminal/neovim*.lua` (and `neovim.lua`),
`sol/reader/surface.py` only as far as the experiments need, their tests
(rewrite the headless Lua tests that run the non-integrated mode to the
integrated one rather than dropping coverage of reader behaviour),
`scripts/reader_timings.py` if it depends on them, CHANGELOG, BEING.
Not `docs/legacy/` or `docs/coordination/proposals/` (Claude). Next: steps 5
and 6's `sol essence` rename (`sol/essence/`, its tests and ESSENCE).

### Acceptance

No reader behaviour lost; documentation check and full suite; the handoff
lists removed files and line counts.

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
