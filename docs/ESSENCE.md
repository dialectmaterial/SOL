# SOL ESSENCE — Computational Inquiry and Reproducible Experiments

**Status:** implemented foundation and bounded research roadmap, 17 October 2026.  
**Repository baseline:** `dialectmaterial/SOL` `main` at `1d200e4fcbff1ca69f48b5dc96c55765f215f303`.  
**Companions:** [Architecture](ARCHITECTURE.md) · [BEING](BEING.md) · [CORE](CORE.md).

## 1. Purpose

ESSENCE investigates patterns, distinctions and relations in the present *Science of Logic* corpus, using established statistical, linguistic, and machine-learning tools. It must form **one reversible inquiry with BEING** rather than become a separate statistics application. The object is identifiable source text; the user chooses a question/method; the result can be checked and traced back to the text.

**Guiding rule:** reuse mature software (Python scientific stack, spaCy/Stanza, scikit-learn, PyTorch, model libraries, TensorFlow Projector, command-line tools or R when justified) through stable inputs/outputs. Write SOL-specific adapters for provenance, state, reproducibility and return-to-reading. Do not reimplement algorithms simply to place the SOL name on them. Never make CORE load a model or runtime merely to inspect a book.

The relation between Hegel's explicit argument and the output of an algorithm is always **a research question**. Model similarity and a visual cluster are not equivalent to the logical movement of a concept. Preserve the boundary between measurement, statistical inference, interpretive hypothesis and argued philosophical necessity.

## 2. What exists now

ESSENCE is not currently a complete model environment. The inspected code contains:

- `sol.essence.prose.export_prose` and `sol analyze prose --json`: a **verified, Hegel-specific** prose-only analysis view over the current corpus.
- `sol analyze term WORD`: a reproducible lexical-distribution experiment with reference-bound source matches; `sol analyze check FILE` checks its result against a current corpus generation.
- `sol.core` public snapshot/reference APIs, including source/edition/generation binding and batch captures; these are usable without opening BEING.
- A narrow optional `sol-kitty` + Zsh handoff for a source passage, with an explicit proposed return to BEING. The handoff carries **references**, not an ML result database or unrestricted authority to save notes.
- Checkout-only reading/rendering research, not an installed ESSENCE model suite.

**Not implemented/verified:** fully integrated experiment picker in the Neovim reader; parameter dashboard; GPU/model registry; syntactic research panel; UltraBERT embedding pipeline; TensorFlow Projector launch as a SOL command; durable research context/experiment history; a terminal-independent BEING–ESSENCE UI. Do not describe these as shipping features until code and tests verify them.

### Existing commands

```sh
sol analyze prose
sol analyze prose --json > prose.sol-analysis.json
sol analyze term ground
sol analyze term ground --doctrine essence --limit 5
sol analyze term ground --json > ground.sol-analysis.json
sol analyze check ground.sol-analysis.json
sol reference capture RECORD_UUID --corpus local-corpus | sol reference check --corpus local-corpus
```

The first `prose` command summarizes eligible records. The JSON export is for consumption by scripts. The lexical study measures exact normalized token occurrences and can break results down by the three doctrines, but a word occurrence does not prove concept identity. `check` currently verifies the **term study**, not arbitrary generated model outputs or `prose` exports.

## 3. Proper model inputs: projections, not destructive cleaning

**Current version-1 prose projection** (see the [archived input policy](legacy/PROSE_INPUTS.md)) selects records that are Hegel-attributed `main_text`, with types `paragraph`, `quotation` or `list_item`, excluding pending-review and explicitly generated text. Canonical section/headings, note callouts, image labels, formulas, editorial material and indexes are **not** silently concatenated into feature strings. Heading ancestry, locations, source pages, attribution, source digests, record type and corpus generation are retained as separate metadata. Words such as *Being*, *Remark*, or *Ground* that occur in **actual prose** are not blacklisted. Headings are removed by structural selection, not a word-level blacklist.

Use precisely `passages[].text` as the input to a prose embedding experiment; preserve `passages[].id` as the map back to the corpus. Example:

```python
import json
with open('prose.sol-analysis.json', encoding='utf-8') as f:
    view = json.load(f)
texts = [p['text'] for p in view['passages']]
ids   = [p['id'] for p in view['passages']]
meta  = [p['metadata'] for p in view['passages']]
```

**Decision:** this is one useful projection, **not** the cleaned text for every method. Maintain a typed, versioned preprocessing policy **per experiment**. Sentence length needs sentence segmentation and punctuation. Syntax needs clause/token/POS/dependency information and a declared pipeline. Some rhetorical studies need heading, annotation, note or formula context. Embedding requires explicit passage granularity and truncation/chunking policies. For every experiment, record why features were included or excluded; preserve the unmodified underlying canonical text and make derivations reproducible.

