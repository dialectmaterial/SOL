# Reader surfaces: bounded proof and decision gate

15 October 2026. Baseline: `3993cca` (including the recent search, spacing,
navigation, and cache fixes). This is a research experiment, not an adopted
second interface or a change to the normal `sol --reader` command.

## Current recommendation

Keep the normal terminal reader. Trial the two checkout-only surfaces below on
the same section before choosing further work. There is no evidence yet that
either experimental surface improves sustained philosophical reading. Do not
adopt an engine or productize these proofs on the strength of screenshots.

Start with the short [Being–Nothing–Becoming reading exercise](READING_TRIAL.md).
Named samples now avoid UUID copying: `--trial beginning` selects the complete
first chapter with its remarks; `--trial opening` selects its short opening
before Remark 1. Extents come from supplied structure, not inferred philosophical
relations or a fixed paragraph count. These presets target the current English
Cambridge corpus; incompatible structure is refused, not silently substituted.

The [upstream audit](READER_ENGINES.md) covers Foliate/foliate-js, Readest,
Zathura, Okular, KOReader, Sioyek, and calibre. It distinguishes reusable engines,
external source viewers, and interaction inspiration. No third-party application
was forked, embedded, or installed. No permanent dependency was added.

## Run the proofs

Run from the repository root with its existing reader-enabled environment.
The existing `shell` extra supplies prompt_toolkit and CommonMark; the proofs
themselves are deliberately excluded from installed package discovery. No
launcher discovers a PDF, opens a personal workspace, or changes configuration.

The ordinary launch remains unchanged:

```sh
.venv/bin/python -B -m sol --reader -n --corpus local-corpus
```

For a same-start comparison, the experiment's `baseline` command opens that
existing reader directly at the selected passage, without a workspace:

```sh
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus --trial beginning baseline
```

This is the original `ReaderView`, not another reading engine. All three launches
start from the normal temporary reader's whole-work scope before opening the
chosen passage; section boundaries therefore do not unexpectedly stop baseline
navigation. Its normal search and navigation remain available: the sample does
**not** impose a stopping boundary on the baseline. Stay with the chosen sample
during the comparison; the continuous TUI and HTML below contain only that
bounded sample. Terminal commands accept `--width 72` after `baseline` or `tui`
to compare the same measure.

Continuous terminal proof (ordinary Alacritty or another capable terminal):

```sh
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus --trial beginning tui
```

Use `j/k`, arrows, Ctrl-D/U, `h/l`, and `b/n`. `v` selects inside a single
canonical passage; Escape clears it. Cross-passage selection is explicitly
refused. `c` reveals the current source context and `q` quits. The sample ends
at the selected extent; it is not a streaming whole-book reader. There is no persistent
position, search, annotation, or export UI in this terminal proof.

Offline typeset proof (choose a new output filename; existing files are refused):

```sh
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus --trial beginning html --output /tmp/sol-typeset-trial.html
xdg-open /tmp/sol-typeset-trial.html
```

This creates an owner-only, self-contained HTML file. It includes actual corpus
text, so keep it private and outside Git. No server is needed. Prose is continuous;
section labels appear when they change. Source context is toggled on demand;
review/fallback warnings remain outside that toggle. Available canonical notes
appear separately with attribution, not silently mixed into Hegel's prose.

Select inside one paragraph and choose **Export selected span**, or click text
and choose **Export clicked position**. These download local research JSON, not
annotations or workspace saves. Restore a packet through the file picker after
changing width/font size to check exact position and selection. Then independently
validate the download against the current local corpus:

```sh
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus validate /absolute/path/to/sol-research-selection.json
```

This only reports acceptance; it does not import anything into a workspace.
The wrapper is temporary test transport around the existing CORE reference and
TextSelection, not a new reference protocol. HTML restore checks the exported
snapshot; Python validation additionally checks the current corpus generation.
Regenerate an artifact deliberately after source corrections. A browser's local
Downloads location is its own setting; SOL does not choose or alter it.

