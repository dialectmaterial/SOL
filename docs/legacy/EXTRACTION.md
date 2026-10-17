# Extraction candidates and reviewed corpus copies

SOL delegates physical PDF extraction to a replaceable adapter. It retains
responsibility for the canonical text: permanent identifiers, edition metadata,
attribution, printed-page labels, hierarchy, and review history. An extractor's
reading order, heading labels, integer element IDs, or PDF author field cannot
establish those meanings.

The first adapter uses **OpenDataLoader 2.5.13**, pinned deliberately rather than
accepting an untested engine update. It produces a private candidate artifact;
it does not rebuild or replace the existing corpus. The ordinary reader still
loads its verified Markdown/JSONL generation without importing OpenDataLoader,
starting Java, extracting a PDF, or contacting a service.

This is a bounded extraction-to-canonical proof, not a generic new-book importer.
The historical, edition-specific `convert` command remains available unchanged.
Canonical corrections should normally be made in Markdown and followed by
`sol-corpus index`.

## Included dependencies

The complete checkout installation includes the extraction SDK and CommonMark:

```sh
python3 scripts/install.py
```

With the native tools already available, refresh an existing installation with:

```sh
pipx install --force .
```

`extract` requires the included SDK and Java 11 or newer on `PATH`.
`normalize` accepts already extracted JSON without the SDK or Java. `ingest`
uses the included CommonMark parser for reindexing; it does not run
the extraction engine. No dependency is installed automatically by these
commands. [OpenDataLoader Python setup](https://opendataloader.org/docs/quick-start-python).

## 1. Create a review candidate

Choose a small page sample before considering a whole-book comparison. Page
numbers here mean one-based **PDF pages**, not the book's printed labels.

```sh
mkdir -p .sol-extractions .sol-ingest-work
sol-corpus extract --pdf Hegel-SOL.pdf --pages 80,282-283 --output .sol-extractions/sample.json
```

The adapter fixes local extraction to JSON, `hybrid=off`, and image output off.
There is no OCR, remote endpoint, hybrid fallback, model download, or formula
enrichment option exposed in SOL's adapter. Scanned documents and enriched
mathematics require separately assessed capabilities; they are not implemented
by this first phase. SDK/JVM failure is an error, not permission to try a server.
[OpenDataLoader hybrid modes](https://opendataloader.org/docs/hybrid-mode).

The artifact preserves the raw document and derives review elements with JSON
pointer selectors, candidate content/type, PDF page, and available physical
metadata. It records the source fingerprint and backend provenance without
allocating canonical UUIDs. `backend.origin` distinguishes `sol_local_execution`
from `external_json_declared`; `normalization.metadata_author_is_attribution` is
false. PDF document metadata is retained as evidence, not passage authorship.
Every candidate remains unreviewed.

Coordinates remain explicitly **unverified** bottom-left PDF-point evidence.
They are not converted to or substituted for canonical source rectangles. Rotation,
crop boxes, and visual calibration remain review work. A plausible rectangle is
not proof of complete or accurate transcription.

An externally obtained OpenDataLoader JSON file can use the same review format:

```sh
sol-corpus normalize --json external.json --pdf Hegel-SOL.pdf --backend-version 2.5.13 --output .sol-extractions/external-candidate.json
```

Here the backend version and external extraction origin are **caller-declared**.
SOL fingerprints the supplied PDF, but cannot verify that an external program
actually ran the declared engine, options, or source. Normalization validates
structure and records the distinction; it does not authenticate extraction.

## 2. Review against the source and existing records

Open the candidate, the source facsimile, and the baseline canonical Markdown.
Decide which existing UUID each relevant element supports, then write the
approved Markdown yourself. Preserve meaningful emphasis, quotations, notes,
formula uncertainty, and paragraph boundaries. Do not accept generated content
merely because its formatting is attractive.

A version-1 review has exactly these top-level fields:

```json
{
  "review_version": 1,
  "artifact_sha256": "<SHA-256 of the complete candidate artifact file>",
  "reviewer": "<your declared review label>",
  "changes": [
    {
      "record_id": "<existing canonical record UUID>",
      "selectors": ["/kids/0"],
      "markdown": "Human-reviewed replacement *Markdown*.",
      "reason": "Compared the candidate, canonical passage, and source page."
    }
  ],
  "exclusions": [
    {
      "selector": "/kids/1",
      "reason": "Running page header, not part of this canonical passage."
    }
  ]
}
```

This example is illustrative: replace its placeholders and selectors with those
in your actual candidate and baseline. The artifact fingerprint can be obtained
with `sha256sum .sol-extractions/sample.json`.

Every element in the candidate's `elements` list must be mapped or excluded
**exactly once**, including nested elements. Each change requires at least one
selector and a nonempty reason. Each target UUID can have only one change, and
the elements' PDF pages must belong to that record's existing source references.
Multiple candidate elements may support one existing paragraph. The prototype
does not split, merge, create, or retire canonical records.

The `reviewer` label is a declaration, not authenticated authorship, a signature,
proof that a human inspected the PDF, or a personal workspace verification event.

## 3. Publish a separate reviewed copy

Save the review privately, then request a **new** output directory:

```sh
sol-corpus ingest --candidate .sol-extractions/sample.json --review .sol-extractions/review.json --baseline local-corpus --output .sol-ingest-work/reviewed-corpus
```

Ingestion requires the baseline's exact source fingerprint and page count. It
copies declared canonical Markdown and assets, applies only the approved Markdown
changes, reindexes, reloads the verified snapshot, and checks that identifiers,
manifest, metadata, order, hierarchy, attribution, page references, and untouched
text remain identical. Existing annotated note identities and link destinations
must also remain intact. Only assets in the declared `assets/` subtree are
carried forward; old conversion audits, PDFs, personal databases, and unrelated
adjunct files are not copied. A separate ingestion audit records the review/artifact fingerprints,
reasons, mappings, and exclusions.

Publication uses an atomic no-clobber directory operation on supported Linux
systems. If that primitive is unavailable, it fails closed rather than replacing
an existing destination. Input/generation changes, conflicting assignments,
symlink paths, unsafe destinations, and existing targets are errors. Outputs must
not be inside `sources/` or the baseline. Output parents must already exist.

The baseline and reader configuration remain unchanged. Inspect the copy without
selecting a new default or creating a workspace:

```sh
sol --corpus .sol-ingest-work/reviewed-corpus -r
```

Changing the configured corpus later is a separate deliberate action. Existing
workspace notes and reviews retain their inspected text digests; ingestion does
not migrate them, mark changed passages verified, or erase evidence of stale text.

## Local storage and the next boundary

Keep candidates, reviews, and reviewed copies under `.sol-extractions/` and
`.sol-ingest-work/`. Both locations are Git-ignored and excluded from release
archives. Inside a repository, a different output location must also be explicitly
ignored. Source material and extracted text remain local; the public repository
contains adapters, contracts, documentation, and invented test fixtures.

The [reader action seam](READER_ACTIONS.md) and [CORE reference protocol](REFERENCE_PROTOCOL.md)
are implemented separately. The next boundary is one reversible BEING–ESSENCE
handoff. This extraction phase does not launch a new terminal or create an ESSENCE
computation environment. See the [modularity contract](MODULARITY.md)
and [historical OpenDataLoader investigation](research/OPENDATALOADER_RESEARCH.md).
