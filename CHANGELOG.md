# Changes

## Unreleased

- Reader: detect equivalent source/destination key names in keys.json before applying remappings, warn and keep default controls instead of crashing startup or silently overwriting an action.

### Sentence segmentation audit — 23 October 2026

A reproducible, read-only, 60-passage private-corpus audit reports v1 boundary
precision 98.25% and recall 99.65% (281 TP, 5 FP, 1 FN). Opt-in
`punctuation-rules-v2` keeps opening list numbers and attached numeric footnote
callouts with their sentences; on the same frozen sample it corrects all six
errors. This is an in-sample result. `sol essence sentences --segmentation` and
the provider API select either method; checks use the recorded method. V1,
existing artifact encodings and the interface default remain unchanged. The
audit publishes counts and abbreviation strings only, with synthetic tests for
the rules and no new dependencies.

### ESSENCE study controls — 23 October 2026

Experiment accepts TF-IDF top_n from 1 to 1,000 (default 20), shows the choice
in Results and records it in the existing TF-IDF artifact. With comparison
results focused, `s` opens a column/direction sort menu; undefined values stay
last, their reasons remain visible, and ties keep engine order. Sources follow
the sorted word. Engine order remains the default and can be restored. Sorting
leaves saved artifacts and exports unchanged; investigation state still records
only the screen and origin.

### Landmark management — 23 October 2026

In the Neovim reader's `L` panel, `r` renames the selected landmark with the
existing name rules and duplicate protection. Rename atomically preserves its
target and metadata, including unavailable targets. `o` toggles name/book order
for the session, with unavailable passages last in book order. Panel hints and
`?` help document the keys. Workspace schema and quick markers are unchanged.

### Section keys keep Neovim running — 23 October 2026

`]c` and `[c` restarted Neovim for every section because the Lua controls lost
their reference to the action channel when the reader was split into modules
(18 October). They now use the channel like `n`/`b`: about 0.83 → 0.56 s from
key to text on the book. The same fix restores the wait for unacknowledged
saves (such as a marker) before quitting.

### Sections prepared ahead — 23 October 2026

The reader builds the neighbouring sections during the opening screen and,
after each section change, while idle, so `n`, `b` and section moves across a
boundary no longer wait for a full section build (about 430 → 275 ms of Python
time on the book; the opening screen is about 0.3 s longer). Prepared sections
are reused only when a fresh CORE capture still matches them.

### Private source-request hardening — 23 October 2026

Malformed source requests raise `SourceError`; region rendering validates before
reading page locations. PDF viewers and following refuse a corpus generation
change during/after PDF verification before accessing a viewer or D-Bus.
Capture output, rendering, caches and public CORE interfaces are unchanged.

### Word units documented — 23 October 2026

`--word` help and BEING/ESSENCE docs now say what whole-word search matches
(no Unicode letter, digit or underscore on either side) and that ESSENCE's word
unit differs (internal apostrophes kept, numbers ignored, curly apostrophes
written as `'`). No search or tokenizer behaviour changed.

### Decouple the ESSENCE launch — 22 October 2026

BEING and ESSENCE share the private launch-file format through
`sol.interchange.essence`, outside the logical hierarchy. The reader probes
Textual without importing ESSENCE's interface. Context bytes, validation,
permissions, lifetime, install hint and the OSC source-return path are unchanged;
ESSENCE still owns its saved investigation state.

### The composition root leaves the reader — 22 October 2026

Stage D, last BEING-lane step: `sol.reader.app` is `sol.app.main`, with
`options`, `launch` and `sol read`'s printing (`commands`) beside it in
`sol.app`, outside the logical divisions. The emptied `sol.reader` and
`sol.terminal` packages are removed. Commands and behaviour are unchanged.

### CORE and shared presentation relocation — 22 October 2026

Move canonical-file resolution and the reference command face into `sol.core`,
first-run corpus import into `sol.corpus`, and verified source capture/rendering
into `sol.core.source`. Detached PDF/image viewers and source following live in
`sol.being.source_view`; `sol read` printing stays in `sol.reader.commands`.
Shared escaping, theme data and width defaults now live in `sol.presentation`,
so ESSENCE no longer imports reader options for themes. Command behavior and the
public CORE API are unchanged; the old internal module paths have no shims.

