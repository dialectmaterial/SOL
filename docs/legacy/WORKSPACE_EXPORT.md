# A readable inquiry report

A workspace keeps the reader's inquiry distinct from the book. Markdown export
turns a consistent workspace snapshot into an inspectable report: reading
positions and visits, bookmarks, personal annotations, comparisons, review
testimony, and relations beyond the published tree. This belongs to SOL's BEING
stage, the reader and virtual shell.

The report is derived, not canonical. Editing it does not correct Hegel's text or
update the workspace. It is not a database backup, an import format, or proof that
the source was inspected. Use JSON export for structured portable workspace data
and SQLite backup for a reopenable workspace copy.

## Export from the terminal

Select an existing workspace with its usual corpus. No actor is needed for this
read-only action:

```sh
sol --workspace study --workspace-export --export-format markdown > study.sol-workspace.md
```

Add the current canonical Markdown of referenced records when the inquiry needs
the text beside its notes:

```sh
sol --workspace study --workspace-export --export-format markdown --include-passages > study-with-text.sol-workspace.md
```

The ordinary export remains JSON, with the same structure as before:

```sh
sol --workspace study --workspace-export > study.sol-workspace.json
```

Exports go only to standard output. SOL does not choose a file, overwrite a
destination, or set permissions on a redirected file. Your shell's redirection
can overwrite an existing file; choose a new destination deliberately. The
`.sol-workspace.md` and `.sol-workspace.json` suffixes exclude personal exports
from this repository and its source archives. A different suffix is not protected
by those rules. Keep reports outside the canonical corpus. They may contain
private questions, actor labels, and, with `--include-passages`, local book text;
review their contents before sharing.

## Export inside the shell

```text
workspace export --format markdown
workspace export --format markdown --include-passages
workspace export --format json
```

These display the report or JSON in the current shell. There is no host-shell
redirection inside SOL's virtual shell. Use the terminal command above to save an
export. `--include-passages` is valid only with Markdown export, and format flags
belong only to the export action.

Export does not move the reading cursor, add a visit, create an actor profile, or
change authored records. A coherent workspace snapshot is rendered without
parsing the PDF, loading an optional interface framework, or changing the corpus.

## What the report retains

The report includes workspace identity and edition provenance, the current saved
position, previous visits, bookmarks, personal-note authors and timestamps,
comparison questions and ordered references, review events, and attributed
directed relations. Every referenced UUID receives a provenance entry against the
currently loaded canonical record graph.

Version-2 workspaces include all stored annotation snapshots, not only the latest
body. A version-1 workspace has no stored edit history; export says so rather than
inventing earlier revisions. An explicitly upgraded legacy note retains its
available `legacy_baseline`, which is not a reconstruction of edits before the
upgrade.

Personal Markdown and included canonical Markdown are preserved literally in
fenced blocks, including italics markers, line breaks, and mathematical notation.
Fence lengths adapt to the content. Links, image references, and raw HTML in those
bodies are inspectable text, not active instructions for a Markdown viewer to
fetch remote content or display a local image. This also keeps personal notes
visibly separate from Hegel's prose and the edition's editorial material.

Metadata values use literal inline code spans, so UUIDs, paths, and timestamps
remain copyable without escaping their punctuation. The report records the loaded
manifest and index digests, with document digests beside referenced records, not
an inventory of every unreferenced document. This framing follows
[CommonMark code spans](https://spec.commonmark.org/0.31.2/#code-spans) and
[fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks).
Unsafe terminal and bidirectional controls are shown as visible escapes rather
than allowed to obscure the report.

## References are not frozen quotations

Stable UUIDs identify records independently of titles, paths, and text hashes.
The report discloses missing references and retired IDs with their redirects
instead of silently repairing them. Notes and reviews retain their recorded
binding digests; changes to the current canonical text remain visible. Comparison
and relation endpoints are live references and do not prove the exact wording
their author originally saw.

`--include-passages` includes current canonical Markdown only for referenced
records, once per resolved record. It does not export the whole book or recreate
historical canonical text. If the text changed after a note or review, the current
quotation is not relabelled as the earlier inspected version.

The source SHA-256 is the digest declared in corpus provenance, not a claim that
this export physically verified PDF bytes. Current review testimony binds its
inspected text digest and declared PDF fingerprint; it does not bind every page
label, attribution field, rectangle, or image. A reader's `verified` outcome stays
attributed testimony and never upgrades canonical transcription status.

## A boundary for the next steps

The report gives a human-readable handoff for an inquiry without making another
correction surface or storage schema. Scripts should continue using JSON for
structured workspace data and the corpus's JSONL index for canonical records.
Selected-span annotations, previewed import and restore, and richer inquiry
composition remain separate future decisions. See [the workspace plan](WORKSPACE_PLAN.md)
for the implemented persistence boundaries.
