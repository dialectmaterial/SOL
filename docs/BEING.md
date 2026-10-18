# SOL BEING — Reading, Presentation, and Scholarly Workspace

**Status:** current implementation + explicitly marked decisions; 18 October 2026.  
**Repository baseline:** `main` at `1d200e4fcbff1ca69f48b5dc96c55765f215f303`.  
**Companions:** [Architecture](ARCHITECTURE.md) · [CORE](CORE.md) · [ESSENCE](ESSENCE.md).

**Implementation reviewed through:** `577166b` (17 October 2026). The baseline above is the original adoption snapshot; the implemented theme, source-preview, note, footnote, search-mark and sentence-study features below were added afterward.

## 1. Purpose and non-negotiable experience

BEING is the place to **read Hegel's *Science of Logic***, locate source evidence, think, mark, question, annotate, compare, and depart for/return from computation. It is not an ebook format, a terminal emulator, or merely a virtual filesystem. Its primary use case is a comfortable sustained reading session. A working structure tree, extensive keybindings and correct UUID handling are only foundations; an unpleasant reading surface is an unresolved product defect even when automated tests pass.

**Decision:** improve the existing Neovim reader before contemplating another engine. Do not demand perfection before developing one ESSENCE interaction. Reject both traps: endlessly building a reader without research operations, or shipping every new operation while neglecting what it feels like to read.

## 2. What is implemented

`sol` invokes a **single native Neovim 0.11+ reader** with a private SOL configuration. Personal Neovim/LazyVim settings are neither loaded nor changed. The former fullscreen prompt_toolkit reader was removed from the installed distribution but remains under `experiments/reader_surfaces/baseline.py` for controlled research. `sol --engine neovim` remains compatible syntax, not a distinct engine.

Python/CORE owns source verification, IDs, lineage, actions and workspace persistence. Neovim owns disposable buffers, layout, input, motions and visual styling. A view contains **at most 64 canonical paragraphs**, divided into bounded reading sections; the reading position is a UUID plus source-codepoint offset, *never* a Neovim buffer address or screen row. Reloading a section in the same native Neovim process preserves the semantic contract. The reader can display adjacent passages continuously or one passage at a time. The book is **not** one unbounded editor buffer.

The Lua implementation is split into package-local modules behind the small
`sol/terminal/neovim.lua` entry: `neovim_text.lua` validates Unicode/spans,
`neovim_view.lua` builds the page and maps exact source positions,
`neovim_panels.lua` owns popup lifecycle and result/source panels,
`neovim_requests.lua` owns the action channel and reloads,
`neovim_footnotes.lua` reads book notes, `neovim_notes.lua` edits personal notes,
and `neovim_controls.lua` wires actions, context, bindings and lifecycle.
`neovim_tree.lua` remains the outline. All are loaded by explicit paths beside
the installed entry, without searching personal Lua/runtime paths. This is an
implementation split only; controls, packets, drafts and reading behavior are
unchanged. Wheel and source-archive checks include every Lua asset, with a
headless reading check from a wheel installed in a temporary environment.

The reader presently uses a centered maximum width of **72 terminal columns** (configurable), native word-aware wrap, semantic emphasis/strong/code spans, headings, a source-context display and review warnings. It is a character-cell presentation, not proportional typesetting. It runs in capable terminal hosts including Alacritty and Kitty; terminal capability heuristics can choose italic or underline fallback. Three presentation presets (Terminal, Dark, Paper) are implemented; see section 4.

The current implementation also includes literal book search, source-positioned results, a dynamic outline/tree, selection and copy, markers, focus/paragraph modes, a session navigation trail, saved reading position, annotated workspaces, comparisons, notes and source-review operations. The most mature workspace operations are additionally exposed via `sol --shell`; not every operation has an equally convenient Neovim keybinding. Avoid claiming full GUI/TUI parity.

### Reading controls (current)

