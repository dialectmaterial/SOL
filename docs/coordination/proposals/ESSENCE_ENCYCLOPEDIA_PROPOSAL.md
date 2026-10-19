# Proposal: the ESSENCE encyclopedia

**Status:** proposal for maintainer decision; no schema, command or runtime is
implemented or adopted by this document. **Prepared:** Codex, 19 October 2026.

This proposes the stage 4 content and checking boundary requested by
[the assigned task](https://github.com/dialectmaterial/SOL/blob/379553bead8b408ae0fe8636b6528bf9ef3a2209/docs/coordination/CURRENT_TASK.md#codex-proposal-for-the-essence-encyclopedia-stage-4),
under [ESSENCE §4](../../ESSENCE.md#4-interaction-model-and-inquiry-contract),
[§5](../../ESSENCE.md#5-prioritized-experiments) and
[§7](../../ESSENCE.md#7-model-history-encyclopedia-and-task-registry-proposed).
The four authorities continue to govern SOL. Accepting this proposal as a
document does not approve its proposed public format or CLI. Their adoption is
a **(reserved)** decision for the maintainer, to be recorded in the authorities
before implementation depends on it.

The first useful result is a small collection one can read outside SOL, inspect
as a sourced graph, and check without CORE, a corpus, Textual or a model runtime.
Reading about BERT should neither choose a checkpoint nor download one. A task
record should explain what an experiment measures; a separately reviewed adapter
record should explain exactly which implementation could produce that output.

## 1. Source format and identity

Recommend UTF-8 CommonMark files with one `json` metadata fence immediately
after the H1 title, followed by ordinary prose under four required headings:
`Purpose`, `Mechanism`, `Evidence and limits`, and `SOL connection`. JSON uses
the standard library and gives field types without introducing a YAML parser.
The prose remains readable with any text editor. The interface renders these
files rather than containing a second copy of the encyclopedia's content.

Proposed repository layout, created only in a later implementation:

```text
docs/encyclopedia/
  README.md
  references.md
  history/term-specificity-1972.md
  tasks/word-frequencies.md
  adapters/sol-word-frequencies-v1.md
```

Each object has a stable ID such as `history/term-specificity-1972`,
`task/word-frequencies` or `adapter/sol-word-frequencies-v1`. The singular ID
namespace is independent of the plural directory name. IDs contain lowercase
ASCII letters, digits and hyphens in exactly two path components; they are
identifiers, never paths to open. Renaming a title does not rename its ID.
The kind determines its directory and filename. A deliberate incompatible
method change gets a new adapter ID; an editorial correction keeps its ID.
Git records revisions. A deprecated record remains resolvable, states why and
may name a replacement; it is not silently redirected or deleted.

The proposed metadata envelope is `format: "sol.encyclopedia-entry"`,
`version: 1`. Reject duplicate JSON keys and unrecognized versions or fields.
Schema changes need an explicit compatibility decision; a misspelling must not
quietly become an extension. Do not embed executable code, Jinja, imports or
download instructions in metadata. An entrypoint is descriptive data only.

Common required fields:

| Field | Proposed meaning |
| --- | --- |
| `format`, `version`, `id`, `kind`, `title` | Envelope, stable identity; kind is `history`, `task` or `adapter`. |
| `editorial` | `state` (`draft`, `reviewed`, `deprecated`), `contributors`, `updated` (ISO date), `reviewer` (nullable), `reviewed` (nullable ISO date), `superseded_by` (nullable ID). Contributors wrote the entry; they are not necessarily the cited authors. |
| `sources` | Unique source IDs resolved in `references.md`; every evidence citation must occur here. |
| `evidence` | Records with `supports` (JSON pointers or `body:<heading-slug>`), `source`, precise `locator`, and epistemic `status` as defined in §3. |
| `relations` | Directed, cited relations (§3); an empty list explicitly means no relation has yet been established. |
| `method_links` | `{method, source, locator}` links to SOL method identifiers at a pinned source revision; an empty list is allowed. |
| `unknowns` | Explicit unresolved questions; use `needs a source` when the gap is evidence. No guessed dates, scores, licenses or predecessor links. |
| `spec` | The kind-specific record described below. |

All fields occur even when their value is an empty list or an allowed `null`.
Null means unknown or inapplicable as explained in `unknowns`/prose, never zero
or a successful measurement. Drafts may be incomplete; a reviewed historical
entry must have its origin, architecture and objective supported. Task contracts
must be specific enough to distinguish word tokens, subword tokens, sentences
and vectors. An adapter cannot be offered as runnable while required version,
license, input limit or output-contract information remains unknown.

`references.md` uses the same H1/fence/prose convention, with
`format: "sol.encyclopedia-references"`, `version: 1`, and a `sources` array.
Every source record contains `id`, `type`, `authors`, `year`, `title`, `venue`,
`url`, nullable `doi`, nullable `revision`, `access` and `checked` (ISO date).
`access` distinguishes `metadata`, `abstract`, `sections` (named in notes) and
`full_text`. Software sources use a repository URL, full commit revision and
repository as venue; unknown personal authorship is stated, not invented.
Reference prose records access limitations and version/reprint distinctions.

## 2. The three knowledge objects

### Historical entry

| `spec` field | Required content |
| --- | --- |
| `publication_year` | Year of the cited originating work, distinguishing a preprint from a later publication in the prose. |
| `origin` | Source ID of that work, not a claim to have established absolute historical priority. |
| `architecture` | Mechanism and representation; a statistical rule may explicitly have no neural architecture. |
| `objective` | Training or analytical objective, including the unit being predicted or weighted. |
| `claimed_advance` | The authors' stated response to an inadequacy, attributed and bounded to their evidence. |
| `limitations` | Explicit author-reported limits and separately labelled editorial cautions. |

Predecessors and responses live in `relations`, with evidence. Year order does
not establish influence. Reported scores require task, dataset/version, split,
metric, baseline, experimental conditions and locator. If these cannot be
checked, omit the score and state the gap. A historical claim about an encoder
does not establish the suitability of any present checkpoint for Hegel.

### Task/capability record

| `spec` field | Required content |
| --- | --- |
| `family` | One of tokenization, lexical-counting, tagging, embedding, retrieval, classification, generation or evaluation; extensions need review. |
| `input` | Shape, units, granularity, language assumptions, required bindings and scope semantics. |
| `output` | Shape, units, ordering, missing-value meaning and source correspondence. |
| `preprocessing` | Required declared policies; no implicit universal cleaned text. |
| `evaluation` | Task, measures, denominators, exclusions, uncertainty and reproducibility requirements. |
| `limitations` | Interpretive limits and conditions under which comparison would be misleading. |

A task ID denotes an I/O and evaluation question, not a model family. Two
implementations become comparable only when their inputs, evaluation protocol
and measures are commensurable. A classifier's accuracy and an embedding's
cosine similarity are different quantities. General task prose can describe
variants, but an adapter must bind an exact variant and artifact contract.

### Runnable adapter record

| `spec` field | Required content |
| --- | --- |
| `task` | One task ID; split records when capabilities have materially different contracts. |
| `implementation` | Exact package/version, repository/full revision and descriptive entrypoint. A release string alone is insufficient for a modified checkout. |
| `checkpoint` | Exact immutable checkpoint revision and weight/tokenizer digests, or `null` for a method with no learned weights. |
| `license` | Separately identified code, weights and tokenizer/data terms, with source locators; nullable only in a draft. No inference from a paper's license. |
| `device` | Supported/expected device and known resource requirements; unmeasured memory is explicitly unknown. |
| `input_limits` | Byte, token, context/window and batching bounds; truncation/chunking policy. Distinguish bytes from codepoints and subword tokens. |
| `output` | Exact protocol/version or documented tensor shape, dimension, dtype, row alignment and missing-value policy. |
| `determinism` | Relevant method/runtime versions, seeds and reproducibility limitations. |
| `effects` | Network, downloads, writes and CORE needs, including which operation would cause them. |
| `readiness` | `draft` or `specified`; `specified` means metadata complete, not installed, trusted, benchmarked or enabled. |

For a learned adapter, also document model objective, language/domain coverage,
pooling, normalization and how long inputs are handled in the required prose.
No learned adapter is proposed for activation in stage 4. A later runtime can
map a reviewed adapter ID to a code-owned implementation allowlist; it must not
import an arbitrary entrypoint named by a Markdown file.

## 3. A genealogy with inspectable claims

Store an outgoing edge on its source object, with `to`, `predicate`,
`statement`, `status` and `evidence` (one or more `{source, locator}` citations).
The containing object supplies `from`. Every target must resolve to an object
in the catalog. Evidence sources must resolve too. The initial predicates are
`uses_architecture`, `extends`, `addresses_limitation`, `changes_objective` and
`trades_off`; their direction is the subject entry toward the related entry.
Task membership and adapter implementation are typed fields, not historical
influence edges. Shared vocabulary, date proximity or a similarity score must
never create an edge automatically.

Use the same epistemic statuses for edges and evidence assertions:

| Status | Meaning and editorial requirement |
| --- | --- |
| `source_report` | The cited author explicitly makes the attributed claim; it is not independently verified truth. |
| `editorial_inference` | An editor derives this limited relation from cited passages, explaining the reasoning in `statement`. |
| `contested` | Conflicting interpretations are described, with citations for each side. |
| `needs_source` | A proposed assertion awaiting evidence; draft only, never presented as an established edge. |

These are separate from editorial state. A reviewed inference remains an
inference. Every edge has a locator and nonempty evidence; even a draft
`needs_source` edge must cite material motivating the question, while naming
the missing support. An entirely unsourced hunch belongs in `unknowns`, not in
the graph. A `trades_off` edge must name the task, metric, resource measure and
conditions; “faster and better” without those cannot pass editorial review.

For example, once both historical nodes exist, the BERT entry can contain:

```json
{
  "to": "history/transformer-2017",
  "predicate": "uses_architecture",
  "statement": "Devlin and colleagues identify BERT as a bidirectional Transformer encoder based on Vaswani and colleagues' implementation.",
  "status": "source_report",
  "evidence": [{"source": "bert19", "locator": "Section 3, Model Architecture, p. 4173"}]
}
```

The evidence is the checked [BERT paper, §3](https://aclanthology.org/N19-1423.pdf),
not a presumed universal progression from encoder-decoder translation to every
later language task. The renderer should show edge status and citation beside
the relation, allow multiple predecessors and contradictory accounts, and
offer date sorting without implying a single improvement ladder. Cycles are
not structurally forbidden: different kinds of conceptual relation can cycle.

## 4. Sources, editorial review and provenance

For historical attribution use the original publication, author manuscript or
official proceedings; record which version was consulted. For mathematical
definitions an authors' textbook is suitable, but does not establish priority.
For implementation behavior use pinned source code, official versioned API
documentation or a checkpoint's official release/model card and license.
Secondary histories may suggest questions; they do not replace primary
evidence for a genealogy claim. Search snippets, unsourced model summaries and
an agent's recollection do not count as checked sources.

Keep exact author order, year, title, venue and persistent URL/DOI. If any is
uncertain, state `needs a source` rather than filling in a plausible citation.
An accessible abstract supports an abstract-level claim; it cannot support
unseen equations, benchmark details or limitations. A live URL is not evidence
that its claims were read. Record checked date, access scope, section/page or
code symbol and revision. A later reprint must not silently acquire the
original issue's page numbers. Source records are not copies of the paper.

Proposed editorial workflow:

1. Write a draft with evidence for each material mechanism, objective,
   historical and empirical claim. Mark editor interpretations explicitly;
   distinguish paper results from measurements actually made in SOL.
2. Review metadata, cited passages and unsupported language in a PR. A named
   reviewer records the scope checked. An agent label records agent work and
   never pretends that a human read the source. Normal other-agent review can
   check content; reserved decisions still belong to the maintainer.
3. Set `reviewed` only when required claims and contracts have evidence, dates
   and a reviewer. Keep unresolved secondary questions visible. Adapter
   readiness has its separate completeness gate; it does not grant execution.
4. Correct claims through Git, preserving IDs and explaining changed evidence
   in the commit/PR. Deprecation preserves citations and names a replacement
   only when one actually exists.

Use short paraphrases and precise links rather than reproducing papers. Entries
contain no private corpus passages, local paths, workspace data or private
analysis output. A source's publication license is distinct from code/weights
licenses. Checking external links or downloading material is an explicit editor
operation; reading or validating the catalog stays offline.

## 5. Initial coverage and links to SOL

Start with the following bounded reading route. These are proposed records,
not assertions that their runtimes exist. The three examples in §7 are draft
records; the remaining records need writing and review before release.

| Coverage | Objects and evidence to prepare | Honest boundary |
| --- | --- | --- |
| Counts and n-grams | `task/word-frequencies`, `adapter/sol-word-frequencies-v1`; a later `task/ngram-counts` defining n, tokenization and boundary policy. SOL code supplies the existing count method. | SOL currently supplies word frequencies, not the proposed general n-gram counter. An origin/history of n-grams **needs a source**; no priority claim or fictional founding paper. |
| Term specificity and TF-IDF | `history/term-specificity-1972` from `sj72`; `task/tfidf-retrieval` with a precisely chosen formula from `ir08`. | TF-IDF combines term and document-frequency weighting; document boundaries and weighting variants need specifying. SOL word rates are not IDF. |
| Word vectors | `history/word2vec-2013` from `w2v13`; `history/glove-2014` from `glove14`; a word-representation task distinct from passage embedding. | Full mechanism and comparison claims require reading the relevant paper sections, beyond the metadata/abstract checks recorded here. No checkpoint selected. |
| Transformer architecture | `history/transformer-2017` from `transformer17`. | Its originating evaluation concerns sequence transduction; it is not itself a sentence-vector adapter. |
| Transformer encoders | `history/bert-2019` from `bert19`, with the checked architecture edge in §3; a contextual-token representation task. | Pooling and a retrieval evaluation would be separately specified. A pretraining objective does not establish passage-retrieval quality. |

This gives seven method/history topics, with task and adapter records only as
needed to explain them. POS/parsing, decoder prompting and projection methods
remain later coverage, not another implementation queue hidden in this task.

Links to existing SOL methods use exact method identifiers and pinned source
locators, rather than silently claiming those implementations descend from a
paper. At baseline revision
`379553bead8b408ae0fe8636b6528bf9ef3a2209`:

| Existing SOL method | Useful encyclopedia connection | What remains distinct |
| --- | --- | --- |
| `unicode-letter-mark-internal-apostrophe-v1` | Tokenization contract and source codepoint correspondence in [tokenization.py](../../../sol/essence/tokenization.py). | These word units are not a model's subword tokens. |
| `word-frequencies-v1` | Count/rate task and built-in adapter; [words.py](../../../sol/essence/words.py), `_METHOD` and `analyze_words`. | Rates per 10,000 tokens are lexical summaries, not TF-IDF or conceptual classifications. |
| `word-rate-comparison-v1` | Comparative evaluation with explicit denominators; [comparison.py](../../../sol/essence/comparison.py), `_METHOD` and `compare_words`. | Rate difference and an unsmoothed log2 ratio are not significance tests or semantic similarity. |
| `sentence-length-distribution-providers-v1` | A length/evaluation task; [sentences.py](../../../sol/essence/sentences.py) and [sentence_inputs.py](../../../sol/essence/sentence_inputs.py). | `punctuation-rules-v1` has known segmentation limits; v1/v2 artifacts remain distinct. |

The encyclopedia stores descriptions and citations. Future laboratory results
retain their existing source bindings, method versions and numerical caveats;
they should refer to a catalog ID plus catalog revision without replacing the
method identifier. Changing an entry does not reinterpret an old artifact.
No artifact or workspace schema changes are part of this proposal.

## 6. Checked reference records

The following IDs are the source records used by the examples. In the proposed
catalog their fields would be serialized in `references.md` as specified in §1.
For all records, `checked` is **2026-10-19**; `revision` and `doi` are null unless
given. Titles and venues identify the work exactly; the access notes delimit
what this proposal has actually checked.

- **`sj72`**, research paper: Karen Spärck Jones. **1972**.
  *A statistical interpretation of term specificity and its application in
  retrieval*. **Journal of Documentation 28(1): 11–21**.
  [Publisher metadata and abstract](https://www.emerald.com/jd/article-abstract/28/1/11/196227/A-STATISTICAL-INTERPRETATION-OF-TERM-SPECIFICITY?redirectedFrom=fulltext);
  DOI `10.1108/eb026526`. Access: **abstract**, including metadata; full text
  was not available at this publisher page. The sample does not assert an exact
  equation or establish priority for every later TF-IDF variant.
- **`ir08`**, textbook: Christopher D. Manning, Prabhakar Raghavan and Hinrich
  Schütze. **2008**. *Introduction to Information Retrieval*.
  **Cambridge University Press**. [Authors' book site](https://nlp.stanford.edu/IR-book/).
  Access: **sections** 6.2.1,
  [Inverse document frequency](https://nlp.stanford.edu/IR-book/html/htmledition/inverse-document-frequency-1.html),
  and 6.2.2,
  [Tf-idf weighting](https://nlp.stanford.edu/IR-book/html/htmledition/tf-idf-weighting-1.html).
  Document frequency counts documents containing a term; the cited TF-IDF
  definition multiplies term frequency by IDF. This is a definition source,
  not evidence of original invention.
- **`w2v13`**, research paper: Tomas Mikolov, Kai Chen, Greg S. Corrado and
  Jeffrey Dean. **2013**. *Efficient Estimation of Word Representations in Vector
  Space*. **International Conference on Learning Representations** (venue as
  listed by Google Research). [Authors' institutional publication record](https://research.google/pubs/efficient-estimation-of-word-representations-in-vector-space/).
  Access: **abstract**, including metadata. It describes two architectures for
  word representations; no detailed implementation or benchmark transcription
  is claimed checked here.
- **`glove14`**, research paper: Jeffrey Pennington, Richard Socher and
  Christopher Manning. **2014**. *GloVe: Global Vectors for Word Representation*.
  **Proceedings of the 2014 Conference on Empirical Methods in Natural Language
  Processing (EMNLP), 1532–1543**, Association for Computational Linguistics.
  [ACL Anthology record](https://aclanthology.org/D14-1162/);
  DOI `10.3115/v1/D14-1162`. Access: **metadata**. Mechanism, objective and
  genealogy claims still need paper-section review before writing that entry.
- **`transformer17`**, research paper: Ashish Vaswani, Noam Shazeer, Niki Parmar,
  Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser and Illia Polosukhin.
  **2017**. *Attention Is All You Need*. **Advances in Neural Information
  Processing Systems 30 (NIPS 2017)**.
  [Official proceedings](https://proceedings.neurips.cc/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html).
  Access: **abstract**, including metadata. The authors describe an
  attention-based architecture evaluated on two translation tasks; this does
  not establish a general ordering over language methods.
- **`bert19`**, research paper: Jacob Devlin, Ming-Wei Chang, Kenton Lee and
  Kristina Toutanova. **2019**. *BERT: Pre-training of Deep Bidirectional
  Transformers for Language Understanding*. **Proceedings of the 2019 Conference
  of the North American Chapter of the Association for Computational Linguistics:
  Human Language Technologies, Volume 1 (Long and Short Papers), 4171–4186**,
  Association for Computational Linguistics. [ACL Anthology record](https://aclanthology.org/N19-1423/);
  DOI `10.18653/v1/N19-1423`. Access: **sections**: metadata, abstract and
  [paper §3, Model Architecture, p. 4173](https://aclanthology.org/N19-1423.pdf).
  That section explicitly identifies a bidirectional Transformer encoder and
  cites Vaswani et al.; this is the evidence for the worked relation.
- **`sol-counts`**, software: **SOL repository contributors** (collective
  attribution; individual authorship not established here). **2026**.
  *SOL word-frequency implementation*. **dialectmaterial/SOL source repository**.
  [Pinned words.py](https://github.com/dialectmaterial/SOL/blob/379553bead8b408ae0fe8636b6528bf9ef3a2209/sol/essence/words.py).
  Revision `379553bead8b408ae0fe8636b6528bf9ef3a2209`.
  Access: **sections**: `words.py` (`_METHOD`, `analyze_words`, validation),
  `tokenization.py` (`word_tokens`), `word_inputs.py` (providers and bounds),
  `pyproject.toml` (package version). All at that revision. This is a software
  citation, not an invented research publication; license **needs a source**.

## 7. Three complete draft entries

These are entire proposed object files, including required prose and all common
and kind-specific fields. Source IDs resolve to §6's reference records; they
would resolve to `references.md` in an implemented catalog. They intentionally
remain drafts, with no fictitious reviewer. The third is a complete *record of*
an adapter, not a claim that its unresolved license has been cleared. The BERT
edge in §3 is a separate worked relation for later nodes, not a dangling edge
inside these three examples.

### Historical entry: term specificity

````markdown
# Statistical term specificity (1972)

```json
{
  "format": "sol.encyclopedia-entry", "version": 1,
  "id": "history/term-specificity-1972", "kind": "history",
  "title": "Statistical term specificity (1972)",
  "editorial": {
    "state": "draft", "contributors": ["Codex"], "updated": "2026-10-19",
    "reviewer": null, "reviewed": null, "superseded_by": null
  },
  "sources": ["sj72"],
  "evidence": [{
    "supports": ["/spec/publication_year", "/spec/origin", "/spec/architecture", "/spec/objective", "/spec/claimed_advance"],
    "source": "sj72", "locator": "Publisher metadata and abstract",
    "status": "source_report"
  }],
  "relations": [], "method_links": [],
  "unknowns": ["Exact weighting equation and experimental conditions need full-text review; predecessor relations need a source."],
  "spec": {
    "publication_year": 1972, "origin": "sj72",
    "architecture": "Statistical term weighting; no neural architecture.",
    "objective": "Weight retrieval matches using collection frequency.",
    "claimed_advance": "The author reports improved retrieval on three test collections with greater weight for rarer terms.",
    "limitations": ["Editorial caution: the checked abstract alone cannot establish the equation or transfer to SOL's text."]
  }
}
```

## Purpose
Explain a sourced motivation for collection-sensitive weighting.

## Mechanism
The account is limited to the abstract; the exact rule remains unknown.

## Evidence and limits
See sj72, abstract. No benchmark numbers or predecessor edges are asserted.

## SOL connection
A question for a future TF-IDF study; SOL's current word rates do not implement
this collection-sensitive weighting.
````

### Task record: word frequencies

````markdown
# Word frequencies

```json
{
  "format": "sol.encyclopedia-entry", "version": 1,
  "id": "task/word-frequencies", "kind": "task", "title": "Word frequencies",
  "editorial": {
    "state": "draft", "contributors": ["Codex"], "updated": "2026-10-19",
    "reviewer": null, "reviewed": null, "superseded_by": null
  },
  "sources": ["sol-counts"],
  "evidence": [{
    "supports": ["/spec", "body:mechanism", "body:evidence-and-limits"],
    "source": "sol-counts", "locator": "words.py: _METHOD, analyze_words; word_inputs.py: provider scopes; tokenization.py: word_tokens",
    "status": "source_report"
  }],
  "relations": [],
  "method_links": [{"method": "word-frequencies-v1", "source": "sol-counts", "locator": "words.py: _METHOD"}],
  "unknowns": ["No evidence here establishes conceptual or retrieval quality."],
  "spec": {
    "family": "lexical-counting",
    "input": {
      "shape": "Target provider, optionally a reference provider",
      "units": "Original Unicode text with source bindings and declared scope",
      "granularity": "CORE passage rows or one UTF-8 file row",
      "language": "Unicode letter tokens; linguistic adequacy is language-dependent",
      "binding": "CORE identity/generation/digests or whole-file byte digest and length",
      "scope": "Count whole tokens contained in the selected half-open codepoint span"
    },
    "output": {
      "shape": "sol.word-frequencies v1: vocabulary, source metadata and count/rate cells",
      "units": "Token counts and rates per 10,000 eligible tokens",
      "order": "Descending target count, then normalized word",
      "missing": "Rate is null when the denominator is zero",
      "correspondence": "Per input row: count and first occurrence's original codepoint offsets"
    },
    "preprocessing": "Declare tokenizer, normalization, Unicode version, provider projection, scope and exclusions; never rewrite canonical text",
    "evaluation": {
      "task": "Reproduce counts and source correspondence for the same bound inputs",
      "measures": "Counts, total eligible-token denominators, rates and exclusions",
      "uncertainty": "Deterministic lexical counts; no significance or semantic-confidence estimate",
      "reproducibility": "check_word_result must recompute the artifact against the selected sources and method"
    },
    "limitations": ["Translation, tokenization and scope affect results", "Raw counts with unequal denominators are not directly comparable", "Counts do not classify philosophical concepts"]
  }
}
```

## Purpose
Describe a lexical-counting contract independently of a particular interface.

## Mechanism
The existing SOL variant normalizes tokens and counts eligible occurrences.
Its declared projection differs between CORE and verbatim file input.

## Evidence and limits
The cited source code specifies behavior. It is not a linguistic-quality
evaluation. Record zero-token scopes and exclusions rather than hiding them.

## SOL connection
The built-in adapter below binds this task to word-frequencies-v1. Comparisons
use a separately identified method and retain both token denominators.
````

### Adapter record: SOL word frequencies

````markdown
# SOL word frequencies v1

```json
{
  "format": "sol.encyclopedia-entry", "version": 1,
  "id": "adapter/sol-word-frequencies-v1", "kind": "adapter",
  "title": "SOL word frequencies v1",
  "editorial": {
    "state": "draft", "contributors": ["Codex"], "updated": "2026-10-19",
    "reviewer": null, "reviewed": null, "superseded_by": null
  },
  "sources": ["sol-counts"],
  "evidence": [{
    "supports": ["/spec/implementation", "/spec/checkpoint", "/spec/input_limits", "/spec/output", "/spec/determinism", "/spec/effects", "body:mechanism"],
    "source": "sol-counts", "locator": "words.py: analyze_words, _METHOD, MAX_RESULT_BYTES; word_inputs.py: FileProvider, load_input and byte bounds; tokenization.py: word_tokens; pyproject.toml: project.version",
    "status": "source_report"
  }],
  "relations": [],
  "method_links": [{"method": "word-frequencies-v1", "source": "sol-counts", "locator": "words.py: _METHOD"}],
  "unknowns": ["Code license needs a source; do not offer as a specified runnable adapter until checked", "Peak memory and throughput are unmeasured"],
  "spec": {
    "task": "task/word-frequencies",
    "implementation": {
      "package": "sol-organizes-logic", "version": "0.1.0",
      "repository": "https://github.com/dialectmaterial/SOL",
      "revision": "379553bead8b408ae0fe8636b6528bf9ef3a2209",
      "entrypoint": "sol.essence.words.analyze_words"
    },
    "checkpoint": null, "license": null,
    "device": "CPU; no accelerator or learned weights; peak memory unmeasured",
    "input_limits": {
      "file_bytes": 67108864, "encoded_result_bytes": 16777216,
      "context_window": "Not applicable: no subword model",
      "chunking": "No model truncation; apply declared provider scope and whole-token containment"
    },
    "output": {
      "protocol": "sol.word-frequencies", "version": 1,
      "shape": "JSON object with bound provider inputs and vocabulary count/rate cells; no vector tensor",
      "missing": "Null rates for a zero token denominator",
      "alignment": "Locations identify input row and first original half-open codepoint span"
    },
    "determinism": "word-frequencies-v1; unicode-letter-mark-internal-apostrophe-v1; NFC+casefold+curly-apostrophe-to-straight; record Python's Unicode database version; no random seed",
    "effects": {
      "network": "None", "downloads": "None",
      "writes": "analyze_words returns a dictionary; saving is a separate caller operation",
      "core": "FileProvider needs no CORE import or corpus; CoreProvider explicitly loads verified CORE inputs"
    },
    "readiness": "draft"
  }
}
```

## Purpose
Identify the existing deterministic implementation of the word-frequency task.

## Mechanism
Word normalization and projections are method data, not inferred from this
entry's title. File offsets address the original decoded text. No pooling,
learned tokenizer or checkpoint applies to this adapter.

## Evidence and limits
Behavior is pinned to the cited revision. License and resource measurements
remain unresolved. No retrieval or interpretation benchmark is claimed.

## SOL connection
The Python entrypoint already exists; this catalog record and its proposed
dispatch mechanism do not. Reading the record never invokes the function.
````

## 8. CORE-free validator and CLI design

Propose an inert `sol.essence.encyclopedia` module boundary in a later task:
`load_catalog(root)` returns parsed records plus diagnostics;
`validate_catalog(catalog, *, publish=False)` returns deterministic diagnostics.
Neither function discovers a default corpus, loads configuration/workspaces,
imports CORE or a model library, or executes an adapter. Content is parsed once
and the UI receives these same records. No implementation is added by this PR.

Use the existing CommonMark parser already used by the docs checker to identify
the metadata fence and headings, and the standard JSON library to decode it.
No new parser or schema dependency is needed. Open only explicit catalog files
under the supplied root; reject symlinks, path escapes, nonregular files and
duplicate IDs. Do not fetch URLs or open source-code paths named by metadata.
Proposed initial bounds are 256 KiB per Markdown file, 8 MiB per catalog,
1,000 objects/references combined and JSON depth 32. They bound parsing work,
not experimental input sizes, and remain maintainer-overridable defaults.

Validation proceeds in a stable filename/field order:

1. Strict UTF-8, CommonMark envelope, exactly one metadata fence, required
   headings, bounded JSON, duplicate keys, finite values and exact field/types.
2. Version/kind/ID syntax, kind-specific required fields, dates and allowed
   status values. Booleans do not stand in for integer years or versions.
3. Unique IDs and source IDs, resolvable typed task/relation/replacement refs,
   evidence source membership, nonempty locators and valid evidence pointers.
   Check declared revision syntax, not the contents of a remote repository.
4. Editorial completeness: drafts generate visible warnings; `--publish`
   additionally rejects drafts, unsupported required claims, `needs_source`
   assertions, absent review attribution and incomplete adapter readiness.
   Inferences and disputes may publish when explicitly reviewed and cited.

Human review establishes whether a citation actually supports a claim. The
validator cannot infer truth from a DOI, verify resource benchmarks or turn a
license string into permission. Unknown secondary questions can remain visible
on reviewed records; missing evidence for a required contract cannot.

Proposed commands (not present commands):

```sh
sol encyclopedia check /path/to/catalog
sol encyclopedia check /path/to/catalog --publish --json
sol encyclopedia list /path/to/catalog --kind history
sol encyclopedia show /path/to/catalog history/term-specificity-1972
sol encyclopedia relations /path/to/catalog history/bert-2019
```

All take an explicit directory in the first release; there is no new persistent
configuration or implicit corpus fallback. `check` exits 0 for a structurally
valid draft catalog (warnings included), 1 for invalid content/publish failure,
2 for invocation/I/O failure. Its proposed JSON report has
`format: "sol.encyclopedia-check"`, `version: 1`, `valid`, `publish`, and ordered
`diagnostics` containing `severity`, relative `file`, `field`, `code`, `message`.
The other commands show literal text/data with control characters escaped;
they cannot evaluate Markdown as terminal commands or automatically open links.
There is no install, download or run command in this stage. Adapter execution
requires a separate task and the already required dependency/runtime decisions.

Later implementation acceptance should cover all three object kinds, source
resolution, cited relations, malformed/duplicate metadata, Unicode, nulls,
unknown versions, draft/publish distinction, bounded inputs, escaped terminal
output and deterministic diagnostics. Run the CLI in a fresh process that
refuses CORE/model imports and has no corpus or network. Check that reading an
adapter creates no files and imports no entrypoint. Use synthetic catalog
fixtures; this proposal adds no application tests or dependencies.

## 9. Decisions requested from the maintainer

Every choice below remains a proposal. Adoption of the public format/CLI is
**(reserved)**; merge of this documentation alone does not adopt it. A follow-up
implementation task should cite the approved choices and corresponding
authority updates. No change to CORE, artifacts, dependencies, personal work
deletion or canonical-corpus policy is requested.

1. **Content format and layout.** Options: CommonMark plus one strict JSON
   metadata fence and shared `references.md`; YAML front matter; separate JSON
   sidecars. **Recommend the JSON fence**, the three directories and stable IDs
   in §1: one readable object file, existing parser, no new dependency. Approve
   the proposed v1 field inventory before code treats it as a contract.
2. **Claims and genealogy.** Options: cited, status-bearing typed edges with
   explicit inference/dispute; prose-only relationships; a chronological chain.
   **Recommend the sourced graph in §3**, with no automatic ancestry from
   dates/similarity and no unsourced edges. Approve its initial predicate/status
   vocabulary, including `uses_architecture` for the checked BERT relation.
3. **Editorial release gate.** Options: display drafts and reviewed entries
   distinctly with a strict publish mode; treat schema validity as approval;
   require human-only editing. **Recommend distinct draft/reviewed states and
   explicit source-access scope**, normal independent review, and the §4
   evidence gate. Agent authorship stays visible; adapter completeness does not
   enable execution. License gaps block runnable specification.
4. **First coverage.** Options: the bounded counts/TF-IDF/word-vector/Transformer
   route in §5; transformers only; a broad model catalog immediately.
   **Recommend the bounded route**, beginning with the three draft examples,
   completing source review before promoting them. Leave n-gram origins marked
   `needs a source` and learned-checkpoint selection for separate work.
5. **Validator and CLI boundary.** Options: offline explicit-directory
   `check/list/show/relations`; validation embedded in Textual; automatic link
   fetching and adapter discovery. **Recommend the CORE-free offline boundary
   in §8**, including deterministic diagnostics and publish mode. Treat the
   parsing bounds as adjustable defaults. Approve command names/report shape
   before implementation; no runtime dispatch in stage 4.
6. **Connection to laboratory results.** Options: catalog IDs plus catalog
   revisions alongside existing method IDs; replace method IDs with entry IDs;
   let prose edits alter historical result interpretation. **Recommend keeping
   method/artifact identities intact** and using the pinned links in §5 for
   now. Any future persisted catalog reference needs its own contract review;
   this proposal changes no existing artifact or workspace schema.
