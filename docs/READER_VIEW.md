# Optional BEING reader view

`sol --reader` opens BEING's first optional reading screen. It keeps the current
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
sol-kitty --reader
```

The reader uses the existing optional `shell` extra (`prompt_toolkit>=3.0.52`),
not a new interface dependency. It requires interactive input and output on a
real terminal. Terminal and dependency checks happen before workspace/actor
onboarding or creating their files. A missing extra or redirected stream produces
an actionable error. The adapter does not install packages or change pipx or
general terminal configuration.

Normal corpus discovery and `--corpus` selection apply. Persistent reading uses
the existing workspace picker and actor onboarding; supplied labels skip the
corresponding questions. `-n` makes the session temporary and bypasses workspace
and actor storage. `sol-kitty --reader` hosts the same adapter in its private
launch profile.

The prototype does not combine `--reader` with one-shot actions, `--plain`,
`--json`, legacy PDF reading, `--ui`, `--editing-mode`, `--source-pdf`, or `--width`.
Use the ordinary interfaces for those workflows.

## Read, select, search, and return

The body displays the active canonical record's exact `plain_text` in a continuous,
read-only view. A separate heading identifies its title, structural location,
printed pages, and PDF pages. Wrapping changes with the terminal width; it does
not change the underlying text. Terminal control, bidirectional formatting, and
unsafe invisible characters appear as visible escapes, retaining a mapping to
the original offsets. A `[source review]` marker remains visible for passages
whose canonical transcription is flagged for review; the new view does not certify
or conceal their uncertainty.

| Key | Action |
| --- | --- |
| `n` / `p`, Page Down / Page Up | Next / previous passage in the current reading scope |
| Alt-Left / Alt-Right | Back / forward through the session's reading trail |
| Arrow keys | Move the text cursor; keep its position visible |
| Shift-arrow keys | Extend or reduce a text selection |
| `/` | Focus the query field while the passage remains visible |
| Enter in the query field | Search and focus the results |
| Up / Down in results, then Enter | Choose and open a result without typing a UUID |
| Tab / Shift-Tab | Switch focus between body and results |
| Escape | Cancel the query, clear the current selection, or close help |
| `?` | Show keyboard help |
| Ctrl-Q / Ctrl-C | Quit |

Search covers the whole reader book and shows up to 20 matches in a bounded result
pane. A browsing directory retained from the compatibility command interface
does not silently restrict the new view's search. Results preserve passage
identity internally; their display numbers and highlights are reading aids.
Opening a result is an ordinary navigation action. Typing a query and inspecting
results do not save a visit. Cursor movement and text selection also create no
checkpoint or authored workspace record.

The reading trail retains at most 100 contexts in this session, including reading
scope, browsing location, requested alias, selected span, query, and results. Back
and forward restore that context. New navigation after going back replaces the
forward branch. This trail is separate from the workspace's durable checkpoint
history and disappears when the reader exits.

Reopening the same context preserves its selection and creates no duplicate trail
entry. Explicit reading visits still use the existing workspace checkpoint and
conflict rules, even when they revisit the same passage.

## Continuity and source binding

Opening a persistent reader restores a valid saved position without recording an
extra visit. If no position has ever been saved, it opens the first passage with
one ordinary guarded checkpoint. An invalid saved reference is reported rather
than silently replaced by that first passage. Ordinary successful navigation uses
the existing corpus-freshness and checkpoint revision checks; failures restore
the entire local reader context.

Selections bind the requested UUID, resolved target UUID, a nonempty half-open
`[start, end)` span in raw Python Unicode codepoints, exact selected text, canonical
content digest, and plain-text digest. Offsets do not refer to Markdown, UTF-8
bytes, wrapped columns, or display escapes. The action layer checks the canonical
record and reader projection before accepting the selection. Rendering and cursor
selection use the loaded state without reading source files or opening storage.
See the [reader action contract](READER_ACTIONS.md).

This completes a first reader slice: visible text, local selection, search, and
reversible navigation. It does not implement durable selected-span annotations,
an active-investigation database, or all phases of the architecture handoff.
There is no workspace schema change. The next priorities are durable spans and
investigations integrated with comparisons and relations, a contextual ESSENCE
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
