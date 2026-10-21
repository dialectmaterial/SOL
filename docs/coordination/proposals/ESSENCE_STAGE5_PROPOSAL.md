# ESSENCE Stage 5: adapters and Experiment B

**Status:** proposal for Claude's review and maintainer decisions, 21 October
2026. Nothing here adopts an API, dependency, artifact format or new Decision.
**Baseline:** `origin/main` at `59624ea`; inspected `sol/essence/` providers,
prose export, lazy exports, method catalog and existing study contracts.
**Task:** [Codex: Stage 5 design proposal](../CURRENT_TASK.md#codex-stage-5-design-proposal-model-adapters-and-experiment-b).

This proposes one local embedding run with checkable source rows and Projector
exports. It follows [ESSENCE §1](../../ESSENCE.md#1-purpose),
[§3](../../ESSENCE.md#3-proper-model-inputs-projections-not-destructive-cleaning),
[stage 5 and Experiment B](../../ESSENCE.md#5-prioritized-experiments), and
[§8](../../ESSENCE.md#8-developer-acceptance-and-prohibitions).
SOL owns selection, receipts, validation and source return. Established libraries
own embedding, similarity and dimensionality reduction. No model store, training
framework, plugin marketplace or extensive parameter UI is proposed.

## 1. Existing boundaries

- `export_prose(snapshot)` returns `sol.prose-input` v1 in canonical order,
  with selection/projection identifiers, input text digests, UUIDs, ancestry,
  attribution, source pages, corpus identity and generation. Only
  `passages[].text` may enter the embedding tokenizer. Heading labels stay out.
- `CoreProvider` and `FileProvider` serve word/sentence/TF-IDF studies. Their
  internal loader is not a public general model API. In particular, word inputs
  use canonical plain text and facsimile masks; they are not the prose export.
  Do not reuse that loader under an embedding label or change its behavior.
- `methods.json` describes shipped studies; `encyclopedia.json` supplies reading
  material. Neither constitutes a runtime registry. Do not turn encyclopedia
  topics into installed-capability claims or reopen its deferred task registry.
- CORE API/reference v1 and existing study artifacts remain unchanged. Strict
  generation checks apply even after an unrelated corpus correction. A projected
  character offset is not automatically a canonical plain-text offset.

## 2. Capability and adapter interfaces (proposed; R1–R3)

Use a small bundled, versioned descriptor collection and explicit internal
dispatch, not third-party entry-point discovery. Registry, execution and result
schema versions are independent of CORE's API version. The names below describe
contracts for review, not available Python functions or installed commands.

| Boundary | Input → output | Responsibility |
| --- | --- | --- |
| List capabilities | no corpus → immutable descriptors | Read package metadata only; no runtime import, network, model load or device enumeration |
| Probe a capability | descriptor + explicit local environment/model location → availability report | On request, check installed distribution versions and local file inventory without loading weights; readiness remains provisional until execution |
| Prepare input | caller-selected source + scope + projection policy → ordered rows + binding + exclusions + freshness check | CORE adapter calls current prose export; file adapter reads explicit UTF-8 bytes without importing CORE |
| Plan run | descriptor + prepared rows + explicit settings → validated run specification or refusal | Resolve exact model/tokenizer files, effective limits, resource caps and policies before embedding |
| Execute adapter | run specification + rows + cancellation/progress channel → keyed vector rows + execution receipt | Lazily import the chosen library in an owned worker; never receive workspace write authority |
| Verify bundle | caller-selected source/model + bundle + verification level → structured report | Validate structure, bind to current source, optionally recompute; never follow executable instructions or absolute paths in artifacts |
| Export/view | verified bundle + selected local destination/mode → TSV pair or explicit viewer session | Separate from embedding and from source navigation |

A descriptor declares stable capability/adapter IDs and interface version;
task (`text-embedding`); accepted providers/scopes; projection and result schema
IDs; runtime distribution requirements; model identity requirements; supported
languages; effective token/dimension limits; pooling, normalization and overflow
policies; CPU/GPU support; privacy/network requirements; and parameter bounds.
Unresolved model-dependent limits are explicitly unknown, never guessed.
Availability distinguishes missing dependency, incompatible version, missing
checkpoint, unsupported input/policy and ready-to-attempt. Show actionable reasons
without importing the unavailable runtime. Update Methods only when an adapter
actually ships; retain the encyclopedia as a separate table of contents.

Prepared rows have stable `row_id`, provider/source identity, projection ID,
input text digest, language and provenance; private text exists only during the
run. The adapter returns the same unique row IDs with vectors. Reject missing,
duplicated, additional or reordered IDs rather than silently zipping two lists.
Scope and parameters are serializable independently of widgets. CLI and TUI
call this same boundary and produce the same scientific payload; timestamps,
resource observations and run IDs may differ. Start headless; later expose only
the tested operation in the current interface.

## 3. First embedding policy (R3–R5)

Recommend a CORE passage pilot: each row is exactly one complete eligible
`passages[].text` from a freshly verified prose export. Scope is an explicitly
selected section or ordered set of complete passages, filtered after export
without changing canonical ordering. Retain all eligibility/scope exclusion
counts. No sentence segmentation, paragraph concatenation, lowercasing or
heading blacklists. Model-tokenizer normalization is separate and recorded.
Declare the edition's translation language from provenance; an unknown language
must remain unknown rather than be inferred from a heading.

For file-only execution, propose a separate `utf8-verbatim-file-v1` projection:
one whole file, no paragraph inference, hashing the complete original bytes,
without newline, BOM or Unicode rewriting. It has no UUID, edition claim or
CORE source return. Full-file only initially; existing span APIs remain intact.
A long file can be refused. Use two independent small files/runs to exercise
file execution; multi-file collections need a later explicit policy.

Tokenize without truncation to measure actual model tokens, including special
tokens, then compare with the recorded effective checkpoint/tokenizer/runtime
limit. Recommend **refuse over-limit input** for the first pilot, listing affected
IDs and lengths; do not silently drop long passages and claim a full-section run.
The researcher may choose a smaller explicit scope and record that selection
bias. `truncated=false`, `chunking=none`, original/effective lengths and limit are
still fields in every row. Future chunking needs a separate policy with source
offsets in a named coordinate space, overlap, chunk order and aggregation rules;
it cannot silently replace the passage baseline.

Recommend the purpose-built English sentence-embedding candidate
`sentence-transformers/all-MiniLM-L6-v2`. Its [publisher model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
lists Apache-2.0, 384 dimensions and a default 256-word-piece limit; it is a
candidate for the translated prose, not evidence of philosophical suitability.
Before adoption, resolve an immutable repository revision, inspect the actual
license/configuration/tokenizer/pooling files, hash all files used and test the
effective limit including special tokens. No unpinned `main` checkpoint in a run.
No particular revision has been downloaded, evaluated or approved by this task.

Use the checkpoint's Sentence Transformers pooling pipeline, float32 output,
explicit L2 normalization, evaluation/inference mode and CPU first. Record empty
prompts explicitly. Reject zero-norm or nonfinite vectors and wrong dimensions.
The [library API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html)
offers local-only loading, revision, device, output precision and normalization
controls; explicitly set them rather than inherit changing defaults. Keep
`trust_remote_code=false`; prefer safe tensor weights. No SOL pooling or
transformer implementation.

**UltraBERT remains unresolved.** A name alone identifies neither a released
checkpoint nor an embedding recipe. Before a comparison, supply publisher URL,
immutable revision/file hashes, intended task, supported languages, license,
token/window limits, resource needs and an established extraction/pooling method.
A classifier backbone requires independent embedding validation. Do not invent
its identity or install a similarly named package. Compare it with the approved
sentence baseline on exactly the same eligible source rows once those questions
are resolved; until then a single baseline proves plumbing, not model superiority.

## 4. Bundle and reproducibility record (R6–R8)

Propose `sol.embedding-study` v1 as a manifest in a private run directory, with
the following fixed relative filenames. TSVs are viewer interchange; the manifest
is the authoritative binding. This is a new format requiring approval, not a
reinterpretation of the existing `sol analyze check` contract.

| Artifact | Required content |
| --- | --- |
| `study.json` | Schema/method/adapter versions, run specification, ordered row receipts, source binding, exclusions, execution outcome and digest/byte length of every payload |
| `vectors.tsv` | UTF-8, LF, no header; N numeric rows, D tab-separated finite float32 values, round-trip decimal precision, no locale formatting |
| `metadata.tsv` | One named header plus N rows in identical order: row ID/index, UUID or explicit absent file identity, input/source digests, language, token lengths, overflow policy, source location and hierarchy labels |
| `environment.json` | Exact interpreter/platform, installed runtime/transitive versions, lockfile digest and sanitized invocation/settings; no credentials, private absolute paths or text |
| `neighbors.json` (later comparison) | Query row IDs, candidate-set digest, metric, k, scores, deterministic tie order, original-space method/runtime and parent bundle digest |
| `projection.json` + coordinates (optional later) | Parent vectors digest, row subset/order, algorithm/version, preprocessing, dimensions, seed and every effective parameter; never replace original vectors |

The manifest records corpus UUID, edition/source fingerprints and full generation
binding, or complete file byte digest/length; exact scope, projection identifier,
source content digest and projected text digest per row; canonical provenance,
all PDF/printed pages and hierarchy metadata; and an ordered input-receipt digest.
Projected text digests and canonical content digests must be separately named.
Rows contain no passage body or preview. The private prose export need not be
persisted; if retained explicitly, it remains outside Git with the same protections.

Model records include publisher/repository, immutable revision, all consumed-file
hashes, license identifier/source, tokenizer version/configuration, special-token
policy, effective input limit, pooling/modules, prompts, dtype, dimension,
normalization and overflow behavior. Execution records include SOL commit/dirty
status, adapter version, UTC start/end, outcome, seed(s), thread/batch settings,
device/backend and hardware, deterministic flags and limitations, elapsed time,
observed peak RSS/VRAM with measurement method (or unavailable), and any explicit
CPU/GPU fallback. Recommend no automatic device fallback: a new device is a new
run. A pinned environment includes a platform-specific exact dependency lock and
package hashes, not merely top-level version ranges. Record model acquisition
separately from computation; downloading weights is not permission to upload text.

Serialization must define strict JSON, duplicate-key/nonfinite rejection,
bounded nesting/strings/counts, UTF-8/LF, TSV field escaping, numeric rounding
and hashing of exact bytes. For metadata, propose reversible backslash escaping
of backslash/tab/CR/LF with a recorded encoding policy; the viewer displays
escaped labels. UUID/digest fields have strict syntax. Reject malformed control
characters. No spreadsheet formulas or text previews are needed in exports.
Manifest entries accept only these relative filenames, no traversal/symlinks.

Proposed pilot caps: 1,024 rows, 4,096 dimensions, 64 MiB source-file bytes,
16 MiB manifest, 256 MiB per TSV and 512 MiB total bundle. Enforce while reading
and writing, before allocation where possible. Empty eligibility is a structured
refusal, not a successful zero-row Projector export. Larger runs require an
explicit reviewed increase, not a claim that these caps cover every future model.

Verification reports independent levels:

1. **Integrity:** schemas, supported methods, byte hashes, row IDs/order/count,
   metadata alignment, finite uniform dimensions, normalization tolerance and
   bounds. Works offline without CORE or an ML import; does not prove that a
   model produced the vectors. A consistently rewritten bundle is not authentic.
2. **Source binding:** regenerate the selected projection from caller-supplied
   current sources and compare the full binding and ordered receipts. CORE uses
   existing strict verification, including unrelated generation changes; files
   require an explicit path and complete original-byte digest. Never trust a
   path from the artifact. Recheck freshness before final publication.
3. **Recomputation:** explicitly load the exact local model/environment and
   reproduce vectors. Report byte equality separately from numeric agreement.
   Proposed float32 tolerance is absolute and relative `1e-5`; record maximum
   error, hardware differences and nearest-neighbor rank changes. Tolerance is
   a reviewed policy, not a universal guarantee across devices or library updates.

Checks without the model say recomputation **not performed**, never verified by
implication. A stale run remains readable as historical output but cannot offer
current-source navigation or a successful freshness check. No weaker reference
protocol or automatic migration is proposed.

## 5. Viewing, source return and interpretation (R9–R10)

Experiment B already calls for separate vector and metadata TSVs. The
[Projector application](https://projector.tensorflow.org/) offers local file
loading; the [official TensorBoard tutorial](https://www.tensorflow.org/tensorboard/tensorboard_projector_plugin)
describes a different checkpoint/log-directory integration. Do not conflate
TSV export with a verified TensorBoard launch path or copy its training example
into SOL.

Recommend manual loading into a pinned, locally served Projector build first,
in an isolated browser profile with outbound networking blocked. Verify assets,
workers, telemetry and file-load behavior with invented data before the private
book is used; record viewer revision/build digest, browser and observed network
behavior. Local file selection inside a remotely supplied web application is
not sufficient evidence of privacy. No automatic public-site launch, cloud
upload, sharing links or published datasets. A hosted mode would need an
explicit user decision about the actual payload and destination; it remains out
of scope. If a local viewer cannot be demonstrated, deliver verified TSVs and
report viewing as blocked rather than silently use the hosted site.

Any later launcher binds loopback only, serves only the selected run directory,
checks paths and owns/terminates its server process; it must not expose the
corpus, home directory or tokens. Serving assets is distinct from ML execution.

For source return, choose a result UUID, validate its recorded generation/content
against the caller's current CORE source, and use existing guarded BEING source
navigation to the **passage start**. Do not pass projection offsets as canonical
offsets. Preserve the original reader cursor/selection and explicit return action;
files explain that CORE return is unavailable. Projector metadata can identify
the UUID for lookup; a clickable browser-to-reader bridge is deferred. Neither
vectors nor neighbor output may create canonical text or workspace assertions.

For the first comparison use a mature library's exact cosine nearest neighbors
in original normalized embedding space, excluding self, with stable row-ID tie
ordering and declared k/candidate set. Use bounded queries/batches rather than
an unbounded N-by-N matrix. Keep that report separate from viewer projections.
Later PCA/t-SNE/UMAP records must include centering/scaling, seed, initialization,
iterations, perplexity or neighbor count, distance metric and exact subsampling.
An unrecordable interactive view is exploratory and not reproducible evidence.
Compare neighbor overlap/rank changes across models on the common row set;
do not numerically align dimensions from different models. Granularity or
overflow comparisons get separate policy IDs and explicitly aligned source units.
Clusters suggest textual neighborhoods, not logical necessity or classification
success. Hierarchy labels are display/evaluation `y`, never feature strings;
any later supervised study splits by contiguous sections and reports leakage
controls rather than randomly splitting adjacent prose.

## 6. Optional software and installation (R2, R4, R9–R10)

No dependency is added by this PR. Proposed software is acquired only after
approval in a separate research environment; ordinary reading, menus, CORE,
integrity checks and encyclopedia browsing need none of it.

| Optional component | Purpose and recommendation | Alternatives / gate |
| --- | --- | --- |
| `sentence-transformers` with `torch`, `transformers`, `tokenizers`, `huggingface-hub`, `safetensors`, `numpy` and resolved transitive packages | One local CPU adapter; lock all installed packages and weight files | Direct Transformers needs a separately validated embedding recipe; ONNX/OpenVINO and GPU backends deferred |
| Model/tokenizer/configuration files | Explicitly acquired, licensed, immutable local checkpoint | No implicit runtime download; missing files cause an actionable refusal |
| `scikit-learn` | Later exact cosine neighbors and optional PCA/t-SNE via mature implementations | Not needed for first vector/TSV pilot; no SOL replacement algorithm |
| Projector frontend build + browser; build toolchain if required by the selected revision | Pinned local viewer with audited network behavior | Manual reviewed build first; choosing it still requires checking its license and complete build dependencies |
| `tensorboard` | Alternative opt-in local Projector server, only if tested with the chosen export/configuration route | Check exact plugin/version requirements; no assumption that bare TSVs are automatically discovered |
| `tensorflow` | Only if a separately approved TensorBoard checkpoint route actually requires it | Not required merely to compute embeddings or write TSV; avoid this additional framework initially |
| `umap-learn` | Deferred projection comparison | Do not add for the first run; PCA/t-SNE/viewer controls already require explicit records |
| spaCy/Stanza, remote APIs, GPU toolkit | No role in the first adapter | Separate task, dependency and privacy decisions if later justified |

Exact runtime versions and supported Python/platform matrix must be established
by an installation spike after approval; upstream API documentation is not a
tested SOL compatibility matrix. In particular, do not assume this checkout's
Python 3.14 or every SOL-supported Python has matching ML wheels. Recommend an
isolated supported Python environment with CPU wheels and a subprocess boundary,
not narrowing the reader's Python requirement. No `pyproject.toml` extra name or
version range is adopted here. Separate SOL distributions are premature.

## 7. Smallest first step and staged acceptance

**First implementation task after approval:** a headless adapter-contract slice
using invented short text, no model download and no added dependency. Implement
metadata listing, strict run/row receipts, fake-adapter boundary tests, bundle
writer and integrity/source-binding checks behind an internal interface. The
fake adapter is a test double, never a scientific embedding capability. Prove
listing imports no CORE/Textual/ML runtime, a file run imports no CORE, malformed
or reordered output fails, and interrupted publication cannot look complete.
This establishes only orchestration; stage 5 remains incomplete.

Next, in a separately approved locked CPU environment, acquire the chosen exact
checkpoint explicitly, execute it on invented text without network access, test
Unicode, unknown language, empty and over-limit input, repeat runs and measure
resources. Then run a small explicitly selected private CORE scope with exact
prose inputs, freshness checks, TSV alignment and a real passage return. Finally
verify the local Projector privacy/mode and load the TSVs. Only afterward add a
thin TUI action and the same headless operation, with parity checks; compare
models only when a second exact checkpoint passes the same gates.

Tests must cover missing/incompatible runtimes/checkpoints, changed files or
unrelated CORE generations, modified snapshots, eligibility flags, mixed/unknown
language, duplicate/missing/reordered IDs, dimension mismatch, NaN/Infinity/zero
norm, truncated output, path traversal/symlinks, resource limits, worker failure,
cancellation and no-overwrite publication. Keep automated correctness,
real-corpus measurements, manual viewer privacy/return checks and scholarly
interpretation separate. A successful fake run or exported TSV is not end-to-end
Experiment B acceptance.

Recommend explicit cancellation on interface exit, owned subprocess termination
and no detached jobs initially. Stage in an owner-only private sibling directory;
publish atomically without replacing an existing destination only after every
file and freshness check succeeds. Remove only runner-owned incomplete staging
files on cancellation; never delete completed runs, corpus files or personal
work. No automatic cache eviction, artifact migration or workspace-history schema.

## 8. Decisions requiring approval

Every item below is **(reserved)**; recommendations are proposals, with no
implementation assumed. IDs cover the contracts and choices above. Approval of
this design PR alone should not be read as approval of an unspecified checkpoint,
dependency lock or external transfer. No authority Decision statement is changed.

| ID | Reserved decision and options | Recommendation |
| --- | --- | --- |
| R1 | Provider/adapter/capability API and versioning: private versioned boundary; public plugin API/entry points; separate distributions | Private v1 boundary and bundled metadata-only registry; publish nothing separately yet |
| R2 | Runtime packaging/dependency set: reader extra; isolated research environment/subprocess; external service | Isolated CPU environment with exact tested lock/platform record; no reader dependency or Python-range change |
| R3 | Input and scope contract: reuse word projection; exact prose-export passages; sentences/chunks; whole-file/spans/collections | Exact prose export for complete CORE passages, separate verbatim whole-file policy; no new canonical schema or projection-offset return |
| R4 | Checkpoint/license/extraction adoption: exact sentence baseline; verified UltraBERT; other purpose-built model | Evaluate all-MiniLM-L6-v2 first; approve immutable revision/file inventory and recipe before use; UltraBERT unresolved |
| R5 | Length/granularity/numeric policy: reject; truncate; chunk/aggregate; CPU/GPU/quantized outputs | Reject overflow, no chunks, explicit float32 L2-normalized CPU output and no automatic fallback |
| R6 | New artifact contract and limits: manifest plus TSVs; monolithic JSON; binary matrix/archive | `sol.embedding-study` v1 manifest and fixed TSV pair with strict escaping/hashes, proposed caps and separately bound optional derivatives |
| R7 | Verification/reproducibility contract: integrity only; source check; exact replay; numerical replay/relaxed freshness | Report all levels separately, retain strict generation binding, exact-byte comparison plus declared `1e-5` numeric tolerance; never claim cross-device identity |
| R8 | Publication, deletion and job lifetime: overwrite/resume; immutable runs; detached jobs; cancel on exit | Owner-only atomic no-overwrite runs, cancel owned worker on exit, clean only owned incomplete staging; defer durable investigation/workspace changes |
| R9 | Viewer/dependencies/privacy: hosted local-file loading; pinned local Projector; TensorBoard/checkpoints; export only | Audit pinned local Projector first, export only until proven; separately approve build/runtime dependencies, no hosted transfer default |
| R10 | Comparison/projection dependency and evidence contract: exact cosine via scikit-learn; approximate index; viewer-only plots; UMAP | Later scikit-learn exact original-space neighbors and recorded PCA/t-SNE; defer approximate search/UMAP; projection never substitutes for original-space evidence |

Defaults within this proposal: preserve existing authorities and artifacts;
implement headless plumbing before presentation; keep the catalog small; retain
source-return guards and interpretation warnings. Unrelated open ESSENCE choices
(split geometry, outer host, durable investigations) remain outside this task.
