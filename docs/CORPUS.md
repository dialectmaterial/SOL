# SOL corpus contract

The corpus is the foundation shared by the terminal reader, simple Python scripts,
classifiers, and future tools. Its canonical source is human-readable Markdown.
The JSONL index is generated from that Markdown, not independently maintained.
Corrections belong in the Markdown; rebuilding the index does not read the PDF.

## Local use and copyright

The supplied Cambridge translation by George di Giovanni is copyrighted. The PDF,
the converted text, indexes containing that text, and source-image crops must remain
local and excluded from Git unless the necessary redistribution permission is
obtained. Converting PDF to Markdown does not make the translation freely
redistributable. Your lawful access conditions still apply to local use.

Publish the converter, reader, contract, and synthetic tests—not this edition's
corpus. SOL's software does not grant rights to the book. Review the actual Git
changes before committing; do not assume that a filename alone protects private
material.

## Create, inspect, and index

For normal first-time setup, run `python3 scripts/install.py` from the checkout,
then `sol`. If no corpus is configured, SOL asks for the supported PDF, imports
it once into the SOL user-data directory, validates it and saves the location.
This uses the same audited converter described below. Unsupported fingerprints
are explained rather than converted with guessed edition rules. Existing corpora
are never regenerated. The following is the explicit maintenance workflow, not
a prerequisite for beginning to read.

Python 3.10 or newer is required. The converter needs Poppler's PDF tools and the
CommonMark parser included in the normal installation (`corpus` remains a compatibility extra). Dependency requirements are
defined once in `pyproject.toml`. On Debian/Ubuntu:

```sh
sudo apt install poppler-utils
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install '.[corpus]'
```

From the project directory, create the local candidate conversion:

```sh
python3 -m sol.corpus.convert convert --pdf Hegel-SOL.pdf
```

The default destination is `local-corpus/`. Read its manifest and audit information
before treating the extraction as an authoritative transcription. Open the
Markdown alongside the PDF, especially where the audit reports ambiguity or a
mathematical layout.

The converter looks for `Hegel-SOL.pdf` in the working directory, then in
`sources/`; its `--pdf PATH` can select another filename. The ordinary reader
uses the indexed corpus and does not open the PDF. Renaming the PDF does not
change its SHA-256 fingerprint or the identifiers in an existing corpus. The
manifest's source filename records the name used at import, not a live path that
the reader needs to open. Leave that historical provenance intact and do not
reconvert an existing corpus merely because its source PDF has been renamed.

After making canonical Markdown corrections, rebuild the index:

```sh
python3 -m sol.corpus.convert index local-corpus
```

The lower-level contract tool can also rebuild or check the generated index:

```sh
python3 -m sol.corpus.contract local-corpus
python3 -m sol.corpus.contract local-corpus --check
```

Use the corpus in the existing terminal reader:

```sh
python3 -m sol --structure
python3 -m sol --corpus local-corpus -r
python3 -m sol --corpus local-corpus -n
```

The installed reader can remember a default corpus independently of the working
directory:

```sh
sol --set-corpus /absolute/path/to/SOL/local-corpus
cd ~
sol
```

`sol` opens the fullscreen reader and remembers the last selected actor and that
actor's workspace for this corpus and source. Missing choices are requested on
first use. `--shell` opens the optional book command interface. Initialize the
corpus identity explicitly first, as described below. `-r` prints one random
passage; `-n` opens a temporary reader without actor profiles or workspace
databases. `--shell -n` chooses a temporary command interface. The fullscreen
reader needs an interactive terminal; one-shot commands support pipes. Setup
does not consume piped commands to answer missing identity questions.

`--set-corpus` validates the corpus before saving its absolute path in
`$XDG_CONFIG_HOME/sol/config.json`, with `~/.config/sol/config.json` as the default
location. It stores a location, not a copy of the corpus. Run the command again if
the corpus moves. `python3 -m sol --set-corpus DIRECTORY` supplies the same setting
when running directly from the checkout.

The argument is an indexed corpus directory, not a PDF filename. If only the
supported source PDF is available, follow the conversion procedure above, then
select the resulting `local-corpus` directory. `--set-corpus` never converts a PDF.

