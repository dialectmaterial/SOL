# Changes

## Unreleased

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
