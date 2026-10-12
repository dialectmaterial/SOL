# A persistent philosophical reading workspace

The first workspace foundation is implemented through the existing CLI and
command shell. Reading continuity, attributed annotations, comparison, source
inspection and review testimony, and relations beyond the tree are available
without installing an interface framework. Richer interfaces and selected-span
annotations remain future work. Interface research is kept separately in
[INTERFACE_RESEARCH.md](INTERFACE_RESEARCH.md).

The aim is a workspace that remembers an inquiry, not merely a terminal that
remembers its commands. The five developments are reading continuity, attributed
annotations, comparison, a source-review desk, and relations beyond the tree.
They belong to the BEING stage: the reader and virtual shell.

## Keep the text and the reader’s work distinct

Canonical Markdown remains the correction surface for the book. The verified
JSONL index remains a generated view. A workspace records what a reader does
with that corpus; it must not become a second independently edited copy of it.

| Corpus | Workspace |
| --- | --- |
| Published hierarchy and permanent record IDs | Reading scope, position, bookmarks and trails |
| Hegel, editorial and translator attribution | The author of each annotation or relation |
| Markdown, notes and source references | Interpretations, comparisons and review decisions |
| Source fingerprint and content integrity | References to the corpus and the version inspected |

The reader retains the complete verified record graph alongside its convenient
three-doctrine view. Passage JSON exposes the canonical record, including its
Markdown and attribution. Verified corpus snapshots, an explicitly initialized
corpus identity, and separate local SQLite storage now provide durable references.
The standard shell remains nonpersistent unless `--workspace NAME` is supplied.

## 1. Reading continuity

Named workspaces save the virtual working directory, reading scope and current
passage UUID. Directory and reading scope are separate: browsing a neighboring
chapter with `cd` does not erase a deliberately chosen reading sequence or cursor.

Opening a workspace shell restores its saved position; `resume` reloads it during
a session, and `--resume` retrieves it through the ordinary CLI. Named bookmarks
target readable passages and support add, explicit replacement, opening and
removal. `workspace history --limit N` lists previous checkpoints. `resume REVISION`
restores a historical position as a new checkpoint using revision conflict checks;
it never deletes or rewinds later history. These are visits, not claims that
displaying a passage means it was read or understood. Richer reading trails remain
future work.

The implemented vertical slice is: open a workspace, start ordered reading,
move to another passage, exit, reopen, and resume the same UUID. Failed operations
do not silently replace a saved reference. Search results are transient; their
display numbers are never used as permanent identity.

## 2. Annotations with attribution

An annotation has its own ID, target record, literal Markdown body, author,
timestamps and personal-note attribution. Notes require an explicit `--actor`
when starting SOL. They remain visibly distinct from Hegel’s prose and the
edition’s notes. The current interface displays annotation Markdown literally,
rather than adding a rendered editor.

The current notes target whole canonical records. Later, a selected quotation can
carry a text snapshot, offsets and the inspected content digest. If the passage
changes, old offsets must not silently attach the note to different words.

If machine-generated suggestions are introduced later, retain their tool/model
provenance and whether a reader adopted them. Never silently turn a suggestion
into an annotation attributed to the reader, or an interpretation attributed to
Hegel. Structured JSON export is available; a readable Markdown export is a
possible next step.

## 3. Comparison

A comparison is a saved, ordered group of record references and an attributed
question. `compare save` requires that question; `compare show` presents the
identified passages sequentially. Canonical records outside the Hegel-only reader
view can also be compared through their Markdown. Side-by-side views and richer
comparison notes remain future work.

Comparisons currently reference live canonical records by stable UUID. They do not
capture frozen quotations or endpoint content digests at creation. Reopening one
after a corpus correction displays the corrected record, not necessarily the text
its author originally saw.

Useful inquiries include how “ground” functions across different locations, how
an earlier determination returns in a later one, or how remarks relate to the
argument they accompany. Preserve the location and attribution of each item.

Label lexical overlap as lexical overlap. Statistical similarity does not itself
establish conceptual identity, a dialectical transition, or a philosophical
dependency. A comparison’s interpretation belongs to its author.

## 4. A source-review desk

`review show` provides read-only inspection of the canonical record, Markdown,
note links, printed and PDF pages, source rectangles or image references where
available, and quality flags. It does not open or verify an image automatically.
`review queue` lists canonical pending flags and can include workspace testimony.
The unscoped queue includes every attribution role, not just quotable Hegel
paragraphs. A `verified` reader outcome never removes a pending canonical flag.
`--within PATH` restricts records with virtual reader paths; omit it for records
without one. The ordinary CLI also exposes this queue without a workspace.

A review event records its explicit actor, time, issue, outcome, source fingerprint
and digest of the inspected text. Outcomes are `inspected`, `correction_needed`
and `verified`. Version 1 binds only the Markdown text digest and declared PDF
fingerprint. Matching these is labelled as matching text/PDF fingerprints, not a
current complete inspection: attribution, page labels, source rectangles and image
bytes are not bound by that review event. `review list` distinguishes matching,
stale and unresolved references. Review testimony is append-only; a new inspection
adds a new event rather than rewriting the earlier claim. Reviews of retired
references are conservatively stale even when a redirect target remains readable.

