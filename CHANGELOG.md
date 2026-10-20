# Changes

## Unreleased

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

`sol analyze tfidf` ranks terms per word-provider passage (or one whole UTF-8
file) and overall, with `--top-n` and `--json`. The dependency-free `tfidf-v1`
method declares raw-count TF, smoothed natural-log IDF and document L2
normalization. `sol analyze check` recomputes saved results against explicit
current sources. The public Python API is ready for later TUI integration;
Methods and the TF-IDF encyclopedia entry document the shipped behavior.

### ESSENCE's Methods screen — 20 October 2026

Methods (`2`) is no longer a placeholder: it lists each study ESSENCE and
`sol analyze` run, and shows what it takes, its settings, what it produces,
its limits and the command that runs it, with the matching encyclopedia entry.

### ESSENCE follows `T` — 20 October 2026

Switching the reader's theme with `T` now restyles an open ESSENCE too, within
half a second, instead of only the next time it opens.

### ESSENCE method descriptions — 20 October 2026

Bundled method descriptions now document word frequencies, comparison, sentence
lengths and every other `sol analyze` operation, including inputs, settings,
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
- `S` (sentence lengths) is gone from the reader; `sol analyze sentences`
  still runs the study.

### Sentence studies over UTF-8 files and CORE providers — 19 October 2026

`sol analyze sentences --file PATH [--span START END]` measures ordinary text
without a configured corpus. The Python sentence API accepts the word engine's
CORE/file providers and scopes; `sol analyze check FILE --input-file PATH`
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
denominators and undefined-value reasons. `sol analyze words-export` verifies
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
saved and can be checked later with `sol analyze check`.

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

`sol analyze words` and the UI-independent `analyze_words` function count a
target and optional reference with the term study's shared, unchanged Unicode
tokenizer. Results show tokens, types, absolute frequencies, explicit token
denominators and rates, with source IDs/pages/offsets and unequal-scope warnings.
Plain UTF-8 files work without CORE. The text-free `sol.word-frequencies` v1
artifact is checked by recomputation with `sol analyze check`; changed corpus
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

`sol analyze segmentation-export` makes a blind plain-text form from an
unmarked sample. Add Enter between sentences or give an exclusion reason;
`sol analyze segmentation-import` creates a new review for `segmentation-check`
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

`sol analyze segmentation-sample` prepares a reproducible blind private form
for marking sentences, and `sol analyze segmentation-check` reports exact
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
you were. `sol analyze sentences [--within PATH]` runs the same study from a
shell, and `sol analyze check` verifies a saved one by recomputation. The
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
research and root documents remain in the [legacy archive](docs/legacy/README.md),
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

The [previous changelog](docs/legacy/root/CHANGELOG.md) is preserved byte-for-byte.
It includes superseded optional-reader and horizontal-tree descriptions, which
are historical changes rather than current feature claims.
