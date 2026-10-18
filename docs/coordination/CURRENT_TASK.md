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

## Claude Code: Reconcile the ESSENCE interface decisions in the documentation

**Status:** In review
**Branch:** `claude/essence-interface-docs`
**Requested:** 18 October 2026, by the maintainer, with the
[ESSENCE interface brief](proposals/ESSENCE_INTERFACE_BRIEF_2026-10-18.pdf)

### Goal

The four authorities record the brief's decisions (hybrid Neovim/Textual
surfaces, on-demand lifecycle, two presentations, CORE-optional ESSENCE,
staged plan, model-history encyclopedia) as Decision or Proposed, reconciled
with current code.

### Scope

`docs/ARCHITECTURE.md`, `docs/BEING.md`, `docs/ESSENCE.md`, `docs/CORE.md`; the
brief stored under `docs/coordination/proposals/`.

### Constraints

Documentation only: no Textual UI, model or corpus schema. `docs/legacy/` and
all existing contracts unchanged.

### Acceptance

Documentation check and full suite pass; the handoff maps each decision to the
edited sections and lists open questions.

## Codex: Split the Lua reader into modules

**Status:** In review
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