| Input | Function |
|---|---|
| `j/k`; `h/l`; `w` | Wrapped-line; character; forward-word motion |
| `Ctrl-D` / `Ctrl-U` | Half-screen scroll |
| `b/n` | Previous / next paragraph |
| `p` | Continuous / single-paragraph mode |
| `gg` / `G` | Start / end of *loaded section*, not entire book |
| `/` + Enter | Literal case-insensitive search across book; select result; its matches are marked, `Esc` hides the marks until the next result |
| `Ctrl-N` / `Ctrl-P` | Next / previous result paragraph |
| `Alt-Left` / `Alt-Right` | Session reading history back / forward |
| `v`, move, `Esc` | Transient selection within *one* source record |
| `y` | Copy selection or current passage; desktop clipboard provider depends on environment |
| `m1`–`m3`; `'1`–`'3`; `dm1`–`dm3` | Set, open, clear one of three paragraph markers |
| `t` | Dynamic structure tree (Vim-style navigation) |
| `c` | Separate book footnote list, workspace notes and source context; Enter on a book note reads it, `e` edits your personal note and `r` shows its versions |
| `a` | Write a personal note on this passage, saved in the workspace (`Ctrl-S` or `:w` saves, `Ctrl-C` discards) |
| `s` | Printed source of this passage (formulas), cropped from the verified PDF, in a separate image viewer |
| `S` | Sentence lengths in the loaded section (ESSENCE study); Enter reads a listed sentence, Alt-Left returns |
| `E` | Open ESSENCE beside the reader (needs the `essence` extra); in ESSENCE, Alt-F toggles fullscreen and Alt-R returns to the reader |
| `f` | Quiet focus mode; keep important warnings |
| `T` | Cycle Terminal / Dark / Paper theme for this session |
| `?`, `q` | Help / save position and quit |

`n` means *next paragraph*, **not** Neovim's default next regex match. `gg/G` operate only within the loaded section. Selections remain inside a single canonical passage and are not automatically saved as annotations. A note written with `a` attaches to the whole passage through the same workspace service as the shell's `note add` (actor, content digest, revision history); a selection is shown above the editor as context but is not stored, because no workspace schema records spans. Drafts survive closing the editor or a failed save, until saved or discarded with `Ctrl-C`. The `c` popup lists the workspace's notes on the passage; temporary `-n` sessions refuse personal notes. Footnotes are the edition's own notes, separate from yours: each footnote's number is drawn as a dim superscript (`⁹⁵`, or `[k]` for lettered notes) where the canonical Markdown records its callout. In `c`, move onto a book footnote and press Enter to read it in a separate view. The number is display only — it is not in `plain_text`, so search, selection and offsets ignore it. Search and passage navigation preserve source offsets as far as the verified projection allows.

**Book footnote reading (18 October):** `c` works from a cursor or a passage-local visual selection. Its book notes, personal notes and technical source context have separate headings. Enter on a book-note row opens only that note, with its canonical `note_paragraph` children ordered by `order`, original emphasis, per-paragraph attribution, review warnings and display-only callouts. Enter on a listed further footnote follows that link. Backspace returns to the preceding note at its earlier panel cursor, or to `c`; Esc or `q` returns directly to the exact passage cursor and selection in the same reading mode. Resizing closes the panel and restores the passage. Opening or following a note checks the source again and saves no reading visit or workspace data. A refused request leaves the preceding panel available; a reply received after that panel closes is ignored.

The note path is limited to eight distinct notes; links back to an open note are marked as cycles. A view accepts at most 64 body paragraphs, lists up to 128 further links, and refuses text over 1 MiB or a presentation over 4 MiB. Limits are disclosed rather than silently truncating source text. Missing/unlinked notes are refused without substituted text; the corpus contract already refuses broken canonical note links on load. Backspace revisits the checked panel already shown, while following a new link makes a new checked request. These are presentation defaults. Controller and headless Neovim checks cover both modes, forward/reverse selections, styling, callouts, nested links, refusal and narrow widths; sustained manual terminal reading remains untested.

**Adoption clarification:** use `j/k` for wrapped rows. Up/Down retain native Neovim buffer-line motion; they are not currently mapped to the same visual-row actions. The single vertical outline has no shipped horizontal-layout switch. No control behavior was changed by the documentation migration.

**Draft lifetime:** unsaved note drafts are process-local recovery state. Closing the note editor (including `:q!`) or a failed save keeps the draft available under `a` during that SOL session; quitting/restarting SOL does not durably save an unpublished draft. Save through `Ctrl-S` or `:w` before leaving SOL. Clipboard, viewer and Ctrl-S behavior still need the manual terminal checks described below.

