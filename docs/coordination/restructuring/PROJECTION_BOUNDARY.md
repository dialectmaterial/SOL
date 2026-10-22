# C3: verified corpus and edition projection boundary

**Date:** 23 October 2026. **Owner:** Codex lane A.
**Status:** proposal only; **maintainer decision (reserved: public contract)**.
Code baseline: `origin/main` at `a509f851f3ee3e041cd4c03c226c4d40cc34314a`.

This answers [REEVALUATION §3.5](REEVALUATION.md#35-cores-edition-shaped-projection-c3)
and [Architecture §9, C3](../../ARCHITECTURE.md#9-placement-register).
Recommendation: retain CORE's verified graph, addressability, models and public
loader; put the current reader's edition choices in an explicit, package-owned
projection description, interpreted behind that loader. Keep the existing view
as the default with identical output. Do not move the whole cluster into BEING
or make ESSENCE's eligibility inherit the reader's choices.

No implementation, new public name, version change, register revision or
multi-edition support is authorized by this document. The inventory describes
the baseline; proposed paths and description fields below do not exist yet.
No private corpus, PDF or workspace was consulted for this proposal.

## 1. Authority and the distinction being proposed

[CORE §§2, 4–10](../../CORE.md) defines canonical records, references and
workspaces; [Architecture §3](../../ARCHITECTURE.md#3-one-book-not-every-pdf) keeps active
work on the audited edition. The existing reading, rather than a new textual
claim, bounds the placement argument:

- [READING_BEING §1.1](READING_BEING.md#11-the-division-p-56) treats the preliminary
  division as something needing justification; a three-root navigation tree
  cannot itself justify a logical architecture.
- [READING_ESSENCE §§3–5](READING_ESSENCE.md#3-reading-notes-text-before-placement),
  especially C3/C4 in §5, distinguishes retained source determinations from
  an empty shared substrate. Its alternatives already identify a projection
  seam and warn against treating projection as Appearance.
- [READING_BEING §3.7](READING_BEING.md#37-workspace-solworkspace) records the
  maintainer's workspace placement in BEING. A projection description acquires
  no ownership of reading work.

**Engineering inference:** CORE can supply a shared *view* without claiming
that view is canonical identity or the logical development itself. Explicit
edition policy is useful to both BEING and ESSENCE's interfaces. This proposal
adds no Hegel quotation, page attribution or philosophical placement beyond
those existing readings. Numeric constants below are code inventory, not new
claims about where a philosophical determination begins.

| Layer | Verified or selected content | Boundary consequence |
| --- | --- | --- |
| Canonical corpus contract v1 | Manifest and declared documents; opaque UUIDs, types, `parent_id`, `order`, exact Markdown and derived `plain_text`, attribution including uncertainty, source references, reciprocal notes, retirement chains; manifest/document/index fingerprints and page coverage | Keep the complete graph and its validation. Structural verification is neither authorship authentication nor proofreading. |
| Canonical organization | Parent graph and generated ancestor `context`; optional canonical `path`, titles and labels; physical `document` editing units | Do not reconstruct parents or UUIDs from reader paths, slugged headings, document names or page numbers. |
| Stored projection metadata | Optional `reader_path`, `reader_title`, `heading`, `random_eligible`, review flags and image/caption metadata | These bytes are verified as part of the record/index, even when their meaning is presentation policy. Moving their *interpretation* does not authorize deleting or rewriting them. |
| Reader projection | A selected sequence of `Passage`s, mutable `Node` tree, virtual `.txt` leaves, aliases, abbreviated roots, integer start/end page presentation and facsimile-caption suppression | A convenient view, not the complete graph. It may refuse a structurally valid corpus; that does not make its records invalid. |
| ESSENCE projections | Versioned feature text, eligibility, masks, scopes, exclusions, token/sentence populations and receipts | Research policy remains in ESSENCE. Canonical identity is shared; eligibility and derived text need not be. |

A source `printed_page` is **provenance**, a string or null in contract v1;
turning it into an integer, comparing page ranges and displaying `p.` are
**projection** decisions. The PDF page remains a one-based physical locator.
A UUID remains the same record if a display path or heading changes. Conversely,
changing stored reader metadata changes the generation and invalidates strict
v1 receipts even when the UUID and prose stay fixed.

## 2. Inventory: where the assumptions live

Links identify files in this baseline; symbols identify the specific operations.
`E/` below means `sol/essence/essence_as_reflection_within_itself/`, and `W/`
means `sol/being/workspace/`. They are abbreviations in this inventory only.

### 2.1 CORE

| Location | Exact assumption or responsibility |
| --- | --- |
| [`models.py`](../../../sol/core/models.py): `Node`, `Passage`, `Book` | `Node.start_page`, `Passage.printed_page/end_printed_page` are integers; node `anchor` is an optional physical position used by import geometry. Node parent/children form a virtual tree, while `Book.passages`, redirects, canonical records, manifest and snapshot are caller-mutable collections. `selection` is a path-component prefix over the selected sequence; `find_passage` resolves only readable IDs/prefixes/redirects and its unreadable-target error names Hegel. `search` uses that sequence and `presentation_text` removes generated facsimile labels and trims display prose. These are not an edition-neutral full-graph model. |
| [`paths.py`](../../../sol/core/paths.py): `alias`, `child_by_name`, `resolve_path`, `display_path` | Already takes a caller-supplied root; no edition default. Slash-separated virtual paths, optional `.txt`, casefold matching, numeric/Latin/Roman/αβγ prefix aliases, exact-name precedence, ambiguity refusal and parent traversal are navigation conventions. They never open host files or resolve canonical identity. |
| [`corpus.py`](../../../sol/core/corpus.py): `load_corpus_book` | Loads and verifies a snapshot and seeds `remember_verified` before exposure. Seeds root title `The Science of Logic` with 7; roots `BEING`, `ESSENCE`, `CONCEPT`, titles and start values 7/337/507. Builds sections carrying `reader_path` regardless of attribution; selects `paragraph`, `list_item`, `quotation`, `formula` only when author equals `G. W. F. Hegel` and role equals `main_text`. It does not exclude pending review or `generated_text` records. |
| Same loader: nested `reader_path`, `printed`, `ensure_node`, final sorting | Paths must start in one of the three roots, have no empty/dot/backslash components or `.txt` intermediate components; passages require `.txt` leaves. Pages use string `re.fullmatch(r"\d+", value)` then `int` (preserve this actual rule, including accepted Unicode decimal digits, rather than silently changing it to ASCII). Section title fallback is `reader_title` → `title` → `plain_text`; passage title fallback is `reader_title` → `heading` → filename stem, using current `dict.get` semantics. Ancestors are synthesized from names; repeated paths update title/label/start and earliest source order. Start pages use the present creation/minimum behavior, not a newly computed subtree minimum. `00-introduction.txt` sorts first, then earliest record order with stable ties. Root seed order remains the tie fallback. File/directory collisions and an empty readable sequence fail. |
| Same loader: `Passage` assembly / `Book` return | First/last source entries supply PDF and integer printed ranges; record UUID copied verbatim, exact `plain_text` retained, heading/type/review/random fields copied with current defaults. Facsimile labels use the existing converter-caption regex (numeric/lower-case Roman labels and relative asset PNG syntax). All records and tombstone redirects survive beside the selected view. No heading slugs or new IDs are computed at runtime. |
| [`config.py`](../../../sol/core/config.py): `discover_corpus`, `save_corpus` | One selected corpus pointer in XDG config version 1; precedence explicit → `SOL_CORPUS` → cwd `local-corpus` → saved → installed local project → source checkout. Invalid explicit/saved choices fail instead of silently switching. `save_corpus` calls **the reader loader**, so saving a valid full-graph corpus currently also requires the Hegel reader view. PDF setup diagnostic directs to the supported converter. No author or doctrine table in discovery itself and no edition/projection selector. |
| [`files.py`](../../../sol/core/files.py): `resolve_file_path` | Canonical `.md` selection uses declared documents and includes non-retired records of all attributions/types; virtual selection uses `Book.selection` IDs **plus section records whose stored `reader_path` has that component prefix**. Its returned `kind: reader_path`, display path, title and ordered target IDs are observable. A new view cannot merely change the tree and leave this section predicate behind. |
| [`references.py`](../../../sol/core/references.py), [`protocol.py`](../../../sol/core/protocol.py), [`wire.py`](../../../sol/core/wire.py), [`reference_cli.py`](../../../sol/core/reference_cli.py) | Full-graph resolution, generation trust, bounded wire and CLI; no three-root, Hegel-author or integer printed-label restriction. `sol.reference` v1 carries string/null labels, source/edition/generation binding, requested/target IDs and chain; it omits paths, titles and bodies. Protocol freshness still hashes manifest/index containing projection metadata. |
| [`source.py`](../../../sol/core/source.py): `SourceService._location`, `capture`, `_validate_sources` | Source lookup has legacy candidate `Hegel-SOL.pdf` after explicit/environment/saved/manifest-filename routes. Captured title prefers `reader_title` over `title`/type. Source locations preserve string/null printed labels and PDF coordinates; PDF fingerprint/page count, not reader integer pages or the filename, establishes binding. This is a smaller edition convenience to inventory, not permission to rewrite the source interface. |
| [`__init__.py`](../../../sol/core/__init__.py) | Lazy identity-preserving facade, `API_VERSION = 1`; exports the projection models/loader and full-graph services together. Public names and module identities constrain a later extraction. |

### 2.2 Corpus maintenance and description sources

| Location | Edition assumptions, and what must stay distinct |
| --- | --- |
| [`contract.py`](../../../sol/corpus/contract.py) | `CONTRACT_VERSION = 1`; validates extensible types, string/null author and printed labels, absolute optional `reader_path` strings, source order/coverage, UUID/parent/order/note/redirect integrity and exact index generation. It does **not** require Hegel, the three roots, `.txt` leaves or Arabic labels. Manifest `edition` is a nonempty object, not a check for one Cambridge fingerprint. `CorpusSnapshot` and load/current guards belong to custody, not projection selection. |
| [`edition.py`](../../../sol/corpus/edition.py) | Audited filename, `FIRST_TEXT_PAGE`, `LAST_TEXT_PAGE`, `PRINTED_PAGE_OFFSET`; abbreviated `BEING/ESSENCE/CONCEPT` `Node` tree, `SUBDIVISIONS`, `SECOND_LEVEL`, `THIRD_LEVEL`, root and `default_pdf`. This is importer evidence **and** source-free guide fallback, not the runtime canonical hierarchy or a ready-made replacement for record `reader_path`. |
| [`layout.py`](../../../sol/corpus/layout.py) | Imports those constants and CORE `Node`; Poppler extraction range/expected source shape, font/heading matching, printed-offset lookup, anchors and `indexed_tree`. For conversion/explicit layout use, never the ordinary verified loader. |
| [`structure.py`](../../../sol/corpus/structure.py) | `EXPECTED_COUNTS`, Greek/Remark/unnumbered-heading audit tables, `build_hierarchy`, parent assignment and volume/title-display evidence. Corrects synthetic abbreviated-tree anchors into canonical hierarchy, distinguishes shared preliminary material, classifies books/doctrine, calculates printed labels with the audited offset. Audit IDs are reconciliation keys, not permanent record UUIDs. |
| [`convert.py`](../../../sol/corpus/convert.py) | `AUDITED_SOURCE_SHA256`, `EDITION`, `GAPS`, small-cap and editorial heading tables; PDF label extraction/coverage; fixed page-range attribution in `attribution`; `Importer.structures` assigns canonical documents, canonical `path` and **separate** doctrine reader paths via source boundaries, slugs and leaf detection. It overrides the inherited Being reader parent for Essence. `text_record` adds `/00-introduction.txt` for directory prose. `make` allocates UUIDs only at ingestion. Formula/review/random policy, source-image captions, notes, references and publication are edition-aware. None should be replayed to derive a runtime view or regenerate existing paths. |
| [`notes.py`](../../../sol/corpus/notes.py), [`references.py`](../../../sol/corpus/references.py) | Audited page/font/geometry ranges, note markers/continuations/math discrimination, bibliography categories and two-column index segmentation. Their `start_page/end_page` are physical extraction coordinates, not reader printed-page integers. `convert` supplies ranges/attribution and writes their evidence into the complete graph. |
| [`onboarding.py`](../../../sol/corpus/onboarding.py) | Prompts for exactly the supported Cambridge source; hash-gates import, uses digest-named local destination, verifies with `load_corpus_book`/`save_corpus`, remembers PDF through `SourceService`. This intentionally remains single-edition; a description alone does not make other PDFs supported. |
| [`markdown.py`](../../../sol/corpus/markdown.py), [`ingest.py`](../../../sol/corpus/ingest.py), [`extraction.py`](../../../sol/corpus/extraction.py), [`backends/opendataloader.py`](../../../sol/corpus/backends/opendataloader.py), [`errors.py`](../../../sol/corpus/errors.py) and package markers | CommonMark/source-callout semantics, reviewed correction against a verified baseline, candidate artifacts/backend validation and errors. No independent three-doctrine/Hegel reader selector here. Ingestion preserves baseline identities and metadata; extraction candidates do not acquire canonical identity or select a reader projection. Keep no-clobber, private-artifact and provenance constraints. |

### 2.3 Consumer closure

This lists direct consumers and the adapters that expose their results; it is
not an assertion that every consumer hard-codes all three doctrine names.

| Consumer | Reliance to preserve or make explicit later |
| --- | --- |
| [`being/actions.py`](../../../sol/being/actions.py): `ReadingSession`, `_checked_source`, `ReaderActions` | Sequence cursor, path scope, literal search, random selection, history and reference return. Source checks compare exact passage text, ID, displayed path to **record `reader_path`**, and integer source ranges. A second mapping would currently be rejected even with a correct UUID. |
| [`being/surface.py`](../../../sol/being/surface.py) and [`quality/search.py`](../../../sol/being/quality/search.py) | Bounded consecutive passage samples, complete graph for notes, verified source return, exact canonical offsets with a display/search mapping. Caption suppression and presentation trimming cannot alter canonical text/digests or source offsets. |
| [`quality/structure.py`](../../../sol/being/quality/structure.py) and [`quantity/navigation.py`](../../../sol/being/quantity/navigation.py) | Outline uses node paths as keys, first passage as each branch's target and integer start as page string; `doctrine` means first path component. Navigation is geometry over supplied text, not an author selector. |
| [`being/render.py`](../../../sol/being/render.py), [`being/shell.py`](../../../sol/being/shell.py) | Page range arithmetic, listing/tree/info/JSON, random pools, scoped `cat`, path completion and guide. `render_tree`/`render_guide` can use the abbreviated `edition.ROOT` without a corpus; that fallback differs from the record-built tree and must remain so. |
| [`being/neovim/reader.py`](../../../sol/being/neovim/reader.py), [`host.py`](../../../sol/being/neovim/host.py), Lua adapters | Groups adjacent passages by path; next/previous and progress use selected order; printed-page jump compares integers. Host exposes path/title/page ranges, source-bound codepoint/UTF-8 mappings and ESSENCE launch context. `neovim_tree.lua` uses path keys and `structure.doctrine`; `neovim_controls.lua`/`neovim_view.lua` display printed ranges; `neovim_panels.lua` and footnote UI display source labels. Other request/text/note/ESSENCE Lua modules consume these payloads, not an independent edition table. `channel/runtime/window/splash` transport or present the reader and must not become corpus selectors. |
| [`W/reader.py`](../../../sol/being/workspace/reader.py), [`store.py`](../../../sol/being/workspace/store.py) | Schema 3 binds one corpus UUID and provenance. Reading state/history store `cwd`, `scope`, `current_id`, `previous_cwd`. Positions store target UUID, Markdown and exact plain-text hashes/length, cursor and optional viewport codepoints at the same revision. Restore resolves saved paths and UUID, recomputes sequence cursor and falls back with warnings if scope/cwd changed. Even a safe fallback would be a visible regression in this migration. |
| [`W/diagnostics.py`](../../../sol/being/workspace/diagnostics.py), [`export.py`](../../../sol/being/workspace/export.py) | Distinguish valid full-graph references from readable passages. Pending review queue scopes and displayed locations use stored reader paths/title fallback, including editorial material; exports include virtual-path metadata. `catalog/launch/lifecycle/profiles/time` and APP workspace commands manage identity, provenance and persistence without their own Hegel tree; preserve no-write reads, guards, archives and copy-only upgrade. |
| [`core/source.py`](../../../sol/core/source.py), [`being/source_view.py`](../../../sol/being/source_view.py) | Full-graph ID/source lookup, request binding and viewer/render checks must keep working outside the selected sequence. A projection must not hide editorial notes from source custody or invent page-offset evidence. Existing source-validation gaps stay as documented in [SOURCE_VALIDATION](SOURCE_VALIDATION.md). |
| [`E/corpus_inputs.py`](../../../sol/essence/essence_as_reflection_within_itself/corpus_inputs.py) | `_DOCTRINES` is exactly the three roots; `_reader_doctrine` requires a descendant `.txt` leaf and rejects malformed components. `_selection` requires exact Hegel/main-text attribution, prose types paragraph/quotation/list_item, no `generated_text is True`, no pending review, and a valid reader doctrine; its optional doctrine filter is a further selection. `_fresh/_current/_binding` check the full generation and initialized corpus identity. `_facsimile_spans` masks only exact trailing converter labels bound to record/source filenames. |
| [`E/word_inputs.py`](../../../sol/essence/essence_as_reflection_within_itself/word_inputs.py), [`words.py`](../../../sol/essence/essence_as_reflection_within_itself/words.py) | `CoreProvider` selects corpus/within-path/exact IDs/span then applies that eligibility in canonical order, records exclusions/masks and path/source/attribution metadata. Even explicit IDs do not bypass the reader-path requirement. `FileProvider` is verbatim UTF-8 and independent of CORE. Artifact method fixes `hegel-main-text-no-pending-flags-three-doctrines-v1`; do not replace it with "whatever is visible in Book". |
| [`E/sentences.py`](../../../sol/essence/essence_as_reflection_within_itself/sentences.py), [`sentence_inputs.py`](../../../sol/essence/essence_as_reflection_within_itself/sentence_inputs.py) | Legacy v1 has its own scope/selection order and reader-doctrine validator, including artifact validation. Provider v2 uses word-provider inputs and retains the declared three-doctrine policy. Both exclude formulas/pending/generated/editorial records, unlike reader sequence policy. Preserve reason precedence, offsets and v1/v2 bytes. |
| [`E/prose.py`](../../../sol/essence/essence_as_reflection_within_itself/prose.py) | `export_prose` filters Hegel/main prose, generated/pending and empty feature text **without requiring `reader_path` or doctrine**. It derives ancestry from `parent_id`, removes headings/images from features via CommonMark and copies any reader metadata as provenance. This existing counterexample must not be narrowed to `Book.passages`. |
| [`E/comparison.py`](../../../sol/essence/essence_as_reflection_within_itself/comparison.py), [`tfidf.py`](../../../sol/essence/essence_as_reflection_within_itself/tfidf.py), tokenizer/validation | Inherit provider eligibility/population and method receipts; do not directly build an edition tree. A different projection must not silently change document populations, counts, denominators, TF-IDF weights or verification. |
| [`essence/tui/words.py`](../../../sol/essence/tui/words.py), [`sentences.py`](../../../sol/essence/tui/sentences.py), [`tfidf.py`](../../../sol/essence/tui/tfidf.py) | TUI loads `Book` for snapshot **and** human labels; section choice takes a passage's parent path, book choice takes all eligible corpus input. Labels/find-and-return use `find_passage`, headings and integer pages, with record-path/source-label fallbacks. TUI `app/context` persist investigation state using those scopes; a view-only change could alter a later study input. |
| [`app/main.py`](../../../sol/app/main.py), [`options.py`](../../../sol/app/options.py), [`commands.py`](../../../sol/app/commands.py), launch/entry points | APP wraps the loader and supplies the **edition ROOT default** to its path wrapper (CORE's resolver requires an explicit root). `--structure`, guide, info, cat, passage, within/random, JSON, shell/reader and source commands expose this view. `sol read` uses `core.files`. `sol --set-corpus` validates it. `sol`, `sol-window`, `sol-corpus`, `sol-corpus-check`, `python -m sol` and `python -m sol.essence.cli` remain entry-point contracts. |
| [`essence/cli.py`](../../../sol/essence/cli.py), word/sentence/TF-IDF CLI adapters | CORE selection loads snapshots directly; path scopes, labels, rendered page strings and artifact recomputation still carry the ESSENCE projection assumptions. Reference CLI operates on all records, not only reader eligibility. Encyclopedia/method registry describe logical/method choices, not a replacement corpus tree. |
| [`interchange/essence.py`](../../../sol/interchange/essence.py), [`presentation`](../../../sol/presentation), [`scripts/reader_timings.py`](../../../scripts/reader_timings.py) | Exchange passes the existing corpus/reference context, no projection selector or workspace authority. Presentation only escapes/displays supplied values. Timing script builds an invented Hegel-attributed reader corpus and exercises loader/actions/host; its defaults are another synthetic compatibility consumer. |

### 2.4 Tests and fixtures that encode these choices

Existing reusable [`fixtures_corpus.py`](../../../tests/fixtures_corpus.py)
creates `/BEING/synthetic.txt`, Hegel/main-text attribution, numeric labels and
a minimal synthetic edition manifest, including a parser-free runtime index.
`CorpusFixture.write_records` reloads the reader: tests using it implicitly
require at least one eligible reader passage. `detach_reader_graph` deliberately
separates the mutable view from verified data. [`fixtures_footnotes.py`](../../../tests/fixtures_footnotes.py)
adds separately attributed notes to that graph; [`fixtures_sentence_v1.py`](../../../tests/fixtures_sentence_v1.py)
freezes four v1 encodings containing reader paths and generation hashes.
`fixtures_async.py` changes event-loop setup only.

Inline synthetic fixtures matter too: `test_corpus_reader.py` writes a multi-root
corpus with formula/editor/note cases; `test_core_models.py`, reader actions,
workspace, render and shell tests hand-construct `Node/Passage/Book`; sentence,
word, comparison and TF-IDF tests add doctrine scopes and explicit exclusion
cases. Protocol tests deliberately include editorial and Roman/null-label
records. Packaging/native/Neovim tests and the timing script reuse the tiny
runtime fixture. Import tests assert facade/model identity and forbid interface
and importer dependencies. A source-fingerprint-only dispatch would break
these valid fixtures and is not part of this proposal.

The complete affected regression families are CORE API/models/config/protocol,
corpus contract/identity/reader/conversion/structure/notes/references/ingestion,
read paths/reference CLI, guide/shell/native commands/reader view CLI/first run,
reader actions/context/cursor/position/flow/search/surface/typography/efficiency,
footnotes/source discovery/viewer, workspace store/reader/diagnostics/export and
lifecycle/launch/catalog/management, ESSENCE analysis CLI/providers/studies/
comparison/TF-IDF/prose/TUI, architecture/package boundaries/packaging and
reader timing/Neovim host/headless/terminal tests. §5 pins exact sentinel names
and the missing equality tests; this inventory does not claim current tests
already prove all proposed invariants.

## 3. Recommended seam

### 3.1 Ownership and flow

Keep `sol.corpus.contract` responsible for parsing/indexing/verification and the
complete graph; keep its lazy CORE exports. Keep `sol.core.models`, `paths`,
`references`, `protocol`, `source` and existing file resolution services in
CORE. `Book`, `Node` and `Passage` stay the compatibility view types; they do
not become universal edition/label types. Keep mutable-collection caveats and
trust verification unchanged; no new cache or immutability project is needed.

Proposed internal location: `sol/core/projections/`, with a small description
value type/validator and builder, and `hegel.py` containing the legacy reader
description. Use immutable Python **data values** (tuples/frozen records with
closed policy identifiers), not user-defined subclass callbacks or code loaded
from corpus metadata. This is a named, shared CORE adapter, not a new logical
division. It stays independent of BEING, ESSENCE, PDF extraction and workspace
state. Import it only on the loader path. Ordinary model/facade imports must
remain lazy and perform no file I/O.

The existing `sol.core.corpus.load_corpus_book(corpus)` would orchestrate:
verify snapshot → seed protocol verification exactly as today → choose the
legacy description explicitly inside this existing default entry point → build
the legacy view from verified records → attach the **unchanged complete** graph,
manifest, directory, snapshot and redirects. A builder accepts an already
verified snapshot and description internally; it neither reads a PDF nor
rewrites records. CORE file selection must consult the same view mapping for
sections/passages if a later alternate view is implemented.

The existing manifest's `edition` and `source` objects remain the edition
identity/provenance description. The package description references their
verified records; it does not copy the translator/ISBN/source identity into a
second authority. Audited importer geometry remains in `sol.corpus`, while
record-specific paths/titles remain in the local corpus. Only runtime view
choices live in the proposed package description.

Do not import the converter's `edition.ROOT` to build this view. That outline is
abbreviated audit/fallback data. Keep its existing APP/render uses intact in the
first implementation. Do not infer the current default from edition title,
translator spelling, source filename or audited PDF hash: the existing loader
accepts synthetic and other structurally matching v1 inputs. It must keep doing
so. This first seam therefore does not claim to auto-detect supported editions.

### 3.2 What the description must say

These are proposed internal fields/semantics, not a new JSON schema or API:

| Description content | Legacy Hegel expression |
| --- | --- |
| Internal projection key and revision | Proposed key `hegel-reader-legacy-v1` at revision 1; separate from edition/corpus UUIDs and ESSENCE method IDs. It selects behavior, never record identity. Freeze it once published as the default. |
| Root seed and ordered branch seeds | Root `("", "The Science of Logic", 7)`; branches `("BEING", "Doctrine of Being (Book One)", 7)`, `("ESSENCE", "Doctrine of Essence (Book Two)", 337)`, `("CONCEPT", "Doctrine of the Concept", 507)`. These are initial values subject to today's record-driven updates/sorting, not final hard-coded titles/pages. |
| Structural-record selection | All section records carrying `reader_path`, even if not Hegel-attributed; retain current invalid-path/title/page failures. |
| Passage selection | Author exactly `G. W. F. Hegel`, role `main_text`, types paragraph/list_item/quotation/formula. Preserve review flags and random default separately. No new generated-text or review exclusion. |
| Mapping source and grammar | Read existing `reader_path` byte-for-byte; permitted first components are seed names; current component and `.txt` rules. Preserve `reader_title`/title/heading defaults and labels. Do not regenerate slugs, normalize Unicode/case, add prefixes or relocate preliminary texts. |
| Ordering and node construction | Current `ensure_node` behavior; source record iteration, minimum encountered order, stable ties, `00-introduction.txt` priority; exact start-page updates and synthesized ancestor names. Explicitly preserve empty branches and file/directory collision failures. |
| Page policy and presentation | Current decimal-string-to-int conversion, first/last source range, exact caption regex and metadata copies/defaults. Keep full source labels unchanged in canonical records/protocol. Arabic compatibility does not supply a future Roman-label jump implementation. |
| Failure behavior | Preserve exception classes and existing actionable messages, including no-prose/Hegel wording; do not leak a new internal validation error type through the facade. |

A useful internal build result includes the existing `Book` plus mapping
information (record ID → selected path, section membership and node metadata)
needed by file resolution. For the first migration, it must equal the stored
reader metadata exactly; no public `Book` field is required. A later alternate
mapping needs a deliberately supported binding accessible to source guards,
file resolution and adapters, rather than a hidden replacement of
`record['reader_path']`. The shape/public exposure of such a binding is a
separate maintainer contract decision.

### 3.3 Demonstrating the current projection without changing identity

For the existing fixture, `reader_path: /BEING/synthetic.txt` must still yield
`Passage.path == ('BEING', 'synthetic.txt')`, the same node names, and
`display_path(...) == '/BEING/synthetic.txt'` with the identical UTF-8 bytes.
Its fixed fixture UUID must be copied unchanged, as must all other IDs,
redirects, parent links, source metadata and exact canonical text. The
same rule applies to **every** existing virtual path, including directory
introductions, Greek components and preliminary material. Seeds do not
reparent canonical records.

With identical passage sequence/text, titles, ranges and tree, a schema-3
checkpoint's saved `cwd/scope/previous_cwd` still resolves to the same nodes;
`current_id` retains its requested identity; the target UUID, content/plain
hashes, plain-text length and cursor/viewport offsets still agree. Restore must
not trigger the scope-change warning or invalidate positions, and ordinary
opening must not create a new visit, rewrite saved paths or upgrade a database.
This is the promised compatibility outcome, not merely "UUIDs survive".

ESSENCE continues using its current eligibility and artifact method identifiers
verbatim. It may later reuse a syntax/mapping primitive after equality is
proved, but not the reader passage predicate: formulas, pending flags and
pathless prose show why that would change results. The path-independent prose
exporter remains path-independent. No new projection key is inserted into an
existing analytical artifact or exchange envelope in this migration.

### 3.4 A second edition versus a second view of the same edition

**Second edition:** first requires separate audited ingestion, edition/source
metadata, permanent corpus identity and its own record UUIDs/provenance; no
matching by slug, number or text hash, and no ID reuse across translations.
It supplies a description of its roots, mapping, labels, ordering and selected
roles/types. A description can only expose evidence already in its verified
graph. It cannot make an unsupported PDF acceptable or invent attribution or
labels. New selection/configuration must be explicit, never a fallback after
a broken saved corpus. Non-Arabic labels require a separately designed model,
rendering and page-navigation interface, since API-v1 `Passage` fields are
integers. Refuse an unsupported legacy view rather than coercing Roman/null
labels to fictitious numbers. Translation alignment is separate work.

**Second projection, same edition/generation:** reuse the same verified graph,
corpus UUID and record UUIDs. It may supply a separately reviewed record-ID-to-
path mapping in trusted package data; do not mutate canonical `reader_path` or
parent metadata just to offer another tree. Define how shared/multiple paths,
unreadable targets, source guards, `.md` versus virtual file membership,
ESSENCE section scopes and human labels behave. The first migration supports
one path per selected record and authorizes no such expansion.

Schema 3 stores paths without a projection discriminator. Consequently another
projection with different path meanings cannot silently share its saved state.
Before enabling it, decide either a separate explicitly bound workspace/profile
with enforced projection identity, or a versioned schema/export migration that
stores the discriminator. Merely choosing another workspace name does not
persist or enforce that binding today. Preserve the legacy default and old
restoration semantics meanwhile. Similarly, path-scoped study artifacts need
an explicit projection/method binding if their interpretation changes.

Reference v1 can still identify records in either view because it is view-free;
it cannot promise reopening a particular tree or reproducing a path-scoped
study. A projection revision alone, kept outside the corpus, does not make a
v1 reference stale. That is intentional: source receipt and view reproducibility
are different promises. A future view-specific receipt belongs to a new,
reviewed contract, not an unknown field smuggled into protocol v1.

## 4. Compatibility and migration gates

| Surface | First extraction requirement | A change that needs a separate decision |
| --- | --- | --- |
| CORE facade and module paths | Keep `API_VERSION = 1`, exact `__all__`, lazy identity exports; keep `Book/Node/Passage`, `node_path`, `presentation_text`, path helpers, `Reference`, resolution functions, snapshot/error/load/current services, discovery/save and all protocol constants/functions. Keep existing constructors, argument defaults, mutable collection behavior and direct module imports. `load_corpus_book(corpus)` retains its signature and returns the same classes. APP wrappers continue working. | Public projection selector/type/export, changed default eligibility, model/page types, errors or return fields. Additive APIs still need maintainer contract review and explicit version policy; do not infer that keeping the integer permits any addition under API 1. |
| Corpus contract | Keep `CONTRACT_VERSION = 1`; read the exact old manifest, Markdown, index and index metadata. No new required field, corpus write, reindex, identity initialization, changed `reader_path` or edition metadata. Older corpora lacking `corpus_id` remain loadable as today; persistent work still requires explicit identity. | Required corpus-side descriptions or changed semantics need a contract/version decision. Even an optional manifest addition changes strict generation hashes and may change edition fingerprints if put under `edition`. |
| Workspace schema 3 | No schema, export shape, SQL definition or stored value change; retain schemas 1/2 read behavior and explicit copy-only upgrades. Equality includes browsing paths, scope, IDs, semantic offsets, revisions and no-op writes. | Projection binding or new path interpretation requires its own schema/export/restore design. Never rename paths in an existing workspace as a side effect of loading. |
| `sol.reference` v1 | Keep `PROTOCOL_VERSION = 1`, byte limits, fields, encodings/status/codes, strict generation equivalence, retirement chain and freshness behavior. Byte-identical source inputs produce byte-identical packets and receipts. No view key/path field. | Relaxed generation rules, projection-aware envelopes or new fields require explicit protocol design/versioning. |
| CLI/installed package | Keep names/flags, JSON field types/order where deterministic, output paths/pages/titles, root fallback guide, errors and exit status. A CORE-only installed wheel still loads the reader projection without BEING/ESSENCE/importer/UI. | Edition/projection selection flags, persisted selection or unsupported-label behavior need a further product/public-contract decision. |
| ESSENCE methods/exchange | Existing selectors, exclusions/reason precedence, scopes, masks, feature text, artifacts, method strings and context packets unchanged. File providers stay CORE-free. | Changing eligible material or scope meaning requires versioned method/provenance review; a source reference alone does not specify the new policy. |

For clarity, the complete existing facade name set to retain is:

```text
API_VERSION
Book Node Passage node_path presentation_text
Reference resolve_reference resolve_record_reference
PROTOCOL_VERSION MAX_REFERENCE_BYTES MAX_REFERENCE_BATCH ProtocolError
capture_reference capture_references check_reference check_references
encode_reference decode_reference
alias child_by_name display_path resolve_path load_corpus_book
CorpusError CorpusSnapshot load_snapshot verify_snapshot_current
discover_corpus save_corpus
```

Proposed implementation sequence, **only after approval**:

1. Freeze synthetic baseline results and refusal behavior in §5 before moving
   logic. Include all seeds/mapping/page rules; record source tree baseline.
2. Introduce the internal description and extract only policy, retaining the
   facade, model identities and the loader's verification/cache-seeding flow.
   Keep converter audit/fallback tables and analytical policy in place.
3. Compare old baseline against the delegated loader at object, rendered,
   serialized, workspace and installed-wheel boundaries. Check no corpus/config
   or workspace write occurs on read. Run docs/architecture/packaging and full
   suite. Revert the extraction if equality cannot be explained and proved.
4. Ship the single default seam only. A second view/edition, generic page model,
   corpus-side data format and public selection API remain separately scoped
   decisions. No data migration should be needed to adopt the first extraction;
   reverting it must read precisely the same local files and schema-3 state.

## 5. Exact acceptance evidence for a later implementation

The current full suite is necessary but insufficient for a byte-identity claim.
Use only invented redistributable fixtures; do not commit a real-corpus golden
file, PDF, workspace, text export or a derived hash inventory of private prose.
When baseline fixtures allocate UUIDs/timestamps, fix them for the comparison;
normalize temporary **host** directories only, never virtual paths, UUIDs,
labels, order or payload fields. Hold interpreter/Unicode version, width/theme,
seeded random input and synthetic corpus generation constant.

Existing exact sentinels (names are relative to their stated test module):

| Test module | Existing tests to retain and what they establish |
| --- | --- |
| `test_core_api.py` | `PublicCoreTests.test_public_book_reference_path_and_snapshot_agree_without_writes`, `test_lazy_facade_identity_exports_and_unknown_names`, `test_fresh_public_import_and_model_request_do_no_io_or_optional_import` — facade, object identity and read/import behavior. |
| `test_core_models.py` | `CoreModelTests.test_model_parent_paths_and_facsimile_projection_are_unchanged`; all `CorePathTests` (explicit root, aliases/exact precedence, relative/parent traversal, missing/ambiguous/file errors); `CoreReferenceTests.test_workspace_compatibility_preserves_resolver_and_class_identity` and retirement tests. |
| `test_corpus_reader.py` | `CorpusReaderTests.test_loads_main_prose_and_formula_but_excludes_notes_editor_and_references`, `test_paths_parent_links_aliases_and_introductions`, `test_uuid_page_ranges_and_folding`, `test_reader_retains_full_canonical_records_and_note_attribution`, `test_virtual_file_start_page_is_its_first_paragraph`, `test_invalid_reader_path_is_rejected`, `test_review_pending_mixed_math_paragraph_is_ordered_but_not_random`, `test_default_corpus_never_uses_pdf_or_markdown_parser`. |
| `test_read_paths.py` / `test_core_config.py` | All `ReadPathTests`, especially `test_virtual_file_is_complete_and_ordered`, `test_directory_scope_preserves_book_order`, `test_canonical_markdown_accepts_relative_absolute_and_corpus_prefix`; `CoreConfigTests.test_save_validates_before_writing_and_stores_absolute_unicode_path` and discovery/refusal cases. |
| `test_corpus_contract.py` / `test_corpus_structure.py` | `CorpusContractTests.test_roundtrip_preserves_ids_unicode_markdown_and_metadata`, `test_text_and_heading_edit_do_not_allocate_ids`, `test_optional_reader_path_requires_an_absolute_string`, `test_existing_index_load_needs_no_markdown_parser`, plus graph/provenance refusals; `SyntheticStructureTests.test_shared_introduction_is_outside_being`. Canonical parents must survive view extraction. |
| `test_core_protocol.py` | `CoreProtocolTests.test_roundtrip_uses_existing_ids_and_returns_full_local_record_without_writes`, `test_complete_retirement_chain_retains_requested_uuid`, `test_generic_editorial_records_and_roman_null_source_labels`, `test_unrelated_correction_invalidates_old_packet_under_strict_generation_policy`, `test_a_freshly_loaded_book_is_checked_without_reading_the_files_again`, batch/memory/generation refusal tests. Retain `test_reference_cli.py` and source-viewer guards too. |
| `test_reader_context.py` / `test_reader_surface_export_guards.py` | `ReaderContextTests.test_corrupted_record_or_projection_is_rejected_before_selection`, `test_offsets_are_half_open_unicode_codepoints_of_exact_plain_text`; `ReaderSurfaceExportGuardTests.test_direct_source_guard_refuses_every_reader_provenance_change`, `test_every_serialized_reference_passes_unchanged_independent_core_check` and detached/stale view cases. |
| `test_reader_position.py` / `test_workspace_reader.py` | `ReaderPositionTests.test_cursor_and_semantic_viewport_roundtrip_same_revision_and_history`, `test_position_uses_unicode_codepoints_not_encoded_bytes_or_wrapped_rows`, `test_dirty_position_writes_once_and_noop_does_not_create_visit`, `test_legacy_v1_v2_reopen_unchanged_and_upgrade_creates_separate_v3_copy`; `WorkspaceReaderTests.test_reordering_recomputes_cursor_by_uuid_not_numeric_position`, `test_retired_reference_discloses_chain_and_preserves_requested_id`. Keep stale/conflict/history tests. |
| `test_workspace_diagnostics.py` | `DiagnosticTests.test_editorial_reference_is_live_but_not_a_main_text_passage`, `test_queue_scope_obeys_path_component_boundaries_and_excludes_unmapped_editorial_records`, `test_diagnostics_are_read_only_and_do_not_open_files_or_databases`. Retain JSON/Markdown export and schema/lifecycle tests. |
| `test_word_frequencies.py` / `test_sentence_study.py` / `test_sentence_providers.py` | `CoreWordTests.test_core_projection_uses_shared_tokenizer`, `test_pending_editorial_generated_and_facsimile_material_is_excluded`; `SentenceStudyTests.test_lengths_positions_and_exclusions`, `test_scope_by_path_and_by_passages`; `CoreSentenceTests.test_provider_scopes_keep_canonical_identity_and_match_legacy_statistics`; `SentenceV1CompatibilityTests.test_four_original_v1_artifacts_still_recompute_and_encode_byte_for_byte`. Retain file-provider independence, comparison and TF-IDF population tests. |
| `test_prose_inputs.py` / `test_essence_tui.py` | `ProseExportTests.test_feature_text_and_hierarchy_have_separate_hashes_and_no_source_writes`, `test_eligibility_excludes_nonprose_editorial_generated_and_pending_records` (including no reader-path requirement); retain TUI section selection, label and return tests and headless CLI equality. |
| `test_architecture.py` / `test_package_boundaries.py` / `test_packaging.py` | All architecture/import checks; especially `PackagingTests.test_core_only_wheel_proves_interface_dependency_boundary`, `test_installed_relocated_modules_preserve_core_and_presentation_boundaries`, `test_built_wheel_entry_points_import_and_display_help`, and source-free guide/reader cases. Ensure the proposed package is included without new dependencies/private data. |

Required **new characterization tests**, proposed names (not tests delivered in
this docs-only PR):

1. `test_legacy_projection_complete_tree_and_passages_equal_baseline`: one
   deterministic synthetic graph covering all three roots, absent branches,
   implicit ancestors, multiple sections sharing paths, introductory leaves,
   title/heading fallback, labels, tied ancestor order, record order, formulas,
   review/random/generated flags, multi-page spans, caption variants and
   tombstones. Compare a cycle-free ordered tree description (including parent
   paths, start pages, anchors and child order), every `Passage` field, redirects
   and **all** canonical records/manifest/snapshot bindings. Assert shared node
   identity within the book, canonical full-graph resolution versus readable
   resolution and exact UTF-8 virtual path bytes. No blanket sorted comparison
   that could hide order changes.
2. `test_legacy_projection_refusals_equal_baseline`: table of invalid roots,
   absolute/empty/dot/backslash/virtual-file traversal paths, no `.txt` leaf,
   directory/file collisions, blank/invalid titles, Roman/null printed labels
   on selected sections/passages, no selected prose and random type errors.
   Compare exception type/message and no writes. Include valid Roman/null
   **unselected** records and accepted decimal labels; contract acceptance and
   reader rejection remain distinct. Do not silently tighten known semantics.
3. `test_legacy_projection_cli_payloads_equal_baseline`: byte-compare
   deterministic `--structure --json`, guide (corpus and abbreviated fallback),
   info/list/cat/passage/within and seeded random JSON/plain output, `sol read`
   canonical and virtual selections, source titles and reader structure/host
   payloads. Check status/stderr for refusals. Keep real Neovim headless tests
   and source guard tests as end-to-end checks; no display/PDF is needed for
   new fixture comparisons.
4. `test_legacy_projection_schema3_restore_has_no_visible_change`: create a
   disposable **synthetic** schema-3 database through old behavior, with
   browsing/scope/previous paths, an exact requested/retired ID and Unicode
   cursor/viewport positions. Open with delegated loader; compare exported
   rows, revisions/history, hashes, offsets and resumed passage/scope/cwd,
   assert no new warnings and byte-identical database before/after a read-only
   restore. With deterministic clocks, compare one explicit subsequent save
   against an old-loader control. Retain schema-1/2 no-auto-upgrade behavior.
5. `test_legacy_projection_reference_and_study_bytes_equal_baseline`: compare
   encoded reference capture/check and batches on readable/editorial/retired
   records, including string/null labels and every binding. Compare word,
   sentence v1/v2, comparison, TF-IDF and prose exports for corpus/within/ID/
   span scopes, plus TUI section derivation and labels. Explicitly include a
   pathless eligible prose-export record that word/sentence providers exclude,
   and reader-visible formula/pending records those studies exclude. Verify
   exclusion precedence, masked counts, first-occurrence offsets and strict
   unrelated-generation invalidation without altering existing method IDs.

Finally run `python -B scripts/check_docs.py` and
`python -B -m unittest discover -s tests` with isolated XDG directories and no
private corpus/PDF overrides. Review the Git diff for docs/code scope and local
material; run installed console/help/import checks already covered by packaging.
An optional later maintainer-run private-corpus comparison must stay local and
is not a prerequisite satisfied or claimed by this proposal.

## 6. Alternatives and maintainer decision

| Alternative | Benefit | Cost / constraint |
| --- | --- | --- |
| Keep as is until a second edition exists | Least churn, no speculative model, current API and verification already work | Edition policy remains implicit in CORE and distributed consumers. It postpones a choice, not an architectural failure. Reasonable if maintaining the single edition outweighs making the seam explicit now. |
| Corpus-side data-file description | Travels with an edition; inspectable without Python; can express a tree independently of a software release | Needs a versioned format, path safety, binding/coverage rules and selection semantics. Listed in the manifest, it changes generation hashes; outside the manifest it is currently unverified. Existing corpora need a legacy default anyway. Never treat an arbitrary file as executable policy. Avoid duplicating canonical parents/titles or reindexing just to extract the seam. |
| Python projection classes | Can implement distinct label systems, mappings and eligibility without forcing a common data vocabulary | Callback/subclass behavior is harder to audit and freeze; may smuggle I/O, analytical policy or UI dependencies into custody. A public class protocol becomes another supported API. Suitable only if concrete incompatible views prove fixed data policies inadequate. |
| Package-owned internal data description behind existing facade (**recommended**) | Exposes current constants/policies explicitly, preserves lazy imports and zero corpus/workspace migration; small shared adapter serves reader and investigator UI | Description semantics and stable default still need contract review. Package revisions must not silently redefine the same default. It does not solve public selection, Roman-page navigation or multi-view workspace binding, and retains converter/guide fallback duplication deliberately. |

**Maintainer decision (reserved: public contract):** approve or reject the
recommended ownership and compatibility promise before implementation; choose
whether to extract the single legacy description now or defer until a concrete
second view exists. If approved, the default means exactly the existing
projection under the existing public names and versions, with §5 equality as
the acceptance gate. No API/contract decision is made by merging this proposal
as documentation. A public selector, new model/page-label interface, corpus-side
format, workspace projection binding or reference extension needs a separate
reviewed decision with its own version policy. No such change is implemented
or implied here.
