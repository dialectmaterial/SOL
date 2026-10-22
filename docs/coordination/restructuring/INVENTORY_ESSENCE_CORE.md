# Stage A inventory: ESSENCE, corpus, CORE and scripts

**Date:** 21 October 2026. **Owner:** Codex. **Status:** inventory for review.

Baseline: `origin/main` at `c0f469780ac09a3ea832e4e3b3b0fecb303d4399`.
The maintainer's leading document was read from PR #86,
[`docs/SPECULATIVE.md` at `1424aae9`](https://github.com/dialectmaterial/SOL/blob/1424aae9ec3e16cc8c9a0c3aaea64a67782b7fd6/docs/SPECULATIVE.md),
especially §§4 and 7 (also §§5–6). It was not yet on this baseline.
This report follows Stage A, rather than treating the target hierarchy as an
already implemented architecture. It makes **no logical subdivision placements**,
creates no logical directories, and changes no product code or contracts.
Claude's parallel `INVENTORY_BEING.md` is outside this task.

## 1. Scope, evidence and reading convention

The inventory covers every Python module recursively in `sol/essence/`,
`sol/corpus/`, `sol/core/`, and `scripts/`, including package initializers,
plus ESSENCE's two bundled JSON resources. Responsibilities below come from
function bodies, import sites, dispatch and test assertions, rather than directory
names alone. Current contract context: [ESSENCE](../../ESSENCE.md) §§2–6 and
[CORE](../../CORE.md) §§2–10; SPECULATIVE leads the future restructuring.

Sections 3–6 describe **each module's current boundary**, route and protection.
Section 9 records outgoing imports and all reverse importers found mechanically
across repository Python source, tests and scripts. Its test-import lists are
an audit trail, **not a coverage measurement**: facade imports, subprocess code,
patch targets and indirect integration tests need the additional evidence in
§§2 and 7. The reproducible scan in §10 parses without importing application code.
Function-local imports are included; their presence is not a claim of eager loading.

In the tables, route and test codes refer to §§2 and 7. `E`, `C` and `R` are
execution routes, not proposed package destinations. Modules without a standalone
command are reached through the listed caller route. No private corpus, PDF,
workspace, engine download or human reading trial was needed for this inventory.

## 2. Entry points and runtime routes

| Route | Entry and actual call path |
| --- | --- |
| E | Installed `sol = sol:cli`, or `python -m sol`, lazily reaches `sol.reader.app.main`; its early `essence` dispatch calls `sol.essence.cli.main` before reader onboarding. Also `python -m sol.essence.cli`. |
| E-W | `sol essence words` → `word_cli.run` → providers and `words.analyze_words`; `words-export` → `word_cli.run_export` → `comparison.export_word_comparison`. `check FILE` decodes/dispatches word artifacts to the same adapter and recomputes with explicit sources. |
| E-S | `sol essence sentences`: the default snapshot route loads CORE and calls the v1 sentence API; provider/file/passage/span options route through `sentence_cli.run` for v2. `check` routes both sentence versions through that adapter. |
| E-T | `sol essence tfidf` and TF-IDF `check` → `tfidf_cli.run` → `tfidf`, reusing word providers and receipts. |
| E-P | `sol essence prose` → CORE discovery/snapshot → `prose.export_prose`; JSON can contain derived prose, unlike the text-free study receipts. |
| E-U | Reader `essence_open` request → `sol.terminal.neovim_reader.essence_panel` → private context file and subprocess `python -m sol.essence.tui --context FILE [--theme ... --theme-file ...]` → `tui.__main__.main` → `EssenceApp`. Lua `neovim_essence.lua` owns split/fullscreen/focus, and receives the app's source-opening escape packet; `essence_source` returns through the reader controller and its guards. |
| C-V | Installed `sol-corpus = sol.corpus.convert:main`, or `python -m sol.corpus.convert`: `convert` invokes audited Cambridge/Poppler import; `index` invokes contract reindexing. Reader first-run onboarding can explicitly invoke the audited converter too. |
| C-X | Same corpus command: `extract` → `extraction.extract_candidate` → lazy OpenDataLoader backend; `normalize` → `normalize_candidate` on external JSON; `ingest` → `ingest.ingest_reviewed` against explicit candidate/review/baseline/output. |
| C-K | Installed `sol-corpus-check = sol.corpus.contract:main`, or `python -m sol.corpus.contract CORPUS`: default regenerates the index; `--check` validates the existing index without writes; `--initialize-identity` explicitly initializes/retains lineage identity. The command name does not mean a read-only load. |
| R | Bare `sol` / `sol being`, one-shot book commands and `--shell` consume CORE book/models/paths. `--set-corpus` validates and saves configuration; `--set-theme` shares the same config file. `sol ref capture/check` goes through `sol.terminal.reference` to CORE reference/transport APIs. Reader, source viewer, workspace services and ESSENCE use snapshots/references in process too. |
| D | Checkout commands `python -B scripts/check_docs.py [--root PATH]`, `python scripts/install.py [--check|--yes] [--source ...]`, `python scripts/reader_timings.py [--corpus ...] [--startup-only] [--json]`. These are not installed console entry points. |

The four installed entry points come from `pyproject.toml`; `sol-window` is the
fourth and reaches the reader through the terminal launcher, rather than owning
an ESSENCE/CORE implementation. There is no `sol essence` console-script entry
separate from `sol` and no standalone command for an individual tokenizer/provider.

## 3. ESSENCE modules: actual work and current boundaries

Paths in this table are relative to `sol/essence/`.

| Module | Actual work and present boundary | Routes; protecting tests |
| --- | --- | --- |
| `__init__.py` | Lazy `__getattr__` exports prose, providers, word/comparison/sentence/TF-IDF functions, preserving object identity. No UI startup or eager CORE import. Dynamic dispatch is additional to the AST graph. | E and public Python API; W, S, T, P, B |
| `cli.py` | Defines six commands, dispatches strict artifact protocols before source discovery, renders legacy sentence summaries, escapes unsafe human-output characters and emits controlled JSON/refusal output. It orchestrates analysis, not reader/workspace state. | E, all headless routes; A, W, S, T, M |
| `word_cli.py` | Defines shared provider/scope flags; bounded artifact input; resolves caller-selected target/reference files or CORE snapshots; renders counts; verifies before CSV/TSV export. Reuses saved scopes but never treats saved file metadata as permission to open a path. Has its own artifact transport helper rather than using CORE wire input. | E-W and shared E-S/E-T flags/providers; W, S, T |
| `sentence_cli.py` | Renders provider statistics, preserves v1 verification, constructs explicit providers for v2 and handles optional CORE origin anchors. File execution stays independent of CORE. | E-S and sentence `check`; S |
| `tfidf_cli.py` | Small human/JSON adapter for ranking and recomputation, sharing provider construction with word CLI. No independent tokenization or weights implementation. | E-T; T |
| `tokenization.py` | Scans original Unicode codepoints: starts at a letter, includes subsequent letters/marks and internal straight/curly apostrophes; yields NFC/casefolded tokens with original half-open offsets. No stemming, stop words or corpus/UI knowledge. Artifact methods bind this policy. | E-W/E-S/E-T/E-U; W, S, T |
| `word_inputs.py` | `CoreProvider`, `FileProvider`, typed refusal and scope validation; 64 MiB stable regular UTF-8 file reads preserve BOM/CRLF; CORE adapter lazily imports corpus selection helpers. Produces ephemeral rows with text, masks, bindings, spans and freshness callback. Does not serialize or persist text. | E-W/E-S/E-T/E-U; W, S, T, U |
| `corpus_inputs.py` | Reloads and compares verified snapshots, requires permanent corpus identity, builds provenance binding, applies Hegel-main-text/type/review/reader-path eligibility and masks only exact converter-generated trailing facsimile labels. These are analysis-specific selection rules over CORE data. | CORE branch of word/sentence providers and v1 sentences; W, S |
| `validation.py` | Shared finite JSON, field/integer and binding validation plus the historically named `TermExperimentError`. Still live through corpus/sentence helpers although the term command was removed. No IO/CORE/UI import. | E-S and corpus-provider guards; W, S indirectly |
| `words.py` | Counts included whole tokens per input row and union vocabulary; computes rates with explicit denominators; records count plus first occurrence offsets per row. Strict schema, deterministic encoding, bounded 16 MiB receipts and exact recomputation. No source text, full token sequence, persistence or UI in artifacts. | E-W/E-T/E-U and Python API; W, T, U |
| `comparison.py` | Recomputes the word study before deriving per-10,000 rate difference and unsmoothed log2 ratio. Explicit undefined statuses for zero denominators/counts; CSV/TSV includes provenance and study digest. Returns strings/data, writes no files, makes no significance claim. | E-W words-export and E-U reference comparison; W, U |
| `sentences.py` | Deterministic punctuation segmentation and descriptive token-length/position/histogram/longest-sentence statistics. Retains v1 snapshot artifacts and delegates provider v2 to `sentence_inputs`. Decodes/checks both; optional owner-only non-overwriting saved-study writer is colocated with computation. Stale docstrings mention the retired term/reader-S workflows. | E-S/E-U and Python API; S, U |
| `sentence_inputs.py` | Reuses word providers; segments full original rows first and admits only complete sentences inside scope, retaining original offsets. Builds/validates/checks v2 receipts and origin bindings. File row is one statistical input, not inferred paragraphs. Lazy reciprocal imports with `sentences` preserve the two API versions. | E-S/E-U via sentences; S |
| `tfidf.py` | Derives raw-TF × smoothed natural-log IDF, L2 per document over all terms, then top-N, with mean document weights overall. One provider row is one document, including empty rows in N. Embeds the complete word receipt and reuses private word validators; no ML library or independent source-loading path. | E-T/E-U and Python API; T, U |
| `prose.py` | Builds an explicit derived prose export: CommonMark/HTML headings and images excluded from features; canonical ancestry, attribution and source metadata retained by copy. Eligibility uses canonical parent graph, not a required reader path. Reloads/compares snapshot and checks freshness before release. This export intentionally includes prose text. | E-P and Python API; P, A |
| `encyclopedia.py` | Reads fresh bundled catalog via `importlib.resources`; renders attributed excerpt separately from SOL note; turns dated parent graph into genealogy rows. Does not run cataloged methods, import CORE or use network. | E-U Encyclopedia/Genealogy; M, U, B |
| `methods.py` | Loads fresh runnable-method descriptions and renders inputs/settings/outputs/limits/CLI examples. Catalog data describes commands rather than dispatching them. | E-U Methods; M, U, B |
| `tui/__init__.py` | Optional Textual availability probe and installation hint, importable by reader without importing Textual itself. | E-U reader preflight; U, B |
| `tui/__main__.py` | Parses context/theme arguments, checks optional dependency, reads context, then lazily starts app. Imports reader option constants, a real dependency back into BEING configuration. | E-U subprocess or explicit module command; U |
| `tui/context.py` | Creates private owner-only bounded context files containing reference/cursor/selection/heading/corpus/state destination; validates context shape and reads regular files with final-symlink refusal. Saves investigation state atomically and tolerates unreadable saved state. Shape validation is separate from CORE reference verification in study adapters. | E-U reader and app; U and `test_neovim_reader.py` |
| `tui/app.py` | Textual Encyclopedia/Methods/Experiment/Results, worker ordering, provider forms, tables, occurrence context and source-opening messages. Adapters perform computation; app controls resizing, theme following and UI state (screen/origin) on leave. Imports reader theme default; rich/Textual are presentation dependencies here. | E-U; U, M |
| `tui/words.py` | Lazily locates engines, maps UI targets/reference choices to providers, derives table/summary/source rows, re-reads verified text for occurrence context and original offsets, emits reader source descriptors only for CORE. Saves receipts/export beside studies exclusively, owner-only; does not write workspace tables. | E-U word and shared adapter helpers; U, W indirectly |
| `tui/sentences.py` | Calls v2 engine using shared UI providers, derives histogram/longest rows, uses verified study-time text for display beginnings, creates CORE source descriptors, saves text-free receipts through shared exclusive writer. No Textual classes. | E-U sentence study; U, S indirectly |
| `tui/tfidf.py` | Uses shared UI providers and TF-IDF API, derives ranking/summary/source rows and saves receipts through shared writer. Passage labels are ephemeral display data. No Textual classes. | E-U ranking; U, T indirectly |

Resource companions, also in scope:

| File | Role and protection |
| --- | --- |
| `encyclopedia.json` | Offline attributed excerpts, SOL notes, reading links and genealogy metadata; loaded only by `encyclopedia.py`. M checks attribution, bounded quotes, dates/sources, parent graph and distinction between topics and runnable methods; B checks packaged resources. |
| `methods.json` | Six runnable method entries with examples, method parameters and limits; loaded by `methods.py`. M parses examples against CLI and checks catalog links, complete rendering and fresh loads; B checks packaged resources. |

## 4. Corpus modules: canonical service and maintenance are distinct

Paths are relative to `sol/corpus/`. Normal indexed reading never needs to run
PDF extraction. Some old module descriptions still mention legacy PDF reading;
that route was removed before this baseline.

| Module | Actual work and present boundary | Routes; protecting tests |
| --- | --- | --- |
| `__init__.py` | Docstring-only package marker; no automatic conversion or indexing. Python submodule imports pass through it; it is not a service facade. | C/R/E; B (import boundaries) |
| `errors.py` | Defines shared `CorpusError`, separating renderer/contract errors without loading parsing or conversion machinery. | Canonical/projection failures; K, P and reader typography integration |
| `markdown.py` | Lazy CommonMark tokenizer, visible HTML and token-to-plain-text semantics. Omits SOL note callouts while retaining math superscripts/code; optional heading/image exclusions for analysis. Shared by canonical indexing, prose and reader typography; parsing imports markdown-it only on use. | C-V/C-K, E-P and R typography; K, P, `test_reader_typography.py` |
| `contract.py` | Canonical marker parsing/rendering, UUID allocation, manifest/relationship/source inventory validation; index regeneration with atomic writes/lock; exact-byte/hash verification and detached `CorpusSnapshot`; explicit lineage initialization. It contains both read-only trust operations and maintenance writes. Snapshot collections remain caller-owned mutable data. Existing verified index loading requires neither PDF nor Markdown parser. | C-K, C-V index and all CORE consumers; K, B, reader/workspace/analysis integrations |
| `edition.py` | Audited Cambridge outline, anchors, page mappings and `Node` tree constants; default PDF discovery. Edition-specific import evidence, not authoritative runtime IDs. Still imported by reader app/render for constants/convenience tree, so not exclusively an isolated converter dependency. | C-V, onboarding, R constants/render; V, R tests (`test_terminal.py`) |
| `layout.py` | Runs `pdftotext -bbox-layout`, constructs word/line/page geometry, normalizes heading comparisons and verifies anchors to construct a fresh abbreviated tree. No canonical UUIDs. Uses core `Node`/`Passage`; currently reached through structure conversion, not ordinary reading. | C-V via structure; V (structure tests, real-PDF subset conditional) |
| `structure.py` | Uses layout geometry and audited edition constants to build exact verified edition hierarchy, captions/source spans/parents, expected heading counts and temporary audit IDs. Explicitly edition-specific; does not infer permanent IDs or generic logical placement. | C-V converter; V |
| `notes.py` | Geometry/font/marker-based note segmentation, nested/continuing/orphan notes and callout evidence. Accounts for every incoming source span once; avoids mistaking math powers for notes. No permanent identities. | C-V Importer; V |
| `references.py` | Segments physical bibliography and subject-index spans, preserving hanging indents/column/page continuations and warnings. Not `sol.core.references`: these are reference-book entries, not portable record resolution. | C-V Importer; V |
| `convert.py` | CLI plus audited Poppler `pdftohtml` importer: glyph/style/line normalization, source allocation, heading/note/reference graph, facsimile images via `pdftoppm`, canonical IDs/Markdown/manifest/index publication. Existing output refused and private staging/output checked for Git exclusion. Separately dispatches index/extract/normalize/ingest lazily. | C-V/C-X and explicit first run; V, X, B |
| `backends/__init__.py` | Docstring-only extraction backend namespace; importing it does not load SDK. | C-X; X |
| `backends/opendataloader.py` | Lazy local pinned SDK execution, Java/tool preconditions, fresh private output directory, source fingerprint stability and strict engine JSON/provenance validation. Produces physical evidence, never canonical identities; no remote/fallback engine. | C-X extract only; X |
| `extraction.py` | Normalizes nested physical output into validated candidate artifacts with positional selectors, exact source/engine provenance and retained raw data. Private exclusive artifact publication; stable regular reads and tamper checking. Normalizing external JSON hashes PDF but does not authenticate supplied engine/version; no hierarchy/attribution/UUID guesses. | C-X extract/normalize; X |
| `ingest.py` | Validates exhaustive explicit human-review dispositions against candidate digest and baseline, permits only approved existing-record Markdown changes, preserves metadata/note links/IDs. Copies declared docs/assets to private sibling staging, reindexes/verifies, atomically publishes a new directory without clobber. Uses platform no-replace primitives; refuses unsupported publication. Does not overwrite baseline or touch personal workspaces/PDF. | C-X ingest; I, X |

## 5. CORE modules: actual public surface and backing services

Paths are relative to `sol/core/`.

| Module | Actual work and present boundary | Routes; protecting tests |
| --- | --- | --- |
| `__init__.py` | Lazy version-1 Python API forwarding to models/paths/references/protocol/config/corpus **and corpus contract**. Import alone does not open files or load applications. This public surface crosses the physical `core/` directory boundary. | R/E/public Python consumers; B, R, K |
| `models.py` | `Node`, frozen `Passage`, mutable `Book`, subtree selection, ID/redirect/prefix lookup, literal Unicode search and facsimile-label presentation. Models are interface-independent but carry edition/reader-shaped paths/pages. Frozen passage does not freeze its referenced node or the book/snapshot graph. | R, converter edition/layout, UI labels; R |
| `paths.py` | Pure virtual-tree path resolution/aliases, dot/parent traversal, ambiguity refusal and path display. No host filesystem operations or hard-coded edition root. | R, E-U labels/scopes, timings; R |
| `corpus.py` | Loads verified canonical snapshot and constructs Hegel-main-text three-doctrine `Book` view from explicit `reader_path`; preserves full canonical graph alongside it. Seeds protocol's verified cache immediately after load. No PDF/conversion/UI dependency, but convenience projection assumes specific author, Arabic main-text page labels and doctrine roots. | R and `save_corpus`; R, K, B |
| `config.py` | XDG config JSON, atomic corpus/theme settings, discovery precedence: explicit → environment → cwd local-corpus → saved → local-install/source-checkout fallback. Validates corpus before save, never silently substitutes broken explicit/saved choice. Theme names supplied by reader. Local-project recognition uses fixed package path and project identity: moving this file affects discovery, not merely imports. | R configuration/discovery, E CORE CLI; R, B |
| `references.py` | Resolves exact/unambiguous-prefix and redirected canonical record identities, retaining requested and resolved IDs/chain; supports full graph and reader view. No similarity inference or UI/workspace knowledge. Returns record data, not navigation authority. | R/E portable references and workspace/source consumers; R, Q |
| `protocol.py` | Strict bounded version-1 JSON reference encode/decode, capture/check and bounded batches, canonical generation/content/source fingerprints and redirect agreement. Lazily imports contract on verified operations. Private verified-generation representation and `single_action` comparison reuse retain disk freshness checks; batches release only after final check. No packet-selected filesystem path/actor/workspace/execution. | `sol ref`, reader surfaces/source opening, E anchors; Q, B and guarded reader integrations |
| `wire.py` | Stable bounded regular-file or piped-stdin input; rejects terminal stdin, special files, final symlinks, replacement/change races, byte-limit overflow. Returns undecoded bytes/text without interpreting protocol or discovering corpus. | `sol ref` and legacy sentence origin input via essence CLI; Q |

Shared persistent research state is an intended CORE responsibility in
SPECULATIVE §4.1, but its existing storage/services are physically in
`sol/workspace/`, outside this inventory's module scope and inside Claude's
parallel boundary work. CORE here does **not** currently own or import a workspace
store. ESSENCE's saved study artifacts and `investigation.json` are another
persistence path, not rows in that shared workspace schema.

## 6. Scripts: engineering infrastructure with product dependencies

| Module | Actual work and present boundary | Routes; protecting tests |
| --- | --- | --- |
| `scripts/check_docs.py` | CommonMark local links/images/heading and explicit anchors, symlink/outside-root refusal and exact leading-document set. At this baseline expects four authorities; PR #86 changes that policy separately. Resolves GitHub main/HEAD links locally; does not network-check external or pinned-commit URLs. CLI with `--root`; no application imports. | D and CI `.github/workflows/tests.yml`; actual docs check (no dedicated test module at baseline) |
| `scripts/install.py` | Explicit checkout installer: prerequisite plan, consent, native Debian/Ubuntu packages, managed checksum-pinned Neovim archive with traversal/link/device checks, pipx install/ensurepath and refusal to replace unrelated console commands. Imports runtime's managed-editor location/version. `--check` is read-only; ordinary install can change user/system state. | D; D tests |
| `scripts/reader_timings.py` | Invented corpus by default, optional explicit read-only corpus. Measures snapshot/book/verification/projection/typography and controller operations with temporary workspaces and terminal boundary replaced; optional early-dispatch fresh subprocess measures import-to-first-payload plus process wall time. Creates temporary state; not physical rendering/key latency, and overlapping stage timings cannot be added. | D, internal `--_startup-worker` subprocess; D tests |

## 7. Test protection map and limits

These are existing tests to preserve with each group, not new tests or claims of
line coverage. Names are under `tests/`; the AST appendix supplies direct imports,
while this map also follows lazy facade and subprocess use.

| Code | Existing tests and behavior protected |
| --- | --- |
| A | `test_analysis_cli.py`: prose input metadata, cross-process read-only words/check, early retired-artifact refusal, early essence dispatch and removed namespace/command refusal. |
| W | `test_word_frequencies.py`: Unicode/token offsets, denominators, scopes, BOM/CRLF, stable bounded file reads, in-memory/disk freshness including unselected text, exclusions/masks, mixed inputs, deterministic strict receipts, explicit-source CLI/check. `test_word_comparison.py`: formula direction, unequal denominators, swapping sides, undefined ratios, verified CSV/TSV/provenance and stale/tampered refusals. Both include fresh-process file-only import blockers. |
| S | `test_sentence_study.py`: segmentation, exclusions, statistics, v1 scope/check/CLI. Four `KnownRuleLimitations` remain **expected failures** (mid-sentence parenthesis, physical line break, ending abbreviation, lowercase start); passing suite does not establish linguistic accuracy. `test_sentence_providers.py`: v2 full-sentence scope containment, original Unicode/BOM/CRLF offsets, file/CORE guards, strict receipts, origins, byte limits, file-only imports and four byte-for-byte original v1 receipt fixtures. |
| T | `test_tfidf.py`: exact IDF/L2/overall weights, full vocabulary before truncation, empty documents in N, original providers/scopes, strict/tampered/oversize/stale results, CLI/check and file-only import isolation. |
| P | `test_prose_inputs.py`: CommonMark/HTML heading/image removal without deleting prose words, canonical ancestry and metadata separation, review/generated/editorial exclusions, fresh detached export and refusal of changed/mutated snapshots. Also K's canonical projection and A's subprocess export. |
| M | `test_methods.py`, `test_encyclopedia.py`: catalog schema, attributed quotations/omission metadata, dated genealogy/parents and topic-vs-runnable distinction; six runnable entries/examples parsed by CLI; render completeness and fresh copies. Includes Textual browse/read/return/genealogy pilots when available. |
| U | `test_essence_tui.py`: private context/state, adapter providers/counts, stale inputs, lazy missing engine handling, saved artifacts/exports, sources/original offsets and reader navigation descriptors, out-of-order worker results, theme changes, all study modes and resize at 80×24/120×40 with long words/undefined cells. `test_neovim_reader.py` covers the host's context/return boundary; actual source-navigation guards also involve reader controller tests. These are automated pilots, not manual UX acceptance. |
| K | `test_corpus_contract.py`, `test_corpus_identity.py`: marker/UUID/relationship/source coverage, canonical Markdown projection, redirects, exact-byte freshness, traversal/symlinks, changed/tampered indexes, parser-free verified loads, explicit/idempotent identity initialization, concurrent edits/locks and interrupted publication fail-closed behavior. |
| V | `test_corpus_conversion.py`: glyph/style/line handling, note graph/attribution, reference section order and private/no-clobber output. `test_corpus_structure.py`: audited counts, hierarchy/captions/source spans and optional local-PDF checks. `test_corpus_notes.py`: nested/orphan/continued notes, math powers and one-time source accounting. `test_corpus_references.py`: hanging indents, old-style digits, columns/continuations and duplicate-span refusal. Layout/edition are covered through these callers; no dedicated `test_layout.py`/`test_edition.py`. |
| X | `test_opendataloader_backend.py`: SDK preconditions/local-only execution, fresh directory/source/JSON validation. `test_extraction_artifacts.py`: exact physical evidence/selectors, strict/tampered JSON, provenance, stable/private/exclusive writes, races and Git exclusion; normalization without SDK. `test_extraction_cli.py`: parser/help, explicit arguments, dispatch and controlled failure; B also blocks extraction imports for help. Engine mocks are not a new real-engine acceptance run. |
| I | `test_corpus_ingestion.py`: exhaustive review/selectors, PDF fingerprint agreement, approved-only Markdown and metadata/ID/note preservation, private exact copies and source/output races, symlink/traversal/Git exclusion, atomic no-replace publication and unsupported-platform refusal. |
| R | `test_core_api.py`, `test_core_models.py`, `test_core_config.py`, `test_corpus_reader.py`: lazy export identity/import safety, lookup/search/redirect/path semantics, Hegel reader projection, config/discovery/atomic saves. `test_package_boundaries.py`, `test_source_discovery.py`, `test_first_run.py`, `test_read_paths.py`, reader action/surface tests also exercise consumers; `test_terminal.py` covers edition path/PDF conveniences. |
| Q | `test_core_protocol.py`: strict shape/version/size/depth/types, capture/check/current generation, redirect/full canonical record agreement, detached records, batch final checks and comparison/cache guards. `test_reference_cli.py`: explicit local binding and controlled transport refusals. `test_wire_input.py`: byte-vs-character limits, regular/stable file input, interactive stdin/symlink/FIFO refusal. Reader surface/export/source and workspace tests protect downstream use too. |
| B | `test_package_boundaries.py`, `test_packaging.py`: no eager reader/PDF/optional UI imports, wheel/sdist resources/entry points, core-only wheel and installed offline methods/headless study behavior, no private sentinels in artifacts. Dynamic code strings in these tests do not appear as imports in the AST appendix. |
| D | `test_install.py`: read-only check/decline, existing tools, unrelated-command refusal, Java version and archive traversal/device/link checks. `test_reader_timings.py`: operations/repeats, explicit corpus unchanged, temporary state cleanup, fresh startup isolation, lazy shell imports and invalid-input refusals. |

## 8. Cohesive groups and questions for Stage C

The following are technical change units to consider together in any later
relocation. They do not assign a logical determination or require that every
file in a group end up in a single directory.

| Cohesive group | Coupling and positive content to preserve | Open question for primary-text reading and subsequent proposal |
| --- | --- | --- |
| Tokenization, providers, word engine and receipts | `tokenization`, `word_inputs`, `corpus_inputs`, `words`, shared validators; original offsets, eligibility/masks and method/version bindings form a reproducibility contract. | How should the reading distinguish determining a unit, admitting an input and measuring it? Does that distinction illuminate the current abstractions without splitting inseparable offset/provenance rules? |
| Word comparison and TF-IDF | `comparison` and `tfidf` consume complete word receipts; private word validators and provider rows are shared implementation interfaces. | What is the relation between the counted unit and its comparison/weighting? Establish textual determinations and neighbors before proposing separation; do not classify by the names “frequency” or “ratio.” |
| Sentence segmentation and measurement | `sentences`, `sentence_inputs`, `validation`, tokenizer/providers, v1 fixtures and v2 adapters. Reciprocal local imports and two receipt shapes must survive together. | Is segmentation's boundary-making the same operation as counting its products? Which existing distinctions should survive any regrouping, including acknowledged rule failures? |
| Prose and canonical visibility | `prose` with `corpus.markdown`/`errors`, canonical renderer tests and reader typography consumers. Analysis options must not silently change canonical visible text. | How does the deliberate exclusion of structural text relate to retaining it as metadata? Read before deciding whether a shared projection and an experiment-specific policy belong together. |
| Verified canonical generation and references | `contract`, CORE facade/corpus/protocol/references/models; disk hashes, mutable caller snapshots, cache seeding, action context and final batch checks are one trust path. | Distinguish corpus identity, current generation, reference agreement and reader projection. Which are shared services under SPECULATIVE's practical CORE exception, and where does edition-specific interpretation begin? |
| Edition-bound conversion | `edition`, `layout`, `structure`, `notes`, corpus `references`, `convert`; geometry, source accounting and permanent identity allocation are different stages. Reader app/render still import edition constants. | What belongs to source organization versus a computation interpreting source evidence? Preserve the audited importer content; determine whether exposing its convenience outline to the reader is a boundary tension. |
| Extraction, review, ingestion | backend, `extraction`, `ingest`, contract writer and corpus CLI; immutable physical evidence, caller-declared review and new-copy publication must stay distinguishable. | When does evidence become an accepted canonical correction? Do not equate human review with authentication or move interpretation into CORE simply because its output is a corpus. |
| Headless adapters | essence `cli`, `word_cli`, `sentence_cli`, `tfidf_cli`; shared flags/dispatch/safe output and explicit-source checks, including local import cycles. | Separate experiment intent from source resolution without weakening artifact refusal-before-access. Which current coupling is necessary and which is only adapter reuse? |
| Optional UI and reader exchange | `tui` app/context/adapters, host `neovim_reader`, `neovim_essence.lua`, theme constants and emitted source packet. Occurrence text is ephemeral; checked identity/offsets cross the process boundary. | What belongs to investigation, presentation, reader encounter and shared state? Reader-independent engines already exist; interface/theme dependencies should be acknowledged rather than calling all of ESSENCE independent. |
| Catalogs and offline packaging | `encyclopedia.py/json`, `methods.py/json`, UI browsers and package-data declarations. Reading topics must not imply implemented adapters. | Is explaining a method the same responsibility as executing it? Preserve attributed evidence and runnable-vs-reading distinction in any later interpretation. |
| Persistence and local preferences | CORE config, ESSENCE artifact writers/context state and external workspace services; these currently have separate owners and failure rules. | How should shared research state serve transitions without a UI owning corpus/state? Coordinate with Claude's inventory; do not invent a schema migration or conflate investigation screen state with research receipts. |
| Development tools | All three scripts, CI/docs policy, installer runtime constants and timing consumers. | SPECULATIVE §6 currently exempts ordinary infrastructure. Keep its dependencies visible; no deeper philosophical placement follows from a tool's use of analysis or reader code. |

Stage C must retrieve the primary CORE edition and identify edition plus stable
logical location, read neighboring transitions, distinguish text from
interpretation and record rationale/alternatives. This inventory supplies code
facts for that work; it does not claim the relevant passages have already been
read or that module names provide textual grounds. Particular unresolved limits:

- Analysis CORE eligibility currently requires Hegel/main-text and reader paths;
  prose export uses a different canonical-ancestry policy. Hierarchical/composable
  author/book/multi-corpus scopes in SPECULATIVE §4 are intentions, not today's
  generalized provider implementation.
- A file is one provider row for TF-IDF and sentence position statistics. Relocating
  code must not silently turn rows into paragraphs or change denominator policy.
- CORE has a practical service boundary but substantial reader/edition-shaped
  projection. `sol/corpus/` is not homogeneous with that runtime boundary.
- `sentences.save_sentence_result`, UI writers and context/state handling mix
  persistence into different layers; no consolidation is proposed here.
- Dynamic imports, literal patch targets, package-data declarations, subprocess
  module commands and fixed `__file__` layout checks need explicit migration
  review in addition to ordinary import rewrites.

## 9. Mechanical import and reverse-import ledger

**Scope:** all repository `sol/**/*.py`, `scripts/*.py`, `tests/*.py` at the
baseline. Each row is one module (including initializers); `tests.*` names map
to same-named files under `tests/`. “Imports” includes standard library and
third-party module names exactly at the import-from base, with relative imports
resolved. A `from package import submodule` also produces a reverse edge for the
known submodule. Package-base edges are included, so importing a package's
submodule may also list its initializer. These are syntactic references, including
function-local imports, not a chronological runtime load graph or transitive
caller closure. `__future__` is retained as syntax, not a runtime dependency.

| Module | Imports (AST) | Direct product/script importers (AST) | Direct test/fixture importers (AST) |
| --- | --- | --- | --- |
| `scripts.check_docs` | `__future__`, `argparse`, `html`, `markdown_it`, `pathlib`, `re`, `urllib.parse` | — | — |
| `scripts.install` | `__future__`, `argparse`, `hashlib`, `os`, `pathlib`, `platform`, `re`, `shutil`, `sol.terminal.runtime`, `subprocess`, `sys`, `tarfile`, `tempfile`, `urllib.request` | — | `tests.test_install` |
| `scripts.reader_timings` | `__future__`, `argparse`, `collections`, `contextlib`, `json`, `os`, `pathlib`, `platform`, `sol`, `sol.core.paths`, `sol.corpus`, `sol.reader`, `sol.reader.actions`, `sol.reader.render`, `sol.reader.surface`, `sol.reader.typography`, `sol.terminal`, `sol.workspace.reader`, `sol.workspace.store`, `statistics`, `subprocess`, `sys`, `tempfile`, `time`, `unittest.mock`, `uuid` | — | `tests.test_reader_timings` |
| `sol.core` | `importlib` | `scripts.reader_timings`, `sol.corpus.ingest`, `sol.essence.cli`, `sol.essence.corpus_inputs`, `sol.essence.prose`, `sol.essence.sentence_cli`, `sol.essence.sentence_inputs`, `sol.essence.sentences`, `sol.essence.tui.sentences`, `sol.essence.tui.tfidf`, `sol.essence.tui.words`, `sol.essence.word_cli`, `sol.reader.actions`, `sol.terminal.reference` | `tests.fixtures_corpus`, `tests.test_core_api`, `tests.test_core_config`, `tests.test_core_models`, `tests.test_core_protocol`, `tests.test_corpus_reader`, `tests.test_essence_tui`, `tests.test_footnote_view`, `tests.test_neovim_reader`, `tests.test_package_boundaries`, `tests.test_prose_inputs`, `tests.test_reader_efficiency`, `tests.test_reader_surface_export_guards`, `tests.test_reader_surface_neovim_host`, `tests.test_reader_theme`, `tests.test_reference_cli`, `tests.test_sentence_providers`, `tests.test_sentence_study`, `tests.test_word_frequencies` |
| `sol.core.config` | `__future__`, `importlib`, `json`, `os`, `pathlib`, `re`, `shlex`, `sol.core.corpus`, `tempfile`, `urllib.parse` | `sol.reader.app`, `sol.reader.onboarding`, `sol.terminal.commands`, `sol.terminal.neovim` | `tests.test_core_config`, `tests.test_corpus_reader`, `tests.test_first_run`, `tests.test_package_boundaries`, `tests.test_reader_theme`, `tests.test_source_discovery` |
| `sol.core.corpus` | `__future__`, `pathlib`, `re`, `shlex`, `sol.core.models`, `sol.core.protocol`, `sol.corpus.contract`, `sys` | `sol.core.config`, `sol.reader.app`, `sol.reader.onboarding`, `sol.terminal.commands` | `tests.fixtures_corpus`, `tests.test_reader_surface_neovim` |
| `sol.core.models` | `__future__`, `dataclasses`, `pathlib`, `re`, `unicodedata` | `sol.core.corpus`, `sol.core.paths`, `sol.corpus.edition`, `sol.corpus.layout`, `sol.reader.actions`, `sol.reader.app`, `sol.reader.launch`, `sol.reader.render`, `sol.reader.shell`, `sol.reader.structure`, `sol.reader.surface` | `tests.test_core_api`, `tests.test_core_models`, `tests.test_reader_actions`, `tests.test_reader_efficiency`, `tests.test_reader_search_projection`, `tests.test_terminal_text` |
| `sol.core.paths` | `__future__`, `re`, `sol.core.models` | `scripts.reader_timings`, `sol.essence.tui.words`, `sol.reader.actions`, `sol.reader.app`, `sol.reader.render`, `sol.reader.shell`, `sol.reader.structure`, `sol.terminal.commands` | `tests.test_core_models`, `tests.test_footnote_view`, `tests.test_neovim_reader`, `tests.test_neovim_reader_alacritty`, `tests.test_reader_actions`, `tests.test_reader_context`, `tests.test_reader_search_actions` |
| `sol.core.protocol` | `__future__`, `contextlib`, `contextvars`, `copy`, `dataclasses`, `hashlib`, `json`, `math`, `re`, `sol.core.references`, `sol.corpus.contract`, `uuid` | `sol.core.corpus`, `sol.reader.surface`, `sol.terminal.neovim_reader` | `tests.test_core_protocol` |
| `sol.core.references` | `__future__`, `dataclasses` | `sol.core.protocol`, `sol.reader.actions`, `sol.reader.surface`, `sol.terminal.source`, `sol.workspace.diagnostics`, `sol.workspace.reader` | `tests.test_core_api`, `tests.test_core_models`, `tests.test_reader_flow_actions`, `tests.test_reader_search_actions` |
| `sol.core.wire` | `__future__`, `os`, `pathlib`, `stat`, `sys` | `sol.essence.cli`, `sol.terminal.reference` | `tests.test_wire_input` |
| `sol.corpus` | — | `scripts.reader_timings`, `sol.corpus.ingest`, `sol.corpus.structure` | `tests.fixtures_corpus`, `tests.fixtures_footnotes`, `tests.test_analysis_cli`, `tests.test_core_api`, `tests.test_core_protocol`, `tests.test_corpus_ingestion`, `tests.test_essence_tui`, `tests.test_extraction_artifacts`, `tests.test_extraction_cli`, `tests.test_first_run`, `tests.test_prose_inputs`, `tests.test_reader_surface_neovim`, `tests.test_reader_theme`, `tests.test_reader_view_cli`, `tests.test_reference_cli`, `tests.test_sentence_providers`, `tests.test_sentence_study` |
| `sol.corpus.backends` | — | — | `tests.test_extraction_artifacts`, `tests.test_opendataloader_backend` |
| `sol.corpus.backends.opendataloader` | `__future__`, `contextlib`, `hashlib`, `importlib`, `io`, `json`, `math`, `os`, `pathlib`, `re`, `shutil` | `sol.corpus.extraction` | `tests.test_extraction_artifacts`, `tests.test_opendataloader_backend` |
| `sol.corpus.contract` | `__future__`, `argparse`, `contextlib`, `dataclasses`, `hashlib`, `html.parser`, `json`, `math`, `os`, `pathlib`, `re`, `sol.corpus.errors`, `sol.corpus.markdown`, `tempfile`, `typing`, `urllib.parse`, `uuid` | `scripts.reader_timings`, `sol.core.corpus`, `sol.core.protocol`, `sol.corpus.convert`, `sol.corpus.extraction`, `sol.corpus.ingest`, `sol.reader.surface`, `sol.terminal.source`, `sol.workspace.reader` | `tests.fixtures_corpus`, `tests.fixtures_footnotes`, `tests.test_analysis_cli`, `tests.test_core_api`, `tests.test_core_protocol`, `tests.test_corpus_contract`, `tests.test_corpus_conversion`, `tests.test_corpus_identity`, `tests.test_corpus_ingestion`, `tests.test_corpus_reader`, `tests.test_essence_tui`, `tests.test_first_run`, `tests.test_packaging`, `tests.test_prose_inputs`, `tests.test_reader_surface_neovim`, `tests.test_reader_theme`, `tests.test_reader_typography`, `tests.test_reader_view_cli`, `tests.test_reference_cli`, `tests.test_sentence_providers`, `tests.test_sentence_study`, `tests.test_source_viewer` |
| `sol.corpus.convert` | `__future__`, `argparse`, `collections`, `hashlib`, `json`, `os`, `pathlib`, `re`, `sol.corpus.contract`, `sol.corpus.edition`, `sol.corpus.extraction`, `sol.corpus.ingest`, `sol.corpus.notes`, `sol.corpus.references`, `sol.corpus.structure`, `subprocess`, `tempfile`, `unicodedata`, `xml.etree.ElementTree` | `sol.reader.onboarding` | `tests.test_corpus_conversion`, `tests.test_extraction_cli` |
| `sol.corpus.edition` | `__future__`, `pathlib`, `sol.core.models` | `sol.corpus.convert`, `sol.corpus.layout`, `sol.reader.app`, `sol.reader.render` | `tests.test_terminal` |
| `sol.corpus.errors` | — | `sol.corpus.contract`, `sol.corpus.markdown`, `sol.reader.typography` | — |
| `sol.corpus.extraction` | `__future__`, `hashlib`, `json`, `math`, `os`, `pathlib`, `re`, `secrets`, `sol.corpus.backends.opendataloader`, `sol.corpus.contract`, `stat`, `subprocess`, `tempfile` | `sol.corpus.convert`, `sol.corpus.ingest` | `tests.test_corpus_ingestion`, `tests.test_extraction_artifacts` |
| `sol.corpus.ingest` | `__future__`, `collections`, `ctypes`, `errno`, `hashlib`, `html.parser`, `json`, `os`, `pathlib`, `re`, `shutil`, `sol.core`, `sol.corpus`, `sol.corpus.extraction`, `stat`, `subprocess`, `sys`, `tempfile` | `sol.corpus.convert` | `tests.test_corpus_ingestion` |
| `sol.corpus.layout` | `__future__`, `collections`, `copy`, `dataclasses`, `functools`, `pathlib`, `re`, `shutil`, `sol.core.models`, `sol.corpus.edition`, `statistics`, `subprocess`, `unicodedata`, `xml.etree.ElementTree` | `sol.corpus.structure` | — |
| `sol.corpus.markdown` | `__future__`, `html.parser`, `markdown_it`, `re`, `sol.corpus.errors` | `sol.corpus.contract`, `sol.essence.prose`, `sol.reader.typography` | `tests.test_prose_inputs`, `tests.test_reader_typography` |
| `sol.corpus.notes` | `collections`, `re` | `sol.corpus.convert` | `tests.test_corpus_conversion`, `tests.test_corpus_notes` |
| `sol.corpus.references` | `__future__`, `collections`, `re`, `unicodedata` | `sol.corpus.convert` | `tests.test_corpus_references` |
| `sol.corpus.structure` | `__future__`, `collections`, `pathlib`, `re`, `sol.corpus`, `typing` | `sol.corpus.convert` | `tests.test_corpus_structure` |
| `sol.essence` | `importlib` | `sol.essence.cli`, `sol.essence.tui.sentences`, `sol.essence.tui.tfidf`, `sol.essence.tui.words` | `tests.test_analysis_cli`, `tests.test_essence_tui`, `tests.test_prose_inputs`, `tests.test_sentence_providers`, `tests.test_tfidf`, `tests.test_word_comparison`, `tests.test_word_frequencies` |
| `sol.essence.cli` | `__future__`, `argparse`, `json`, `pathlib`, `sol.core`, `sol.core.wire`, `sol.essence`, `sol.essence.prose`, `sol.essence.sentence_cli`, `sol.essence.sentences`, `sol.essence.tfidf`, `sol.essence.tfidf_cli`, `sol.essence.word_cli`, `sol.essence.words`, `sys`, `unicodedata` | `sol.essence.sentence_cli`, `sol.essence.tfidf_cli`, `sol.essence.word_cli`, `sol.reader.app` | `tests.test_analysis_cli`, `tests.test_methods`, `tests.test_sentence_providers`, `tests.test_tfidf`, `tests.test_word_comparison`, `tests.test_word_frequencies` |
| `sol.essence.comparison` | `__future__`, `csv`, `hashlib`, `io`, `json`, `math`, `sol.essence.word_inputs`, `sol.essence.words` | `sol.essence.tui.words`, `sol.essence.word_cli` | `tests.test_word_comparison` |
| `sol.essence.corpus_inputs` | `hashlib`, `posixpath`, `re`, `sol`, `sol.essence.validation` | `sol.essence.sentences`, `sol.essence.word_inputs` | — |
| `sol.essence.encyclopedia` | `importlib.resources`, `json` | `sol.essence.tui.app` | `tests.test_encyclopedia`, `tests.test_methods` |
| `sol.essence.methods` | `importlib.resources`, `json` | `sol.essence.tui.app` | `tests.test_methods` |
| `sol.essence.prose` | `__future__`, `copy`, `hashlib`, `json`, `sol`, `sol.corpus.markdown` | `sol.essence.cli` | `tests.test_prose_inputs` |
| `sol.essence.sentence_cli` | `__future__`, `sol.core`, `sol.essence.cli`, `sol.essence.sentences`, `sol.essence.word_cli`, `sol.essence.word_inputs` | `sol.essence.cli` | — |
| `sol.essence.sentence_inputs` | `__future__`, `json`, `re`, `sol`, `sol.essence.sentences`, `sol.essence.tokenization`, `sol.essence.validation`, `sol.essence.word_inputs`, `uuid` | `sol.essence.sentences` | — |
| `sol.essence.sentences` | `__future__`, `datetime`, `json`, `math`, `os`, `pathlib`, `re`, `sol`, `sol.essence.corpus_inputs`, `sol.essence.sentence_inputs`, `sol.essence.tokenization`, `sol.essence.validation`, `sol.essence.word_inputs`, `statistics`, `unicodedata` | `sol.essence.cli`, `sol.essence.sentence_cli`, `sol.essence.sentence_inputs`, `sol.essence.tui.sentences` | `tests.test_essence_tui`, `tests.test_sentence_providers`, `tests.test_sentence_study` |
| `sol.essence.tfidf` | `__future__`, `math`, `sol.essence.word_inputs`, `sol.essence.words` | `sol.essence.cli`, `sol.essence.tfidf_cli` | — |
| `sol.essence.tfidf_cli` | `sol.essence.cli`, `sol.essence.tfidf`, `sol.essence.word_cli`, `sol.essence.word_inputs` | `sol.essence.cli` | — |
| `sol.essence.tokenization` | `__future__`, `unicodedata` | `sol.essence.sentence_inputs`, `sol.essence.sentences`, `sol.essence.tui.words`, `sol.essence.words` | `tests.test_word_frequencies` |
| `sol.essence.tui` | `importlib.util` | `sol.essence.tui.__main__`, `sol.essence.tui.app`, `sol.essence.tui.sentences`, `sol.essence.tui.tfidf`, `sol.terminal.neovim_reader` | `tests.test_encyclopedia`, `tests.test_essence_tui` |
| `sol.essence.tui.__main__` | `__future__`, `argparse`, `sol.essence.tui`, `sol.essence.tui.app`, `sol.essence.tui.context`, `sol.reader.options`, `sys` | — | `tests.test_essence_tui` |
| `sol.essence.tui.app` | `__future__`, `base64`, `json`, `rich.text`, `sol.essence.encyclopedia`, `sol.essence.methods`, `sol.essence.tui`, `sol.essence.tui.context`, `sol.reader.options`, `textual`, `textual.app`, `textual.binding`, `textual.containers`, `textual.theme`, `textual.widgets`, `textual.widgets.option_list` | `sol.essence.tui.__main__` | `tests.test_encyclopedia`, `tests.test_essence_tui` |
| `sol.essence.tui.context` | `__future__`, `json`, `os`, `pathlib`, `stat` | `sol.essence.tui.__main__`, `sol.essence.tui.app`, `sol.terminal.neovim_reader` | `tests.test_essence_tui`, `tests.test_neovim_reader` |
| `sol.essence.tui.sentences` | `__future__`, `dataclasses`, `pathlib`, `sol`, `sol.essence`, `sol.essence.tui` | `sol.essence.tui.app` | `tests.test_essence_tui` |
| `sol.essence.tui.tfidf` | `dataclasses`, `pathlib`, `sol`, `sol.essence`, `sol.essence.tui` | `sol.essence.tui.app` | `tests.test_essence_tui` |
| `sol.essence.tui.words` | `__future__`, `dataclasses`, `datetime`, `hashlib`, `os`, `pathlib`, `sol`, `sol.core.paths`, `sol.essence`, `sol.essence.tokenization` | `sol.essence.tui.app`, `sol.essence.tui.sentences`, `sol.essence.tui.tfidf` | `tests.test_essence_tui` |
| `sol.essence.validation` | `__future__`, `json`, `math`, `re`, `uuid` | `sol.essence.corpus_inputs`, `sol.essence.sentence_inputs`, `sol.essence.sentences` | — |
| `sol.essence.word_cli` | `__future__`, `pathlib`, `sol`, `sol.essence.cli`, `sol.essence.comparison`, `sol.essence.word_inputs`, `sol.essence.words`, `sys` | `sol.essence.cli`, `sol.essence.sentence_cli`, `sol.essence.tfidf_cli` | `tests.test_word_frequencies` |
| `sol.essence.word_inputs` | `__future__`, `copy`, `dataclasses`, `hashlib`, `os`, `pathlib`, `sol.essence.corpus_inputs`, `stat`, `typing` | `sol.essence.comparison`, `sol.essence.sentence_cli`, `sol.essence.sentence_inputs`, `sol.essence.sentences`, `sol.essence.tfidf`, `sol.essence.tfidf_cli`, `sol.essence.tui.words`, `sol.essence.word_cli`, `sol.essence.words` | `tests.test_essence_tui`, `tests.test_word_frequencies` |
| `sol.essence.words` | `__future__`, `collections`, `json`, `math`, `re`, `sol.essence.tokenization`, `sol.essence.word_inputs`, `unicodedata`, `uuid` | `sol.essence.cli`, `sol.essence.comparison`, `sol.essence.tfidf`, `sol.essence.tui.words`, `sol.essence.word_cli` | — |

### Additional dependencies that syntax-only imports do not resolve

- **CORE lazy exports:** `core.__init__._EXPORTS` maps model names to
  `core.models`; path helpers to `core.paths`; `Reference`/resolvers to
  `core.references`; protocol version/limits/error/capture/check/encode/decode
  to `core.protocol`; `load_corpus_book` to `core.corpus`;
  `CorpusError`/`CorpusSnapshot`/`load_snapshot`/`verify_snapshot_current` to
  `corpus.contract`; discovery/save to `core.config`. The ledger records
  callers importing the facade; these symbol bindings identify the further
  dependency. `single_action` and `remember_verified` are direct protocol
  imports, not facade exports.
- **ESSENCE lazy exports:** `essence.__getattr__` maps prose names to `prose`,
  providers/error to `word_inputs`, word API to `words`, comparison API to
  `comparison`, sentence API to `sentences`, and TF-IDF API to `tfidf`.
  Thus facade-importing tests W/S/T/P protect implementations even when their
  direct reverse-import column is empty. `tui.words.engine` and
  `comparison_engine`, and `tui.sentences.engine`, instead lazily import
  implementation submodules via ordinary from-imports included in the ledger.
- **SDK:** `corpus.backends.opendataloader.extract_pdf` calls
  `importlib.import_module("opendataloader_pdf")` on explicit extraction only.
  The SDK and Java dependency are not ordinary AST import edges. Poppler, Git,
  pipx, installer sudo/apt and Neovim are subprocess/tool dependencies, not
  Python imports; routes and module descriptions above identify their owners.
- **Reader exchange:** `neovim_reader` builds the `-m sol.essence.tui` command;
  `neovim_essence.lua` consumes the app's `ESC ]5379;sol-essence;` base64 JSON
  source message. Lua loads and process commands are outside Python AST.
  Reader option theme constants are direct imports in `tui.app`/`__main__`.
- **Resources and installed routes:** `importlib.resources.files` accesses the
  two JSON catalogs; setuptools package-data includes both. `pyproject.toml`
  entry-point strings are not AST edges. `sol.__init__.cli` and `sol.__main__`
  reach reader dispatch before ESSENCE, not the other way round.
- **Tests and tooling:** fresh-process `-c` code strings/import blockers,
  `importlib.import_module` in packaging tests, literal patch targets, and
  source commands in CI/docs need the behavioral test map in §7. In particular,
  `scripts/check_docs.py` has no direct AST importer and is still run by CI.
  There are no other files in `scripts/` at this baseline.

## 10. Reproducing the mechanical ledger

Run this standard-library script from the repository root. It prints the same
four-column rows as §9, without opening a corpus or importing SOL. It deliberately
does not claim to resolve dynamic facade symbols, runtime reachability, Lua,
command strings or code embedded in test strings; those are inspected in §§2,
7 and 9. A dash means no syntactic reference found in this scan, not “unused.”

```python
import ast
from pathlib import Path

paths = sorted([
    *Path("sol").rglob("*.py"),
    *Path("scripts").glob("*.py"),
    *Path("tests").glob("*.py"),
])
modules = {
    p: str(p.with_suffix("")).replace("/", ".").removesuffix(".__init__")
    for p in paths
}
known = set(modules.values())
edges, imports = {}, {}
for path, module in modules.items():
    deps, names = set(), set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for item in node.names:
                names.add(item.name)
                deps.add(item.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = module.split(".")
                if path.name != "__init__.py":
                    package = package[:-1]
                base = ".".join(
                    package[:len(package) - node.level + 1]
                    + ([base] if base else [])
                )
            names.add(base)
            if base in known:
                deps.add(base)
            for item in node.names:
                child = base + "." + item.name
                if child in known:
                    deps.add(child)
    edges[module], imports[module] = deps, names


def cell(values):
    return ", ".join("`" + v + "`" for v in sorted(values)) or "—"


for path, module in modules.items():
    if not str(path).startswith(("sol/essence/", "sol/corpus/", "sol/core/", "scripts/")):
        continue
    reverse = [name for name, deps in edges.items() if module in deps]
    product = [name for name in reverse if not name.startswith("tests.")]
    tests = [name for name in reverse if name.startswith("tests.")]
    print("|", cell([module]), "|", cell(imports[module]), "|",
          cell(product), "|", cell(tests), "|")
```

The inventory and ledger contain **49 Python modules** and **two JSON resource
files**. A later baseline requires regenerating the ledger and rereading changed
bodies/tests; this document is a snapshot, not a permanent placement register.
