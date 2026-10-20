# SOL ESSENCE — Computational Inquiry and Reproducible Experiments

**Status:** implemented foundation and bounded research roadmap, 17 October 2026; interface and encyclopedia scope revised 20 October 2026 (supporting research: [ESSENCE interface brief](coordination/proposals/ESSENCE_INTERFACE_BRIEF_2026-10-18.pdf)).
**Repository baseline:** `dialectmaterial/SOL` `main` at `1d200e4fcbff1ca69f48b5dc96c55765f215f303`.  
**Companions:** [Architecture](ARCHITECTURE.md) · [BEING](BEING.md) · [CORE](CORE.md).

## 1. Purpose

ESSENCE investigates patterns, distinctions and relations in the present *Science of Logic* corpus, using established statistical, linguistic, and machine-learning tools. It must form **one reversible inquiry with BEING** rather than become a separate statistics application. The object is identifiable source text; the user chooses a question/method; the result can be checked and traced back to the text.

**Guiding rule:** reuse mature software (Python scientific stack, spaCy/Stanza, scikit-learn, PyTorch, model libraries, TensorFlow Projector, command-line tools or R when justified) through stable inputs/outputs. Write SOL-specific adapters for provenance, state, reproducibility and return-to-reading. Do not reimplement algorithms simply to place the SOL name on them. Never make CORE load a model or runtime merely to inspect a book.

