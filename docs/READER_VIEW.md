# BEING reader view

`sol` opens a quiet, keyboard-driven reading screen. It keeps the current
passage visible while you move, select words, search, and
return through a reading trail. It runs directly in an ordinary capable terminal;
Alacritty is a first-class host. BEING is not a Kitty application. The explicit
`sol --reader` spelling remains available; `sol --shell` opens the optional
command interface. Existing shell commands, workspace
operations, comparison desks, source panes, and reference handoff remain available
through their existing interfaces.

## Open the reader

The optional installed `sol --engine neovim` backend presents adjacent paragraphs
as continuous prose and uses the same workspace positions. It does not change
the default reader described here. See [Continuous reading with Neovim](NEOVIM_READER.md)
for its native keys, section boundaries and current limitations.

```sh
sol
sol --workspace reading --actor "Your name"
sol -n
sol --width 72 --emphasis underline
```

Install or refresh SOL from the project checkout:

```sh
pipx install --force .
```

The normal installation includes prompt_toolkit and the CommonMark parser for
typography. The existing `.[shell]` extra remains compatible.
The reader requires interactive input and output on a real terminal, not Kitty,
remote control, graphics support, or `KITTY_WINDOW_ID`. Terminal
and dependency checks happen before workspace/actor
onboarding or creating their files. A missing dependency or redirected stream produces
an actionable error. The adapter does not install packages or change pipx or
general terminal configuration.

Normal corpus discovery and `--corpus` selection apply. SOL remembers the last
actor and that actor's last workspace, then restores its reading position. If no
workspace exists for the chosen actor, it asks to create one. Explicit `--actor`
and `--workspace` select a different reading context. An actor attributes personal
activity; it does not replace Hegel's authorship. `-n` makes the session temporary
and bypasses workspace and actor storage.

Use `sol --workspace-list` to inspect local workspaces and
`sol --workspace-delete NAME` to remove one from normal use by archiving it
recoverably. These management operations do not require a corpus or actor.

Kitty is an optional host, not the reader's architecture. `sol-kitty --reader`
opens the same adapter in a private launch profile. Kitty-specific panes,
source/facsimile viewing, and ESSENCE integration remain separate optional
workflows; they are not required for ordinary reading in Alacritty or another
capable terminal.

The fullscreen reader does not combine `--reader` with one-shot actions, `--plain`,
`--json`, legacy PDF reading, `--ui`, `--editing-mode`, or `--source-pdf`.
Use the ordinary interfaces for those workflows. `--width` is supported: it sets
a maximum reading measure of 20–240 columns, default 72, centered when space
permits and narrowed to fit a smaller terminal.

## Read, select, search, and return

The body displays one active canonical record's exact `plain_text` in a continuous,
read-only view. Its title and printed page align with the prose column. A quiet
footer keeps passage position, selection count, and essential keys secondary.
Responsive space above the column separates the title from the terminal's window
bar, with a small blank lead before prose. This is a stable reading margin, not
paragraph-by-paragraph vertical centering. It shrinks first when the terminal is
short or contextual panels/warnings need room. Focus mode retains a quiet top
margin without reserving space for a hidden title.
Press `c` for the full structural path, PDF pages, workspace, current reading
scope, and any typography fallback explanation. Press `f` to hide ordinary
metadata. Source-review warnings, operational errors, and typography fallback
notices remain visible; focus mode does not conceal them.

Canonical CommonMark emphasis is mapped to source-codepoint ranges only when its
visible projection matches the indexed text exactly. Semantic emphasis maps to
italics or underline, strong emphasis to bold, and inline code to underline;
quotation records or spans receive a document-context label. These are generic
terminal styles, not Kitty graphics or ANSI-decorated canonical text.
`--emphasis auto` uses italics for recognized terminal families
and underlining for unknown ones. This is a heuristic based on `TERM`, not a
capability test;
choose `--emphasis italic` or `--emphasis underline` explicitly when needed. A
projection disagreement gives unstyled text with an explicit fallback notice,
never guessed alignment.

| Normal terminal host | Expected emphasis with `--emphasis auto` |
| --- | --- |
| Alacritty (`alacritty` or its common `xterm-256color` setting) | Standard terminal italics |
| Kitty (`xterm-kitty`) | The same standard terminal italics |
| Unknown/basic terminal | Visible underline instead of assumed italics |

The terminal and selected font ultimately determine glyph appearance. Override
the heuristic when needed; no emulator-specific identity is required.

Prose wraps at word boundaries where possible. Only a sequence too long to fit
the measure falls back to character wrapping. Resizing reflows presentation:
it does not insert newlines, change canonical whitespace, or alter the underlying
text. The renderer and visual-motion geometry share one layout plan. Presentation
padding and visually suppressed spaces at wrap boundaries map back to the same
original source codepoints; styles and selections retain that mapping. Source
offsets are semantic, while wrapped rows and terminal cells are presentation.

Terminal control, bidirectional formatting, and unsafe invisible characters
appear as visible escapes, retaining a mapping to
the original offsets. A `[source review]` marker remains visible for passages
whose canonical transcription is flagged for review; the new view does not certify
or conceal their uncertainty.

