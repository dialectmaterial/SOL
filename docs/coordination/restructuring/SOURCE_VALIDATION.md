# Source-request validation: public CORE interface proposal

**Date:** 22 October 2026. **Author:** Codex lane B.
**Status:** proposal only; **maintainer decision (reserved: public contract)**.
**Inspected baseline:** `origin/main` at
`9beb586073d2247c852f7640bd4e660167d5cc90`; later documentation-only main
integration is recorded in HANDOFF and does not change the inspected source.
The original proposal changed no Python, tests, exports, versions, dependencies,
schemas or Decision statements. Its public-interface acceptance criteria remain
pending; subsequent private hardening is recorded below.

This follows [REEVALUATION §3.6](REEVALUATION.md#36-the-source-viewer-imports-private-core-helpers).
Authority remains [CORE §§4–6/8](../../CORE.md#4-core-public-api-and-runtime-boundary),
[Architecture §§2/9](../../ARCHITECTURE.md#dependency-direction) and
[SPECULATIVE §5.3](../../SPECULATIVE.md#53-autonomy-and-final-authority).
Keep capture/verification/rendering in CORE and detached viewers in BEING.
There is no new logical placement or claim that page coordinates constitute
Measure; the stage E reading and judgment remain the rationale.

**Private hardening, 23 October 2026.** The three known gaps pinned in #107
are closed privately: malformed requested IDs/request shapes raise `SourceError`
with chained validation causes; `render_region` validates before reading source
entries or bbox; `open_pdf`/`follow_pdf` retain the freshly loaded snapshot and
call `verify_snapshot_current` after PDF hashing, translating `CorpusError`
before any viewer, companion or D-Bus access. Regressions cover all four
consumers, crop/fallback rendering and changes during/after hashing. Capture
output, identifier-prefix resolution, rendering/cache/viewer behavior, request
version and `sol.core` facade/API_VERSION are unchanged. The new generation
wrapper is private; this does **not** implement the proposed public validator,
immutable results, full-UUID/absolute-path contract or asynchronous highlight
ownership changes. Those decisions remain pending in #104. The inventory and
limitations below describe the inspected baseline unless marked otherwise.

## 1. Inventory method and scope

Inspected all tracked Python/Lua source, tests and scripts, including imports
inside functions and string patch targets. Useful reproduction commands:

```sh
rg -n '_request_current|_verify_file|_verified_copy' sol tests scripts
rg -n 'SourceService|inspect_info|set_pdf|render_page|render_region|open_pdf|follow_pdf|open_viewer|core.source|source_view' sol tests scripts
rg -n 'source_preview|source_pdf|source_follow' sol/being/neovim
rg -n '__import__|sys.modules|forbidden|sol.core.source' tests
```

The inventory is of the PDF source-request pipeline, including its producers,
consumers and trust dependencies. `SurfaceCapture`, `capture_reference(s)`,
typography's HTML `capture`, extraction candidates and workspace source bindings
are different operations; they do not invoke these two helpers. In particular,
the path-free `sol.reference` wire envelope is **not** a source-view request.
`tests/test_source_discovery.py` concerns locating an installed checkout/corpus,
not PDF fingerprint verification. No private corpus or PDF was needed for this
audit. File/line references below refer to the inspected baseline.

### 1.1 Every direct caller of the two helpers

| Helper | Caller and exact sites | What that caller adds |
| --- | --- | --- |
| `_request_current(request) -> CorpusSnapshot` | `sol/core/source.py`: `_render`, lines 406, 431, 449 | Initial check; another check before returning a verified PNG cache hit; another after rendering, before publishing the PNG/sidecar. |
| `_request_current` | `sol/being/source_view.py`: `open_pdf`, line 68; `follow_pdf`, line 113 | Both validate the selected source-list index, then call `_verify_file` before viewer selection or companion access. Neither uses the returned snapshot. |
| `_verify_file(path, expected) -> None` | `sol/core/source.py`: `_render`, line 412 | Checks the captured PDF even on a PNG cache hit. A render miss additionally copies and verifies the bytes supplied to Poppler. |
| `_verify_file` | `sol/being/source_view.py`: `open_pdf`, line 73; `follow_pdf`, line 116 | Checks the file handed to the viewer or associated with the companion. There is no later corpus check in either function. |

These are all five `_request_current` call sites and all three `_verify_file`
call sites. Only `source_view.py:13` imports either helper across a package
boundary; CORE calls its own definitions. No test or script directly calls or
patches either helper. `test_pdf_modified_during_copy_never_becomes_completed_snapshot`
patches `_stat_identity`, a lower-level helper.

### 1.2 Producers, adjacent checks and consumers

| Operation | All production callers | Guarantees, results and errors |
| --- | --- | --- |
| `SourceService(book, source_pdf=None, cache_dir=None)` | `sol/corpus/onboarding.py:81–83`; `sol/app/main.py:295–296`; Neovim `reader.py:326–331` | Requires `book.corpus_directory`; resolves explicit PDF/cache paths and refuses a cache root equal to or below the corpus. Construction does not verify the corpus/PDF or create the cache. `SourceError` on these explicit refusals. |
| `SourceService.set_pdf(path)` | Onboarding and app sites above | `_current` before and after creating a verified snapshot; then saves the absolute original path under its source SHA-256 in `sources.json`, preserving other entries. Mapping must be outside the corpus; final mapping symlink/competing lock rejected. Returns resolved `Path`. Writes cache/configuration, never canonical files. Onboarding catches `SourceError` and keeps an otherwise completed import; the app reports `SourceError` through its `ValueError` boundary (exit 2). |
| `SourceService.capture(identifier)` | Neovim `reader.py:331`, cached per resolved target ID | `_current`, canonical reference resolution including explicit retirement chain, source-page bounds, verified PDF copy, `_current` again. Returns a mutable version-1 local dict, with full requested/target IDs, chain, record metadata digest, content digest, copied sources/attribution/source manifest and corpus generation/directory. No body text. `SourceError` for freshness/PDF/page failures; reference resolution can raise plain `ValueError`. |
| `SourceService.inspect_info()` | **None** outside its definition (including tests/scripts) | Same freshness/copy/freshness sequence, returning copied manifest source data plus original `path` and `verified_pdf` strings. Does not produce a full source request. |
| `render_page(request, page_index, cache_dir=None)` | **Tests only**; `render_region`'s fallback calls `_render` directly | Returns PNG `Path`, full page at 120 dpi. `_render` supplies request/PDF checks, cache safety, renderer execution, PNG integrity and late generation checks. |
| `render_region(request, page_index, cache_dir=None)` | Neovim `reader.py:91–95`; tests | Returns `(Path, bool)`: recorded bbox at 144 dpi with six-point padding, or whole-page fallback with `False`. Bbox is in PDF points from top left. Does index/bbox access **before** `_render` validates the request; malformed dicts may leak built-in exceptions. |
| `_verified_copy(source, destination, expected)` | `SourceService._snapshot_pdf`, line 256; `_render`, line 439 | Rejects final source symlink/non-file, opens source once, hashes the same bytes it copies to an exclusive destination, compares before/after `fstat` identity and expected SHA-256, fsyncs and chmods completed copy to `0400`. Raises `SourceError`, wrapping copy I/O failures. A rename of the original pathname does not redirect the opened stream. |
| `open_pdf(request, page_index)` | Neovim `source_pdf`, `reader.py:110–115`; tests | Request/index/PDF checks, then configured/platform viewer or Zathura reuse. Returns viewer name or `None` when unavailable; detached `Popen`, no shell. Launch I/O becomes `SourceError`. Malformed command strings can still raise `ValueError`/`IndexError`; this proposal does not redesign command parsing. |
| `follow_pdf(request, page_index=0)` | Neovim `source_panel`, `reader.py:335–336`; tests | Same checks even with no companion; returns bool, turns/highlights only a live SOL-opened Zathura on the same path. Never creates a viewer. D-Bus errors become `False`. |
| `open_viewer(path)` | Neovim `source_preview`, `reader.py:90–105`; tests | Opens a rendered image detached, returns name/`None`; no source-request, generation, PDF or PNG validation of its own. Provenance is the upstream renderer's responsibility. Launch I/O becomes `SourceError`. |
| Neovim `source_panel` / `source_preview` / `source_pdf` | Panel dispatch `reader.py:474–475`; Lua `neovim_panels.lua:187–240`, requests/controls modules | Lazily creates service/capture; converts UI page ordinals (one-based list position) to zero-based source-list indexes. PDF-viewer absence falls back to a crop. On `SourceError`, evicts cached capture for the next request. Preserves cursor, selection and workspace; capture failure before insertion leaves no cache entry. |
| `_show_on_companion` / `_show` / `_highlight_when_ready` | `open_pdf` and `follow_pdf`; `_show_on_companion` calls `_show`; retry thread calls `_show` directly | Path/process/D-Bus availability checks, zero-based Zathura page conversion and bbox formatting. **No independent provenance revalidation.** The initial retry thread retains the mutable request and can run after the caller's check. |

There are no other production callers of these public-looking source-module
operations. Tests import the source module directly; installed-wheel smoke
checks also import it and assert rendering is callable without running it.
`source.py`'s diagnostic still advertises shell `source set-pdf PATH`, but no
such caller exists in the current shell. Do not infer an integration from that
string; correcting it is outside this documentation task.

For completeness, the remaining private call graph inside `source.py` is:

- `_json`: `_digest`, `set_pdf`, `_render`; `_digest`: `_record_digest`,
  `_render`; `_record_digest`: `capture`, `_request_current`.
- `_xdg`: `source_config_path`, `source_cache_path`; `source_config_path`:
  `_mapping`, `set_pdf`; `source_cache_path`: `_cache_directory`.
- `_mapping`: `_location`, `set_pdf`; `_mapping_lock`: `set_pdf`;
  `_atomic_bytes`: `set_pdf`, `_render`.
- `_stat_identity`: `_verified_copy`, `_verify_file`; `_cache_directory`:
  service constructor, `_cache_subdirectory`, `_render`;
  `_cache_subdirectory`: `_snapshot_pdf`, `_render`.
- `_validate_sources`: `capture`, `_request_current`; `_current`: `set_pdf`,
  `inspect_info`, `capture` (twice each); `_source`: `_location`,
  `_snapshot_pdf`, `set_pdf`, `inspect_info`, `capture`.
- `_location`: `inspect_info`, `capture`; `_snapshot_pdf`: `set_pdf`,
  `inspect_info`, `capture`; `_render`: `render_page`, `render_region`;
  `_crop_arguments` and `_png_digest`: `_render` (PNG digest at hit and miss).

### 1.3 What validation actually proves today

**Corpus freshness and identity.** `_request_current` requires dict/version
integer `1` (bool refused), reloads with `load_snapshot(binding['directory'])`,
and compares the whole corpus binding with its actual ID, resolved directory,
manifest, index and index-metadata SHA-256 values. It resolves `requested_id`
against the freshly loaded full graph and compares target ID, entire chain,
`_record_digest`, content digest and exact source-list equality. Metadata digest
covers all record fields except `markdown` and `plain_text`; this includes
attribution, context, document, page evidence and image references. It checks
manifest PDF SHA-256/page count and validates source pages. It returns the fresh
`CorpusSnapshot`, whose contained dicts/lists remain mutable.

`load_snapshot` checks canonical document fingerprints, manifest/index metadata,
record graph/provenance, content digests and one consistent generation, with a
final disk check. Its safe-document resolver rejects absolute/traversing paths,
escaping parent symlinks and final document symlinks. This is document containment
relative to the selected corpus root. It does not restrict which local corpus
root a request may name. `_request_current` does not use a caller-supplied Book
or trust the reader's old in-memory records.

By contrast, capture's `_current` checks the snapshot's disk generation but does
not deep-compare all mutable Book/manifest/record containers with a fresh parse.
Capture copies metadata so later request edits do not mutate the Book; that is
not deep immutability or permission to trust caller-edited Book data. The
request's subsequent reload/comparison is an essential separate check.

**PDF bytes.** `_request_current` never opens the PDF. `_verify_file` rejects a
final symlink/non-file, hashes one opened stream and compares
`(dev, ino, size, mtime_ns, ctime_ns)` before/after plus the expected digest.
It returns `None`. It does not parse PDF structure or page geometry. The renderer
additionally uses `_verified_copy` for the exact bytes Poppler reads; the detached
PDF viewer subsequently opens a pathname itself. `0400` is accidental-write
protection, not protection from the same owner replacing or chmodding the file.

**Paths, writes and limits.** `_cache_directory` resolves roots and excludes the
canonical corpus; `_cache_subdirectory` rejects an existing final child symlink
and checks containment again before mkdir. `set_pdf` similarly excludes corpus
storage for the source mapping. Those are **producer/write-path checks**.
Neither request validator proves `source.verified_pdf` is below a SOL cache,
outside the corpus, or the same pathname originally returned by `capture`.
A regular file elsewhere with the expected bytes can pass. Ancestor symlinks
and pathname replacement after checking are not prevented by `_verify_file`.
Source `path` is informational and never a fallback when a captured PDF fails.
Configured/remembered originals may resolve symlinks; the cached final file may
not. Do not promote these checks into a containment/authentication guarantee.

**Request/schema limits.** This is local mutable capture data, not a bounded
decoder or authenticated receipt. Extra/unbound display fields (`title`,
top-level attribution/type/document/transcription status and source filename/path)
are not independently compared with the record. A prefix in `requested_id` can
still resolve; the helper does not require equality to the resolved requested
UUID. Python equality admits some JSON-type substitutions in nested comparisons.
`_validate_sources` checks nonempty list, integer physical pages and label types,
not bbox shape/finite coordinates itself (canonical record validation does that
on load). No trust may be cached over a previously successful mutable request.

**Error types.** `SourceError` subclasses `ValueError` and has no stable
status/code fields. `_request_current` wraps `KeyError`, `TypeError`,
`CorpusError` and `OSError`, while its explicit mismatch refusals are already
`SourceError`. Unresolved/ambiguous IDs can leak plain `ValueError`;
wrong-shaped `requested_id` can leak `AttributeError` from `.strip()`.
`_verify_file` wraps file-open/read `OSError` and raises its own `SourceError`
for missing/changed/symlink files; it expects a Path rather than coercing one.
Its pre-open path probes sit outside that I/O wrapper, another reason not to
advertise the helper itself as a fully normalized public error boundary.
The index check at the three consumers rejects bool, strings and out-of-range
integers as `SourceError`. Later renderer subprocess failures/timeouts/PNG
failures become `SourceError`; malformed input to `render_region` can fail earlier.
Viewer-command errors remain separate from source-validation errors.

**Temporal limits.** Corpus load checks changes during loading, but viewer paths
have no final generation check after PDF hashing; render paths do, including
cache hits. No check can keep a detached viewer's future pathname opens stable,
authenticate a party able to rewrite the corpus and all fingerprints, prove
transcription accuracy, or authorize reading arbitrary paths from hostile input.

## 2. Existing tests and uncovered cases

The main evidence is `SourceViewerTests` in
[`tests/test_source_viewer.py`](../../../tests/test_source_viewer.py).
All fixtures are invented three-page PDF/Markdown and tiny PNG data. The table
uses existing method names (omit the common `test_` prefix).

| Existing methods | Protected behavior |
| --- | --- |
| `capture_preserves_uuid_redirect_metadata_and_exact_sources` | Retired prefix expands to full IDs/chain; nonconsecutive physical pages 1 and 3, Roman/null labels, verified digest, copied source list, no implicit config write. |
| `new_capture_checks_original_even_when_verified_snapshot_exists`; `render_stays_on_captured_pdf_after_original_is_replaced` | New captures reverify original; existing requests render the captured PDF. |
| `explicit_bad_source_does_not_use_automatic_good_source`; `environment_source_has_priority_and_is_not_silently_replaced`; `saved_source_is_explicit_and_missing_path_does_not_fall_back` | Explicit path → environment → remembered path → adjacent filename/Hegel-SOL fallback; no recovery by silently substituting a different original. |
| `set_pdf_retains_other_mapping_and_does_not_modify_corpus_or_reader_config` | Mapping preservation and corpus/config noninterference. |
| `metadata_change_invalidates_request_even_with_same_markdown`; `request_cannot_retarget_pages_or_drop_metadata` | Changed attribution/reindexed generation and changed requested page refused. The latter currently mutates a page; its name does not imply every missing-field case is covered. |
| `bool_and_out_of_bounds_indexes_are_rejected`; `declared_physical_page_bounds_are_checked_on_capture` | Zero-based index typing/bounds and manifest physical page bounds. |
| `png_cache_hit_is_verified_and_corruption_is_rerendered`; `corrupt_pdf_snapshot_is_rejected_even_with_png_cache_hit` | PNG bytes/sidecar revalidation and PDF check before cache return. |
| `cache_must_remain_outside_canonical_corpus`; `cache_child_symlink_cannot_send_writes_to_corpus`; `source_mapping_cannot_be_stored_inside_corpus` | Cache/config write containment. These do not test arbitrary captured-PDF path containment. |
| `legacy_pdf_reader_gets_actionable_source_error`; `pdf_modified_during_copy_never_becomes_completed_snapshot`; `renderer_failure_leaves_no_completed_png_or_metadata` | Missing canonical corpus, simulated copy race and failure cleanup. |
| `region_crops_recorded_box_and_falls_back_to_the_whole_page`; `poppler_renders_actual_synthetic_noncontiguous_page`; `poppler_crops_the_recorded_region` | Page/crop arguments, distinct cache keys, whole-page fallback; last two use real Poppler when installed and otherwise skip explicitly. |
| `viewer_is_detached_and_configurable`; `viewer_is_not_guessed_without_a_display_or_program`; `pdf_viewer_opens_the_verified_snapshot_at_the_physical_page`; `pdf_viewer_is_configurable_and_never_guessed_without_a_display`; `pdf_viewer_refuses_a_changed_snapshot` | Detached launch streams/session, environment/platform availability, page 3 vs source-list index 1, Zathura reuse, altered-PDF refusal before launch. |
| `highlight_marks_the_box_on_its_page_and_on_the_passages_other_pages`; `following_turns_only_a_window_sol_opened_and_never_opens_one` | Highlight coordinate conversion and companion lifecycle; no provenance failure exercised in follow itself. |

Additional existing coverage:

- `tests/test_neovim_reader.py`: `test_source_preview_shows_evidence_without_moving_or_saving`,
  `test_source_pdf_opens_the_page_for_the_current_passage`,
  `test_source_follow_turns_only_an_open_zathura_window`,
  `test_stale_source_capture_is_replaced_on_the_next_request`. These use service,
  rendering and viewer doubles; they protect orchestration, ordinal conversion,
  fallback, no position/workspace changes and retry eviction, not helper internals.
- `tests/test_reader_view_cli.py`:
  `test_set_source_pdf_verifies_through_the_source_service` and
  `test_wrong_source_pdf_is_refused_and_not_remembered`; `tests/test_first_run.py`:
  successful/reused import and failure-to-remember cases protect setup behavior.
- `tests/test_corpus_contract.py`: unsafe paths/symlinks, bad graph/provenance,
  stale Markdown/source fingerprint/index and parser-free loading;
  `tests/test_corpus_identity.py`: unchanged legacy identity, manifest races and
  edits during verification. These underlie snapshot validation, but do not
  validate a source request or read a PDF.
- `tests/test_core_api.py`: identity-preserving lazy exports, API version 1,
  no import-time I/O/interfaces and read-only corpus/reference operations.
  `tests/test_core_protocol.py` tests a different envelope with stricter JSON,
  mutation/race rules and stable `ProtocolError` codes; it is precedent, not
  automatic coverage for source requests.
- `tests/test_architecture.py`: static division directions, lazy facade module
  targets, absent old packages and five scanner tests. **It currently allows**
  BEING → CORE and records a `from` module, not its private imported symbols.
  The current private import passes; no exception is required to make it pass.
- Fresh-process and installed-wheel guards are enumerated in §5.3. They protect
  lazy loading; ordinary source tests import BEING and CORE together and cannot
  establish that boundary by themselves.

Missing direct coverage includes malformed request normalization, the full
generation/chain/digest tamper matrix, `_verify_file`'s final-symlink and read-race
branches, stale/corrupt follow refusal before D-Bus, post-PDF-check corpus change,
and mutations seen by the asynchronous highlighting thread. A public contract
must specify these instead of inferring them from successful viewer tests.

## 3. Recommended interface (for maintainer decision)

### 3.1 Names, signatures and value types

Add **one combined validation operation** to `sol/core/source.py`. Proposed
signatures/value layout below are design notation, not implemented code:

```python
@dataclass(frozen=True)
class SourcePage:
    pdf_page: int                  # physical PDF page, one-based
    printed_page: str | None       # never converted to an integer
    bbox: tuple[float, float, float, float] | None  # PDF points, top-left

@dataclass(frozen=True)
class ValidatedSourceRequest:
    verified_pdf: Path
    page_index: int                # zero-based position in sources
    sources: tuple[SourcePage, ...] # canonical order, every contributing page

    @property
    def page(self) -> SourcePage: ...  # sources[page_index]

def validate_source_request(
    request: dict[str, object], page_index: int
) -> ValidatedSourceRequest: ...
```

There is no optional `verify_pdf=False`, trust-cache token, viewer configuration,
Book/workspace argument, cache-directory argument, callback or subprocess call.
The selected index is required; `follow_pdf` continues to supply its own default
`0`. Success always means request **and selected page and PDF bytes** passed.
Use the full ordered page tuple for highlighting the other pages; a result with
only the selected page would leave that code dependent on mutable input again.
BBox values are normalized to finite floats after validation; `None` means
whole-page evidence. No PDF geometry is inferred or clamped by this operation.

The result exposes no mutable request, canonical record, manifest, Book or
`CorpusSnapshot`. All nested values are immutable primitives/tuples/Paths;
`frozen=True` alone would not suffice for dict/list fields. Result construction
is not authentication: callers can construct dataclasses themselves, and no
later CORE operation accepts them as proof instead of revalidating a request.
The name describes the completed check, not a promise of future freshness.

Keep `SourceError(ValueError)` as the public failure type, re-exporting the
**same class object**, without introducing status/code subclasses in this work.
Expected invalid, unresolved, stale, changed-PDF and inaccessible-file cases
must raise `SourceError`, with useful diagnostics and chained causes where
appropriate. Message wording is not a machine contract. Validate input types
before calling the resolver/Path functions, and normalize their expected
`ValueError`/I/O failures; do not blanket-catch programmer bugs, `BaseException`
or cancellation. Viewer absence remains `None`/`False` in BEING after successful
validation and is not a source-validation failure.

### 3.2 Required behavior and ordering

1. Validate the locally supplied version-1 capture's owned field types before
   file access; extract/copy only those fields. Require dicts, version exactly
   integer 1, full lowercase requested/target UUIDs, a string-ID list for the
   chain, well-formed SHA-256 bindings, a nonempty source list with strictly
   integer pages/string-or-null labels and finite valid rectangles, and source
   SHA-256/strictly integer positive page count. Reject bool as numeric input,
   including bbox coordinates. Accept legacy corpus `id: None` if the verified
   corpus is likewise uninitialized; never allocate identity. The corpus
   binding's key set remains the existing five fields in §1.3.
2. Require nonempty, NUL-free **absolute string** paths for the corpus directory
   and captured `verified_pdf`, as emitted by `capture`. Check that
   `type(page_index) is int` and it indexes the copied sources. Reject malformed
   fields/indexes as `SourceError`, never raw lookup/type/path exceptions.
   A structurally invalid request need not cause corpus/PDF I/O. No new decoder,
   size budget, transport or arbitrary `Mapping` protocol is introduced.
3. Reload the corpus, compare the full binding, resolve the full requested ID,
   compare resolved requested/target IDs and chain, metadata/content digests,
   source list and manifest source binding, as today. Apply source typing before
   Python equality so bool/int equality cannot bless substituted evidence.
   Return locations derived from that freshly checked canonical record, not
   unbound top-level display fields. Preserve nonconsecutive pages and labels.
4. Check the named captured PDF using existing `_verify_file` semantics: final
   symlink/non-file refusal, SHA-256 and before/after opened-file identity.
   Do **not** resolve the final PDF symlink before checking it. Never reopen
   `source.path`, discover another PDF, write a cache/mapping, render, or launch
   a viewer. Unavailable/changed snapshot requires recapture.
5. Call `verify_snapshot_current` on the privately retained fresh snapshot
   **after** PDF hashing and before returning. Translate `CorpusError` to
   `SourceError`. This closes the current viewer path's gap between corpus load
   and PDF hashing; rendering keeps its checks after expensive render/cache work.
6. Return detached immutable locations plus PDF path and selected index. Reading
   the original request or changing it after return must not affect the result
   or a highlight job built from it. No request/result memoization across actions.
   Concurrent mutation during the call is outside the local caller contract;
   extract owned fields once and do not retain a reference to their containers.

Recognized capture-owned fields for this validator are `version`, `corpus`,
`requested_id`, `target_id`, `redirect_chain`, `metadata_sha256`,
`content_sha256`, `sources`, and `source.sha256/pdf_pages/verified_pdf`.
Extra top-level/source descriptive fields are accepted and ignored; they are
not returned as verified data. Source-list entries must satisfy the canonical
contract and match the fresh list; an otherwise valid canonical extension is
not silently stripped before comparison. The metadata digest is compared to
the canonical record, not computed from these extra top-level fields.

The operation inherits canonical document containment from `load_snapshot`.
It deliberately makes **no new cache containment guarantee for `verified_pdf`**:
a regular absolute file of the expected bytes outside the cache remains valid.
Cache roots are configurable and are not recorded as an authoritative request
field. Proving cache membership would require another input/contract or an
opaque service-owned capture handle. Absolute path validation does not solve
ancestor-symlink races or restrict local filesystem read authority. This API is
for in-process local captures, not hostile remote payloads.

Success records conditions checked during this call. Once handed to a detached
viewer, the file can change; the result is not an open descriptor or a lease.
Do not claim the stronger exact-opened-bytes guarantee of `_verified_copy` for
PDF viewers. A descriptor/snapshot lifecycle API would be separate work.

### 3.3 Lazy facade, versioning and private internals

If approved, add exactly these `_EXPORTS` mappings in `sol/core/__init__.py`:

| Public name | Lazy target |
| --- | --- |
| `SourceError` | `sol.core.source` |
| `SourcePage` | `sol.core.source` |
| `ValidatedSourceRequest` | `sol.core.source` |
| `validate_source_request` | `sol.core.source` |

The existing `__all__`, `__getattr__` and `__dir__` machinery supplies listing,
lazy resolution and identity-preserving cached exports. Support both
`from sol.core import validate_source_request` and the defining-module import.
Merely importing `sol.core`, requesting model/config/reference names or listing
`dir(core)` must not load `sol.core.source`. Requesting a source name may load
`source`, `sol.corpus.contract` and stdlib dependencies, but must do no data I/O,
run no subprocess, and load no UI, workspace, Markdown parser, extraction engine
or PDF Python library. Wildcard imports and enumerating every name with
`getattr` explicitly resolve all exports and can therefore load source.

**Version recommendation (reserved):** retain `API_VERSION = 1` for an additive,
backward-compatible extension. There is no existing facade name/signature to
remove. Existing version assertions remain correct. The project has not defined
an automatic increment rule for every addition; this recommendation needs the
maintainer's explicit interpretation. Version 1 alone would not prove an older
installation has this new function; feature-detect the name or require a release
containing it. If the maintainer treats API_VERSION as an exact export-set
version, choose 2 and deliberately update docs/API/wheel assertions together;
do not smuggle that interpretation into implementation.

Source request `version: 1`, corpus contract 1, `PROTOCOL_VERSION = 1` and
workspace schema 3 remain separate and unchanged. This does not make local
source requests a `sol.reference` envelope or promise a serialized source format.
The accepted owned dict fields nonetheless become a Python contract and must be
documented in CORE §4 if approved. No `SourceService`, rendering, config-path or
generic file-hashing export is added to the facade by this proposal.

Keep `_request_current`, `_verify_file`, `_verified_copy`, `_record_digest`,
cache/mapping/atomic-write helpers, renderer settings, PNG validation and final
generation checks private. `_request_current` may be refactored privately to
share the typed extraction/canonical checks; do not simply rename it and expose
the mutable snapshot or advertise it as doing PDF verification. `_verify_file`
remains useful internally and must not become a general public file-verifier
that a caller can combine incorrectly with a different request's digest.

### 3.4 Compatibility and future implementation boundary

The future implementation would replace the two calls and index/read sequence
in both `open_pdf` and `follow_pdf` with the combined validator. BEING uses
`result.verified_pdf`, `result.page.pdf_page` and `result.sources`; companion
matching and asynchronous highlight work receive the immutable result.
`_show`, `_show_on_companion`, `_highlight_arguments` and the initial retry thread
must stop reading the original mutable request. They remain private BEING code,
with Zathura/D-Bus and process/environment policy entirely outside CORE.

`_render` should use the same public validation operation at entry, using an
internally retained fresh snapshot/check helper for its later checks if needed.
`render_region` must validate before its initial bbox access (avoid validating
and hashing twice by passing the already checked values through private code).
Never remove `_verified_copy` on a cache miss, the PDF check on a PNG hit, or
the existing final generation checks. Its existing return values stay
`Path` / `(Path, bool)`. Capture/set-PDF/setup and viewer result types stay the
same; source operations retain local imports so normal reading remains lazy.

Captures emitted by today's `SourceService.capture` remain valid, including
legacy null corpus IDs, renamed originals, configurable external cache roots,
retirement chains, Roman/null printed labels and bbox/full-page fallback.
Existing source-module imports remain at their current paths. Private helpers
need no public deprecation shim; remove their BEING imports in the implementing
PR, retain internal helpers as needed, and do not add aliases at removed
`sol.reader`/`sol.terminal` paths.

Explicit contract changes to approve: full-ID/absolute-path requirements for
hand-built requests, strict field typing, one `SourceError` family for expected
validation failures, immutable return types, final post-hash generation check,
and the agreed interpretation of API_VERSION. Previously accepted malformed
hand-built dicts are not a compatibility target, but this is a conscious
tightening rather than a claim of byte-for-byte behavior preservation.
Passing one capture cannot bless its mutated replacement; staleness still
forces reopening/recapture and the reader's existing eviction behavior.
No source test should start interpreting printed labels as physical pages.

## 4. Alternatives and tradeoffs

| Option | Benefit | Cost / contract consequence |
| --- | --- | --- |
| **Recommended: combined validator and immutable locations** | One required trust sequence; no mutable snapshot escapes; UI gets the exact page/location data it needs, including other-page highlights. | Four facade names and a typed result become supported API; explicit malformed-input/error/freshness decisions need approval. Does not solve future viewer file replacement. |
| Public `check_source_request(request) -> CorpusSnapshot` plus `verify_source_pdf(path, sha256) -> None` | Smallest mechanical replacement of private imports; CORE renderer can reuse snapshot. | Easy to forget PDF verification, mix a path/digest from another request, omit page bounds or trust mutable data. Exposes two low-level contracts and a mutable snapshot without solving shared ordering. Not recommended. |
| Keep private imports, document an architecture **EXCEPTION** | No public commitment; useful temporary containment while maintainers defer the API choice. | Cross-package dependence on unstable helpers remains; preserve every current check and regression test. Current architecture guard already permits this edge, so adding to its existing `EXCEPTIONS` set alone would be ineffective/unused. If a new private-symbol rule is introduced, grant only the exact source/helper pairs with rationale and removal condition. Do not exempt all BEING → CORE imports. |
| Move the viewer's checks into CORE without a facade addition (e.g. internal `prepare_source_page`) | Consolidates sequencing and can fix type errors; leaves API_VERSION untouched while experimentation continues. | If BEING calls another private entry point, the private seam has merely narrowed. A non-underscore function consumed across divisions is a de facto contract and still warrants review. Moving `open_pdf`, D-Bus or viewer discovery into CORE instead would violate interface independence. |
| `SourceService.validate(request, page_index)` method | Can own configurable cache knowledge and eventually opaque handles. | Viewer must carry a Book/service or a new factory; couples an independent detached viewer to live reader state and original selection. More lifecycle/compatibility change than this need requires. A true service-owned handle is the alternative if cache membership becomes a requirement. |
| Return only `None` or a fresh dict / `Path` | Fewer public types; resembles current helpers. | `None` leaves the UI reading unverified/mutable inputs again; `Path` alone omits selected/other-page evidence; dict returns need defensive-copy/type guarantees and remain mutable for retry threads. |
| Public descriptor/context-manager/snapshot lease | Could deliver verified opened bytes through a defined lifetime. | Detached viewers reopen paths and need adapter/lifetime/platform decisions; materially larger public contract. Reserve for a concrete stronger threat/lifecycle requirement. |

Copying `_request_current` or `_verify_file` into BEING would duplicate trust
rules; it is not a preferred alternative. The maintainer may defer all public
changes and retain the current private seam. This PR records a recommendation,
not approval or an instruction to implement it.

## 5. Exact future acceptance tests

All new tests use synthetic corpora/PDFs/temp paths and mocked viewers; no
copyrighted data, personal workspaces, display or network required. Keep all
existing source tests in §2. Extract shared fixture builders if a new
`tests/test_source_validation.py` needs them; do not call another TestCase's
`setUp`. Public behavior tests call the validator, not private helpers. Patches
for deterministic races may target the owning CORE functions.

### 5.1 Validator cases in `tests/test_source_validation.py`

| Proposed exact test name | Setup and required assertion |
| --- | --- |
| `test_current_capture_returns_immutable_ordered_locations` | Capture retired prefix using existing invented data; validate index 1. Assert result class, absolute snapshot Path, index 1 → physical page 3, sources `(1, 3)`, labels `('i', None)`, float bbox tuple and `page is sources[1]`. Mutation of frozen fields fails; no nested list/dict is returned. |
| `test_result_is_detached_from_input_and_later_calls_revalidate` | Mutate request source rows/path after success: old result unchanged; next call refuses changed bound evidence/PDF. Alter disk generation after success: next call refuses; result is not a trust token. |
| `test_legacy_null_corpus_identity_remains_read_only` | Capture valid legacy no-ID corpus; success, no identity allocation or file changes. |
| `test_invalid_request_shape_fails_as_source_error_before_io` | Table: non-dict; missing each owned field; malformed nested dict/list/string; versions `True`, `0`, `2`, `'1'`; malformed UUID/digest; invalid chain; `pdf_pages` bool/nonpositive; relative/empty/NUL/non-string paths. Guard load/PDF open; assert `SourceError`, no I/O or raw `KeyError`/`TypeError`/`AttributeError`/`ValueError`. Include prefix requested ID (capture's output is always expanded). |
| `test_source_locations_require_exact_json_types_and_valid_rectangles` | Table: page bool/string/zero/above declared bounds; bad labels; empty sources; bbox bool, NaN/inf, wrong length, inverted/negative rectangle, tuple where capture uses list. All raise `SourceError`, never fabricate/clamp a crop. Valid canonical numeric coordinates normalize to immutable floats. |
| `test_page_index_is_a_source_list_index_not_a_pdf_page` | Index 1 selects physical page 3; reject `True`, `False`, `-1`, `2`, `1.0`, `'1'`, `None`. Structurally invalid index fails before load/PDF read. |
| `test_generation_binding_tampering_and_disk_edits_are_refused` | Independently alter each of the five binding fields (including wrong ID and directory); unindexed Markdown edit, damaged index/metadata, and a valid reindexed attribution-only or unrelated-record change. All old captures fail `SourceError`; nothing is repaired. |
| `test_record_chain_digests_and_source_binding_cannot_be_substituted` | Table: unknown requested ID, wrong target, truncated/reordered chain, content/metadata digest, PDF SHA/page count, changed/reordered/dropped sources or bbox/label, missing metadata digest. Assert `SourceError`; resolve real retirements explicitly, no fuzzy fallback. |
| `test_pdf_missing_directory_symlink_wrong_digest_and_read_failure_are_refused` | Remove captured file; use directory; final symlink to an otherwise correct PDF; altered bytes; mock open/read `OSError`. All raise `SourceError` before any viewer/process action. |
| `test_pdf_change_during_hash_is_refused` | Deterministically alter opened-file before/after identity (including same-size edits) or inject a write during read. Assert `SourceError`; no stat-only cache can bypass SHA verification. |
| `test_corpus_change_during_pdf_hash_is_refused_before_return` | Change canonical file/reindex between initial snapshot check and end of PDF verification; final generation check raises `SourceError` and no result escapes. |
| `test_validation_uses_captured_bytes_without_discovery_or_writes` | Replace/delete original PDF; keep captured one intact. Success with original discovery, mapping writes, mkdir, render subprocesses and viewer launch patched to fail. Fingerprint all corpus/config/cache files before/after: unchanged. Changed captured PDF must fail even if original is good. |
| `test_external_same_digest_pdf_is_allowed_without_a_cache_membership_claim` | Copy exact bytes to another regular absolute temp path and replace `verified_pdf`; success. Repeat via final symlink: refusal. This locks the deliberate containment limit, not an accidental omission. |
| `test_unbound_display_fields_are_ignored_and_never_returned_as_evidence` | Change title/attribution/source filename/original path or add an extra descriptive field. Canonical immutable locations remain unchanged; do not return or bless these fields as verified. Bound-field changes still fail. |

### 5.2 Consumers, races and architecture

In `tests/test_source_viewer.py`, add
`test_open_and_follow_validate_before_viewer_or_companion_access`: parameterize
both entry points over stale request, invalid index and corrupt/symlink PDF;
assert `SourceError` before `Popen`, `_show_on_companion` or D-Bus calls, including
headless/no-companion conditions. Add
`test_open_and_follow_use_the_public_validator_result`: patch the owning public
entry point with distinctive immutable paths/page locations and assert both
consumers use those, not raw request fields. Patch the name where the viewer
looks it up; test facade identity separately.

Add `test_highlight_retry_uses_detached_validated_locations`: delay the retry
thread, mutate raw sources/bbox/path after launch, then run it; captured immutable
locations determine navigation/highlights. This does not assert corpus freshness
for the entire asynchronous viewer lifetime. Keep existing companion/no-launch,
fallback, no-display and detached-stream tests.

In the renderer tests add
`test_render_region_validates_before_bbox_lookup` (malformed requests produce
`SourceError`), `test_corpus_change_during_render_or_cache_hit_is_refused`
(inject disk edit at each late-check boundary), and
`test_renderer_reads_the_same_verified_bytes_it_copies` (replace source pathname
after source open; the render gets the checked copy or refuses, never unchecked
replacement bytes). Preserve corrupt-PDF-on-PNG-hit, PNG sidecar/crop settings,
cleanup and real-Poppler synthetic tests. Avoid duplicate PDF hashes merely to
share validation; instrument one validation at render entry, plus the required
verified copy on a miss.

In `tests/test_architecture.py` retain all five existing tests and **no new
division exception** for the recommended design. Add:

- `test_source_consumers_use_public_core_validation`: static AST check of the
  real product source rejects imports/access of `_request_current`/`_verify_file`
  from outside `sol.core`/`sol.corpus`; the migrated viewer imports the public
  validator. Inspect from-import symbols as well as module edges, since the
  current scanner intentionally records the module only. No inspected import
  is executed. This can be a focused rule rather than a new global ban on every
  private name in SOL.
- `test_private_source_validation_rule_finds_local_relative_and_aliased_uses`:
  synthetic top-level/function-local/conditional and relative from-imports,
  aliased helper imports, and module aliases followed by literal helper
  attribute access fail with file:line diagnostics; CORE-internal equivalents
  and public validator imports pass. Include `raise RuntimeError(...)` in
  inspected source to prove no execution. Arbitrary computed getattr/data-flow
  remains outside the static guard; do not claim otherwise.
- Extend `test_dynamic_imports_and_lazy_facade_tables_are_inspected`: the four
  new facade literals resolve to `sol.core.source` and pass direction policy;
  a synthetic facade target of `sol.being.source_view` still fails. Existing
  unknown-package, removed-package and unused-exception checks remain intact.

Retain the four Neovim orchestration tests in §2 and expand the stale-capture
eviction case to errors from open/follow as well as crop rendering. Confirm the
next request recaptures without moving the reader or saving workspace state.

### 5.3 Facade and must-not-load guards

| File / existing guard | Exact future extension or preservation |
| --- | --- |
| `test_core_api.py`: `test_lazy_facade_identity_exports_and_unknown_names` | Assert identity of all four new facade names with `sol.core.source`, uniqueness in `__all__`, discoverability in `dir`, unknown names still `AttributeError`. Existing `API_VERSION == 1` assertions stay under the recommended version decision. |
| `test_core_api.py`: `test_fresh_public_import_and_model_request_do_no_io_or_optional_import` | Add `sol.core.source`-absent assertions after bare import, `dir(core)` and model/config/reference name resolution. Keep its no-file-I/O and interface import guard. |
| New `test_core_api.py`: `test_source_validation_exports_import_without_io_processes_or_interfaces` | Fresh process: request all four source exports while Path data reads/mkdir and process starts fail. Forbid `sol.app`, `sol.being` (workspace/viewer/Neovim included), `sol.presentation`, `sol.essence`, `markdown_it`, Textual/Rich, extraction/conversion backends, OpenDataLoader, fitz/pypdf/pdfplumber and ML frameworks. Check `sys.modules` as well as an import hook; source/contract/std library are allowed here. |
| New `test_core_api.py`: `test_source_validation_runs_without_interfaces_or_pdf_libraries` | Fresh process with already-created invented corpus/PDF capture, same forbidden modules, process calls guarded: invoke validation successfully and on a stale capture. File reads are allowed during validation, writes are not. Assert no UI/workspace/parser/extractor was loaded. This distinguishes import safety from operation safety. |
| `test_package_boundaries.py`: `test_reader_import_does_not_load_pdf_conversion_or_optional_ui`; `test_config_import_has_no_reader_corpus_or_interface_dependency` | Preserve source-module absence for parser startup/config discovery. No eager source-name imports in root, config, reference, options or normal reader startup. Add bare-facade/`dir` source-absence assertion if not already covered by the fresh public-import test. |
| `test_reference_cli.py`: `test_fresh_process_capture_and_check_import_no_optional_ui_or_extraction` | Keep the explicit **`sol.core.source` must-not-load** guard for capture, check and all help modes. Public source exports must stay lazy. Keep protocol decode/import no-I/O tests in `test_core_protocol.py`. |
| `test_workspace_export_cli.py`: `test_actor_free_markdown_export_has_no_writes_or_optional_source_imports`; packaging's `test_installed_markdown_inquiry_export_preserves_json_and_private_state` | Preserve source-module prohibition, no actor/profile/default-workspace writes and no network. Merely adding a facade mapping cannot make export resolve it. |
| `test_packaging.py`: `test_installed_relocated_modules_preserve_core_and_presentation_boundaries` | Under its existing no-data-I/O/no-interface guard, resolve the four source exports from the installed wheel, assert identity and wheel paths. Do not import BEING to validate a source request. |
| `test_packaging.py`: `test_core_only_wheel_proves_interface_dependency_boundary` | Exercise new facade exports and a synthetic successful validation in the wheel containing only CORE/contract, no interfaces or dependencies. Create the invented capture/PDF outside the guarded subprocess; fingerprint files before/after validation. Keep ordinary reference operations, API version assertion, and parser/PDF/extractor/UI prohibitions. Its existing fixture source fingerprint is synthetic; use a matching invented PDF rather than trying to recover one from a hash. |
| Help/one-shot/installed reader guards in `test_reader_view_cli.py`, `test_packaging.py`; ESSENCE/Neovim fresh-process boundaries | Keep passing unchanged. Validation access is an explicit source action, not a requirement of `--help`, ordinary random output, reference exchange, ESSENCE import or workspace export. |

These runtime guards complement the static architecture test: a legal CORE →
CORE edge can still eagerly load source code or an optional package. Do not
weaken a must-not-load tuple to get the public export change through.

## 6. Decision and implementation gate

**Maintainer decision (reserved: public CORE contract):** accept the combined
operation, result types, failure/temporal/path limits, owned local dict schema,
and additive API_VERSION interpretation in §3; choose an alternative in §4; or
defer and keep today's private coupling. No option is implemented here. The
absolute/full-ID/strict-typing and final-generation-check choices are explicit
parts of that decision, not incidental cleanup.

After approval, a separate implementation PR should update CORE §4's supported
API/limits and the changelog, migrate consumers atomically, implement §5, and
close the private seam in the placement register/REEVALUATION with the approved
PR link. Do not change governing Decision statements in this proposal PR.

Required verification for that implementation and for this documentation PR:

```sh
/home/dima/Projects/code/sol/.venv/bin/python -B scripts/check_docs.py
/home/dima/Projects/code/sol/.venv/bin/python -B -m unittest discover -s tests
git diff --check
```

Run the implementation's focused validator/viewer/API/architecture tests too;
the full suite includes package/wheel and fresh-process guards. CI covers Python
3.10 and 3.14. Actual results for this documentation-only PR are recorded in
[HANDOFF](../HANDOFF.md); the test matrix above remains proposed. Do not commit
corpus data, PDFs, source images, workspaces, logs or generated test artifacts.