### ESSENCE engines relocated — 22 October 2026

Restructuring stage D: move the ten analytical engine modules to
`sol.essence.essence_as_reflection_within_itself` (register E1–E4). Keep the
lazy `sol.essence` exports, commands, method receipts and behavior unchanged;
update CLI/UI imports and test patch targets without old-path shims.

### BEING's code moves into its divisions — 22 October 2026

Restructuring stage D, BEING lane: the Neovim reader is `sol.being.neovim`
(`neovim.py` is now `host.py`, `neovim_reader.py` is `reader.py`,
`reader_channel.py` is `channel.py`; the Lua files and fonts moved with it);
the reading session, surface, rendering and shell are in `sol.being`; layout
geometry is in `sol.being.quantity`; search, outline and typography are in
`sol.being.quality`; workspaces are `sol.being.workspace`. Code is moved, not
rewritten; commands, workspaces and behaviour are unchanged, and `sol-window`
keeps its name (reinstall to refresh its entry point).

### The logical divisions exist — 22 October 2026

Restructuring stage B: empty packages for BEING (Quality, Quantity, Measure),
ESSENCE (Essence as Reflection within Itself, Appearance, Actuality) and a
reserved CONCEPT. Nothing has moved into them yet; behaviour is unchanged.

### SPECULATIVE leads the documentation — 21 October 2026

The maintainer's *Speculative Architecture and Methodology* is now
`docs/SPECULATIVE.md`, the leading of five governing documents. SOL is described
as a computational investigation of philosophy and a philosophical investigation
of computation, to be restructured under BEING, ESSENCE, a reserved CONCEPT and a
separate CORE. The other documents, the README and the agent rules were aligned
with it; no code changed.

### A smaller SOL: one reader, a minimal shell, no Kitty — 21 October 2026

- `sol being` names the reader; bare `sol` still opens it. `--reader` is gone.
- `sol --shell` is a minimal command line for browsing the book (`ls`, `cd`,
  `tree`, `read`, `cat`, `search`, `open`, `context`, `info`, `guide`). It uses
  no workspace, saves nothing and needs no `prompt-toolkit`, which is no longer
  a dependency.
- Removed: `sol-kitty` and its panes, the Kitty/Zsh ESSENCE handoff and
  `sol reference return`, `sol compare`, the shell's workspace commands
  (notes, bookmarks, comparisons, reviews, relations), `neofetch`, the legacy
  PDF reader (`--pdf`), the hidden `--engine`, `--ui`, `--editing-mode`,
  `--source-pdf` and the empty `corpus`/`shell`/`extraction` extras. Comparisons,
  reviews and relations already stored in a workspace stay readable and
  exportable.

### ESSENCE cleanup — 21 October 2026

- Rename the analysis CLI to `sol essence`, with no `analyze` alias; update
  help, study verification messages, Methods and current documentation.
- Remove the one-word term experiment, segmentation-pilot commands and modules,
  and checkout-only formula review sheet, with their dedicated tests. Keep the
  shared word tokenizer and CORE freshness/selection guards for word and sentence
  studies; their methods and saved artifact formats remain unchanged.

### Legacy documents folded in and removed — 21 October 2026

The still-valid contracts from the pre-17-October documents now live in the
current ones: the corpus contract and reference protocol in CORE §§9–10, the
prose-input policy in ESSENCE §3, workspace storage and export rules in BEING
§3. `docs/legacy/`, two finished proposals and old handoff reports were then
removed from the tree; Git history keeps them.

### Remove reader surface experiments — 21 October 2026

- Remove `experiments/reader_surfaces/` and the Neovim research-export entry (`neovim.run`, `:SOLExport`, standalone Lua mode). The reader keeps its integrated controls, checked selections and action results.
- Run all retained headless Lua behavior checks in integrated mode; move the former HTML source-integrity checks to the installed payload builder. Retire tests of the removed experimental frontends.

### ESSENCE Results fit beside the reader — 21 October 2026

At 80×24, word occurrences stay visible below the frequency table, including
with a reference. All comparison columns fit; long words and undefined measures
wrap. Sentence and TF-IDF tables also fit without sideways scrolling. Resizing
keeps focus, selected rows and export status. Summaries scroll independently.