**Refused moves (18 October):** every move in the reader (sections, `b/n` across sections, tree, markers, search results, history, study sentences) first accepts the position the screen shows, then prepares the destination's view, and saves the destination only once that view is ready. If preparation, a changed corpus or another session's newer save refuses the move, the screen, the saved position and the history stay where they were; the same key can be tried again. Another session's save is never overwritten: until SOL is reopened, moves keep being refused. A study sentence in the current paragraph is its own history entry, so Alt-Left returns to the earlier cursor. Tested with injected failures on every route; not yet exercised by hand in a terminal.

**Transient state (18 October):** marks hidden with `Esc` stay hidden through `p`, `f`, `b/n`, resizing and `T`; opening another search result marks its matches again. Nothing about this is saved. Selection and `y` copy the exact source text around footnote numbers, multibyte and combining characters and wrapped emphasis, forward and backward, in both modes and at narrow widths (headless Neovim tests). `S` takes the paragraph the cursor is in as its origin, so a study started after moving with `j/k` returns there with Alt-Left; running it saves no visit. Not yet checked by hand in Alacritty or Kitty.

**Editing notes (18 October):** in `c`, each workspace note shows its author, date and revision, and says when its passage has changed since it was written or when it was written on a retired record ID. `e` opens the note under the cursor (or the only one) in the same editor as `a`; `r` lists its versions, newest first. A save goes through the workspace's edit service: only the note's author can edit it, a newer revision saved from another session refuses the save, and so does a corpus that changed since the reader opened. The note keeps its ID, target and original source digest, so an edit never rebinds it to newer text; a save that changes nothing adds no revision. A refused save keeps the draft for the next `e`. Notes cannot be deleted, hidden or retracted; that needs a retention decision. Tested in headless Neovim and through the controller; not yet used by hand.

### Basic operations

```sh
python3 scripts/install.py --check   # Verify setup without installing
python3 scripts/install.py           # Install/update checkout; may offer native dependencies
sol                                  # Reader, remembered actor/workspace
sol -n                               # Temporary reader, no workspace/profile writes
sol --actor "Researcher" --workspace logic-study
sol --width 64                       # Adjust prose measure
sol --theme paper                    # Theme for this session: terminal, dark or paper
sol --set-theme dark                 # Remember a theme in ~/.config/sol/config.json
sol --set-source-pdf PATH            # Verify and remember the original PDF for s (first import does this)
sol --structure --depth 2            # Printable book structure
sol --dynamic-structure              # Standalone dynamic tree
sol --search "ground" --within /essence --word --limit 8
sol --passage RECORD_UUID --context 1
sol guide
```

First-run setup for this baseline accepts the **specific audited Cambridge/di Giovanni PDF only**, not arbitrary files. `sol --set-corpus /absolute/path/to/local-corpus` selects an already indexed corpus. Reading normally neither reruns PDF extraction nor accesses the network. See [CORE](CORE.md).

## 3. What makes this a scholarly workspace

**Canonical text and personal research are distinct.** The book is identity-managed local canonical Markdown and generated JSONL; the workspace is a separate local SQLite database of reader activity. Workspaces retain explicit actor labels (not authenticated accounts), checkpointed positions, bookmarks, attributed notes and revisions, comparisons/questions, review testimony and directed relations. An author's assertion is not book metadata; an ML output is not a reader-authored assertion.

A workspace is bound to the corpus identity and source fingerprint. New workspaces use **schema 3**; older supported versions can be opened without silent migration. Upgrades produce separate copies. Concurrent/stale revisions are refused rather than overwritten. Reading history in a session and durable checkpoint visits are separate. Existing notes and comparisons may refer to *live* records, not frozen historical quotations; after edits, disclose that distinction. A durable selected-span note with exact source-version binding is still **future work**.

Examples of available compatibility-shell operations (not necessarily Neovim shortcuts):

```text
bookmark add beginning
note draft
note list
note history NOTE_ID
note edit NOTE_ID
compare save examination UUID_A UUID_B --question "What is the relation?"
compare show examination
relate add UUID_A compares-with UUID_B --reason "A provisional observation"
review show
review queue --limit 10
workspace history --limit 10
workspace check
```

Unverified/flagged source material stays visible to the reader with warnings but does not become verified because it has been displayed. Notes from the translator or edition stay separate from Hegel's prose and personal annotations.

### Exports, backup, integrity