For another section, replace `--trial beginning` with
`--start EXISTING_PASSAGE_ID_OR_PREFIX --count 24` before `baseline`, `tui`, or
`html`. Without either selector, the original first-24-record sample remains.
Use the same selector for all three launches. `--trial` cannot be combined with
`--start` or `--count`: a complete chapter is never silently truncated to fit a
default. `inventory` reports the resolved extent, pages, linked-note count and
corpus-generation binding for a named trial, without printing book text. The
HTML header and embedded inventory retain that extent. No IDs are
assigned, and none of these commands changes the normal SOL reader launch.

## What is preserved, and where the seam lives

The pipeline remains verified CORE Book → ReaderActions/ReaderState → semantic
typography → replaceable view. The new files live only in
`experiments/reader_surfaces/`; installed entry points, package dependencies,
CORE, workspace schemas, canonical Markdown, and UUID assignment are unchanged.

The terminal adapter maps each display boundary to an existing record UUID and
raw Unicode-codepoint offset. Presentation separators, padding, and warning rows
have no source identity. Adjacent passages are not converted into one canonical
mega-record. Styles reuse `map_typography` and word wrapping reuses `LineLayout`.
When adjacent passages change their supplied section heading, a neutral label
marks the transition beside the new prose. Labels wrap at word boundaries and
are skipped by source-cursor navigation; they cannot enter a selected span. This
is orientation within the reading flow, not a tree or a reconstructed ontology.

The HTML adapter emits escaped exact plain text with semantic `em`, `strong`,
and `code` wrappers, not privileged raw Markdown/HTML. Source paragraphs alone
are selectable. Browser DOM text must equal canonical plain text, byte-for-byte
after UTF-8 encoding, before any range is accepted. DOM UTF-16 positions become
Python-codepoint boundaries; split surrogate pairs, cross-record ranges, text
mismatches, malformed source bindings, and altered in-memory graphs are refused.
Repeated strings are located by offsets, not fuzzy substring matching.

Exports reuse the existing CORE version-1 envelope, requested/resolved IDs,
content digest, exact TextSelection fields and plain-text digest. Reading position
is an existing record plus source offset, never scroll pixels or an EPUB CFI.
Neither browser nor terminal writes workspace tables. Notes are separately
verified against CORE and retain their own attribution.

## Safety and explicit limits

The typeset document has hash-authorized fixed script/style blocks, no remote
fonts/scripts/images, and a restrictive CSP (`default-src 'none'`, no connection,
objects, base URL, or form submission). The browser check runs offline. Source
text cannot introduce executable tags or active links. Controls/bidi characters
that this proof cannot render faithfully are refused, never normalized away.

This does not sandbox browser extensions or a compromised host. A meta CSP does
not provide `frame-ancestors` or sandbox enforcement. Exports are neither signed
nor authenticated and contain no execution/write authority. Python's current
corpus check remains necessary before treating a browser packet as SOL context.

This is not full scholarly typesetting: math, tables, facsimiles, complex lists,
and future semantic styles need explicit additional work. Notes can be inspected,
but their spans cannot be exported by this proof. Cross-record selections are not
implemented. No annotation database, investigation ontology, comparison desk,
tree sidebar, ESSENCE method, or CONCEPT work was added.

## Evidence recorded in this pass

Source/API research is separate from execution evidence. None of the seven
upstream applications was run or compared in a sustained reading session.

- Unit/contract checks use invented public fixtures: source mappings, wrapping,
  neutral labels/separators, styled selections, Unicode, CORE generation/digests,
  detached graph refusals, source controls, notes, exclusive file creation, and
  non-mutation.
- Real Alacritty: a uniquely owned temporary window showed three adjacent
  records together. Programmatic keys exercised motion and one-record selection;
  native resizing reflowed it while preserving the exact selection/source offset.
  The inactive next record's review warning remained visible. Kitty state was
  removed, temporary fixtures were used, and no personal workspace was opened.
- Real browser: system Chrome 155.0.8059.79 with a disposable Playwright context,
  offline, loaded the generated file directly. Ninety-seven mapping/refusal checks
  included astral characters, combining diacritics, Greek/CJK/NBSP, styled DOM
  nodes, element endpoints, surrogate refusal, reverse selection, altered DOM,
  source-shaped script markup, and cross-record refusal. Resize/font changes,
  actual download/restore buttons, clearing stale selections, and Python packet
  validation passed. No nonlocal page-resource requests were observed.