### A genealogy opens the ESSENCE encyclopedia — 21 October 2026

The encyclopedia's first page is a small map of where its methods come from,
from the 1230 concordance and Mendenhall's 1887 word counting to TF-IDF (1972),
word vectors (2013) and Transformers (2017), each date sourced. ● marks what
ESSENCE runs; Enter on a method opens its entry.

### ESSENCE looks right in small windows and every theme — 21 October 2026

- Results keep their tables in view in small windows; summaries name the section
  ("Quality, from p. 84") instead of a corpus path.
- Radio choices use the theme's accent; sentence-length bars too.
- The longest sentences' beginnings end at a word with "…".
- Export buttons and the layout hint are compact.

### The maintainer's visual audit choices — 21 October 2026

- The reading line is 66 columns by default (was 72); `--width` still overrides it.
- Focus mode (`f`) hides the status line as well as headings, leaving only the text.
- The full status line and plain bold headings stay as they were.

### Less test-runner overhead in UI checks — 21 October 2026

- Run UI behavior checks on isolated asyncio loops in the normal application
  mode, avoiding per-task debug stack tracing. Keep every test and assertion,
  synchronization wait, worker check and cleanup.
- `PYTHONASYNCIODEBUG=1` retains the diagnostic tracing mode. No product code,
  dependency, CI job or ordinary suite command changes.

### Cleaner prompts and outline — 21 October 2026

Answering `/`, `gp` or `M` no longer leaves the question and answer on the
command line, and the outline panel is no taller than its contents.

### The guide and README describe today's reader — 21 October 2026

`sol guide` and the README now name complete search, `gp`, `s`/`S` with
Zathura, landmarks, notes, ESSENCE, themes, `sol-window` and `keys.json`; the
guide no longer says search stops at 20 passages or that `Ctrl-Q` quits.

### Cheaper verified reader startup — 21 October 2026

- Hash canonical bytes directly after UTF-8 validation; reduce path allocation
  and resolve the corpus boundary once per scan, retaining all document reads,
  hashes, parent-link checks and final generation checks.
- Defer optional book-shell imports; add an isolated fresh-process startup probe
  alongside the existing warm-process reader measurements.
- Source verification policy, CORE/reference contracts and caches are unchanged.

### Zathura highlights the passage and follows your reading — 21 October 2026

`S` now highlights the passage on the printed page, and the Zathura window it
opened follows the paragraph you are reading until you close it.

### Cheaper section view preparation — 20 October 2026

- Project styles and callouts together; reuse up to 256 immutable typography
  results per reader, keyed by exact Markdown and plain-text values.
- Scan ASCII source controls in bulk with the same Unicode refusal policy.
  Reference verification, export freshness checks and staged saves are unchanged.

### A moved key does nothing — 20 October 2026

A key moved away in `keys.json` no longer falls back to Vim's own meaning
(`gp` pasted and reported an error); it does nothing.

### Faster occurrence navigation — 20 October 2026

- Ctrl-N / Ctrl-P within the shown passage updates the exact cursor and search
  marks without rebuilding its Neovim buffer, in either reading mode.
- Keep source verification and staged saves on this path, including refusal,
  retry and history; avoid a redundant check during full view preparation.
- Extend the text-free timing probe to cover occurrence steps, paragraph moves
  across section boundaries and an outline jump on an explicitly chosen book.

### Your own reader keys — 20 October 2026

`~/.config/sol/keys.json` moves the reader's keys, for example
`{"version": 1, "keys": {"n": "J", "b": "K"}}`; `?` lists them.

### Named landmarks — 20 October 2026

`M` names the place you are reading and `L` lists your named places; Enter
opens one and `D` forgets it. They are the workspace's bookmarks, so names
made with the shell's `bookmark` appear too. Temporary `-n` sessions keep them
until the session ends.

### The printed page in Zathura — 20 October 2026

`S` opens the passage's printed page in a PDF viewer (Zathura when installed),
where it can be zoomed and read in context; pressing it again turns the same
Zathura window to the new page. It also works from the `s` popup. The viewer
shows SOL's verified copy of the PDF; `SOL_PDF_VIEWER` chooses another viewer.

### Complete reader search — 20 October 2026

