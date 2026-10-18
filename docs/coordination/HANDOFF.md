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

**Task:** <its title, linked to CURRENT_TASK.md at a commit (blob/<sha>/…), since the heading disappears when the task is replaced>
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

## Formula review sheet — 18 October 2026

**Task:** Codex: Formula review sheet, assigned directly by the maintainer in the Codex session; recorded in [CURRENT_TASK at c7e0181](https://github.com/dialectmaterial/SOL/blob/c7e01819a51f3c6650def3e2f36e1c695154db1b/docs/coordination/CURRENT_TASK.md#codex-formula-review-sheet).
**Branch / PR:** `codex/formula-review-sheet` · opening with `gh pr create --base main` after this report.
**Last implementation commit:** `db5ab104240d32edadbb04d285c17fa89d88dd33` (script, tests and behavior documentation; task assignment `c7e0181` and this report follow).

### Changed files

- `scripts/formula_review_sheet.py` — checkout-only `create`, interactive `review`, individual `record` and `check`. All flagged math records, including note paragraphs, or an explicit eligible-ID subset; exact typed text and every page/crop through unchanged `SourceService.capture` / `render_region`. Private HTML/JSON/assets, no replacement of existing sheets, temporary PDF/cache removed. Append-only JSONL human verdicts retain reviewer/time, correction notes and sheet/text/metadata bindings; changed displays/crops, malformed history and competing writers refuse. No canonical or workspace writes.
- `tests/test_formula_review_sheet.py` — nine synthetic tests: full record/page coverage, escaping, source failures, privacy and nonmutation, same-item history, skip/resume, invalid and competing input, tampering and a real Poppler/CLI round trip. The PDF/PNG builder functions are reused without borrowing another TestCase's setup.
- `docs/BEING.md` §5, `CHANGELOG.md` — usage, historical-source semantics and the separate human-approved application step. Codex's slot records the direct formula assignment; Claude's task remains as on merged main.

### Tests performed

- Documentation check passed. Full suite after rebasing onto #18: 1,612 tests, OK (11 skipped, 4 existing expected failures). Focused suite: nine tests, including actual Poppler crop/full-page output and CLI create → record → check. XDG/Neovim state was isolated.
- Real local book: 47 eligible flagged math records. The retyping audit contains 70 replacements across 30 distinct records; passed those existing IDs explicitly. Generated the private 30-record sheet with 49 source crops; every verdict remains pending, no testimony was inferred, no PDF copy remains in the output, and the canonical snapshot before/after is identical. Output location is disclosed privately in the session, not committed. Inspected a generated crop; HTML structure is tested, but no browser was available for a rendered layout check.
- Re-reviewed fixed [#16](https://github.com/dialectmaterial/SOL/pull/16#issuecomment-6247294242): deep-copied returned records and the single/batch mutation regression; docs, 1,603 tests and every GitHub check passed. It merged on the maintainer's instruction while review checks ran.
- Reviewed/merged [#18](https://github.com/dialectmaterial/SOL/pull/18#issuecomment-6247385054): task board only; separate worktree docs/1,603 tests and all GitHub checks passed. Rebasing retained Claude's updated slot. Reviewed [#19](https://github.com/dialectmaterial/SOL/pull/19#issuecomment-6247384407) separately: docs/1,605 tests and CI pass, but a synthetic canonical record with 70-level extra metadata is newly accepted instead of refused with `nesting_limit`. Posted the reproduction and left it for the author; the approved numeric-subclass exception does not cover this additional relaxation.

### Outstanding issues

- The private sheet is a fixed copy; the terminal command records progress. `check --corpus` requires exact generation agreement. Recording against the unchanged historical sheet remains possible after corpus changes; this declares only what the human saw there. Keep `sheet.json`, HTML/crops and the verdict history together for any later application step.
- There is deliberately no apply operation and no automatic `reviewed` status, correction or reindex. Human formula verification remains outstanding. The maintainer's subsequent Lua-module request is a separate task/branch; it is not implemented here.
- No changes to `sol/terminal/source.py`, Claude's speed files, dependencies, CORE/reference/corpus/workspace contracts, synced `sources/`, source PDF or canonical corpus. No private text, crops or verdicts are staged or committed.

### Decisions requiring approval

- None reserved. Defaults: offline HTML plus immutable JSON/crops, terminal skip/resume, append-only verdict events with the last per-item event used only for progress, explicit reviewer, required correction note, private 700/600 permissions, 16 MiB metadata/history reads, and explicit full-ID subset selection. Applying verdicts remains separately human-approved.

## Make reader moves fast without weakening checks — 19 October 2026

**Task:** ["Claude Code: Make reader moves fast without weakening checks"](https://github.com/dialectmaterial/SOL/blob/claude/assign-speed-and-footnotes/docs/coordination/CURRENT_TASK.md)
**Branch / PR:** `claude/fast-reader-moves`, stacked on #15 (task board), which is stacked on #13 · opened with `gh pr create`
**Last implementation commit:** `b1250a40bb7fe6e5bcdc3c899a5c9e8fb878fda7`

### Changed files
- `sol/core/protocol.py` — (1) the last few fully verified generations are kept as immutable JSON text, keyed by every file fingerprint; a call whose fingerprints match builds new records from it after `verify_snapshot_current`, instead of `load_snapshot`. Exactly as strict as before. (2) `single_action(snapshot)`: within one user action the full in-memory comparison runs at the first call and the verified copy is reused; files are still checked on every call.
- `sol/terminal/neovim_reader.py` — each editor request, and the first view, runs in one `single_action`.
- Review fix (Codex, PR #16): `check_reference(s)` returns a deep copy of each record, so a caller changing a returned record cannot alter what later calls in the same action treat as verified; Codex's reproduction is a regression test for single and batch checks.
- `tests/test_core_protocol.py` — the scope: a file change between two calls of one action is refused; an in-memory change during an action is refused by the next; results come from the verified files; another snapshot object is compared in full. The batch test now allows zero reloads instead of exactly one.
- `tests/test_neovim_reader.py` — a corpus changed between two requests refuses `next`, `previous` and `passage_next` without saving.
- `docs/CORE.md` (§6, "Verification cost", with the approved Decision), `CHANGELOG.md`.

### Tests performed
- `scripts/reader_timings.py --corpus local-corpus --repeats 3` on the real book, medians in ms (before from the 18 October baseline):

| Operation | Before | After |
| --- | ---: | ---: |
| Startup to first view | 1,792 | 767 |
| Section next / previous | 2,852 / 2,866 | 746 / 734 |
| Search-result open | 2,252 | 657 |
| History back | 2,271 | 689 |
| Sentence study `S` | 1,215 | 698 |
| Search | 312 | 172 |

- After step (1) alone, a section move was 1.6 s.
- Existing changed-corpus, stale-reference, mutated-memory and conflict tests pass unchanged except the one batch-count assertion above.
- `.venv/bin/python -B scripts/check_docs.py` — OK; `.venv/bin/python -B -m unittest discover -s tests` — 1594 tests, OK (11 skipped, 4 expected failures).

### Outstanding issues
- Target "well under half a second" missed: 0.65–0.75 s. What remains is the one full comparison per action (about 100 ms), nine fingerprint checks (about 13 ms each, kept deliberately), view building, and a deep copy of the sample in `sol/reader/surface.py` `__init__` (about 70 ms; Codex's file this round, a candidate for later).
- The verified-generation texts hold about 24 MB per corpus generation in memory (at most four generations).

### Decisions requiring approval
- **Once-per-action comparison:** approved by the maintainer in the session on 19 October 2026 and recorded as a Decision in CORE §6; nothing left open.
- **Default:** `single_action` lives in `sol.core.protocol` and is not exported from `sol.core`; the reader imports it from there.

## Footnote reading view — 18 October 2026

**Task:** [Codex: Footnote reading view](https://github.com/dialectmaterial/SOL/blob/5fad439ebfa27756b0c2fd127511e6483501f0e6/docs/coordination/CURRENT_TASK.md#codex-footnote-reading-view).
**Branch / PR:** `codex/footnote-view` · [PR #17](https://github.com/dialectmaterial/SOL/pull/17), opened with `gh pr create --base main`. Status: `In review`.
**Last implementation commit:** `650e7d17ce625e58a66c887b39395d451298d927` (projection/controller `e207f0d`, then panels/tests/documentation; this report follows).

### Changed files

- `sol/reader/surface.py` — canonical note/body link paths, bounded by eight distinct notes and 64 body paragraphs per note; no navigation or workspace operation.
- `sol/terminal/neovim.py` — one checked, on-demand footnote projection through `CaptureExport`, retaining each ordered paragraph's ID, CORE reference, exact text, local style/callout offsets, attribution and warnings. Links disclose cycles/depth bounds; text and presentation budgets refuse oversized views.
- `sol/terminal/neovim_reader.py` — only seven added/changed lines for `footnote_open` (`trail`) validation and dispatch. This shared-file exception was coordinated in [the task-board review](https://github.com/dialectmaterial/SOL/pull/15#issuecomment-6247113306); navigation and persistence are unchanged.
- `sol/terminal/neovim.lua` — separate book-note list in `c`, individual styled note panels, nested links and panel backtracking; popup return packets preserve the passage selection through close/resize/native `:q`. Personal notes and technical context have separate headings. Replies after a panel closes are ignored.
- `tests/fixtures_footnotes.py`, `tests/test_footnote_view.py`, `tests/test_reader_surface_neovim.py` — invented multi-paragraph and cyclic canonical notes; projection/controller refusals and real headless Neovim return/style/clipboard checks.
- `docs/BEING.md`, `CHANGELOG.md` — implemented controls, bounds and limits. Only Codex's task status changes in `CURRENT_TASK.md`; existing reports are retained.

### Tests performed

- Reviewed and merged [PR #13](https://github.com/dialectmaterial/SOL/pull/13#issuecomment-6247103589) and [task-board PR #15](https://github.com/dialectmaterial/SOL/pull/15#issuecomment-6247113306), each in a separate worktree: documentation and 1,592 tests passed (11 skipped, 4 expected failures); `gh pr checks --watch` finished with every check passing.
- Focused projection/controller suite: six tests. Headless/host suite: 69 tests, one skipped. Footnote scenarios cover widths 72/20, both reading modes, forward/reverse selections and exact yank, ordered multibyte/styled body records, per-paragraph attribution/review flags, nested links, cycles, backtracking, failed requests, late replies, resize and native window close.
- Documentation check passed. Full suite: 1,600 tests, OK (11 skipped, 4 existing expected failures), using the checkout's `.venv/bin/python -B` with isolated XDG state and Neovim logs. Source changes between controller requests and during projection are refused; panel requests leave the saved position/selection and workspace bytes unchanged.
- Reviewed newly opened [PR #16](https://github.com/dialectmaterial/SOL/pull/16#issuecomment-6247193239) in another worktree: its docs/1,594 existing tests pass, but a returned `Reference.record` aliases the action's trusted graph. Mutating its attribution makes a later capture/check accept the changed author within the same action. Posted an invented-corpus reproduction and left it unmerged for the author, per CLAUDE.md.

### Outstanding issues

- No manual Alacritty/Kitty session or sustained real-book reading trial was performed; headless tests establish mechanics, not reading comfort. Backspace revisits the already checked panel; following a link makes a fresh checked request. Note panels do not create a persistent note-reading position or offer personal annotations on note paragraphs.
- The corpus contract already rejects unresolved canonical note links on load. Unlinked/missing requests and changed generations refuse without substituted text; no relaxed corpus validation is introduced.
- PR #16 is not part of this branch. Main was refreshed at `5fad439`; if its corrected speed changes merge first, rebase this branch and retain both changelog/handoff entries. No source PDF, private corpus, personal workspace, synced project source or `AGENTS.md` was edited or committed.

### Decisions requiring approval

- None reserved. Defaults the maintainer may overrule: Enter on an explicit book-note/link row; Backspace one panel; Esc/`q` directly to the passage; resize closes the panel. Bounds: eight notes per path, 64 body paragraphs, 128 listed links, 1 MiB source text and 4 MiB presentation. Paragraph/text/presentation overflow refuses; excess links are explicitly disclosed, with source text unchanged.

## Edit and review personal notes in the reader — 18 October 2026

**Task:** [CURRENT_TASK](CURRENT_TASK.md), "Claude Code: Edit and review personal notes in the reader" ([proposal stage 3](proposals/CODEX_READER_WORKSPACE_PLAN.md#3-complete-the-personal-note-workflow-inside-the-reader))
**Branch / PR:** `claude/reader-note-editing` · opened with `gh pr create`
**Last implementation commit:** `d46e3520971bf33d9e2ddd8f2b1b61e5110fca0c`

### Changed files
- `sol/terminal/neovim_reader.py` — `note_edit` (note, revision, body) and `note_history` (note) panel requests, limited to notes listed on the sent passage; edits go through `prepare_annotation_edit` / `save_annotation_edit` from the revision the editor opened. Each listed note gains `revision`, `edit_refusal`, `changed_source`, `retired_target` and, when safe to send raw, `body`. Extra request fields may now be several per action.
- `sol/terminal/neovim.lua` — the `a` editor also revises (`note(edit)`, drafts keyed per note); `c` shows revision and status lines, `e` edits and `r` shows versions of the note under the cursor (or the only note); a version panel; personal-note payloads are validated.
- `tests/test_neovim_reader.py` — edit keeps ID/target/digest, a no-op save adds no revision, stale revision, another author, unknown note, bad revision, empty body and a changed corpus are refused; history newest first; a note with invisible characters is shown but not editable.
- `tests/test_reader_surface_neovim.py` — headless Neovim: `e` on the heading with two notes refuses to guess, on another author's note refuses, on yours opens the text; save sends the revision; a refused save keeps the draft; `r` shows versions. The existing note test's sample payload gained the new fields.
- `docs/BEING.md` (§2 controls and "Editing notes", §7), `CHANGELOG.md`.

### Tests performed
- `.venv/bin/python -B scripts/check_docs.py` — OK.
- `.venv/bin/python -B -m unittest discover -s tests` — 1588 tests, OK (11 skipped, 4 expected failures).
- Real terminal: none by hand.

### Outstanding issues
- A note containing invisible control characters (for example a zero-width joiner from older shell input) is shown escaped and must be edited with `sol --shell`; the reader will not send such text raw to Neovim.
- Notes on a retired record ID are listed under the successor and are editable; the edit keeps the retired ID as the note's target.
- No deletion, hiding or retraction: that is a future reserved decision (a retention policy, possibly a schema change). Nothing here depends on it.

### Decisions requiring approval
- **Key bindings (default):** `e` and `r` inside the `c` popup, acting on the note under the cursor or the only note. `a` still adds. Alternatives: numbered notes, or keys in the reading view.

## Reader speed baseline — 18 October 2026

**Task:** [Codex: Measure reader speed before optimising](https://github.com/dialectmaterial/SOL/blob/c2eb068/docs/coordination/CURRENT_TASK.md#codex-measure-reader-speed-before-optimising).
**Branch / PR:** `codex/reader-timings` · [PR #14](https://github.com/dialectmaterial/SOL/pull/14), opened with `gh pr create --base main`. Status: `In review`.
**Last implementation commit:** `fbba797fe4a9e22807712e060d86d207ba8e8923` (script/tests and documentation; this report follows).

### Changed files

- `scripts/reader_timings.py` — developer diagnostic, not an installed interface: synthetic by default, explicit `--corpus`, `perf_counter`, repeated medians/min–max/quartiles/raw samples, real controller callbacks and temporary workspaces. Only the Neovim boundary is replaced; source checks and persistence remain enabled. No new dependencies, caches or runtime edits.
- `tests/test_reader_timings.py` — four tests cover every operation/repetition, JSON CLI, invalid input, environment restoration and explicit-corpus nonmutation. No exact timing threshold is asserted.
- `docs/ARCHITECTURE.md`, `CHANGELOG.md` — short dated usage/limits; only Codex's status changes in `CURRENT_TASK.md`. All earlier reports remain below.

### Tests performed

- Reviewed corrected PR #12 (`71f3ce3`) in a separate worktree: docs and full suite passed (1,585 tests, 11 skipped, 4 expected failures); `gh pr checks 12 --watch` passed every check. Merged it and [commented the review](https://github.com/dialectmaterial/SOL/pull/12#issuecomment-6243009382). A detached-worktree cleanup error occurred after the remote merge; the merged remote branch was then removed explicitly, with its commits preserved on main.
- Focused benchmark tests: 4 tests, OK in 0.83 s. Synthetic human-readable CLI also ran successfully. Documentation check OK; full suite: 1,589 tests, OK (11 skipped, 4 existing expected failures), with isolated XDG state/logs and packaging checks included.
- Real corpus: `.venv/bin/python -B scripts/reader_timings.py --corpus /absolute/path/to/local-corpus --repeats 5 --warmups 1 --json`. Runtime base `189b1c6`; Core Ultra 7 255H, 16 logical CPUs, Linux x86-64, Python 3.14.4, width 72. Source: 4,629 records / 1,803 readable passages. Ordinary sample: 2 passages, no notes; heavy: 64 passages / 52 linked notes. Controller moves between the first two 10-passage sections; study runs on the second. Raw corpus/report data were not added to Git; rounded aggregate milliseconds follow.

| Operation | Median ms | Min–max ms |
| --- | ---: | ---: |
| Snapshot load | 124.5 | 118.8–136.7 |
| Reader book load | 136.6 | 135.4–143.5 |
| CORE verify | 14.4 | 14.3–14.8 |
| Ordinary payload | 412.7 | 391.1–428.5 |
| Note-heavy payload | 699.2 | 669.3–714.7 |
| Ordinary typography, standalone | 2.2 | 2.0–2.5 |
| Note-heavy typography, standalone | 53.5 | 52.9–67.1 |
| Python startup to first payload | 1,791.9 | 1,775.4–1,860.6 |
| Controller next | 2,851.5 | 2,812.8–2,930.2 |
| Controller previous | 2,866.1 | 2,806.3–2,929.1 |
| Search | 312.0 | 307.0–323.6 |
| Search-open | 2,251.5 | 2,221.0–2,317.4 |
| History back | 2,270.7 | 2,225.5–2,346.3 |
| Section study `S`, including temporary artifact save | 1,214.9 | 1,184.5–1,230.3 |

- Section moves are slowest; previous has the highest median but its spread overlaps next. A separate, instrumented single-run `cProfile` diagnostic (not baseline timing) reported 52 `_fresh_snapshot` calls, 57 `load_snapshot` calls and about 25.5 million recursive `_json_value` calls. Cumulative times are nested and cannot be added. This points to snapshot/reference preparation for investigation, not proof that guards can be removed.

### Outstanding issues

- Warm process/filesystem; no cold-disk, import, Neovim launch/version probe, IPC, drawing, Alacritty/Kitty or human latency measurement. Controller timings include SQLite checks/saves; isolated stages overlap and cannot be subtracted for attribution. Ordinary/heavy section lengths differ substantially. Five samples on an unpinned workstation are evidence for this run, not a performance guarantee.
- Candidates only: profile repeated full-snapshot JSON validation and capture/check calls within one controller request; inspect graph-copy/serialization costs; consider sharing already prepared typography/callout work. Do not cache trust across requests over caller-mutable collections or relax generation guards. No optimisation is adopted.
- Private source files, personal workspaces and `AGENTS.md` were untouched; generated workspaces/studies lived in cleaned temporary directories. No code under `sol/` was edited, and no manual terminal-reading trial was performed.

### Decisions requiring approval

- None introduced; no reserved decision is taken. Defaults: checkout-only script under `scripts/`, five measured runs after one warm-up, width 72, first minimum/maximum-note sections and first two controller sections. Future invalidation or public-contract changes need a separate task and any applicable reserved approval.

## Editor-trimmed marking forms — 18 October 2026

**Task:** [Codex: Make sentence marking practical by hand](https://github.com/dialectmaterial/SOL/blob/11576774cadab3a9ad204128fae3abf1b44b9cc3/docs/coordination/CURRENT_TASK.md#codex-make-sentence-marking-practical-by-hand), maintainer-requested follow-up to [Claude's PR #8 review](https://github.com/dialectmaterial/SOL/pull/8#issuecomment-6242615575).
**Branch / PR:** `codex/marking-form-trailing-space` · [PR #11](https://github.com/dialectmaterial/SOL/pull/11), opened with `gh pr create --base main`. Status: `In review`.
**Last implementation commit:** `7d553efc66fcea8271a5afcb87b1f4b58e5a5df2` (fix and documentation; this report follows).

### Changed files

- `sol/essence/segmentation_marking.py` — accepts `EXCLUDE:` with or without a trailing space; restores omitted source whitespace at added sentence breaks and passage ends. Words, interior sentence whitespace and original newlines still require exact matching. Gold strings and offsets come from canonical source, not normalized form text.
- `tests/test_segmentation_marking.py` — three regressions and a trimmed-form CLI round trip: every line `rstrip()`ped, retained/trimmed tabs and Unicode spaces, passage-end trimming, unchanged review/score, and rejection of whitespace loss inside a sentence.
- `docs/ESSENCE.md`, `CHANGELOG.md` — describe the narrow tolerance. Only Codex's task branch, follow-up scope and status change in `CURRENT_TASK.md`; earlier reports remain intact.

### Tests performed

- Reproduced before fixing: stripped `EXCLUDE:` failed at the first heading, trimmed boundary whitespace failed source matching, and the trimmed CLI round trip failed.
- `.venv/bin/python -B -m unittest discover -s tests -p 'test_segmentation*.py'` — 38 tests; OK (4 existing expected failures).
- `.venv/bin/python -B scripts/check_docs.py` — OK; external URLs were not network-checked.
- `.venv/bin/python -B -m unittest discover -s tests` — 1,585 tests; OK (11 skipped, 4 existing expected failures), with isolated XDG config/data/cache/state and Neovim logs. The fully trimmed synthetic CLI review retains the same marks and 80% F1; this is not a book estimate.
- `gh pr list` at session start found no open PRs from the other agent; PR #10 was already merged. No cross-agent review or merge was necessary. Main remained at `b2863c1` when refreshed before reporting.

### Outstanding issues

- No real-book sample, human annotation or manual graphical-editor trial was performed. UTF-8/LF, unmodified headings, original newlines and exact non-boundary source text remain required. Forms remain blind; no segmenter, artifact, CORE protocol, schema, dependency, reader or terminal changes are included.

### Decisions requiring approval

- None introduced; no reserved decision is taken. Defaults: restore only known canonical whitespace at added breaks/passage ends, and keep exported v1 headers byte-compatible so existing forms continue to import. Their conservative instruction to retain spaces remains useful but is no longer a requirement at the tolerated boundaries.

## Sentence marking in an ordinary text editor — 18 October 2026

**Task:** [Codex: Make sentence marking practical by hand](https://github.com/dialectmaterial/SOL/blob/11576774cadab3a9ad204128fae3abf1b44b9cc3/docs/coordination/CURRENT_TASK.md#codex-make-sentence-marking-practical-by-hand).
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