Reader discovery proceeds through an explicit `--corpus`, the `SOL_CORPUS`
environment variable, `./local-corpus`, the saved default, a local pipx
installation's remembered source checkout, and `local-corpus` in a recognized SOL
checkout, whose project identity is checked in `pyproject.toml`.
A local `pipx install .` can therefore find the checkout's corpus from
another directory without packaging its private contents. An installation from
GitHub should use `--set-corpus` to locate separately supplied local text. Refresh
installed code with `pipx reinstall sol-organizes-logic` after an update.

Reading verifies the generated index and does not parse the PDF or require
`markdown-it-py`. A missing, invalid, or stale selected corpus produces an error
rather than silently trying another source. Ordinary reading never falls back to
PDF extraction. Explicit `sol --pdf PATH -r` selects the slower legacy PDF reader, whose
identifiers are separate from corpus UUIDs; `--pdf` and `--corpus` are mutually
exclusive. Help, version information, and `guide` remain usable without
a corpus, and the structure command can show an abbreviated outline.

Do not rerun the initial conversion over an existing canonical corpus. That risks
discarding corrections and allocating new IDs. Correct the existing Markdown and
reindex. A future import of a different source must be a separate, explicit
reconciliation operation, not an overwrite disguised as a refresh.

## Physical files versus book structure

The local corpus separates doctrine/chapter Markdown from introductory, editorial,
note, and reference material. A chapter is a practical editing unit; not every
heading or paragraph needs its own physical file. The manifest lists the exact
document filenames rather than relying on a directory scan to infer reading order.

The logical hierarchy is explicit in each record's `parent_id`. It retains the
edition's volumes, doctrines/books, sections, chapters, subdivisions, Remarks, and
introductory texts. Shared prefaces and introductions must not be misattributed to
the Doctrine of Being merely because they precede it physically.

The terminal's three-root view—`/BEING`, `/ESSENCE`, `/CONCEPT`—is a convenience
view defined by `reader_path` metadata. In that view, shared opening texts may
appear under `/BEING`; their canonical parentage remains separate and accurate.
Directory-owned prose is exposed as `00-introduction.txt`. Those are virtual reader
files, not necessarily separate physical Markdown documents.

Editorial material is preserved rather than deleted, but distinguished from
Hegel's main text. Bibliography and index entries remain reference records. Notes
remain separate records with links to their callouts, including nested note
relations where needed. Default quotations must not mix these categories.

## Canonical Markdown records

Content uses CommonMark: ATX headings, paragraphs, `*emphasis*`, `**strong emphasis**`,
quotations, lists, links, and code where appropriate. Small HTML anchors provide
stable link targets. HTML subscript/superscript can retain mathematical typography
that ordinary Markdown cannot express. The canonical Markdown is preserved in the
index; plain text is derived with a real CommonMark parser, not regular-expression
formatting removal.

Every content record is explicitly delimited:

```markdown
<!-- sol:{"attribution":{"author":null,"role":"synthetic_example","status":"unresolved"},"id":"bf063808-ce2b-4673-9fd2-4cd2e91f02e1","order":1,"parent_id":"1776818d-601c-4c9a-ac73-dce6d64a7f32","sources":[{"pdf_page":8,"printed_page":"viii"}],"type":"paragraph"} -->
<a id="bf063808-ce2b-4673-9fd2-4cd2e91f02e1"></a>

*A synthetic example*, not an excerpt from the book.
<!-- /sol -->
```

This example's parent and page labels are illustrative. In a real corpus, the parent
must exist and the source reference must match the page inventory.

The opening HTML comment contains one compact JSON object on one line. The UUID
anchor immediately follows it. The closing comment ends the record. All nonblank
canonical content must be inside records: unindexed headings or prose are rejected.
Section records begin with an ATX heading; deeper hierarchy is expressed by parent
IDs, not by inventing non-CommonMark headings with seven or more `#` characters.

### Required metadata

| Field | Meaning |
| --- | --- |
| `id` | Permanent, opaque, lower-case UUID. |
| `type` | Content category, such as `section`, `paragraph`, `quotation`, `list_item`, `formula`, `note`, `reference`, or `index_entry`. |
| `parent_id` | Parent record UUID, or `null` for a root record. |
| `order` | Unique nonnegative integer expressing corpus reading order. |
| `sources` | Ordered source references with one entry per contributing PDF page. |
| `attribution` | Object containing `author`, `status`, and `role`. |