- `/` reaches every matching passage and reports the total number of literal
  occurrences; the 20-passage ceiling is removed from the reader.
- Ctrl-N / Ctrl-P step through occurrences within passages and across sections,
  wrapping in both directions. The status line shows `N of M` for the opened match.
- Reuse text-keyed occurrence projections and align ordinary text directly to
  keep common-word searches responsive; Unicode fallback warnings remain explicit.

### Go to a printed page — 20 October 2026

`gp` asks for a printed page and opens the first paragraph on it, so a
citation such as "p. 240" is one step away.

### The opening screen says SOL's own name — 20 October 2026

The line *Science Organizes Logic* under the title is gone: the title is
SOL's recursive name, SOL ORGANIZES LOGIC, and the line contradicted it.

### Clearer help and outline in the reader — 20 October 2026

- `?` now groups the keys into Reading, Finding your way, Text, sources and
  notes, ESSENCE and Leaving; long descriptions wrap under their own column.
- `t` shows the outline as a centred panel with ▾/▸ for open and closed
  sections, ● on where you are, and each section's page on the right.

### An opening screen while SOL loads — 20 October 2026

Starting the reader now shows SOL's title, SOL ORGANIZES LOGIC, while
the book loads: beneath it Being (●) and Nothing (○) move into each other and
vanish into Becoming (◉), and part again. It uses the reader's theme, gives
way to any question SOL asks, and ignores keys pressed while loading.
`SOL_NO_SPLASH=1` turns it off.

### ESSENCE study interface and TF-IDF — 20 October 2026

- Calmer Experiment controls, conditional file/reference fields, taller catalog lists and corrected Encyclopedia help.
- Results omit unused reference columns, use singular input grammar, and keep source headings/pages visible alongside wrapping contexts. Spaces beside highlighted words survive folding; layouts reflow on resize using theme colors.
- TF-IDF is now a study: top terms per passage in reading order, then overall mean weights. Enter opens a passage in the reader; workspace artifacts retain the engine's checkable provenance.

### SOL's own themes and a reading window — 20 October 2026

- **Paper** and **Night** join the themes: SOL's own, from actualspirit.com —
  cream paper, ink and the Actual Spirit purple, or the site's dark band with
  lilac headings. `T` cycles Mocha, Latte, Paper, Night and Terminal; ESSENCE
  follows.
- **`sol-window`** opens the reader in a window of its own (foot, kitty or
  Alacritty) in Libertinus Mono, a monospaced book face bundled with SOL, on
  Paper. Your terminal keeps its own font.
- **Fixed:** at narrow widths the status line's page ran into the reading mode
  ("p. 7Continuous"); the section path now gives way instead.
- A saved `paper` theme now opens SOL's Paper (it meant Catppuccin Latte since
  this morning).

### Faster verified reader startup — 20 October 2026

Reader exports reuse the selection source/provenance guard directly instead of
constructing navigation sessions for every record. Verified-generation caching
reuses equal, detached JSON data, and export snapshots use a JSON copy instead
of per-object deepcopy. Full memory comparisons, final export checks and disk
fingerprint verification remain in place; no persistent Book index is added.

### Runnable TF-IDF engine and CLI — 20 October 2026

`sol essence tfidf` ranks terms per word-provider passage (or one whole UTF-8
file) and overall, with `--top-n` and `--json`. The dependency-free `tfidf-v1`
method declares raw-count TF, smoothed natural-log IDF and document L2
normalization. `sol essence check` recomputes saved results against explicit
current sources. The public Python API is ready for later TUI integration;
Methods and the TF-IDF encyclopedia entry document the shipped behavior.

### ESSENCE's Methods screen — 20 October 2026

Methods (`2`) is no longer a placeholder: it lists each study ESSENCE and
`sol essence` run, and shows what it takes, its settings, what it produces,
its limits and the command that runs it, with the matching encyclopedia entry.

### ESSENCE follows `T` — 20 October 2026

Switching the reader's theme with `T` now restyles an open ESSENCE too, within
half a second, instead of only the next time it opens.

### ESSENCE method descriptions — 20 October 2026

Bundled method descriptions now document word frequencies, comparison, sentence
lengths and every other `sol essence` operation, including inputs, settings,
artifacts, save locations, limits and CLI examples. The offline loader and
Markdown renderer are ready for the Methods screen; this change adds no UI.

