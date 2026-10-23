# SOL ESSENCE — Computational Inquiry and Reproducible Experiments

**Status:** implemented foundation and bounded research roadmap, 17 October 2026; interface and encyclopedia scope revised 20 October 2026 (supporting research: [ESSENCE interface brief](coordination/proposals/ESSENCE_INTERFACE_BRIEF_2026-10-18.pdf)); framed by the leading [SPECULATIVE](SPECULATIVE.md) document on 21 October 2026.  
**Companions:** [SPECULATIVE](SPECULATIVE.md) (leading) · [Architecture](ARCHITECTURE.md) · [BEING](BEING.md) · [CORE](CORE.md).  
**Original adoption:** 17 October 2026 at `main` `1d200e4`.

## 1. Purpose

**ESSENCE as a logical division ([SPECULATIVE §4](SPECULATIVE.md#4-initial-repository-hierarchy)).** ESSENCE is responsible for computation, analytic methods, comparison and the Textual analysis interface; the corpus it analyses is requested from CORE. Its first-level divisions are **Essence as Reflection within Itself, Appearance and Actuality**. Placing today's engines, CLI and interface under them is a restructuring task, argued from the text and recorded in the [placement register](ARCHITECTURE.md#9-placement-register).

**The reciprocal inquiry ([SPECULATIVE §2.1](SPECULATIVE.md#21-the-reciprocal-investigation)).** ESSENCE is where computation investigates philosophy, and also where philosophy investigates computation. A word tokenizer segments text into units; it also raises what makes something a unit, where its boundaries come from, what it presupposes and what abstraction loses, and those questions may change the tokenizer or its role. Every method ESSENCE runs is therefore an object of inquiry as well as an instrument, which is why methods carry their stated limits ([Methods](#7-methods-encyclopedia)) and why no result is taken as evidence that computation is adequate to the Idea ([SPECULATIVE §2.3](SPECULATIVE.md#23-adequacy-to-the-conceptand-the-idea)).


ESSENCE investigates patterns, distinctions and relations in the present *Science of Logic* corpus, using established statistical, linguistic, and machine-learning tools. It must form **one reversible inquiry with BEING** rather than become a separate statistics application. The object is identifiable source text; the user chooses a question/method; the result can be checked and traced back to the text.

**Guiding rule:** reuse mature software (Python scientific stack, spaCy/Stanza, scikit-learn, PyTorch, model libraries, TensorFlow Projector, command-line tools or R when justified) through stable inputs/outputs. Write SOL-specific adapters for provenance, state, reproducibility and return-to-reading. Do not reimplement algorithms simply to place the SOL name on them. Never make CORE load a model or runtime merely to inspect a book.

**Decision (maintainer, 18 October 2026): ESSENCE orchestrates experiments; it is not an ML framework.** Simple, auditable transformations (tokenization, counts, sentence segmentation) may run in ESSENCE itself. Heavier methods run through task interfaces and adapters to existing libraries or models (spaCy, scikit-learn, PyTorch, Hugging Face, remote APIs), never as reimplementations. The encyclopedia is a modest table of contents of methods, with short attributed Wikipedia excerpts and further links ([§7](#7-methods-encyclopedia)). The immediate goal is much narrower: a reversible interface between reading in BEING and investigation in ESSENCE ([§4](#4-interaction-model-and-inquiry-contract)).

The relation between Hegel's explicit argument and the output of an algorithm is always **a research question**. Model similarity and a visual cluster are not equivalent to the logical movement of a concept. Preserve the boundary between measurement, statistical inference, interpretive hypothesis and argued philosophical necessity.

## 2. What exists now

**Implemented (stage D, 22 October 2026):** the ten cohesive engine modules
`tokenization`, `word_inputs`, `corpus_inputs`, `words`, `validation`,
`comparison`, `tfidf`, `sentences`, `sentence_inputs` and `prose` live in
`sol.essence.essence_as_reflection_within_itself`, following register rows
[E1–E4](ARCHITECTURE.md#9-placement-register) and their stage C rationale.
The lazy `sol.essence` facade exports the same names; CLI adapters, optional
Textual interface and catalogs remain at their existing paths. Engine bodies,
receipt methods/versions and the four known sentence-boundary failures were
unchanged by that relocation. The later opt-in segmentation v2 audit is recorded
below. Old engine module paths have no compatibility shims.

ESSENCE is not currently a complete model environment. The inspected code contains:

- `sol.essence.essence_as_reflection_within_itself.prose.export_prose` and `sol essence prose --json`: a **verified, Hegel-specific** prose-only analysis view over the current corpus.
- `sol essence sentences [--within PATH]`: the existing v1 corpus sentence-length study (run from the reader with `S` until 19 October, when the maintainer removed that key). `sol essence sentences --file PATH [--span START END]` and the provider API add v2 studies over UTF-8 files or independently scoped CORE inputs; `sol essence check FILE --input-file PATH` verifies file studies against an explicit local source.
- `sol essence tfidf`: dependency-free, versioned lexical TF-IDF over the existing word providers; engine, CLI and interactive study. Top terms per document and overall retain word-study provenance and are recomputable with `check` (details below).
- The optional Textual interface and the word engine's CORE/file counts, comparison measures and CSV/TSV export described in §4–§5. The interface also runs the sentence-length study through the provider API (19 October).
- `sol.core` public snapshot/reference APIs, including source/edition/generation binding and batch captures; these are usable without opening BEING.
- ESSENCE opens beside the reader (`E`) with the reader's exact position, and opens a result's source passage back in the reader. The earlier `sol-kitty` + Zsh handoff was removed on 21 October 2026.
- A bundled, offline methods encyclopedia on screen `1`, with nine entries and individually attributed Wikipedia excerpts ([§7](#7-methods-encyclopedia)).
- Checkout-only reading/rendering research, not an installed ESSENCE model suite.

**Not implemented/verified:** a general experiment picker beyond the three shipped lexical/sentence studies; parameter dashboard; GPU/model registry; task/capability registry and adapters; file providers for prose exports; syntactic research panel; UltraBERT embedding pipeline; TensorFlow Projector launch as a SOL command; durable research context/experiment history. Sustained human acceptance of the reader and investigation interface remains open. Do not describe these as shipping features until code and tests verify them.

The command namespace is `sol essence`; the former `analyze` name has no alias.

### Existing commands

```sh
sol essence tfidf --input-file /absolute/path/to/text.txt --top-n 20 --json > tfidf.sol-analysis.json
sol essence check tfidf.sol-analysis.json --input-file /absolute/path/to/text.txt --json
sol essence tfidf --within /ESSENCE --corpus local-corpus
sol essence prose
sol essence prose --json > prose.sol-analysis.json
sol essence sentences --within /BEING/i-determinateness-quality
sol essence sentences --json > quality.sol-analysis.json
sol essence sentences --file /absolute/path/to/text.txt --span 0 500 --json > sentences.sol-analysis.json
sol essence check sentences.sol-analysis.json --input-file /absolute/path/to/text.txt
sol reference capture RECORD_UUID --corpus local-corpus | sol reference check --corpus local-corpus
```

The first `prose` command summarizes eligible records. The JSON export is for consumption by scripts. Word frequencies measure normalized lexical occurrences, which do not prove concept identity. `check` verifies word-frequency, TF-IDF and sentence studies by recomputation, not arbitrary generated model outputs or `prose` exports. File analysis through the Python API or `python -m sol.essence.cli` needs no CORE import or configured corpus; the installed `sol` entry point still loads BEING's command dispatcher.

### TF-IDF engine contract (tfidf-v1)

The maintainer requested this simple auditable transformation without a new dependency.
`sol.essence.analyze_tfidf(target: CoreProvider | FileProvider, *, top_n: int = 20) -> dict`
returns a `sol.tfidf` v1 artifact. `documents[]` contains `input_index` and
`top_terms` (`word`, `score`); `overall` contains the highest mean-weight terms.
The index maps to `word_study.target.inputs`, which retains CORE identities,
source pages and digests, or a file digest and offsets. The embedded complete
`sol.word-frequencies` v1 receipt declares tokenization and projection; artifacts
contain vocabulary and first-occurrence locations, never passage text or file paths.

A document is exactly one retained word-provider input row: one CORE passage,
or one whole file (newlines do not create documents). Span selections keep only
wholly contained tokens. N counts all retained rows, including zero-token rows;
df(t) counts rows containing term t. The fixed formula is:

- `tf(t,d) = c(t,d)`, the raw included token count, without sublinear scaling.
- `idf(t) = ln((1+N)/(1+df(t))) + 1`, natural logarithm, add-one smoothing
  on both document counts and an outer +1.
- `w(t,d) = tf(t,d) * idf(t)`, then divide each document vector by its L2
  norm over **all** terms. Empty vectors stay empty.
- Overall weights are the mean of the unrounded normalized document weights
  across all N rows, including empty rows; N=0 produces no terms.
- Round final scores to 12 decimals, order by decreasing rounded score then
  normalized word, and retain `top_n` (1–1000, default 20) independently for
  each document and overall. Truncation happens after normalization and aggregation.

No stemming or stop-word removal occurs. With a single file, N=df=1 and IDF=1:
its ranking is normalized term counts. These weights do not establish conceptual
similarity or significance. File input is verbatim; CORE retains the word study’s
eligibility exclusions and facsimile masking. The shared 64 MiB input-file and
16 MiB result limits apply, including the embedded receipt.
`check_tfidf_result(target, result)` validates the declared method, recomputes
weights and invokes word-study verification against caller-supplied current
sources. It refuses changed whole-file bytes or corpus generations, including
unselected material, and never follows artifact paths. `encode_tfidf_result`
and `decode_tfidf_result` provide deterministic strict JSON transport. CLI `check`
reuses the saved scope and requires explicit file input for a file artifact.
The TUI can call this API later; this change adds no TUI controls or persistence.

## 3. Proper model inputs: projections, not destructive cleaning

**Current version-1 prose projection** (`sol.prose-input`, `sol.essence.export_prose(snapshot)`) selects records that are Hegel-attributed `main_text`, with types `paragraph`, `quotation` or `list_item`, excluding pending-review and explicitly generated text. Canonical section/headings, note callouts, image labels, formulas, editorial material and indexes are **not** silently concatenated into feature strings. Heading ancestry, locations, source pages, attribution, source digests, record type and corpus generation are retained as separate metadata. Words such as *Being*, *Remark*, or *Ground* that occur in **actual prose** are not blacklisted. Headings are removed by structural selection, not a word-level blacklist.

Use precisely `passages[].text` as the input to a prose embedding experiment; preserve `passages[].id` as the map back to the corpus. Example:

```python
import json
with open('prose.sol-analysis.json', encoding='utf-8') as f:
    view = json.load(f)
texts = [p['text'] for p in view['passages']]
ids   = [p['id'] for p in view['passages']]
meta  = [p['metadata'] for p in view['passages']]
```

**How the projection reads text.** It uses the CommonMark parser and visible-text renderer with explicit exclusions: Markdown headings (ATX, setext, and headings nested in quotations or lists) and HTML `h1`–`h6` contribute no text; Markdown and HTML image labels, including converter facsimile captions, contribute none; emphasis and visible link text stay prose; SOL note callouts stay omitted; ordinary superscripts and literal blocks stay visible. No word list, stemming, case folding or stop-word removal is applied. A heading wrongly transcribed as a prose sentence needs a canonical correction; capitalization is not a substitute for recorded structure. Each row keeps the record UUID, the derived text and its SHA-256, and separate `metadata` (canonical Markdown digest, type, parent, order, document, attribution, source pages, heading/title/path fields, and root-first ancestry from canonical parents); none of it is concatenated into `text`. The export carries corpus/edition/source identity, generation and projection version, checks the generation before and after, refuses a caller-modified snapshot, and writes nothing. Do not vectorize serialized rows, whole JSON or whole Markdown documents. A classifier gets prose as `X` and a deliberately derived category as `y`; category names and paths are never prefixed to `X`. A heading study, if wanted, is a separate experiment on titles.

**Decision:** this is one useful projection, **not** the cleaned text for every method. Maintain a typed, versioned preprocessing policy **per experiment**. Sentence length needs sentence segmentation and punctuation. Syntax needs clause/token/POS/dependency information and a declared pipeline. Some rhetorical studies need heading, annotation, note or formula context. Embedding requires explicit passage granularity and truncation/chunking policies. For every experiment, record why features were included or excluded; preserve the unmodified underlying canonical text and make derivations reproducible.

In particular, avoid these errors:

1. Treating a heading in the index as prose because it contains meaningful philosophical vocabulary.
2. Removing legitimate prose words because the same strings occur as heading titles.
3. Vectorizing JSON metadata alongside text, introducing obvious category leakage.
4. Implicitly treating translators' sentences as Hegel's original German syntax.
5. Silently concatenating paragraphs, ignoring section boundaries, or truncating input beyond model limits.
6. Calling distances or embeddings ontological relationships without an independent argument.

## 4. Interaction model and inquiry contract

**Implemented (stage D):** the private launch-file schema, validation, owner-only
I/O and Textual availability probe live in `sol.interchange.essence`, outside
the logical hierarchy ([Architecture §9, I1](ARCHITECTURE.md#launch-exchange-outside-the-logical-hierarchy-i1)).
BEING writes it and the TUI entry point reads it; the reader removes its private
context directory at exit. Saved investigation state remains owned by
`sol.essence.tui.context`. The format, lifetime and source-return OSC are unchanged.

**Decisions (maintainer, 18 October 2026)**, from the [ESSENCE interface brief](coordination/proposals/ESSENCE_INTERFACE_BRIEF_2026-10-18.pdf). They direct the work; how far each is implemented is recorded below and in the dated sections that follow.

1. **Hybrid surfaces.** Neovim remains the persistent BEING reader. ESSENCE gets its own interactive application, built with **Textual**, launched only when ESSENCE is requested. **Textual is an optional extra** (`sol-organizes-logic[essence]`, decided 18 October 2026): the reader installs and runs without it, and ESSENCE explains how to install it when it is missing.
2. **On-demand lifecycle.** No Textual process exists while the reader is idle. Entering ESSENCE starts it in a Neovim terminal buffer; leaving ESSENCE saves the investigation state and ends the process. ESSENCE remains an ordinary application inside a terminal Neovim provides, not a terminal emulator.
3. **Two presentations, one investigation.** ESSENCE appears either **beside** BEING (one split, the reader still visible) or **fullscreen**. Switching between them reuses the same process and investigation; it does not restart anything. Together with plain reading there are three visible states.
4. **Outer versus inner layout.** Neovim owns the outer geometry (split or fullscreen); Textual owns the layout inside its terminal buffer. Textual screens are logical views *within* ESSENCE (encyclopedia, method, experiment, results), not the two outer presentations.
5. **Interface before analytical breadth.** First prove launch, both presentations, focus, state preservation, close and return; then add the smallest real operation, a word tokenizer and frequency table ([§5](#5-prioritized-experiments)).
6. **One capability, interactive and headless.** Every analytical operation the interface offers also runs from the CLI with the same inputs and the same artifact, so results can be scripted, checked and reproduced without the UI. The read-only encyclopedia browser has no CLI.
7. **CORE is optional for ESSENCE.** ESSENCE accepts ordinary text files; CORE is the provider that adds verified identity, provenance and source return when present. The path is staged in [Architecture §2](ARCHITECTURE.md#2-logical-divisions-and-component-responsibilities); this is implemented for the word, sentence and TF-IDF studies, whose CLI and interface accept a UTF-8 text file without CORE (`FileProvider`). File results cannot open in the reader, and BEING still needs a CORE corpus.

**Implemented (18 October 2026), stage 1 shell:** `sol.essence.tui` is a Textual application with four screens (Encyclopedia, Methods, Experiment, Results) initially holding placeholder text; Encyclopedia now browses the bundled catalog (§7), and Methods (20 October) browses the bundled methods catalog (`sol/essence/methods.json`): for each runnable study its inputs, settings, output, limits and command line, with its encyclopedia entry named; the reader's origin is shown at the top. `1`–`4` switch screens, `q` or Ctrl-Q leaves; the command palette is off. Leaving saves only the open screen and the origin record, owner-only, under `$XDG_STATE_HOME/sol/essence/` for workspace sessions (temporary `-n` sessions save nothing); the next opening returns to that screen. Opening it imports no model. Measured on this machine inside Neovim's terminal: start-up about 110 ms; a split-to-fullscreen change reflows without a restart; Escape, Alt-Left/Right, Alt+letters, Ctrl-S/N, Tab, function keys and arrows arrive intact through terminal mode. Textual reads Escape-then-letter as Alt+letter, binds Ctrl-Q to quit and Ctrl-P to its palette, so ESSENCE avoids those for other purposes. Reader-side behaviour: [BEING §6](BEING.md#6-being--essence-without-terminal-dogma).

**Implemented (18 October 2026), stage 2 interface side:** the Experiment screen chooses a **target** (this passage, its section, the whole book, or a UTF-8 text file) and an optional **reference** (its section, the whole book, or a text file) and runs the stage 2 word-frequency engine (`sol.essence.essence_as_reflection_within_itself.words.analyze_words`) in a background worker. Results shows, for each side, tokens, distinct words, inputs, provider and scope, the engine's warnings (unequal denominators, different projections), and a table of the most frequent 2,000 words with counts and rates per 10,000 tokens; an undefined rate is shown as such. Workspace sessions save the artifact owner-only as `~/.local/share/sol/studies/words-*.sol-analysis.json` for `sol essence check`; temporary sessions save nothing. Choosing only text files needs no CORE corpus. Opening a word's passage in the reader is stage 3. On the real book through this interface code: a passage counts in about 0.5 s, a section against the whole book in about 1.4 s.

**Implemented (18 October 2026), stage 3 interface side:** with a reference, a count calls `sol.essence.essence_as_reflection_within_itself.comparison.compare_words` once (it runs the stage 2 study and adds the measures), so the interface computes no measure itself. Results then adds **Difference** (per 10,000 tokens) and **Log₂ ratio** columns; an undefined measure says why in the engine's terms (*absent in target*, *absent in reference*, *empty target*, *empty reference*), and the summary states both formulas, that there is no smoothing, and the engine's warnings, including that the measures are descriptive only. Below the table, **Sources** lists where the highlighted word occurs: one row per occurrence, numbered within its passage or file (*2 of 5*), with the words around it (about 40 characters each side, the word in bold) and the passage's heading and printed page (19–20 October). The study records only each input's first occurrence; the others are found again at display time with the same tokenizer in the verified text and are never saved. Where they cannot be confirmed (the text changed, or masked tokens were left out of the count), only the first is listed, with the input's count. At most 1,000 rows are listed per word, and the label says when fewer than all occurrences are shown. The context is read from the loaded book or the chosen file for display only and is shown only if that text still has the digest the count recorded; otherwise the row says the text has changed. After a count the word table has the focus: arrows choose a word, Enter moves to its sources, Escape back; switching screens with `1`–`4` starts on that screen's first control. Enter on a corpus row opens that occurrence in the reader ([BEING §6](BEING.md#6-being--essence-without-terminal-dogma)); text-file rows are listed but cannot open. **Export CSV / Export TSV** call `export_word_comparison`, which checks the sources against the study again first, and write `~/.local/share/sol/studies/words-*.csv|tsv` owner-only, never overwriting; temporary sessions write nothing, and a count without a reference has no table to export. **Cancel** abandons a running count: the engine cannot be interrupted, so it finishes in the background and its result is discarded and not saved. On the real book (this machine): a section against the whole book about 2.8 s (the comparison adds about 0.5 s to the count), an export about 3.2 s.

**Implemented (19 October 2026), the sentence study in the interface:** the Experiment screen first chooses a study, **Word frequencies** or **Sentence lengths**; sentence lengths take the same targets (this passage, its section, the whole book, a text file) and no reference. They run `sol.essence.essence_as_reflection_within_itself.sentences.analyze_sentences` with the word engine's providers, so the result is the `sol.sentence-study` v2 artifact of [§5](#5-prioritized-experiments), saved owner-only as `~/.local/share/sol/studies/sentences-*.sol-analysis.json` in workspace sessions (nothing in temporary ones) and checked with `sol essence check`. Results then shows the totals, the distribution of words per sentence as bars, the means by place in the paragraph, what was left out, and that the study describes the translation's sentences under `punctuation-rules-v1`; the table lists the twelve longest sentences with their length, how they begin and their heading and page. Beginnings, headings and pages are read for display and never saved. Enter opens a sentence at its first character in the reader through `essence_source`, and Alt-Left returns; a text file's sentences cannot open there. This replaces the reader's former `S`. On the real book: a chapter of 137 passages (624 sentences) measures in about 1 s; the longest sentence opened at its first letter.

**Implemented (20 October 2026), study layout and TF-IDF:** Experiment offers Word frequencies, Sentence lengths and **TF-IDF · top terms by passage**. Reference choices appear only for word frequencies; file path fields appear only when their source is **A text file**. Borderless groups and neutral Run/Cancel controls use the active Textual theme, including SOL Paper and Night. Encyclopedia and Methods have taller, bounded lists and correctly named help. Word results without a reference omit its columns and export controls; summaries use singular/plural input counts. Sources reserve a wrapping heading/page column before the wrapping context; spaces adjoining the bold word survive line folding. Results reflow when the terminal changes size.

**Visual audit (21 October 2026):** every screen and each study's Results were rendered on the book (Textual's own screenshots, Paper at 100×36 and Night at 80×24). Fixed: the chosen option's dot uses the theme's accent and the others stay visible on dark pages (the chosen dot was green, the others near-invisible in Night); a summary takes at most a quarter of the height, so the tables keep room in small windows (at 80×24 the word table showed three rows); rate columns are headed `per 10k`; summaries name a section by its title and first page instead of its corpus path; sentence-length bars use the accent instead of solid ink; the longest sentences' beginnings end at a word with `…`; Export buttons are one line; the layout hint fits 80 columns. The remaining 80×24 Results limitations were addressed by the small-window layout below.

**Small-window Results (21 October 2026):** at 80×24 and 120×40 the Results pane stays within its window. The scrollable summary takes at most a fifth of its height; word frequencies and their occurrences share the remaining space, with compact source help and one-line export controls. Column widths reserve room for cell padding and vertical scrollbars: words, undefined measures, sentence beginnings, locations and TF-IDF terms wrap rather than requiring sideways scrolling. All comparison columns remain present. The occurrence list stays visible while arrows choose a word; Enter focuses its occurrences, Enter there opens the reader, and Escape returns to words. Resizing preserves the selected word/occurrence, focus and export status. Long rows and summaries remain available by vertical scrolling; engines, saved artifacts and exports are unchanged.

TF-IDF calls `sol.essence.analyze_tfidf` with the same passage/section/book/file targets and no reference. Experiment offers **Top terms per passage and overall**, an integer from **1 to 1,000**, default **20**; invalid values are refused before a worker starts. The results header shows the chosen number, and the existing TF-IDF artifact records it as `top_n`. The screen/origin investigation state does not record study choices, so its format is unchanged and a new opening starts at 20. Results lists each passage in reading order with its ranked terms and weights **first**, then a separate overall mean-weight table. Every retained top term remains available by scrolling. Enter on a passage sends its ID, span start and content digest through the same guarded reader request as sentences; file rows explain that they cannot open. Workspace sessions save `tfidf-*.sol-analysis.json` owner-only beside other studies, checkable with `sol essence check`; temporary sessions save nothing. Headings and pages are display-only. TF-IDF declares raw-count TF, smoothed IDF, L2 normalization and no stop-word removal; it does not claim to identify concepts.

**Implemented (23 October 2026), comparison sorting:** with the word-comparison
results table focused, `s` opens a sort menu. Arrows choose **Engine order
(default)** or **ascending / descending** for Word, Target count/rate, Reference
count/rate, Difference or Log₂ ratio; Enter applies, Escape cancels. A line above
the table shows the active column/direction and that undefined values are always
last. Numeric sorting uses the engine's numeric values, before the 2,000-row
display limit; ties (including undefined ties) retain engine order in either
direction. Undefined rates still say *undefined*, and undefined measures retain
their reason (*absent in target/reference*, *empty target/reference/both*).
Source navigation follows the sorted word; resizing retains that word and its
occurrence. New results start in engine order; the menu can also restore it.
Sorting changes only presentation: saved artifacts and CSV/TSV exports retain
all engine rows in their original order and with their unchanged content.

**Panel redesign (24 October 2026):** a compact SOL / ESSENCE masthead and
source line sit above numbered screens. Rounded, titled panels separate catalog
contents from reading, study choice from source configuration, and a result's
summary, measurements and source context. At 100 columns and above, catalogs
and Experiment use a sidebar beside their detail/setup pane; below that they
stack, preserving their existing widgets, selection, input values and focus.
Below 60 columns the target and reference groups stack too. The wide study
sidebar explains the selected operation; narrow windows keep its choices and
give the configuration more space. Focused panels use the current theme's
accent; Paper, Night, Catppuccin and Terminal remain supported. Results starts
with a **Choose a study** action rather than empty tables. Result columns account
for frame widths and fold at narrow widths. Existing controls, computations,
source-return guards, artifacts, exports and screen/origin persistence are
unchanged. Automated layout checks and rendered synthetic previews are visual
and interaction evidence, not sustained human acceptance.

**Results and method workflow (24 October 2026):** Results opens with compact
totals: target/reference token denominators, sentence/word totals and mean, or
TF-IDF token/input totals and top_n. **i Details** (also a button) opens the full
existing scrollable summary, scope, method notes, exclusions and saved-artifact status;
its parenthesized number counts existing method/source notes. `i` hides details
again; Escape returns focus to the measurements without closing the disclosure.
Each new result starts collapsed; layout changes preserve its current state.

Word results offer a local display filter: `/` or Ctrl-F focuses it, Enter moves
to the word table, Escape clears a nonempty filter and a further Escape returns
to the table. Matching is a literal substring of normalized word spellings
(NFC, case folding, curly-to-straight apostrophes), before the 2,000-row display
limit. Sorting still uses all engine rows; sources follow the selected matching
word, named on their panel. Empty matches clear old source rows and show an
explicit status. Counts, token denominators, artifacts and complete exports are
unfiltered. Filtering and the details disclosure are session presentation only;
a new result clears the filter and the saved screen/origin format is unchanged.

**Methods** offers **Use this method** for words, word comparison, TF-IDF and
sentence lengths. It selects the matching Experiment study without running it
or clearing existing paths/settings. Comparison supplies a book reference for
a CORE session, or a file reference otherwise, only when none was selected.
Prose export and saved-study checking remain labeled CLI operations with their
documented commands. Catalog/detail panels and all existing reading controls
remain available.

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
| 0. Documentation | These decisions reconciled in the governing documents | Docs check passes; no application code changed; open decisions listed |
| 1. Interface shell | Textual mock (Encyclopedia / Methods / Experiment / Results); entry from and return to Neovim; split and fullscreen | Launches on demand, resizes without restart, restores the reader position, keyboard focus is robust |
| 2. Minimal experiment | Word tokenizer and frequency table over a selectable target; source-linked counts; plain-text file input | Same output from CLI and TUI; works on a plain-text file without CORE |
| 3. Comparison | Reference-corpus selector; normalized lexical comparison; navigation and export | Explicit denominators; no false comparability; stale generations refused |
| 4. Encyclopedia (implemented, 20 October) | Bundled methods table of contents; short attributed Wikipedia excerpts and further links | Browsable offline, without CORE or model downloads |
| 5. Model adapters | Capability-driven registry; optional runtimes; comparison experiments (including Experiment B below) | Model versions, input limits, policies and reproducibility documented and tested |

**The first new experiment stays elementary:** a deterministic, documented word tokenizer, with token count, type count and a frequency table for the selected scope. Its purpose is to test the whole research loop, not to settle what a word is. The shared word tokenizer (`sol.essence.essence_as_reflection_within_itself.tokenization`) is implemented: it takes runs of letters with combining marks and internal apostrophes, applies NFC and case folding, excludes digits and punctuation, and splits hyphenated compounds; the method is declared in each artifact ([§4](#4-interaction-model-and-inquiry-contract)). Model-specific subword tokenization and morphology come later as **distinct analyses**, never as aliases of this one.

The shipped sentence study (Experiment A, below) is not superseded; it remains the first complete reader-to-ESSENCE round trip and moves into the new interface once stage 1 exists.

### Stage 2 engine — word frequencies (implemented, 18 October)

The headless engine is available independently of the interface shell. The
tokenizer lives unchanged in `sol.essence.essence_as_reflection_within_itself.tokenization.word_tokens` (the term
study that first used it was removed on 21 October 2026). It
yields normalized words and original, half-open Python codepoint offsets:
letter runs with combining marks and internal straight/curly apostrophes,
NFC then case folding then curly-to-straight apostrophes; punctuation and
digits excluded, hyphens split. The artifact records the runtime Unicode
version. These are ordinary word tokens, not morphological or model subwords.
They are not the reader's search unit: whole-word search in BEING bounds a
literal match by Unicode letters, digits and underscore, so it finds numbers
and the parts of `can’t`, and it keeps the source's curly apostrophe. On the
book's 1,757 analysed passages the two differ at 633 places, almost all curly
apostrophes and numbers ([WORD_UNIT](coordination/restructuring/WORD_UNIT.md)).
Both are kept for now; whether to align them is a maintainer decision.

The interface-facing function is
`sol.essence.essence_as_reflection_within_itself.words.analyze_words(target, *, reference=None) -> dict`.
Each argument is a `CoreProvider(snapshot, scope=None)` or
`FileProvider(path, scope=None)` from `sol.essence.essence_as_reflection_within_itself.word_inputs` (also exported
from `sol.essence`). Providers can differ; no Textual import is involved.

- CORE consumes a verified `CorpusSnapshot` with permanent identity. Default
  scope is `{"kind":"corpus"}`; alternatives are
  `{"kind":"within","path":"/BEING/..."}`,
  `{"kind":"passages","ids":["FULL_UUID",...]}`, or
  `{"kind":"span","id":"FULL_UUID","start":0,"end":20}`.
  IDs must be exact and distinct; inputs retain canonical order. Reader paths
  match whole path components. The CORE word-study projection selects
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
sol essence words --corpus /absolute/path/to/corpus --within /BEING --compare
sol essence words --corpus /absolute/path/to/corpus --passage FULL_UUID --span 0 20
sol essence words --file /private/target.txt --reference-file /private/reference.txt
sol essence words --file /private/target.txt --span 0 20 --compare --json > /private/words.json
sol essence check /private/words.json --input-file /private/target.txt
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
with caller-supplied providers and matching scopes. `sol essence check`
reuses validated artifact scopes, but file paths must be supplied explicitly;
CORE sources come from `--corpus`/discovery and `--reference-corpus`. It emits
a verification receipt, not another study. Any changed corpus generation or
file bytes, including unselected material, invalidate the result; input
changes during execution are refused too. Rechecking does not overwrite the
artifact or change canonical/workspace data. The interface runs the same engine (stage 3 interface side, §4); a formal
CLI/TUI equivalence trial remains open.

### Stage 3 engine — comparison measures and export (implemented, 19 October)

`sol.essence.essence_as_reflection_within_itself.comparison.compare_words(target, *, reference, result=None)`
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
sol essence words --file /private/target.txt --reference-file /private/reference.txt --json > /private/study.json
sol essence words-export /private/study.json --input-file /private/target.txt --reference-file /private/reference.txt --format csv > /private/comparison.csv
sol essence words-export /private/study.json --input-file /private/target.txt --reference-file /private/reference.txt --format tsv > /private/comparison.tsv
sol essence words-export /private/core-study.json --corpus /private/corpus --format csv
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
Textual; the interface's controls and source navigation are described in §4.

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

**Implemented (17 October): the sentence-length half.** `sol.essence.essence_as_reflection_within_itself.sentences` selects eligible Hegel main text exactly as the term study does (pending-review records are excluded and counted), masks converter facsimile labels, and segments with declared rules (`punctuation-rules-v1`): a sentence ends at `.`, `!`, `?` or an ellipsis (with closing quotes/brackets) followed by whitespace and a capital, digit, opening quote/bracket or dash; never inside a bracket opened within the sentence (citations such as *(Princ. Math. Phil. Natu. Lib. II, …)*), after a listed abbreviation (single letters only in lower case, so a logical term like *S-U-P.* still ends a sentence) or within a chain of initials; a newline always ends one. Length is counted in the term study's word tokens. The artifact (`sol.sentence-study` v1) stores record IDs, digests, codepoint offsets and token counts — **no book text** — plus the distribution, percentiles, means by place in the paragraph (first/middle/last/only) and the longest sentences; `check` recomputes it exactly against the current generation. Rules were tuned on the local corpus: of 9,127 sentences (median 31 words), the three longest (150, 148, 146 words) were read and are genuine Hegel sentences, a random sample of boundaries was correct, and the 40 held-back periods followed by capitals were almost all citation abbreviations; one known miss is a full sentence inside a parenthesis opened mid-sentence. **Audit (23 October):** a fixed-seed, 60-passage hand-style review now reports boundary precision/recall and coverage below. **Not yet done:** independently human-adjudicated segmentation validation, part-of-speech/dependency statistics, and sentence-level scopes smaller than a loaded section from the reader. POS tagging and parsing will be probabilistic/error-prone, so present them as **model annotations**, not source facts. The linguistic conclusions describe the chosen translator's text; contrast with Hegel's German only if a distinct German source is actually available and audited in a future research cycle.

#### Sentence providers and file input — implemented 19 October 2026

`sol.essence.analyze_sentences(provider, *, origin=None, segmentation="punctuation-rules-v1")` accepts the **same**
`CoreProvider(snapshot, scope=None)` and `FileProvider(path, scope=None)` as
the word engine. CORE scopes are `corpus`, `within` a reader path, exact
`passages` IDs, or a `span` with one exact `id`, `start` and `end`. Files use
`file` or a `span` with `start` and `end`. Set scope on the provider; a separate
`scope=` argument remains available only for the legacy snapshot API.

The original complete text is segmented with `punctuation-rules-v1` by default
(or explicitly selected `punctuation-rules-v2`, described below)
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
named method `sentence-length-distribution-providers-v1` (or
`sentence-length-distribution-providers-v2` for opt-in punctuation v2). Its `input` records
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
sol essence sentences --file /absolute/path/to/text.txt
sol essence sentences --file /absolute/path/to/text.txt --span 10 500 --json > sentences.sol-analysis.json
sol essence check sentences.sol-analysis.json --input-file /absolute/path/to/text.txt
sol essence sentences --corpus local-corpus --passage RECORD_UUID --span 10 500 --json
```

```python
from sol.essence import FileProvider, analyze_sentences, check_sentence_result
provider = FileProvider("/absolute/path/to/text.txt", {"kind": "span", "start": 10, "end": 500})
result = analyze_sentences(provider)
checked = check_sentence_result(provider, result)
```

This adds no model, dependency or corpus/workspace contract. An explicit
`--segmentation punctuation-rules-v1|punctuation-rules-v2` CLI choice uses
providers and protocol v2, including for whole-corpus input. Without that option,
ordinary corpus CLI output retains protocol v1. Bare snapshots retain v1; choose
an explicit `CoreProvider` to run punctuation v2. Checks recompute with the exact
recorded method; old snapshot and provider artifacts remain valid.

#### Sentence-boundary audit — 23 October 2026

The [counts-only audit](coordination/restructuring/SENTENCE_AUDIT.md) documents a
fixed-seed random sample of 60 eligible private-corpus passages, complete
hand-style boundary rules and coverage by error type. The single-agent review
found 282 internal gold boundaries: v1 has 281 TP, 5 FP and 1 FN (**98.25%
precision, 99.65% recall**). Opening numbered-list markers cause the five false
splits; an attached footnote number causes the missed boundary. Semicolons and
colons remain within sentences by design. Abbreviation/quotation/bracket
coverage and absent rare cases are stated explicitly; no corpus text is
published and the corpus was read-only.

The new, separately named **`punctuation-rules-v2`** keeps opening Arabic list
markers with their item and attached numeric footnote callouts with the preceding
sentence, with a decimal guard. It otherwise retains v1's rules and declared
abbreviation list. On the **same frozen sample**, it has 282 TP, 0 FP and 0 FN
(100% precision/recall); this is an in-sample correction, not independent
validation. The **interface, API and CLI default remains v1** pending broader
review. Synthetic tests cover each rule and artifact-method dispatch. The four
expected-failure tests still document both methods' limits: mid-sentence
parentheses, physical line breaks, sentence-final abbreviations and lowercase
starts. No independent human adjudication or real-book accuracy for absent
categories is claimed.

### Experiment B — embeddings and TensorFlow Embedding Projector

**Research question:** what textual neighborhoods does a selected *embedding method* place near a given passage, and how stable are these neighborhoods under model, granularity and projection choices?

Build one controlled, reproducible local embedding experiment. Compare model suitability/requirements rather than chasing model releases. **UltraBERT** is a possible candidate discussed in the project, not an adopted or verified local dependency in this baseline. Confirm the exact released checkpoint, intended use, language coverage, embedding extraction method, token/window limits and license **before** integration. A classifier backbone is not automatically an optimal sentence-embedding model; benchmark against a purpose-built sentence-embedding baseline.

For each row preserve: source UUID, text digest, model input length, truncation/chunking, language, provenance, relevant hierarchy labels (as metadata, *not* embedding input), and a stable row order. Compute numeric vectors; check all are same dimensionality, finite, and aligned with metadata. Export separate local TSV files: a numeric vectors TSV (one row per example, same dimension throughout) and a corresponding metadata TSV (one row per vector, with clearly labeled fields). Include UUID and source location in metadata. Support the **TensorFlow Embedding Projector** through local file loading and/or an opt-in launch path. Do not expose private copyrighted text via an external upload without an explicit user decision; evaluate the privacy characteristics of the chosen viewer/mode.

Report nearest neighbors in original embedding space separately from 2-D/3-D PCA, t-SNE or UMAP visualizations. Choice of projection, random seed, perplexity/neighbors and subsampling change visible clusters. Do not claim that Cartesian appearance proves a logical relation, a stable taxonomy or successful classification. If labels derive from Hegel's section headings, isolate them as supervised/evaluation `y`, and split train/test data by meaningful contiguous sections to reduce leakage from adjacent prose.

### Experiments after these two

Only after the workflow is proven: lexical concordances and collocations, full dependency patterns, cross-section retrieval, topic models, supervised classifiers, passage alignment for new audited editions, alternate languages, and user-authored relational hypotheses. Do not implement a model store or experimental UI with dozens of hyperparameter controls before one method works end to end.

## 6. The present lexical experiment as a reference

The word-frequency study normalizes Unicode token spellings, counts words,
reports counts and rates per 10,000 eligible tokens, and records contributing
passage IDs and offsets. It filters explicit attributed main-text records and
review flags rather than reinterpreting the document tree. Results retain a
method identifier, source and generation hashes and can be checked by
recomputation. Zero-token inputs have undefined rates. A source match is lexical
evidence, not classification of a philosophical concept. The former one-word
term experiment was removed in the maintainer's 21 October cleanup; the shared
word tokenizer remains in `sol/essence/essence_as_reflection_within_itself/tokenization.py`.

The reader-to-ESSENCE round trip runs through `E` and the reader's guarded `essence_source` request ([BEING §6](BEING.md#6-being--essence-without-terminal-dogma)); the earlier Kitty/Zsh handoff was removed on 21 October 2026.

<a id="7-model-history-encyclopedia-and-task-registry-proposed"></a>

## 7. Methods encyclopedia

**Decision (maintainer, 20 October 2026), implemented:** the encyclopedia stays a
modest table of contents. The broader encyclopedia proposal (PR #37; in Git history since 21 October 2026)
remains historical design material; its §9 is deferred. No genealogy graph,
editorial review states, catalog CLI, task registry or model execution is adopted.

**Decision (maintainer, 21 October 2026), implemented:** "a small genealogical
map, as the 'first page' of the encyclopedia". This amends the decision above
for the map only; editorial review states, a catalog CLI, a task registry and
model execution remain unadopted, and the proposal's larger graph is not.

The small bundled file `sol/essence/encyclopedia.json` contains nine entries:
word counts, word tokenization, relative frequencies and comparisons, sentence
segmentation and length, lexical distribution and source context, prose
projection, TF-IDF, word vectors, and Transformers. SOL's notes identify the
existing operations (word frequencies and occurrences, sentence lengths, TF-IDF,
prose projection) and distinguish reading topics without runnable adapters.

Each entry has one short **verbatim Wikipedia excerpt**, its article title and
URL, and one or two further links. Shared attribution to **Wikipedia
contributors**, the **CC BY-SA 4.0** license and license URL, and the access date
(**20 October 2026**) are stored alongside the entries and displayed for each
one, with a link to the article's contributor history. Excerpts are unchanged;
some are sentence fragments. The quotations retain their CC BY-SA 4.0 license
separately from SOL's code. The SOL-specific notes are outside the quotation.
No Wikipedia images or other media are bundled.

**Genealogy** is the encyclopedia's first item and opens first: a map of where
the methods come from, with a year column and lines of descent, drawn from the
`genealogy` block of the same file (each node names its parent and the entry it
opens). ● marks what ESSENCE runs, ○ a reading topic; ancestors without an entry
(Hugh of Saint-Cher's concordance, 1230; Mendenhall's counting for authorship,
1887; Harris's distributional hypothesis, 1954) are shown but cannot be chosen.
Every year is one given by a linked Wikipedia article (accessed 21 October
2026), listed below the map; a method without a sourced date has none. Enter on
Genealogy moves into the map, and Enter on a method opens its entry.

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

**Source lineage:** consolidated from installed `sol.essence` implementation and tests, prose-input policy, term study, reference protocol, handoff, modularity/usage manuals, research discussions and the present 17 October priorities. Earlier documents are in Git history.