- Visual inspection: synthetic continuous-terminal and browser screenshots were
  inspected. A private actual-Hegel artifact was also rendered and inspected:
  24 passages, nine notes, 116 italic spans, all 24 source nodes exact. This is
  layout inspection, not a claim of sustained scholarly reading.

One actual-Hegel sample had 44,064 source codepoints. Observed verified load was
0.2024 seconds; 72-column continuous layout took 0.135 seconds for 666 rows.
Initial HTML generation took 20.078 seconds and produced 142,257 bytes in that
measured build. These are one-run, warm-filesystem observations, not cold-start
or comparative benchmark scores. Small later presentation changes affect size.
The initial export bottleneck was repeated strict CORE capture/check of
whole-generation bindings for each passage/note. The bounded follow-up below
removes redundant checks without changing CORE. Ordinary reading does not
reopen/extract the PDF.

The initial suites collected 1,236 tests (61 added in that proof). All enabled checks
passed: the reader-enabled environment skipped five explicit host opt-ins; the
lean environment skipped 78 optional/host checks. The new Alacritty and browser
proofs passed separately after the final changes. These counts include the
existing regression/packaging checks; installed package discovery still excludes
the experiments. No new claim of manual verification is inferred from skips.
The local corpus manifest and index hashes are unchanged:

```text
corpus.json  3ac1f6dd1bbbc73124cff625cd3898adb76b91d4470083dde53a63e4421d8dab
index.jsonl a35f69ea855d9febb30d8e2a5863a5ee6bdb3b1a60e7c0efe1e336faf99c773c
```

Chrome is the only browser integration tested here. Firefox and other viewers
remain unverified. The complete upstream applications, screen readers, native
Wayland-only operation, and a sustained book/PDF comparison remain open.

## Follow-up: safe export latency and a fair control

The user has not yet tried the prototypes. This follow-up therefore removes
measured/reproducible obstacles, not purported human reading problems, and does
not choose an engine or change the normal reader.

Profiling the same 24 passages and nine notes found 66 full CORE snapshot
validations: capture followed immediately by a second receiver check for each
reference. Fresh export now retains CORE capture once per distinct requested
record, including linked notes, with only a render-local cache. It resolves
against an exporter-owned copied snapshot, verifies the existing envelope and
complete record binding, checks the convenience reader projection, and renders
from defensive copies. Detached alias chains, text, notes, and attribution are
refused. A final whole-graph comparison and source-file freshness check run
before any artifact is created; the cache is then closed and discarded, even on
failure. This is not a reusable trust cache or a new CORE batch API.

Imported packets still use the unchanged full `check_reference`. Protocol,
generation strictness, source codepoints, and workspace authority are unchanged.
The tests independently check generated packets through that original receiver.
As before, this detects integrity changes; it is not a lock, authentication, or
protection against a malicious host restoring indistinguishable bytes.

One unprofiled export of the same sample now took 9.611 seconds, versus the
previous 20.078-second observation. Matching instrumented profiles show 33,
rather than 66, full validations; profiled runtime changed from 43.027 to 23.465
seconds. Instrumented and uninstrumented times must not be compared directly.
These remain local warm-filesystem observations, not a universal speed claim.
Generation is still not instant; eliminating its remaining whole-corpus work
would need separately justified public CORE support, not a guard bypass.

The `baseline` launcher addresses a separate comparator defect: opening a record
from an empty reader previously restricted scope to its virtual leaf. The actual
24-record sample crosses two prefaces and the introduction, so that control would
have stopped after ten records. Initializing through ordinary public whole-work
reading actions before opening the chosen record now gives all three surfaces
the same normal scope and start. The original ReaderView is used unchanged;
`--count` still bounds only the experimental TUI/HTML surfaces.