```sh
sol --workspace logic-study --workspace-export --export-format markdown > logic-study.sol-workspace.md
sol --workspace logic-study --workspace-export > logic-study.sol-workspace.json
# Source-aware backup/upgrade commands are documented through the installed `sol` help and workspace interface.
```

Workspace report exports retain references, questions, notes/revisions, reading state, attribution, source provenance and unresolved IDs; adding `--include-passages` includes the *current* canonical Markdown of referenced records, **not** historic text snapshots. Exports can include copyrighted and private material: keep out of Git. Workspace backup/upgrade operations produce validated separate SQLite copies and reject overwriting targets.

## 4. Theming and typography: next bounded task

**Decision:** implement exactly three shipped presets before introducing theme plugins or large theme catalogs:

| Preset | Intent | Technical rule |
|---|---|---|
| **Terminal** | Existing host's native appearance | Inherit foreground/background; use minimal highlight overrides |
| **Dark** | Quiet, carefully tuned TUI reading | Readable contrast and restrained differentiation of hierarchy, notes, search and warnings |
| **Paper** | Book-like page | Light paper-toned background with legible dark text and restrained accents |

**Implemented (17 October):** the three presets above. Python (`sol/terminal/theme.py`) owns the palettes as inert highlight data; the Lua reader validates group names and attributes again and sources no colorscheme file. Terminal clears the reader's colors so the host's foreground, background and 16-color palette show through. Dark and Paper use 24-bit color when `COLORTERM` declares it, a computed xterm-256 approximation otherwise, and fall back to Terminal with a visible notice on basic terminals. `NO_COLOR` removes Terminal's single color accent. Body text meets WCAG AAA (7:1) against page and panel; headings, warnings, status and search meet at least AA (4.5:1); tests enforce these ratios. The default is Terminal. `T` cycles presets for the session only; `sol --theme NAME` selects one for a launch and `sol --set-theme NAME` saves it in the existing `config.json` alongside the corpus pointer. Reading floats share the page color; popups and the outline use a distinct panel color; `~` end-of-buffer and `@@@` last-line markers are hidden. Themes never alter canonical text, offsets, selection identity or workspace data. **Not yet done:** the visual audit below (spacing, heading density, status-line weight, popup intrusion) and sustained manual reading trials in each preset.

Do not confuse installing a Neovim color scheme with designing a reading surface. Evaluate: paragraph spacing, inter-section gaps, measure, top/bottom breathing room, heading density, how emphasis maps to actual fonts, whether the always-visible status hints dominate, line-wrap behavior, warning visibility, tree/search popup intrusion and preservation of position after resizing. The present source defines a centered floating window without border and a verbose action statusline; these are concrete starting points for visual audit.

**Safety:** presentation styling must never change canonical Markdown, `plain_text`, passage UUIDs, offset mapping, selection content or workspace schema. Theme switching should be runtime-selectable and persist as a preference only through an explicit, simple config path; it must not modify user terminal themes or `~/.config/nvim`. Invalid/high-contrast or no-color terminals must degrade legibly. Test 80×24 and larger sizes, Alacritty, different fonts, Unicode and italics fallback.

### Design experiment before expanding features

The earlier `prompt_toolkit` surface was subjectively easier to read despite less functionality. Compare the historical baseline and current Neovim on **the same chapter**. Document why: use a friction log with (a) interruption point, (b) recovery effort, (c) spacing/typography issue, (d) a source or math issue, (e) one corrective change. Then implement small changes inside Neovim with regression tests. Resist another framework migration based on screenshots alone.

Checkout-only proofs include continuous terminal and offline self-contained HTML surfaces (under `experiments/reader_surfaces/`); these are **research comparisons, not installed alternative readers**. They demonstrate that source-bound selection can survive layout changes but do not establish long-term human comfort. A browser HTML proof is not a finished BEING GUI. If terminal-native reading proves intrinsically inadequate, use the existing CORE/reader-action separation to evaluate a typeset projection later.

## 5. Mathematical notation and source fidelity

The corpus contract supports separate `formula` records and prose passages with `contains_math: true`; this does not mean every supported type is present in the imported book. The recorded scratch import below found **no `formula` records** and 46 mixed main-text paragraphs containing mathematics, all `needs_visual_review`. **Implemented:** mathematical passages remain addressable and navigable; `s` renders printed evidence from the verified PDF without requiring Kitty; the older Kitty source-view integration also remains. **Not implemented:** faithful native Neovim rendering of arbitrary 2-D mathematical notation or a verified general LaTeX conversion pipeline.