Corrections still happen in canonical Markdown followed by reindexing. A workspace
decision never rewrites the corpus’s transcription status, random eligibility,
or PDF. A reader's `verified` outcome is attributed testimony, not canonical
verification. The interface exposes uncertainty rather than erasing it to make
the page attractive.

## 5. Relations beyond the tree

The hierarchy preserves the book’s explicit organization. A separate relation
layer can express connections across it without moving passages into artificial
new parents.

`relate add` creates typed, directed edges between stable record references. Each
edge carries an explicit actor, rationale and timestamps. The current edges are
labelled reader assertions. Future imported textual cross-references and computed
similarities must retain distinct provenance, rather than being silently combined
with a reader’s philosophical interpretation.

Relation endpoints are live UUID references, not frozen text snapshots. Their
rationales retain author attribution, but the current format does not prove the
exact endpoint text at the time a relation was created.

For example, “compares with” may be a simple reader-created link. “Presupposes”
or “sublates” is a more substantive claim requiring an argument, not a label
generated from shared vocabulary. The graph should support inquiry into the
movement of the Idea without presenting a classifier’s output as that movement.

## Explicit corpus identity

Persist full UUIDs, not result numbers, path names, prefixes or text hashes. Paths
are locators and reading aids; text hashes detect changes, not identity.

The manifest's `corpus_id` is a permanent lineage UUID. Initialize it explicitly
before making durable workspace references:

```sh
sol-corpus-check local-corpus --initialize-identity
```

Initialization verifies the existing corpus and updates the manifest and its
index-metadata fingerprint. It preserves canonical Markdown, passage IDs and
index text. Existing identities are retained. Ordinary reading does not perform
this change automatically, and a corpus without an identity remains usable in
the nonpersistent reader. New conversions include an identity from the outset.

Edition/translator information and the PDF fingerprint remain provenance. The
PDF hash alone is insufficient as identity: two initial conversions of the same
source can allocate different passage IDs. A workspace refuses a corpus identity
or source-fingerprint mismatch instead of guessing from filenames or text.

Moving a corpus should only change its locator. Reindexing should retain passage
references. Missing references must remain visible as unresolved; retired IDs
should retain the original request and disclose their redirect and resolved
target. Never quietly match a missing passage by similar wording or page number.

## Storage and boundaries