The continuous TUI also marks supplied section changes with neutral headings,
so neighboring visible prose does not cross into another section anonymously.
Source selection, label skipping, long-heading wrapping and resize mappings are
covered by regression checks. The real Alacritty scenario now includes a visible
section change plus source-review warning while the earlier record is active.

Current suites collected 1,272 tests: all enabled checks passed, with five host
opt-ins skipped in the reader-enabled environment and 79 optional/host checks
skipped in the lean environment. This follow-up adds 36 regressions. Real
continuous Alacritty, existing-reader Alacritty and offline Chrome checks passed
separately. Source manifest/index hashes remain those recorded above. Tests and
programmatic host driving still do not establish sustained reading quality.

There is still no sustained human reading evidence or winning surface. The
normal reader, corpus, installed package, CORE and workspace schemas are unchanged.

## Follow-up: a source-bounded reading trial

The [reading exercise](READING_TRIAL.md) now starts in Being rather than the
prefaces, without requiring copied UUIDs. The `beginning` preset includes the
complete supplied first chapter, including remarks; `opening` stops before its
first Remark 1 and is explicitly not the complete Becoming section. Titles,
labels, parent relationships, source order and contiguous reader projection
define these edition-specific extents. Missing, duplicate, reordered or
incompatible structure is refused. No new IDs or inferred logical relations are
created. A chapter over the existing 64-record budget is refused, never cut off.

In the current corpus, `beginning` contains 55 paragraphs, 25 linked notes and one
source-review passage (printed 59–82 / PDF 132–155). `opening` contains three
paragraphs, no linked notes and no review warnings (printed 59–60 / PDF 132–133).
These counts are observations, not hardcoded selection rules. Inventory records
the existing IDs and corpus-generation binding; exported HTML also identifies
its extent visibly. This is experiment metadata, not a second CORE protocol.

Offline Chrome checks on both actual-source artifacts found every source node
exact, with 367 and 14 emphasis elements respectively. Width/font-size changes
preserved selection; the opening's actual downloaded packet passed independent
Python validation against the current corpus. The chapter retained all 25 note
occurrences and its warning. No remote resource requests occurred. Screenshots
were inspected, but this remains layout inspection, not sustained reading.

Thirty-seven additional regression tests cover structural selection, derived
bounds, source identity, CLI compatibility and private/inert HTML labels. The
isolated Alacritty resize/selection proof and 97-check browser proof passed again.
Host driving is programmatic; physical-keyboard reading remains untested. Source
manifest/index hashes and normal reader/workspace behavior remain unchanged.

## Decision gate and reading exercise

The engineering question is now testable; the reading question remains open.
Use the same difficult section in baseline, continuous TUI, and typeset HTML,
with an actual book/PDF/established reader as a comparator. Read for 30–45 minutes
per meaningful session rather than judging only initial polish.

Record concentration interruptions, context lost at paragraph boundaries,
typography/notes/source-review friction, relocation failures after returning,
and time spent recovering the earlier thought. No universal score is claimed.
The user decides which surface supports the argument.

Recommended next action: conduct that comparison, then choose whether to refine
continuous terminal reading, retain an optional typeset projection, or investigate
a narrowly pinned foliate-js adapter. Do not select a permanent GUI framework or
fork a reader yet. Adoption requires exact source identity, a measurable reading
benefit, and an accepted dependency/licence/maintenance plan.

## Reproduce the checks

```sh
.venv/bin/python -B -m unittest discover -s tests -p 'test_reader_surface_*.py'
SOL_TEST_LIVE_SURFACE_ALACRITTY=1 .venv/bin/python -B -m unittest discover -s tests -p test_reader_surface_alacritty.py
SOL_TEST_LIVE_SURFACE_BROWSER=1 SOL_PLAYWRIGHT_MODULE=/absolute/path/to/playwright .venv/bin/python -B -m unittest discover -s tests -p test_reader_surface_browser.py
```

The browser test requires an already installed Node/Playwright and Chrome
(`SOL_TEST_CHROMIUM` overrides `/usr/bin/google-chrome`). It never downloads a
browser. Host tests are opt-in; skipped tests are not live verification. All GUI
keys were programmatic; physical keyboard and sustained reading remain untested.