In particular, avoid these errors:

1. Treating a heading in the index as prose because it contains meaningful philosophical vocabulary.
2. Removing legitimate prose words because the same strings occur as heading titles.
3. Vectorizing JSON metadata alongside text, introducing obvious category leakage.
4. Implicitly treating translators' sentences as Hegel's original German syntax.
5. Silently concatenating paragraphs, ignoring section boundaries, or truncating input beyond model limits.
6. Calling distances or embeddings ontological relationships without an independent argument.

## 4. The complete inquiry contract (proposed, not implemented)

The unit of integration should be a **versioned research context**, transportable across terminals and external tools:

```text
origin:       corpus ID + edition/source fingerprint + verified generation
scope:        passage UUID(s) / bounded record span(s), possibly selected codepoint ranges
question:     researcher-entered text; distinct from canonical text
input:        named, versioned projection, ordered IDs, digest per input row
method:       algorithm / model / checkpoint / software versions
parameters:   declared hyperparameters, seed, batching, device and preprocessing policy
result:       immutable artifact path + checksums + metrics/warnings + source-linked rows
navigation:   result-to-source references and original BEING resume context
```

A result should distinguish **reproducing the exact experiment generation** (strict full-corpus snapshot agreement) from **resolving an unchanged passage later** (a possible weaker check, not yet implemented). CORE v1 currently takes the strict position; do not relax that protocol or overwrite stale artifacts without an explicit, separately versioned policy. The result artifact has **no authority** to edit canonical text or store author assertions in a personal workspace. Acceptance of a suggested relation should require deliberate scholarly authorship.

The process should work whether ESSENCE runs as a standalone CLI, in a Neovim-accessible pane, in ordinary Zsh, in Kitty, or opens a browser. Browser visualization is not a violation of the TUI-first direction; forcing browser-grade plots into a terminal would be unnecessary work. **ESSENCE is not a terminal emulator.**

## 5. Prioritized experiments

### Experiment A — syntax and positionality (highest priority)

**Research question:** how do sentence lengths and selected grammatical constructions vary across paragraphs and across positions within a passage or chapter of Hegel's *Science of Logic* in the current **English translation**?

Design a minimal, inspectable analysis rather than jumping straight to a large model:

1. Select the current passage, a bounded paragraph window, or an explicit chapter from BEING; send ordered UUIDs and exact source scope.
2. Extract eligible prose with provenance. Handle paragraph and sentence boundaries explicitly; choose/document tokenizer and sentence segmenter; assess quotation/semicolon/abbreviation behavior on Hegel examples.
3. Compute sentence length in word tokens (and optionally characters), distributions by position within a paragraph/chapter, and a deliberately small set of POS/dependency statistics if a tagged model is available.
4. Report counts, denominators, missing data, pipeline confidence and unusual segmentation, not only a figure.
5. Present an inspectable table/plot with every observation linked to the source paragraph; selecting a record navigates to it in BEING, with a way to resume the original reading context.
6. Save versioned inputs/method/output. Validate that a re-run on the same source and method is reproducible within the stated determinism limits.

A sentence-length comparison can be deterministic, cheap, and independently validated against a hand-checked sample. POS tagging and parsing will be probabilistic/error-prone, so present them as **model annotations**, not source facts. The linguistic conclusions describe the chosen translator's text; contrast with Hegel's German only if a distinct German source is actually available and audited in a future research cycle.

### Experiment B — embeddings and TensorFlow Embedding Projector

**Research question:** what textual neighborhoods does a selected *embedding method* place near a given passage, and how stable are these neighborhoods under model, granularity and projection choices?

Build one controlled, reproducible local embedding experiment. Compare model suitability/requirements rather than chasing model releases. **UltraBERT** is a possible candidate discussed in the project, not an adopted or verified local dependency in this baseline. Confirm the exact released checkpoint, intended use, language coverage, embedding extraction method, token/window limits and license **before** integration. A classifier backbone is not automatically an optimal sentence-embedding model; benchmark against a purpose-built sentence-embedding baseline.

For each row preserve: source UUID, text digest, model input length, truncation/chunking, language, provenance, relevant hierarchy labels (as metadata, *not* embedding input), and a stable row order. Compute numeric vectors; check all are same dimensionality, finite, and aligned with metadata. Export separate local TSV files: a numeric vectors TSV (one row per example, same dimension throughout) and a corresponding metadata TSV (one row per vector, with clearly labeled fields). Include UUID and source location in metadata. Support the **TensorFlow Embedding Projector** through local file loading and/or an opt-in launch path. Do not expose private copyrighted text via an external upload without an explicit user decision; evaluate the privacy characteristics of the chosen viewer/mode.

