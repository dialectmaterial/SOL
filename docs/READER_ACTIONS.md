# Reader actions and interfaces

BEING is a reader and philosophical workspace. Its virtual shell is one interface
to that reader, not the application's governing architecture. The current
`sol` opens the full-screen reader by default; `sol --shell` retains the optional
command interface.

`sol.reader.actions` now owns paragraph-reading state independently of the
command loop: a `ReadingSession`, semantic source cursor, viewport anchor, browsing
location, previous browsing location, and latest search results. `ReaderActions`
returns passages, locations, and search results. It does not prompt, print,
launch panes, open databases, register
actors, extract PDFs, or import optional interface frameworks.

The shell, one-shot workspace reading, and [reader view](READER_VIEW.md)
use this boundary. Parsing command strings, choosing colors and width, editing
drafts, rendering output, and managing
source/comparison panes remain interface responsibilities. Native `sol read FILE`
retains its separate whole-file and real-shell path semantics; it is not changed
into a random paragraph operation.

## A reader without a shell

Use an explicitly selected, already indexed local corpus:

```python
from pathlib import Path
from sol.core import load_corpus_book
from sol.reader.actions import ReaderActions

book = load_corpus_book(Path("local-corpus"))
reader = ReaderActions(book)
first = reader.read((), first=True)
following = reader.move(1)
matches = reader.search("ground", (), whole_word=True, limit=10)
neighbors = reader.context(1)
```

The example does not create a workspace or record a visit. Search and context
do not move the reading cursor. Search results contain existing passage IDs;
`reader.open_result(1)` deliberately opens the first result at its first verified
source match, if there is one. Exact offsets are set before its guarded checkpoint.
`reader.open(identifier)` accepts the existing identifier/retirement resolution
rules. These are reader passages, not the entire canonical corpus: applications
handling editorial material or notes should use CORE's full canonical records.

Book paths are tuples of actual location components. `locate(value)` uses CORE's
existing virtual aliases to translate a compatibility path into a node and tuple.
`browse(path)`, `up()`, and `back()` manage browsing; paths are not host filesystem
access or another shell language. Random prose eligibility is unchanged.

## Continuity and personal work

An already opened `WorkspaceReader` can be injected:

```python
reader = ReaderActions(book, workspace_reader=existing_workspace_reader)
passage, message = reader.restore()
```

The workspace reader and optional injected session must belong to the same loaded
book. Their lifecycle remains the caller's responsibility. This does not introduce
a second database or actor system. New workspaces use schema 3; existing versions
1 and 2 are not automatically migrated.

With a workspace, browsing and reading scope remain independent. Reading,
opening, moving, and changed browsing locations use the existing checkpoint and
corpus-freshness guards. Browsing without a current passage cannot replace an
absent or unresolved saved position. Same-location browsing is a no-op.

Without a workspace, changed browsing locations reset the reading selection and
cursor, as before. A same-location browse preserves both cursor and search
results. Search and inspection never create checkpoints.

If an action or checkpoint fails with a domain, runtime, or storage error, local browsing,
reading cursor, restored reference, selection, search, and trail are rolled back
before the error reaches the interface. Concurrent or stale writes are not retried
or forced. This is
local navigation recovery, not a transaction over arbitrary external effects.
Successful latest restoration only inspects the existing checkpoint; historical
restoration creates a new visit through the existing workspace rules. Both clear
the transient latest-search list. Retired requested IDs remain distinct from
their resolved targets in durable state.

## Selection and the session reading trail

`snapshot()` returns a frozen `ReaderState` containing the current passage,
browsing location, reading scope, requested UUID, selection, back/forward
availability, query, a tuple of results, `cursor_offset`, and `viewport_offset`.
Inspecting it does not create a visit. The adapter renders and moves its text
cursor from loaded state without disk I/O.

`select_span(start, end)` accepts a nonempty half-open span in the canonical
record's exact `plain_text`, measured in raw Python Unicode codepoints. It checks
the canonical source and reader projection, retaining the requested retired alias
separately from its resolved target. It returns a frozen `TextSelection` with
`requested_id`, `target_id`, `start`, `end`, `text`, `content_sha256`, and
`plain_text_sha256`. These are not byte offsets, Markdown offsets, or screen
columns. `clear_selection()` clears that local span. Both operate on the loaded
generation and create no checkpoint, note, or other durable object.

`history_back()` and `history_forward()` restore session-local reading contexts.
The bounded trail holds at most 100 contexts: location, scope, requested alias,
cursor, viewport anchor, selected span, query, and results. Search, source cursor
motion, viewport changes, and selection amend the current context without adding
a visit. New navigation discards any forward branch. With a
workspace, successful trail navigation still uses its ordinary freshness and
revision guards; failures restore the complete prior state. This is separate from
durable checkpoint history and does not introduce an investigation database.

The screen restores a valid latest checkpoint without another visit. It opens the
first passage with one guarded checkpoint only when no saved position exists;
an invalid saved reference remains visible and is not replaced automatically.

## Semantic movement and saved positions

