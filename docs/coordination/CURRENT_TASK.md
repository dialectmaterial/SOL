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

## Claude Code: BEING relocation

**Status:** In review (first PR; the composition root follows after Codex B)
**Branch:** `claude/being-relocation`
**Scope:** `sol/terminal/{neovim,neovim_reader,reader_channel,runtime,splash,window}.py`,
the Lua files and `fonts/` → `sol/being/neovim/`; `sol/reader/{actions,surface,render,shell}.py`
→ `sol/being/`; `navigation` → `sol/being/quantity/`; `search`, `structure`,
`typography` → `sol/being/quality/`; `sol/workspace/` → `sol/being/workspace/`.
Afterwards (second PR, after Codex B merges): the composition root
`sol/reader/{app,launch,options}.py` out of `sol.reader`, and removal of the
empty `sol/reader` and `sol/terminal` packages.

## Codex A: decouple the ESSENCE launch

**Status:** In review
**Branch:** `codex/decouple-essence-launch`
**Requested:** 22 October 2026, by Claude for the maintainer
**Authority:** SPECULATIVE §5.2; Architecture §9; stage D rules above.
**Scope:** remove `sol.essence.tui`/`context` imports from
`sol/being/neovim/reader.py`; move the existing transient launch-file schema,
validation and owner-only I/O into a neutral module; probe Textual without
loading the ESSENCE interface. Record alternatives and reasoning in Architecture
§9 and resolve the Neovim row's pending note. Preserve format, behavior, messages,
lifetime and OSC bytes; saved investigation state stays with ESSENCE.
**Acceptance:** fresh-process import/launch boundary test; full suite and docs
check; stage D entry-point/wheel checks; merge `origin/main` and resolve any
integration with #97/#98 before opening the PR; handoff, ordinary worktree git
commit, push and PR against main. Do not merge the PR.

## Codex B: CORE and shared relocation

**Status:** In review
**Branch:** `codex/core-shared-relocation`
**Scope:** register rows for `terminal.commands`, `terminal.reference`,
`reader.onboarding`, `terminal.source`, `terminal.text` and the themes:
- `sol/terminal/reference.py` → CORE (the `sol reference` command face);
- the path resolver of `sol/terminal/commands.py` (`resolve_file_path` and its
  helpers) → CORE; the printing of `sol read` stays with the CLI, in `sol/reader/`
  for now;
- `sol/reader/onboarding.py` → CORE's corpus maintenance (`sol/corpus/`);
- `sol/terminal/source.py` split: verified snapshot, page capture and crops →
  CORE; the PDF viewer (Zathura open, highlight, follow) → `sol/being/source_view.py`;
- `sol/terminal/text.py` and the theme data (`sol/terminal/theme.py` plus the theme
  list, default theme and width constants now in `sol/reader/options.py`) → a
  shared presentation package outside the logical hierarchy, `sol/presentation/`,
  so that `sol.essence.tui` no longer imports the reader's option parser.
CORE must stay importable without a terminal, workspace or reader
([CORE §8](../CORE.md#8-scope-and-integrity-checklist)). Files: those modules,
their tests, `docs/CORE.md`, your register rows.

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
