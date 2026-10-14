# Optional BEING reader view

`sol --reader` opens a quiet, keyboard-driven reading screen. It keeps the current
passage visible while you move, select words, search, and
return through a reading trail. The ordinary `sol` command interface remains the
default while this prototype is evaluated. Existing shell commands, workspace
operations, comparison desks, source panes, and reference handoff remain available
through their existing interfaces.

## Open the reader

```sh
sol --reader
sol --reader --workspace reading --actor "Your name"
sol --reader -n
sol --reader --width 72 --emphasis underline
sol-kitty --reader
```

Install or refresh the optional `shell` extra from the project checkout:

```sh
pipx install --force '.[shell]'
```

The extra supplies prompt_toolkit and the CommonMark parser for typography.
The reader requires interactive input and output on a real terminal. Terminal
and dependency checks happen before workspace/actor
onboarding or creating their files. A missing extra or redirected stream produces
an actionable error. The adapter does not install packages or change pipx or
general terminal configuration.

Normal corpus discovery and `--corpus` selection apply. Persistent reading uses
the existing workspace picker and actor onboarding; supplied labels skip the
corresponding questions. `-n` makes the session temporary and bypasses workspace
and actor storage. `sol-kitty --reader` hosts the same adapter in its private
launch profile.

The prototype does not combine `--reader` with one-shot actions, `--plain`,
`--json`, legacy PDF reading, `--ui`, `--editing-mode`, or `--source-pdf`.
Use the ordinary interfaces for those workflows. `--width` is supported: it sets
a maximum reading measure of 20–240 columns, default 88, centered when space
permits and narrowed to fit a smaller terminal.

## Read, select, search, and return

The body displays one active canonical record's exact `plain_text` in a continuous,
read-only view. Two subdued lines normally show passage/page position and essential
keys. Press `c` for title, structural path, printed/PDF pages, workspace, and any
typography fallback explanation. Press `f` for less chrome. Source-review warnings
and operational errors remain visible; focus mode does not conceal them.

Canonical CommonMark emphasis is mapped to source-codepoint ranges only when its
visible projection matches the indexed text exactly. Italics, strong emphasis,
code, and quotations can therefore appear without inserting markup or altering
selection offsets. `--emphasis auto` uses italics for recognized terminal families
and underlining for unknown ones. This is a heuristic, not a capability test;
choose `--emphasis italic` or `--emphasis underline` explicitly when needed. A
projection disagreement gives unstyled text with an explicit fallback notice,
never guessed alignment.

Wrapping changes with the terminal width; it does not change the underlying text.
Terminal control, bidirectional formatting, and unsafe invisible characters
appear as visible escapes, retaining a mapping to
the original offsets. A `[source review]` marker remains visible for passages
whose canonical transcription is flagged for review; the new view does not certify
or conceal their uncertainty.

| Key | Action |
| --- | --- |
| `j` / `k`, Up / Down | Move through displayed, wrapped rows |
| `h` / `l`, Left / Right | Move by source character |
| Ctrl-D / Ctrl-U | Move about half a visible page |
| `gg` / `G` | Beginning / end of the current reading scope |
| `}` / `{` | Next / previous semantic passage |
| Page Down / Page Up; `p` | Compatibility passage navigation; `p` goes backward |
| Alt-Left / Alt-Right | Back / forward through the session's reading trail |
| `v`, then movement | Begin a local selection; press `v` again to stop selecting |
| Shift-arrow keys | Extend or reduce a text selection |
| `/` | Focus the query field while the passage remains visible |
| Enter in the query field | Search and focus the results |
| Up / Down or `j` / `k` in results, then Enter | Choose and open a result without typing a UUID |
| `n` / `N` in the body | Next / previous search-result passage, wrapping |
| Tab / Shift-Tab | Switch focus between body and results |
| Escape | Cancel the query, clear the current selection, or close help |
| `c` / `f` / `?` | Context / focus mode / keyboard help |
| Ctrl-Q | Save changed reading position and quit |
| Ctrl-C | Quit without an extra cursor-position save |

For example, search `/ground`, open a result, read with `j`/`k`, move between
matching passages with `n`/`N`, and return with Alt-Left. Here `n` means the next
search result, not the next paragraph; use `}` for the latter.

Search covers the whole reader book and shows up to 20 matches in a bounded result
pane. A browsing directory retained from the compatibility command interface
does not silently restrict the new view's search. Results preserve passage
identity internally; their display numbers and highlights are reading aids.
Opening a result is an ordinary navigation action. Typing a query and inspecting
results do not save a visit. Cursor movement and text selection also create no
checkpoint or authored workspace record.

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

This staged update covers reader presentation, semantic navigation, and
source-bound reading-position continuity. It does not implement durable
selected-span annotations, an active-investigation database, tree navigation,
an integrated comparison/source-review desk, or all phases of the handoff.
It does not rewrite the corpus or implement a full terminal emulator.
The next priorities are durable spans and investigations integrated with
comparisons and relations, a contextual ESSENCE
loop, reuse of external tools and exported data, and validated heterogeneous
ingestion. See the [workspace priorities](WORKSPACE_PLAN.md#next-work-in-priority-order)
and [modularity contract](MODULARITY.md#handoff-priorities-and-acceptance-gates).

The adapter uses prompt_toolkit's existing full-screen application, layout, focus,
and key-binding facilities. [Official full-screen application documentation](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/full_screen_apps.html).

The opt-in live check uses a private Kitty window and invented text:

```sh
SOL_TEST_LIVE_KITTY=1 python3 -B -m unittest discover -s tests -p test_reader_view_integration.py
```

It checks visible page labels, source selection, search, and return to the original
selected context, without creating a personal workspace or changing terminal settings.
