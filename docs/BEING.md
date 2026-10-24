# SOL BEING — Reading, Presentation, and Scholarly Workspace

**Status:** current implementation and explicitly marked decisions; framed by the leading [SPECULATIVE](SPECULATIVE.md) document on 21 October 2026.  
**Companions:** [SPECULATIVE](SPECULATIVE.md) (leading) · [Architecture](ARCHITECTURE.md) · [CORE](CORE.md) · [ESSENCE](ESSENCE.md).  
**Original adoption:** 17 October 2026 at `main` `1d200e4`; features since then are recorded below with their dates.

## 1. Purpose and non-negotiable experience

**BEING as a logical division ([SPECULATIVE §4](SPECULATIVE.md#4-initial-repository-hierarchy)).** BEING is the reading environment and the immediate encounter with texts, including the Neovim reader. Its first-level divisions are **Quality, Quantity and Measure**. Which of today's reader, terminal and workspace modules belongs under which, if any, is to be argued from the text in the restructuring, never from word associations, and recorded in the [placement register](ARCHITECTURE.md#9-placement-register); nothing below presupposes a placement. SPECULATIVE's own example ([§6](SPECULATIVE.md#6-limits-of-the-logical-hierarchy)) notes that even the word tokenizer, used by ESSENCE today, might belong under a BEING determination once justified.


BEING is the place to **read Hegel's *Science of Logic***, locate source evidence, think, mark, question, annotate, compare, and depart for/return from computation. It is not an ebook format, a terminal emulator, or merely a virtual filesystem. Its primary use case is a comfortable sustained reading session. A working structure tree, extensive keybindings and correct UUID handling are only foundations; an unpleasant reading surface is an unresolved product defect even when automated tests pass.

**Decision:** improve the existing Neovim reader before contemplating another engine. Do not demand perfection before developing one ESSENCE interaction. Reject both traps: endlessly building a reader without research operations, or shipping every new operation while neglecting what it feels like to read.

## 2. What is implemented

`sol` invokes a **single native Neovim 0.11+ reader** with a private SOL configuration. Personal Neovim/LazyVim settings are neither loaded nor changed. An unusable editor executable is reported with a reinstall hint, including if it disappears between preflight and launch. The reader uses only its integrated mode; checkout surface experiments and the separate research-export mode have been removed. `sol` and `sol being` open it; there is no other engine.

Python owns source verification and IDs (CORE), lineage, actions and workspace persistence (BEING). Neovim owns disposable buffers, layout, input, motions and visual styling. A view contains **at most 64 canonical paragraphs**, divided into bounded reading sections; the reading position is a UUID plus source-codepoint offset, *never* a Neovim buffer address or screen row. Reloading a section in the same native Neovim process preserves the semantic contract. The reader can display adjacent passages continuously or one passage at a time. The book is **not** one unbounded editor buffer.

The Lua implementation is split into package-local modules behind the small
`sol/being/neovim/neovim.lua` entry: `neovim_text.lua` validates Unicode/spans,
`neovim_view.lua` builds the page and maps exact source positions,
`neovim_panels.lua` owns popup lifecycle and result/source panels,
`neovim_requests.lua` owns the action channel and reloads,
`neovim_footnotes.lua` reads book notes, `neovim_notes.lua` edits personal notes,
and `neovim_controls.lua` wires actions, context, bindings and lifecycle.
`neovim_tree.lua` remains the outline. All are loaded by explicit paths beside
the installed entry, without searching personal Lua/runtime paths. Wheel and
source-archive checks include every Lua asset, with a headless reading check from a wheel installed in a temporary environment.

The reader presently uses a centered maximum width of **66 terminal columns** (configurable with `--width`; the maintainer chose 66 over 72 and 80 in the visual audit), native word-aware wrap, semantic emphasis/strong/code spans, headings, a source-context display and review warnings. It is a character-cell presentation, not proportional typesetting. It runs in capable terminal hosts including Alacritty and Kitty; terminal capability heuristics can choose italic or underline fallback. Five presentation presets (Catppuccin Mocha, the default, and Latte; SOL's own Paper and Night; Terminal) are implemented, and `sol-window` opens the reader in its own window in a book face; see section 4.

The current implementation also includes literal book search, source-positioned results, a dynamic outline/tree, selection and copy, markers, focus/paragraph modes, a session navigation trail, saved reading position, annotated workspaces with notes, markers and named places, and printed-source views. Avoid claiming full GUI parity.

**Startup measurement:** the opening screen still covers a fully
verified corpus load and checked first view. The loader hashes the same raw
bytes it validates as UTF-8, and resolves the corpus boundary once per file
scan while resolving and checking each document anew. No source fingerprint,
reference check or final export check is skipped or newly cached. The optional
book shell imports only when used. `scripts/reader_timings.py --startup-only`
measures fresh application imports and dispatch to the first payload, using an
explicit corpus and new temporary workspace per run; the ordinary probe keeps
its existing warm-process measurements. Neither measures Neovim painting or
physical time to readable text; version probing and the opening screen are
replaced at the terminal boundary. Real-book medians and limits are in the
[handoff report](coordination/HANDOFF.md#faster-startup-to-readable-text--21-october-2026).

### Reading controls (current)

| Input | Function |
|---|---|
| `j/k`; `h/l`; `w` | Wrapped-line; character; forward-word motion |
| `Ctrl-D` / `Ctrl-U` | Half-screen scroll |
| `b/n` | Previous / next paragraph |
| `p` | Continuous / single-paragraph mode |
| `gg` / `G` | Start / end of *loaded section*, not entire book |
| `/` + Enter | Literal case-insensitive search across book; select result; its matches are marked, `Esc` hides the marks until the next result |
| `Ctrl-N` / `Ctrl-P` | Next / previous search occurrence, wrapping through the whole book |
| `Alt-Left` / `Alt-Right` | Session reading history back / forward |
| `v`, move, `Esc` | Transient selection; notes and `E` take one passage, `y` may span several |
| `y` | Copy the selection (exact source text, paragraphs joined by a blank line) or the current paragraph to the system clipboard |
| Mouse | Wheel scrolls; dragging selects, and the selection is copied when the button is released |
| `m1`–`m3`; `'1`–`'3`; `dm1`–`dm3` | Set, open, clear one of three paragraph markers |
| `M`; `L` | Name the current place; list named places (Enter reads one, `r` renames it, `D` forgets it, `o` toggles name/book order for this session). They are the workspace's named bookmarks, including any made by earlier versions; a temporary session keeps them until it ends |
| `t` | Dynamic structure tree (Vim-style navigation) |
| `c` | Beside the text when there is room: pages, footnotes, your notes, markers and the record; Enter on a footnote reads it, `e` edits your note and `r` shows its versions |
| `a` | Write a personal note on this passage, saved in the workspace (`Ctrl-S` or `:w` saves, `Ctrl-C` discards) |
| `gp` | Go to a printed page: type its number (the status line shows the page you are on) |
| `s` | Printed source of this passage (formulas), cropped from the verified PDF, in a separate image viewer |
| `S` | The whole printed page in a PDF viewer (Zathura preferred) with the passage highlighted, to zoom and read it in context; Zathura then follows the passage you rest on until it is closed; also from the `s` popup |
| `E` | Open ESSENCE beside the reader (needs the `essence` extra); in ESSENCE, Alt-F toggles fullscreen and Alt-R returns to the reader; a word's source chosen in ESSENCE opens here, and Alt-Left returns |
| `f` | Quiet focus mode: hides headings and the status line, keeps important warnings |
| `T` | Cycle Mocha / Latte / Paper / Night / Terminal for this session |
| `?` | Help |
| `sol --shell` | A minimal command interface for browsing the book (`ls`, `cd`, `tree`, `read`, `cat`, `search`, `open`, `context`, `info`, `guide`); it uses no workspace and saves nothing |
| `:q`, `:qa` | Save the exact position and quit (`q` and `Ctrl-q` only say so) |
| `:qa!` | Quit without saving the current position |

`n` means *next paragraph*, **not** Neovim's default next regex match. `gg/G` operate only within the loaded section. Selections are not automatically saved as annotations; one that spans paragraphs can be copied, but notes and ESSENCE take a single passage. Search and passage navigation preserve source offsets as far as the verified projection allows.

**Named landmarks:** in `L`, `r` prompts with the selected landmark's current
name. Names use 1–80 characters of ordinary text after trimming surrounding
spaces; empty names, control/invisible formatting characters and reserved `sol:`
names are refused. Renaming to another landmark's name is refused; keeping the
same name leaves it unchanged. Rename preserves the saved target, authorship and
timestamps in one transaction, including when the target passage is unavailable;
a failed rename retains the old landmark. `o` switches between name order (the
default) and the passages' order across the whole book. Retired targets follow
their live passage; landmarks at the same passage use name order, and unavailable
passages come last in book order. The order lasts only for the reader session,
with nothing new saved in the workspace. Naming, renaming and sorting leave the
reading position unchanged. The three quick markers keep their existing controls.

**Your own keys:** `~/.config/sol/keys.json` (under `XDG_CONFIG_HOME` when set) moves reader keys: `{"version": 1, "keys": {"n": "J", "b": "K"}}` makes `J` do what `n` does, and `n` then does nothing. Keys are written in Neovim's notation (`<C-n>`, `gp`); two keys can swap. Only reader keys move, not keys inside panels such as Enter or `D`. Checked in a real terminal on the book (tmux, 20 October): `/` with "770 matches in 305 passages", `Ctrl-N` about 0.25 s within a passage and about 1 s to the next, `gp`/a remapped `P` to pages 100, 240 and 500, `M`/`L` naming, listing and reopening, and `S` opening one Zathura window that the next `S` turned from PDF page 158 to 372. `?` lists your keys under their own heading, and a key SOL does not use is named in a warning. A malformed file stops SOL with its path rather than guessing. The file is data passed to the private Neovim configuration; it cannot run commands, and the user's own Neovim configuration still never loads.

**Complete book search:** `/` lists every matching passage and gives the total
occurrence count. Enter opens a passage's
first occurrence; `Ctrl-N` / `Ctrl-P` visit individual occurrences in source
order, across paragraphs and loaded sections, wrapping in both directions. The
status line shows the opened match as `12 of 87` while its search marks are
visible. `Esc` hides the marks and count. Search remains literal,
case-insensitive NFC/casefold substring matching, excluding generated facsimile
captions. A Unicode fragment or a match across an excluded caption can have no
exact contiguous source span: it still counts and has its own visit, at the
passage start with the existing projection warning, without a guessed highlight
or source offset. Occurrence data is transient, reused only while the query and
source text values agree; opening results still verifies the canonical source
and stages the destination before saving. Automated controller and headless
Neovim checks cover these behaviors; sustained manual reading remains untested. marks hidden with `Esc` stay hidden through `p`, `f`, `b/n`, resizing and `T`; opening another search result marks its matches again. Nothing about this is saved.

**Whole words in search, and how ESSENCE counts words.** `/` in the reader always matches substrings. `sol --search QUERY --word` and the shell's `search QUERY --word` match whole words: the match must not be preceded or followed by a Unicode letter, digit or underscore. That rule is not ESSENCE's word unit. ESSENCE's tokenizer keeps an internal apostrophe in a word, ignores numbers and splits at digits. So in an invented line `The concept’s 2nd`, whole-word search finds `concept`, `2nd` and the literal `concept’s`, while ESSENCE counts `concept's` and `nd`. ESSENCE also writes the curly apostrophe as `'`, which reader search does not do: searching `concept's` with a straight apostrophe will not find text printed with a curly one. Both rules are kept on purpose for now: the reader finds literal occurrences, ESSENCE declares an analytical unit. The measured differences on the book and the options are in [WORD_UNIT](coordination/restructuring/WORD_UNIT.md); which rule the reader should follow is an open maintainer decision.

**Navigation latency:** `Ctrl-N` / `Ctrl-P` within the passage
already shown sends a checked position and search-mark update, keeping the
Neovim buffer, layout, typography and callouts. It works in both reading modes;
a changed reading mode, theme, focus or warning uses full view preparation.
Every step still verifies the source, accepts the outgoing cursor and stages
the destination before the guarded save. A refused update preserves the shown
view, accepted position and history, and can be retried. Cross-passage and
section moves retain full destination preparation, which avoids one redundant
active-reference check already performed by the payload validator. No source
trust is cached across actions. Full views parse each passage once for styles
and callouts. Each reader retains at most 256 immutable typography projections,
keyed by exact Markdown and plain-text strings; a changed value is projected
again, and every export still checks its source and current generation. Source
safety scans keep the same Unicode control policy while scanning ASCII in bulk.
`scripts/reader_timings.py` measures same-passage
occurrences, section changes, paragraph moves across a section boundary and an
outline jump against an explicit local corpus, using temporary workspaces and
text-free reports. Its controller times exclude Neovim IPC and terminal painting;
headless checks separately verify cursor updates without rebuilding the buffer.
**Sections prepared ahead:** while the opening screen shows, the reader also
builds the sections before and after the first one, and after each section
change it builds the new neighbours one at a time while no request is waiting.
A prepared section is used only for the same section, width, emphasis and
theme, and only inside an action whose fresh CORE capture rechecks the corpus
files and must equal the prepared record's checked reference; otherwise the
section is built as before. On the book (23 October) this cut a section change
from about 430 to 275 ms of Python time, for about 0.3 s more opening screen.
The rest is CORE's per-check file verification (CORE §5), unchanged.
**Measured on screen (23 October, tmux, 100×36, the book):** from key to the
new section's text, `]c`/`[c` took 1.16 s before sections were prepared ahead,
0.83 s after, and 0.56 s once they used the action channel. Until then they
restarted Neovim for every section (a variable lost when the Lua reader was
split into modules on 18 October; `n`/`b` across a boundary were unaffected).
Of the 0.56 s, Python takes about 0.52 s, mostly CORE re-hashing the corpus
files on each check, and Neovim decodes and draws in about 0.04 s. Opening to
readable text takes about 2.0–2.3 s.

**Book footnote reading:** Footnotes are the edition's own notes, separate from personal notes. Each number is a dim superscript (`⁹⁵`, or `[k]` for lettered notes) at its canonical Markdown callout. The number is display only, absent from `plain_text`, so search, selection and offsets ignore it. `c` works from a cursor or a passage-local visual selection. Its book notes, personal notes and technical source context have separate headings. Enter on a book-note row opens only that note, with its canonical `note_paragraph` children ordered by `order`, original emphasis, per-paragraph attribution, review warnings and display-only callouts. Enter on a listed further footnote follows that link. Backspace returns to the preceding note at its earlier panel cursor, or to `c`; Esc or `q` returns directly to the exact passage cursor and selection in the same reading mode. Resizing closes the panel and restores the passage. Opening or following a note checks the source again and saves no reading visit or workspace data. A refused request leaves the preceding panel available; a reply received after that panel closes is ignored.

The note path is limited to eight distinct notes; links back to an open note are marked as cycles. A view accepts at most 64 body paragraphs, lists up to 128 further links, and refuses text over 1 MiB or a presentation over 4 MiB. Limits are disclosed rather than silently truncating source text. Missing/unlinked notes are refused without substituted text; the corpus contract already refuses broken canonical note links on load. Backspace revisits the checked panel already shown, while following a new link makes a new checked request. These are presentation defaults. Controller and headless Neovim checks cover both modes, forward/reverse selections, styling, callouts, nested links, refusal and narrow widths; sustained manual terminal reading remains untested.

**Native motions and outline:** use `j/k` for wrapped rows. Up/Down retain native Neovim buffer-line motion; they are not currently mapped to the same visual-row actions. The single vertical outline has no shipped horizontal-layout switch.

**Help and outline:** `?` groups the keys under Reading, Finding your way, Text, sources and notes, ESSENCE and Leaving, with headed sections and descriptions that wrap under their own column. `t` opens the outline as a centred panel at most 84 columns wide with ▾/▸ for open and closed branches, ● and the heading colour on the current section, and each section's printed page at the right; titles too long for a line end in an ellipsis. Screenshot-checked in foot on the book.

**Opening screen:** while the reader loads the book and prepares its first view, the terminal shows SOL's title (the maintainer's SOL / ORGANIZES / LOGIC lettering, SOL's recursive name) in the reader theme's colours. Beneath it the first movement of the *Logic* plays: the full ● of Being and the empty ○ of Nothing travel toward each other, vanish into ◉, Becoming, and part again, while the words *Being · Nothing · Becoming* light in turn. It is drawn on the alternate screen by one thread from the moment the reader is chosen until Neovim takes the screen, which draws over its last frame. It steps aside for any question (actor, workspace, first corpus) and for errors, which print on the ordinary screen. Keys typed meanwhile are not echoed and are discarded, so they cannot act in the reader. Small terminals get a compact title and an animation track that fits their columns; `SOL_NO_SPLASH=1` turns it off. Measured with Codex's #47 on this machine: about 1.2–1.8 s before Neovim starts.

**Refused moves:** every move in the reader (sections, `b/n` across sections, tree, markers, search results, history and sources opened from ESSENCE) first accepts the position the screen shows, then prepares the destination's view, and saves the destination only once that view is ready. A jump within the current paragraph is its own history entry, so Alt-Left returns to the earlier cursor. On refusal the shown view and history remain in place; the outgoing displayed cursor may already be checkpointed. There is no claim of one transaction across that checkpoint and the destination. A recoverable preparation/storage failure permits retry, history return and reopen at the accepted UUID/codepoint. Another session's newer save remains authoritative and is never overwritten; moves stay refused until SOL is reopened. A stale generation requires resolving the corpus mismatch before retrying. Editor publication failures have the §7 recovery limit.

Controller tests inject failures in destination view preparation, position capture and storage, and real competing saves and generation changes during preparation after the outgoing checkpoint. Forward, reverse, tree and ESSENCE-source routes are covered; the next-payload probe passes with the existing staging implementation. These are synthetic checks, not manual terminal acceptance; no new Alacritty/Kitty acceptance is claimed. The absent sentence-study reader route (`study_open`) is excluded.

**Selection and clipboard:** `y` and a mouse selection copy to the system clipboard. Python picks the program from the real session before Neovim's environment is isolated (`wl-copy` on Wayland, else `xclip` or `xsel` on X11, `pbcopy` on macOS) and hands it the variables it needs, such as the real `XDG_RUNTIME_DIR` that holds the Wayland socket. Without such a program, or when it fails, the reader asks the terminal through OSC 52 and says so. Copying gives exact source text: footnote numbers and line wrapping are not copied, a selection end on a blank line or heading moves to the nearest prose, and paragraphs are joined by a blank line. Selection and `y` copy the exact source text around footnote numbers, multibyte and combining characters and wrapped emphasis, forward and backward, in both modes and at narrow widths (headless Neovim tests). Not yet checked by hand in Alacritty or Kitty.

**Quitting:** `q` and `Ctrl-q` only show quitting instructions, since they are easy to hit by accident: `:q` or `:qa` (also `:wq`, `:x`) save the exact position, a selection included, and quit; `:qa!` still quits without saving. Popups, the outline and ESSENCE keep `q` for closing.

**Panels and status line:** the `c` panel opens beside the page when the reader's columns leave at least 34 spare (the page moves left; the panel takes at most 64 columns and the page's height), and over the page when they do not; footnotes, search results, help and the note editor (`a`, `e`) open the same way; the editor then takes the page's full height. The panel names the passage, its place in the book and its pages, then Footnotes, Your notes (dates in local time), Markers and About this text as separate headed sections. The status line shows the cursor's place in the book (a breadcrumb of section titles and the page), the reading mode, focus, how far through the book the cursor is, and `? keys · :q quit`. Clipboard, quitting and panel placement are tested in headless Neovim and through a real session in tmux on the book (copy read back with `wl-paste`, `:q` exit 0, panel placement); not yet checked by hand in Alacritty or Kitty.

**Personal notes:** `a` writes a note on the whole passage through the workspace service (actor, content digest, revision history). A selection appears above the editor as context but is not stored: no workspace schema records spans. `Ctrl-S` or `:w` saves; `Ctrl-C` discards. Temporary `-n` sessions refuse personal notes. In `c`, each workspace note shows its author, date and revision, and says when its passage has changed since it was written or when it was written on a retired record ID. `e` opens the note under the cursor (or the only one) in the same editor as `a`; `r` lists its versions, newest first. A save goes through the workspace's edit service: only the note's author can edit it, a newer revision saved from another session refuses the save, and so does a corpus that changed since the reader opened. The note keeps its ID, target and original source digest, so an edit never rebinds it to newer text; a save that changes nothing adds no revision. A refused save keeps the draft for the next `e`. Notes cannot be deleted, hidden or retracted; that needs a retention decision. Tested in headless Neovim and through the controller; not yet used by hand.

Unsaved note drafts are process-local recovery state. Closing the note editor (including `:q!`) or a failed save keeps the draft available under `a` during that SOL session; quitting/restarting SOL does not durably save an unpublished draft. Save through `Ctrl-S` or `:w` before leaving SOL. Clipboard, viewer and Ctrl-S behavior still need the manual terminal checks described below.

### Basic operations

```sh
python3 scripts/install.py --check   # Verify setup without installing
python3 scripts/install.py           # Install/update checkout; may offer native dependencies
sol                                  # Reader, remembered actor/workspace
sol -n                               # Temporary reader, no workspace/profile writes
sol --actor "Researcher" --workspace logic-study
sol --width 64                       # Adjust prose measure
sol --theme paper                    # Theme for this session: mocha, latte, paper, night or terminal
sol-window                           # The reader in its own window: Libertinus Mono, Paper
sol --set-theme mocha                # Remember a theme in ~/.config/sol/config.json
sol --set-source-pdf PATH            # Verify and remember the original PDF for s (first import does this)
sol --structure --depth 2            # Printable book structure
sol --dynamic-structure              # Standalone dynamic tree
sol --search "ground" --within /essence --word --limit 8
sol --passage RECORD_UUID --context 1
sol guide
```

First-run setup accepts the **specific audited Cambridge/di Giovanni PDF only**, not arbitrary files. `sol --set-corpus /absolute/path/to/local-corpus` selects an already indexed corpus. Reading normally neither reruns PDF extraction nor accesses the network. See [CORE](CORE.md).

## 3. What makes this a scholarly workspace

**Canonical text and personal research are distinct.** The book is identity-managed local canonical Markdown and generated JSONL; the workspace is a separate local SQLite database of reader activity. Workspaces retain explicit actor labels (not authenticated accounts), checkpointed positions, bookmarks, attributed notes and revisions, comparisons/questions, review testimony and directed relations. An author's assertion is not book metadata; an ML output is not a reader-authored assertion.

A workspace is bound to the corpus identity and source fingerprint. New workspaces use **schema 3**; older supported versions can be opened without silent migration. Upgrades produce separate copies. Concurrent/stale revisions are refused rather than overwritten. Reading history in a session and durable checkpoint visits are separate. Existing notes and comparisons may refer to *live* records, not frozen historical quotations; after edits, disclose that distinction. A durable selected-span note with exact source-version binding is still **future work**.

Personal work is written from the reader: notes (`a`; edits and versions in `c`), quick markers (`m1`–`m3`) and named places (`M`/`L`). Comparison groups, review testimony and relations stored by earlier versions stay in the database and in exports; the shell commands that created them were removed on 21 October 2026, and `--review-queue` still lists canonical pending transcriptions.

Unverified/flagged source material stays visible to the reader with warnings but does not become verified because it has been displayed. Notes from the translator or edition stay separate from Hegel's prose and personal annotations.

### Exports, backup, integrity

```sh
sol --workspace logic-study --workspace-export --export-format markdown > logic-study.sol-workspace.md
sol --workspace logic-study --workspace-export > logic-study.sol-workspace.json
# Source-aware backup/upgrade commands are documented through the installed `sol` help and workspace interface.
```

Workspace report exports retain references, questions, notes/revisions, reading state, attribution, source provenance and unresolved IDs; adding `--include-passages` includes the *current* canonical Markdown of referenced records, **not** historic text snapshots. Exports can include copyrighted and private material: keep out of Git. Workspace backup/upgrade operations produce validated separate SQLite copies and reject overwriting targets.

**Storage rules.** Each workspace is one SQLite file in `$XDG_DATA_HOME/sol/workspaces` (default `~/.local/share/sol/workspaces`; `--workspace-dir` selects another), outside the canonical book and never synchronized to Git or a service; foreign keys are enforced on every connection. Schema 2 added annotation history and editing; schema 3, which new workspaces use, adds checkpoint-bound reading positions. Recognized schema 1 and 2 files open in their own format, and unrecognized or incompatible files are refused, with no migration on ordinary open. `--workspace-backup FILE.sqlite3` takes SQLite's online backup, validates it and publishes it without overwriting anything (the parent directory must exist; files are mode `0600`); `--workspace-upgrade FILE.sqlite3` migrates only a separately named, validated copy, leaving the original and any open session untouched, and an upgraded legacy note keeps the body available at upgrade as its baseline, not a reconstructed history. JSON and Markdown exports go to standard output only, add no reading activity, and keep schema-2/3 `annotation_history` without fabricating it for schema 1; use the `.sol-workspace.json`/`.md` suffixes, which Git and release archives ignore. Personal and canonical Markdown in a report is shown literally in fenced blocks (links and images are inert text), metadata in code spans, unsafe controls as visible escapes. Review testimony binds only the inspected Markdown digest and the manifest's declared PDF fingerprint, not attribution, page labels, rectangles or image bytes; testimony on a retired reference is conservatively stale, and exports and `--workspace-check` disclose this binding rather than repair it. **Listing and removing workspaces:** `sol --workspace-list` and `sol --workspace-delete NAME` need no reader, actor or corpus (`--workspace-dir` and `--json` apply). Close the workspace everywhere first. Deletion acts at once, without a second confirmation: it removes the workspace from normal use, clears launch preferences that point to it, and keeps the unchanged database in a private subdirectory of `workspaces/.trash/`, printing the recovery path (`recovery_path` in JSON); actor profiles and the corpus are untouched, and missing, open, linked, unrecognized or unsafe databases are refused rather than forced. Listing does not show archived workspaces. To restore, close SOL and move the database from its recovery path back to the workspace directory, only if the original filename is free; there is no automatic restore or permanent archive deletion. Actor labels live separately in `$XDG_DATA_HOME/sol/profiles.sqlite3` (mode `0600`); they are attribution, not authentication. Authored writes, checkpoints and resumes refuse a changed corpus generation (manifest, index and Markdown, not PDF bytes) rather than reloading it: reindex explicitly, then reopen.

<a id="4-theming-and-typography-next-bounded-task"></a>

## 4. Theming and typography

**Decision:** implement exactly three shipped presets before introducing theme plugins or large theme catalogs:

| Preset | Intent | Technical rule |
|---|---|---|
| **Mocha** (default) | [Catppuccin](https://catppuccin.com/palette) Mocha, dark | Catppuccin's own colors; readable contrast and restrained differentiation of hierarchy, notes, search and warnings |
| **Latte** | Catppuccin Latte, light | Catppuccin's own colors; legible dark text on a light page |
| **Paper** | SOL's own, light, from [actualspirit.com](https://actualspirit.com) | Paper `#f3f0e6`, ink `#17151c`, headings in the Actual Spirit purple `#55308a` |
| **Night** | SOL's own, dark | The site's dark band `#1b1820`, warm ink, lilac `#c3a6ee` headings |
| **Terminal** | Existing host's native appearance | Inherit foreground/background; use minimal highlight overrides |

**Decision (maintainer, 20 October 2026):** SOL's look is Catppuccin throughout. Mocha and Latte replace the earlier Dark and Paper presets (a saved `dark` or `paper` reads as `mocha` or `latte`), Mocha is the default, and ESSENCE opens in the reader's theme with Textual's matching Catppuccin theme (Terminal: the terminal's ANSI colors). While ESSENCE is open it follows `T` within half a second: the reader rewrites an owner-only file beside ESSENCE's private context, which ESSENCE reads twice a second (20 October).

**Theme presentation:** Python (`sol/presentation/theme.py`) owns the palettes as inert highlight data; the Lua reader validates group names and attributes again and sources no colorscheme file. Terminal clears the reader's colors so the host's foreground, background and 16-color palette show through. Mocha and Latte use 24-bit color when `COLORTERM` declares it, a computed xterm-256 approximation otherwise, and fall back to Terminal with a visible notice on basic terminals. `NO_COLOR` removes Terminal's single color accent. Body text meets WCAG AAA (7:1) against page and panel; headings, warnings, status and search meet at least AA (4.5:1); tests enforce these ratios. Latte's panels stay on its page color, since its text falls short of 7:1 on Catppuccin's Mantle. **Paper and Night** are SOL's own, from the maintainer's site; each preset declares whether its page is light or dark, and ESSENCE registers matching Textual themes. The default is Mocha. `T` cycles presets for the session only; `sol --theme NAME` selects one for a launch and `sol --set-theme NAME` saves it in the existing `config.json` alongside the corpus pointer. Reading floats share the page color; popups and the outline use a distinct panel color; `~` end-of-buffer and `@@@` last-line markers are hidden. Themes never alter canonical text, offsets, selection identity or workspace data. **Visual audit (21 October):** the reader was rendered off-screen on the book (tmux capture, Libertinus Mono, 110×36 and 80×24) in every preset, with `c`, `?`, the outline, search and focus open. Two faults were fixed: a prompt's question and answer stayed on the command line, and the outline panel filled the screen height below its last entry. The maintainer chose from rendered options: the full status line and plain bold headings stay; focus mode (`f`) now hides the status line as well as headings; the default measure is 66 columns (was 72). Section headings rarely appear mid-screen, because each section opens as its own view. **Not yet done:** sustained manual reading trials in each preset.

**`sol-window`** opens a new foot, kitty or Alacritty window running the reader in Libertinus Mono (bundled, SIL OFL) and Paper unless `--theme` says otherwise; the font is found through a private fontconfig file in `~/.cache/sol/`, so nothing is installed and the user's terminal keeps its own font. A proportional face such as the site's Source Serif cannot be used in a terminal, which gives every letter one cell; foot was observed to slant and embolden Libertinus Mono for emphasis.

Do not confuse installing a Neovim color scheme with designing a reading surface. Evaluate: paragraph spacing, inter-section gaps, measure, top/bottom breathing room, heading density, how emphasis maps to actual fonts, whether the always-visible status hints dominate, line-wrap behavior, warning visibility, tree/search popup intrusion and preservation of position after resizing. The present source defines a centered floating window without border and a verbose action statusline; these are concrete starting points for visual audit.

**Safety:** presentation styling must never change canonical Markdown, `plain_text`, passage UUIDs, offset mapping, selection content or workspace schema. Theme switching should be runtime-selectable and persist as a preference only through an explicit, simple config path; it must not modify user terminal themes or `~/.config/nvim`. Invalid/high-contrast or no-color terminals must degrade legibly. Test 80×24 and larger sizes, Alacritty, different fonts, Unicode and italics fallback.

### Design experiment before expanding features

The earlier `prompt_toolkit` surface (removed; in Git history) was subjectively easier to read despite less functionality. Document why: use a friction log with (a) interruption point, (b) recovery effort, (c) spacing/typography issue, (d) a source or math issue, (e) one corrective change. Then implement small changes inside Neovim with regression tests. Resist another framework migration based on screenshots alone.

Earlier continuous-terminal and offline HTML proofs are retained in Git history. Headless tests of the integrated reader cover exact source-bound selections across layout changes; they do not establish long-term human comfort. If terminal-native reading proves intrinsically inadequate, use the existing CORE/reader-action separation to evaluate a typeset projection later.

## 5. Mathematical notation and source fidelity

The corpus contract supports separate `formula` records and prose passages with `contains_math: true`; this does not mean every supported type is present in the imported book. Mathematical passages remain addressable and navigable. Faithful native Neovim rendering of arbitrary 2-D mathematical notation and a verified general LaTeX conversion pipeline are unimplemented.

**Near-term decision:** prioritize a **source-faithful formula preview**. From the current formula or mixed passage, offer a single action that displays the correct original crop/page (or a reviewed typed formula where available) and returns without losing passage and cursor position. For Alacritty, a separate local image/PDF/browser viewer is legitimate. Kitty can optionally offer enhanced panes, but formula access must not depend on Kitty. Avoid OCR hallucination: generated LaTeX is an unreviewed candidate, not authoritative source. Preserve exponent/fraction placement, printed/PDF page labels, transcription status, attribution, image provenance, and warning flags. Never replace ambiguous formula content with a guessed linear string. A linear transcription made by reading the printed crop (as on 17 October) is not a guess, but it is also not reviewed: it keeps the record's pending status, its audit lists the old and new text, and only a person's comparison against `s` may set `transcription_status` to `reviewed` (a canonical Markdown correction followed by reindexing, not workspace testimony).

**Printed-source crops:** `s` in the reader shows the printed source of the current passage. Python captures the record against the verified corpus generation and a private, fingerprint-checked PDF snapshot, then renders the record's recorded bounding box on each source page at 144 dpi with a 6-point margin; a page entry without a box is rendered whole and labelled as such. A separate image viewer shows it (`xdg-open` or `open`, or the command in `SOL_IMAGE_VIEWER`), detached from the terminal, so it works in Alacritty and does not depend on Kitty. Without a graphical display, SOL shows the file path instead of guessing a viewer. The popup names PDF and printed pages and the transcription status, and says plainly that the printed source is authoritative for records flagged `needs_visual_review` or `needs_review`; number keys show further pages. Nothing moves the cursor, clears a selection or writes to the workspace. The converter's own `assets/*.png` facsimiles are not used, because the corpus manifest does not fingerprint them. The first-run import remembers the verified PDF; existing setups use `sol --set-source-pdf PATH`.

**Recorded source checks (17 October, scratch import of the audited PDF):** the corpus has **no `formula` records**; the converter's short-block rule never fires on this book. Mathematics appears in 46 mixed main-text paragraphs, all `needs_visual_review`, 25 of them spanning two pages, and every source entry has a bounding box. Crops were checked by eye against the PDF for a mixed passage over two pages (polynomials, inline dy/dx), the Newton product passage (stacked fractions the typed text scrambles into `xd y y d x d xd y x y − − + 2 2 4`) and `−a · −a = +a²` (superscript lost in the typed text); all matched the print. A capture from a changed corpus generation is refused, and a missing PDF names `sol --set-source-pdf`. The whole-page fallback is exercised only by synthetic tests, since no real record lacks a box. The popup and viewer were then used in a real terminal session (17 October).

**Retyped mathematics:** in the local corpus (main text and one footnote, 47 records with `contains_math`), 30 records whose typed mathematics was scrambled were retyped in canonical Markdown as linear Unicode (`a²`, `dy/dx`, `(x + dx/2)`), checked against the PDF crops; prose was untouched and record IDs, metadata and pages are unchanged. The corpus audit file `audit/math-retyping-2026-10-17.json` lists each change. They keep `needs_visual_review`, since no person has confirmed them yet; the edition's apparent misprint `f(x+1)` (for `f(x+i)`) is kept as printed. **Not demonstrable yet:** a human-reviewed formula, and native 2-D rendering of stacked notation.

**Zoomable printed page ([reader backlog](coordination/proposals/READER_GAPS_AFTER_ZATHURA.md) item 2):** `S` in the reader, or in the `s` popup, opens the private, fingerprint-checked PDF snapshot at the passage's physical page in a PDF viewer: Zathura when installed, otherwise Sioyek, Okular, Evince or MuPDF, or the command in `SOL_PDF_VIEWER` (`{page}` and `{file}` are replaced). The page can then be zoomed and read with its surroundings, which a fixed-resolution crop cannot offer. A Zathura window SOL opened is turned to each new page over D-Bus (`gdbus`) instead of opening another, so it works as a companion beside the reader; once it is closed, `S` opens a new one. Without a graphical display or PDF viewer, `S` shows the crop popup instead and says why. The reading position, selection and workspace never change. Tested with mocked viewers and in Zathura 2026.10.4 by D-Bus; not yet used in a reading session. In Zathura, `S` also highlights the passage's recorded region on the page, and on the next page when the passage continues there (Zathura's D-Bus `HighlightRects`, with the converter's boxes in PDF points from the top-left corner). Until that window is closed, it follows the reader: about 0.4 s after the cursor comes to rest in another passage, the window turns to it and highlights it. Following checks the snapshot again, never opens a window, never moves the reader, and waits while a move is loading; it stops quietly when Zathura is closed or a request fails. Tested with mocked D-Bus and headless Neovim, and by D-Bus against Zathura 2026.10.4 on the book (calls accepted); the highlight's placement has not yet been seen on screen. Returning from the PDF to the text is not implemented.

The checkout-only formula review-sheet tool was removed in the maintainer's
21 October cleanup. Printed-source crops and page viewing remain available;
canonical transcription status still requires human review.

Acceptance: demonstrate one reviewed simple formula, one complex or unreviewed Newton-related formula, a mixed prose/math passage, a missing source image, a corrected formula, and a stale reference; compare actual rendering against original PDF evidence.

## 6. BEING ↔ ESSENCE without terminal dogma

CORE v1 envelopes capture and check source identity. ESSENCE opens beside the reader with `E` and returns exactly (below). The earlier Kitty/Zsh handoff (`sol-kitty`, `sol reference return`) was removed on 21 October 2026.

The next development target is a **terminal-independent handoff interface**, using existing CORE references and guarded reader actions. Starting from the current chapter/passage, preserve an investigation origin and a way to return to the exact passage while retaining previous navigation state. Any new result must be a separately versioned, attributable **computation artifact**; do not auto-insert model interpretations into the authored workspace.

A narrow, demonstrable first scenario: read a chapter → select scope → initiate an ESSENCE sentence-length analysis → inspect measurements and supporting passage IDs → choose a result → return to its source in BEING → recover the original reading context. **Returning to the result's passage** and **returning to the previous reader position** are different operations; support or explicitly distinguish both rather than assuming one action solves both.

**Sentence study:** `sol essence sentences` runs ESSENCE's sentence study, also available as **Sentence lengths** in ESSENCE ([interface and scopes](ESSENCE.md#4-interaction-model-and-inquiry-contract)). It shows the distribution, means by place in the paragraph and the twelve longest sentences. Workspace sessions save artifacts owner-only as `~/.local/share/sol/studies/sentences-*.sol-analysis.json`, never overwriting; temporary `-n` sessions save nothing. `sol essence check` checks the artifact. Enter on a corpus sentence in ESSENCE opens its first character through guarded navigation; Alt-Left returns to the earlier reader position. There is no sentence-study reader key, panel or reader action. The reader's `S` opens the printed PDF page (§5).

**Decision (maintainer, 18 October 2026): ESSENCE opens beside or over the reader, on demand.** ESSENCE will become a separate Textual application in a Neovim terminal buffer, beside the reader or fullscreen, started only when requested ([ESSENCE §4](ESSENCE.md#4-interaction-model-and-inquiry-contract)). Requirements on the reader side, **proposed** and to be marked implemented only when tested on real terminals:

- **Handoff:** entering ESSENCE carries the current source reference, the selection if any, and the exact reading position (UUID and codepoint).
- **Return:** leaving ESSENCE restores the reader's cursor, selection and mode; opening a result's source and returning to the earlier position stay two distinct operations, as above.
- **Focus:** one visible focus at a time; reader keys act only when the reader is focused, ESSENCE keys only in ESSENCE; Escape and quitting are never ambiguous across the two.
- **Key compatibility:** no existing reader key is remapped to make room for ESSENCE. **Decided 18 October 2026:** `E` opens ESSENCE (it was unmapped). **Decided by the maintainer, 19 October 2026:** `S` is removed from the reader; the sentence study moves into ESSENCE.
- **Failure:** a launch failure, crash or refused result leaves the reader usable at the same place and shows the error.
- **Lifetime:** the reader starts no Textual or model process by itself; closing ESSENCE ends its process without affecting the reader.

**Launch boundary (stage D):** `sol.being.neovim.reader` uses the stdlib-only
`sol.interchange.essence` context format and Textual probe, so opening ESSENCE
does not import its interface into the reader. The context directory belongs
to the reader and is removed at its exit; format, messages and return behavior
are unchanged ([Architecture §9, I1](ARCHITECTURE.md#launch-exchange-outside-the-logical-hierarchy-i1)).

**Opening and returning from ESSENCE:** `E` (in normal or visual mode) captures the reader's exact position and selection first, then asks Python to check the reader's position against the corpus and write a private context file (reference, cursor, the selection's offsets and digests, a heading label; no book text), then opens ESSENCE in a Neovim terminal float on the right, the page re-centring in the remaining columns. Below 100 columns it opens fullscreen. In ESSENCE, Alt-F toggles fullscreen and beside, Alt-R returns to the reader (leaving ESSENCE beside it, or hiding it when there is no room), and `E` in the reader returns to ESSENCE; these are Neovim terminal-mode mappings, and every other key goes to ESSENCE. ESSENCE survives section changes in the reader. Alt-R and leaving (`q`) return to that captured position and selection, endpoints and direction included (once; after a section change the reader stays where it is). Leaving ends the process, closes its window and re-widens the page; a process that fails to start or exits with an error is reported and the reader stays where it was. Without Textual, `E` explains how to install the extra. Tested in headless Neovim with a real terminal process; the real app was also run inside Neovim's terminal, with keys typed through terminal mode. **Not yet tried by hand** in Alacritty or Kitty.

**Opening a result source:** ESSENCE can ask the reader to open a word's source passage. It writes a private OSC sequence (`ESC ] 5379 ; sol-essence ; BASE64 BEL`) to its own terminal; the reader's terminal buffer catches it (Neovim's `TermRequest`), checks its exact shape, shows the reader (from fullscreen, ESSENCE moves beside it, or hides when there is no room) and, once Neovim has left terminal mode, sends an `essence_source` request: record ID, codepoint offset and the counted text's content digest. Python captures the record through CORE, refuses it if the passage's content no longer has that digest ("count again") or the offset lies outside it, and opens it through ordinary guarded, staged navigation — returning to the *result*; Alt-Left restores the earlier position — returning to the *reader*. A malformed request is reported and ignored; other terminal sequences are untouched. Quitting the reader while ESSENCE is open first sends ESSENCE its Ctrl-Q, so it saves its state as it does on `q`, waiting at most two seconds. Popups (`c`, search, printed source, footnotes, note editor) and the outline centre in the reader's columns while ESSENCE is beside it. ESSENCE starts with the reader's own XDG directories and `TMPDIR`, not the private ones Neovim runs with, so what it saves outlives the reader. Tested in headless Neovim with a terminal process sending the sequences; the real Textual app's sequence and Ctrl-Q were checked through Neovim's terminal; on 19 October the whole loop ran on the real book in `sol` inside tmux (count, open a word at its exact character, Alt-Left back, quit with ESSENCE open). **Not yet tried by hand** in Alacritty or Kitty.

## 7. Boundaries and known limitations

- Current normal reading is bounded by chapters/64-record sections, not a whole-book text buffer.
- `gg`/`G` reach the ends of the loaded section, not the book; `gp` jumps to a printed page, the outline to any section.
- Search is complete and occurrence-based (§2); matches without an exact contiguous source span still have no guessed highlight or offset.
- Reader keys can be moved with `keys.json`; panel keys cannot, and Neovim options are not configurable.
- These gaps, found by comparing the reader with Zathura (20 October), are ranked in the [reader backlog](coordination/proposals/READER_GAPS_AFTER_ZATHURA.md).
- Visual selection is transient. Copy can span paragraphs; notes and ESSENCE accept one passage, and no durable cross-paragraph span annotation is available.
- Printed-source preview is implemented and was used in a real terminal (17 October); the reader judged the separate viewer helpful but awkward. `S` opens the whole page in a zoomable PDF viewer, not yet tried in a reading session. Native 2-D mathematical typesetting remains unimplemented; retyped linear mathematics awaits human review.
- The outline/search/marker UI is functional but readability, styling, and mode transitions require actual use testing.
- Comparisons, review testimony and relations can no longer be created (their shell commands were removed on 21 October 2026); records already stored stay readable and exportable. A note containing invisible control characters cannot be edited in the reader.
- Footnote marks are inline display text and can push a wrapped line one cell further. Book-note panels have explicit depth, size and link bounds; they do not save a separate note-reading position or offer personal annotations on note paragraphs.
- Notes cannot yet anchor to a selected span; that needs a new workspace schema version.
- A view that Neovim fails to display after Python accepted it (a crash, or a response over the 16 MiB channel budget) leaves the destination saved; the reader then exits, and reopening resumes there.
- Human reading acceptance is **not** established by headless tests, mock terminal checks, or a 24-passage HTML rendering benchmark.

## 8. Acceptance checklist for agents

A change may be called done only when (1) core corpus/ref/workspace tests pass; (2) recorded UUID+codepoint location survives theme switches, resizing, section transitions, and restart; (3) warnings and notes remain correctly attributed; (4) regular Alacritty and optional Kitty degrade gracefully; (5) reading in a chosen substantial *Science of Logic* chapter demonstrates fewer interruptions; (6) math preview and ESSENCE returns demonstrably preserve the right context; and (7) code and these documents agree on what is actually implemented.

**Source lineage:** consolidated from GitHub's reader view, Neovim implementation, reader actions, workspace plan/export, usage manual, handoff documentation, renderer experiments and dated discussions. Earlier documents are in Git history.
