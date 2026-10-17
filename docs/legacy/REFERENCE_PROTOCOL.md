# CORE reference protocol, version 1

SOL components need to agree on which text they are discussing. This protocol
transfers an existing canonical reference, not a paragraph copy or authority to
execute an action. It works with the complete canonical corpus, including notes,
editorial text, sections, and formulas; it does not require the Hegel-only reader
projection or the virtual shell.

## Use it from a real shell

Choose an existing record UUID or an unambiguous prefix:

```sh
sol reference capture RECORD_ID --corpus local-corpus | sol reference check --corpus local-corpus
```

Capture prints JSON. Check accepts one JSON envelope from a file or piped stdin
(until EOF), then prints a JSON result and returns zero only on agreement. It does
not display the paragraph, open a reader, move a cursor, save a visit, select an
actor, write configuration, or create/migrate a workspace.

Both processes select their corpus through `--corpus` or the existing local
discovery/configuration rules. The packet never chooses a directory or source
PDF. A corpus without its permanent UUID is refused; identity initialization is
a separate explicit `sol-corpus-check DIRECTORY --initialize-identity` operation.

## The envelope

| Field | Binding |
| --- | --- |
| `protocol`, `version` | Exactly `sol.reference` and integer `1` |
| `corpus` | Permanent corpus UUID, edition fingerprint, source SHA-256 and PDF page count |
| `generation` | Exact manifest and generated-index SHA-256 fingerprints |
| `reference` | Requested UUID, resolved UUID, complete redirect chain, target Markdown fingerprint, canonical type, source pages, and attribution |

Source-page entries retain ordered one-based PDF pages, printed labels as strings
or null, and existing canonical rectangles when available. Roman printed-page
labels remain Roman strings. Attribution transfers only `author`, `role`, and
`status`; source entries transfer only `pdf_page`, `printed_page`, and optional
`bbox`. Unknown metadata extras are not exported. No paths, commands, passage
bodies, actor credentials, workspace addresses, or arbitrary metadata subtrees
are carried.

The edition fingerprint covers the complete edition metadata, including translator
information where supplied, without copying that potentially extensible dictionary
into the packet. Its version-1 digest is SHA-256 of UTF-8 JSON using sorted keys,
no insignificant whitespace, unescaped Unicode, and finite numbers only (Python
`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False,
allow_nan=False)`). Target content fingerprints retain the corpus contract's
SHA-256 of exact canonical Markdown, not terminal-folded text.

Wire output uses JSON Unicode escapes so metadata cannot activate terminal control
or bidirectional formatting when inspected. Decoding preserves the original
Unicode strings. Both wire input and output are limited to **65,536 bytes**;
oversized references fail rather than being truncated. Input may be UTF-8 text
with ordinary JSON whitespace. Duplicate keys, nonfinite/overflow numbers,
escaped lone surrogates, incorrect types, unsupported versions, unknown fields,
and malformed chains are errors. File input must be a stable regular file, not a
symlink, FIFO, or device. This is one envelope per invocation, not JSONL streaming.

## Agreement and refusal

The receiver revalidates its local snapshot and canonical graph. The protocol
also rejects modified in-memory snapshot dictionaries rather than combining
their altered values with old disk fingerprints. A final generation check refuses
corpus changes during capture/check. Requested retired IDs remain distinct from
their resolved targets; only registered redirects are followed.

Version 1 uses **strict generation agreement**. An unrelated correction elsewhere
in the book invalidates an old packet too. This deliberate first policy makes
staleness visible instead of guessing that a result is still applicable. Recapture
or another acceptance policy must be a separate, deliberate decision.

Successful checks return `status: current`, corpus/generation binding, IDs, chain,
target content fingerprint, type, source-page evidence, and attribution. This is a
verification receipt, not another reference envelope; retain the input packet for
further transfer. Failures return a nonzero status and
JSON with `status` and `error`; protocol refusals also include a stable `code`.
The coarse statuses are `invalid`, `mismatch`, `stale`, and `unresolved`. Examples
include `corpus_mismatch`, `edition_mismatch`, `source_mismatch`,
`generation_changed`, `record_mismatch`, and `unresolved_reference`.

These fingerprints are **integrity evidence, not authentication**. A successful
check does not prove who produced a packet, physically verify the PDF/images,
authenticate attribution, or certify accurate transcription. Someone able to
rewrite the corpus and all its fingerprints is outside this integrity guarantee.
Consumers must not execute data strings or treat a reference as authorization for
personal writes.

## Python and the local handoff boundary

```python
from pathlib import Path
from sol.core import load_snapshot, capture_reference, check_reference

snapshot = load_snapshot(Path("local-corpus"))
packet = capture_reference(snapshot, existing_record_id)
reference = check_reference(snapshot, packet)
```

`encode_reference` and `decode_reference` supply the bounded wire representation;
`ProtocolError` exposes `status` and `code`. Importing them does not load BEING,
workspace storage, terminal adapters, a Markdown parser, or an extraction engine.
Protocol version 1 is separate from CORE API version 1, corpus contract version 1,
and workspace schema versions. No existing schema or UUID system changes.

The optional [BEING–ESSENCE handoff](HANDOFF.md) now uses these envelopes inside a
separate private local transport. Its metadata carries only transport version,
session nonce, and origin-packet digest; a returned wrapper adds one CORE envelope.
Those fields correlate an exchange without adding actor, workspace, path, or
execution authority. The CORE envelope and protocol version are unchanged.

`sol reference return [ID]` independently selects the local corpus, validates
the captured origin, and publishes one response without overwriting another.
It reads the explicit `--handoff-dir DIRECTORY` or `SOL_HANDOFF_DIR`, never a
directory from the packet or stdin. This publication proposes navigation;
BEING's `essence check` only inspects, and `essence return` explicitly accepts
once through the [reader actions](READER_ACTIONS.md). Strict generation agreement
and BEING's checkpoint/conflict checks still apply.

Pane launch, ordinary zsh execution, and temporary file lifecycle belong to the
terminal adapter, not CORE. Automatic navigation, analysis-result ingestion,
workspace synchronization, and authenticated actor transfer are not supplied by
this reference protocol. A substantial ESSENCE application needs its own bounded
result contract and review policy before any personal-write integration.

## Bounded batch operations

`sol.core.capture_references(snapshot, identifiers)` and
`check_references(snapshot, payloads)` accept a list or tuple of 1 to 1,024 items.
They preserve input order, requested identities and complete retirement chains.
Their outputs are ordinary version-1 envelopes or resolved references; there is
no additional wire format or authority.

Each call loads and verifies one current generation, checks its agreement with
the supplied caller-owned snapshot, and verifies the disk generation again before
returning any result. A bad item or changed generation refuses the entire batch.
There is no shared trust cache. The existing single-record functions use the same
checks through a batch of one.

Reader sample exports declare the passages and linked notes together, then retain
their independent final graph, projection and disk checks before writing an
artifact. Batch verification does not permit a renderer to change source text,
offsets, provenance or identities after capture.