### Every occurrence of a word in ESSENCE — 20 October 2026

A word's sources in ESSENCE now list every occurrence, not just the first in
each passage, each with the words around it; Enter opens that very occurrence
in the reader. Very common words list their first 1,000.

### Smaller changes — 20 October 2026

- Rechecked navigation refusal on current main: retained the existing staging fix and added coverage for tree/reverse moves, destination CORE/storage failures, and competing saves or stale generations during preparation; retry, history and UUID/codepoint resume are verified. Removed `study_open` is excluded; editor publication recovery and manual terminal limits remain documented.
- Encyclopedia excerpts starting mid-sentence now display a leading … without changing the stored quote; packaging checks verify the wheel’s GPL-3.0-or-later declaration and LICENSE payload.

### Catppuccin throughout — 20 October 2026

The reader's themes are now Catppuccin: **Mocha** (dark, the new default) and
**Latte** (light) replace Dark and Paper, and Terminal still uses your own
terminal colors. `T` cycles them. ESSENCE opens in the reader's theme, using
Textual's Catppuccin themes. If you saved `dark` or `paper` with
`sol --set-theme`, it now opens as Mocha or Latte.

### SOL is licensed under the GPL — 20 October 2026

SOL is now free software under the GNU General Public License, version 3 or
later; see [LICENSE](LICENSE). The book you read with it is not covered and is
never part of the repository.

### A modest ESSENCE methods encyclopedia — 20 October 2026

Encyclopedia (`1`) now browses nine bundled method entries: existing lexical,
prose and sentence operations, plus TF-IDF, word vectors and Transformers as
reading topics. Each has a short verbatim Wikipedia excerpt, contributor
attribution, CC BY-SA 4.0 link, article URL, access date and further reading.
The keyboard browser works offline without CORE or models. Graphs, review
states and a catalog CLI remain deferred (proposal §9).

### The note editor opens beside the text — 19 October 2026

`a` (and `e` in `c`) now opens the note editor beside the passage when there
is room, like the context panel, so the text you are writing about stays in
view. **Fixed:** the selection quoted above the editor lost every letter "s".

### Words in context in ESSENCE — 19 October 2026

A word's sources in ESSENCE now show the words around it and the passage's
heading and page, instead of a file path, so you can judge an occurrence
before opening it in the reader.

### Sentence lengths in ESSENCE — 19 October 2026

ESSENCE's Experiment screen now offers sentence lengths beside word
frequencies, for this passage, its section, the whole book or a text file.
Results shows how long the sentences are, how that varies by place in the
paragraph, and the twelve longest; Enter opens one in the reader, and
Alt-Left there returns. This replaces the reader's former `S`.

### Copying, quitting, the context panel and the status line — 19 October 2026

- `y` now copies to your system clipboard; it failed before because the reader
  hid your desktop session from the clipboard program. A selection may span
  paragraphs, and dragging with the mouse selects and copies on release.
  Where no clipboard program works, the terminal is asked instead (OSC 52).
- `q` and `Ctrl-q` no longer quit, so a stray key cannot end a reading
  session. Use `:q` or `:qa` to save your place and quit, or `:qa!` to quit
  without saving.
- `c` opens beside the text when there is room, with headed sections for
  footnotes, your notes, markers and the record, and note dates in local time.
- The status line shows where you are in the book (section titles and page),
  the reading mode, how far through the book you are, and how to find help
  and quit.
- `S` (sentence lengths) is gone from the reader; `sol essence sentences`
  still runs the study.

### Sentence studies over UTF-8 files and CORE providers — 19 October 2026

`sol essence sentences --file PATH [--span START END]` measures ordinary text
without a configured corpus. The Python sentence API accepts the word engine's
CORE/file providers and scopes; `sol essence check FILE --input-file PATH`
verifies file results against the caller's explicit source. Provider studies
use a v2 artifact with digests and original offsets, without input text or
local file paths. Spans retain only complete sentences; cut sentences are
reported as excluded. The original segmenter, v1 artifacts and reader `S`
remain unchanged. V2 allows 16 MiB of result/provenance data; v1 retains 1 MiB.

