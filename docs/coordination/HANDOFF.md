# Handoff reports

Claude Code adds one report per completed task, newest first, so a reviewer can
judge the work from GitHub alone: the report says what to look at, the pull
request shows the diff. Reports describe; they do not change what the five
governing documents ([SPECULATIVE](../SPECULATIVE.md), [Architecture](../ARCHITECTURE.md), [BEING](../BEING.md),
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

## Restructuring stage C: reading the Doctrine of Being — 22 October 2026

**Task:** [Claude Code: Reading the Doctrine of Being](https://github.com/dialectmaterial/SOL/blob/582914b546e5b1675511ef8dce892552f41a2499/docs/coordination/CURRENT_TASK.md#claude-code-reading-the-doctrine-of-being)
**Branch / PR:** `claude/reading-being` · pull request opened with this report; Codex reviews.
**Last implementation commit:** `582914b546e5b1675511ef8dce892552f41a2499` (this report is committed after it)

### Changed files
- `docs/coordination/restructuring/READING_BEING.md` — what the division of being, Quality, Quantity and Measure say (pp. 56–336 of the Cambridge edition, sections listed), a working interpretation for reader code, placements with alternatives and confidence, answers to the inventory's stage C questions.
- `docs/ARCHITECTURE.md` — twelve provisional rows in the §9 placement register.
- `docs/coordination/CURRENT_TASK.md` — status In review.

### Tests performed
- `.venv/bin/python -B scripts/check_docs.py` — passes. Documentation only; no code changed.
- Every page cited was read in the local corpus with `sol read`; the sections not read in full are listed in the document.

### Outstanding issues
- *Real measure* (pp. 302–325) and the mathematical remarks are not read in full; no Measure placement should be implemented before they are.
- `reader.search` and the word tokenizer are to be confirmed against Codex's reading of the determinations of reflection.
- `INVENTORY_BEING.md` (#87) is referenced by name; it is still under review.

### Decisions requiring approval
- Workspace placement: decided by the maintainer on 22 October 2026, after review began. The workspace stays in BEING (root package) and moves to CORE only once ESSENCE shares it; recorded in READING_BEING §3.7, the register, ARCHITECTURE §2, CORE §1 and BEING §2.
- Defaults: BEING-root placement for code that presents all three determinations (the Neovim reader, the session, the shell); the composition root, terminal escaping and themes outside the hierarchy.

## Restructuring stage A: BEING inventory — 22 October 2026

**Task:** [Claude Code: Restructuring stage A — BEING inventory](https://github.com/dialectmaterial/SOL/blob/3a995af8f2015ade1fa5b2b57c4b6df58460a3e6/docs/coordination/CURRENT_TASK.md), assigned directly by the maintainer. Its slot in `CURRENT_TASK.md` has since been replaced by stage C (#89), so the status is recorded here rather than set to *In review*.
**Branch / PR:** `claude/inventory-being` · [#87](https://github.com/dialectmaterial/SOL/pull/87); Codex reviews.
**Last implementation commit:** `fda9e991e0085b945e6e0b45cd72daa366cf4d78` (this report is committed after it)

### Changed files
- `docs/coordination/restructuring/INVENTORY_BEING.md` — entry points; module tables for `sol`, `sol.reader`, `sol.terminal`, `sol.workspace` including the initializers; cohesive groups; boundary findings; stage C questions; the mechanical import ledger and its regenerating script (after Codex's review of #87).

### Tests performed
- `.venv/bin/python -B scripts/check_docs.py` — passes.
- Ledger regenerated with the documented script at the refreshed baseline; Codex's independent scan of `scripts.reader_timings` agrees.
- `.venv/bin/python -B -m unittest discover -s tests` — run by Codex on the reviewed head: 1,249 tests OK (7 skipped, 4 expected failures); this change touches only documentation.

### Outstanding issues
- The ledger is syntactic: string patch targets, subprocess module names and Lua are covered only in the prose findings.

### Decisions requiring approval
- None. No placement is proposed.


## Restructuring stage A: ESSENCE and CORE inventory — 21 October 2026

**Task:** [Codex: Restructuring stage A — ESSENCE and CORE inventory](https://github.com/dialectmaterial/SOL/blob/3a995af8f2015ade1fa5b2b57c4b6df58460a3e6/docs/coordination/CURRENT_TASK.md#codex-restructuring-stage-a--essence-and-core-inventory), assigned directly by the maintainer.
**Branch / PR:** `codex/inventory-essence-core` · [branch pull request](https://github.com/dialectmaterial/SOL/pulls?q=is%3Apr+head%3Acodex%2Finventory-essence-core); Claude reviews; author does not merge.
**Last implementation commit:** `3a995af8f2015ade1fa5b2b57c4b6df58460a3e6` (this report is committed afterward).

### Changed files

- `docs/coordination/restructuring/INVENTORY_ESSENCE_CORE.md` — all 49 Python modules (24 ESSENCE, 14 corpus, 8 CORE, 3 scripts) and both JSON catalogs: actual responsibilities, present boundaries, execution routes, protecting tests, complete AST import/reverse-import ledger, reproducible scan, dynamic/resource/process edges, cohesive change groups and Stage C reading questions. No logical subdivision placements or product changes.
- `docs/coordination/CURRENT_TASK.md` — replace only Codex's completed cleanup slot with this directly assigned inventory task, `In review`. Claude's task and parallel `INVENTORY_BEING.md` are untouched.
- Baseline `origin/main`: `c0f469780ac09a3ea832e4e3b3b0fecb303d4399`. Read CLAUDE.md and SPECULATIVE from PR #86's `origin/claude/speculative-docs` at `1424aae9ec3e16cc8c9a0c3aaea64a67782b7fd6`, especially §§4 and 7; that leading document was not yet on main. Do not copy or amend the maintainer's document in this PR.
- Publication checkout: `/tmp/sol-inventory-essence-core`, cloned/fetched from origin because the supplied checkout's Git metadata is read-only.

### Tests performed

- `/home/dima/Projects/code/sol/.venv/bin/python -B scripts/check_docs.py` — OK: baseline four-authority layout and local links/anchors; external URLs not network-checked. PR #86 owns the separate five-document checker update.
- `/home/dima/Projects/code/sol/.venv/bin/python -B -m unittest discover -s tests` — **1,249 tests, OK (7 skipped, 4 expected failures)**, 105.423 s. Existing expected failures document sentence segmentation limits; no accuracy claim added.
- Executed the inventory's embedded AST scan and compared all **49 ledger rows** byte-for-byte with the document; checked every scoped Python file has a narrative row and both catalogs are recorded. All agree. Scan includes function-local/relative imports; lazy exports, subprocess strings, Lua and package data are reviewed separately in the inventory.
- `git diff --check` — OK. Changed-file audit: only inventory, Codex's task slot and this report; no product/test/config changes or edits to Claude's inventory.

### Outstanding issues

- Stage C primary-text reading and placement rationale remain future work; no quotations or logical-category assignments are fabricated here. Existing analysis scope, snapshot mutability, sentence-rule limits and reader/UI/persistence couplings are recorded as questions, not changed.
- No private-corpus, real extraction engine or manual reading/visual acceptance trial is claimed; this is a documentation inventory.

### Decisions requiring approval

None. Default: record syntactic imports separately from dynamic/runtime dependencies and protecting behavior tests. No reserved decision, contract, dependency, workspace schema or corpus-write policy change. Leave this PR open for Claude's review; do not merge.

## SPECULATIVE leads the documentation — 21 October 2026

**Task:** maintainer request (21 October 2026): make the speculative architecture document leading and align all documentation with it.
**Branch / PR:** `claude/speculative-docs` · PR #86
**Last implementation commit:** `d93cc1af60f863af7268703d2fb17b41baba3c2c` (this report is committed after it)

### Changed files
- `docs/SPECULATIVE.md` — the maintainer's document, verbatim (front matter dropped).
- `docs/ARCHITECTURE.md` — rewritten in SPECULATIVE's terms; all earlier decisions, statuses and measurements kept; restructuring stages A–F; reading protocol and autonomy; placement register.
- `docs/BEING.md`, `ESSENCE.md`, `CORE.md` — framing sections for each division; the workspace store's CORE-or-BEING placement recorded as an open restructuring question.
- `README.md`, `CONTRIBUTING.md`, `CLAUDE.md`, `scripts/check_docs.py` — five governing documents; CLAUDE.md gains the structural-autonomy rule and reading protocol.
- `docs/coordination/CURRENT_TASK.md` — stage A inventory assigned, split by package.

### Tests performed
- Documentation check (every link into SPECULATIVE resolves) and full suite: OK.
- Codex's review: README divisions, ESSENCE status lines, stale BEING/CONTRIBUTING claims and two ARCHITECTURE caveats fixed; dead `sol/terminal/tty.py` removed.

### Outstanding issues
- Restructuring has not begun; the placement register is empty.

### Decisions requiring approval
None reserved: the maintainer made SPECULATIVE leading. Default: SPECULATIVE is treated as maintainer-only (agents never edit it).


## Cleanup steps 1, 3 and `sol being` — 21 October 2026

**Task:** maintainer's cleanup plan (CURRENT_TASK, 21 October), steps 1, 3 and the reader half of 6.
**Branch / PR:** `claude/minimal-shell` · see the pull request
**Last implementation commit:** `955a2648780073b70a18b2ab65db5bfc7b1c3645` (this report is committed after it)

### Changed files
- `sol/reader/shell.py` — rewritten as a browsing-only shell on `input()`/readline; no workspace, Kitty, handoff or prompt adapter.
- Removed: `sol/terminal/{kitty,handoff,comparison,essence,prompt}.py`, `sol/workspace/{commands,comparison}.py`, `sol/reader/{legacy_pdf,models}.py`; `sol read`'s path resolver moved into `sol/terminal/commands.py`.
- `sol/reader/options.py`, `app.py` — `sol being`; `--shell` refuses workspace/actor options and skips onboarding; `--pdf`, `--engine`, `--ui`, `--editing-mode`, `--source-pdf`, `sol compare`, neofetch removed.
- `sol/terminal/reference.py` — `return` removed; `sol/workspace/reader.py` — `execute`, comparison/review/relation writers removed (store tables unchanged).
- `pyproject.toml`, `scripts/install.py` — no `prompt-toolkit`, `sol-kitty`, empty extras, Kitty/Zsh tool checks.
- Tests: 16 modules for removed features deleted; shell-driven tests pruned; onboarding, packaging and CLI tests converted to `sol being`; new completion and shell-help tests.
- Docs: BEING §§2–3, 6–7, CORE §§6–8, ARCHITECTURE (maintainer's 21 October decision recorded beside the superseded `sol-kitty` one), README, CONTRIBUTING, `sol guide`, CHANGELOG.

### Tests performed
- Documentation check and full suite after merging main (with #83 and #84): 1,249 tests OK (7 skipped, 4 expected failures).
- Codex's review asked for still-valid cases to be kept: added `tests/test_read_paths.py` (moved resolver: virtual files, relative aliases, directory order, Markdown path forms, refusal of outside/unlisted files without reading them) and, in `test_workspace_reader.py`, the uppercase `.SQLITE3` upgrade refusal, the no-database `--review-queue --json`, non-overwriting `--workspace-backup` and misplaced workspace options.
- Recovery messages now name `sol --workspace NAME --workspace-upgrade FILE.sqlite3` instead of the removed shell command.

### Outstanding issues
- None: #84 (merged) renamed `sol essence`, removed the term study and rewrote ESSENCE §6; its formula-sheet removal covered BEING §5.

### Decisions requiring approval
None reserved: the maintainer decided these removals on 21 October.

## ESSENCE cleanup (steps 5 and 6) — 21 October 2026

**Task:** [Codex: ESSENCE cleanup (steps 5 and 6)](https://github.com/dialectmaterial/SOL/blob/a26cefc7302928bde0de0f4ef5cbc05f32cdb9d4/docs/coordination/CURRENT_TASK.md#codex-essence-cleanup-steps-5-and-6), assigned directly by the maintainer.
**Branch / PR:** `codex/essence-cleanup` · [pull request](https://github.com/dialectmaterial/SOL/pulls?q=is%3Apr+head%3Acodex%2Fessence-cleanup); Claude reviews; author does not merge.
**Last implementation commit:** `a26cefc7302928bde0de0f4ef5cbc05f32cdb9d4` (this report is committed afterward).

### Changed files

- `sol/essence/cli.py`, `__init__.py`, Methods and encyclopedia catalogs — remove the term experiment and four segmentation-pilot commands, their artifact dispatch and public term exports. The six remaining commands use `sol essence`; no `analyze` alias. Unknown/retired artifacts are refused before corpus discovery.
- `sol/essence/corpus_inputs.py` — relocate the unchanged freshness, provenance, doctrine/path, selection and facsimile-mask helpers used by words and sentences out of the deleted `terms.py`. `word_inputs.py` and `sentences.py` import the new module. The tokenizer was already extracted in `tokenization.py`; keep its algorithm unchanged and update its description. Word/sentence/TF-IDF methods and artifact formats remain unchanged.
- `sol/essence/tui/app.py` — saved-study messages say `sol essence check`. `sol/reader/app.py` changes **only the single subcommand dispatch condition**.
- ESSENCE, BEING, Architecture, CHANGELOG — update command examples and current descriptions, retire segmentation-pilot and formula-sheet instructions. Keep formula/source acceptance and the need for human review. Historical `docs/legacy/` and old coordination reports/proposals are untouched.
- Tests — retire term/pilot/formula-sheet tests and the term-based handoff/live-Kitty round trips. Keep prose coverage; check the renamed dispatch, removed commands and artifacts, and read-only word/check round trips. Preserve all four sentence-rule expected failures in `test_sentence_study.py`; make that fixture independent of the removed term TestCase. Packaging now runs a sentence experiment without reader/workspace/UI dependencies and checks the exact six retained Methods entries.
- Publication checkout: `/tmp/sol-essence-cleanup`, cloned from `origin/main` at `eb44ef2`, because the supplied checkout's Git metadata is read-only. No edits to Claude's shell, terminal, options or pyproject files.

### Removed files and line counts

Counts against `origin/main` at `eb44ef2`: **10 complete files / 2,636 lines** removed. The implementation commit changes **31 files: 343 added, 3,520 deleted, net −3,177 lines**, excluding this report. The new shared corpus helper module accounts for 105 added lines; the four expected-failure tests were relocated rather than discarded.

| Removed file | Lines |
| --- | ---: |
| `scripts/formula_review_sheet.py` | 379 |
| `sol/essence/segmentation_check.py` | 241 |
| `sol/essence/segmentation_marking.py` | 164 |
| `sol/essence/terms.py` | 377 |
| `tests/test_analysis_handoff.py` | 92 |
| `tests/test_formula_review_sheet.py` | 265 |
| `tests/test_kitty_handoff_integration.py` | 159 |
| `tests/test_segmentation_check.py` | 269 |
| `tests/test_segmentation_marking.py` | 292 |
| `tests/test_term_experiment.py` | 398 |

### Tests performed

- `/home/dima/Projects/code/sol/.venv/bin/python -B scripts/check_docs.py` — OK (four authorities, local links/anchors and legacy inventory); external URLs not network-checked. `git diff --check` — OK.
- `/home/dima/Projects/code/sol/.venv/bin/python -B -m unittest discover -s tests` — **1,518 tests, OK (7 skipped, 4 expected failures)**, 101.685 s. Includes wheel/source-archive and retained headless reader checks. An initial run exposed the old eleven-entry Methods assertion; the final run checks the six retained entries and passes.
- Focused CLI, word-frequency, Methods and sentence checks passed. `python -B -m sol essence --help` lists sentences, words, tfidf, check, words-export and prose; the retired term command exits 2. Automated checks reject the `analyze` namespace and all four segmentation commands.

### Outstanding issues

- Root help still has two `analyze` mentions in `sol/reader/options.py`; that file is explicitly owned by Claude's concurrent rename/cleanup. Actual `analyze` dispatch is removed and tested. Legacy docs await Claude's separate document-removal PR; their historical command spellings were not rewritten.
- No private-corpus or real-terminal trial: this is command removal/rename, with retained engines covered by invented corpora and packaging checks. No segmentation accuracy or formula-review claim is made.

### Decisions requiring approval

None beyond the maintainer-approved cleanup. Default: reject retired term artifacts rather than retain a hidden compatibility verifier. Claude reviews the PR; do not merge as author.

## Cleanup step 4: legacy documents folded in and removed — 21 October 2026

**Task:** maintainer's cleanup plan (CURRENT_TASK, 21 October), step 4.
**Branch / PR:** `claude/legacy-docs` · PR #83
**Last implementation commit:** `ddc6e3ffc97773d50d73a09f45e407b9964d5f1e` (this report is committed after it)

### Changed files
- `docs/CORE.md` §§9–10 — corpus contract v1 and reference protocol v1 in detail (verified against `sol/corpus/contract.py`, `sol/core/protocol.py`, `sol/core/wire.py`).
- `docs/ESSENCE.md` §3 — prose-input projection rules (`sol/essence/prose.py`).
- `docs/BEING.md` §3 — workspace storage, backup/upgrade, export, review-binding limits, and the list/delete/recover contract (`sol/workspace/store.py`, `lifecycle.py`, `profiles.py`, `export.py`).
- `docs/ARCHITECTURE.md` §5 — Hegel's Remark on the particular concept, pointed to rather than quoted (copyrighted translation); documentation policy: history lives in Git.
- Removed `docs/legacy/` (36 files), two finished proposals and HANDOFF reports older than the last five; `scripts/check_docs.py` no longer verifies the archive inventory.

### Tests performed
- Documentation check and full suite: OK. Codex reviewed and asked for the three BEING additions above, now made.

### Outstanding issues
- None known.

### Decisions requiring approval
None reserved: the maintainer decided the removal on 21 October; Decision wording in ESSENCE §7 is unchanged apart from replacing a link to the removed proposal.


## ESSENCE Results in small windows — 21 October 2026

**Task:** [Codex: ESSENCE Results in small windows](https://github.com/dialectmaterial/SOL/blob/a7827cf/docs/coordination/CURRENT_TASK.md#codex-essence-results-in-small-windows).
**Branch / PR:** `codex/essence-results-small` · [pull request](https://github.com/dialectmaterial/SOL/pulls?q=is%3Apr+head%3Acodex%2Fessence-results-small); Claude reviews; author does not merge.
**Last implementation commit:** `93ce0007ae0f473b28480fe94458b155a73f5a43` (this report is committed afterward).

### Changed files
- `sol/essence/tui/app.py` — bound Results to its window; summaries use at most 20% of height; word and occurrence tables share the remaining space. Compact help/export controls keep occurrences visible at 80×24. Explicit column budgets include padding and scrollbar space; long words, undefined measures, sentences, locations and TF-IDF terms wrap. Resize rebuilds preserve word/occurrence selection, focus, messages and export disabled state; intermediate highlight events cannot reset the occurrence.
- `tests/test_essence_tui.py` — real-engine pilots for words with/without reference, sentences and TF-IDF at 80×24 and 120×40; visible table bounds, no horizontal scroll, source opening, Escape, resize selection and unchanged study receipts. Long Unicode words and undefined measures exercise all five reader themes.
- `docs/ESSENCE.md` §4, `CHANGELOG.md` — current presentation behavior; `CURRENT_TASK.md` — Codex is `In review`. No Encyclopedia/Methods changes, engine, artifact, export, dependency or public-contract changes.
- Render evidence (before/after terminal-cell renders on the invented corpus at 80×24 and 120×40) was reviewed in PR #80 and not kept in the repository.
- Publication checkout: `/tmp/sol-essence-results-small`, cloned from `origin/main` at `a7827cf`, because the supplied checkout's Git metadata is read-only.

### Tests performed
- Documentation check: `/home/dima/Projects/code/sol/.venv/bin/python -B scripts/check_docs.py` — OK; external URLs not network-checked. `git diff --check` — OK.
- Full suite: `/home/dima/Projects/code/sol/.venv/bin/python -B -m unittest discover -s tests` — **1,816 tests, OK (12 skipped, 4 expected failures)**, 132.457 s. All ESSENCE tests pass in this run.
- Focused `SmallResultsTests` — 2 tests, OK; covers repeated resizing and source navigation at both sizes and long-word/undefined-measure cases in Mocha, Latte, Paper, Night and Terminal.
- Actual Textual terminal driver in tmux, 80×24 then 120×40 — selected occurrence remains visible with heading/page and context; exports fit. Checked the native text “An invented passage makes this installed research…” in all five reader themes, including spaces next to bold. Visually inspected Paper comparison and the four non-ANSI theme renders; Terminal's ANSI palette is absent from SVG screenshots, so its text was checked through the real terminal driver.

### Outstanding issues
- No private-book visual trial; renders and pilots use the public invented corpus. Long rows and summaries require vertical scrolling. Windows narrower than 80 columns are outside this task's acceptance.

### Decisions requiring approval
None reserved. Defaults: summary height cap 20%; word/occurrence tables share space; wrap rather than omit columns or shorten the engine's undefined-measure labels. Claude may revise these presentation defaults in review.





## Remove the experiments and the research-export mode — 21 October 2026

**Task:** [Codex: Remove the experiments and the research-export mode (step 2)](https://github.com/dialectmaterial/SOL/blob/d137627ba67d77a3c73571c2e0b037b493f54ac9/docs/coordination/CURRENT_TASK.md#codex-remove-the-experiments-and-the-research-export-mode-step-2).
**Branch / PR:** `codex/remove-experiments` · [pull request](https://github.com/dialectmaterial/SOL/pulls?q=is%3Apr+head%3Acodex%2Fremove-experiments); Claude reviews; author does not merge.
**Last implementation commit:** `0a89491e6596df7aea4881250fb16b01e24758c3` (this report is committed afterward).

### Changed files
- `sol/terminal/neovim.py` — remove `run` and the research destination/export wrapper; retain isolated native hosting, bounded strict packet reads, checked view preparation and selection restoration.
- `sol/terminal/neovim_{view,controls,requests}.lua`, `neovim_reader.py` — remove the mode discriminator, standalone help/status/quit/export branches and `:SOLExport`; use integrated navigation, controls and action envelopes throughout. The internal result writer remains for integrated quit/section returns.
- `sol/reader/surface.py` — describe its retained checked projections and selection packets as reader internals. Source verification, generation checks, selection fields and detached-view guards remain.
- `tests/test_reader_surface_neovim.py` — retain **all 53** headless behavior tests, now with integrated navigation on every launch. The selection export/restore check now quits through the integrated path and validates the packet inside its action envelope. Assert `:SOLExport` is absent. Unicode boundaries, wrapping, exact selections, forced-mutation refusals, resizing and fresh-editor restoration remain covered alongside the existing controls/panels tests.
- `tests/test_reader_surface_export_guards.py` — retain all **20** checks, replacing HTML rendering with the installed payload builder: retirement chains, defensive copies, corpus/reference/generation bindings, late source/graph mutations and imported packet checks.
- Neovim host, opt-in Alacritty and packaging tests — use installed modules, integrated payloads and action envelopes. Retain host isolation/private-file/preflight/strict-read checks; retire only the research file-export wrapper cases. Source archives explicitly exclude experiments and run the retained source guards; installed-wheel headless Lua loading remains checked.
- `tests/test_reader_cursor.py` — remove its baseline-only toolkit geometry class; retain all 26 semantic/source-layout tests. `test_reader_view_cli.py` drops a patch of the removed frontend; its routing checks remain.
- `MANIFEST.in`, `docs/BEING.md`, `CHANGELOG.md`, `CURRENT_TASK.md` — stop shipping experiments, describe the remaining reader, record removal, mark Codex's task `In review`.
- `scripts/reader_timings.py` already uses installed modules and needs no change. `neovim.lua` remains the unchanged package-local entry.
- Work performed in `/tmp/sol-remove-experiments`, a clean clone from `origin/main` at `d137627`, because the supplied checkout's Git metadata is read-only. Main had not advanced at publication preparation.

### Removed files and line counts

Counts are against `origin/main` at `d137627`. **31 complete files / 6,308 lines** removed: 12 experiment files / 1,995 lines and 19 experiment-only test files / 4,313 lines. The implementation commit changes 50 files overall: **282 added, 6,798 deleted, net −6,516 lines**; the additional deletions include standalone Lua branches, the research host wrapper and baseline/export-only test cases in retained files. The report itself is excluded from these totals.

| Removed file | Lines |
| --- | ---: |
| `experiments/__init__.py` | 1 |
| `experiments/reader_surfaces/__init__.py` | 1 |
| `experiments/reader_surfaces/__main__.py` | 102 |
| `experiments/reader_surfaces/baseline.py` | 715 |
| `experiments/reader_surfaces/browser.js` | 178 |
| `experiments/reader_surfaces/browser_acceptance.cjs` | 113 |
| `experiments/reader_surfaces/common.py` | 5 |
| `experiments/reader_surfaces/html.py` | 160 |
| `experiments/reader_surfaces/neovim.py` | 5 |
| `experiments/reader_surfaces/reading_layout.py` | 147 |
| `experiments/reader_surfaces/trials.py` | 159 |
| `experiments/reader_surfaces/tui.py` | 409 |
| `tests/test_reader_alacritty_integration.py` | 248 |
| `tests/test_reader_experience.py` | 540 |
| `tests/test_reader_hosts.py` | 106 |
| `tests/test_reader_lexer_cache.py` | 90 |
| `tests/test_reader_reflow.py` | 313 |
| `tests/test_reader_spacing.py` | 244 |
| `tests/test_reader_surface_alacritty.py` | 195 |
| `tests/test_reader_surface_baseline.py` | 152 |
| `tests/test_reader_surface_browser.py` | 60 |
| `tests/test_reader_surface_cli.py` | 98 |
| `tests/test_reader_surface_html.py` | 306 |
| `tests/test_reader_surface_neovim_cli.py` | 77 |
| `tests/test_reader_surface_trial_cli.py` | 172 |
| `tests/test_reader_surface_trial_html.py` | 134 |
| `tests/test_reader_surface_trials.py` | 332 |
| `tests/test_reader_surface_tui.py` | 491 |
| `tests/test_reader_view.py` | 376 |
| `tests/test_reader_view_integration.py` | 168 |
| `tests/test_reading_layout.py` | 211 |

### Tests performed
- `/home/dima/Projects/code/sol/.venv/bin/python -B scripts/check_docs.py` — OK; local links/anchors and legacy inventory checked, external URLs not network-checked.
- Same interpreter, `-B -m unittest discover -s tests` — **1,608 tests, OK (8 skipped, 4 expected failures)**, 98.477 s. Includes native TTY, headless Neovim, controller and packaging checks. No added skip or expected-failure markers.
- Focused Neovim surface/host/Alacritty discovery — 81 tests, OK (1 explicit GUI skip); source guards — 20 tests, OK; packaging — 21 tests, OK. The full suite includes the final versions.
- Cursor and dependent flow-action modules — 26 and 15 tests, OK. The initial full run found a dangling decorator after the retired toolkit class; fixed before the successful full run.
- `scripts/reader_timings.py --repeats 1 --warmups 0 --json` — OK on its invented temporary corpus; no removed-module dependency. No performance improvement is claimed.
- `git diff --check` — OK. All retained Python modules parse. Compared headless test method names against the base: 53 before/after, with the export check renamed to integrated quit/restore.

### Outstanding issues
- No manual terminal/readability acceptance or private-corpus run is claimed. Opt-in GUI checks remain opt-in.
- Claude's separate document cleanup owns CONTRIBUTING and historical documents: CONTRIBUTING's optional-experiments/archive paragraph still describes the retired tools and should be reconciled there. `docs/legacy/` and `docs/coordination/proposals/` are untouched as assigned.

### Decisions requiring approval
None reserved. The removals implement the maintainer's approved step 2; no authority Decision statement, dependency set, public CORE/reference/corpus contract or workspace schema changes. Default: retain the internal integrated result writer and detached source-checking helpers needed by the installed reader and its tests.


## A faster full test suite — 21 October 2026

**Task:** [Codex: A faster full test suite](https://github.com/dialectmaterial/SOL/blob/aba326e38eeacdb29ac41e6ce1e78d3670d4e053/docs/coordination/CURRENT_TASK.md#codex-a-faster-full-test-suite).
**Branch / PR:** `codex/test-speed` · [pull request](https://github.com/dialectmaterial/SOL/pulls?q=is%3Apr+head%3Acodex%2Ftest-speed); Claude reviews; author does not merge.
**Last implementation commit:** `6a57ccb8e0820b10e805e9beccfdc6a1b01bb847` (this report is committed afterward).

### Changed files
- `tests/fixtures_async.py` — cooperative setup for UI tests: retain `IsolatedAsyncioTestCase` and its per-test loop, cancellation and cleanup; use normal application loop mode unless `PYTHONASYNCIODEBUG` is set. Avoid expensive asyncio creation-stack tracing during ordinary behavior checks.
- Eight UI test modules (encyclopedia, ESSENCE, reader cursor/experience/reflow/spacing/surface/view) — mix in that setup; ESSENCE's existing async setup calls its parent. Every test method, assertion, decorator, input sequence, wait and worker check is unchanged.
- `CONTRIBUTING.md`, `CHANGELOG.md` — explain normal versus opt-in debug diagnostics. Codex's task status is `In review`. No product, dependency, CI, authority, public contract or schema change.
- Publication uses `/tmp/sol-test-speed`, cloned from `origin/main` at `aba326e`, because the supplied checkout's Git metadata is read-only.

### Tests performed
- Documentation check (`python -B scripts/check_docs.py`) — OK; external URLs were not network-checked. `git diff --check` — OK.
- Full discovery before and after — **1,807 tests, OK (12 skipped, 4 expected failures)** in both runs; no added skips or changed expected failures. Includes packaging, real headless Neovim and native TTY checks. The ordinary command stays `python -B -m unittest discover -s tests`.
- Full discovery with `PYTHONASYNCIODEBUG=1` — 1,807 tests, OK (12 skipped, 4 expected failures), 99.287 s reported / 100.727 s wall time; restores the original diagnostic mode.
- Focused ESSENCE checks — 32 tests, OK, 28.893 s (baseline module total 39.343 s). AST comparison of all 1,807 test methods, including their assertions and decorators, against `origin/main` — identical.

| Full discovery timing | Before (s) | After (s) |
| --- | ---: | ---: |
| Wall clock, including discovery and runner | 101.255 | 81.277 |
| unittest's reported run time | 100.883 | 80.905 |

**19.7% less wall time (20.0 s saved)** on this machine. The task's approximate
150 s was not reproduced: the measured baseline here was 101.3 s. Same Python
3.14.8 interpreter (`/home/dima/Projects/code/sol/.venv/bin/python`), dependency
installation, public fixtures, temporary XDG/Neovim paths and sequential runs,
without another suite/profile running concurrently. A temporary `TextTestResult`
subclass timestamps `startTest`/`stopTest`, preserving discovery and runner
behavior; the wall timer also includes discovery and class setup/cleanup. Test
rows include each test's setup/cleanup, not shared class setup. These are local
samples, not a cross-host speed guarantee. Packaging and subprocess timings also
vary; the unchanged native TTY and Zathura tests are useful controls.

Slowest baseline tests, with the same tests after the change:

| Test | Before (s) | After (s) |
| --- | ---: | ---: |
| `test_encyclopedia.EncyclopediaBrowserTests.test_browse_read_scroll_and_return_at_terminal_sizes` | 7.18 | 5.37 |
| `test_essence_tui.EssenceAppTests.test_methods_screen_browses_every_method` | 4.40 | 2.77 |
| `test_reader_terminal_portability.ReaderTerminalPortabilityTests.test_default_reader_in_xterm_vt100_and_screen_ttys` | 4.39 | 4.32 |
| `test_essence_tui.ComparisonScreenTests.test_export_writes_only_in_workspace_sessions` | 4.33 | 2.94 |
| `test_essence_tui.CountOrderTests.test_an_older_count_never_replaces_a_newer_one` | 3.55 | 3.03 |
| `test_reader_surface_neovim.ReaderSurfaceNeovimTests.test_zathura_follows_the_resting_passage_after_s_until_it_closes` | 3.53 | 3.53 |
| `test_essence_tui.ComparisonScreenTests.test_measures_sources_and_opening_one_in_the_reader` | 3.40 | 2.59 |
| `test_essence_tui.EssenceAppTests.test_follows_the_reader_theme_while_open` | 2.98 | 2.90 |

The remaining slowest tests are encyclopedia browsing (5.37 s), native TTYs
(4.32 s), Zathura following (3.53 s), count ordering (3.03 s), exports (2.94 s)
and theme polling (2.90 s). Real launches and all polling/synchronization waits
remain. A separate cProfile of encyclopedia browsing identified repeated
asyncio stack extraction and line-cache work; profiling distorted total wall
time, so those timings are excluded from the comparison. Raw timing logs/JSON
and the temporary profiler remain outside Git at `/tmp/sol-speed-*`,
`/tmp/time-sol-suite.py` and `/tmp/sol-ui-before.prof`; no private corpus was used.

### Outstanding issues
- Normal mode omits asyncio's debug-only diagnostics (creation stacks, slow-callback logging and thread checks); `PYTHONASYNCIODEBUG=1` restores them. Test behavior, exception propagation, resource warnings and loop cleanup remain. No manual reading/visual acceptance is claimed.

### Decisions requiring approval
None reserved. Default: run UI behavior checks in the application's normal loop mode, with debug diagnostics available explicitly. Existing tests and assertions remain intact; the reviewer can overrule this runner default.


## BEING describes the current reader — 21 October 2026

**Task:** [Codex: BEING describes the current reader, not its history](https://github.com/dialectmaterial/SOL/blob/78c2389/docs/coordination/CURRENT_TASK.md#codex-being-describes-the-current-reader-not-its-history).
**Branch / PR:** `codex/being-current` · [pull request](https://github.com/dialectmaterial/SOL/pulls?q=is%3Apr+head%3Acodex%2Fbeing-current); Claude reviews; author does not merge.
**Last implementation commit:** `5c98def611e0d95ac62f7552e7eb2ddcb17318e1` (this report is committed afterward).

### Changed files
- `docs/BEING.md` — §§2–7 consolidate current feature descriptions, controls and their evidence. Notes include draft lifetime; search includes hidden marks; refusal behavior includes checkpoint limits; source crops, PDF following, themes and ESSENCE retain their qualifications. Sentence lengths points to the already documented ESSENCE interface. The old §4 anchor remains explicit.
- `docs/coordination/CURRENT_TASK.md` — only Codex's status, now `In review`; this handoff is the other coordination change. No behavior change, so no CHANGELOG entry. No README, guide, code or legacy edits.
- Publication uses a clean clone at `/tmp/sol-being-current`, from `origin/main` at `78c2389`, because the supplied checkout's Git metadata is read-only.

### Removed as obsolete
- Dated delivery/stage labels, migration assurances, the old clipboard failure explanation and navigation-probe commit narration: implementation history belongs in CHANGELOG/Git. Their current behavior, test coverage and limits remain.
- “Three presets” implementation text and “next bounded task” in §4's title: the existing table and §2 already describe five current presets. Every Decision paragraph, including the earlier three-preset decision, stays verbatim.
- The old 20-passage search ceiling, passage-only search stepping and missing count: §2 already documents complete occurrence search and its projection caveats.
- The blanket passage-local selection limit: the existing controls/copy description permits copying across paragraphs; note/ESSENCE and durable-span limits remain.
- The retired reader sentence-study key/panel/actions, automatic loaded-section origin/save workflow, its old handoff example and popup listing: these controls no longer exist. The study's distribution, paragraph-position means, twelve longest sentences, private artifact path/checking and separate result/history returns remain described through its current interface. The stale plan to move the study into ESSENCE is replaced by a link to ESSENCE §4, which already documents it there. Decision/Decided statements are untouched.
- Duplicate descriptions of notes, footnotes, search marks, math-record counts and refusal behavior: consolidated without dropping current facts. Refusal now uses the existing later qualification that the outgoing cursor may already be checkpointed.

### Tests performed
- `.venv/bin/python -B scripts/check_docs.py` — OK, including after the final report; external URLs are not network-checked.
- `.venv/bin/python -B -m unittest discover -s tests` — 1,807 tests, OK (12 skipped, 4 expected failures), Python 3.14.8; temporary XDG config/data/state/cache and Neovim log paths. Includes packaging/headless checks; no new manual terminal or private-corpus trial.
- `git diff --check` — OK. Compared all five complete Decision paragraphs and the explicit Decided statements against `origin/main`: identical. Existing test evidence, unseen PDF-highlight placement, unreviewed mathematics and manual-acceptance limits remain qualified.

### Outstanding issues
- None introduced. Existing product/acceptance limits remain; this editorial task establishes no new usability or visual acceptance. Dated Decision wording and the adoption metadata outside §§2–7 are retained.

### Decisions requiring approval
None. Editorial defaults only; no reserved decision, public contract, schema or dependency change.

## Faster startup to readable text — 21 October 2026

**Task:** [Codex: Faster startup to readable text](https://github.com/dialectmaterial/SOL/blob/e602ce668b6e840e838026c65c9c05586d900574/docs/coordination/CURRENT_TASK.md#codex-faster-startup-to-readable-text).
**Branch / PR:** `codex/startup-time` · [PR #67](https://github.com/dialectmaterial/SOL/pull/67); Claude reviews; do not merge as author.
**Last implementation commit:** `275dcb24ab67cd78fff1e1a6496486844fce85a3` (integration of current main; startup implementation `12734c0`; this report is committed afterward).

### Changed files
- `sol/corpus/contract.py` — hash the exact bytes already decoded as UTF-8; use string-based resolved-path containment and resolve the scan boundary once per scan. Each document still resolves its parents, refuses symlinks and is read/hashed anew; all before/after generation checks remain.
- `sol/reader/app.py` — lazy compatibility wrappers defer the optional book shell.
- `scripts/reader_timings.py` — `--startup-only` runs fresh application imports/dispatch through the first checked payload in a new process and temporary workspace per sample; existing version 2 measurements remain unchanged.
- Regression tests, BEING §2, CHANGELOG and Codex's task status. No protocol, verification cache, dependency, schema or Claude source-request changes. Read-only Git metadata in the supplied checkout required a clean clone at `/tmp/sol-startup-time`, initially based on `origin/main` at `e602ce6`. PR #66 reached main after publication; merged `7dda0ae` into the published branch without rewriting it, preserving both changelog entries. Relative to current main, Claude’s files remain untouched.

### Tests performed
- Focused corpus contract (41 tests) and timing probe (6 tests) — OK. Coverage includes repeated byte reads, CRLF fingerprint changes, invalid UTF-8, escaping parent links, undeclared canonical documents, fresh-process isolation and deferred shell imports.
- `.venv/bin/python -B scripts/check_docs.py` and `git diff --check` — OK; external URLs were not network-checked.
- `.venv/bin/python -B -m unittest discover -s tests` — final integrated branch: 1,807 tests, OK (12 skipped, 4 expected failures); pre-integration run: 1,803 tests, OK. Isolated XDG/Neovim paths; packaging and headless Neovim checks included.
- Read-only real book: 4,629 records / 1,803 passages; identical index SHA-256 before/after. No private text, PDF, workspace or profile is committed. No source PDF or personal workspace opened. Python 3.14.8, width 72, warm OS cache, sequential runs without concurrent tests/profiling. All CORE verification remains real; terminal boundary replaced.

| Measurement | Before median (ms) | After median (ms) |
| --- | ---: | ---: |
| Fresh application imports/dispatch to first payload | 1,360 | 1,289 |
| Fresh process wall time, including harness/setup/cleanup | 1,539 | 1,466 |
| Existing warm-process startup to first controller payload | 1,126 | 1,041 |
| Snapshot load | 354 | 333 |
| Book load | 424 | 402 |
| Source verification | 26.4 | 19.3 |
| Ordinary standalone payload | 421 | 400 |
| Footnote-heavy standalone payload | 663 | 640 |

Fresh-process medians: same new harness on baseline and implementation,
`reader_timings.py --startup-only --corpus LOCAL_CORPUS --repeats 5 --warmups 1 --json`.
One discarded warmup, five measured fresh processes with new temporary SQLite
workspaces; application time starts before reader imports. Wall time also
includes interpreter/harness setup and cleanup. Other rows use the unchanged
version 2 probe, `--corpus LOCAL_CORPUS --repeats 3 --warmups 1 --json`, with
one discarded warmup and three samples. Reports remain outside Git at
`/tmp/startup-{before,after}-final-v3.json`, `/tmp/startup-before-v2.json` and
`/tmp/startup-after-final-v2.json`.

The fresh-application improvement is modest (5%); warm controller startup is
8% smaller. A separate one-run startup cProfile comparison attributes
399 → 275 ms to canonical file scans and 213 → 114 ms to safe-path work;
these are overlapping profiled totals, not additive stage medians.
Measurements precede that integration; #66 adds source-follow request handling, not startup work. Both profiles retain 10 `verify_snapshot_current` calls, 12 canonical scans
and 1,274 safe-path checks. The largest remaining fresh-load cost is whole-graph
JSON validation/detachment in the existing CORE trust machinery, left unchanged.
Profile overhead distorts totals (whole profiled dispatch was 2.19 → 2.36 s);
use the unprofiled medians for outcome claims. Profiles are outside Git at
`/tmp/startup-only-{before,after}-final.prof`.

### Outstanding issues
- Startup still takes about a second; this change does not establish subsecond or physical time to readable text. Version probing, splash, Neovim launch/IPC/painting, remembered-personal-workspace resume and a human reading trial are excluded. Existing terminal acceptance evidence is unchanged.
- Small local samples with warm OS cache, not cold-storage performance or a cross-host guarantee. Full source reads/hashes and full-graph trust validation remain substantial costs.

### Decisions requiring approval
None reserved. Default: resolve the boundary once within each canonical-file scan, never retain path or verification results across scans; hash the exact bytes after decoding them as UTF-8. Existing CORE/reference policies and caches are untouched.

## Faster section and outline view preparation — 20 October 2026

**Task:** [Codex: Faster section and outline moves](https://github.com/dialectmaterial/SOL/blob/6eddeaa94c979adf73cf02d5783329b550d84b2f/docs/coordination/CURRENT_TASK.md#codex-faster-section-and-outline-moves).
**Branch / PR:** `codex/section-latency` · [pull request](https://github.com/dialectmaterial/SOL/pulls?q=is%3Apr+head%3Acodex%2Fsection-latency); Claude reviews, author does not merge.
**Last implementation commit:** `7b412c771c97c5688ebb287ddcee56066dcaedea` (this report is committed afterward).

### Changed files
- `sol/terminal/neovim.py` — one typography projection for both styles and callouts; ASCII safety scanning in bulk with unchanged Unicode policy. All captures, reference checks and export finish checks remain.
- `sol/terminal/neovim_reader.py` — reader-local LRU of at most 256 immutable typography results, keyed by exact Markdown and plain-text strings. Full payloads still rebuild their references, warnings, provenance, notes and personal state; no source trust is cached.
- Controller/host regression tests; BEING §2, CHANGELOG and Codex's task status. No Lua/key handling, CORE, surface export, dependency or workspace changes. Git metadata in the original checkout is read-only; work/publication uses `/tmp/sol-section-latency`, cloned from `origin/main` at `6eddeaa`.

### Tests performed
- Documentation check and `git diff --check` — OK; external URLs were not network-checked.
- Full suite — 1,799 tests, OK (12 skipped, 4 expected failures); isolated XDG paths, existing `/tmp/sol-complete-search/.venv/bin/python` (Python 3.14.8).
- Focused controller (52) and host (34) tests — OK. New checks cover single projection, fresh/cached payload equivalence after Markdown-only and plain-text changes, detached style containers, source edits after a cache hit, and every Unicode control/format/surrogate/separator codepoint against the previous refusal policy. Existing staged-move, source-during-preparation and competing-save refusals remain covered by the full suite.
- Read-only real book: 4,629 records / 1,803 passages, identical generation and dataset metadata before/after; no personal workspace or source PDF opened. Same version 2 `scripts/reader_timings.py --corpus LOCAL_CORPUS --repeats 3 --warmups 1 --json`, width 72, temporary SQLite workspaces, real CORE checks, replaced terminal boundary. One discarded warmup and three measured runs per operation, baseline then implementation sequentially without concurrent profiling/tests. Reports outside Git: `/tmp/section-{before,after}-final.json`.

| Operation | Before median (ms) | After median (ms) |
| --- | ---: | ---: |
| Section next (`j` boundary route) | 1211 | 988 |
| Section previous (`k` boundary route) | 981 | 910 |
| `n` across section boundary | 1011 | 928 |
| `b` across section boundary | 1012 | 917 |
| Outline, second section | 1036 | 928 |
| Standalone ordinary payload | 460 | 461 |
| Standalone footnote-heavy payload | 977 | 705 |

The paragraph-boundary and outline medians improve by 8–11%; heavy payload
preparation by 28%. Section-next improves 18% in this comparison but remains
borderline at 988 ms (after samples 1,015/988/985 ms). An earlier comparison
was 1,016 → 1,005 ms there; three-run samples do not establish reliable
subsecond latency on every route. Startup is 1,169 → 1,233 ms and ordinary
payload time is effectively unchanged; no startup improvement is claimed.
Controller measurements exclude Neovim IPC, painting and physical-key latency.

A separate one-run cProfile comparison (`/tmp/section-profile` and
`/tmp/section-after-profile`) attributes 9.55 → 6.41 s to the 11 controller
view preparations and 2.91 → 0.60 s to typography (566 → 266 calls).
Both profiles call `verify_snapshot_current` exactly 216 times; its cumulative
cost is 9.07 → 8.10 s, still substantial. These are overlapping profiled totals,
not additive components or keypress medians; the baseline profile overlapped an
initial timing probe, so use the clean medians above for outcome claims.

### Outstanding issues
- The task's goal is only partly met: useful view-preparation savings, but section-next remains around a second and none of these samples establish consistently low physical-key latency. Full destination exports still detach the whole source graph and retain all existing verification work.
- No real-terminal or sustained human reading trial; Claude's terminal task remains separate. Existing BEING §7 limits on editor/transport failure after a successful save still apply.

### Decisions requiring approval
- Default implemented: retain only immutable typography by exact input values, bounded to 256 entries per reader; never reuse references or verification results. No reserved change is required by this implementation.
- **(reserved; proposal only)** Consider separately approving action-scoped fingerprint batching with a mandatory final verification before persistence/output and explicit semantics for edits during an action. This would change CORE's per-reference fingerprint policy and needs its own design/tests and maintainer approval. The current policy remains unchanged; this PR does not implement or depend on that proposal.

Earlier reports are in Git history (trimmed 21 October 2026).