| Key | Action |
| --- | --- |
| `j` / `k`, Up / Down | Move through wrapped rows; continue at passage edges |
| `h` / `l`, Left / Right | Move by source character |
| Ctrl-D / Ctrl-U | Move about half a visible page |
| `gg` / `G` | Beginning / end of the current reading scope (`c` identifies it) |
| `b` / `n` | Previous / next semantic passage (at its beginning) |
| `{` / `}` | Previous / next passage aliases |
| Page Down / Page Up; `p` | Compatibility passage navigation; `p` goes backward |
| Alt-Left / Alt-Right | Back / forward through the session's reading trail |
| `v`, then movement | Begin a local selection; press `v` again to stop selecting |
| Shift-arrow keys | Extend or reduce a text selection |
| `/` | Focus the query field while the passage remains visible |
| Enter in the query field | Search and focus the results |
| Up / Down or `j` / `k` in results, then Enter | Choose and open a result without typing a UUID |
| Ctrl-P / Ctrl-N in the body | Previous / next search-result passage, wrapping |
| Tab / Shift-Tab | Switch focus between body and results |
| Escape | Cancel query, clear selection, dismiss match marks, or close help |
| `c` / `f` / `?` | Context / focus mode / keyboard help |
| Ctrl-Q | Save changed reading position and quit |
| Ctrl-C | Quit without an extra cursor-position save |

Ordinary reading no longer stops at each passage boundary. From the last wrapped
row, another `j`, Down, or Ctrl-D enters the next passage at its beginning. From
the first row, `k`, Up, or Ctrl-U returns to the previous passage's end. A large
half-page motion first reaches the current passage's edge; it does not skip the
tail or carry its row budget across several passages. Flow stays inside the
current reading scope and does not wrap at its ends. `b/n` (and the retained
`{`/`}` aliases) deliberately jump to the beginning of the previous/next passage,
regardless of the cursor's visual row. These units are canonical passages, not
fixed printed/PDF pages; page numbers remain provenance.

Automatic crossing is disabled while selecting, including an empty `v` or
Shift-arrow anchor. Finish or clear selection before continuing. Selected spans
never acquire offsets from another passage. Each actual crossing records one
ordinary guarded passage visit, with the backward end offset captured before
the checkpoint. Row motion within a passage remains transient.

For example, search `/ground`, open a result, read with `j`/`k`, move between
matching passages with Ctrl-N/Ctrl-P, and return with Alt-Left. `n` always means
the next passage in the reading scope, even when a search exists. Ctrl-N means
the next matching passage, not an occurrence within the current paragraph.
`gg`/`G` act on the current scope, not just the
currently displayed paragraph. Vertical movement follows visual rows; horizontal
movement follows source characters. A layout change resets the preferred visual
column without changing the semantic cursor or selected span.

Search covers the whole reader book and shows up to 20 matches in a bounded result
pane. A browsing directory retained from the compatibility command interface
does not silently restrict the new view's search. Results preserve passage
identity internally; their display numbers and highlights are reading aids.
Opening a result lands at its first verified source occurrence, rather than the
paragraph beginning. Current-passage matches receive a generic terminal underline
and a color accent when supported, retaining the source's italics/bold/code styles.
Escape dismisses the marks without deleting the query; Ctrl-N/Ctrl-P or a new
search reveal them again. Marks are presentation, not a text selection.

Search uses the existing literal NFC/casefold semantics, including whole-word mode
for callers that request it. A verified mapping connects these normalized matches
to original source-codepoint spans. If a match cannot be represented exactly
(for example one `s` inside the casefold expansion of `ß`), only verified peers
are marked. An explicit fallback notice remains visible in focus mode; `c` gives
the reason. With no verified span the matching passage opens at its beginning,
without guessing an offset or altering canonical text.

Opening a result is one ordinary guarded navigation action, setting the source
position before its checkpoint. Even a jump within the current paragraph retains
the originating cursor, viewport, and selection for Alt-Left return. Returning
to an unchanged match preserves its viewport and adds no duplicate trail entry.
Typing a query and inspecting
results do not save a visit. Cursor movement and text selection also create no
checkpoint or authored workspace record.
Opening a passage or returning through history dismisses the result pane without
discarding the query and matching passages. It does not resurrect the pane on
ordinary navigation; press `/` and Enter to inspect the cached query again.

The reading trail retains at most 100 contexts in this session, including reading
scope, browsing location, requested alias, source cursor, viewport anchor,
selected span, query, and results. Back and forward restore that context.
New navigation after going back replaces the
forward branch. This trail is separate from the workspace's durable checkpoint
history and disappears when the reader exits.

Reopening the same context preserves its selection and creates no duplicate trail
entry. Explicit reading visits still use the existing workspace checkpoint and
conflict rules, even when they revisit the same passage.

## Continuity and source binding