### Comparison and sources in ESSENCE — 18 October 2026

When ESSENCE compares a target with a reference, Results shows how much more
or less often each word occurs (a difference per 10,000 words and a log₂
ratio), says why a measure is undefined, and can export the table as CSV or
TSV. Below the table, the passages where the highlighted word occurs are
listed; Enter opens one in the reader, and Alt-Left there returns to where you
were. A running count can be cancelled. Quitting the reader while ESSENCE is
open now saves ESSENCE's state, and the reader's popups stay in the reader's
columns instead of covering ESSENCE.

**Fixed:** studies saved from ESSENCE (and the new exports) were written into
the reader's private temporary folder and deleted when the reader closed; they
now go to `~/.local/share/sol/studies` like the reader's own studies.

### Compare word rates and export verified tables — 19 October 2026

The UI-independent `compare_words` function reports a rate difference and
log₂ rate ratio for target/reference word frequencies, with explicit
denominators and undefined-value reasons. `sol essence words-export` verifies
a saved study against its CORE/file inputs before emitting CSV or TSV with
counts, rates, measures and provenance. There is no smoothing or significance
claim; the existing `sol.word-frequencies` v1 artifact stays unchanged.

### Slightly faster start — 19 October 2026

Starting `sol` read and checked the whole corpus twice in quick succession;
it now does so once, with the same checks. A page appears after about 0.86 s
instead of 0.95 s on the development machine.


### Word frequencies in ESSENCE — 18 October 2026

In ESSENCE's Experiment screen, choose what to count (this passage, its
section, the whole book or a text file) and, optionally, what to compare it
with, then press Count words. Results lists the words with counts and rates
per 10,000 words for both sides, says how many words each side has, and warns
when the two are not directly comparable. With a workspace, each count is
saved and can be checked later with `sol essence check`.

### ESSENCE opens beside the reader — 18 October 2026

`E` in the reader opens ESSENCE, a new Textual application, on the right of
the page; Alt-F makes it fullscreen and back, Alt-R returns to the reader, and
`q` closes it, leaving you exactly where you were reading. Its four screens
(Encyclopedia, Methods, Experiment, Results) are placeholders for now; the
first real experiment, word frequencies, comes next. ESSENCE needs the new
`essence` extra (`pip install 'sol-organizes-logic[essence]'`, or
`pipx inject sol-organizes-logic textual`); without it the reader works as
before and `E` says what to install.

### Count words through CORE or ordinary files — 18 October 2026

`sol essence words` and the UI-independent `analyze_words` function count a
target and optional reference with the term study's shared, unchanged Unicode
tokenizer. Results show tokens, types, absolute frequencies, explicit token
denominators and rates, with source IDs/pages/offsets and unequal-scope warnings.
Plain UTF-8 files work without CORE. The text-free `sol.word-frequencies` v1
artifact is checked by recomputation with `sol essence check`; changed corpus
generations or file bytes are refused. No interface or dependency is added.

### Split the Lua reader implementation — 18 October 2026

The Neovim entry now composes package-local text/view, panel, request, footnote,
personal-note and control modules. Reader behavior and controls are unchanged.
Modules load only beside the installed entry, and packaging checks cover every
Lua file plus a headless read from an installed wheel.

### Prepare private formula reviews — 18 October 2026

Checkout-only `scripts/formula_review_sheet.py` writes an offline HTML sheet
outside Git for math records needing visual review, including notes. Each item
shows exact typed text and all printed-page crops through the existing verified
source renderer. Interactive or individual human verdicts append to a private,
source-bound history; skip/resume, correction notes and integrity checks are
included. Nothing marks a record reviewed or changes canonical Markdown.

### Faster section moves — 19 October 2026

Moving to the next or previous section, opening a search result or going back
in history took 2.3–2.9 s on the real book, because each keypress re-read and
re-checked the whole corpus about nine times. It now takes about 0.4–0.5 s;
startup to the first view went from 1.8 s to 0.5 s. Every change to the corpus
files is still refused on each check; the full comparison of the corpus held
in memory now runs once per keypress, as approved (CORE §6).

### Read individual book footnotes — 18 October 2026

