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

## Sentence marking in an ordinary text editor — 18 October 2026

**Task:** [Codex: Make sentence marking practical by hand](CURRENT_TASK.md#codex-make-sentence-marking-practical-by-hand).
**Branch / PR:** `codex/segmentation-marking-form` · [PR #8](https://github.com/dialectmaterial/SOL/pull/8), opened with `gh pr create --base main`. Task status: `In review`.
**Last implementation commit:** `6e27ed1c58d6439e6b7ec46603a0884d39074f25` (implementation and documentation; the task-board merge and this report follow).

### Changed files

- `sol/essence/segmentation_marking.py` — blind, sample-fingerprinted plain-text blocks; import accepts only added LF breaks and designated exclusion reasons, names the passage/source codepoint/form location on a text mismatch, and fills the existing review fields without editing source text.
- `sol/essence/segmentation_check.py` — shares the existing outside-Git, owner-only, non-overwriting writer with text forms; JSON serialization and the scorer remain unchanged.
- `sol/essence/cli.py` — `segmentation-export` and `segmentation-import`, with explicit reviewer attribution and bounded UTF-8 input; no sample text or predictions in their receipts.
- `tests/test_segmentation_marking.py` — 14 synthetic tests: blind export independent of predictions, exact mark/import/check round trips, Unicode and original-newline handling, edits/omissions/order/sample/generation failures, exclusions, privacy and overwrite refusal.
- `docs/ESSENCE.md`, `CHANGELOG.md` — four-step editor workflow and its limits. Only Codex's status changes in `CURRENT_TASK.md`; all earlier handoff reports are preserved below.

### Tests performed

- `.venv/bin/python -B -m unittest discover -s tests -p 'test_segmentation*.py'` — 35 tests; OK (4 existing expected failures).
- `.venv/bin/python -B scripts/check_docs.py` — OK; external URLs were not network-checked.
- `.venv/bin/python -B -m unittest discover -s tests` — 1,582 tests after merging PR #9; OK (11 skipped, 4 existing expected failures). XDG config/data/cache/state and Neovim log locations were isolated; packaging checks are included.
- Both command help pages work through `python -m sol analyze`. The synthetic end-to-end CLI review retains 4 matching boundaries, 1 false split and 1 miss (80% precision/recall/F1), not a book accuracy estimate. Existing sentence artifacts and source fixture bytes remain unchanged.
- No real-book sample or human markings were made, and no manual graphical-editor or terminal-reader trial was performed.

### Outstanding issues

- Source newlines are preserved but are not marks; adding another Enter there marks a boundary. An unsplit block declares one sentence, so a blank exclusion line cannot prove a passage was actually reviewed. The form and ESSENCE explain this; unreviewed blocks should be excluded explicitly.
- Editors must preserve spaces, Unicode and LF line endings. Auto-indent, trailing-space trimming, hard reflow, BOM/CRLF conversion or normalization cause refusal rather than silent repair.
- The branch started at `origin/main` (`e203a6d`), then merged PR #7 (`2e21734`) and PR #9 (`8c7cf31`) without rewriting published history. The CHANGELOG/HANDOFF conflicts retain both entries with this work first; Claude's entries and task status are preserved. Relative to current main, no reader/terminal, segmenter, sentence-study artifact, CORE protocol, dependency, canonical corpus or workspace changes are included; private source material and `AGENTS.md` stay outside Git.

### Decisions requiring approval

- The earlier proposed pilot size, seed, annotation adjudication and quality targets remain maintainer decisions (90 passages/30 per doctrine, seed `20261018`, seek 300 internal gold boundaries; proposed precision/recall targets 98% overall and 95% per doctrine). This task neither adopts defaults nor runs or approves that pilot.

## Keep dismissed marks dismissed and study the live paragraph — 18 October 2026

**Task:** [CURRENT_TASK](CURRENT_TASK.md), "Claude Code: Keep dismissed marks dismissed and study the live paragraph" ([proposal stage 2](proposals/CODEX_READER_WORKSPACE_PLAN.md#2-stabilize-transient-reader-state), live-origin part of stage 7)
**Branch / PR:** `claude/transient-reader-state` · opened with `gh pr create`
**Last implementation commit:** `ca654fbe851e5769727d51dcc172a34c6fb23cdf`

### Changed files
- `sol/terminal/neovim.lua` — `Esc` also clears `data.search_marks`, so views rebuilt from the current one (`p`, `f`, paragraph-mode `b/n`) no longer redraw dismissed marks.
- `sol/terminal/neovim_reader.py` — the study's origin is the request packet's reference (checked with `check_return_reference`), not Python's last accepted position.
- `tests/test_reader_surface_neovim.py` — headless Neovim: dismissal survives `p`, `]p`/`[p`, `p`, `f`, resize and `T`, and a new result shows marks; exact selection and yank around callouts, multibyte/combining characters and emphasis, forward and reverse, both modes, widths 72 and 24.
- `tests/test_neovim_reader.py` — the study origin follows the live packet, saves no visit, and Alt-Left from a result returns to the live cursor.
- `docs/BEING.md` (§2 controls table and "Transient state"), `CHANGELOG.md`.

### Tests performed
- Reproduced first: marks returned after `p`, `]p`/`[p` and `f` (not after resize or `T`); the study named the previously saved paragraph as origin.
- The selection/yank test passed before the change; it pins existing behaviour.
- `.venv/bin/python -B scripts/check_docs.py` — OK.
- `.venv/bin/python -B -m unittest discover -s tests` — 1568 tests, OK (11 skipped, 4 expected failures).
- Real terminal: none by hand. The headless tests run the real Lua adapter in Neovim, not a terminal emulator.

### Outstanding issues
- `Esc` hides marks for the shown view only; history back to a search result reloads from Python without marks, as before (history never restored marks).
- Visual checks in Alacritty/Kitty at 80x24 remain for the stage 5 reading pass.

### Decisions requiring approval
- **When marks return.** Implemented as the proposal suggested: only a newly opened search result (`/` then Enter, Ctrl-N/Ctrl-P) shows marks again; mode, focus, theme and layout changes never do.

## Sentence-segmentation error measurement — 18 October 2026

**Task:** [Codex: Measure sentence-segmentation error](https://github.com/dialectmaterial/SOL/blob/b07fdffacaf9ac812d947b351bb7a309d6e4b966/docs/coordination/CURRENT_TASK.md#codex-measure-sentence-segmentation-error).

**Branch / PR:** `codex/sentence-segmentation-check` is pushed; [open the review PR](https://github.com/dialectmaterial/SOL/pull/new/codex/sentence-segmentation-check). PR creation through the GitHub integration returned HTTP 403, `Resource not accessible by integration`; `gh` is not installed. Task status is `In review`.

**Last implementation commit:** `722e68cf4734bff71c841e940a552e934a1c7d32` (review follow-up: clear doctrine-path refusal and regression test; this report is committed last).

### Changed files

- `sol/essence/segmentation_check.py` — blind, reproducible equal-per-doctrine samples; complete source-bound marks or explicit exclusions; exact internal-boundary scores, error offsets and per-doctrine summaries. Samples are owner-only, non-overwriting and outside Git. Unexpected doctrine paths now raise a clear `ValueError` rather than leaking a lookup error.
- `sol/essence/cli.py` — `sol analyze segmentation-sample` and `segmentation-check`; no change to existing sentence-study commands or formats.
- `tests/test_segmentation_check.py` — invented gold examples, malformed/stale input and privacy checks; four known rule limitations are expected failures rather than silent method fixes.
- `docs/ESSENCE.md`, `CHANGELOG.md` — private human-marking procedure, metric definitions, known limits and proposed pilot criteria. `docs/coordination/CURRENT_TASK.md` changes only Codex's status to `In review`; earlier handoff reports are preserved.

### Tests performed

- Focused segmentation comparison: 21 tests, including 4 expected failures — OK. The unchanged sentence study (9 tests) and existing analysis CLI (24 tests) passed in the original implementation pass and remain covered by the full suite.
- `.venv/bin/python -B scripts/check_docs.py` — OK; external URLs were not network-checked.
- `.venv/bin/python -B -m unittest discover -s tests` — 1,565 tests run after merging PR #5 and adding the doctrine-path guard; OK (11 skipped, 4 expected failures). XDG config/data/cache/state and Neovim log locations were isolated. Packaging checks are included.
- Both commands' help works through `python -m sol analyze`. Synthetic end-to-end sample/mark/compare gives 4 matching boundaries, 1 false split and 1 miss (80% precision/recall); this is test data, not a book estimate. Existing sentence artifacts and canonical fixture bytes remain unchanged.
- No real-book sample or markings were generated, no human error rate is claimed, and no terminal UI/manual reading check was required or performed.

### Outstanding issues

- The unchanged rules retain misses inside mid-sentence parentheses, suppression after abbreviations that really end sentences, lower-case sentence starts, and false splits at physical line breaks. Their frequency in the book remains unmeasured.
- The task branch was checked/rebased against `origin/main` (`3ef6528`) before initial publication. The two-agent board (`1f9660c`) and then PR #5 (`449fb02`) were merged without rewriting published commits. Both CHANGELOG entries and both handoff reports are preserved, with this work first. Codex's task remains `In review`; Claude's task status is unchanged from main. Relative to current main, no `sol/terminal/`, `sol/reader/`, `punctuation-rules-v1` code, protocol, schema or dependency changes are included. Private source/corpus/workspaces and untracked `AGENTS.md` are excluded.
- The merge's index-wide whitespace check flagged main's existing Markdown hard break in `docs/BEING.md:3`; it was retained unchanged. The feature-branch diff whitespace check passes.
- PR creation remains a maintainer step because of the integration's permission limit; no account permissions were changed. Use the link above, or run from an authenticated GitHub CLI installation:

  ```sh
  gh pr create --repo dialectmaterial/SOL --base main --head codex/sentence-segmentation-check --title "Measure sentence segmentation against private human annotations" --body "Validation-only tooling, tests and proposed private pilot; see docs/coordination/HANDOFF.md#sentence-segmentation-error-measurement--18-october-2026. Frozen punctuation-rules-v1 and existing artifacts/protocol/dependencies are unchanged."
  ```

### Decisions requiring approval

- **Pilot size:** propose 90 complete passages, 30 per doctrine, seed `20261018`; seek at least 300 human-marked internal boundaries before using quality targets, expanding by 10 passages per doctrine with the same ranking if approved. No automatic size default or real-book sampling run was adopted.
- **Error tolerance:** propose at least 98% boundary precision and recall overall, and at least 95% of both per doctrine. These are proposed descriptive pilot targets, not certified population bounds or an acceptance gate applied by the tool.
- **Gold review:** approve the sentence-end/closing-punctuation convention, explicit exclusions and independent adjudication of doubtful marks. Any later segmentation-rule, artifact or dependency change needs its own approval and versioning; none is proposed as implemented here.

## Preserve reading state when navigation is refused — 18 October 2026

**Task:** [CURRENT_TASK](CURRENT_TASK.md), "Claude Code: Preserve reading state when navigation is refused" ([proposal stage 1](proposals/CODEX_READER_WORKSPACE_PLAN.md#1-fix-navigation-failure-recovery-first))
**Branch / PR:** `claude/navigation-failure-recovery`, stacked on `claude/two-agent-board` (merge that first) · PR link in the maintainer's session
**Last implementation commit:** `faf7292a640f2ccace52510c6d12abf8d425160f`

### Changed files
- `sol/reader/actions.py` — `ReaderActions.staged()`: moves made inside the block are saved once, when it completes; any failure (including the save's own conflict or stale-corpus refusal) restores local state, history included. `accept_return_position(..., history_locations=True)` makes a same-passage jump its own history entry.
- `sol/terminal/neovim_reader.py` — every live route accepts the shown position, then stages the destination and prepares its view inside `staged()`; mode, focus, theme, notice and search marks are restored if that fails. The view in use changes only after success.
- `tests/test_neovim_reader.py` — injected view failure on all seven routes (`next`, `passage_next`, `marker_open`, `search_open`, `search_next`, `history_back`, `study_open`): saved position stays the shown one, retry succeeds, history returns exactly once, reopen resumes correctly; mode/focus/theme survive a refused move; competing save and changed corpus refuse without saving.
- `tests/test_reader_actions.py` — `staged()` saves once, refuses nesting, rolls back on failure and on a conflicting save.
- `docs/BEING.md` (§2 "Refused moves", §7 limit), `CHANGELOG.md`.

### Tests performed
- Reproduced first: before the fix, the route test failed on all seven routes (the destination was saved although its view failed), and the mode test failed (a refused move's mode leaked into the next view).
- `.venv/bin/python -B scripts/check_docs.py` — OK.
- `.venv/bin/python -B -m unittest discover -s tests` — 1544 tests, OK (11 skipped).
- Real terminal: none. No manual Alacritty/Kitty session was run; refused moves are hard to trigger by hand without fault injection.

### Outstanding issues
- Editor-side failure after Python accepted a view (Neovim crash, or a response over the channel's 16 MiB budget) still leaves the destination saved; the reader exits and resumes there. Recorded in BEING §7; fixing it needs an acknowledgement from Neovim before saving.
- After another session's newer save, every move is refused until SOL is reopened. That is the existing compare-and-swap rule, not new, but the refusal message could say "reopen SOL".
- The competing-save and changed-corpus tests passed before the fix as well; they lock in existing refusals on the live routes.
- `node_open` shares the staged path but has no injected-failure case: the synthetic corpus's tree offers no second readable node.
- The study's origin still comes from Python's last accepted cursor rather than the live paragraph (proposal stage 7); left untouched, since `sol/essence/` work is Codex's lane.

### Decisions requiring approval
- **Saving the outgoing position on a refused move.** The position the screen shows is saved even when the move to the destination is refused. Alternative: save nothing on refusal. Assumed: save it, because the editor displayed it.
- **Same-passage jumps in history.** Opening a sentence, marker or tree node in the paragraph already shown now adds a history entry. Assumed acceptable; it only affects explicit jumps, not cursor motion.

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
