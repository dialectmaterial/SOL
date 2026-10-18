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

## Claude Code: Finish the reader speed list

**Status:** Ready
**Branch:** `claude/reader-speed-list`
**Requested:** 19 October 2026, by the maintainer

### Goal

Bring a section move from about 0.68 s towards 0.5 s on the real book, by the
remaining items measured on 19 October.

### Scope

`sol/core/protocol.py`, `sol/core/models.py`, `sol/reader/actions.py`,
`sol/reader/surface.py`, their tests, CORE and CHANGELOG:
- a faster in-memory comparison in `_fresh_snapshot` (JSON text plus structural
  equality). **Approved by the maintainer on 19 October:** it may accept an
  in-memory value that is a subclass of `int` or `float` with the same value,
  which the current comparison refuses; record this in CORE §6;
- the deep copy of the section in `sol/reader/surface.py`;
- repeated passage lookups (`Book.selection`, `find_passage`,
  `ReadingSession.current`), with identical results.
Measure with `scripts/reader_timings.py`. Authority: CORE §§4–6.

### Constraints

File fingerprints are still checked on every call; no other relaxation. No
change to the CORE API, reference protocol, corpus contract or workspace
schema. Do not touch `sol/terminal/` (Codex's task).

### Acceptance

Before/after timings in the handoff; existing refusal tests unchanged; a test
for each relaxed or rewritten check showing what it still refuses. The
documentation check and the full suite pass.

## Codex: Split the Lua reader into modules

**Status:** Ready
**Branch:** `codex/lua-modules`
**Requested:** 19 October 2026, by the maintainer

### Goal

`sol/terminal/neovim.lua` (about 1,330 lines) becomes a small entry file plus
cohesive modules (for example panels, the note editor, footnote view, search
and markers), with no change in behaviour, so stage 6 and later work touch
smaller files.

### Scope

[Proposal cleanup](proposals/CODEX_READER_WORKSPACE_PLAN.md#cleanup-alongside-the-stages):
`sol/terminal/*.lua`, the Python code that locates and packages the Lua files
(`sol/terminal/neovim.py`, packaging data, `scripts/install.py` if needed),
tests, and Architecture or BEING only where they name files.

### Constraints

No behaviour change: every existing headless Neovim and controller test passes
unchanged, except where a test names a file path. Modules are loaded from the
installed package directory only, never from the user's runtime path or
configuration. The wheel and source archive still contain every Lua file, and
the packaging checks prove it. Do not touch `sol/core/`, `sol/reader/` or
`sol/terminal/neovim_reader.py` (Claude Code's task).

### Acceptance

The documentation check and the full suite pass, including packaging checks;
a reader started from an installed wheel in a temporary environment opens a
passage headlessly. The handoff lists the modules and what each owns.

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