`set_cursor(offset)` and `set_viewport(offset)` use source-codepoint positions,
not bytes, terminal cells, wrapped rows, or Markdown positions. `move_horizontal`
moves by codepoint; `move_up`, `move_down`, and `half_page` accept a validated
source-to-display layout so the adapter can account for wrapping, wide characters,
and escaped controls. Width-only callers use the action layer's basic layout.
The full-screen adapter supplies its word-aware renderer's layout, including
display-only padding and hidden wrap separators. Those separators remain source
codepoints; visual motion chooses the following visible glyph when boundaries
coincide. Changing layout resets the preferred visual column, not the semantic
cursor. Neither layout nor preferred column is saved as reading identity.
`advance_reading(rows, ..., selecting=False)` is the bounded reading-flow action.
It moves within the supplied visual layout first; an outward motion already at
the outer row can make one guarded adjacent-passage visit within the same scope.
Forward entry is source offset zero, backward entry is the previous text's end,
set before its checkpoint. At scope ends it stays put without another visit.
An existing semantic selection or explicit selecting flag prevents crossing;
the flag also covers a still-empty interface anchor. This is not a global text
buffer or a multi-passage selection scheme. Existing `move_up`, `move_down`, and
`half_page` remain passage-local for other clients.
`move_paragraph(offset)` changes the canonical passage and starts its source
cursor at zero. `jump()` accepts `passage-start`, `passage-end`, `scope-start`, or
`scope-end`; scope boundaries retain the current reading selection.

`search_next(reverse=False)` visits the next result from the latest literal search,
wrapping at the result boundary. It changes passages, not character-level matches,
and refuses an absent result set. The screen chooses whole-book search explicitly;
other clients can still search a selected subtree.
Query and whole-word mode belong to transient reader context and survive history
return, not workspace schema. `search_highlights()` returns a frozen derived
projection of half-open source ranges plus any explicit degradation reason. It
does not allocate selection IDs, change canonical text, or authorize a workspace
write. Normal repeated `open()` still preserves the current selection/location;
explicit search opening clears destination selection but keeps its origin in the
return trail, including same-passage jumps.

These local movement actions do not write per-key checkpoints. `save_position()`
deliberately saves a changed semantic position through the injected workspace
reader's ordinary freshness and expected-revision guards. An unchanged position
adds no revision; failure rolls back local action state rather than forcing a save.
Without a workspace, it has no persistent effect.

Schema 3 associates an optional position with the same checkpoint revision. It
contains target UUID, canonical content digest, plain-text digest and length,
cursor offset, and optional viewport offset. Restoration accepts offsets only
against the exact bound text; a changed text binding resumes the identified passage
at its beginning and reports why. Versions 1 and 2 open unchanged, save passages,
and warn that exact offsets need an explicit separate-copy upgrade. The original
database is never migrated in place. Selected spans are not made durable.

The optional view saves a changed position on Ctrl-Q and stays open if that save
fails. Ctrl-C leaves without this extra save, retaining passage checkpoints already
made. Selection and the reading trail remain session-local.

## Typography as a separate projection

`sol.reader.typography.map_typography(markdown, plain_text)` lazily uses the corpus
contract's CommonMark parser and visible-HTML rules. It returns immutable,
nonoverlapping style spans in exact source-codepoint ranges. Missing source/parser
or a projection mismatch explicitly degrades to completely unstyled text rather
than guessing alignment. The adapter decides how to display emphasis, including
an underline fallback; neither mapping nor styling changes canonical text or
selection coordinates. Importing this module loads no optional frameworks.
The ordinary full-screen reader is terminal-emulator-independent: Alacritty and
Kitty use standard terminal styles, with a visible underline fallback for unknown
terminal families. Optional Kitty hosting is separate from this action contract.

## What remains separate

This is a bounded action seam, not a rewrite of every workspace operation.
Annotation editing, comparison capture, review testimony, and relations continue
through their existing guarded services. Some workspace command parsing and
formatting remain coupled; moving those is future, incremental work.

`ReadingSession` and `context_passages` remain re-exported from `sol.reader.app`
for compatibility. New clients should import them from `sol.reader.actions`.
CORE's public API version and corpus contract remain unchanged. Workspace schema 3
adds optional source-bound reading positions; older stores remain compatible.

## Explicit handoff actions

`capture_active_reference()` captures the active requested UUID and verified
canonical generation without navigation or a visit. `check_return_reference(packet)`
verifies the [CORE envelope](REFERENCE_PROTOCOL.md) and its agreement with the
reader's passage projection without changing reading state. A generic canonical
record that cannot be read through that projection is refused.

`accept_return_reference(packet)` checks again, then calls the ordinary guarded
open action with the requested UUID. It preserves retirement resolution and uses
the same local checkpoint, freshness, conflict, and rollback rules as other
navigation. None of these actions launches a pane or creates transport files.

The shell adapter owns one exchange, detects changed reader position, and limits
acceptance to one deliberate navigation. It requires `essence return --accept-move`
when the position changed; the flag does not bypass canonical or workspace guards.
The terminal adapter owns the native shell and private transport. Actor and
workspace authority remain local to BEING. See the [handoff workflow](HANDOFF.md)
and [modularity contract](MODULARITY.md).

Remaining workspace parsing/presentation can be separated incrementally. Durable
spans and active investigations are future workspace contracts. ESSENCE tools and
their result-ingestion policies remain separate application contracts, not
implicit capabilities of a returned reference.