Each source reference contains `pdf_page` and `printed_page`. PDF pages are
one-based integers; printed labels are strings so that Roman numbering survives
without being confused with PDF page positions. Unlabelled pages use `null`.
Optional `bbox` is `[x0, y0, x1, y1]` in the importer's PDF-page coordinates and
must be a finite, nonnegative rectangle. Multi-page paragraphs retain all
contributing source pages rather than receiving only their first page's label.

Optional metadata includes `title`, `label`, logical `path`, `reader_path`,
`reader_title`, `heading`, `note_ids`, `backlinks`, and review information. Titles,
labels, and paths are useful context, but are not identity. Keep title metadata
consistent when editing a visible heading.

Attribution records uncertainty instead of manufacturing authorship. For example,
`author` may be `null` and `status` may be `unresolved`; an inference can be labelled
`inferred` rather than `confirmed`. Hegel's main prose uses author
`G. W. F. Hegel` and role `main_text` for the current reader. Editorial material and
notes use separate roles. A note's numbering alone is not sufficient proof of its
author, especially when the note contains mixed editorial and historical material.

## Identity and corrections

IDs are allocated once when records enter the canonical corpus. They are not
derived from titles, page numbers, order, or text hashes. Changing text, emphasis,
a heading, or its position must not change the record's ID. Hashes serve integrity
checks only; they are not identity.

Permanence applies within that corpus, not across independent initial conversions.
Two conversions of the same PDF can assign different UUIDs to equivalent passages.
To share a reference with someone using a different conversion, include its edition,
printed and PDF pages, logical location, and a distinctive search phrase alongside
the ID. Rebuilding an existing corpus index preserves the IDs in its Markdown.

When editing:

1. Preserve the opening marker's `id` and the matching anchor.
2. Correct the Markdown body; update related title/attribution/provenance metadata
   when the correction requires it.
3. Preserve real paragraph boundaries, quotations, lists, and meaningful emphasis.
4. Rebuild the JSONL index and inspect the validation result.

Splitting, merging, or deleting records is a substantive corpus edit, not a formatting
shortcut. Preserve an existing ID for the content it still identifies, allocate IDs
only for genuinely new records, and update affected parent and note references.
Do not reuse a removed record's ID for unrelated text. Such changes should be
documented in an editorial correction log. The initial correction pass retains
eight retired UUIDs as `retired_record` tombstones with redirect metadata, preserving
their identity and explaining where applicable content now belongs. A tombstone
is editorial history, not a passage: exclude `retired_record` from classifier
text and ordinary reading. Follow its redirect metadata when reconciling old
references, rather than treating its explanatory body as source prose.

### Corpus identity for persistent workspaces

Record UUIDs identify passages within a corpus. A separate manifest `corpus_id`
identifies that corpus lineage; it is an opaque lower-case UUID, not the PDF hash,
directory name, or a selected root record. New conversions include this identity.
Older corpora without it remain readable through one-shot actions and `sol -n`,
but the default persistent reader requires explicit initialization:

```sh
sol-corpus-check local-corpus --initialize-identity
```

This verifies the existing corpus before adding the identity to `corpus.json` and
updating the manifest fingerprint in `index.meta.json`. Canonical Markdown, passage
IDs, and `index.jsonl` remain unchanged. Running it again retains the existing
identity. It needs neither PDF extraction nor the optional Markdown parser. Do not
assign a new identity merely because you move or rename a corpus.

The metadata pair is committed with index metadata last. An interrupted update
fails verification rather than silently accepting inconsistent provenance; inspect
the corpus and explicitly reindex if recovery is needed. Workspace reads never
initialize identity or repair this pair automatically.

Workspaces use separate local SQLite files, not records inserted into canonical
Markdown. Their default directory is `$XDG_DATA_HOME/sol/workspaces`, falling back
to `~/.local/share/sol/workspaces`; `--workspace-dir DIRECTORY` overrides it. A
database is bound to its corpus identity and source fingerprint. It refuses an
incompatible corpus instead of guessing that equal source filenames imply equal
records. Missing references remain unresolved, and retired IDs retain their
original identity while exposing redirect targets.

