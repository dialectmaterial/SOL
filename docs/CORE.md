# SOL CORE — Canonical Corpus, Identity, Provenance, and Interchange

**Status:** implemented contract and preservation rules, with explicitly marked future decisions; 17 October 2026, provider and collection decisions 18 October 2026; framed by the leading [SPECULATIVE](SPECULATIVE.md) document on 21 October 2026.  
**Companions:** [SPECULATIVE](SPECULATIVE.md) (leading) · [Architecture](ARCHITECTURE.md) · [BEING](BEING.md) · [ESSENCE](ESSENCE.md).  
**Original adoption:** 17 October 2026 at `main` `1d200e4`.

## 1. Why CORE exists

**CORE's place ([SPECULATIVE §4](SPECULATIVE.md#4-initial-repository-hierarchy)).** CORE is a separate service layer for corpus organization, retrieval, metadata, addressability and shared persistent research state. Its exception from the logical hierarchy is an agreed **practical boundary**, not a declaration that it can never be rethought. It serves BEING and ESSENCE; it must not silently absorb ESSENCE's computational responsibilities or become a dumping ground. CORE is also SOL's custodian of the **primary working text** for its agents: the edition held here is the source they read before structural decisions ([SPECULATIVE §5.1](SPECULATIVE.md#51-source-hierarchy)).

