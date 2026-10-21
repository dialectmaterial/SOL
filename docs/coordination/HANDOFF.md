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