Default shell onboarding offers up to ten recognized workspaces for the selected
corpus identity and source fingerprint, inspecting candidates read-only and sorting
by their latest recorded activity. A displayed number selects a workspace; an
entered name receives normal workspace validation. `-n` and `-r` do not consult
this catalog. Onboarding also requires an actor label;
`--workspace NAME` and `--actor NAME` each skip only their corresponding question.
Accepted actor labels are kept separately in `$XDG_DATA_HOME/sol/profiles.sqlite3`,
or `~/.local/share/sol/profiles.sqlite3`. These are local attribution labels, not
authenticated accounts or operating-system identities. Registering a new label
does not rewrite older authors or migrate a workspace. Read-only
one-shot workspace commands do not require or create an actor profile.

Reader annotations, comparison questions, directed relations, and review decisions
retain their explicit actor attribution. Whole-record annotation bodies are literal
Markdown, separate from the edition's notes. Optional `note draft [--on ID]` captures
the target UUID and text digest before input, accepts an explicit save, and refuses
changed targets or corpus generations before inserting one new note. Cancelled
drafts are discarded. New workspaces use schema version 2, retaining append-only
annotation snapshots. `note edit NOTE_ID` uses the enhanced multiline editor;
basic input requires `note edit NOTE_ID "TEXT" --expect-revision N`. Saving requires
the original actor and an unchanged note revision and corpus generation. The
original target and inspected-text digest are retained. `note history NOTE_ID`
shows saved bodies; a no-op save adds none. Existing version-1 workspaces remain
unchanged on open and still support reading and new notes. Explicit
`workspace upgrade FILE.sqlite3` or `sol --workspace NAME --workspace-upgrade FILE.sqlite3`
creates a verified version-2 copy without replacing the original or switching an
open session. Legacy notes receive their current body as a baseline, with no
invented editor or preceding edit history. None of this modifies canonical Markdown.
Review events bind
the inspected Markdown digest and declared PDF fingerprint, not complete attribution
or source-location metadata. The reader distinguishes matching and stale bindings
and conservatively marks reviews of retired targets stale. `verified`
remains a reader's testimony, not a change to canonical
`transcription_status` or `random_eligible`. Corrections still belong in canonical
Markdown followed by reindexing.

`sol --workspace NAME --workspace-export` writes a consistent JSON snapshot of
workspace references, authored records, and history to standard output. Version-2
exports include `annotation_history`; version-1 exports retain their schema version
without synthetic history. Use the
`.sol-workspace.json` suffix for exported files so they remain excluded from Git
and source archives. Export is available; importing, selected-span anchoring, and
a full-screen review interface remain future work. See
[WORKSPACE_PLAN.md](WORKSPACE_PLAN.md) for command syntax
and the boundary between the canonical book and a reader's inquiry.

## Notes, bibliography, and index

Paragraphs or notes with callouts list their target note UUIDs in `note_ids`.
Each target note lists those referring records in `backlinks`. The relationship is
reciprocal and validated. A nested note can have a note as its `parent_id`; its
callout remains a separate `note_ids` relationship. Original labels are preserved
as labels, not repurposed as permanent IDs.

A recognized callout is displayed as a clickable superscript in canonical
Markdown:

```html
<sup data-sol-note="NOTE_UUID">[14](relative-note-file.md#NOTE_UUID)</sup>
```

Here `NOTE_UUID` stands for the actual lower-case UUID. The annotation UUID, link
fragment, and record's `note_ids` must agree. The generated `plain_text` omits
these recognized callouts so a note number cannot become fused to a prose word
or mistaken for classifier input. Ordinary mathematical `<sup>2</sup>` remains
visible. Unclosed, unregistered, or mismatched annotated links are rejected.

The importer represents a note as a `note` container with its preserved label,
source span, attribution, and backlinks. Its body paragraphs are separate
`note_paragraph` child records. To retrieve the complete note, select the target
`note` record, then its children with `parent_id` equal to that note UUID, sorted
by `order`. Do not assume the note container's heading alone is its full text.
Children can themselves carry `note_ids` for references to other notes. A note's
semantic parent is its first identified referring paragraph rather than whichever
heading happens to precede the physical footer; additional callers remain in
`backlinks`. Unlinked or ambiguous notes retain explicit review information.

The bibliography and subject index are retained as their own content categories.
Printed page references and cross-references must remain visible and machine
accessible. An index is editorial evidence useful for navigation or classification
hints—not automatically a set of authoritative training labels. Reference text
must not be incorporated into the default Hegel-only classifier input by accident.