In `c`, Enter on a book footnote opens its own reading view, with ordered body
paragraphs, emphasis, attribution and review warnings. Enter follows a listed
further footnote; Backspace returns one panel, and Esc or `q` restores the exact
passage cursor and selection in either reading mode. Book notes, personal notes
and source context have separate headings. Each new note open checks the corpus;
cycles, missing links and presentation bounds have explicit refusals. No reading
visit or workspace data is saved by viewing a footnote.

### Edit your notes in the reader — 18 October 2026

In `c`, press `e` on one of your notes to revise it in the same editor as `a`,
or `r` to see its earlier versions. Each note now shows its revision and warns
when the passage has changed since you wrote it. Only a note's author can edit
it, a newer version saved elsewhere is never overwritten, and a save that
changes nothing adds no version. Before, editing needed `sol --shell`.

### Measure reader speed before optimising — 18 October 2026

`scripts/reader_timings.py` reports repeated Python reader timings with medians
and spread, using invented text by default or an explicitly supplied local
corpus. It measures loading, verification, payload/typography preparation and
real controller navigation, search, history and sentence study in temporary
workspaces. No Neovim/terminal speed claim, cache, runtime change or dependency
is introduced. Tests check reporting and isolation, not timing thresholds.

### Marking forms survive editor line-end trimming — 18 October 2026

Import accepts `EXCLUDE:` with or without its trailing space and restores source
whitespace trimmed before an added sentence break or at a passage end. A form
with every line `rstrip()`ped now round-trips to the same marks and scores.
Words, interior sentence spacing, source newlines and canonical text remain
protected; existing exported forms, review fields and segmentation are unchanged.

### Sentence marking in a text editor — 18 October 2026

`sol essence segmentation-export` makes a blind plain-text form from an
unmarked sample. Add Enter between sentences or give an exclusion reason;
`sol essence segmentation-import` creates a new review for `segmentation-check`
without editing JSON. Import preserves original spaces, Unicode and newlines,
refuses text/header/sample changes and names the passage and mismatch location.
Both output files are owner-only, outside Git and never overwrite a target.
The segmenter, sentence-study artifacts, CORE protocol, dependencies, sample-size
and quality-target decisions are unchanged.

### Hidden search marks stay hidden; the study starts where you are — 18 October 2026

After `Esc` hid the search marks, switching modes with `p`, focus with `f`, or
paragraphs with `b/n` brought them back; now they stay hidden until you open
another search result. `S` used to take the last paragraph SOL had saved as the
study's origin, not the one you had since moved to with `j/k`; it now uses the
paragraph under the cursor, so Alt-Left from a listed sentence returns there.
A new test confirms that selecting and copying text around footnote numbers,
accented and non-Latin characters and italics stays exact in both modes and at
narrow widths.

### Sentence-segmentation validation — 18 October 2026

`sol essence segmentation-sample` prepares a reproducible blind private form
for marking sentences, and `sol essence segmentation-check` reports exact
boundary misses, false splits, precision/recall and per-doctrine counts.
Samples retain source/generation bindings, require complete marks or explicit
exclusions, and are written owner-only outside Git without overwriting files.
Synthetic expected-failure cases record known rule limitations. The segmenter,
sentence-study artifacts, CORE protocol and dependencies are unchanged; a human
real-book error estimate and approval of sample size/quality targets remain open.
An unexpected doctrine path in a sampled study is refused with a clear error.

### A refused move no longer loses your place — 18 October 2026

Moving in the reader used to save the destination before its view was built.
If building it failed, the screen stayed where it was while the workspace and
the back-history already pointed at a passage you never saw, and quitting
resumed there. Now a move is saved only once its view is ready; a refused move
leaves the screen, the saved position and the history unchanged, and can be
retried. Opening a study sentence in the paragraph you are reading now makes a
history entry, so Alt-Left returns to where you were.

### First inquiry from the reader: sentence lengths — 17 October 2026

`S` in the reader measures the sentences of the loaded section through a new
ESSENCE study and lists the distribution, the means by place in the paragraph
and the longest sentences. Enter reads one of them; Alt-Left returns to where
you were. `sol essence sentences [--within PATH]` runs the same study from a
shell, and `sol essence check` verifies a saved one by recomputation. The
segmentation rules are declared in the artifact and were tuned on the book's
own citations, abbreviations and initials. Artifacts hold IDs, offsets and
digests, never book text, and are saved only for workspace sessions.

