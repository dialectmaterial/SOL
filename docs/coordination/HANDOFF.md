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

## The sentence study in ESSENCE — 19 October 2026

**Task:** "Claude Code: The sentence study in ESSENCE", assigned in task-board PR #33 (not yet merged; this branch leaves `CURRENT_TASK.md` alone to avoid a conflict).
**Branch / PR:** `claude/essence-sentences-ui` · opened with `gh pr create`
**Last implementation commit:** `10dab25070141869582ab5e86da77be41c6803a8`

### Changed files
- `sol/essence/tui/sentences.py` (new, no Textual): choices to providers (shared with words), `run` → `SentenceCount` (the v2 study, its provider, display-only texts and labels), `summary` (totals, bars, means by place, exclusions, method note), `rows` (twelve longest: words, beginning, heading | page), `source` (what `essence_source` needs, or None for a file), owner-only `save`.
- `sol/essence/tui/words.py`: `_create` takes a file-name prefix.
- `sol/essence/tui/app.py`: a study choice on Experiment (focused first); the worker runs either study; Results shows the sentence view, hides sources and export for it, and Enter opens a sentence in the reader.
- `tests/test_essence_tui.py`: real engine on an invented corpus (three targets, labels, source offset, saving, no book text in the artifact, recheck), files without a corpus, a changed corpus refused, and the screen flow with the exact open request.
- `docs/ESSENCE.md` §2 and §4, `CHANGELOG.md`.

### Tests performed
- `.venv/bin/python -B scripts/check_docs.py` — OK; full suite — **1,714 tests, OK** (12 skipped, 4 expected failures).
- Real session in tmux on the book: `E`, `3`, Sentence lengths, This section (Existence: 137 passages, 624 sentences, longest 123), Run; Enter on the longest opened it in the reader at its first letter; the study was saved in the reader's data folder.

### Outstanding issues
- Only the twelve longest sentences are listed (the v2 study keeps those); browsing every sentence needs a decision on the study's shape.
- Built on main, not on #32: `essence_source` exists on main already, so opening works without #32. ESSENCE §2 line 24 is edited by both PRs; whichever merges second resolves one line.

### Decisions requiring approval
- **Defaults:** the study choice and its order; no reference for sentences; the summary's wording; columns Words | Beginning | Where; beginnings cut at 60 characters.

## ESSENCE sentence study without CORE — 19 October 2026

