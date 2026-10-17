# Handoff reports

Claude Code adds one report per completed task, newest first, so a reviewer can
judge the work from GitHub alone: the report says what to look at, the pull
request shows the diff. Reports describe; they do not change what the four
authorities ([Architecture](../ARCHITECTURE.md), [BEING](../BEING.md),
[ESSENCE](../ESSENCE.md), [CORE](../CORE.md)) say. Keep each report short; the
commit messages and diff carry the detail. Trim reports older than the last few
merged tasks; Git history keeps them.

<!--
Template — copy to the top of the reports and fill in every heading.
Write "None." rather than deleting a heading.

## <Task title> — <date>

**Task:** <link to the CURRENT_TASK version or its title>
**Branch / PR:** `claude/<name>` · <PR link or "not opened: reason">
**Last implementation commit:** `<full SHA>` (this report is committed after it)

### Changed files
- `<path>` — <what and why, one line>

### Tests performed
- <command> — <result, e.g. "1527 passed, 11 skipped">
- <manual or real-corpus check> — <what was observed>

### Outstanding issues
- <known limits, failures, things not done>

### Decisions requiring approval
- <decision, the options, and what was assumed meanwhile>
-->

## Coordination workflow between Claude Code and ChatGPT — 17 October 2026

**Task:** [CURRENT_TASK](CURRENT_TASK.md), "Coordination workflow between Claude Code and ChatGPT"
**Branch / PR:** `claude/coordination-workflow` · not opened yet: the session could not push, and `gh` is not installed
**Last implementation commit:** `3303502a3adab2275f42d85bc7a47d3273f3fcf0`

### Changed files
- `CLAUDE.md` — Claude Code's working rules: read the task and the latest handoff first, branch per task, run checks, report, open a PR.
- `docs/coordination/CURRENT_TASK.md` — the one active task, with a template for the next.
- `docs/coordination/HANDOFF.md` — this file: reports with SHA, files, tests, issues, decisions.
- `CONTRIBUTING.md` — one paragraph linking the three files.
- `README.md` — separate commit `0e496b8c53e1fe9308fb5a16bf636943dbf9ea04`: the prose-input link added in `7fe81fa` pointed at `docs/PROSE_INPUTS.md`, which lives in `docs/legacy/`; the CI documentation check failed on it.

### Tests performed
- `scripts/check_docs.py` — OK (four authorities, links, legacy inventory). It allows `docs/coordination/` because only the top level of `docs/` is reserved for the authorities.
- Full unit suite — 1527 passed, 11 skipped. No application code changed.

### Outstanding issues
- Push and PR are left to the maintainer (commands in the pull-request notes of the session).
- ChatGPT cannot commit; the maintainer copies its next task into `CURRENT_TASK.md`.
- `AGENTS.md` (the ChatGPT project's untracked mirror instructions) stays untracked and unchanged.

### Decisions requiring approval
- **Push policy.** Approved by the maintainer: CONTRIBUTING now says branch and pull request, with the maintainer merging, matching CLAUDE.md.
- **Who writes `CURRENT_TASK.md`.** Assumed: the maintainer, possibly pasting ChatGPT's draft. Alternative: ChatGPT drafts in a PR comment and Claude Code commits it at the start of the task.

## Footnotes, search marks, retyped mathematics and the sentence study — 17 October 2026

Recorded retrospectively so this work can be reviewed; it was committed to `main` before the workflow existed and has no pull request.

**Task:** maintainer's requests in a Claude Code session; then the plan in [Architecture §6](../ARCHITECTURE.md#6-immediate-development-order-and-acceptance-gates)
**Branch / PR:** `main`, commits `a84a246`…`92fa35f` (rebased onto `7fe81fa`)
**Last implementation commit:** `92fa35fe1ec4588ef19cb583501073966a9e67e5`

### Changed files
- `sol/reader/surface.py`, `sol/terminal/neovim.py`, `sol/terminal/neovim.lua` — `c` shows footnote text (from `note_paragraph` records, previously never loaded); footnote numbers drawn where the book prints them.
- `sol/reader/typography.py` — reports each footnote callout's plain-text offset.
- `sol/terminal/neovim_reader.py`, `neovim.lua` — search marks in the opened passage; `S` runs the sentence study, Enter opens a sentence, Alt-Left returns.
- `sol/essence/sentences.py`, `sol/essence/cli.py` — `sol analyze sentences` and its `check`.
- `docs/ARCHITECTURE.md`, `BEING.md`, `ESSENCE.md`, `CORE.md`, `CHANGELOG.md` — dated status for each workstream.
- Tests: `test_sentence_study.py` (new), `test_neovim_reader.py`, `test_reader_surface_neovim.py`, `test_reader_surface_neovim_host.py`, `test_reader_typography.py`.

### Tests performed
- Full suite — 1527 passed, 11 skipped; documentation check OK.
- Real corpus — all 761 linked footnotes get a placed number; the sentence study ran on the whole book (9,127 sentences) and from the reader on a real section (1.4 s, returned to the exact origin). Longest sentences and samples of split and unsplit boundaries were read by eye.

### Outstanding issues
- No human reading trial of these features yet; no formal error rate for sentence segmentation; one known miss (a sentence inside a parenthesis opened mid-sentence).
- Outside Git: 30 records of the private corpus had mathematics retyped from PDF crops (audit in the corpus); they keep `needs_visual_review` until the maintainer confirms them.

### Decisions requiring approval
- **Retyped mathematics.** BEING §5 now distinguishes a transcription read from the crop (kept pending) from a guess. Approve, or prefer crops only.
- **Sentence-study scope from the reader** is the loaded section only; selection-sized scopes would need a decision on how a selection becomes a study scope.
