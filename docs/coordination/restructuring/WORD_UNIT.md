# Word units: reader search and ESSENCE

**Date:** 22 October 2026. **Lane:** Codex A. **Status:** research for a
**maintainer decision**; no behavior or placement change implemented.
**Code baseline:** `origin/main`, `9beb586073d2247c852f7640bd4e660167d5cc90`.
This answers [REEVALUATION §3.9](REEVALUATION.md#39-the-tokenizers-unit-limit-discrete-magnitude-or-reflection).

**Recommendation:** keep the two policies and document their names and limits.
Search retrieves literal occurrences; ESSENCE declares an analytical unit.
Their difference is observable but does not yet establish a need for a universal
word definition. Unification, a new reader mode, and any CORE API are decisions
for the maintainer. This report changes only coordination documentation.

## 1. Exact current definitions

### 1.1 Reader: a boundary predicate on a literal query

The implementation is [search.py](../../../sol/being/quality/search.py), with
passage retrieval also in [Book.search](../../../sol/core/models.py) and
[reader actions](../../../sol/being/actions.py). Search does **not** tokenize.
For presented text `T` and a nonempty query `Q`, define:

```python
F = lambda s: unicodedata.normalize("NFC", s).casefold()
pattern = r"(?<!\w)" + re.escape(F(Q.strip())) + r"(?!\w)"
# Python re, Unicode str semantics, no ASCII or IGNORECASE flag.
matches = re.finditer(pattern, F(T))
```

Only characters immediately **outside** the matched literal are tested.
Here `\w` means exactly a character satisfying `str.isalnum()` or `_`.
There is no requirement that the query consist of word characters, or that its
interior form a single word. Whole-word queries can include apostrophes,
hyphens, spaces, punctuation, or numbers. Thus maximal `\w+` runs are a useful
diagnostic unit for this predicate, **not the complete language of search**.
Search without the whole-word option has no boundary guards.

NFC precedes casefold; there is no NFKC, accent removal, apostrophe conversion,
or second NFC pass. For example, `ß` folds to `ss`; `İ` folds to `i` followed
by U+0307. The projection proves which normalized boundaries map back to the
unchanged source. A valid search result can have an unmappable occurrence:
searching `i` inside `İ` finds a folded match but cannot select an exact original
substring. It reports degradation, rather than inventing offsets. Verification
inside a normalization segment is bounded at 128 original codepoints;
pathological combining sequences can also produce explicit degradation.

### 1.2 ESSENCE: a scanner on the original text

[word_tokens](../../../sol/essence/essence_as_reflection_within_itself/tokenization.py)
scans original Python string codepoints, **before folding**:

1. Skip until a character has Unicode General Category starting with `L`.
2. Start a token there. Consume subsequent characters of category `L*` or
   `M*` (including spacing and enclosing marks, not just nonzero combining
   classes).
3. Also consume ASCII apostrophe U+0027 or right single quotation mark U+2019
   together with the following character, **only when that next character is
   `L*`**. Continue scanning the same token. The preceding consumed character
   may be a mark; the rule does not demand an immediately preceding letter.
4. Stop before anything else; resume looking for a letter. Yield
   `NFC(original_slice).casefold().replace("’", "'")` and the original
   half-open `[start, end)` codepoint offsets.

There is no second NFC pass, linguistic dictionary, stemming, accent removal,
or NFKC. The method identifies itself as
`unicode-letter-mark-internal-apostrophe-v1`, normalization
`NFC+casefold+curly-apostrophe-to-straight`; receipts also record the runtime's
Unicode database version. Leading marks and standalone numbers are skipped.
Trailing apostrophes are excluded; consecutive apostrophes break the token.
U+02BC MODIFIER LETTER APOSTROPHE is `Lm`: it behaves as a letter and is **not**
converted to ASCII apostrophe. Other quotation marks are not special unless
their own categories admit them.

The scanner itself knows nothing about facsimiles, attribution, or review
status. [Providers](../../../sol/essence/essence_as_reflection_within_itself/word_inputs.py)
add admission, masks and scope. Word studies tokenize the complete input and
admit only tokens wholly within the requested span, excluding tokens wholly
contained in a mask. Sentence lengths, word comparison and TF-IDF also depend
on this scanner; it is not just the frequency table's private implementation detail.

### 1.3 Consequences by character class

All examples below are invented probes, not quotations from the corpus.

| Case | Reader whole-word behavior | ESSENCE behavior |
| --- | --- | --- |
| `can't` | Both `can` and `t` match; the full literal `can't` also matches. | One token `can't`. |
| `can’t` | `can`, `t`, and literal `can’t` match; ASCII `can't` does not. | One token normalized to `can't`. |
| `well-being` | `well`, `being`, and full literal `well-being` match. | Two tokens, `well` and `being`. |
| Other hyphens/dashes/soft hyphen | Non-`\w` separators; a full matching literal can span them. No hyphen or line-end repair. | Separators unless `L*`/`M*`; no hyphen or line-end repair. |
| `abc123_def` | One diagnostic run; `abc` and `def` fail boundary guards. | `abc`, `def`; digits and underscore excluded. |
| `123`, `١٢٣`, `²`, `Ⅳ` | Numeric characters belong to `\w`, including Unicode decimal digits and nondecimal numeric characters. Whole literals match. | `Nd`, `Nl`, `No` cannot start or continue tokens; all these examples yield none. |
| `e` + U+0301 | NFC composes to `é`, so the letter remains in one diagnostic run. | One token `é`, offset length two in the original. |
| `a` + U+0315 + `b` | The uncomposed mark is not `\w`: diagnostic runs `a`, `b`; the full literal can also match. | One token containing the mark. |
| Leading marks | Generally non-`\w`, but folding can change classification: leading U+0345 folds to letter `ι`. | A leading mark is skipped before scanning; that U+0345 does not become a token starter retroactively. |
| `İ` | Diagnostic run `i`; the following folded dot is not `\w`. Selecting only `i` has no exact source span. | One token `i` + U+0307, with the original one-codepoint span. |
| `λόγος`, `漢字` | Unicode letters participate; casefold applies. A following digit blocks a shorter whole-word query. | Unicode letters participate; each uninterrupted letter/mark run is one token. A following digit ends it. |

Neither system performs Greek, Chinese, Arabic or other language-specific word
segmentation. Shared NFC/casefold does not imply shared boundaries: search
classifies **after** folding, ESSENCE classifies **before** folding.

### 1.4 Facsimile labels and admission are separate policies

Reader label declarations come from [load_corpus_book](../../../sol/core/corpus.py):
Markdown image lines of the exact `Source facsimile, printed page …` form,
with a `[0-9ivxlcdm]+` page label and a relative `assets/*.png` destination
(optionally preceded by `../`). For each declared label, presentation removes
**every** identical standalone plain-text line, allowing spaces/tabs on its
edges, then strips outer whitespace. It does not verify that the image basename
belongs to that record's source. An inline occurrence remains. Projection
retains surviving source indices; a match across a removed line can degrade if
it has no single contiguous source span.

ESSENCE's [_facsimile_spans](../../../sol/essence/essence_as_reflection_within_itself/corpus_inputs.py)
instead walks **trailing** converter image lines backward through Markdown.
Each printed-page label and image basename must match a source pair
`(str(printed_page), record_id + '-' + pdf_page + '.png')`. The corresponding
plain-text label must be an exact trailing standalone line after trimming
trailing whitespace. Its original span becomes a mask. Earlier identical
prose, inline labels, ordinary images and unsupported layouts remain.
The file provider adds no corpus facsimile masks.

The reader admits Hegel main-text paragraphs, list items, quotations and
formulas, including review-flagged records. ESSENCE's CORE selection admits
Hegel main-text paragraphs, list items and quotations, excluding generated
text, `needs_review`/`needs_visual_review`, and invalid doctrine/file reader
paths. It is a declared analysis population, not the reader's complete book.

## 2. Read-only private-corpus measurement

### 2.1 Material, method and reproducibility

The real private corpus was read at
`/home/dima/Projects/code/sol/local-corpus`, using the checkout's product
modules and `/home/dima/Projects/code/sol/.venv/bin/python -B`:
Python **3.14.8**, Unicode **16.0.0**. The edition is the existing Cambridge
2010 di Giovanni *Science of Logic* corpus. No PDF was opened, index rebuilt,
workspace created, or canonical file written. `load_snapshot` verifies the
generation; `verify_snapshot_current` checked it again after the run.

| Generation binding | SHA-256 |
| --- | --- |
| Manifest | `3ac1f6dd1bbbc73124cff625cd3898adb76b91d4470083dde53a63e4421d8dab` |
| Index | `91b1d25a60a914bd3644df038179583c8690b396cecb2e676ddfc2d6a6f36269` |
| Index metadata | `c193832c84a357eecb50968938ade4758328aece18f2634c14c9d6d3b1f87c8f` |

The throwaway script is **outside Git** at `/tmp/sol-word-unit-probe.py`;
its aggregate JSON output is `/tmp/sol-word-unit-results.json`, also untracked.
It emits counts and individual normalized forms only: no record IDs, source
positions, filenames, sentences, passages or context. This document records
aggregates and isolated tokens, not a corpus/export artifact.

```sh
PYTHONPATH=/tmp/sol-word-unit-study /home/dima/Projects/code/sol/.venv/bin/python -B /tmp/sol-word-unit-probe.py --self-test
PYTHONPATH=/tmp/sol-word-unit-study /home/dima/Projects/code/sol/.venv/bin/python -B /tmp/sol-word-unit-probe.py --corpus /home/dima/Projects/code/sol/local-corpus > /tmp/sol-word-unit-results.json
```

The first path is the writable study clone; both temporary files are local
research aids, not durable repository tools. The synthetic self-test covers
14 input cases plus actual search projection and facsimile assertions, including straight
and curly apostrophes, hyphens, underscores, numeric categories, composed and
uncomposed marks, leading marks, expansion, Greek and CJK. Internal assertions
reconcile every cause subtotal and prove tokenizer boundaries against the
product's fold/alignment helpers.

The final script SHA-256 is
`f49a0f7686d0798d0c349f7b66916d56e47fa06c6556e6b89b6d2212ef0df2a2`.

For each record independently:

1. Enumerate maximal `\w+` runs on `F(text)` as diagnostic search units S.
2. Run the actual `word_tokens(text)` as E. Map its original endpoints through
   independently verified fold boundaries into the same folded coordinate
   system; retain E's normalized form, including apostrophe conversion.
3. Compare `(normalized_form, start, end)` triples. An identical triple is an
   agreement; unmatched occurrences are counted separately on each side.
4. Form connected components of strictly overlapping S/E intervals. Adjacent
   intervals do not merge. A component with unequal triple sets is one
   **differing location**, even when one E token overlaps two S runs.
5. Assign one cause per location from the original characters, in priority
   order: underscore; apostrophe (curly before straight); numeric character
   (decimal before other-number, with/without letters); mark; other.
   Count the symmetric difference of the two sets of start/end boundaries,
   without counting the same boundary twice within a record. Also count the
   union of codepoints covered by differing components.

No offset is compared across records. All observed S endpoints map exactly to
original codepoint boundaries, so the original-boundary difference count equals
the folded-boundary count here. The synthetic `İ` case demonstrates why that
cannot be assumed for arbitrary text. These metrics do not enumerate all
possible punctuation-containing or multiword search queries.

### 2.2 Populations and disagreements

There are **4,629 canonical records**. ESSENCE excludes 2,541 for attribution,
285 for record type/generated status, and 46 for review, in the provider's
first-reason order. All **1,757 admitted records** occur in the reader's
**1,803 passages**. The remaining 46 reader passages need visual review;
all current reader passages are paragraphs. There are no formula-type records
in this reader generation, although mathematical symbols occur in paragraphs.

The primary comparison applies both lexical definitions to the same **1,757
admitted reader presentations**. An assertion checks that ESSENCE's actual
masked token stream equals the presentation's token stream. The canonical raw
audit additionally scans every record's `plain_text` without admission or
caption filtering; it includes editorial/translator/structural material and
must not be interpreted as the reader's search population or an ESSENCE result.
The 46-record supplement applies the tokenizer hypothetically to reader
presentations; the real ESSENCE provider excludes them.

| Metric | Shared admitted text (primary) | Reader-only review text | All canonical raw text |
| --- | ---: | ---: | ---: |
| Records | 1,757 | 46 | 4,629 |
| Records with a lexical disagreement | 420 | 34 | 2,754 |
| Search diagnostic units S | 313,087 | 15,527 | 391,853 |
| ESSENCE scanner tokens E | 312,481 | 15,365 | 383,282 |
| Identical occurrences | 312,107 | 15,291 | 382,055 |
| Unmatched S occurrences | 980 | 236 | 9,798 |
| Unmatched E occurrences | 374 | 74 | 1,227 |
| Differing locations (overlap components) | 633 | 224 | 8,952 |
| Differing original/folded boundary positions | 1,266 | 452 | 17,926 |
| Folded codepoints covered by differing locations | 3,332 | 425 | 28,244 |

In the primary population, 0.313% of S and 0.120% of E occurrences differ;
23.90% of passages contain a difference. The **net count difference is only
606**, which hides the 980 versus 374 unmatched occurrences. It is not an
estimate of changes to search-result passage counts: search returns passages,
can cap results, and permits more than `\w+` queries.

Independent use of actual `search_projection(text, normalized_E_form, True)`
at all 374 risky E occurrences in the primary population confirmed **374 local
self-query misses**: the normalized analytical form does not retrieve its own
exact source span. This measures that occurrence, not whether the same query
finds some other occurrence in the passage. In the raw audit, 1,226 of 1,227
unmatched E occurrences miss; the single ASCII-apostrophe token still matches
as a full literal. This is why segmentation differences alone cannot predict
every reader query.

### 2.3 Causes and top individual forms

Each cell below is **locations / unmatched S / unmatched E**; causes are
exclusive under §2.1's priority. Zero rows are retained to delimit the evidence.

| Cause | Primary | Reader-only review | Canonical raw |
| --- | ---: | ---: | ---: |
| Internal curly apostrophe | 347 / 694 / 347 | 12 / 24 / 12 | 845 / 1,690 / 845 |
| Internal straight apostrophe | 0 / 0 / 0 | 0 / 0 / 0 | 1 / 2 / 1 |
| Decimal numbers without letters | 260 / 260 / 0 | 149 / 149 / 0 | 7,742 / 7,742 / 0 |
| Decimal numbers joined to letters | 22 / 22 / 22 | 16 / 16 / 16 | 308 / 308 / 325 |
| Other numeric characters without letters | 0 / 0 / 0 | 1 / 1 / 0 | 1 / 1 / 0 |
| Other numeric characters joined to letters | 4 / 4 / 5 | 46 / 46 / 46 | 55 / 55 / 56 |
| Underscores | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Combining marks / other residual causes | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

Top differing **single forms**, counted only at unmatched occurrences in the
primary population (not total corpus frequencies):

| Cause | Search forms and counts | ESSENCE forms and counts |
| --- | --- | --- |
| Curly apostrophe | `s` 344; `concept` 36; `kant` 33; `god` 14; `one` 13 | `concept's` 36; `kant's` 33; `god's` 14; `one's` 13; `latter's` 11 |
| Decimal only | `2` 74; `1` 71; `3` 50; `7` 10; `4` 5 | None |
| Decimal joined to letters | `2nd` 3; `3rd` 3; `64ff` 2 | `ff` 10; `nd` 3; `rd` 3; `th` 3 |
| Other numbers joined to letters | `t¼` 3; `cen¼n` 1 | `t` 3; `cen` 1; `n` 1 |

The latter forms are observations of the indexed transcription, not accepted
linguistic or mathematical corrections. No passages or page locations are
inferred from them. Across **all raw records**, the highest differing S forms
are `s` 800, `1` 284, `2` 267, `hegel` 247, `3` 167; the highest differing E
forms are `hegel's` 246, `ff` 101, `b` 89, `kant's` 74, `a` 69. Their different
ranking reflects the broader population. In the review-only supplement the
leading S forms are `0` 29, `2` 26, `7` 22; leading E forms are `at` 15,
`a` 12, `y` 8.

There are **no original combining-mark characters** in any of these indexed
plain texts, so zero mark disagreements provide no empirical assurance for
decomposed text. There are 16 E occurrences containing non-Latin letters in
the raw audit, four in review-only text, and none in the primary population.
Non-Latin letters alone produce no separate discrepancy; numeric attachment
can still matter. The 3,344 ASCII hyphens in primary text (4,338 raw) add no
independent segmentation difference: both definitions split them. Punctuation
queries can still span them. Those absences do not supersede the synthetic
Unicode probes or existing Unicode tests.

Facsimile handling is also separately measurable. The reader declares and
removes **74 label occurrences in 46 passages**: 370 diagnostic S runs and 296
E scanner tokens. ESSENCE recognizes the same 74 mask spans in those reader
records, but excludes all 46 records for review before counting tokens.
Across the entire canonical graph it recognizes 100 mask spans. **Zero masks
occur in the 1,757 admitted records.** There is therefore no observed caption
policy disagreement within the primary population, and no license to claim
that the two general caption algorithms are equivalent.

## 3. Options for the maintainer

### 3.1 Search follows the tokenizer

**User effects.** A genuine analytical-token reader mode would stop matching
`can` or `t` inside a contraction, join straight/curly apostrophe equivalence,
and stop treating standalone numbers as tokens. Conversely, letters next to
digits or underscore become complete tokens. Uncomposed marks stay attached.
The maintainer must also specify multiword/punctuation queries: retaining
literal interiors while requiring tokenizer-aligned endpoints can preserve
`well-being` and phrases, whereas demanding exactly one token would reject
them. Changing endpoint rules alone would **not** resolve curly-apostrophe
equivalence. This option must state both rules, preferably as an explicit new
mode if existing numeric/literal lookup is to remain available.

**Tests and compatibility.** Keep default substring search and canonical
offset proofs intact; update whole-word parity in Book, actions and projection
together. Extend `test_reader_search_projection`, `test_reader_search_actions`,
`test_reader_actions` and `test_terminal` for contractions, numbers, underscores,
marks, punctuation and phrase endpoints, plus UI highlights/history. Reusing
the unchanged tokenizer need not change ESSENCE receipts. Relabeling the
existing option without deciding its query grammar is insufficient.

**Performance.** Tokenizing a whole passage for every query adds a Python
category scan and allocation; finding only candidate boundary evidence may
avoid that cost. Search can have repeated interactive queries, so cache design
must respect caller-mutable Book data and invalidation. No cache is proposed
here. Benchmark the actual action/projection path before adopting it.

**Owner.** BEING/Quality owns reader matching, highlighting and query grammar;
ESSENCE/Reflection owns analytical normalization and token admission. A direct
BEING import of ESSENCE would violate the current architecture guard. Sharing
requires a separately justified primitive and dependency decision, not an
import shortcut. CORE must not inherit eligibility or study scope.

### 3.2 Tokenizer follows search

**User effects.** A concrete interpretation is maximal Unicode `\w+` runs
after NFC/casefold, without apostrophe conversion: contractions split, numbers
and underscores count, digit-letter runs stay joined, and surviving marks can
split runs. On admitted text that hypothetical inventory has **606 more
tokens**, with the full 980/374 occurrence replacement above. This is only the
lexical inventory: it cannot copy every valid literal search query, because
both a contraction and its pieces can be whole-word matches. No unique token
stream can contain every such overlapping match as a partition.

**Tests and compatibility.** Word totals, vocabulary, rates, comparisons,
TF-IDF vectors, sentence lengths, token locations and artifact validation would
change. Update word/comparison/TF-IDF/sentence/provider tests and
versioned fixtures deliberately; preserve old-artifact interpretation or
explicitly version/refuse it. Do not silently retain the current tokenization
method ID. Folded fragments like `i` within `İ` have no original half-open span;
either the new method excludes them (already a qualification of search units)
or a separately approved offset/artifact contract must represent them.

**Performance.** C regex scanning is faster than the current Python scanner in
the limited enumeration benchmark below. Exact original-offset reconstruction
can cost more, especially with expansion and combining sequences; timing
`re.findall` alone omits a required part of an ESSENCE implementation.

**Owner.** ESSENCE/Reflection must declare and version this changed analytical
standpoint. BEING's lookup convention does not establish the investigation's
unit. CORE continues to supply unchanged verified text, not lexical truth.
Any public artifact/offset contract change is **reserved** for the maintainer.

### 3.3 Keep both and document the distinction — recommended

**User effects.** Existing retrieval, numeric lookup, counts, offsets and saved
artifacts remain stable. Documentation should call the reader option
“literal search with Unicode word-character boundaries” and name the analytical
unit “Unicode letter/mark tokens with internal apostrophes.” A future help or
encyclopedia edit can show the invented `can't 123` example and warn that a
normalized ESSENCE form may require the source's apostrophe spelling in reader
search. This PR supplies the maintainer report; it does not change runtime help.

**Tests and compatibility.** Existing behavioral tests and v1/v2 fixtures stay
valid. A follow-up documentation/UI change should verify its examples against
both APIs. No fabricated corpus fixture or private text belongs in the tests.

**Performance.** No product runtime cost or new indexing/cache work.

**Owner.** BEING/Quality retains literal retrieval; ESSENCE/Reflection retains
the method-defined scanner and its receipt. CORE retains source/projection
provenance services. This makes the existing difference inspectable rather
than claiming a universal word unit from either package's location.

### 3.4 A shared CORE word-unit helper

**User effects.** Moving code alone changes no matches or counts and does not
resolve a disagreement. A helper with one default forces one of §§3.1–3.2's
behavior choices. A helper with explicit policies can preserve both, but still
needs separate boundary, equivalence, offset and query-grammar contracts.
Captions, review eligibility, source scope and sentence policy remain separate.

**Tests and compatibility.** A pure helper needs a synthetic Unicode matrix,
original-span guarantees, independently importable/file-only coverage,
installed-wheel coverage and architecture-guard checks. Existing reader parity
and method fixtures must remain unchanged for a pure extraction. A public
CORE API would be **reserved**; policy/version changes require their own
compatibility plan. A private helper still needs a justified CORE responsibility.

**Performance.** Extraction alone has no expected meaningful gain. Sharing an
index would add memory and invalidation obligations beyond sharing code;
do not infer a cache from the proposed helper. Exact folded/source alignment
remains necessary regardless of module location.

**Owner.** CORE could own a genuinely shared, policy-explicit source-coordinate
primitive, with BEING and ESSENCE specifying their own policies. The present
evidence does not justify moving the complete analytical tokenizer, admission
or equivalence into CORE. Shared use by several ESSENCE methods is already
cohesive Reflection use, not proof of a CORE service.

## 4. Evidence for ownership, performance and decision limits

The ownership judgments above use the existing primary-edition readings,
not newly claimed quotations or page evidence:
[READING_BEING §3.1](READING_BEING.md#31-reading-state-readeractions-readernavigation-readersearch)
distinguishes literal retrieval and reading actions; its
[§4](READING_BEING.md#4-answers-to-the-inventorys-stage-c-questions) leaves the
tokenizer question open.
[READING_ESSENCE §4](READING_ESSENCE.md#4-code-inspection-and-what-the-analogy-makes-questionable)
and [E1](READING_ESSENCE.md#5-proposed-placement-register-rows) keep reproducible
method units with policy, scope and bindings.
[REEVALUATION §§3.2–3.3](REEVALUATION.md#32-search-in-quality-and-comparison-in-reflection)
and [§3.9](REEVALUATION.md#39-the-tokenizers-unit-limit-discrete-magnitude-or-reflection)
retain Quality/Reflection provisionally and reject promoting experimental
eligibility to CORE merely because it is shared. Boundary cutting, counting
and equivalence are related aspects; they do not require three new services
or prove that a lexical statistic constitutes Hegelian Measure. The current
[dependency direction](../../ARCHITECTURE.md#dependency-direction) also forbids
BEING and ESSENCE importing each other.

On this machine, seven in-memory repetitions over the **same primary texts**,
excluding corpus loading and I/O, gave these medians (observed ranges):

| Operation | Time | Count |
| --- | ---: | ---: |
| NFC/casefold plus regex run enumeration | 57.913 ms (57.497–61.215) | 313,087 units |
| Full `word_tokens` enumeration with original offsets | 307.679 ms (297.116–362.467) | 312,481 tokens |
| One pre-folded whole-word query, chosen query `concept` | 31.586 ms (31.440–31.756) | 1,693 occurrences |

The first operation does not reconstruct original offsets; the third does
neither folding nor highlighting and scans all admitted text without a result
limit. These are different operations, not an end-to-end speedup claim. The
full diagnostic audit took about ten seconds including verification and three
populations. No alternative product implementation exists here to benchmark.

**Maintainer decision:** accept deliberate separate policies, choose a new
reader token mode, redefine analytical units with explicit artifact migration,
or commission a policy-explicit shared primitive. The recommendation is
§3.3, with a user-facing explanation as a bounded follow-up. The small net
count difference does not justify silently changing reproducible studies;
the spread across 420 passages does justify explaining the distinction.
No decision, public API, dependency, artifact, workspace, corpus or register
placement is changed by this research.