**Task:** [Codex: ESSENCE sentence study without CORE](https://github.com/dialectmaterial/SOL/blob/759338cff70384edf44b6c8cb595156fdbae72b1/docs/coordination/CURRENT_TASK.md#codex-essence-sentence-study-without-core).
**Branch / PR:** `codex/sentence-file-provider` · opened with `gh pr create --base main`; status `In review`.
**Last implementation commit:** `7dd17efe99cae3b6ca0c4845ea57be8c71a66957` (this report follows).

### Changed files

- `sol/essence/sentences.py`, `sentence_inputs.py` — the existing word engine's CORE/file providers and scopes, v2 input/provenance envelope, complete-sentence span filtering, strict source-bound verification; original segmenter and v1 snapshot behavior preserved.
- `sol/essence/validation.py`, `terms.py` — move existing inert validation helpers/error type into a CORE-free module, with the term module's previous names re-exported unchanged. Sentence CORE imports are deferred to CORE operations.
- `sol/essence/cli.py`, `sentence_cli.py`, `word_cli.py`, `__init__.py` — shared target-provider arguments, file/span CLI and explicit-file verification, lazy sentence exports and bounded v1/v2 codecs. Decode precedes source discovery; saved paths are never opened.
- `tests/test_sentence_providers.py`, `fixtures_sentence_v1.py` — 22 tests and four original synthetic v1 encodings, including file/CORE scopes, cut sentences, Unicode/CRLF/BOM, empty inputs, stale/altered data, file guards, CORE-free execution, CLI dispatch and v1 byte compatibility. The synthetic fixture is Python source, so source-archive tests retain it without changing packaging.
- `docs/ESSENCE.md` §2/§5, `CHANGELOG.md`, `CURRENT_TASK.md` — implementation, method/bounds, CLI/API and task status. No interface, terminal, CORE, corpus, reader, dependency or legacy file changed.

### Python contract for the interface

All four functions are available from `sol.essence` and `sol.essence.sentences`:

```python
analyze_sentences(provider, *, origin=None) -> dict
check_sentence_result(provider, result) -> dict
encode_sentence_result(result) -> str
decode_sentence_result(data: bytes | str) -> dict
```

`provider` is the **existing** `CoreProvider(snapshot, scope=None)` or
`FileProvider(path, scope=None)`. CORE scopes are corpus/within/passages/span;
a CORE span names one exact `id`. File scopes are file/span. Offsets are
half-open codepoints in the complete original text. Segment first, then retain
only whole contained sentences; `exclusions.outside_span` counts excluded
segments. A file is one input row; positional statistics describe its retained
sentence sequence, without inferring paragraphs. An optional CORE reference
anchor is allowed only for CORE.

Explicit providers produce `sol.sentence-study` **v2**, method
`sentence-length-distribution-providers-v1`, using unchanged
`punctuation-rules-v1` and word tokens. `input` contains provider, binding,
scope and rows; `sentences` contains `[input_index, start, end, tokens]`.
There is no input text or local file path. Verification requires the caller's
provider with the recorded scope; CLI `check` restores that scope after
decoding but always needs `--input-file PATH` for file results. Files bind
every original byte, including BOM/CRLF and text outside a span. CORE retains
strict edition/generation checks. Refusals expose `status`/`code` through
existing study errors or filesystem errors.

Bare-snapshot `analyze_sentences(snapshot, *, scope=None, origin=None)` stays
v1, as do the ordinary corpus CLI and the reader's `S`. Both codecs still
check existing v1 artifacts; v1 retains 1 MiB. V2 allows 16 MiB (the real-book
provenance exceeds 1 MiB); input files keep the word provider's 64 MiB bound.
`save_sentence_result` retains its existing non-overwriting, owner-only policy.

### Tests performed

- 100 focused sentence/term/word/comparison tests passed; docs and whitespace checks passed. Full suite: **1,710 tests, OK (12 skipped, 4 existing expected failures)**, isolated XDG config/data/state/cache. Approved escalation was required because the restricted sandbox stalls an existing Textual test during asyncio executor shutdown; the isolated test and all full suites pass outside that restriction.
- A subprocess blocks all CORE/corpus/reader/terminal/TUI imports and successfully runs file analysis, v2 encode/decode/check and the ESSENCE CLI. The installed `sol` dispatcher also runs with an explicit file and no configured corpus; that dispatcher itself still imports BEING.
- Four pre-change synthetic v1 artifacts (whole corpus, within, chosen passage plus origin, empty scope) still check and encode byte-for-byte, allowing only the declared Unicode-runtime version to differ between supported Python versions. V1 sentence JSON/human output, check JSON/human output and term JSON/stdout/stderr match main byte-for-byte on invented inputs.
- Read-only real-book trial: v2 whole corpus has **9,127 sentences / 312,481 tokens**, **1,124,157 encoded bytes**; every sentence row, summary and positional statistic matches v1. V2 codec and recomputation pass; corpus generation remains current. Nothing saved or modified.
- Before implementation: resolved #29's task-board-only conflict and merged it at the maintainer's explicit instruction ([record](https://github.com/dialectmaterial/SOL/pull/29#issuecomment-6263268001)); reviewed/merged #30 after docs, 1,688 tests, GitHub checks, 11 malformed-source persistence refusals and 91,999 real-book word-source offsets ([review](https://github.com/dialectmaterial/SOL/pull/30#issuecomment-6263328023)). Claude's working files and local `AGENTS.md` were untouched.

### Outstanding issues

- `S` has not moved into the interface; no file-based reader/source-return feature or file-based segmentation-review workflow is added. These are outside the assigned engine task.
- Known punctuation-rule limitations remain. No new human segmentation error rate or manual reading-quality claim.

### Decisions requiring approval

- None **(reserved)**. Defaults for review: explicit providers use v2 while bare snapshots stay v1; whole contained sentences for spans; one file input row; retained-sequence positional statistics; verbatim UTF-8/CRLF/BOM; complete-source digest checks; CORE-only anchors; 16 MiB v2 and unchanged 1 MiB v1 bounds. No Decision statement, CORE/reference/corpus/workspace contract, dependency or deletion/overwrite policy changed.

## ESSENCE stage 3, the interface side — 18 October 2026

**Task:** "Claude Code: ESSENCE stage 3, the interface side", assigned in task-board [PR #28](https://github.com/dialectmaterial/SOL/pull/28) (approved by the maintainer on 18 October 2026; not yet merged, so this branch's `CURRENT_TASK.md` is left as it was to avoid a conflict).
**Branch / PR:** `claude/essence-comparison-ui`, stacked on Codex's #29 · opened with `gh pr create`
**Last implementation commit:** `1539983c49133e8d3665f7ec583d40a72da331d7` (first round `66663f0`; fixes from a real-book session follow it)

### Changed files
- `sol/essence/tui/words.py` — `Count` (study, comparison view, providers); with a reference, `run` calls `compare_words` once; `rows` adds the two measures and names undefined ones; `sources` lists each contributing passage per side (corpus rows carry ID, first offset and content digest; file rows cannot open); `export` calls `export_word_comparison` and writes owner-only, never overwriting.
- `sol/essence/tui/app.py` — Results: measure columns, Sources table (Enter opens in the reader), Export CSV/TSV (workspace sessions only), a status line; Experiment: Cancel; Ctrl-Q with priority. The open request is a private OSC written through Textual's driver, as Textual writes its own clipboard OSC.
- `sol/terminal/neovim_essence.lua` — `TermRequest` on ESSENCE's buffer: strict shape check, reader shown (from fullscreen: beside, or hidden when narrow), `essence_source` request; a malformed request is reported and ignored. `VimLeavePre` sends Ctrl-Q and waits up to 2 s.
- `sol/terminal/neovim_reader.py` — `essence_source` navigation: CORE capture, refusal on a changed content digest or an offset outside the passage, then the staged path shared with `study_open`.
- `sol/terminal/neovim_view.lua`, `neovim_panels.lua`, `neovim_notes.lua`, `neovim_tree.lua` — popups, the note editor and the outline centre in the reader's columns while ESSENCE is beside it.
- Tests: `test_essence_tui.py` (measure columns and undefined labels, sources, the exact OSC payload, file sources not opening, export only in workspace sessions, nothing to export without a reference, cancel saves and shows nothing, Ctrl-Q from a text field saves; real engines: sources at the right offset, owner-only export, stale file refused); `test_neovim_reader.py` (open, history back, four refusals that move nothing); `test_reader_surface_neovim.py` (headless Neovim with a raw-terminal stand-in: foreign OSC ignored, malformed one warned once, valid one sent, fullscreen becomes beside, popup stays left of ESSENCE, quitting saves).
- `docs/BEING.md` (§2 `E` row, §6), `docs/ESSENCE.md` (§4), `CHANGELOG.md`.

### Second round: a real session on the book (19 October)
Running `sol` in tmux on the real corpus found three things the tests had not:
- **Studies saved from ESSENCE were lost** (since stage 2): ESSENCE inherited Neovim's private XDG/`TMPDIR` directories, so `words-*.sol-analysis.json` went into the reader's temporary folder, deleted on exit. The launch now carries the reader's own values (`ESSENCE_ENVIRONMENT` in `neovim_reader.py`), and Neovim starts ESSENCE with them.
- **Opening a source failed in a real terminal:** terminal mode ends only after the OSC callback returns, and the reader captures a position only in normal mode. The request now waits for `ModeChanged` to normal mode in the reader window. The headless test now reports terminal mode and announces the change, and fails with the real error if the wait is removed.
- **The keyboard path on Results was unpredictable:** Tab stopped at the tab bar and the scroll container, and switching screens could jump back to Results. Now a count focuses the word table, Enter goes to the word's sources, Escape goes back, and `1`–`4` start on each screen's first control. The summary scrolls in at most 8 lines, so the table keeps its height.

### Tests performed
- `.venv/bin/python -B scripts/check_docs.py` — OK; full suite — **1,688 tests, OK** (12 skipped, 4 expected failures); `git diff --check` clean.
- Mutation check: restoring the old popup geometry fails the new headless test (108 > 76 columns).
- Real Textual app inside a headless Neovim terminal: its open request arrives intact through `TermRequest`; Ctrl-Q sent by Neovim saves state and exits in about 0.25 s.
- Real book (read-only, this machine): section vs whole book 2.8 s through the interface (`analyze_words` alone 1.7 s; the comparison's study digest and rows add about 0.5 s); whole book alone 1.6 s; 1,177 sources for *being*, the first opening at the word; CSV export 3.2 s, 11.7 MB.
- Real session after the fixes, `sol` in tmux at 160×45 on the real book: `E`, then `3`, section vs whole book, Count (about 6 s); the study saved owner-only in the reader's data folder; TSV export 11.7 MB; Down to *determinateness*, Enter, Enter: the reader opened p. 10 with the cursor on the word's first letter; Alt-Left returned to the start; `q` with ESSENCE open saved `{"screen": "results", …}` and exited 0.
- After the fixes: docs OK; full suite **1,688 tests, OK** (12 skipped, 4 expected failures).
- Not done: a manual session in Alacritty or Kitty (this machine has foot); tmux is a real terminal, but a human did not watch it.

### Outstanding issues
- Cancel cannot stop the engine; the count finishes in the background and is discarded.
- A source opens at the word's first occurrence in that passage; later occurrences are not listed separately (the v1 artifact keeps only the first).
- If the reader is busy with another request, a source request is dropped silently, as other requests are.
- Exports name themselves `words-<time>.csv|tsv`; they are not linked to the saved study's file name.
- Studies saved from ESSENCE before this fix are gone (they were in a temporary folder); nothing to migrate.

### Decisions requiring approval
- **Defaults:** OSC number 5379 and the `sol-essence` tag; opening from fullscreen leaves ESSENCE beside the reader (hidden below 100 columns); Ctrl-Q as the save-on-quit signal with a 2 s wait; export only in workspace sessions, into the studies directory; undefined-measure labels; sources table height 8 rows. No reserved decision: no CORE/protocol/workspace contract or dependency changes.

## ESSENCE stage 3 engine: comparison measures and export — 19 October 2026

**Task:** [Codex: ESSENCE stage 3 engine, comparison measures and export](https://github.com/dialectmaterial/SOL/blob/df852763fe325cb06acdac825538d91ff98cca9a/docs/coordination/CURRENT_TASK.md#codex-essence-stage-3-engine-comparison-measures-and-export), assigned by the maintainer and in task-board PR #28.
**Branch / PR:** `codex/essence-comparison` · opened with `gh pr create --base main`. Status: `In review`.
**Last implementation commit:** `df852763fe325cb06acdac825538d91ff98cca9a` (this report follows).

### Changed files

- `sol/essence/comparison.py` — two documented descriptive measures over verified v1 counts, explicit undefined reasons, unchanged source study, and CSV/TSV export with denominators, source bindings, scope/study digests and warnings. No new saved artifact schema.
- `sol/essence/cli.py`, `word_cli.py`, `__init__.py` — `sol analyze words-export FILE --format csv|tsv`, common provider reconstruction with `check`, and lazy Python exports. Decode precedes source discovery; verification completes before table output.
- `tests/test_word_comparison.py` — 17 invented-input tests: formulas/sign, unequal denominators, zero counts/empty scopes, Unicode CSV/TSV round trips, both providers, CORE CLI export, stale/unselected changes, tampered counts, v1 compatibility and CORE/UI-free file execution.
- `docs/ESSENCE.md` §5, `CHANGELOG.md` — formulas, zero policy, limits and examples. `CURRENT_TASK.md` records only Codex's assigned slot from #28 and status; Claude's slot is untouched here.

### Python contract for the interface

Both functions are in `sol.essence.comparison`, also exported from `sol.essence`:

```python
compare_words(target, *, reference, result=None) -> dict
export_word_comparison(target, *, reference, result=None, format="csv") -> str
```

`target` and required `reference` are the existing `CoreProvider(snapshot,
scope=None)` or `FileProvider(path, scope=None)`, independently scoped and
possibly mixed. `result=None` runs a new `analyze_words`; otherwise `result`
must be the existing `sol.word-frequencies` v1 artifact and is strictly
recomputed with those providers/scopes before any measure or export is used.
Refusals use existing `WordStudyError` (`status`, `code`) / filesystem errors.
The previous `analyze_words` names and result shape are unchanged.

The comparison view has `method`, `study` (the unchanged verified v1 artifact),
`study_sha256` (SHA-256 of `encode_word_result(study)` without newline), `rows`
and `warnings`. Every row has `word`, the existing `target`/`reference` cells
(including count, denominator, rate, locations), plus
`rate_difference_per_10000_tokens`, `rate_difference_status`,
`log2_rate_ratio`, `log2_ratio_status`. Order is the study's union-vocabulary
order. UI code may save `view['study']` through the existing v1 codec; the
comparison view itself is not an artifact accepted by `sol analyze check`.

For counts `a,b` and token totals `Nt,Nr`, difference is
`10000*(a/Nt-b/Nr)`; log ratio is `log2((a*Nr)/(b*Nt))`. Round only the final
measures to six decimals. No smoothing: zero counts make the log ratio null
with `zero_target_count`/`zero_reference_count`; the difference stays defined
when both denominators are positive. An empty denominator makes both null
with `empty_target`/`empty_reference`. Otherwise status is `defined`; two empty
scopes have no vocabulary rows. Positive measures mean a higher target rate.
Warnings retain projection/size/source cautions and explicitly deny a
significance, confidence or conceptual-similarity interpretation.

Export returns text without writing files, using standard CSV quoting and LF
records (`format='csv'` or `'tsv'`). Empty numeric cells have explicit status
columns; a header-only table represents an empty union. Each word row repeats
the method ID, original-study digest, provider/binding metadata, scope digests
and warnings. There are no passage texts, contexts, source paths, headings,
token sequences or new dependency. Keep the original private study for source
locations and empty-scope provenance; exports do not replace it or authorize
source/workspace writes.

### Tests performed

- 17 focused comparison/export tests passed. Docs check and `git diff --check` passed. Full suite: **1,680 tests, OK (11 skipped, 4 existing expected failures)**.
- Existing `words --json` v1 and term CLI JSON/stdout/stderr are byte-for-byte identical to main on invented inputs. Existing artifact check/encoding remain unchanged. A subprocess blocks all CORE/corpus/reader/terminal/TUI imports and successfully compares/exports ordinary files through API and CLI.
- Read-only private Being-versus-book trial: 131,267 versus 312,481 tokens; 7,317 TSV rows round-tripped, 11,709,384 UTF-8 bytes with warnings/provenance. Study and export computed in memory, no output file saved and no source modified.
- Reviewed and merged [#24](https://github.com/dialectmaterial/SOL/pull/24#issuecomment-6251723844) after 1,653 tests and its launch-refusal regression; [#25](https://github.com/dialectmaterial/SOL/pull/25#issuecomment-6251744268) after 1,661 tests, stale-context and cancelled-count regressions; [#27](https://github.com/dialectmaterial/SOL/pull/27#issuecomment-6251879359) after resolving HANDOFF/CHANGELOG-only conflicts, 1,663 combined tests and a read-only real-book verification check. Every PR's GitHub checks passed before merge.

### Outstanding issues

- [#28](https://github.com/dialectmaterial/SOL/pull/28#issuecomment-6251755945) is reviewed (docs, 1,642 tests and GitHub checks pass) but conflicts in `CURRENT_TASK.md` after the earlier merges. CLAUDE.md requires the author to resolve this non-HANDOFF/CHANGELOG conflict; requested that fix. The assigned Codex task is recorded here so the implementation does not wait on a coordination-only conflict. The dropped on-disk cache was not implemented.
- Interface controls/source navigation remain Claude's lane. No file in `sol/essence/tui/`, `sol/terminal/`, `sol/core/`, `sol/corpus/`, `sol/reader/` or `pyproject.toml` is changed by this engine PR. No keyness/significance estimator or inference for rare/overlapping observations is added.

### Decisions requiring approval

- None reserved. Defaults for review: two descriptive effect sizes; no pseudocounts; null plus a reason rather than infinity; six-decimal final rounding; required reference; a derived view over unchanged v1 studies; CSV/TSV with explicit denominators and provenance, blank undefined numeric cells, header-only empty tables. These change no CORE/reference/workspace contract or dependency.

## Faster reader start-up — 19 October 2026

**Task:** maintainer's request in the session ("sol starts super slow"), within Claude Code's CORE/reader lane.
**Branch / PR:** `claude/faster-startup` · opened with `gh pr create`
**Last implementation commit:** see the PR (the commit before this report).

### Changed files
- `sol/core/protocol.py` — `_remember` (cache entry from a verified snapshot, used by both paths) and `remember_verified` (only genuine `CorpusSnapshot`s; a snapshot outside the fast comparison's rules is not cached).
- `sol/core/corpus.py` — `load_corpus_book` calls `remember_verified` right after `load_snapshot`.
- `tests/test_core_protocol.py` — a freshly loaded book's first check reads no files, and a later in-memory change is still refused; a corpus beyond the nesting bound is not cached and is still refused.
- `docs/CORE.md` (§6), `CHANGELOG.md`.

### Tests performed
- Real start-up in a pseudo-terminal (launch to drawn page), three runs each, same environment: `main` 0.95 s; this branch 0.86 s. Python-side phases before the change: imports 0.05 s, book load 0.2 s, workspace 0.05 s, first check 0.4 s, rest 0.25 s, Neovim about 0.1 s.
- `.venv/bin/python -B scripts/check_docs.py` — OK; full suite — 1644 tests, OK (11 skipped, 4 expected failures).

### Outstanding issues
- The estimate was 0.6 s; the gain is 0.1 s because the cache must still be built once (about 0.17 s). Remaining start-up is mostly verification itself (validating every record, about 0.11 s; the comparison and fingerprint checks) plus the first page.
- The remembered workspace is still opened twice: first read-only to validate it before adoption (deliberate, about 25 ms), then for use. Left as is.

### Decisions requiring approval
- None. Going further would mean trusting a previously validated generation across starts, or showing the first page before verification finishes; either relaxes a check and would be a reserved decision.


## ESSENCE stage 2, interface side: word frequencies on screen — 18 October 2026

**Task:** the maintainer's go on 18 October to take the interface side of stage 2 while Codex builds the engine (["Codex: ESSENCE stage 2 engine"](https://github.com/dialectmaterial/SOL/blob/main/docs/coordination/CURRENT_TASK.md)); continues "Claude Code: ESSENCE stage 1, the interface shell".
**Branch / PR:** `claude/essence-words-ui`, stacked on #24 · opened with `gh pr create`
**Last implementation commit:** `942f67243959f6f10403b67ff40d50a44b796787`

### Changed files
- `sol/essence/tui/words.py` (new): choices → `CoreProvider`/`FileProvider` scopes (passage = `passages`, section = `within` the passage's parent reader path, book = whole corpus, file = `FileProvider`); `run`, `rows` (top 2,000), `summary`, owner-only `save`; lazy engine import with `EngineMissing`.
- `sol/essence/tui/app.py`: Experiment screen (target and reference choices, file inputs, Count words, background worker, status); Results screen (summary lines and a word table).
- `tests/test_essence_tui.py`: scopes from choices, files without a corpus, rows/summary/saving, missing engine, the screen flow with a stand-in engine, and a real-engine test that skips until the engine is merged.
- `docs/ESSENCE.md` (§4 implemented note), `CHANGELOG.md`.

### Interface contract used (Codex's engine, in progress)
`sol.essence.words.analyze_words(target, *, reference=None)`, `encode_word_result(result)`; `sol.essence.word_inputs.CoreProvider(snapshot, scope)` and `FileProvider(path, scope)`; scopes `{"kind": "passages", "ids": [...]}`, `{"kind": "within", "path": "/..."}`, `None` for the corpus. Read from Codex's working tree without modifying it; any change there needs a matching change in `words.py`.

### Tests performed
- `.venv/bin/python -B scripts/check_docs.py` — OK; full suite — 1632 tests, OK (12 skipped, 4 expected failures).
- With Codex's in-progress engine files laid over a throwaway copy: all 13 ESSENCE interface tests pass, including the real-engine test; on the real book, passage 0.5 s, section vs book 1.4 s, whole book 1.1 s.
- Not done: a manual run in Alacritty.

### Outstanding issues
- Codex's engine (#26) is merged; the real-engine test now runs in the normal suite.
- Opening a word's source passage in the reader (stage 3) is not implemented.
- Long counts cannot be cancelled yet; a new count replaces a running one.

### Decisions requiring approval
- **Defaults:** the four target choices and three reference choices; "this section" is the passage's parent reader path; 2,000 rows shown; artifacts saved only for workspace sessions.

## ESSENCE stage 1, the interface shell — 18 October 2026

**Task:** ["Claude Code: ESSENCE stage 1, the interface shell"](https://github.com/dialectmaterial/SOL/blob/main/docs/coordination/CURRENT_TASK.md)
**Branch / PR:** `claude/essence-shell` · opened with `gh pr create`
**Last implementation commit:** `9f5c723788fdb519e4d928016b42fc9ba6b21969`

### Changed files
- `sol/essence/tui/` (new): `context.py` (private handoff file and investigation state; no Textual import), `app.py` (Textual app, four placeholder screens, palette off), `__main__.py` (`python -m sol.essence.tui --context FILE`; without Textual, a clear message and exit 2), `__init__.py` (install hint, availability check).
- `sol/terminal/neovim_essence.lua` (new): the terminal float, split/fullscreen/hidden layouts, Alt-F and Alt-R terminal-mode mappings, close and failure handling; state in `_G.SOLEssence` across reader reloads.
- `sol/terminal/neovim_reader.py`: `essence_open` request (checks the packet, writes the context in a private temporary directory removed at exit, state file only with a workspace, selection without its text).
- `sol/terminal/neovim.lua`, `neovim_view.lua` (page centres in the columns ESSENCE leaves), `neovim_requests.lua` (`essence` result), `neovim_controls.lua` (`E`, help, `relayout`).
- `pyproject.toml`: optional extra `essence = ["textual>=8,<9"]`; `.github/workflows/tests.yml` installs `.[essence]` so the Textual tests run in CI.
- Tests: `tests/test_essence_tui.py` (new; context round trip and refusals, no Textual import, missing-Textual message, screens, saved/restored state, temporary sessions, palette off); `test_reader_surface_neovim.py` (headless Neovim with a real terminal process: open beside, toggle, back to reader, survive a reload, `E` refocus, close, unchanged position, narrow terminal, launch failure); `test_neovim_reader.py` (context contents and privacy, missing Textual, temporary session); `test_packaging.py` (the new extra, never a base dependency).
- `docs/BEING.md` (§2 controls, §6 implemented note), `docs/ESSENCE.md` (§4 implemented note with measurements), `CHANGELOG.md`.

### Tests performed
- Spike in a headless Neovim server with keys typed through terminal mode: start-up about 110 ms (three runs); 40→120 columns reflow without restart; Escape, Alt-Left/Right, Alt-X, Ctrl-S/N, Tab, Shift-Tab, F1, arrows, Ctrl-Left intact; Ctrl-\ Ctrl-N returns control to Neovim. Escape-then-letter reads as Alt+letter; Ctrl-Q quits and Ctrl-P opens the palette in Textual by default.
- The real app inside Neovim's terminal at split width: renders the origin and screens; `3` switches screen.
- `.venv/bin/python -B scripts/check_docs.py` — OK; `.venv/bin/python -B -m unittest discover -s tests` — 1626 tests, OK (11 skipped, 4 expected failures).
- Not done: a manual session in Alacritty or Kitty.

### Outstanding issues
- Quitting the reader while ESSENCE is open ends ESSENCE without saving its state (Neovim stops the job); stage 1 saves state only on `q`.
- Popups from the reader (`c`, search) still centre on the whole screen and draw over ESSENCE.
- The screens are placeholders; the engine is Codex's stage 2, to be connected afterwards.

### Decisions requiring approval
- **Defaults:** ESSENCE on the right, 45% of the columns (at least 40); fullscreen below 100 columns; Alt-F and Alt-R as layout keys; `1`–`4` and `q` inside ESSENCE; state only for workspace sessions. The dependency and `E` were decided by the maintainer (#23).

## ESSENCE stage 2 engine: word frequencies — 18 October 2026

**Task:** [Codex: ESSENCE stage 2 engine, word frequencies without an interface](https://github.com/dialectmaterial/SOL/blob/c1dd916bfdb8bb054b3a99d5c01fc92950cdbf0c/docs/coordination/CURRENT_TASK.md#codex-essence-stage-2-engine-word-frequencies-without-an-interface).
**Branch / PR:** `codex/essence-word-frequencies` · opened with `gh pr create --base main`. Status: `In review`.
**Last implementation commit:** `c1dd916bfdb8bb054b3a99d5c01fc92950cdbf0c` (this report follows).

### Changed files

- `sol/essence/tokenization.py`, `terms.py` — move the existing tokenizer unchanged into a CORE-free module; the old `_tokens` name remains an alias to that exact function. Existing term and sentence artifacts/methods are unchanged.
- `sol/essence/word_inputs.py` — explicit `CoreProvider` / `FileProvider` boundary, independent scopes, strict snapshot/file freshness, existing corpus projection and facsimile masks. File input never imports CORE or discovers application data.
- `sol/essence/words.py` — deterministic token/type counts and union frequency table; absolute counts, explicit per-side token denominators, rates and source locations; versioned `sol.word-frequencies` v1 codec and exact recomputation verifier. Only vocabulary, aggregates and provenance are serialized, never passage text, contexts or token sequences.
- `sol/essence/word_cli.py`, `cli.py`, `__init__.py` — headless/API exports, `sol analyze words`, source/scope options and `sol analyze check` dispatch. Artifact paths never select input files; callers provide those explicitly. Check emits a receipt without rewriting the artifact.
- `tests/test_word_frequencies.py` — 26 tests with invented inputs, including CORE-free imports, unequal/mixed providers, Unicode, empty scopes, source changes, raced reads, untrusted JSON and artifacts larger than the legacy 1 MiB bound.
- `docs/ESSENCE.md` §5, `CHANGELOG.md`, `CURRENT_TASK.md` — implementation, API/artifact semantics and status. Rebased onto the merged task board; only Codex's status differs there.

### Python contract for the interface

```python
from sol.essence import CoreProvider, FileProvider, analyze_words

analyze_words(
    target: CoreProvider | FileProvider,
    *, reference: CoreProvider | FileProvider | None = None,
) -> dict
```

Each provider owns its independently chosen source and scope:
`CoreProvider(snapshot, scope=None)` takes a verified `CorpusSnapshot`; scopes
are `corpus`, `within` with `path`, `passages` with exact `ids`, or `span` with
exact `id`, `start`, `end`. `FileProvider(path, scope=None)` takes an explicit
regular UTF-8 file; scopes are `file` or `span` with `start`, `end`. Defaults
select the whole eligible source. Spans are half-open codepoints in original
text; only wholly contained tokens count. CORE inputs retain canonical order
and the term study's attribution/type/review filters. Reference is optional
and may use another provider/source. No widget, persistence or workspace input
is required. Refusals are `WordStudyError` (`status`, `code`) or filesystem
`OSError`; no partial artifact is returned on a failed freshness check.

The returned serializable dict is the artifact, with `protocol`, `version`,
`method`, `target`, `reference` (or null), `frequencies`, `warnings`. Each side
has `provider`, `binding`, `scope`, text-free `inputs`, `summary` containing
`token_count`, `type_count`, `input_count`, and `exclusions`. A frequency row
has normalized `word` and one cell per side: `count`, `denominator`,
`rate_per_10000_tokens`, `locations`. Each location is
`[input_index, count_in_input, first_start, first_end]`; CORE input metadata
supplies exact UUID, reader path, pages, attribution and digests for return to
source. Zero denominators give null rates. Rows sort by descending target
count, then word; words unique to the reference remain visible.

`encode_word_result(result)` and `decode_word_result(data)` transport the
artifact. `check_word_result(target, result, *, reference=None)` requires
caller-supplied providers with matching scopes, verifies full generation/file
bindings and recomputes every field. The CLI calls these same functions.
Neither decode nor an artifact's locations authorize source navigation without
the normal CORE checks. See ESSENCE §5 for exact scope objects and CLI examples.

### Tests performed

- Focused: 26 new word-study tests, plus the unchanged 24 CLI, 26 term and 9 sentence tests passed.
- Shared `.venv/bin/python -B scripts/check_docs.py` — passed. Shared `.venv/bin/python -B -m unittest discover -s tests` after rebase — **1,642 tests, OK (11 skipped, 4 existing expected failures)**, with isolated XDG state and Neovim log path. `git diff --check` passed.
- Byte-for-byte stdout/stderr/JSON comparison of the term command against main on an invented corpus — identical. `python -m sol analyze words --file ... --json` also passed with an explicitly absent configured corpus.
- Read-only private whole-book trial: **312,481 tokens, 7,317 types, 1,757 input rows**; encoded artifact **4,288,905 bytes**, strictly recomputed successfully in memory. No book text or artifact was written to Git or saved by this trial.
- Reviewed newly opened [interface PR #24](https://github.com/dialectmaterial/SOL/pull/24#issuecomment-6251361426) before publishing: docs and GitHub checks pass, but visual `E` sends no ESSENCE request and changes the selected span. Posted the headless reproduction and left it open for Claude's fix. Its separate local full run was interrupted after hanging in the first Textual pilot's asyncio teardown (also reproduced under a timed focused run); no local full-suite pass is claimed for #24.

### Outstanding issues

- Interface integration and a CLI/TUI equivalence trial belong to the later interface work; no interface acceptance is claimed here. No file under `sol/terminal/`, `sol/essence/tui/` or `pyproject.toml` was touched.
- File inputs are bounded at 64 MiB and artifacts at 16 MiB. This is a synchronous, in-memory lightweight experiment, not a collection index or background-job runner. Locations retain the first occurrence per contributing input, with its aggregate count.

### Decisions requiring approval

- None reserved. Reviewable defaults: the unchanged term tokenizer/projection; whole-token span containment; independent CORE/file providers; union vocabulary; per-10,000 rates rounded to six decimals; undefined zero-token rates; strict whole-source binding; explicit file paths at check time; bounded ASCII JSON. This is an ESSENCE result format, not the proposed investigation-persistence schema or a change to any CORE/workspace contract.

## Reconcile the ESSENCE interface decisions in the documentation — 18 October 2026

**Task:** ["Claude Code: Reconcile the ESSENCE interface decisions in the documentation"](https://github.com/dialectmaterial/SOL/blob/claude/essence-interface-docs/docs/coordination/CURRENT_TASK.md), requested by the maintainer with the [ESSENCE interface brief](proposals/ESSENCE_INTERFACE_BRIEF_2026-10-18.pdf)
**Branch / PR:** `claude/essence-interface-docs` · opened with `gh pr create`
**Last implementation commit:** `0a6bceb20aa673552b086c2e20458323d67b5a6b`

### Changed files
- `docs/ESSENCE.md` — §1 orchestrator/encyclopedia purpose; §2 not-implemented list; §4 rewritten as the interaction model (seven decisions, launch/return table, target/reference, investigation record merged with the old inquiry contract, open decisions); §5 staged plan and the word-frequency first experiment; §7 rewritten as the model-history encyclopedia and task registry (methods map kept); §8 lazy imports, state ownership, manual acceptance for the prototype.
- `docs/ARCHITECTURE.md` — §2 staged path to independent components, ESSENCE's current CORE dependency; §4 hybrid surfaces and outer/inner layout; §6 D revised (interface stages first, embeddings at the model-adapter stage, with the reason); §8 research briefs are evidence, not authorities.
- `docs/BEING.md` — §6 reader-side requirements (handoff, return, focus, key compatibility, failure, lifetime).
- `docs/CORE.md` — §1 CORE as an optional provider (API v1 and protocol unchanged); future collections as requirements, not a schema.
- `docs/coordination/proposals/ESSENCE_INTERFACE_BRIEF_2026-10-18.pdf` — the brief, unchanged.

### Decisions mapped to sections
| Brief decision | Recorded in |
| --- | --- |
| Hybrid: persistent Neovim BEING, on-demand Textual ESSENCE | Architecture §4; ESSENCE §4 (1–2); BEING §6 |
| Two presentations, one investigation; outer vs inner layout | ESSENCE §4 (3–4); Architecture §4 |
| Interface before breadth; word tokenizer first | ESSENCE §4 (5), §5 |
| One capability, interactive and headless | ESSENCE §4 (6) |
| CORE optional; independent components, staged packaging | ESSENCE §4 (7); Architecture §2; CORE §1 |
| Model history ≠ model picker; three knowledge objects; sourced genealogy | ESSENCE §7 |
| Target vs reference; scaling constraints | ESSENCE §4, §7 |
| Staged plan 0–5 with exit criteria | ESSENCE §5; Architecture §6 D |

### Claims checked against code
- One distribution (`sol-organizes-logic`); Textual is not a dependency (`pyproject.toml`).
- Every ESSENCE study imports `sol.core` (5 imports in `sol/essence/`), so CORE-optional is stated as a decision with a path, not a fact.
- `S` runs the sentence study and captures the live paragraph without saving a visit, but carries no selection (`neovim_reader.py` `study_panel`).
- The term study's tokenizer (`sol.essence.terms._tokens`): letters plus combining marks and internal apostrophes, NFC, case-folded; digits and punctuation excluded; hyphenated compounds split.

### Semantic changes from the previous text
- Architecture §6 D: embeddings were the "second experiment"; they now wait for the interface and word-frequency stages.
- ESSENCE §4: the "complete inquiry contract" gained a provider (`core | file`), a comparison scope, an execution block and the return layout; it stays a conceptual schema.
- ESSENCE §7: the "ML roadmap" is now the encyclopedia/registry design; the earlier model-history file is still not available and nothing is claimed about it.

### Tests performed
- `.venv/bin/python -B scripts/check_docs.py` — OK (links and anchors); `.venv/bin/python -B -m unittest discover -s tests` — 1616 tests, OK (11 skipped, 4 expected failures). No code changed.

### Outstanding issues
- The nested-terminal arrangement (keys, alt-keys, resizing, launch latency) is unproven on this machine; the brief says so too.
- Open alternative recorded at the maintainer's request (ESSENCE §4, referenced from Architecture §4): Textual as the outer host with Neovim embedded; not adopted; proposed test: an `nvim --embed` spike plus the reading-trial evidence.
- Open decisions listed in ESSENCE §4: entry key and `S`; split side, widths, focus; investigation persistence and background jobs; provider/adapter API and package split; first tokenizer and scopes; encyclopedia source format and governance; Textual as base or optional dependency.

### Decisions requiring approval
- **(reserved, approved by the maintainer on 18 October 2026)** New **Decision** statements in Architecture §§2, 4, 6, ESSENCE §§1, 4, 5, 7, BEING §6 and CORE §1, taken from the maintainer's brief. Because they change authority Decision statements, the maintainer merges this PR.

## Split the Lua reader into modules — 18 October 2026

**Task:** [Codex: Split the Lua reader into modules](https://github.com/dialectmaterial/SOL/blob/f1bdaa6/docs/coordination/CURRENT_TASK.md#codex-split-the-lua-reader-into-modules).
**Branch / PR:** `codex/lua-modules` · [PR #21](https://github.com/dialectmaterial/SOL/pull/21), opened with `gh pr create --base main`. Status: `In review`.
**Last implementation commit:** `552a769f09e0e747e5a0535bc758ba387310859c` (modules, packaging, tests and documentation; this report follows).

### Changed files

- `sol/terminal/neovim.lua` — 22-line entry, down from 1,332. Loads only explicit files beside its own installed path, with no `require`, user runtime search or `package.loaded` cache. View reloads start the same packaged entry.
- `neovim_text.lua` — exact Unicode/codepoint helpers and inert payload validation.
- `neovim_view.lua` — bounded page projection, source/cursor/selection mapping, packet capture/restore/export, typography and themes.
- `neovim_panels.lua` — shared popup state/lifecycle and search, sentence-study and printed-source result panels.
- `neovim_requests.lua` — persistent action channel, response dispatch and view mode/focus reloads.
- `neovim_footnotes.lua` — book-note panels, nested links and panel backtracking.
- `neovim_notes.lua` — personal-note editor, draft recovery and revision history.
- `neovim_controls.lua` — actions, source/personal-note context, outline integration, bindings and lifecycle. The existing `neovim_tree.lua` is unchanged; it now loads through the same package-local loader.
- `pyproject.toml`, `tests/test_packaging.py` — ship/check all `sol.terminal/*.lua` assets in wheel and source archive; actual headless passage from a wheel pip-installed without dependencies/network into a temporary venv. Misleading runtime/package paths and preloads cannot replace modules; a missing packaged module refuses without falling back.
- `docs/BEING.md`, `CHANGELOG.md` — implementation file ownership and unchanged behavior. Only Codex's status changes in `CURRENT_TASK.md`.

### Tests performed

- Existing controller/headless tests are unchanged. Focused suites: 69 surface/host tests (one existing skip) and 37 controller tests passed. Packaging: 20 tests passed, including the actual installed-wheel/headless scenario. The missing-module check also ran in the final full suite.
- Documentation check passed. Full suite: 1,607 tests, OK (11 skipped, 4 existing expected failures), with isolated XDG state/Neovim logs and wheel/source-archive tests. Headless checks cover source identity, both reading modes, note drafts/history, nested footnotes, selections/yank, theme/resize, navigation and action-channel lifecycle.
- Reviewed and merged [task board #18](https://github.com/dialectmaterial/SOL/pull/18#issuecomment-6247385054), after separate worktree docs/1,603 tests and all GitHub checks passed. Latest maintainer sequencing was to open the completed [formula sheet PR #20](https://github.com/dialectmaterial/SOL/pull/20), then take this Lua task; #20's GitHub checks pass and its private 30-record sheet has no verdicts recorded.
- Re-reviewed corrected [speed PR #19](https://github.com/dialectmaterial/SOL/pull/19#issuecomment-6247719999) in a fresh worktree: the reported 70-level metadata reproduction now refuses before caching, preserving the existing nesting bound; docs/1,606 tests and every GitHub check passed. Merged it and rebased this branch before implementation.

### Outstanding issues

- No manual terminal-reading trial was performed; this is a behavior-preserving implementation split, verified through unchanged tests and the installed artifact. No new control, packet field, dependency, schema, source status or workspace behavior is introduced.
- Formula review work remains in separate PR #20. No source PDF, canonical book text, private crop/verdict artifact, synced project file or `AGENTS.md` is included here. No file under `sol/core/`, `sol/reader/` or `sol/terminal/neovim_reader.py` was edited.

### Decisions requiring approval

- None reserved. Defaults: seven cohesive factory modules plus the existing tree; one private per-view context with explicit connections, and direct module loading from the installed entry's directory. Python retains all source verification and persistence authority.

## Finish the reader speed list — 19 October 2026

**Task:** ["Claude Code: Finish the reader speed list"](https://github.com/dialectmaterial/SOL/blob/claude/assign-speed-and-lua/docs/coordination/CURRENT_TASK.md)
**Branch / PR:** `claude/reader-speed-list`, stacked on #18 (task board) · opened with `gh pr create`
**Last implementation commit:** `c49681fc0e4adae5516c4b864c24efbcb8a5ab18`

### Changed files
- `sol/core/protocol.py` — the in-memory comparison uses canonical JSON text plus structural equality with a private parsed copy (about 47 ms instead of 100 ms); the copy is never returned. Approved edge: an `int`/`float` subclass with an equal value is accepted.
- Review fix (Codex, PR #19): the verified copy is checked once against every `_json_value` rule, including the 64-level nesting bound, before it is cached; a corpus with deeper metadata is refused on the first and every later call. Codex's reproduction is a regression test.
- `sol/reader/surface.py` — `CaptureExport` has CORE check the reader's own snapshot instead of its deep copy, so a reader action compares once; the copy stays the export's private graph and `finish()` still proves they agree. (The deep copy itself stays: at 47 ms it beat a JSON round trip at 80 ms.)
- `sol/core/models.py`, `sol/reader/actions.py` — `find_passage` finds an exact current ID without building an index; `ReadingSession.current` indexes the whole-book scope directly.
- Tests: what the faster comparison still refuses (changed text, `2.0` for `2`, `true` for `1`, tuple for list, number key, extra field, lone surrogate) and the approved int-subclass case; both lookups against the old full scans on IDs, retired IDs, prefixes, unknown IDs and two scopes.
- `docs/CORE.md` (§6 Decision), `CHANGELOG.md`.

### Tests performed
- `scripts/reader_timings.py --corpus local-corpus --repeats 5`, medians in ms; before = after #16:

| Operation | Before | After |
| --- | ---: | ---: |
| Section next / previous | 683 / ~700 | 467 / 495 |
| Search-result open | 615 | 446 |
| History back | 597 | 415 |
| Startup to first view | 670 | 515 |
| Footnote-heavy view build | 637 | 484 |
| Search | 172 | 124 |

- `.venv/bin/python -B scripts/check_docs.py` — OK; `.venv/bin/python -B -m unittest discover -s tests` — 1604 tests, OK (11 skipped, 4 expected failures).

### Outstanding issues
- A changed in-memory value that is an `int` or `float` subclass of equal value is no longer refused (approved).
- A refusal of a lone surrogate in memory now reports `snapshot_modified` instead of `invalid_utf8`; both refuse.
- Remaining per-move cost is spread thin: nine file-fingerprint checks (kept on every call), view building and the SQLite save.

### Decisions requiring approval
- None open. The comparison edge case was approved by the maintainer on 19 October and recorded in CORE §6.

## Formula review sheet — 18 October 2026

**Task:** Codex: Formula review sheet, assigned directly by the maintainer in the Codex session; recorded in [CURRENT_TASK at c7e0181](https://github.com/dialectmaterial/SOL/blob/c7e01819a51f3c6650def3e2f36e1c695154db1b/docs/coordination/CURRENT_TASK.md#codex-formula-review-sheet).
**Branch / PR:** `codex/formula-review-sheet` · [PR #20](https://github.com/dialectmaterial/SOL/pull/20), opened with `gh pr create --base main`. Status: `In review`.
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