**Near-term decision:** prioritize a **source-faithful formula preview**. From the current formula or mixed passage, offer a single action that displays the correct original crop/page (or a reviewed typed formula where available) and returns without losing passage and cursor position. For Alacritty, a separate local image/PDF/browser viewer is legitimate. Kitty can optionally offer enhanced panes, but formula access must not depend on Kitty. Avoid OCR hallucination: generated LaTeX is an unreviewed candidate, not authoritative source. Preserve exponent/fraction placement, printed/PDF page labels, transcription status, attribution, image provenance, and warning flags. Never replace ambiguous formula content with a guessed linear string. A linear transcription made by reading the printed crop (as on 17 October) is not a guess, but it is also not reviewed: it keeps the record's pending status, its audit lists the old and new text, and only a person's comparison against `s` may set `transcription_status` to `reviewed` (a canonical Markdown correction followed by reindexing, not workspace testimony).

**Implemented (17 October):** `s` in the reader shows the printed source of the current passage. Python captures the record against the verified corpus generation and a private, fingerprint-checked PDF snapshot, then renders the record's recorded bounding box on each source page at 144 dpi with a 6-point margin; a page entry without a box is rendered whole and labelled as such. A separate image viewer shows it (`xdg-open` or `open`, or the command in `SOL_IMAGE_VIEWER`), detached from the terminal, so it works in Alacritty and does not depend on Kitty. Without a graphical display, SOL shows the file path instead of guessing a viewer. The popup names PDF and printed pages and the transcription status, and says plainly that the printed source is authoritative for records flagged `needs_visual_review` or `needs_review`; number keys show further pages. Nothing moves the cursor, clears a selection or writes to the workspace. The converter's own `assets/*.png` facsimiles are not used, because the corpus manifest does not fingerprint them. The first-run import now remembers the verified PDF; existing setups use `sol --set-source-pdf PATH`. **Acceptance run (17 October, scratch import of the audited PDF):** the corpus has **no `formula` records**; the converter's short-block rule never fires on this book. Mathematics appears in 46 mixed main-text paragraphs, all `needs_visual_review`, 25 of them spanning two pages, and every source entry has a bounding box. Crops were checked by eye against the PDF for a mixed passage over two pages (polynomials, inline dy/dx), the Newton product passage (stacked fractions the typed text scrambles into `xd y y d x d xd y x y − − + 2 2 4`) and `−a · −a = +a²` (superscript lost in the typed text); all matched the print. A capture from a changed corpus generation is refused, and a missing PDF names `sol --set-source-pdf`. The whole-page fallback is exercised only by synthetic tests, since no real record lacks a box. The popup and viewer were then used in a real terminal session (17 October). **Retyped mathematics (17 October):** in the local corpus (main text and one footnote, 47 records with `contains_math`), 30 records whose typed mathematics was scrambled were retyped in canonical Markdown as linear Unicode (`a²`, `dy/dx`, `(x + dx/2)`), checked against the PDF crops; prose was untouched and record IDs, metadata and pages are unchanged. The corpus audit file `audit/math-retyping-2026-10-17.json` lists each change. They keep `needs_visual_review`, since no person has confirmed them yet; the edition's apparent misprint `f(x+1)` (for `f(x+i)`) is kept as printed. **Not demonstrable yet:** a human-reviewed formula, and native 2-D rendering of stacked notation.

### Private formula review sheet

Checkout-only `scripts/formula_review_sheet.py` prepares a private offline HTML
sheet beside its source-bound `sheet.json` and initially empty `verdicts.jsonl`.
It selects all canonical records with `contains_math: true` and
`transcription_status: needs_visual_review`, including note paragraphs, in
canonical order. This includes more than the 30 retyped records; repeat
`--record FULL_UUID` to select an explicit eligible subset. Each item shows its
ID, attribution, exact typed text and canonical Markdown, plus every recorded
source page, with PDF/printed labels. The script calls the existing
`SourceService.capture` and `render_region`: recorded regions are cropped, and
entries lacking a bounding box are explicitly labelled whole pages. Missing or
changed PDF/corpus data refuse generation; no guessed formula is supplied.