### Search matches marked in the passage — 17 October 2026

Opening a search result, or moving with Ctrl-N/Ctrl-P, marks every verified
match of the query in that passage with the theme's search colour; Esc hides
the marks. This restores what the earlier prompt_toolkit reader did. The
ranges come from the existing source-exact search projection, so a match that
cannot be mapped is reported, never guessed.

### Footnotes in the reader — 17 October 2026

`c` now shows each footnote's text, numbered as in the book. Before, it showed
only the converter's heading ("Note 99"), because a converted footnote keeps its
text in separate `note_paragraph` records that the reader never loaded. A
footnote's number is shown where the book prints it, as a dim superscript
(`Landen⁹⁵`, or `[k]` for lettered notes). The number is inline display text
only: it is not part of the passage, so search, selection and offsets ignore it.
Its position comes from the callout recorded in the canonical Markdown.

### Retyped mathematics in the local corpus — 17 October 2026

Thirty passages of the private corpus had their mathematics retyped from the
printed page as linear Unicode (`s = at²`, `dy/dx`, `(x + dx/2)(y + dy/2)`),
replacing converter output such as `xd y y d x … − − + 2 2 4`. The corpus is
not in Git; its `audit/math-retyping-2026-10-17.json` lists every before/after
pair. The passages keep `needs_visual_review` until a person confirms them
against `s`.

### Personal notes in the reader — 17 October 2026

Press `a` to write a note on the current passage without leaving the reader.
It is saved through the same workspace service as the shell's `note add`, with
your actor name, the passage's content digest and revision history; `c` lists
the passage's notes. A selection is shown as context but not stored. Drafts
survive closing the editor or a failed save. Temporary `-n` sessions refuse
notes. The reader's request handling now declares each action's field in one
table instead of a chain of special cases.

### Printed-source preview — 17 October 2026

Press `s` in the reader to see the printed source of the current passage: the
record's recorded region, cropped from the verified PDF snapshot, opens in a
separate image viewer (`SOL_IMAGE_VIEWER` overrides the desktop default), so
formulas whose typed transcription is unreviewed can be read as printed in any
terminal. The popup shows pages and transcription status; the reading position,
selection and workspace are untouched. The first-run import remembers the PDF;
existing setups use `sol --set-source-pdf PATH`.

### Reader themes — 17 October 2026

The reader has three presentation presets: **Terminal** (inherits the host's
colors; the default), **Dark** and **Paper**. Press `T` to cycle them for a
session, start with `sol --theme NAME`, or save one with `sol --set-theme NAME`.
Dark and Paper degrade to 256 colors or, on basic terminals, to Terminal with a
notice; `NO_COLOR` is honoured. Popups and the outline use a distinct panel color,
and Neovim's `~`/`@@@` filler markers are hidden. Saving a theme now preserves the
saved corpus pointer and vice versa. Canonical text, offsets and workspace
schemas are unchanged.

### Documentation consolidation — 17 October 2026

Adopt four human-facing design documents: [Architecture](docs/ARCHITECTURE.md),
[BEING](docs/BEING.md), [ESSENCE](docs/ESSENCE.md), and [CORE](docs/CORE.md).
The root README is a short setup/navigation gateway. Earlier guides, contracts,
research and root documents remain in the legacy archive (removed from the tree on 21 October 2026; in Git history),
with an integrity inventory and navigable historical links. This migration changes
documentation and its checks, not application behavior or data contracts.

### Reader consolidation — preceding implementation

Bare `sol` opens the single isolated Neovim reader. The earlier prompt_toolkit
fullscreen baseline is research-only, outside the installed package. Continuous
reading remains chapter/64-record bounded; `b/n` changes paragraphs and `p` toggles
paragraph/continuous mode. The outline is vertical; horizontal navigation is not
shipped. First interactive launch can import the exact audited PDF once. The
checkout installer includes all Python feature dependencies and handles native
requirements with consent. Existing corpus IDs, CORE v1 references and workspace
schemas are preserved.

## Earlier development history

The previous changelog is in Git history.
It includes superseded optional-reader and horizontal-tree descriptions, which
are historical changes rather than current feature claims.