**Workspaces stay in BEING. Decision (maintainer, 22 October 2026).** SPECULATIVE assigns *shared* persistent research state to CORE; the workspace is attributed reading work used only by the reader, so it stays in BEING (§7) and CORE stays independent of it (§8, item 7). It moves to CORE, or splits, only once ESSENCE actually reads or writes the same research state ([placement register](ARCHITECTURE.md#9-placement-register)).


CORE is SOL's shared, noninteractive foundation. It gives a *specific text* stable identities and verifiable provenance across reading, annotation, correction, analysis and rendering. It is not an independent Hegelian phase, an operating-system kernel, a GUI or a model host. It must not depend on a terminal emulator, Neovim, a machine-learning framework, a real shell or internet access.

**Present scope:** the existing verified canonical edition of Hegel's *Science of Logic*, Cambridge translation by George di Giovanni. General PDFs, scans, other works and multiple-translation alignment are **out of scope for this development cycle**. Do not remove current metadata or bake away future possibilities, but do not prematurely build a generic ingest architecture either.

**CORE as a provider (decision, maintainer, 18 October 2026).** ESSENCE is to run on ordinary text files without CORE; when CORE is present it is the provider that adds verified identity, edition and generation binding, provenance and source return ([Architecture §2](ARCHITECTURE.md#2-logical-divisions-and-component-responsibilities), [ESSENCE §4](ESSENCE.md#4-interaction-model-and-inquiry-contract)). That boundary is an adapter around today's public API; it changes neither API version 1 nor the reference protocol. Results from files carry a file digest instead of a CORE generation and cannot claim CORE's guarantees.

**Future collections (proposed requirements, not a schema).** Later analyses may compare a target with an author's oeuvre, a bibliography or a thematic collection. When that arrives: a text may belong to several collections, so membership is not a single directory parent; edition, translator, source language and attribution stay attached to every record an analysis uses; and large collections need indexed, batched access. None of this is implemented, and any new corpus schema or protocol needs its own versioned proposal and approval.

**Fundamental separation:** source PDF (evidence) → carefully attributed and reviewable canonical **Markdown** (human-maintained text and structure) → generated **JSONL index** (derived machine-readable view) → replaceable reading/analysis projections. Physical pages are retained as source locators; they do not define the book's logical ontology. Hierarchy and edited typography must be respected rather than treated as computationally meaningless noise.

## 2. Actual artifact and identity layers

| Layer | Function | Mutable? | Identity rule |
|---|---|---|---|
| Source PDF and page/crop evidence | The historical source for import and visual checking | Preserve source unchanged | Source SHA-256 + page inventory; filename not identity |
| Corpus manifest `corpus.json` | Corpus lineage, edition/translation, source and document inventory | Explicit controlled maintenance only | Permanent `corpus_id` UUID; edition/source fingerprints |
| Canonical Markdown documents | Human correction surface for passages, sections, notes, formula evidence | Correct with review/audit, never blind reconversion | Embedded immutable record UUIDs, type, parent/order, attribution, source references |
| Generated JSONL + metadata | Verified searchable/readable structured projection | Regenerate from canonical documents | Same record UUIDs; content/generation hashes detect freshness |
| CORE book projection/snapshot | Validated in-memory graph for clients | Ephemeral read-only contract | Verified references, retirement chains and canonical source positions |
| BEING workspace SQLite | Personal readings, notes, bookmarks, comparisons and claims | Independently versioned author operations | References CORE UUIDs; **not** part of canonical book |
| ESSENCE artifacts | Reproducible measurements, embeddings and method outputs | New versioned result per experiment | Input UUIDs + digests + projection/model/method version |

The private local corpus and copyrighted Cambridge translation, source images, JSONL text and personal analyses should remain outside the public repository. The code and synthetic fixtures can be published; the conversion does not remove copyright or rights in the original translation.

### Canonical record structure

Every canonical content record is delimited in Markdown by `<!-- sol:{...} -->` and `<!-- /sol -->` with a stable HTML UUID anchor. A minimal illustration (synthetic—not Hegel text):

```markdown
<!-- sol:{"id":"bf063808-ce2b-4673-9fd2-4cd2e91f02e1","type":"paragraph","parent_id":"1776818d-601c-4c9a-ac73-dce6d64a7f32","order":1,"sources":[{"pdf_page":8,"printed_page":"viii"}],"attribution":{"author":null,"role":"synthetic_example","status":"unresolved"}} -->
<a id="bf063808-ce2b-4673-9fd2-4cd2e91f02e1"></a>

*A synthetic example, not book content.*
<!-- /sol -->
```

The schema requires opaque lowercase UUID `id`, a record `type`, parent UUID or null, unique nonnegative reading `order`, ordered source references, and explicit attribution. Types include `section`, `paragraph`, `quotation`, `list_item`, `formula`, `note`, `reference`, and `index_entry`. Source records use **one-based PDF page integer** and distinct printed-page label as string/null (preserving Roman numerals); optional bounding boxes are source evidence with explicitly declared coordinate conventions. A multi-page passage keeps all contributing PDF references. Editor/translator notes, front matter, formula records, indexes and Hegel main prose are not equivalent source categories.

Metadata may include title/heading/path, note links, reader aliases, image references and review state. **Paths and headings are not identity.** The three virtual doctrine roots `/BEING`, `/ESSENCE`, `/CONCEPT` can be convenient navigation aliases without falsifying the canonical parentage of prefatory material. Do not infer the book's actual logical tree from a filesystem path string or visual indentation.

### Source typography, formulas, annotations

Canonical Markdown uses CommonMark semantics; emphasis, strong and inline code map to terminal styles. Links, notes and HTML sup/sub remain part of the source semantics, but this does not imply clickable links or faithful superscript/subscript typesetting in the native reader. Footnote callouts (`<sup data-sol-note="UUID">`) are omitted from `plain_text`; the typography projection reports each callout's plain-text offset so a view can show the number in place without it entering the text. A converted note is a `note` record holding only its heading; its text is in `note_paragraph` children ordered by `order`, which views must read. Plain-text projection and raw Markdown are different coordinate systems. Mathematical `formula` records and `contains_math: true` mixed passages must retain their evidence, flags and sources, even if a terminal cannot display the notation accurately. A facsimile crop is safer than an invented fraction/exponent transcription. Where a person or agent retypes mathematics from the crop, the record keeps its pending `transcription_status` until a human confirms it (`reviewed` is the conventional confirmed token), and the change is recorded in a corpus audit file; the local corpus's 17 October retyping is listed in `audit/math-retyping-2026-10-17.json`. Reader annotations have separate attributed workspace records, never modifications to the canonical author text.

## 3. Conversion, extraction and review: what currently works

**Current first-run setup:** after installation, interactive `sol` asks for an initial local PDF only when no corpus is configured. It accepts only the exact audited Cambridge/di Giovanni fingerprint, not arbitrary editions/scans or renamed lookalikes with different bytes. It validates and stores an indexed corpus under the user's SOL data directory. The checkout installer itself installs/checks tools; it does not prompt for or convert the book. An already configured corpus is reused; ordinary reading does **not** re-extract the PDF or silently switch to another one.

The historical edition-specific converter is maintained for the audited source. OpenDataLoader **2.5.13** is included in the full Python installation, but running this replaceable extraction adapter is an explicit maintenance action, not ordinary reading or first-run import. It creates **unreviewed candidates** (local JSON, with raw elements, selectors, declared backend/source fingerprints and page information). The current adapter's local mode uses `hybrid=off`, images off and does not expose OCR, hosted services, formula enrichment or server fallback; scanned PDFs are therefore not solved. An external extracted JSON can be normalized when its origin/version are clearly caller-declared, not authenticated.

### Safe corpus commands

```sh
sol --set-corpus /absolute/path/to/local-corpus
sol -r
sol --passage RECORD_UUID --context 1
sol-corpus-check /absolute/path/to/local-corpus --initialize-identity
python3 -m sol.corpus.convert index local-corpus
python3 -m sol.corpus.contract local-corpus --check
```

`--set-corpus` selects an **indexed directory**, not a PDF. After reviewed canonical Markdown corrections, rebuild the generated index; do not rerun initial conversion and reallocate IDs. If an older corpus has no permanent lineage identity, initialize it explicitly; do not silently generate a new ID when reading. Index checks cover canonical documents, graph and metadata; a passing check does **not** certify the accuracy of the printed book transcription or the physical PDF's contents.

### Bounded extraction-to-review workflow

```sh
mkdir -p .sol-extractions .sol-ingest-work
sol-corpus extract --pdf Hegel-SOL.pdf --pages 80,282-283 --output .sol-extractions/sample.json
# Inspect extracted candidate + canonical record + original PDF before preparing review JSON.
sol-corpus ingest --candidate .sol-extractions/sample.json \
  --review .sol-extractions/review.json --baseline local-corpus \
  --output .sol-ingest-work/reviewed-corpus
```

A review JSON links each candidate element selector exactly once to an existing record or an explicit exclusion, identifies the reviewer and provides reasons and approved replacement Markdown. The first ingestion proof **does not** split, merge, mint or retire records; changes target existing UUIDs and relevant pages. Publish a **new**, validated corpus directory without clobbering the baseline. Preserve original UUIDs, metadata, order, hierarchy, notes, page evidence and untouched text. Review testimony is a declaration, not cryptographic proof a human checked every symbol. Candidate and review artifacts remain private and Git-ignored.

The project must never quietly overwrite audited canonical Markdown from a fresh PDF extraction. This protection matters especially for complex notation, editorial notes and translation variants.

## 4. Core public API and runtime boundary

The exposed `sol.core` **API_VERSION is 1** and is separate from the corpus contract, workspace schemas and wire protocol versions. Example of a noninteractive client:

```python
from pathlib import Path
from sol.core import load_corpus_book, resolve_reference, load_snapshot
book = load_corpus_book(Path('local-corpus'))
passage = book.passages[0]
reference = resolve_reference(book, passage.identifier)
print(reference.target_id, reference.record['sources'])
snapshot = load_snapshot(Path('local-corpus'))
```

CORE exposes shared `Book`, `Node`, `Passage`, corpus discovery, verified `CorpusSnapshot`, passage/record resolution, reference capture/check and bounded serialization. The convenient `Book.passages` is the reader's selected projection of canonical records; it does **not** contain all editorial/front-matter/note/index material. Applications studying all source types must use the full verified canonical graph with explicit filtering. Importing CORE does not start Neovim, an editor, a workspace, source extraction or a model.

**Implementation caveat:** read-only describes the consumer contract, not deep immutability. `Book` and `CorpusSnapshot` still expose caller-mutable collections. Clients must not mutate or cache trust over them; generation/reference verification remains necessary.

Canonical Markdown changes must be deliberate and followed by regeneration/verification. An unchanged source filename or stable page number is not enough to assume the same generation. Retired IDs retain their requested identity and disclosed redirect chain; absent IDs stay unresolved, never automatically mapped by similar wording.

## 5. Source-bound positions and typography

The canonical reader selection is `{requested_id, resolved target, start, end, text, source digest}` with **half-open Unicode codepoint offsets in exact canonical `plain_text`**. It is not a byte offset, terminal cell coordinate, DOM UTF-16 position, raw Markdown span, buffer row, or PDF pixel coordinate.

The implemented Neovim adapter maps between UTF-8 byte boundaries and Python codepoint boundaries; the offline HTML research experiment maps DOM UTF-16 positions (including surrogate-pair checks) back to those same codepoints. Display-only padding, soft wraps and headings cannot become the content of a selection. A viewport resize should change layout, **not** source position. Mismatched projections, unsafe controls and impossible selections must fail clearly, not fabricate an approximate match.

When comparing reader surfaces or exposing ESSENCE input rows, always retain the UUID plus exact text digests and source structure. A quotation made after a corpus change may no longer be the quotation originally inspected. The system should show staleness, not repair it by fuzzy match.

## 6. CORE reference protocol v1 (implemented)

A `sol.reference` JSON envelope, `version: 1`, binds: corpus UUID; edition metadata fingerprint; source SHA-256 and PDF page count; exact manifest/index generation hashes; requested and resolved record UUIDs and entire retirement chain; target Markdown digest; canonical type; page references; limited attribution. It carries **no passage body**, local corpus path, commands, arbitrary metadata, actor credentials, personal-workspace address or write permission. Serialized input/output are bounded to **65,536 bytes**; duplicate JSON keys, malformed strings and nonfinite values are rejected.

```sh
sol reference capture RECORD_UUID --corpus local-corpus \
  | sol reference check --corpus local-corpus
```

Capturing and checking only verify identity against the caller-selected local corpus and current generation. They do not navigate or save visits. Explicit batch capture/check handles **1–1,024 references**, preserving input order and enforcing one consistent generation. A bad input invalidates the entire batch. The v1 policy is **strict generation equivalence**: even an unrelated document correction makes a previously captured envelope stale. That is a deliberate reproducibility choice—not necessarily the final policy for ordinary long-lived passage identity. Any future relaxed policy requires a **new, explicit, tested contract**, not an unnoticed downgrade.

Refusal statuses include invalid/mismatch/stale/unresolved; implementations provide more detailed codes. A matching cryptographic digest is **integrity evidence**, not human author authentication or proof that a PDF facsimile was visually inspected. Never execute packet data or allow a packet to authorize a workspace write.

**Verification cost (19 October 2026).** Every capture or check still verifies the corpus files' fingerprints (manifest, Markdown documents, index, index metadata) and refuses any change. When they match a generation CORE has already loaded and validated in full, it builds the call's records from that verified parse, kept privately as immutable JSON text, instead of re-reading the files; each call still gets new dictionaries. **Decision (approved by the maintainer, 19 October 2026):** inside `sol.core.protocol.single_action(snapshot)`, which the reader opens once per editor request, the caller's in-memory snapshot is compared with the verified copy at the first call only, and that copy is reused for the rest of the action; outside such a block every call compares in full. A modification of the in-memory snapshot during one action is refused by the next action. On the real book this took a section move from about 2.9 s to 0.75 s; strict generation equivalence is unchanged. **Decision (approved by the maintainer, 19 October 2026):** the comparison uses canonical JSON text plus structural equality with a private parsed copy; it refuses changed values, JSON types (`true` for `1`, `2.0` for `2`), tuples for lists, non-string keys and nesting beyond 64 levels (checked once on the verified copy), but accepts an `int` or `float` subclass with an equal value. With the reader's exports checked on its own snapshot, a section move takes about 0.5 s. `load_corpus_book` hands a just-loaded snapshot to this cache before any other code holds it (`remember_verified`), so the reader's first check does not read every file a second time.

### BEING–ESSENCE exchange

ESSENCE receives the reader's position and returns to a source through the reader's own guarded requests ([BEING §6](BEING.md#6-being--essence-without-terminal-dogma)); CORE supplies only the references and their checks. The earlier Kitty/Zsh handoff transport and `sol reference return` were removed on 21 October 2026.

## 7. Workspaces, provenance and deliberate correction

Workspaces are **BEING**, not CORE, even if their references consume CORE IDs. Each is an independent SQLite database, with source-bound bookmarks, notes/revisions and reading checkpoints; comparison groups, review testimony and relations stored by earlier versions remain readable and exportable. Current workspaces use schema 3; recognized legacy schemas can be inspected without automatic upgrade. Operations use transaction/checkpoint guards; backup or upgrade publishes a separately validated non-overwriting copy. Workspace author names are attribution labels, not login authentication. Reader verification testimony does not clear canonical `needs_review` flags.

**Correction protocol:** locate exact source evidence → record uncertainty → correct canonical Markdown and appropriate provenance → reindex → check consistency → inspect impact on retained reading work and analysis artifacts. Keep old identities for corrected records. A new source extract cannot silently rewrite the approved record or move its parent's logical location.

**Future consideration, not an active requirement:** separate imported editions/translations would require separate canonical identities and explicit alignments, since paragraphs and note structures can differ. For this cycle, stay on the single audited source. Do not make new corpus IDs by hashing filenames or conflating different translations.

## 8. Scope and integrity checklist

1. Preserve canonical Markdown as the correction surface; treat JSONL as generated and replaceable.
2. Do not modify record UUIDs or retire/rewrite IDs to make presentation easier.
3. Keep original PDF and copyright-bearing text out of Git; validate fingerprints when using local source evidence.
4. Distinguish source text, translator/editor material, personal notes, inferred structure, model results and research claims.
5. Preserve explicit uncertainty (especially formulas and OCR/review flags).
6. Maintain strict typed references and separate snapshots/generation digests from durable record IDs.
7. Keep CORE independent from Neovim, any particular terminal or shell, user workspace state and ML frameworks.
8. Test malformed/missing/retired records, Unicode, selected-span offsets, corpus edits, concurrent changes, bad Markdown, source mismatch and unsafe input.
9. Do not expand ingestion to arbitrary PDFs or other books during this milestone.
10. Keep the detailed contracts in §§9–10 current; update tests with any actual contract change. Earlier documents live only in Git history.

## 9. Corpus contract v1 in detail

**Copyright and locality.** The Cambridge translation by George di Giovanni is copyrighted. The PDF, the converted text, indexes containing that text and source-image crops stay local and out of Git; converting does not make the translation redistributable. Publish the converter, reader, contract and synthetic tests, never this edition's corpus, and review the actual Git changes before committing rather than trusting a filename.

**Files.** A corpus directory holds `corpus.json` (the manifest), the canonical Markdown documents it lists, the generated `index.jsonl` and `index.meta.json`. The manifest records at least `contract_version` (currently `1`), `corpus_id` (a permanent lower-case UUID, optional for older corpora and required for persistent workspaces), `edition` (edition and translation metadata with completeness/review status), `source` (filename at import, SHA-256 fingerprint, PDF page count), `documents` (exact relative Markdown filenames, in reading order; never inferred from a directory scan) and `page_inventory`. The source filename is provenance, not a live path: renaming the PDF changes neither its fingerprint nor any identifier, and is no reason to reconvert.

**Page inventory.** Every PDF page appears once, including front and reference matter, with its printed label and a disposition: `records`, `blank` or `excluded`. Blank and excluded pages need a reason; every `records` page must be cited by at least one record, and a cited page's printed label must agree with the inventory. The supplied PDF lacks front-matter printed pages **l** and **lxix**; they are recorded as source gaps and never invented. "Source complete" therefore means the supplied PDF is accounted for, not that it is a complete copy of the edition.

**Records.** All nonblank canonical content sits inside records (§2): the opening comment holds one compact JSON object on one line, the UUID anchor follows immediately, and `<!-- /sol -->` closes it; unindexed headings or prose are rejected. Section records begin with an ATX heading, and deeper hierarchy is expressed by `parent_id`, never by headings of seven or more `#`. Required fields: `id`, `type`, `parent_id`, `order`, `sources`, `attribution` (`author`, `status`, `role`). Each source entry has a one-based integer `pdf_page`, a string-or-null `printed_page`, and optionally `bbox` = `[x0, y0, x1, y1]` in PDF points from the page's top-left corner, a finite nonnegative rectangle. Optional metadata includes `title`, `label`, `path`, `reader_path` (an absolute virtual path, not a host path), `reader_title`, `heading`, `note_ids`, `backlinks`, `contains_math` and `random_eligible` (JSON booleans, not strings), and `transcription_status` (an extensible lower-case token: `needs_review` and `needs_visual_review` make the reader warn; an absent status is not proof of verification). Attribution records uncertainty rather than manufacturing authorship: Hegel's main prose uses author `G. W. F. Hegel`, role `main_text`; editorial material and notes use their own roles, and a note's number alone does not establish its author.

**Logical versus physical structure.** Documents are editing units; the logical hierarchy (volumes, doctrines, sections, chapters, Remarks, introductions) is in `parent_id`. Shared prefaces and introductions are not attributed to the Doctrine of Being because they precede it physically; the reader's `/BEING`, `/ESSENCE`, `/CONCEPT` roots are a `reader_path` view. Editorial material, bibliography and index entries are preserved as their own categories, never mixed into default quotations.

**Notes.** A record with callouts lists its target notes in `note_ids`, and each note lists its referring records in `backlinks`; the relation is reciprocal and validated. A callout is `<sup data-sol-note="NOTE_UUID">[14](note-file.md#NOTE_UUID)</sup>`, where the UUID, fragment and `note_ids` agree; `plain_text` omits recognized callouts, while ordinary mathematical `<sup>2</sup>` stays visible, and unclosed, unregistered or mismatched annotated links are rejected. A note is a `note` container (label, sources, attribution, backlinks) whose text is in `note_paragraph` children ordered by `order`; a note's semantic parent is its first identified referring paragraph, other callers stay in `backlinks`, and nested notes may have a note as parent.

**Identity and corrections.** IDs are allocated once, on entry to the canonical corpus, and are never derived from titles, pages, order or text hashes; hashes are integrity checks only. Permanence holds within a corpus, not across independent conversions: to share a reference with another conversion, add the edition, printed and PDF pages, location and a distinctive phrase. To correct: keep the opening marker's `id` and anchor, correct the body and related metadata, preserve paragraph boundaries and meaningful emphasis, reindex and inspect validation. Splitting, merging or deleting records is a substantive edit: keep an ID for the content it still identifies, mint IDs only for new records, never reuse a removed ID, and record the change. Retired IDs remain as `retired_record` tombstones with redirect metadata, excluded from reading and analysis text.

**Corpus identity.** `sol-corpus-check DIRECTORY --initialize-identity` verifies an older corpus, then adds `corpus_id` to `corpus.json` and updates the manifest fingerprint in `index.meta.json` (written last). Markdown, passage IDs and `index.jsonl` are unchanged; running it again keeps the identity. An interrupted update fails verification instead of being repaired silently; reads never initialize identity.

**Generated index.** `index.jsonl` holds one object per record in reading order, with the canonical metadata plus `markdown`, `plain_text` (derived with a real CommonMark parser), `document`, ancestor `context` and a content digest; consumers need no Markdown interpretation. `index.meta.json` records the manifest, source, document and index fingerprints and the record count; replacement is atomic, metadata last. Reindexing rejects duplicate or malformed UUIDs, duplicate or out-of-order `order`, missing or cyclic parents, broken reciprocal note links, unsafe paths, undeclared documents and invalid provenance. Corpus-backed JSON passages (`sol -r --json`) expose the indexed record under `canonical` and the import identity under `corpus` (`id` is `null` for an uninitialized older corpus); their top-level `text` is a presentation, not canonical Markdown.

**What validation proves.** Structural and coverage checks give evidence of headings, page accounting, links, provenance and deterministic indexing. They do not prove paragraph boundaries, italics, note attribution, quotations or mathematical symbols. Prefer a source crop or review flag to a confident flattened formula, audit chapter by chapter against the rendered PDF, and record the checked scope; a converter run is not proofreading.

## 10. Reference protocol v1 in detail

**Envelope.** `protocol` = `sol.reference`, `version` = integer `1`; `corpus`: corpus UUID, edition fingerprint, source SHA-256 and PDF page count; `generation`: exact manifest and index SHA-256; `reference`: requested and resolved UUIDs, the complete redirect chain, the target's canonical-Markdown SHA-256, canonical type, source pages and attribution. Source entries carry only `pdf_page`, `printed_page` and optional `bbox`; attribution only `author`, `role` and `status`. No paths, commands, passage bodies, credentials, workspace addresses or arbitrary metadata are carried. The edition fingerprint is the SHA-256 of `json.dumps(edition, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` encoded as UTF-8.

**Wire.** Output uses JSON Unicode escapes, so metadata cannot carry terminal or bidirectional controls; decoding restores the strings. Input and output are limited to **65,536 bytes**; oversized references fail rather than truncate. Duplicate keys, nonfinite or overflowing numbers, escaped lone surrogates, wrong types, unknown fields, unsupported versions and malformed chains are errors. File input must be a stable regular file (no symlink, FIFO or device); one envelope per invocation.

**Agreement.** The receiver revalidates its own snapshot and graph, refuses caller-modified snapshot dictionaries, and checks the generation again at the end. Retired requested IDs stay distinct from their targets, and only registered redirects are followed. A successful check returns `status: current` with the binding, IDs, chain, content fingerprint, type, sources and attribution: a receipt, not a new envelope. Failures exit nonzero with `status` (`invalid`, `mismatch`, `stale`, `unresolved`), `error` and, for protocol refusals, a stable `code` such as `corpus_mismatch`, `edition_mismatch`, `source_mismatch`, `generation_changed`, `record_mismatch` or `unresolved_reference`.

**Python.** `load_snapshot`, `capture_reference`, `check_reference`, `encode_reference`, `decode_reference` and `ProtocolError` (with `status` and `code`) are in `sol.core`; importing them loads no reader, workspace, terminal adapter, Markdown parser or extraction engine. `capture_references` and `check_references` take 1–1,024 items, preserve order and chains, load and verify one generation, check it against the caller's snapshot and again before returning, and refuse the whole batch on any bad item. Protocol version 1 is separate from CORE API version 1, corpus contract version 1 and workspace schemas.

**Source lineage:** corpus contract, extraction workflow, public modularity API, reference protocol, workspace plan/exports, reader-action and presentation specifications, audited ingestion documentation, and actual code/tests. The pre-17 October documents they came from are in Git history (removed from the tree on 21 October 2026).