```sh
.venv/bin/python -B scripts/formula_review_sheet.py create \
  --corpus /absolute/path/to/local-corpus --output /private/path/formula-review
# Add --pdf /absolute/path/to/original.pdf if normal source discovery needs it.
# Open /private/path/formula-review/review.html, then record each human verdict:
.venv/bin/python -B scripts/formula_review_sheet.py review \
  --sheet /private/path/formula-review --reviewer "Your name"
.venv/bin/python -B scripts/formula_review_sheet.py record \
  --sheet /private/path/formula-review --record 1 --reviewer "Your name" \
  --verdict needs-correction --note "The exponent differs from the print."
.venv/bin/python -B scripts/formula_review_sheet.py check \
  --sheet /private/path/formula-review --corpus /absolute/path/to/local-corpus
```

The output's parent must already exist outside every Git checkout and the
canonical corpus; an existing sheet is never replaced. Directories are private
(700), files 600, and the temporary verified PDF/cache is removed. The sheet
does not load remote resources. `review` offers confirmed, needs correction,
skip and quit, and resumes pending items. Needs correction requires a note;
`record` can revisit an item by number or full ID. Every verdict is appended,
retaining earlier testimony, reviewer and UTC time, bound to the sheet's hash
and record text/metadata digests. The last verdict on an item supplies progress
counts; it is not approval to apply it. HTML/crop changes or malformed history
refuse further recording. `check --corpus` additionally refuses a different
canonical generation. Historical verdicts may still be recorded against the
unchanged sheet, without asserting that it matches a later corpus.

**This is a review aid only.** All verdicts start absent. Confirmed means the
named human recorded that verdict; it never sets canonical status to
`reviewed`, certifies a formula, or rewrites text. Applying testimony or changing
`transcription_status` in canonical Markdown remains a separate human-approved
step, followed by reindexing and checking. The private artifact format belongs
to this checkout script, not the CORE reference protocol or workspace schema.

Acceptance: demonstrate one reviewed simple formula, one complex or unreviewed Newton-related formula, a mixed prose/math passage, a missing source image, a corrected formula, and a stale reference; compare actual rendering against original PDF evidence.

## 6. BEING ↔ ESSENCE without terminal dogma

**Implemented:** CORE v1 envelopes can capture and check source identity. With `sol-kitty`, an optional private, one-exchange handoff launches an ordinary Zsh ESSENCE pane; BEING checks a proposed return and explicitly accepts it. This is not a general active-investigation workflow and is currently host-specific. It is not a reason to construct an ESSENCE terminal emulator.

The next development target is a **terminal-independent handoff interface**, using existing CORE references and guarded reader actions. Starting from the current chapter/passage, preserve an investigation origin and a way to return to the exact passage while retaining previous navigation state. Any new result must be a separately versioned, attributable **computation artifact**; do not auto-insert model interpretations into the authored workspace.

A narrow, demonstrable first scenario: read a chapter → select scope → initiate an ESSENCE sentence-length analysis → inspect measurements and supporting passage IDs → choose a result → return to its source in BEING → recover the original reading context. **Returning to the result's passage** and **returning to the previous reader position** are different operations; support or explicitly distinguish both rather than assuming one action solves both.

**Implemented (17 October), inside the reader process:** `S` runs ESSENCE's sentence study on the loaded section, with the current passage as its recorded origin, and shows the distribution, means by place in the paragraph and the twelve longest sentences. With a workspace the artifact is saved owner-only as `~/.local/share/sol/studies/sentences-*.sol-analysis.json` (never overwritten; temporary `-n` sessions save nothing). Enter opens a listed sentence at its first character through the ordinary guarded navigation — returning to the *result*; Alt-Left then restores the exact earlier position and selection — returning to the *reader*. The scope is the loaded section, not a free selection; the artifact can be checked later with `sol analyze check`. The Kitty exchange above is unchanged and remains the only cross-terminal path.

