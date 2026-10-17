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

## Sentence-segmentation error measurement — 18 October 2026

**Task:** [Codex: Measure sentence-segmentation error](https://github.com/dialectmaterial/SOL/blob/b07fdffacaf9ac812d947b351bb7a309d6e4b966/docs/coordination/CURRENT_TASK.md#codex-measure-sentence-segmentation-error).

**Branch / PR:** `codex/sentence-segmentation-check`; [open the review PR](https://github.com/dialectmaterial/SOL/pull/new/codex/sentence-segmentation-check) after branch publication.

**Last implementation commit:** `ce0135ef69ead149013bbb4d730d6b502e216a6a` (code and documentation complete; this report is committed last).

### Changed files

- `sol/essence/segmentation_check.py` — blind, reproducible equal-per-doctrine samples; complete source-bound marks or explicit exclusions; exact internal-boundary scores, error offsets and per-doctrine summaries. Samples are owner-only, non-overwriting and outside Git.
- `sol/essence/cli.py` — `sol analyze segmentation-sample` and `segmentation-check`; no change to existing sentence-study commands or formats.
- `tests/test_segmentation_check.py` — invented gold examples, malformed/stale input and privacy checks; four known rule limitations are expected failures rather than silent method fixes.
- `docs/ESSENCE.md`, `CHANGELOG.md` — private human-marking procedure, metric definitions, known limits and proposed pilot criteria. This handoff is the only other intended documentation change until the shared task board is available on main.

### Tests performed

- Focused suites: segmentation comparison (20 tests, including 4 expected failures), unchanged sentence study (9 tests) and existing analysis CLI (24 tests) — OK.
- `.venv/bin/python -B scripts/check_docs.py` — OK; external URLs were not network-checked.
- `.venv/bin/python -B -m unittest discover -s tests` — 1,558 tests run; OK (11 skipped, 4 expected failures). XDG config/data/cache/state and Neovim log locations were isolated. Packaging checks are included.
- Both commands' help works through `python -m sol analyze`. Synthetic end-to-end sample/mark/compare gives 4 matching boundaries, 1 false split and 1 miss (80% precision/recall); this is test data, not a book estimate. Existing sentence artifacts and canonical fixture bytes remain unchanged.
- No real-book sample or markings were generated, no human error rate is claimed, and no terminal UI/manual reading check was required or performed.

### Outstanding issues

- The unchanged rules retain misses inside mid-sentence parentheses, suppression after abbreviations that really end sentences, lower-case sentence starts, and false splits at physical line breaks. Their frequency in the book remains unmeasured.
- The assigned two-agent board is still only on `origin/claude/two-agent-board` at this report's preparation. The maintainer was asked to merge it before finalization; its Codex status cannot be changed on main without copying or replacing the unmerged board. The implementation is ready for review; the board status update remains pending that merge.
- The unpublished task branch was checked/rebased against current `origin/main` (`3ef6528`) before this report. Earlier handoff entries remain intact. No `sol/terminal/`, `sol/reader/`, `punctuation-rules-v1` code, protocol, schema or dependency changes are included. Private source/corpus/workspaces and untracked `AGENTS.md` are excluded.

### Decisions requiring approval

- **Pilot size:** propose 90 complete passages, 30 per doctrine, seed `20261018`; seek at least 300 human-marked internal boundaries before using quality targets, expanding by 10 passages per doctrine with the same ranking if approved. No automatic size default or real-book sampling run was adopted.
- **Error tolerance:** propose at least 98% boundary precision and recall overall, and at least 95% of both per doctrine. These are proposed descriptive pilot targets, not certified population bounds or an acceptance gate applied by the tool.
- **Gold review:** approve the sentence-end/closing-punctuation convention, explicit exclusions and independent adjudication of doubtful marks. Any later segmentation-rule, artifact or dependency change needs its own approval and versioning; none is proposed as implemented here.

## Codex reader and workspace proposal — 17 October 2026

**Task:** maintainer's request to preserve the [complete implementation proposal](proposals/CODEX_READER_WORKSPACE_PLAN.md) for shared review; no application implementation.

**Branch / PR:** [codex/reader-workspace-proposal](https://github.com/dialectmaterial/SOL/tree/codex/reader-workspace-proposal) is published. PR not opened: the GitHub integration returned HTTP 403, `Resource not accessible by integration`; `gh` is not installed and no browser automation session is available. [Open the proposal PR](https://github.com/dialectmaterial/SOL/pull/new/codex/reader-workspace-proposal).

**Last implementation commit:** `26840f58d3a344a013bd0b09f053b253190bc098` (proposal document only; this report is committed afterward).

### Changed files

- `docs/coordination/proposals/CODEX_READER_WORKSPACE_PLAN.md` — preserves all seven original stages, technical choices, dependencies, acceptance gates, outstanding decisions and a proposed first task; reconciles the already shipped sentence study and reader round trip.
- `docs/coordination/HANDOFF.md` — this entry makes the proposal discoverable from the shared coordination workflow. Earlier reports are retained unchanged.

### Tests performed

- `scripts/check_docs.py` — OK: four authorities, local links/anchors and lossless legacy inventory; external URLs were not network-checked.
- `python -B -m unittest discover -s tests` — 1,538 tests run; OK (11 skipped). Commands used the live checkout's existing virtual environment from the isolated proposal worktree, with temporary XDG config/data/cache/state and Neovim log locations.
- Synthetic probes on baseline `dfe075a` reproduced navigation saving a destination before failed view preparation, dismissed search marks returning after a mode switch, missing reader note-staleness metadata, and the sentence study using Python's earlier passage instead of the live native-cursor paragraph as its origin. No fixes or regression-test files were added.
- No manual Alacritty/Kitty session, sustained reading trial or independent proofreading of private mathematical transcriptions was performed.

### Outstanding issues

- This is a proposal for review, not approval or implementation of its stages. `CURRENT_TASK.md` and agent-role instructions remain unchanged; the maintainer chooses the next task and implementer.
- The plan now treats the sentence method (`d43e09b`) and in-process reader round trip (`04dcebc`) as implemented foundations needing validation, rather than proposed new features.
- Claude's coordination introduction was merged in PR #1 while the repository was being inspected. Its subsequent policy clarification `59602dd` was still separate at this proposal's base; this branch neither copies nor overwrites it.
- The original live worktree, untracked `AGENTS.md`, synced sources, canonical corpus, workspaces and four authorities were untouched. Only the two documentation files above are intended changes.
- The proposal is readable on the published branch. PR creation remains a maintainer step because of the integration's permission limit; no account permissions were changed. Use the link above, or run the following from an authenticated GitHub CLI installation:

  ```sh
  gh pr create --repo dialectmaterial/SOL --base main --head codex/reader-workspace-proposal --draft --title "Review the Codex reader and workspace implementation proposal" --body "Documentation-only proposal for shared review: docs/coordination/proposals/CODEX_READER_WORKSPACE_PLAN.md and its entry in docs/coordination/HANDOFF.md. The seven stages remain proposed; CURRENT_TASK.md and application code are unchanged."
  ```

### Decisions requiring approval

- Review the proposal and select one bounded task before any stage is implemented. Stage 1, navigation failure recovery, is recommended first.
- The proposal's decision table preserves the unresolved issues: Codex's standing role/task assignment, note retraction and durable drafts/spans, segmentation validation and scope, pending mathematical review, general investigation transport and comparison endpoint binding. No new public contract, schema, dependency or authority decision is approved by this PR.

## Coordination workflow between Claude Code and ChatGPT — 17 October 2026

**Task:** [CURRENT_TASK](CURRENT_TASK.md), "Coordination workflow between Claude Code and ChatGPT"
**Branch / PR:** `claude/coordination-workflow` · merged as PR #1 (`dfe075a`) and, for the later CONTRIBUTING commit `59602dd`, PR #2 (`f574d84`)
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