Report nearest neighbors in original embedding space separately from 2-D/3-D PCA, t-SNE or UMAP visualizations. Choice of projection, random seed, perplexity/neighbors and subsampling change visible clusters. Do not claim that Cartesian appearance proves a logical relation, a stable taxonomy or successful classification. If labels derive from Hegel's section headings, isolate them as supervised/evaluation `y`, and split train/test data by meaningful contiguous sections to reduce leakage from adjacent prose.

### Experiments after these two

Only after the workflow is proven: lexical concordances and collocations, full dependency patterns, cross-section retrieval, topic models, supervised classifiers, passage alignment for new audited editions, alternate languages, and user-authored relational hypotheses. Do not implement a model store or experimental UI with dozens of hyperparameter controls before one method works end to end.

## 6. The present lexical experiment as a reference

The shipped term study normalizes Unicode token spellings, counts full-word matches, reports totals and normalized frequencies per 10,000 eligible tokens, and records contributing passage IDs/pages. It filters explicit attributed main-text records and review flags rather than reinterpreting the document tree. Results retain a method identifier, source and generation hashes and can be verified against the same corpus; changing even unrelated canonical material invalidates a strict v1 study check. Zero-token groups have undefined rate, not a manufactured zero. A source match is *lexical evidence*, not the classification of the underlying philosophical concept.

With the optional **existing** Kitty handoff, one can open an ESSENCE Zsh pane from the compatibility reader workflow, execute an analysis, publish a return UUID, and accept the proposed navigation back in BEING. This validates reference passing, **not** a full model-output/parameter/visualization pipeline. Preserve its safety and permissions model while researching a terminal-independent equivalent.

## 7. ML roadmap: evidence, not a speculative catalog

The user described a newly created file about the historical development of machine/deep-learning models. **It was not visible in GitHub `main` at this baseline and was not available for review.** Therefore this document does **not** claim to integrate its contents. Preserve the possibility of adding a short, historically situated rationale for model families once the actual file is supplied. Avoid invented claims about a specific model's architecture, release date, parameter count or embedding quality.

A good model inventory should distinguish:

| Family | Appropriate role in SOL | Critical caution |
|---|---|---|
| Hand-coded lexical/statistical methods | Auditable baselines, concordance and length distributions | Counts are not semantic interpretation |
| Classical NLP, POS/dependency parsers | Measurable syntactic hypotheses | Model errors and translation dependency |
| Sparse vectors/TF-IDF | Transparent lexical similarity baseline | Shared vocabulary, not necessarily meaning |
| Static word vectors | Word-distribution investigation | Polysemy and context compression |
| Transformer encoder embeddings | Context-aware passage retrieval/classification | Pooling, model objective, input length, domain, language |
| Decoder/LLM prompting | Hypotheses, summaries and exploratory analyses | Nondeterminism, hallucination, provenance, leakage |
| Dimensionality reduction | Inspection of high-dimensional output | Graphical proximity is representation-dependent |

This classification is a **provisional methods map**, not a statement that all are integrated in code or that model families follow a teleological historical progression.

## 8. Developer acceptance and prohibitions

- Read current `sol/essence/`, `sol/core/`, docs/tests, and Git status first. Keep experiments opt-in and separate from ordinary reading/install.
- Make the first syntax experiment run on a verified corpus with exact input rows and a source-return mechanism. Produce a machine-readable artifact and a readable summary.
- Do not silently download models, upload copyrighted text, contact remote APIs, or install GPU frameworks during ordinary reader startup.
- Test malformed/empty input, Unicode, missing paragraphs, flagged prose, pipeline errors, corpus changes, interrupted runs, altered row order, mismatched IDs, nonfinite vectors and unavailable optional dependencies.
- Use a pinned environment/checkpoint and report memory/VRAM and CPU/GPU fallbacks where applicable; no assumed acceleration.
- Keep artifacts outside Git; include a method-specific verifier before treating generated files as reusable evidence.
- Preserve original read position and source-linked result navigation as distinct operations.
- Do not allow model output to create canonical records or philosophical workspace assertions automatically.

**Source lineage:** consolidated from installed `sol.essence` implementation and tests, prose-input policy, term study, reference protocol, handoff, modularity/usage manuals, research discussions and the present 17 October priorities. Archived historical details should remain accessible under `docs/legacy/`.
