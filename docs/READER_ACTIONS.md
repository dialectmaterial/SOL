# Reader actions and interfaces

BEING is a reader and philosophical workspace. Its virtual shell is one interface
to that reader, not the application's governing architecture. The current
`sol` commands remain compatible; no new installation step is needed.

`sol.reader.actions` now owns paragraph-reading state independently of the
command loop: a `ReadingSession`, browsing location, previous browsing location,
and latest search results. `ReaderActions` returns passages, locations, and
search results. It does not prompt, print, launch panes, open databases, register
actors, extract PDFs, or import optional interface frameworks.

The shell, one-shot workspace reading, and [optional reader view](READER_VIEW.md)
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
`reader.open_result(1)` deliberately opens the first result, if there is one.
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
a second database, actor system, checkpoint format, or migration.

With a workspace, browsing and reading scope remain independent. Reading,
opening, moving, and changed browsing locations use the existing checkpoint and
corpus-freshness guards. Browsing without a current passage cannot replace an
absent or unresolved saved position. Same-location browsing is a no-op.

Without a workspace, changed browsing locations reset the reading selection and
cursor, as before. A same-location browse preserves both cursor and search
results. Search and inspection never create checkpoints.

If an action or checkpoint fails with a domain/runtime error, local browsing,
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
availability, query, and a tuple of results. Inspecting it does not create a visit.
The adapter renders and moves its text cursor from loaded state without disk I/O.

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
selected span, query, and results. Search and selection amend the current context
without adding a visit. New navigation discards any forward branch. With a
workspace, successful trail navigation still uses its ordinary freshness and
revision guards; failures restore the complete prior state. This is separate from
durable checkpoint history and does not introduce an investigation database.

The screen restores a valid latest checkpoint without another visit. It opens the
first passage with one guarded checkpoint only when no saved position exists;
an invalid saved reference remains visible and is not replaced automatically.

## What remains separate

This is a bounded action seam, not a rewrite of every workspace operation.
Annotation editing, comparison capture, review testimony, and relations continue
through their existing guarded services. Some workspace command parsing and
formatting remain coupled; moving those is future, incremental work.

`ReadingSession` and `context_passages` remain re-exported from `sol.reader.app`
for compatibility. New clients should import them from `sol.reader.actions`.
CORE's public API version, corpus contract, and workspace schemas are unchanged.

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