**Decision (maintainer, 18 October 2026): ESSENCE opens beside or over the reader, on demand.** ESSENCE will become a separate Textual application in a Neovim terminal buffer, beside the reader or fullscreen, started only when requested ([ESSENCE §4](ESSENCE.md#4-interaction-model-and-inquiry-contract)). Requirements on the reader side, **proposed** and to be marked implemented only when tested on real terminals:

- **Handoff:** entering ESSENCE carries the current source reference, the selection if any, and the exact reading position (UUID and codepoint). `S` already captures the position this way without saving a visit; it does not carry a selection.
- **Return:** leaving ESSENCE restores the reader's cursor, selection and mode; opening a result's source and returning to the earlier position stay two distinct operations, as above.
- **Focus:** one visible focus at a time; reader keys act only when the reader is focused, ESSENCE keys only in ESSENCE; Escape and quitting are never ambiguous across the two.
- **Key compatibility:** no existing reader key is remapped to make room for ESSENCE. **Decided 18 October 2026:** `E` opens ESSENCE (it was unmapped); `S` stays the quick sentence study.
- **Failure:** a launch failure, crash or refused result leaves the reader usable at the same place and shows the error.
- **Lifetime:** the reader starts no Textual or model process by itself; closing ESSENCE ends its process without affecting the reader.

**Implemented (18 October 2026), stage 1 shell:** `E` (in normal or visual mode) captures the reader's exact position and selection first, then asks Python to check the reader's position against the corpus and write a private context file (reference, cursor, the selection's offsets and digests, a heading label; no book text), then opens ESSENCE in a Neovim terminal float on the right, the page re-centring in the remaining columns. Below 100 columns it opens fullscreen. In ESSENCE, Alt-F toggles fullscreen and beside, Alt-R returns to the reader (leaving ESSENCE beside it, or hiding it when there is no room), and `E` in the reader returns to ESSENCE; these are Neovim terminal-mode mappings, and every other key goes to ESSENCE. ESSENCE survives section changes in the reader. Alt-R and leaving (`q`) return to that captured position and selection, endpoints and direction included (once; after a section change the reader stays where it is). Leaving ends the process, closes its window and re-widens the page; a process that fails to start or exits with an error is reported and the reader stays where it was. Without Textual, `E` explains how to install the extra. Tested in headless Neovim with a real terminal process; the real app was also run inside Neovim's terminal, with keys typed through terminal mode. **Not yet tried by hand** in Alacritty or Kitty.

## 7. Boundaries and known limitations

- Current normal reading is bounded by chapters/64-record sections, not a whole-book text buffer.
- No native cross-paragraph span selection; normal visual selection is transient and passage-local.
- Printed-source preview is implemented and was used in a real terminal (17 October); the reader judged the separate viewer helpful but awkward. Native 2-D mathematical typesetting remains unimplemented; retyped linear mathematics awaits human review.
- The outline/search/marker UI is functional but readability, styling, and mode transitions require actual use testing.
- Some scholarly actions are still most accessible through the optional compatibility shell: comparisons, reviews and relations. Writing, editing and viewing notes and their versions is in the reader; a note containing invisible control characters is edited through the shell.
- Footnote marks are inline display text and can push a wrapped line one cell further. Book-note panels have explicit depth, size and link bounds; they do not save a separate note-reading position or offer personal annotations on note paragraphs.
- Notes cannot yet anchor to a selected span; that needs a new workspace schema version.
- Comparison presentation is not yet a mature integrated side-by-side desk; authoring/version-binding details matter.
- The current Kitty exchange is host-bound; the terminal-independent research workflow remains proposed.
- A view that Neovim fails to display after Python accepted it (a crash, or a response over the 16 MiB channel budget) leaves the destination saved; the reader then exits, and reopening resumes there.
- Human reading acceptance is **not** established by headless tests, mock terminal checks, or a 24-passage HTML rendering benchmark.

## 8. Acceptance checklist for agents

A change may be called done only when (1) core corpus/ref/workspace tests pass; (2) recorded UUID+codepoint location survives theme switches, resizing, section transitions, and restart; (3) warnings and notes remain correctly attributed; (4) regular Alacritty and optional Kitty degrade gracefully; (5) reading in a chosen substantial *Science of Logic* chapter demonstrates fewer interruptions; (6) math preview and ESSENCE returns demonstrably preserve the right context; and (7) code and these documents agree on what is actually implemented.

**Source lineage:** consolidated from GitHub's reader view, Neovim implementation, reader actions, workspace plan/export, usage manual, handoff documentation, renderer experiments and dated discussions. Detailed historical experiments remain in `docs/legacy/` after migration.