Each named workspace is a local SQLite file, using Python’s standard-library
support. Transactions and related tables store bookmarks, notes, comparisons,
review events and graph edges. The current format is schema version 1. An
unrecognized or incompatible database is rejected; automatic migrations are not
implemented. Reading checkpoints use revision checks to detect competing saves
instead of silently overwriting another session’s position.
[SQLite as an application file format](https://www.sqlite.org/appfileformat.html)

`workspace backup FILE.sqlite3` and `--workspace-backup FILE.sqlite3` use SQLite's
online backup mechanism, validate the snapshot, and publish it without overwriting
any existing destination. The parent directory must already exist. Backups use
mode `0600` on POSIX systems; unsupported publication mechanisms fail rather than
falling back to overwriting. Opening a backup under a different workspace name is
supported for inspection. Automatic replacement of the original database is not.
Launching a CLI backup still requires a valid selected corpus; recovery without
that corpus is not implemented. An already-open shell can back up its database
even when the loaded corpus generation has changed.

Storage defaults to `$XDG_DATA_HOME/sol/workspaces`, or
`~/.local/share/sol/workspaces`. `--workspace-dir DIRECTORY` selects another
location. Keep it outside the canonical book; it is not synchronized to Git or
a remote service. JSON export provides a consistent snapshot of workspace
references, authored records and history, not another canonical book. Foreign-key
enforcement is enabled on each database connection. Import, Markdown/JSONL export,
previewed restore and explicit format migrations remain future work.
[SQLite foreign keys](https://www.sqlite.org/foreignkeys.html)

Workspace storage and corpus-reference operations live in `sol_workspace.py` and
`sol_workspace_reader.py`, separate from input and rendering. Pure diagnostics in
`sol_workspace_diagnostics.py` work from a loaded corpus and one consistent
workspace export. `workspace check` reports unresolved, retired and versioned
references; it performs no repairs and is not source verification.

The corpus-backed reader retains its verified filesystem generation. Authored
writes, checkpoints and resume operations refuse a changed generation rather than
automatically reloading it. Reindex explicitly if necessary, then reopen SOL. This
guard checks the manifest, index and canonical Markdown, not PDF or PNG asset
bytes. A matching generation proves consistency of the loaded files, not a
philosophically or typographically correct transcription.

The CLI and shell use the same operations; any future Textual desk should do
likewise. `run_shell` now accepts injected `read_command` and `write_output`
functions, so an input experiment can avoid replacing command semantics or
storage. No interface library, image renderer or Kitty integration has been added.

## Using the implemented workspace

After initialization, opt into persistence and identify the author of notes and
assertions:

```sh
sol --workspace quantity-study --actor "Your name" --shell
```

Inside that shell:

```text
first /being
workspace
bookmark add beginning
note add "*Question:* How does this determination return later?"
review show
review record inspected --issue "Canonical record inspected; source comparison remains."
cd /essence
resume
compare save quantity-and-opposition PASSAGE_UUID_A PASSAGE_UUID_B --question "What differs?"
compare show quantity-and-opposition
relate add PASSAGE_UUID_A compares-with PASSAGE_UUID_B --reason "An inquiry to pursue"
workspace history --limit 10
workspace check
workspace backup quantity-study-backup.sqlite3
review queue --limit 10
```

Replace the illustrative passage IDs with displayed UUIDs or unambiguous prefixes.
Omitting an annotation or review target uses the current passage. `--on ID`
selects an explicit target for `note add` or `review record`, and filters
`note list`, `review list` or `relate list`. Lists without `--on` show the saved
records across the workspace. `review show ID` inspects a specific canonical
record; it never changes the reading cursor.

Other operations are `bookmark list`, `bookmark open NAME`,
`bookmark set NAME [ID]`, `bookmark remove NAME`, `note show NOTE_ID`,
`compare list`, and `relate list`. Duplicate bookmark names require explicit `set`; duplicate
comparison names are refused. Notes, comparison questions, reviews and relations
require an explicit actor; ordinary navigation and bookmark use do not.

Outside the shell:

```sh
sol --workspace quantity-study --resume
sol --workspace quantity-study --resume --plain
sol --workspace quantity-study --resume --json
sol --workspace quantity-study --resume --resume-revision 1
sol --workspace quantity-study --workspace-check --json
sol --workspace quantity-study --workspace-backup quantity-study-backup.sqlite3 --json
sol --workspace quantity-study --workspace-export > quantity-study.sol-workspace.json
```

Choose the historical revision from `workspace history`; restoring it appends a
new visit. To inspect the example backup from its directory, run
`sol --workspace quantity-study-backup --workspace-dir . --resume` with the same
corpus selected. This opens the snapshot separately, without replacing the
original workspace. Existing backup filenames are never reused automatically.

Export always emits JSON to standard output. `workspace export` offers the same
snapshot inside the shell. Keep the `.sol-workspace.json` suffix for personal
exports, which is excluded from Git and source archives. Direct workspace reading
also supports random quotation, `--read`, `--first` and `--passage`. Context, search and inspection
remain available through ordinary CLI invocations or inside the workspace shell;
they do not silently replace a saved reading position.

The standalone source queue is available through
`sol --review-queue --limit 10`, with `--within PATH` and `--json` as needed. Add
`--workspace NAME` to show its reader testimony. These queue and health operations
are inspection, not saved-position changes or a way to clear quality flags.

## Next work, in priority order

1. Add optional multiline annotation drafts with explicit save and cancellation.
   Capture the intended record and inspected version before editing; do not store
   a cancelled draft or leak its body into command history. The synchronous input
   seam is ready for a small experiment, not a claim that an editor exists.
2. Establish immutable authorship and revision audit before exposing annotation
   editing. Preserve the original author and record who edited what, when, and
   against which version. A replacement body must not erase earlier evidence or
   silently become attributed to the current actor.
3. Design review binding version 2 around an explicitly defined full-record digest,
   including the relevant attribution and provenance fields. Captured version
   binding for comparison and relation endpoints can also be considered without
   creating a second canonical book. Asset verification needs its own stated
   scope. Require a backup and explicit migration plan; never reinterpret old
   text/PDF-only testimony as proof of metadata it did not record. The installed
   workspace schema remains version 1.
4. Add explicit backup restore and import previews. Show identity mismatches,
   unresolved references, duplicate IDs and authorship conflicts before any
   accepted change. Do not automatically merge workspaces or overwrite a newer
   checkpoint. Continue to provide export independently of a graphical interface.
5. Introduce selected-span annotations with verified quote snapshots, a documented
   offset basis and target-version binding. If the text changes, show an unresolved
   anchor rather than selecting similar words silently.
6. Consider richer comparison and review layouts only after these workflows expose
   a measured need for simultaneous views. Computational similarities or classifier
   suggestions must retain their own provenance and must never silently become
   reader-asserted philosophical relations or changes to Hegel's published tree.

Each step should retain a useful plain-text workflow before adding a new screen.

## Acceptance boundaries

Test reopening in another directory, moving the corpus, and reindexing after a
correction. Test missing and retired passage IDs, a damaged workspace, two shell
sessions updating it, interrupted writes and version upgrades. Do not silently
discard unresolved references or overwrite a newer session’s position.

No ordinary resume operation should extract the PDF or access the network.
Preserve the current plain/JSON CLI, local corpus verification, and ability to
read without installing an interface framework. These are foundations, not
temporary conveniences to remove when the interface becomes richer.