The semantic cursor and optional viewport anchor use raw Unicode codepoints,
not bytes, terminal cells, wrapped rows, or display escapes. New workspaces use
schema 3: optional positions bind target UUID, canonical content digest, exact
plain-text digest/length, cursor, and viewport to the same checkpoint revision.
Changing terminal, width, or emphasis does not invalidate those positions.
Reopening returns to the same source location with newly wrapped rows; the
viewport anchor is approximate, and keeping the source cursor visible takes
priority over reproducing a former screen arrangement.
Cursor keys never write per-key database checkpoints. Ctrl-Q saves a changed
position once, guarded by corpus freshness and expected checkpoint revision. A
failed save leaves the reader open with the error rather than overwriting a
competing update. Ctrl-C skips this extra save but does not undo passage
checkpoints already made. Temporary `-n` sessions save neither passage nor cursor.

Opening a persistent reader restores a valid saved position without recording an
extra visit. If no position has ever been saved, it opens the first passage with
one ordinary guarded checkpoint. An invalid saved reference is reported rather
than silently replaced by that first passage. Ordinary successful navigation uses
the existing corpus-freshness and checkpoint revision checks; failures restore
the entire local reader context. If only the saved text-bound offset is stale,
the identified passage opens at its beginning with an explanation instead of
reusing that offset.

Existing versions 1 and 2 remain unchanged and retain passage-level continuity.
To gain durable offsets, explicitly make and reopen a separate upgraded copy:

```sh
sol --workspace reading --workspace-upgrade reading-v3.sqlite3
sol --reader --workspace reading-v3 --workspace-dir . --actor "Your name"
```

The original remains intact; no in-place migration or invented old offsets occur.

Selections bind the requested UUID, resolved target UUID, a nonempty half-open
`[start, end)` span in raw Python Unicode codepoints, exact selected text, canonical
content digest, and plain-text digest. Offsets do not refer to Markdown, UTF-8
bytes, wrapped columns, or display escapes. The action layer checks the canonical
record and reader projection before accepting the selection. Rendering and cursor
selection use the loaded state without reading source files or opening storage.
See the [reader action contract](READER_ACTIONS.md).

This existing selection is the future bridge from reading to annotation,
comparison, relations, copy/export, and a BEING → CORE → ESSENCE investigation.
Those operations should consume the same canonical UUIDs, codepoint span, and
source bindings, not introduce a second selection-identity scheme. The current
view does not yet save selected-span notes or export selections.

This staged update covers reader presentation, semantic navigation, and
source-bound reading-position continuity. It does not implement durable
selected-span annotations, an active-investigation database, tree navigation,
an integrated comparison/source-review desk, or all phases of the handoff.
It does not rewrite the corpus or implement a full terminal emulator.
The immediate next test is sustained reading by the user, recording friction
that makes a book or PDF preferable. Durable spans, comparisons, relations, and a
contextual ESSENCE loop should follow demonstrated reading needs; investigation
remains a hypothesis, not a mandate to add another layer. See the
[acceptance record and reading log](READER_ACCEPTANCE.md) and
[modularity contract](MODULARITY.md#handoff-priorities-and-acceptance-gates).

The adapter uses prompt_toolkit's existing full-screen application, layout, focus,
and key-binding facilities. [Official full-screen application documentation](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/full_screen_apps.html).

## Check the actual terminal experience

Automated toolkit tests use invented text and isolated workspaces. They test
wrapping, source offsets, selection, resizing, and persistence; naming a terminal
in a test environment is not a manual check of that emulator's rendering.

For a manual acceptance pass, open `sol --reader` directly in Alacritty:

1. Inspect a long prose paragraph and one containing several italic spans.
2. Try measures of 40, 72, and 100 columns, then make the terminal narrower than
   the selected measure. Ordinary words should remain intact where they fit.
3. Check `j`/`k`, `h`/`l`, Ctrl-D/U, `gg`/`G`, and `b`/`n` with context revealed.
4. Select across styled words with `v`; resize and verify that the selected source
   words remain the same.
5. Search, open a match, use Ctrl-N/Ctrl-P, and return through Alt-Left.
6. Quit with Ctrl-Q, reopen the same schema-3 workspace at another terminal width,
   and check the meaningful text location rather than the former screen row.
7. Compare ordinary, `c` context, and `f` focus views; genuine warnings must remain
   visible. If available, do a smaller comparison pass in Kitty and test the
   explicit underline fallback.

The existing opt-in integration check uses a private Kitty window and invented text;
it checks optional hosting, not a requirement for BEING:

```sh
SOL_TEST_LIVE_KITTY=1 python3 -B -m unittest discover -s tests -p test_reader_view_integration.py
```

It checks visible page labels, source selection, search, and return to the original
selected context, without creating a personal workspace or changing terminal settings.

The separate opt-in Alacritty check launches two private real-terminal readers
with different column counts and a temporary schema-3 workspace:

```sh
SOL_TEST_LIVE_ALACRITTY=1 python3 -B -m unittest discover -s tests -p test_reader_alacritty_integration.py
```

It drives bindings programmatically and verifies selection, search/history, and
quit/reopen position. Neither live test proves physical-keyboard ergonomics or
that sustained philosophical reading is better than a book/PDF. A known toolkit
edge case can visually drop a decomposed combining mark at a full-width row edge;
source identity remains unchanged. See the acceptance record for limitations and
the distinction between visual inspection and automated checks.