The reader's ordered `cat` and sequential navigation include Hegel's formula
records as well as prose. A mixed prose/mathematics record keeps its `paragraph`
type with `contains_math: true` rather than losing its prose classification.
Uncertain cases can have `random_eligible: false`; this is an actual JSON boolean,
not the string `"false"`. `contains_math` is also a JSON boolean. Random quotations
exclude formula-only records and explicitly ineligible passages. Both remain in ordered reading,
with source facsimiles where needed. Classifiers should use the review and
attribution metadata to choose their own deliberate inclusion policy. Notes,
editorial material, bibliography, and index entries remain available in the full
corpus rather than being mixed into those quotations.

`transcription_status`, when supplied, is an extensible lower-case token such as
`needs_review`, `needs_visual_review`, or `reviewed`. The reader warns and counts
pending source review for the first two statuses, independently of formula type
or random eligibility. An absent status is not proof of verification. Reader
titles and headings must be strings; `reader_path` must be an absolute virtual
path, not a host filesystem path.

The reader retains the full verified canonical record graph, including notes and
editorial records that it does not quote by default. Corpus-backed JSON passages,
such as `sol -r --json`, expose their indexed record under `canonical`, retaining Markdown,
attribution, parent IDs, note links, and all source references. The top-level
`text` is a reader presentation, not a replacement for canonical Markdown;
`needs_source_review` exposes the reader's explicit pending-status check.
The separate `corpus` object exposes the verified import identity, edition, and
source provenance without repeating the entire manifest and page inventory.
Its `id` is `null` for an older corpus that has not initialized its identity.

## Manifest and generated JSONL

`corpus.json` records at least:

- `contract_version`: currently `1`.
- `corpus_id`: optional for older corpora, required for persistent workspaces;
  explicitly initialized as a permanent lower-case UUID.
- `edition`: edition and translation metadata, with completeness/review status.
- `source`: source filename, SHA-256 fingerprint, and PDF page count.
- `documents`: exact relative Markdown filenames.
- `page_inventory`: every PDF page, its printed label, and its disposition.

Inventory dispositions are `records`, `blank`, or `excluded`. Blank/excluded pages
require a reason. Every page declared as `records` must be cited by at least one
indexed record. A cited page's printed label must agree with the inventory. The
inventory must cover every PDF page, including front matter and reference matter.
This makes exclusions explicit instead of silently throwing content away.

The supplied PDF has missing front-matter printed pages **l** and **lxix**. Preserve
those as source gaps in the manifest/review information. They cannot be recovered
from this PDF, and the converter must not invent their content. Consequently,
“source complete” means accounting for the supplied PDF; it does not mean that the
supplied PDF is a complete copy of the published edition.

`index.jsonl` contains one JSON object per line, in reading order. Records retain
their canonical metadata and add `markdown`, `plain_text`, `document`, ancestor
`context`, and a content digest. Scripts can filter by `type` and attribution while
retaining IDs, hierarchy, notes, and source references. No Markdown interpretation
is needed to consume an already generated index.

`index.meta.json` records the manifest, source, document, and index fingerprints
plus the indexed-record count. Index replacement is atomic; metadata is written
last. A partial update or stale Markdown is detected rather than silently used.
Reindexing rejects duplicate/malformed UUIDs, duplicate or out-of-order order
values, missing/cyclic parents, broken reciprocal note links, unsafe file paths,
undeclared canonical documents, and invalid provenance.

## What validation does—and does not—prove

The first conversion is a candidate transcription with an audit trail. Structural
and coverage checks provide concrete evidence: known headings, page accounting,
stable links, provenance, and deterministic indexing. They do not prove that every
paragraph boundary, italic span, note attribution, quotation, or mathematical
symbol is semantically correct.

Mathematical arrangements need special attention. A source crop or explicit review
flag is preferable to a confident but incorrect flattened formula. Preserve the
available text, identify approximation/uncertainty, and link it to the source page.
Do not conceal unresolved cases merely to produce a clean validation report.

Human audit should proceed chapter by chapter against rendered PDF pages. Record
the checked scope and unresolved issues. Claims of complete proofreading require
that work—not merely a successful converter run or a count of indexed pages.