**Decision (maintainer, 18 October 2026): ESSENCE orchestrates experiments; it is not an ML framework.** Simple, auditable transformations (tokenization, counts, sentence segmentation) may run in ESSENCE itself. Heavier methods run through task interfaces and adapters to existing libraries or models (spaCy, scikit-learn, PyTorch, Hugging Face, remote APIs), never as reimplementations. The encyclopedia is a modest table of contents of methods, with short attributed Wikipedia excerpts and further links ([§7](#7-methods-encyclopedia)). The immediate goal is much narrower: a reversible interface between reading in BEING and investigation in ESSENCE ([§4](#4-interaction-model-and-inquiry-contract)).

The relation between Hegel's explicit argument and the output of an algorithm is always **a research question**. Model similarity and a visual cluster are not equivalent to the logical movement of a concept. Preserve the boundary between measurement, statistical inference, interpretive hypothesis and argued philosophical necessity.

## 2. What exists now

ESSENCE is not currently a complete model environment. The inspected code contains:

- `sol.essence.prose.export_prose` and `sol analyze prose --json`: a **verified, Hegel-specific** prose-only analysis view over the current corpus.
- `sol analyze term WORD`: a reproducible lexical-distribution experiment with reference-bound source matches; `sol analyze check FILE` checks its result against a current corpus generation.
- `sol analyze sentences [--within PATH]`: the existing v1 corpus sentence-length study (run from the reader with `S` until 19 October, when the maintainer removed that key). `sol analyze sentences --file PATH [--span START END]` and the provider API add v2 studies over UTF-8 files or independently scoped CORE inputs; `sol analyze check FILE --input-file PATH` verifies file studies against an explicit local source.
- The optional Textual interface and the word engine's CORE/file counts, comparison measures and CSV/TSV export described in §4–§5. The interface also runs the sentence-length study through the provider API (19 October).
- `sol.core` public snapshot/reference APIs, including source/edition/generation binding and batch captures; these are usable without opening BEING.
- A narrow optional `sol-kitty` + Zsh handoff for a source passage, with an explicit proposed return to BEING. The handoff carries **references**, not an ML result database or unrestricted authority to save notes.
- A bundled, offline methods encyclopedia on screen `1`, with nine entries and individually attributed Wikipedia excerpts ([§7](#7-methods-encyclopedia)).
- Checkout-only reading/rendering research, not an installed ESSENCE model suite.

**Not implemented/verified:** a general experiment picker beyond the word experiment; parameter dashboard; GPU/model registry; task/capability registry and adapters; file providers for the older term/prose and segmentation-review workflows; syntactic research panel; UltraBERT embedding pipeline; TensorFlow Projector launch as a SOL command; durable research context/experiment history. Sustained human acceptance of the reader and investigation interface remains open. Do not describe these as shipping features until code and tests verify them.

### Existing commands

```sh
sol analyze prose
sol analyze prose --json > prose.sol-analysis.json
sol analyze term ground
sol analyze term ground --doctrine essence --limit 5
sol analyze term ground --json > ground.sol-analysis.json
sol analyze check ground.sol-analysis.json
sol analyze sentences --within /BEING/i-determinateness-quality
sol analyze sentences --json > quality.sol-analysis.json
sol analyze sentences --file /absolute/path/to/text.txt --span 0 500 --json > sentences.sol-analysis.json
sol analyze check sentences.sol-analysis.json --input-file /absolute/path/to/text.txt
sol reference capture RECORD_UUID --corpus local-corpus | sol reference check --corpus local-corpus
```

The first `prose` command summarizes eligible records. The JSON export is for consumption by scripts. The lexical study measures exact normalized token occurrences and can break results down by the three doctrines, but a word occurrence does not prove concept identity. `check` verifies term, word-frequency and sentence studies by recomputation, not arbitrary generated model outputs or `prose` exports. File analysis through the Python API or `python -m sol.essence.cli` needs no CORE import or configured corpus; the installed `sol` entry point still loads BEING's command dispatcher.

## 3. Proper model inputs: projections, not destructive cleaning

**Current version-1 prose projection** (see the [archived input policy](legacy/PROSE_INPUTS.md)) selects records that are Hegel-attributed `main_text`, with types `paragraph`, `quotation` or `list_item`, excluding pending-review and explicitly generated text. Canonical section/headings, note callouts, image labels, formulas, editorial material and indexes are **not** silently concatenated into feature strings. Heading ancestry, locations, source pages, attribution, source digests, record type and corpus generation are retained as separate metadata. Words such as *Being*, *Remark*, or *Ground* that occur in **actual prose** are not blacklisted. Headings are removed by structural selection, not a word-level blacklist.

Use precisely `passages[].text` as the input to a prose embedding experiment; preserve `passages[].id` as the map back to the corpus. Example:

```python
import json
with open('prose.sol-analysis.json', encoding='utf-8') as f:
    view = json.load(f)
texts = [p['text'] for p in view['passages']]
ids   = [p['id'] for p in view['passages']]
meta  = [p['metadata'] for p in view['passages']]
```

**Decision:** this is one useful projection, **not** the cleaned text for every method. Maintain a typed, versioned preprocessing policy **per experiment**. Sentence length needs sentence segmentation and punctuation. Syntax needs clause/token/POS/dependency information and a declared pipeline. Some rhetorical studies need heading, annotation, note or formula context. Embedding requires explicit passage granularity and truncation/chunking policies. For every experiment, record why features were included or excluded; preserve the unmodified underlying canonical text and make derivations reproducible.

In particular, avoid these errors:

1. Treating a heading in the index as prose because it contains meaningful philosophical vocabulary.
2. Removing legitimate prose words because the same strings occur as heading titles.
3. Vectorizing JSON metadata alongside text, introducing obvious category leakage.
4. Implicitly treating translators' sentences as Hegel's original German syntax.
5. Silently concatenating paragraphs, ignoring section boundaries, or truncating input beyond model limits.
6. Calling distances or embeddings ontological relationships without an independent argument.

## 4. Interaction model and inquiry contract

**Decisions (maintainer, 18 October 2026)**, from the [ESSENCE interface brief](coordination/proposals/ESSENCE_INTERFACE_BRIEF_2026-10-18.pdf). They direct future work; none is implemented yet.

1. **Hybrid surfaces.** Neovim remains the persistent BEING reader. ESSENCE gets its own interactive application, built with **Textual**, launched only when ESSENCE is requested. **Textual is an optional extra** (`sol-organizes-logic[essence]`, decided 18 October 2026): the reader installs and runs without it, and ESSENCE explains how to install it when it is missing.
2. **On-demand lifecycle.** No Textual process exists while the reader is idle. Entering ESSENCE starts it in a Neovim terminal buffer; leaving ESSENCE saves the investigation state and ends the process. ESSENCE remains an ordinary application inside a terminal Neovim provides, not a terminal emulator.
3. **Two presentations, one investigation.** ESSENCE appears either **beside** BEING (one split, the reader still visible) or **fullscreen**. Switching between them reuses the same process and investigation; it does not restart anything. Together with plain reading there are three visible states.
4. **Outer versus inner layout.** Neovim owns the outer geometry (split or fullscreen); Textual owns the layout inside its terminal buffer. Textual screens are logical views *within* ESSENCE (encyclopedia, method, experiment, results), not the two outer presentations.
5. **Interface before analytical breadth.** First prove launch, both presentations, focus, state preservation, close and return; then add the smallest real operation, a word tokenizer and frequency table ([§5](#5-prioritized-experiments)).
6. **One capability, interactive and headless.** Every analytical operation the interface offers also runs from the CLI with the same inputs and the same artifact, so results can be scripted, checked and reproduced without the UI. The read-only encyclopedia browser has no CLI.
7. **CORE is optional for ESSENCE.** ESSENCE accepts ordinary text files; CORE is the provider that adds verified identity, provenance and source return when present. The path is staged in [Architecture §2](ARCHITECTURE.md#2-component-responsibilities); today every study requires CORE.

**Implemented (18 October 2026), stage 1 shell:** `sol.essence.tui` is a Textual application with four screens (Encyclopedia, Methods, Experiment, Results) initially holding placeholder text; Encyclopedia now browses the bundled catalog (§7), and Methods (20 October) browses the bundled methods catalog (`sol/essence/methods.json`): for each runnable study its inputs, settings, output, limits and command line, with its encyclopedia entry named; the reader's origin is shown at the top. `1`–`4` switch screens, `q` or Ctrl-Q leaves; the command palette is off. Leaving saves only the open screen and the origin record, owner-only, under `$XDG_STATE_HOME/sol/essence/` for workspace sessions (temporary `-n` sessions save nothing); the next opening returns to that screen. Opening it imports no model. Measured on this machine inside Neovim's terminal: start-up about 110 ms; a split-to-fullscreen change reflows without a restart; Escape, Alt-Left/Right, Alt+letters, Ctrl-S/N, Tab, function keys and arrows arrive intact through terminal mode. Textual reads Escape-then-letter as Alt+letter, binds Ctrl-Q to quit and Ctrl-P to its palette, so ESSENCE avoids those for other purposes. Reader-side behaviour: [BEING §6](BEING.md#6-being--essence-without-terminal-dogma).

**Implemented (18 October 2026), stage 2 interface side:** the Experiment screen chooses a **target** (this passage, its section, the whole book, or a UTF-8 text file) and an optional **reference** (its section, the whole book, or a text file) and runs the stage 2 word-frequency engine (`sol.essence.words.analyze_words`) in a background worker. Results shows, for each side, tokens, distinct words, inputs, provider and scope, the engine's warnings (unequal denominators, different projections), and a table of the most frequent 2,000 words with counts and rates per 10,000 tokens; an undefined rate is shown as such. Workspace sessions save the artifact owner-only as `~/.local/share/sol/studies/words-*.sol-analysis.json` for `sol analyze check`; temporary sessions save nothing. Choosing only text files needs no CORE corpus. Opening a word's passage in the reader is stage 3. On the real book through this interface code: a passage counts in about 0.5 s, a section against the whole book in about 1.4 s.

**Implemented (18 October 2026), stage 3 interface side:** with a reference, a count calls `sol.essence.comparison.compare_words` once (it runs the stage 2 study and adds the measures), so the interface computes no measure itself. Results then adds **Difference** (per 10,000 tokens) and **Log₂ ratio** columns; an undefined measure says why in the engine's terms (*absent in target*, *absent in reference*, *empty target*, *empty reference*), and the summary states both formulas, that there is no smoothing, and the engine's warnings, including that the measures are descriptive only. Below the table, **Sources** lists where the highlighted word occurs: one row per occurrence, numbered within its passage or file (*2 of 5*), with the words around it (about 40 characters each side, the word in bold) and the passage's heading and printed page (19–20 October). The study records only each input's first occurrence; the others are found again at display time with the same tokenizer in the verified text and are never saved. Where they cannot be confirmed (the text changed, or masked tokens were left out of the count), only the first is listed, with the input's count. At most 1,000 rows are listed per word, and the label says when fewer than all occurrences are shown. The context is read from the loaded book or the chosen file for display only and is shown only if that text still has the digest the count recorded; otherwise the row says the text has changed. After a count the word table has the focus: arrows choose a word, Enter moves to its sources, Escape back; switching screens with `1`–`4` starts on that screen's first control. Enter on a corpus row opens that occurrence in the reader ([BEING §6](BEING.md#6-being--essence-without-terminal-dogma)); text-file rows are listed but cannot open. **Export CSV / Export TSV** call `export_word_comparison`, which checks the sources against the study again first, and write `~/.local/share/sol/studies/words-*.csv|tsv` owner-only, never overwriting; temporary sessions write nothing, and a count without a reference has no table to export. **Cancel** abandons a running count: the engine cannot be interrupted, so it finishes in the background and its result is discarded and not saved. On the real book (this machine): a section against the whole book about 2.8 s (the comparison adds about 0.5 s to the count), an export about 3.2 s.

**Implemented (19 October 2026), the sentence study in the interface:** the Experiment screen first chooses a study, **Word frequencies** or **Sentence lengths**; sentence lengths take the same targets (this passage, its section, the whole book, a text file) and no reference. They run `sol.essence.sentences.analyze_sentences` with the word engine's providers, so the result is the `sol.sentence-study` v2 artifact of [§5](#5-prioritized-experiments), saved owner-only as `~/.local/share/sol/studies/sentences-*.sol-analysis.json` in workspace sessions (nothing in temporary ones) and checked with `sol analyze check`. Results then shows the totals, the distribution of words per sentence as bars, the means by place in the paragraph, what was left out, and that the study describes the translation's sentences under `punctuation-rules-v1`; the table lists the twelve longest sentences with their length, how they begin and their heading and page. Beginnings, headings and pages are read for display and never saved. Enter opens a sentence at its first character in the reader through `essence_source`, and Alt-Left returns; a text file's sentences cannot open there. This replaces the reader's former `S`. On the real book: a chapter of 137 passages (624 sentences) measures in about 1 s; the longest sentence opened at its first letter.

**Proposed launch and return requirements:**

| Event | Required behaviour |
|---|---|
| Open ESSENCE from BEING | Capture the reader's reference, cursor and any selection; start Textual asynchronously; load no model weights to open the UI. |
| Switch presentation | Same process, same investigation; recompute outer and inner layout. |
| Move focus | A visible focus indicator; keys act on the focused surface; Escape and quitting are never ambiguous. |
| Leave ESSENCE | Save the investigation state, end only the Textual process, close its buffer, restore the BEING cursor. |
| Crash or invalid result | The reader stays usable; logs survive; the error is visible; nothing claims completion. |
| Long model job | An explicit policy: cancelled on exit, or run by a separate runner that does not depend on the UI process. |

**Target and reference.** An analysis takes two independent choices: an **analysis target** and an optional **reference corpus** to compare it with. Scopes range from a selection, passage or section to a chapter or the book; author oeuvres, bibliographies and thematic collections are future scopes ([CORE §1](CORE.md#1-why-core-exists)). The first milestone supports only scopes the present corpus offers. Comparisons show absolute counts, normalized rates and their denominators, and warn that raw counts across unequal scopes are not comparable.

**Proposed investigation record** (a conceptual schema, *not* a change to CORE's version-1 reference protocol; implementing it needs a separately approved, versioned format):

```text
origin:      provider (core | file); corpus, edition and generation, or file digest
scope:       record UUIDs and codepoint ranges, or file spans
comparison:  target scope and optional reference scope
question:    researcher-entered text, distinct from canonical text
input:       named, versioned projection, ordered IDs, digest per input row
method:      task, tokenizer/algorithm/model, exact versions
parameters:  projection, normalization, seed, thresholds, device
execution:   runner, start/end time, outcome
result:      artifact digest, warnings, source-linked rows
return_to:   reader reference, cursor and selection, prior focus and presentation
```

A result should distinguish **reproducing the exact experiment generation** (strict full-corpus snapshot agreement) from **resolving an unchanged passage later** (a possible weaker check, not yet implemented). CORE v1 currently takes the strict position; do not relax that protocol or overwrite stale artifacts without an explicit, separately versioned policy. The result artifact has **no authority** to edit canonical text or store author assertions in a personal workspace. Acceptance of a suggested relation should require deliberate scholarly authorship. Browser visualization (for example the TensorFlow Embedding Projector) remains a legitimate output alongside the Textual interface.

**Open decisions** (each needs its own review before implementation):

- ~~the key that opens ESSENCE~~ **decided 18 October 2026:** `E` in the reader (unmapped until now); `S` stayed the quick sentence study until the maintainer removed it on 19 October 2026 ([BEING §6](BEING.md#6-being--essence-without-terminal-dogma));
- the default split side, minimum widths and focus transitions;
- the persistence format of an investigation, and what happens to explicitly started background jobs on exit;
- the provider/adapter API, its versioning, and when (if ever) to publish separate distributions;
- the tokenizer and scopes of the first milestone (default: the term study's tokenizer; scopes the corpus offers, plus plain-text files);
- ~~the encyclopedia's source format and initial coverage~~ **decided 20 October 2026:** small bundled JSON table of contents; see §7. Proposal §9 is deferred.

**Open alternative (raised by the maintainer, 18 October 2026): Textual as the outer host.** Instead of Neovim hosting ESSENCE, a single Textual application could host both BEING and ESSENCE as modules, with Neovim embedded inside it for reading. *For:* Textual's widgets suit panels (footnotes, notes, search, results) better than hand-built Lua popups, and one process simplifies shared state. *Against:* Textual has no built-in terminal, so Neovim would run either in an experimental third-party terminal widget or through a Neovim UI client (`nvim --embed`, redrawing its grid and forwarding every key); reading would pass through a second rendering layer (italics, Unicode widths, latency, Ctrl/Alt keys at risk), split/fullscreen would have to be rebuilt, and a stable reader would be migrated again. Porting the reader to Textual *without* Neovim is a further variant that would give up the present motions and exact selection. **Not adopted:** the decision above stands. Keep the reader's logic in Python (`ReaderActions`) and ESSENCE's state independent of any interface, so the host can change later by replacing presentation. **Proposed test before reconsidering:** a one-session spike running the real reader inside Textual via `nvim --embed`, comparing key handling, italics and latency with Alacritty; and the evidence of the reading trial (if Neovim reads well, the case weakens; if it reads badly, revisit the host rather than nest it).

## 5. Prioritized experiments

**Decision (maintainer, 18 October 2026): a staged plan that does not build everything at once.** Each stage has an exit criterion; later stages wait for earlier ones.

| Stage | Deliverable | Exit criterion |
|---|---|---|
| 0. Documentation | These decisions reconciled in the four authorities | Docs check passes; no application code changed; open decisions listed |
| 1. Interface shell | Textual mock (Encyclopedia / Methods / Experiment / Results); entry from and return to Neovim; split and fullscreen | Launches on demand, resizes without restart, restores the reader position, keyboard focus is robust |
| 2. Minimal experiment | Word tokenizer and frequency table over a selectable target; source-linked counts; plain-text file input | Same output from CLI and TUI; works on a plain-text file without CORE |
| 3. Comparison | Reference-corpus selector; normalized lexical comparison; navigation and export | Explicit denominators; no false comparability; stale generations refused |
| 4. Encyclopedia (implemented, 20 October) | Bundled methods table of contents; short attributed Wikipedia excerpts and further links | Browsable offline, without CORE or model downloads |
| 5. Model adapters | Capability-driven registry; optional runtimes; comparison experiments (including Experiment B below) | Model versions, input limits, policies and reproducibility documented and tested |

**The first new experiment stays elementary:** a deterministic, documented word tokenizer, with token count, type count and a frequency table for the selected scope. Its purpose is to test the whole research loop, not to settle what a word is. The term study's existing tokenizer (`sol.essence.terms`) is the natural candidate: it takes runs of letters with combining marks and internal apostrophes, applies NFC and case folding, excludes digits and punctuation, and splits hyphenated compounds; the final choice is open ([§4](#4-interaction-model-and-inquiry-contract)). Model-specific subword tokenization and morphology come later as **distinct analyses**, never as aliases of this one.

The shipped sentence study (Experiment A, below) is not superseded; it remains the first complete reader-to-ESSENCE round trip and moves into the new interface once stage 1 exists.

### Stage 2 engine — word frequencies (implemented, 18 October)

The headless engine is available independently of the interface shell. The
tokenizer was moved unchanged to `sol.essence.tokenization.word_tokens`; the
term study still uses that exact function and its v1 output is unchanged. It
yields normalized words and original, half-open Python codepoint offsets:
letter runs with combining marks and internal straight/curly apostrophes,
NFC then case folding then curly-to-straight apostrophes; punctuation and
digits excluded, hyphens split. The artifact records the runtime Unicode
version. These are ordinary word tokens, not morphological or model subwords.

The interface-facing function is
`sol.essence.words.analyze_words(target, *, reference=None) -> dict`.
Each argument is a `CoreProvider(snapshot, scope=None)` or
`FileProvider(path, scope=None)` from `sol.essence.word_inputs` (also exported
from `sol.essence`). Providers can differ; no Textual import is involved.

- CORE consumes a verified `CorpusSnapshot` with permanent identity. Default
  scope is `{"kind":"corpus"}`; alternatives are
  `{"kind":"within","path":"/BEING/..."}`,
  `{"kind":"passages","ids":["FULL_UUID",...]}`, or
  `{"kind":"span","id":"FULL_UUID","start":0,"end":20}`.
  IDs must be exact and distinct; inputs retain canonical order. Reader paths
  match whole path components. The existing term-study projection selects
  Hegel main-text paragraphs, quotations and list items in the three doctrines,
  excludes generated/pending-review records, and masks converter facsimile
  labels. Exclusion reasons and masked token counts are explicit.
- File input is a caller-selected regular UTF-8 file, with default scope
  `{"kind":"file"}` or `{"kind":"span","start":0,"end":20}`.
  It requires no CORE imports, configuration or corpus. Bytes, line endings
  and BOM are preserved for hashing; offsets address decoded text. Symlinks,
  special files, invalid UTF-8 and inputs over 64 MiB are refused.
- A span counts only tokens wholly contained in its half-open bounds; cutting
  a word does not invent a partial token. An empty span/input is valid. The
  reference is independently selected and optional; both sides use the same
  tokenizer. Different projections/source bindings and unequal token totals
  produce warnings. Rates describe these inputs, without a significance or
  conceptual-similarity claim.

`sol.word-frequencies` v1 is a separate, deterministic result artifact, not a
persisted investigation record or a change to CORE's protocol. Its top-level
fields are `protocol`, `version`, `method`, `target`, optional `reference`
(`null` when absent), `frequencies` and `warnings`. Each side contains its
provider, binding, scope, text-free `inputs`, `summary` (`token_count`,
`type_count`, `input_count`) and `exclusions`. CORE bindings retain corpus,
edition/source digests and full manifest/index generation; file bindings retain
the full byte digest and byte count, never a path to open automatically.

The frequency table is the union vocabulary, ordered by descending target
count then normalized word. Every row has `word`, `target` and `reference`.
Each non-null cell contains `count`, `denominator` (all included tokens on
that side), `rate_per_10000_tokens` (six decimal places) and `locations`.
Locations are `[input_index, count_in_input, first_start, first_end]` tuples
encoded as JSON arrays. CORE input rows provide exact IDs, content/text digests,
reader paths, pages, attribution and selected spans for source return; file
rows provide text digests and spans. No passage text, contexts or token
sequences are stored; normalized vocabulary is intrinsic to the table. Keep
these artifacts private and outside Git.

```sh
sol analyze words --corpus /absolute/path/to/corpus --within /BEING --compare
sol analyze words --corpus /absolute/path/to/corpus --passage FULL_UUID --span 0 20
sol analyze words --file /private/target.txt --reference-file /private/reference.txt
sol analyze words --file /private/target.txt --span 0 20 --compare --json > /private/words.json
sol analyze check /private/words.json --input-file /private/target.txt
```

`--compare` uses the whole target source as reference. `--reference-within`,
repeatable `--reference-passage`, `--reference-span`, `--reference-corpus`
and `--reference-provider core|file` select an independent reference; target
`--provider` defaults to `file` with `--file`/`--input-file`, otherwise `core`.
Use `--json` for the complete table and source locations. Human output shows
absolute counts, denominators and rates; zero-token rates are `null` in JSON
and `n/a` in text, including the missing side of a union-vocabulary row.

`encode_word_result`/`decode_word_result` validate bounded (16 MiB), strict
UTF-8 JSON with no duplicate keys, nonfinite numbers, unknown fields or method
versions. `check_word_result(target, result, *, reference=None)` recomputes
with caller-supplied providers and matching scopes. `sol analyze check`
reuses validated artifact scopes, but file paths must be supplied explicitly;
CORE sources come from `--corpus`/discovery and `--reference-corpus`. It emits
a verification receipt, not another study. Any changed corpus generation or
file bytes, including unselected material, invalidate the result; input
changes during execution are refused too. Rechecking does not overwrite the
artifact or change canonical/workspace data. Interface integration and its
CLI/TUI equivalence trial remain separate work.

### Stage 3 engine — comparison measures and export (implemented, 19 October)

`sol.essence.comparison.compare_words(target, *, reference, result=None)`
uses the same CORE/file providers and scopes as `analyze_words`. It analyzes
fresh inputs, or strictly recomputes the supplied **existing v1** `result`
before deriving measurements. Its returned view has `method`, the unchanged
v1 `study`, `study_sha256`, `rows` and `warnings`. Each row contains `word`,
the original `target`/`reference` frequency cells, two measurements and their
statuses. This view is not a new saved artifact: keep the original
`sol.word-frequencies` v1 JSON, which still checks and encodes unchanged.

The deliberately small method, `word-rate-comparison-v1`, uses occurrence
counts `a`, `b` and complete token denominators `Nt`, `Nr`:

- **Rate difference per 10,000 tokens:** `10000 * (a/Nt - b/Nr)`.
  Positive means a higher target rate; zero means equal rates at the reported
  precision. It is computed from counts before rounding, rather than by
  subtracting the rounded rates in the study.
- **Log₂ rate ratio:** `log2((a*Nr)/(b*Nt))`, defined only with positive counts
  and denominators. `+1` means twice the reference rate, `-1` half. There is
  **no smoothing or pseudocount**: a missing word yields `null` and
  `zero_target_count` or `zero_reference_count`, not infinity or an invented
  small count. The rate difference remains defined in those cases.

Both measures round to six decimal places. A zero token denominator makes
both undefined, with `empty_target` or `empty_reference`; two empty scopes
have no vocabulary rows. Numeric fields are `rate_difference_per_10000_tokens`
and `log2_rate_ratio`; status fields are `rate_difference_status` and
`log2_ratio_status` (`defined` for finite reported measurements). Rows retain
the study's descending-target-count/word order, including reference-only words.
These are **descriptive lexical effect sizes**, with no significance test,
confidence estimate or conceptual-similarity claim. Unequal sizes, overlapping
scopes and small counts do not establish a population inference. Existing
projection/edition/unequal-denominator warnings are retained. No keyness
statistic is implemented.

`export_word_comparison(target, *, reference, result=None, format="csv")`
repeats the same source verification and returns CSV or TSV text without
writing files. From the CLI, export a saved target/reference study with
explicit sources (replace these private paths):

```sh
sol analyze words --file /private/target.txt --reference-file /private/reference.txt --json > /private/study.json
sol analyze words-export /private/study.json --input-file /private/target.txt --reference-file /private/reference.txt --format csv > /private/comparison.csv
sol analyze words-export /private/study.json --input-file /private/target.txt --reference-file /private/reference.txt --format tsv > /private/comparison.tsv
sol analyze words-export /private/core-study.json --corpus /private/corpus --format csv
```

CORE scopes are recovered from the validated artifact, just as for `check`;
an independent CORE reference uses `--reference-corpus`. File sources are
never opened from artifact data. A reference is required. Changed source
bytes/generations, tampered studies and unsupported versions refuse before
any table is emitted. CSV/TSV are derived tables, not accepted by `check` and
never used to update the corpus; verify their retained original study instead.

Both formats have one header and a row per union-vocabulary word, Unicode
spellings, absolute counts, explicit per-side token denominators, rates,
measurements and statuses. Undefined numeric cells are empty; their status
explains why. Additional columns retain the method ID, the canonical v1
encoding's SHA-256 (without its final newline), provider names, full source
bindings, scope digests and warnings. Binding/warning cells are quoted JSON;
scope details remain in the original study. No passage text, contexts,
source paths, headings or token sequences are exported. Empty unions produce
a header-only table; retain the study for empty-scope totals and provenance.
Keep the study and exports private and outside Git. The engine imports no
Textual; interface controls and source navigation remain separate work.

### Experiment A — syntax and positionality (highest priority)

**Research question:** how do sentence lengths and selected grammatical constructions vary across paragraphs and across positions within a passage or chapter of Hegel's *Science of Logic* in the current **English translation**?

Design a minimal, inspectable analysis rather than jumping straight to a large model:

1. Select the current passage, a bounded paragraph window, or an explicit chapter from BEING; send ordered UUIDs and exact source scope.
2. Extract eligible prose with provenance. Handle paragraph and sentence boundaries explicitly; choose/document tokenizer and sentence segmenter; assess quotation/semicolon/abbreviation behavior on Hegel examples.
3. Compute sentence length in word tokens (and optionally characters), distributions by position within a paragraph/chapter, and a deliberately small set of POS/dependency statistics if a tagged model is available.
4. Report counts, denominators, missing data, pipeline confidence and unusual segmentation, not only a figure.
5. Present an inspectable table/plot with every observation linked to the source paragraph; selecting a record navigates to it in BEING, with a way to resume the original reading context.
6. Save versioned inputs/method/output. Validate that a re-run on the same source and method is reproducible within the stated determinism limits.

A sentence-length comparison can be deterministic, cheap, and independently validated against a hand-checked sample.

**Implemented (17 October): the sentence-length half.** `sol.essence.sentences` selects eligible Hegel main text exactly as the term study does (pending-review records are excluded and counted), masks converter facsimile labels, and segments with declared rules (`punctuation-rules-v1`): a sentence ends at `.`, `!`, `?` or an ellipsis (with closing quotes/brackets) followed by whitespace and a capital, digit, opening quote/bracket or dash; never inside a bracket opened within the sentence (citations such as *(Princ. Math. Phil. Natu. Lib. II, …)*), after a listed abbreviation (single letters only in lower case, so a logical term like *S-U-P.* still ends a sentence) or within a chain of initials; a newline always ends one. Length is counted in the term study's word tokens. The artifact (`sol.sentence-study` v1) stores record IDs, digests, codepoint offsets and token counts — **no book text** — plus the distribution, percentiles, means by place in the paragraph (first/middle/last/only) and the longest sentences; `check` recomputes it exactly against the current generation. Rules were tuned on the local corpus: of 9,127 sentences (median 31 words), the three longest (150, 148, 146 words) were read and are genuine Hegel sentences, a random sample of boundaries was correct, and the 40 held-back periods followed by capitals were almost all citation abbreviations; one known miss is a full sentence inside a parenthesis opened mid-sentence. **Not yet done:** a formal hand-checked sample with a reported error rate, part-of-speech/dependency statistics, and sentence-level scopes smaller than a loaded section from the reader. POS tagging and parsing will be probabilistic/error-prone, so present them as **model annotations**, not source facts. The linguistic conclusions describe the chosen translator's text; contrast with Hegel's German only if a distinct German source is actually available and audited in a future research cycle.

#### Sentence providers and file input — implemented 19 October 2026

`sol.essence.analyze_sentences(provider, *, origin=None)` accepts the **same**
`CoreProvider(snapshot, scope=None)` and `FileProvider(path, scope=None)` as
the word engine. CORE scopes are `corpus`, `within` a reader path, exact
`passages` IDs, or a `span` with one exact `id`, `start` and `end`. Files use
`file` or a `span` with `start` and `end`. Set scope on the provider; a separate
`scope=` argument remains available only for the legacy snapshot API.

The original complete text is segmented with unchanged `punctuation-rules-v1`
**before** the half-open codepoint span is applied. Only complete sentences
contained in the span are measured. A sentence cut at either boundary is
excluded, with the count in `exclusions.outside_span`; no fragment becomes a
new sentence. File bytes decode as UTF-8 without rewriting CRLF, Unicode or a
BOM. The existing word tokenizer measures lengths. A whole file is one input
row: `by_position` describes the retained sentence sequence in that row,
not inferred paragraphs. CORE rows retain their passage boundaries and the
word engine's attribution/type/review filters and facsimile policy. Empty
inputs yield zero sentences and null means/percentiles.

Explicit providers produce **`sol.sentence-study` v2**, with the separately
named method `sentence-length-distribution-providers-v1`. Its `input` records
provider, binding, scope and input rows (digests, spans, sentence counts and,
for CORE, source identities/provenance); `sentences` rows are
`[input_index, start, end, token_count]`. Summaries, histogram, positional
statistics and longest-row indexes use the same calculations as v1. No input
text or local file path is stored. Files bind the complete original byte
digest and byte length; even a change outside a selected span is stale. CORE
retains strict corpus/edition/generation checks. A file has no CORE source
return guarantee or CORE reference anchor.

`encode_sentence_result`, `decode_sentence_result` and
`check_sentence_result(provider, result)` handle v2; a checker needs the
caller-selected provider **with the recorded scope**, never a path from the
artifact. The CLI reconstructs the recorded scope after decoding, but file
checks always require `--input-file PATH`. V2 is bounded to 16 MiB, allowing
whole-book provenance, and files to the shared 64 MiB input bound. V1 keeps
its 1 MiB bound and original encoding/method; bare-snapshot calls, existing
artifacts and ordinary corpus CLI output remain v1 (as did the reader's `S` until its removal on 19 October).

```sh
sol analyze sentences --file /absolute/path/to/text.txt
sol analyze sentences --file /absolute/path/to/text.txt --span 10 500 --json > sentences.sol-analysis.json
sol analyze check sentences.sol-analysis.json --input-file /absolute/path/to/text.txt
sol analyze sentences --corpus local-corpus --passage RECORD_UUID --span 10 500 --json
```

```python
from sol.essence import FileProvider, analyze_sentences, check_sentence_result
provider = FileProvider("/absolute/path/to/text.txt", {"kind": "span", "start": 10, "end": 500})
result = analyze_sentences(provider)
checked = check_sentence_result(provider, result)
```

This adds no model, dependency, corpus/workspace contract or interface control.
The underlying segmenter's known limitations and the need for human boundary
validation remain unchanged.

#### Measuring segmentation error against private marks

**Implemented (18 October): validation tools, with the method unchanged.**
`sol analyze segmentation-sample` prepares a blind local annotation form;
`sol analyze segmentation-check` compares completed marks with the existing
`punctuation-rules-v1`. These are review commands, not a replacement segmenter
or a change to `sol.sentence-study` v1 or CORE. No dependency was added.
**No real-book error rate has been established:** human marking is still required.

The sample uses complete, eligible nonempty passages from each doctrine, with
the existing sentence study's attribution/type/review filters. A declared seed
and SHA-256 ranking of `seed:UUID` select equal counts per doctrine; records
are then presented in canonical order. The form retains source text, IDs,
digests, pages, generation and method, but reveals no predicted boundaries or
counts. This balanced passage sample is a descriptive pilot, not a book-wide
weighted error estimate. It measures `segment` boundaries in exact canonical
`plain_text`, not the accuracy of token counts or subsequent facsimile masking.

**Marking in an ordinary text editor (18 October).** No JSON editing is needed:

1. After approving a size, create an unmarked sample in an existing private
   directory outside Git and outside the corpus. Replace the example paths.

   ```sh
   sol analyze segmentation-sample --corpus /absolute/path/to/local-corpus \
     --per-doctrine 30 --seed 20261018 --output /absolute/private/path/sample.json
   ```

2. Export a blind text form. Keep the original `sample.json` unchanged.

   ```sh
   sol analyze segmentation-export /absolute/private/path/sample.json \
     --corpus /absolute/path/to/local-corpus --output /absolute/private/path/sentences.txt
   ```

3. Open `sentences.txt` in your text editor, using UTF-8, LF line endings and
   **soft wrap**. Inside each `TEXT` block, press Enter after every complete
   sentence, including its punctuation and closing quotes/brackets. Keep every
   original space when possible. If your editor trims whitespace before an added
   sentence break or at a passage end, import restores it from the source.
   Do not delete spaces inside sentences, correct words, change Unicode,
   hard-wrap, auto-indent or edit headings. Turn off those editor features.
   An original source newline is **not** a mark; add another Enter there if it
   really ends a sentence. An unsplit block declares one whole sentence. Visit
   every block; put a reason on its `EXCLUDE: ` line if it is unreviewed or too
   doubtful to adjudicate. Even excluded text must remain intact. Save the file.

4. Import using that same original sample, supply your reviewer label, then score
   the new review. Output files must not already exist.

   ```sh
   sol analyze segmentation-import /absolute/private/path/sample.json \
     /absolute/private/path/sentences.txt --reviewer "Your name" \
     --corpus /absolute/path/to/local-corpus --output /absolute/private/path/review.json
   sol analyze segmentation-check /absolute/private/path/review.json \
     --corpus /absolute/path/to/local-corpus
   ```

For example, this invented text has a retained space at the start of the second
line; Enter was **added**, not substituted for that space:

```text
TEXT
A first invented statement.
 A second one follows.
```

The form shows the original unsplit text and passage IDs/doctrines, never the
segmenter's boundaries or counts. A fingerprint binds it to the complete
original sample. Import allows added LF breaks inside `TEXT`, source whitespace
trimmed at those breaks or passage ends, and reasons on the designated exclusion
lines (`EXCLUDE:` with or without its trailing space). It reconstructs sentence
strings from canonical source slices, not the edited form. An edited word,
missing space inside a sentence, dropped or reordered passage, changed sample or
changed source generation is refused. Existing v1 form headers remain unchanged
for compatibility; their advice to retain spaces is conservative, not a demand
to disable line-end trimming at added sentence breaks.
Text mismatches name the passage, source codepoint (1-based) and form line/column.
No newline is inserted into canonical text: the new JSON stores exact source
slices in the existing `gold_sentences` field, or an explicit `exclude_reason`.
JSON-based marking remains supported for scripts and expert users.

Sample, form and review creation use owner-only files, refuse existing targets
and symlinks, and refuse Git checkouts. Keep raw samples, marked forms and reports
private and outside Git. Keep the corpus unchanged while marking. The example's
size and seed are explicit, not approved defaults. Import is a declaration of
marks, not evidence that each block was read; blank exclusion lines and no added
breaks cannot distinguish an unreviewed passage from a one-sentence passage.
Reviews with no scored passages are refused, and exclusions are reported, not
hidden. Mark the pilot before inspecting predictions and have a second reader
independently check doubtful cases. A reviewer label is attribution, not proof
of human review. To save the text-free score report privately, use
`segmentation-check ... --json > /absolute/private/path/report.json`.

Scoring compares exact **internal sentence-end codepoint offsets**. The final
passage end is obligatory and excluded. A false split is a predicted boundary
absent from the marks; a miss is a marked boundary absent from the prediction.
A shifted boundary counts as both; no fuzzy matching is used. With `TP` matching
boundaries, `FP` false splits and `FN` misses, precision is `TP/(TP+FP)`, recall
is `TP/(TP+FN)`, and F1 is `2TP/(2TP+FP+FN)`. Zero denominators are `null`, not
perfect scores. Reports retain counts, affected-passage counts, per-doctrine
metrics, explicit exclusions and exact error offsets without copying book text.
A successful command means the review was compared, not that a quality target
was met. Retain the private form alongside the report to reproduce it.

Synthetic tests preserve four known limitations as **expected failures**:
a sentence inside a parenthesis opened mid-sentence, an artificial line break
inside a sentence, an abbreviation that also ends a sentence, and a deliberately
lowercase sentence start. The latter three are test challenges, not claims about
their frequency in this edition. They are not silently corrected or grounds
for inferring a real-book error percentage. A later rule change must trigger
review of those expected failures and use a separately approved method version.

**Proposed for maintainer approval:** begin with 90 complete passages (30 per
doctrine), seed `20261018`, and report the actual number of internal gold
boundaries. Seek at least 300 marked internal boundaries before treating the
quality targets as useful evidence; if necessary, approve expansion by ten
passages per doctrine using the same ranking. Proposed pilot targets are at
least 98% precision and recall overall, and at least 95% of both in each
doctrine. These are discussion targets, not statistical population guarantees
or an acceptance rule enabled in code. Adjudicate disagreements and report
exclusions before deciding whether to retain the rules or compare an established
external segmenter on the same held-out sample. No method/dependency change or
real-book acceptance is approved by this validation step.

### Experiment B — embeddings and TensorFlow Embedding Projector

**Research question:** what textual neighborhoods does a selected *embedding method* place near a given passage, and how stable are these neighborhoods under model, granularity and projection choices?

Build one controlled, reproducible local embedding experiment. Compare model suitability/requirements rather than chasing model releases. **UltraBERT** is a possible candidate discussed in the project, not an adopted or verified local dependency in this baseline. Confirm the exact released checkpoint, intended use, language coverage, embedding extraction method, token/window limits and license **before** integration. A classifier backbone is not automatically an optimal sentence-embedding model; benchmark against a purpose-built sentence-embedding baseline.

For each row preserve: source UUID, text digest, model input length, truncation/chunking, language, provenance, relevant hierarchy labels (as metadata, *not* embedding input), and a stable row order. Compute numeric vectors; check all are same dimensionality, finite, and aligned with metadata. Export separate local TSV files: a numeric vectors TSV (one row per example, same dimension throughout) and a corresponding metadata TSV (one row per vector, with clearly labeled fields). Include UUID and source location in metadata. Support the **TensorFlow Embedding Projector** through local file loading and/or an opt-in launch path. Do not expose private copyrighted text via an external upload without an explicit user decision; evaluate the privacy characteristics of the chosen viewer/mode.

Report nearest neighbors in original embedding space separately from 2-D/3-D PCA, t-SNE or UMAP visualizations. Choice of projection, random seed, perplexity/neighbors and subsampling change visible clusters. Do not claim that Cartesian appearance proves a logical relation, a stable taxonomy or successful classification. If labels derive from Hegel's section headings, isolate them as supervised/evaluation `y`, and split train/test data by meaningful contiguous sections to reduce leakage from adjacent prose.

### Experiments after these two

Only after the workflow is proven: lexical concordances and collocations, full dependency patterns, cross-section retrieval, topic models, supervised classifiers, passage alignment for new audited editions, alternate languages, and user-authored relational hypotheses. Do not implement a model store or experimental UI with dozens of hyperparameter controls before one method works end to end.

## 6. The present lexical experiment as a reference

The shipped term study normalizes Unicode token spellings, counts full-word matches, reports totals and normalized frequencies per 10,000 eligible tokens, and records contributing passage IDs/pages. It filters explicit attributed main-text records and review flags rather than reinterpreting the document tree. Results retain a method identifier, source and generation hashes and can be verified against the same corpus; changing even unrelated canonical material invalidates a strict v1 study check. Zero-token groups have undefined rate, not a manufactured zero. A source match is *lexical evidence*, not the classification of the underlying philosophical concept.

With the optional **existing** Kitty handoff, one can open an ESSENCE Zsh pane from the compatibility reader workflow, execute an analysis, publish a return UUID, and accept the proposed navigation back in BEING. This validates reference passing, **not** a full model-output/parameter/visualization pipeline. Preserve its safety and permissions model while researching a terminal-independent equivalent.

<a id="7-model-history-encyclopedia-and-task-registry-proposed"></a>

## 7. Methods encyclopedia

**Decision (maintainer, 20 October 2026), implemented:** the encyclopedia stays a
modest table of contents. The broader [encyclopedia proposal](coordination/proposals/ESSENCE_ENCYCLOPEDIA_PROPOSAL.md)
remains historical design material; its §9 is deferred. No genealogy graph,
editorial review states, catalog CLI, task registry or model execution is adopted.

The small bundled file `sol/essence/encyclopedia.json` contains nine entries:
word counts, word tokenization, relative frequencies and comparisons, sentence
segmentation and length, lexical distribution and source context, prose
projection, TF-IDF, word vectors, and Transformers. SOL's notes identify the
existing operations (including term counts and segmentation error measurement)
and distinguish reading topics without runnable adapters.

Each entry has one short **verbatim Wikipedia excerpt**, its article title and
URL, and one or two further links. Shared attribution to **Wikipedia
contributors**, the **CC BY-SA 4.0** license and license URL, and the access date
(**20 October 2026**) are stored alongside the entries and displayed for each
one, with a link to the article's contributor history. Excerpts are unchanged;
some are sentence fragments. The quotations retain their CC BY-SA 4.0 license
separately from SOL's code. The SOL-specific notes are outside the quotation.
No Wikipedia images or other media are bundled.

Open **Encyclopedia (`1`)** in ESSENCE. Up/Down selects a method and shows its
entry below; Enter focuses the scrollable detail, Page Down/Up or arrows scroll,
and Escape returns to the list. Tab also moves focus. The layout stacks the
list above details so it works beside the reader. `1`–`4` still switch screens;
`q` or Ctrl-Q leaves. Selection survives screen switches during the session;
only the existing screen/origin state is saved on exit.

The catalog loads with standard-library package resources, including from an
installed wheel outside the checkout. Browsing needs no corpus, model runtime,
network or downloads. External reading links open only on explicit selection.
This is reading material, not an experiment or a claim that the listed models
are installed. Adding an entry means editing the bundled data and checking its
excerpt, attribution, date, links and description of ESSENCE's actual support.

## 8. Developer acceptance and prohibitions

- Read current `sol/essence/`, `sol/core/`, docs/tests, and Git status first. Keep experiments opt-in and separate from ordinary reading/install.
- Make the first syntax experiment run on a verified corpus with exact input rows and a source-return mechanism. Produce a machine-readable artifact and a readable summary.
- Do not silently download models, upload copyrighted text, contact remote APIs, or install GPU frameworks during ordinary reader startup.
- Test malformed/empty input, Unicode, missing paragraphs, flagged prose, pipeline errors, corpus changes, interrupted runs, altered row order, mismatched IDs, nonfinite vectors and unavailable optional dependencies.
- Use a pinned environment/checkpoint and report memory/VRAM and CPU/GPU fallbacks where applicable; no assumed acceleration.
- Keep artifacts outside Git; include a method-specific verifier before treating generated files as reusable evidence.
- Preserve original read position and source-linked result navigation as distinct operations.
- Do not allow model output to create canonical records or philosophical workspace assertions automatically.
- Keep imports lazy: opening the interface or a menu must not import an ML runtime, download a model or allocate a GPU. Discover capabilities from metadata.
- Never let the interface become the owner of selection or analysis state; that state is serializable independently of widgets, with stable source references.

**Manual acceptance for the first interface prototype (stage 1):** start `sol` in an ordinary terminal and confirm no Textual process exists; select a passage and enter ESSENCE, checking the shown source identity and that no model is imported or downloaded; switch fullscreen and split repeatedly, checking one process, an unchanged scope and sane behaviour at narrow widths; return focus to BEING, navigate, reopen ESSENCE with the expected context, then exit and confirm the original source offset is restored; force a launch failure, a UI exception and a job cancellation, and confirm BEING stays usable and the failure is visible; run the same tokenizer headlessly and in the interface on identical input and compare input digests, counts, parameters and output.

**Source lineage:** consolidated from installed `sol.essence` implementation and tests, prose-input policy, term study, reference protocol, handoff, modularity/usage manuals, research discussions and the present 17 October priorities. Archived historical details should remain accessible under `docs/legacy/`.
