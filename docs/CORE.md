# SOL CORE — Canonical Corpus, Identity, Provenance, and Interchange

**Status:** implemented contract and preservation rules, with explicitly marked future decisions; 17 October 2026, provider and collection decisions 18 October 2026.  
**Repository baseline:** `dialectmaterial/SOL` `main` at `1d200e4fcbff1ca69f48b5dc96c55765f215f303`.  
**Companions:** [Architecture](ARCHITECTURE.md) · [BEING](BEING.md) · [ESSENCE](ESSENCE.md).

## 1. Why CORE exists

CORE is SOL's shared, noninteractive foundation. It gives a *specific text* stable identities and verifiable provenance across reading, annotation, correction, analysis and rendering. It is not an independent Hegelian phase, an operating-system kernel, a GUI, a workspace database or a model host. It must not depend on a terminal emulator, Neovim, a machine-learning framework, a real shell or internet access.

**Present scope:** the existing verified canonical edition of Hegel's *Science of Logic*, Cambridge translation by George di Giovanni. General PDFs, scans, other works and multiple-translation alignment are **out of scope for this development cycle**. Do not remove current metadata or bake away future possibilities, but do not prematurely build a generic ingest architecture either.

**CORE as a provider (decision, maintainer, 18 October 2026).** ESSENCE is to run on ordinary text files without CORE; when CORE is present it is the provider that adds verified identity, edition and generation binding, provenance and source return ([Architecture §2](ARCHITECTURE.md#2-component-responsibilities), [ESSENCE §4](ESSENCE.md#4-interaction-model-and-inquiry-contract)). That boundary is an adapter around today's public API; it changes neither API version 1 nor the reference protocol. Results from files carry a file digest instead of a CORE generation and cannot claim CORE's guarantees.

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

### Present BEING–ESSENCE handoff (implemented but host-specific)

`sol-kitty` can create a private controlled Kitty pane carrying a checked reference into normal Zsh. In BEING's compatibility command interface, `essence open` captures a source reference; ESSENCE can use `sol reference return [ID]` to publish one proposal. BEING inspects `essence check` and accepts `essence return` (possibly `--accept-move` if the reader position changed). Acceptance checks the same canonical generation/record and ordinary BEING workspace conflict rules. `essence close` ends the owned exchange.

The transport is correlated by a private session nonce and origin digest; window/process lifecycle belongs to the `sol.terminal` adapter, not CORE. No automatic importing of results, saving notes or surrendering actor authority happens. Ordinary zsh is not a sandbox. The next interface should make the semantic handoff terminal-independent without reimplementing identity validation.

## 7. Workspaces, provenance and deliberate correction

Workspaces are **BEING**, not CORE, even if their references consume CORE IDs. Each is an independent SQLite database, with source-bound bookmarks, notes/revisions, comparison groups, review testimony, relations and reading checkpoints. Current workspaces use schema 3; recognized legacy schemas can be inspected without automatic upgrade. Operations use transaction/checkpoint guards; backup or upgrade publishes a separately validated non-overwriting copy. Workspace author names are attribution labels, not login authentication. Reader verification testimony does not clear canonical `needs_review` flags.

**Correction protocol:** locate exact source evidence → record uncertainty → correct canonical Markdown and appropriate provenance → reindex → check consistency → inspect impact on retained reading work and analysis artifacts. Keep old identities for corrected records. A new source extract cannot silently rewrite the approved record or move its parent's logical location.

**Future consideration, not an active requirement:** separate imported editions/translations would require separate canonical identities and explicit alignments, since paragraphs and note structures can differ. For this cycle, stay on the single audited source. Do not make new corpus IDs by hashing filenames or conflating different translations.

## 8. Scope and integrity checklist

1. Preserve canonical Markdown as the correction surface; treat JSONL as generated and replaceable.
2. Do not modify record UUIDs or retire/rewrite IDs to make presentation easier.
3. Keep original PDF and copyright-bearing text out of Git; validate fingerprints when using local source evidence.
4. Distinguish source text, translator/editor material, personal notes, inferred structure, model results and research claims.
5. Preserve explicit uncertainty (especially formulas and OCR/review flags).
6. Maintain strict typed references and separate snapshots/generation digests from durable record IDs.
7. Keep CORE independent from Neovim, Alacritty, Kitty, Zsh, user workspace state and ML frameworks.
8. Test malformed/missing/retired records, Unicode, selected-span offsets, corpus edits, concurrent changes, bad Markdown, source mismatch and unsafe input.
9. Do not expand ingestion to arbitrary PDFs or other books during this milestone.
10. When consolidating documentation, retain prior detailed contracts in `docs/legacy/` rather than deleting them; update tests with any actual contract changes.

**Source lineage:** corpus contract, extraction workflow, public modularity API, reference protocol, workspace plan/exports, reader-action and presentation specifications, audited ingestion documentation, and actual code/tests in the GitHub baseline. Historical material stays accessible under `docs/legacy/` after the documentation migration.
