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

## Claude Code: The sentence study in ESSENCE

**Status:** Ready
**Branch:** `claude/essence-sentences-ui`
**Requested:** 19 October 2026, by the maintainer

### Goal

The sentence-length study, removed from the reader as `S`, runs from ESSENCE's
Experiment screen beside word frequencies, on a passage, section, the whole
book or a text file, and a listed sentence opens in the reader.

### Scope

[ESSENCE §4–§5, Experiment A](../ESSENCE.md#experiment-a--syntax-and-positionality-highest-priority),
[BEING §6](../BEING.md#6-being--essence-without-terminal-dogma): `sol/essence/tui/`,
`sol/terminal/` only if opening a sentence needs it, tests, ESSENCE §4 and CHANGELOG.
Call `sol.essence.sentences.analyze_sentences` with the v2 providers (#31);
Results shows counts, the histogram, means by place in the paragraph and the
longest sentences; Enter opens one through the reader's `essence_source`.

### Constraints

No change to `sol/essence/` outside `sol/essence/tui/` (Codex's lane) and no
change to the v1/v2 artifacts. Workspace sessions save the artifact; temporary
sessions save nothing. No new dependency.

### Acceptance

Textual pilot tests for choices, results, saving and opening a sentence; the
real-engine test; a real session on the book reported. Documentation check and
full suite pass.

## Codex: Proposal for the ESSENCE encyclopedia (stage 4)

**Status:** Ready
**Branch:** `codex/encyclopedia-proposal`
**Requested:** 19 October 2026, by the maintainer

### Goal

A reviewed proposal the maintainer can decide on, so that stage 4 can then be
built: how encyclopedia entries are written, sourced, related and checked.

### Scope

[ESSENCE §4 open decisions, §5 stage 4, §7](../ESSENCE.md#7-model-history-encyclopedia-and-task-registry-proposed):
a new `docs/coordination/proposals/ESSENCE_ENCYCLOPEDIA_PROPOSAL.md`. Cover the
source format (plain, structured Markdown per §7), the fields of the three
knowledge objects (historical entry, task/capability record, runnable
adapter), how relations in the genealogy carry a citation and a status, what
counts as a source, editorial and provenance rules, initial coverage (a short
list of entries, e.g. from n-gram counts and TF-IDF to word vectors and
transformer encoders), how entries link back to SOL's own methods, and a
design for a CORE-free validator and CLI. Include two or three complete
sample entries with real, checked citations, and say what is unknown.

### Constraints

A proposal, not an implementation: no application code, no change to the four
authorities, no dependency. Do not invent citations: every reference must be
one you can name exactly (authors, year, title, venue), or be marked as
needing a source. Do not touch Claude Code's files (`sol/essence/tui/`,
`sol/terminal/`).

### Acceptance

The documentation check passes; the proposal lists the decisions it asks the
maintainer to take, each with options and a recommendation.

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
