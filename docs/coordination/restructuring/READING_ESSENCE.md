# Stage C reading: the Doctrine of Essence

**Date:** 22 October 2026. **Owner:** Codex. **Status:** provisional proposals for Claude's review; nothing relocated.

Code baseline: `origin/main` at `0f5156aa511f8305abf3bf6fd7719a4e51515d8d`.
Scope: [the Codex stage C task](../CURRENT_TASK.md#codex-reading-the-doctrine-of-essence)
and all twelve cohesive groups in [the stage A inventory §8](INVENTORY_ESSENCE_CORE.md#8-cohesive-groups-and-questions-for-stage-c).
The register rows below are for later transfer by Claude to
[Architecture §9](../../ARCHITECTURE.md#9-placement-register). They propose destinations,
including explicit deferrals, without changing that register or the inventory.

## 1. Edition, retrieval and location convention

Primary working text: G. W. F. Hegel, *The Science of Logic*, translated and
edited by George di Giovanni (Cambridge University Press, 2010), ISBN
9780521832557, as identified by the private CORE manifest. Read from
`/home/dima/Projects/code/sol/local-corpus`, without conversion, reindexing or
workspace access. No other translation or commentary was used.

Example retrieval from a checkout with the project's environment:

```sh
.venv/bin/python -B -m sol read hegel/essence/preliminary/essence.md --corpus /home/dima/Projects/code/sol/local-corpus
.venv/bin/python -B -m sol read /ESSENCE/i-essence-as-reflection-within/1-shine/c-reflection --corpus /home/dima/Projects/code/sol/local-corpus
```

This checkout has no `.venv`; execution used the existing interpreter at
`/home/dima/Projects/code/sol/.venv/bin/python` from the task clone. The division
and all three section introductions were read through `sol read`, as were the
transitions listed below. Additional chapter openings and the identity/diversity
passages were read directly from the local index. Printed pages and UUIDs were
checked against each record's `sources`, not calculated from PDF offsets.

All locations below refer to this edition. `hegel/` paths are private corpus
document addresses, **not repository links**; `/ESSENCE/` and `/BEING/` paths are
CORE reader paths. UUIDs identify canonical records; a pair of UUIDs means the
endpoints of the indicated run in canonical order, not an invented paragraph
numbering system. The source ledger contains addresses and titles only. The
reading notes are paraphrases; the architectural inferences are marked separately.
CORE's indexed transcription has not been manually proofread in full; this is
not new facsimile or transcription acceptance.

## 2. Source ledger

The keys L0–L9 below resolve every textual reference in the notes and register
to edition, logical section, printed pages and stable records. All document
paths are relative to the private corpus root.

| Key | Logical location and document | Printed pages and canonical records used |
| --- | --- | --- |
| L0 | Being → Measure → The becoming of essence → C. Transition into essence; `hegel/being/iii-measure/3-the-becoming-of-essence.md`; reader `/BEING/iii-measure/3-the-becoming-of-essence/c-transition-into-essence.txt` | pp. 333–335; `79b2f152-cc26-4a22-a197-261df5419f09` through `e473873c-6d86-4029-bb5d-d71ecc8f6e1f`. |
| L1 | Essence, doctrine opening and division; `hegel/essence/preliminary/essence.md`; reader `/ESSENCE/essence.txt` | pp. 337–339; opening `21f4e2ea-573e-493d-9949-aaa97b67bc49`; criticism of abstraction `319b8071-e53e-4040-8d29-29f737ec2fe7` (pp. 337–338); determining `d51c21ed-6286-4da8-af7c-a16c85cc5628` (pp. 338–339); reflection `9c58bdc2-a23f-4fa0-b3f4-1668a9652d24`, middle/transition `13d100c5-0f18-4a7f-84f0-976c4371dc02`, division `92925627-5fdf-4c21-8ead-8a0276006dbd` and `21f9ba07-0ccf-41dd-affc-b848e58ba5fa` (p. 339). |
| L2 | I. Essence as reflection within, opening; `hegel/essence/i-essence-as-reflection-within/00-introduction.md`. Also I.1 Shine → C. Reflection → 2. External reflection and 3. Determining reflection; `hegel/essence/i-essence-as-reflection-within/1-shine.md` | Opening p. 340, `f3348472-a58c-4068-a155-a1e205cd100e` and `1faa0a0e-7b0d-455d-8846-ee94b0999169`; external reflection pp. 348–350, `c64b2a7d-9651-4d8e-b541-6f751de92074` through `838865b8-eb0a-44f9-b7d4-90990ad68fba`; determining reflection pp. 351–353, `e5a30dcb-17a0-406b-82de-cd0c7ca42584` through `fb86155c-75aa-4eb0-8936-6a1aca255b3d`. |
| L3 | I.2 The essentialities or the determinations of reflection: opening, A. Identity, B. Difference → 2. Diversity; `hegel/essence/i-essence-as-reflection-within/2-the-essentialities-or-the-determinations-of-reflection.md` | Opening p. 354, `6e9754ab-58fd-4966-b1b4-de903918740d` through `3eceeb82-fec0-4eac-a1f5-e9661fb3374e`; identity p. 356, `1fcf1ba9-87b7-4a3e-a632-5516a15785e1` through `aef60ecc-8476-4a75-aaad-b97f80a6a036`; diversity pp. 362–365, `9b8b853c-fd42-4b54-a448-c84c72c90fa7` through `da126faa-5a34-48a4-8280-8ff2288361a5`; comparison specifically pp. 363–364, `c2ba0187-31a0-46f6-9af1-e5cff34b3c81` and `fe8b034f-ff6a-4b4d-8445-4fbec9a10f59`. |
| L4 | I.3 Ground, opening; C. Condition → c. Procession of the fact into concrete existence; `hegel/essence/i-essence-as-reflection-within/3-ground.md`; transition reader `/ESSENCE/i-essence-as-reflection-within/3-ground/c-condition/c-procession-of-the-fact-into-concrete-existence.txt` | Opening pp. 386–388, `1a70fa5a-e240-43a9-bd9a-f692438b247b` through `7dd0ca8a-b9e3-4aec-88a7-dbafb9a655c8`; transition pp. 414–417, `83499489-acb6-4042-bafc-c402e56d7caa` through `672f538d-f99e-404e-ad0f-da39ba285fb0`; ground's disappearance specifically `208ca93b-9dac-46ef-8caa-4492ef4bd3af` (p. 417). |
| L5 | II. Appearance, opening; `hegel/essence/ii-appearance/00-introduction.md`. Also II.2 Appearance, chapter opening; `hegel/essence/ii-appearance/2-appearance.md` | Section pp. 418–419, `211b4b78-b949-4791-9d91-a8cc294856e7` through `8859f459-90a6-4a30-beaf-90c9a4d050e4`; chapter pp. 437–438, `76597585-142a-4566-8452-87a81687ddb3` through `f15fa8ec-0b2b-4b81-9cb4-6d53c823a394`. |
| L6 | II.3 The essential relation → C. Relation of outer and inner, including concluding transition; `hegel/essence/ii-appearance/3-the-essential-relation.md`; reader `/ESSENCE/ii-appearance/3-the-essential-relation/c-relation-of-outer-and-inner` | pp. 460–464, `9bf7465a-915c-46b9-bb28-4dd2c270fbd0` through `e2a53e3e-fd2b-4938-9002-40e19a5cc5ea`; conclusion especially `ddae6490-bc6e-4d39-a4fc-e29fa5f34852` through `e2a53e3e-fd2b-4938-9002-40e19a5cc5ea` (pp. 463–464). |
| L7 | III. Actuality, opening and division; `hegel/essence/iii-actuality/00-introduction.md` | p. 465, `be30b64c-cd89-4150-b147-5e9c5ce556f0` through `59694340-11ef-4927-bcd4-e2a34137c713`. |
| L8 | III.2 Actuality, chapter opening; `hegel/essence/iii-actuality/2-actuality.md` | pp. 477–478, `4c3aca9f-5ca6-4d15-8745-6a3fca51acea` through `ddf68ebb-09f3-4a83-8c9e-8d8fba711d65`; distinction from being/concrete existence especially `fe90e414-187c-4351-a036-a7b1d4b25fda` (pp. 477–478). |
| L9 | III.3 The absolute relation → C. Reciprocity of action, end of Essence; `hegel/essence/iii-actuality/3-the-absolute-relation.md`; reader `/ESSENCE/iii-actuality/3-the-absolute-relation/c-reciprocity-of-action.txt` | pp. 503–505, `d0f6e205-4c67-434e-a83f-9dd5395ba041` through `f5215e76-2c35-4c46-bb9c-14175f473144`. |

## 3. Reading notes: text before placement

### 3.1 The division and its starting difficulty

**Text (L0, pp. 333–335; L1, pp. 337–339).** The transition out of Being
does not merely replace an object with a concealed object behind it: the
determinations lose their supposed independence and become moments of the
unity to which they refer. The doctrine opening warns against an abstraction
that removes determinations yet leaves them unchanged outside an empty
essence. Essence's determining instead belongs to its own negative movement;
its distinctions remain within its unity. The closing division distinguishes
remaining within itself, emerging in concrete existence and appearance, and
unity with that appearance as actuality (L1, p. 339).

**Architectural interpretation.** A renamed directory would not answer this
difficulty. The useful question is how an analysis constitutes its objects and
what the resulting abstraction retains or loses. The current source/feature
distinction offers an engineering place to ask that question, but it does not
demonstrate the immanent movement described in L1. Every proposal below is an
analogy subject to this limit.

### 3.2 Essence as Reflection within Itself

**Text (L2, p. 340).** The first section initially confronts the opposition
of essential and unessential; the latter becomes shine belonging to essence's
own positing. The section proceeds through reflection, its determinations,
and ground, whose movement leads into concrete existence and appearance.
This is why the first section cannot simply mean an interior cut off from
what follows (L2, p. 340; L4, pp. 386–388, 414–417).

**Text (L2, pp. 348–353).** External reflection starts from an immediate
it treats as presupposed and applies determinations to it. Hegel's argument
does not leave this separation intact: determining reflection unites positing
with external reflection, and its determinations combine dependence on
reflection with their own reflected subsistence. The account therefore gives
a standard against which merely external classification can be criticized;
it does not simply endorse classification of independently given objects
(L2, pp. 349–353).

**Text (L3, pp. 354, 356, 362–365).** Identity here is not a bare equality
produced by leaving an excluded other untouched. Difference is developed
through diversity and opposition; the chapter opening also names contradiction
and return to ground. In the diversity passage, likeness and unlikeness
depend initially on an outside standpoint that compares. Their subsequent
movement undermines their indifferent separation (L3, pp. 363–365).

**Architectural interpretation.** A tokenizer fixes which variants count as
one item; scopes and masks fix which items can enter a study. A comparison
adds a declared standpoint with its denominators and reference population.
These are reasons to study these operations together under reflection,
rather than distributing normalization, counting and comparison solely by
their names. This remains an external computational determination of supplied
text. Normalized token equality supplies no evidence of essential identity
in the sense of L3. Nor do zero counts, rule failures or disagreement between
methods by themselves instantiate the contradiction announced on p. 354.

**Text (L4, pp. 386–388, 414–417).** Ground is developed out of reflected
determination, not supplied as a second, unrelated foundation. Ground and
condition presuppose one another; their mediation culminates in concrete
existence. In the final transition ground does not remain underneath the
grounded as a separate substrate (L4, p. 417).

**Architectural interpretation.** This transition prevents treating a
permanent service dependency as a literal ground/grounded relation. CORE
remains separately callable while an experiment runs and after it ends.
Its practical exemption comes from SPECULATIVE, not from equating a database,
fingerprint or provider with Hegel's ground.

### 3.3 Appearance

**Text (L5, pp. 418–419).** The second section develops essence's emergence
into concrete existence, then appearance, then essential relation. In this
movement the determinations acquire subsistence; the essential belongs in
what appears. The chapter opening expressly rejects making appearance the
verdict of an alien reflection comparing an essence with existence (L5,
p. 437). It develops law, the opposition of appearing and essential worlds,
and relation (L5, p. 438). Appearance is therefore more determined than
simply being visible to someone.

**Text (L6, pp. 460–464).** The relation of outer and inner first exposes
two incomplete ways of holding their identity: a common content with forms
still external to it, and a formal conversion between the opposed terms.
The conclusion makes each side the totality through its other and unites
content and form in self-expression; the essential relation thereby becomes
actuality (L6, pp. 463–464).

**Architectural interpretation.** A screen or exported view is not placed in
Appearance merely because it presents results. A more demanding possible
analogy would concern how an analytical determination obtains expression in
source-linked results, and how that expression forces revision of the
determination. Today's table rendering and prose export alone do not establish
that relation. I therefore leave Appearance without a positive module proposal
from this inventory, while retaining it as a substantive alternative for later
investigation. In particular, the prose policy is currently an externally
declared selection, which makes reflection the better provisional fit.

### 3.4 Actuality and the exit from Essence

**Text (L7, p. 465; L8, pp. 477–478).** Actuality is the developed unity of
essence and concrete existence, following the relation of inner and outer.
Its opening distinguishes the absolute, actuality proper with possibility
and necessity, and absolute relation. The chapter on actuality explicitly
distinguishes it from both initial being and concrete existence; mere
presence does not suffice (L8, pp. 477–478).

**Text (L9, pp. 503–505).** At the end, reciprocity reworks the apparent
independence of active and passive substances. The cause's relation to its
effect becomes a relation back to itself; the argument manifests necessity
as freedom and concludes with the concept through universal, singular and
particular determinations. The exit is a transformation of the earlier
relations, not their simple deletion (L9, pp. 504–505).

**Architectural interpretation.** Running an algorithm, recomputing a receipt,
or atomically publishing a reviewed copy is insufficient grounds for an
Actuality placement. Those operations supply useful evidence about a declared
procedure; they do not establish the unity described in L7–L8. Nor does mutual
calling between reader and investigator warrant identifying that exchange
with L9. No present group receives a positive Actuality placement, and this
reading does not authorize developing CONCEPT.

## 4. Code inspection and what the analogy makes questionable

The inventory's module facts, import ledger and protecting tests remain the
coverage map ([§§3–9](INVENTORY_ESSENCE_CORE.md#3-essence-modules-actual-work-and-current-boundaries)).
For these proposals I also inspected current implementation bodies and test
assertions, especially the following seams:

- `tokenization.word_tokens`, `words._METHOD`/validation and providers preserve
  original offsets while normalizing lexical forms. `test_word_frequencies`
  checks casefold/Unicode/apostrophe behavior, unchanged BOM/CRLF bindings,
  whole-token spans and changed unselected bytes. The unit is a reproducible
  method choice, with consequences for what counts as identical.
- `comparison.compare_words` recomputes before deriving measures; `tfidf`
  consumes a complete word receipt. `test_word_comparison` checks denominator
  direction, side swapping, zeros and stale sources. `test_tfidf` checks one
  file/one document, empty rows in N and normalization before truncation.
  A different document unit changes the standpoint of the weighting; a move
  must preserve these choices and their explicit limits.
- `sentences` and `sentence_inputs` share segmentation and providers through
  local reciprocal imports. `test_sentence_providers` checks complete original
  sentences inside spans and four byte-identical v1 receipts. The four known
  rule failures in `test_sentence_study` remain expected failures. Their
  philosophical productivity would be to question the boundary policy, not to
  relabel segmentation failures as a successful dialectic.
- `prose.prose_text`/`export_prose` select features while copying canonical
  metadata and following parent IDs. `test_prose_inputs` checks the separation
  of feature and canonical hashes, preserved prose words, omitted structural
  labels, detached metadata and no source writes. Shared `corpus.markdown`
  serves both canonical indexing and reader typography. The same rendering
  machinery supports different policies; removing an image from features can
  omit philosophically relevant notation even when provenance survives.
- CORE's lazy facade, `corpus.load_corpus_book`, reference/protocol guards and
  contract retain one trust path. `test_core_api` checks shared identities,
  no-write loads, missing-corpus refusal and imports without applications.
  `Book`'s three-doctrine/Arabic-page projection is edition-shaped; snapshots
  remain caller-mutable. Neither is made generic or immutable by a placement.
- Corpus conversion/extraction/ingestion keeps physical evidence, reviewed
  replacements and publication distinct. `test_corpus_ingestion` checks
  existing IDs/metadata, exhaustive dispositions, unchanged baseline, races
  and no-replace publication. Review declaration is not proof of correctness.
  These operations involve interpretation, but currently maintain the corpus
  rather than conduct a research comparison or statistical investigation.

The resulting proposal preserves the positive content of the present cohesive
groups: offsets, reproducibility, explicit policies, source return and guarded
publication. Its criticism of the present layout is bounded: analysis-specific
selection must not become universal corpus truth, and a shared corpus package
must not conceal the distinction between runtime retrieval and import/review
maintenance. No algorithm, schema, public name or deletion policy changes here.

## 5. Proposed placement-register rows

Each row uses [SPECULATIVE §5.3's schema](../../SPECULATIVE.md#53-autonomy-and-final-authority).
L-keys are complete CORE-edition citations through §2; the rationale is **my
architectural interpretation**, not an assertion that Hegel prescribed software
packages. Paths name proposals, not new directories. Deferral at a present path
is a provisional placement with an unresolved classification. Test codes refer
to the [inventory §7](INVENTORY_ESSENCE_CORE.md#7-test-protection-map-and-limits).
CORE and tooling rows explicitly use the practical exceptions in
[SPECULATIVE §§4–6](../../SPECULATIVE.md#4-initial-repository-hierarchy), not an
uncited philosophical exemption.

| Module or function group | Proposed location | Textual grounding | Interpretive rationale, including alternatives | Technical consequences for stage D | Status |
| --- | --- | --- | --- | --- | --- |
| E1. Tokenization, providers, word engine and receipts: `sol/essence/{tokenization,word_inputs,corpus_inputs,words,validation}.py`; method-defined units, admission, binding and recomputation. Shared validation also belongs to E3. | `sol/essence/essence_as_reflection_within_itself/`, retaining cohesive modules. | L1, pp. 337–339; L2, p. 340, pp. 348–353; L3, p. 356. | The study determines which variants and admitted occurrences count as one unit, keeping the policy visible in its receipt. **Alternatives:** BEING Quality/Quantity/Measure could isolate unit-making/counting, but that would separate analysis policy from its bindings and needs Claude's Being reading; CORE would incorrectly universalize experimental eligibility. An ESSENCE-root engine remains viable if the analogy proves unproductive. This proposal does not identify normalization with essential identity. | Preserve offsets, masks, lazy CORE adapters, file-only operation, method versions and exception identity; do not duplicate `validation` for sentences. Audit lazy facade exports and literal patch sites. W/S/T/B tests. | Provisional |
| E2. Word comparison and TF-IDF: `sol/essence/{comparison,tfidf}.py`; relations over complete word receipts. | `sol/essence/essence_as_reflection_within_itself/`, beside E1. | L2, pp. 348–353; L3, pp. 362–365, especially pp. 363–364. | Explicit reference populations, denominators and document units constitute the standpoint of comparison. **Alternatives:** Appearance for source-linked result relations remains possible but current descriptive weighting does not establish L5's mediated appearance; BEING Quantity/Measure would prioritize numeric formulas over the declared analytical standpoint. Actuality is unsupported by mere successful recomputation (L8, pp. 477–478). | Keep shared word validators/receipt, document units, undefined-zero statuses, whole-vocabulary L2 norm before top-N, and export checks. No significance or conceptual-similarity claim. W/T/U tests. | Provisional |
| E3. Sentence segmentation and measurement: `sol/essence/{sentences,sentence_inputs}.py`, with E1 tokenizer/providers/validation; v1/v2 receipts and saved-study helper. | `sol/essence/essence_as_reflection_within_itself/`; move as one change unit with shared dependencies. | L1, pp. 337–339; L2, pp. 348–353. | Boundary rules and resulting statistics determine the object studied together. **Alternatives:** split segmentation into BEING Quality and lengths into Quantity/Measure only after a joint reading establishes a useful seam; leave under ESSENCE root if current reflection fit is rejected. Persistence does not make the entire engine CORE or Actuality. | Preserve reciprocal local imports, complete-sentence span admission, original offsets and v1 fixtures. Keep `save_sentence_result` with its existing safety rules for now; persistence split deferred to P2. S/U/B tests, all four expected failures retained. | Provisional |
| E4. Prose feature policy: `sol/essence/prose.py`, consuming shared canonical visibility. | `sol/essence/essence_as_reflection_within_itself/`; shared parser remains C2. | L1, pp. 337–339 (abstraction's limitation); L2, pp. 348–353; compare L5, pp. 437–438. | Feature exclusion is a declared abstraction over canonical material; preserving metadata makes its loss inspectable. **Alternatives:** Appearance is plausible for a future account of how features express source structure, but a selected view alone is insufficient; CORE must not turn this one experiment policy into canonical plain text. Root-level ESSENCE is the fallback. | Keep CommonMark semantics shared, canonical/feature hashes separate, ancestry and copied attribution intact, freshness at release. Do not make prose eligibility silently depend on reader paths. P/K/A tests and typography consumers. | Provisional |
| E5. Headless adapters: `sol/essence/{cli,word_cli,sentence_cli,tfidf_cli}.py`; shared flags, dispatch and controlled output. | Retain `sol/essence/` as cross-method adapters; no first-level determination assigned yet. | L2, p. 340; L5, pp. 418–419; L7, p. 465 supply distinctions, not an adapter classification. | They orchestrate investigations across methods; engine placement does not determine the location of the command surface. **Alternatives:** colocate each adapter with its engine under Reflection if later coupling warrants it; Appearance merely because output is printed, or Actuality because a command executes, lacks support. These are substantive ESSENCE interfaces, not §6 development tooling. | Later rewrite engine imports while preserving refusal-before-source-access, explicit sources, escaping, `python -m sol.essence.cli` and installed dispatch. Do not split shared provider flags or artifact handling gratuitously. A/W/S/T/B tests. | Provisional; subdivision unresolved |
| E6. Optional UI and reader exchange: `sol/essence/tui/` app, launch, context and study adapters; reader host/Lua and theme imports are dependencies outside Codex's placement scope. | Retain `sol/essence/tui/`; reader host stays pending Claude's rows. | L5, pp. 418–419, 437–438; L6, pp. 460–464; compare L9, pp. 503–505. | Screens, source descriptors and workers present and coordinate investigations. **Alternatives:** Appearance is an open substantive interpretation of source/result relations, not justified just by visible presentation; Actuality cannot be inferred from a working reader round trip. Moving study adapters beside Reflection engines may eventually clarify coupling, but no whole-UI subdivision follows yet. | Preserve ephemeral context, checked IDs/offsets, worker ordering, optional imports, exclusive receipt writes, OSC return and current theme dependency. Coordinate host changes with Claude; no new state owner. U/M/B and reader source guards. | Provisional; subdivision unresolved |
| E7. Catalogs and offline packaging: `sol/essence/{encyclopedia,methods}.py` and their JSON resources. | Retain `sol/essence/` for catalogs; packaging declarations remain ordinary infrastructure. | L1, pp. 337–339 and L2, p. 340 set the interpretive burden; no passage read establishes a catalog determination. | Describing methods, their limits and history differs from executing them. **Alternatives:** Reflection alongside engines could be warranted by future content-specific inquiry; Appearance cannot follow merely from rendering catalog entries. CORE would confuse methodological descriptions with canonical corpus services. | Keep resources with their loaders, attributed excerpts separate from SOL notes, topics separate from runnable methods, fresh loads and optional UI. Update resource/packaging paths together only if later moved. M/U/B tests. | Provisional; subdivision unresolved |
| C1. Verified canonical generation and references: `sol/corpus/contract.py`, `sol/core/{__init__,references,protocol}.py`; shared snapshots, identity, generation, trust and interchange. | Retain present `sol/core/` facade and `sol/corpus/contract.py` backing service under CORE's practical boundary; no logical subdivision. | Practical authority: SPECULATIVE §4.1; L3, p. 356 and L4, pp. 386–388, 414–417 are limits on literal identity/ground analogies. | Every consumer needs the same addressable, verified source generation. **Alternatives:** Reflection because validation compares records, or Actuality because checks succeed, would classify by incidental operation and entangle shared trust with experiment policy. A later physical consolidation into `sol/core/` is possible; reading does not settle that package seam. | Keep runtime reads distinct from explicit identity/reindex writers in the same contract module; preserve lazy public exports, redirects, mutable-snapshot guards, cache/action semantics and final batch checks. No API/protocol/corpus policy change. K/Q/R/B and downstream guards. | Provisional; CORE exception holds |
| C2. Shared canonical visibility: `sol/corpus/{markdown,errors}.py`; parser, plain projection and shared error, used by E4, contract and reader typography. | Retain `sol/corpus/` as shared CORE backing service; no logical subdivision. | Practical authority: SPECULATIVE §4.1; contrast external abstraction in L1, pp. 337–338 with the experimental policy in E4. | Shared visibility must stay consistent across indexing and reading. **Alternatives:** move with E4 under Reflection would make shared source semantics belong to one investigation; Appearance based on rendering alone fails L5, pp. 437–438. A shared location within `sol/core/` is technically possible later. | Preserve lazy Markdown dependency and canonical note/math/code rules; exclusion options remain explicitly selected by analyses, not new defaults. Retain `CorpusError` identity. K/P/B and typography tests. | Provisional; CORE exception holds |
| C3. Models, virtual paths and reader projection: `sol/core/{models,paths,corpus}.py`; addressability, literal retrieval and current edition-shaped `Book`. | Retain `sol/core/`, including current projection pending a separate projection-boundary decision. | Practical authority: SPECULATIVE §4.1; L4, p. 417 excludes deriving a permanent service substrate from Hegel's transition. | Models/path resolution are shared by reader, converter and investigator; literal search here retrieves rather than performs a research analysis. **Alternatives:** move Hegel-specific `load_corpus_book` into BEING while retaining generic CORE snapshots/models; this is the strongest later separation, but cannot be resolved from Essence's section division alone. Moving everything to BEING would break genuinely shared use; Appearance is not equivalent to projection. | Disclose author/doctrine/Arabic-page assumptions. Preserve UUID-backed paths, full graph beside reader view, protocol cache seeding and caller-mutable collections; no generic multi-corpus redesign. R/K/Q/B and reader tests. | Provisional; shared CORE exception holds, projection seam unresolved |
| C4. Edition-bound conversion: `sol/corpus/{edition,layout,structure,notes,references,convert}.py`, package marker; audited geometry, note/reference segmentation and canonical publication. | Retain `sol/corpus/` as explicit CORE corpus-maintenance machinery, separate from runtime load routes; no logical subdivision. | Practical authority: SPECULATIVE §4.1; L1, pp. 337–339 and L5, pp. 418–419 do not identify physical extraction with a logical transition. | Its present purpose is source organization and audited corpus construction. **Alternatives:** ESSENCE Reflection for research into segmentation assumptions is a real future use, but moving the importer there now would give an investigation ownership of corpus maintenance. Treating publication as Actuality is unsupported. CORE exemption here is purpose-specific, not granted to arbitrary future analytical code in `corpus/`. | Preserve audited source accounting, generated vs permanent IDs, note/attribution boundaries and no-clobber publication. Reader edition-constant imports remain a known seam for coordination with Claude; never introduce conversion into ordinary verified reading. V/K/X/B tests. | Provisional; CORE maintenance exception holds |
| C5. Extraction, review and ingestion: `sol/corpus/backends/{__init__,opendataloader}.py`, `extraction.py`, `ingest.py`, dispatched by `convert.py`. | Retain current corpus-maintenance boundary, with candidate evidence, declared review and accepted copy kept distinct; no logical subdivision. | Practical authority: SPECULATIVE §4.1; compare L4, pp. 414–417 and L7–L8, pp. 465, 477–478; neither grounds a software publication analogy. | Physical evidence becomes an allowed correction only through explicit review and guarded publication; this is corpus custody. **Alternatives:** split research evaluation of extraction into ESSENCE if such work emerges; the existing local backend and review validator do not themselves conduct that investigation. Actuality cannot mean that reviewed bytes reached disk. | Preserve lazy SDK boundary, provenance without false authentication, exhaustive review dispositions, approved existing-record changes only, private staging and atomic new-copy publication. No source/baseline/workspace overwrite or new dependency. X/I/K/B tests. | Provisional; CORE maintenance exception holds |
| P1. Local preferences: `sol/core/config.py`, corpus/theme discovery and settings. | Retain `sol/core/config.py` as shared configuration service; no logical subdivision. | Practical authority: SPECULATIVE §§4.1, 6; no textual placement claimed. | Corpus discovery serves multiple components; saved theme names do not make the whole service a reader responsibility. **Alternatives:** extract presentation preferences into BEING after coordinating with Claude; a neutral configuration module outside CORE is also viable. Neither requires a philosophical determination now. | Preserve explicit/env/cwd/saved/install precedence, refusal of broken choices, atomic writes and fixed checkout-recognition assumptions. Audit `__file__` behavior if later moved. R/B tests. | Provisional; practical exception holds |
| P2. Study persistence and UI state: `sentences.save_sentence_result`, TUI exclusive writers, `tui/context.py` investigation state; current ESSENCE owners. | Retain colocated with E3/E6 for now; shared persistence destination unresolved. | Practical authority: SPECULATIVE §4.1; L7–L8, pp. 465, 477–478 do not make persistence Actuality. | Method receipts, screen state and durable shared research state have different responsibilities and failure rules. **Alternatives:** a shared CORE storage primitive with ESSENCE-owned receipt semantics may become useful; moving all study/UI state into CORE now would silently redefine ownership and conflate it with workspace tables. A dedicated ESSENCE storage module is another later option. | Preserve owner-only/exclusive writes and existing context lifetime; relocation must not become a schema migration or authorize new writes. S/U tests. Coordinate with P3 before any shared-store proposal. | Provisional; classification unresolved |
| P3. External shared workspace services/storage, referenced by inventory §8 but physically `sol/workspace/`, in Claude's scope. | No Codex relocation proposal; intended shared persistent-state service belongs within CORE's practical remit, exact split coordinated with Claude. | Practical authority: SPECULATIVE §4.1; CORE §1 records the existing open question. No logical determination inferred from these passages. | **Alternatives:** CORE store with BEING interaction services, or present package retained behind a shared boundary. Essence's division does not decide which current workspace operations are shared versus reader-specific. Do not claim CORE currently owns this store. | Preserve current schema, author/freshness/revision guards and public contracts; no migration. Claude supplies module-level rows from the BEING inventory before stage D touches these files. | Provisional; joint boundary unresolved |
| D1. Development tools and packaging: `scripts/{check_docs,install,reader_timings}.py`, CI, fixtures and package-data declarations. | Keep conventional `scripts/`, tests, configuration and CI locations. | Practical authority: SPECULATIVE §6; no Hegelian subdivision asserted. | They validate, install, package or measure the product rather than supply a logical phase. **Alternatives:** classifying timing as Quantity or docs rendering as Appearance gives names priority over responsibility. Philosophical investigation of these tools remains possible without relocating them. | Keep product imports visible, installer consent/archive guards, temporary timing workspaces, resources and public entry points protected. Docs check and D/B tests; no new infrastructure. | Provisional; infrastructure exception holds |

## 6. Coverage and decisions left open

All inventory §8 groups have rows: tokenization/providers/words → E1;
comparison/TF-IDF → E2; sentences → E3; prose/visibility → E4/C2;
verified generation/references → C1/C3; edition conversion → C4;
extraction/review/ingestion → C5; headless adapters → E5; UI/reader exchange →
E6; catalogs/packaging → E7/D1; persistence/preferences → P1–P3; tools → D1.
All eight CORE modules are covered in C1, C3 and P1; all fourteen inventoried
corpus modules are covered in C1, C2, C4 and C5. ESSENCE's lazy `__init__.py`
stays as the public facade with E5; the stage B empty division markers remain
unchanged. No file is inferred to belong to a subdivision just because a
caller does.

The practical CORE exception holds for shared corpus/runtime services and
present corpus-custody operations, with explicit qualifications for the
edition-shaped reader projection and maintenance interpretation. It does not
extend to ESSENCE's experiment selection or weighting merely because they
consume CORE. Preference storage remains practical shared infrastructure;
study/UI persistence and the workspace split require coordinated examination.

Before stage D, Claude should review whether Reflection explains E1–E4 better
than a common ESSENCE-root engine group, and bring the Being reading to the
unit/count/measure alternative. Appearance and Actuality need positive,
function-specific arguments before they receive current modules. Their empty
status is a result of this limited proposal, not a judgment that computational
work can never belong there. No deeper logical directories, contract changes
or reserved decisions are implemented or needed to make these proposals
reviewable.
