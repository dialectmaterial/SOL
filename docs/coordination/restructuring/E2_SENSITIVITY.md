# E2 sensitivity study — stage F

Research only. E2 methods, schemas and the placement register are unchanged.

**Result:** no candidate meets the local nodal screen under either missing-rank
convention described below. Under the amended capped-rank convention, 178
one-paragraph transitions yield 27 abrupt comparison flags (7 rate differences,
20 log ratios), including increments below 1% in tokens. Six are self-comparison
endpoints; 21 remain without them. None has the required stable lead-in; all 16
with enough following observations pass persistence, while 11 lack enough
following observations. This negative nodal result is not absence of persistent
abrupt change. The original average-rank reading yields 28 flags. TF-IDF has no
local abrupt flag, and all 288 top_n sweep calls preserve existing prefixes
and scores. Large context changes also flag 64 five-term passage profiles.
These results support sensitivity to a comparing standpoint, not a demonstrated
quality constituted by a measure-relation. The limitations and positive
sensitivity results below are essential to that conclusion.

## Prospective protocol

First committed on 22 October 2026 in `fe1aeef`, before the results commit
`30ef3d8`; code baseline `729ff24475e0743c86491efe14e1b2e6a4dd35f5`. Git history
establishes declaration before the results commit, not before the first private
corpus read. The numerical cutoffs, selections, primary depth and requirements for
preceding/following observations were retained. The missing-rank convention was amended
after `fe1aeef`, from “tied at k+1 (average ranks for that tie)” to capped rank
k+1 in `30ef3d8`. The protocol below contains that amendment; its numerical effect
is reported under Results. These are operational screening conventions, not
definitions of philosophical quality or statistical significance. Negative
screens are reported.

- Source: the existing private `/home/dima/Projects/code/sol/local-corpus`, read
  only through public CORE snapshots and ESSENCE providers/functions. Retain
  standard eligibility, tokenizer, zeros, normalization and rounded scores.
  No stop-word removal, stemming, smoothing of comparison ratios or new method.
- TF-IDF populations: each doctrine, each two-doctrine union and all three.
  Compare both overall rankings and the same passage's ranking across contexts.
- Units: CORE input rows remain passages (paragraphs, quotations or list items),
  even inside section/chapter scopes. Also collapse the identical eligible
  vocabulary/counts of a selected section, chapter, doctrine and whole book to
  one file document via FileProvider, checking count equality. This tests a
  supported one-document limit, not a nonexistent multi-file provider. Select
  one chapter per doctrine by the median eligible passage in canonical order
  (first three reader-path components); select its median passage's leaf path
  as the section. Report exact choices and supported-unit limitations.
- Comparison populations: each doctrine against each other doctrine, their
  union, and the whole eligible book (overlap allowed). Rank signed rate
  difference descending, with lexical tie-break, and separately defined signed
  log2 ratios descending. Do not rank undefined ratios; report their counts.
  These are research ranking views: comparison.py itself retains count order.
- Local perturbations: within each selected chapter, grow a canonical-order
  prefix of passages one passage at a time, measuring TF-IDF overall rankings
  and comparison of that fixed chapter against the growing reference. Start
  with five passages; do not interpret the initial empty/tiny reference as a
  node. Also slide each selected section's reference from preceding to
  following sibling leaf scopes in canonical order, where available. These
  section replacements are discrete context contrasts, not arbitrarily small
  numerical increments.
- Sweep every integer TF-IDF top_n from 5 through 100 on the three selected
  section scopes. Verify exact prefix membership, rank and score invariance
  against top_n=100, for both overall and document results. Larger-population
  contrasts use depths 5, 10, 20, 50 and 100.
- Metrics at depth k: overlap = intersection/minimum available list length;
  Jaccard = intersection/union; Spearman-style rho = Pearson correlation of
  ranks on the union, missing words all assigned capped rank k+1;
  RBO with p=0.9 = (1-p) sum[d=1..k] p^(d-1) A_d + p^k A_k,
  A_d = prefix intersection/d. For threshold decisions use exact rational
  p=9/10 and A_d, including the finite extrapolation term; equality satisfies
  the inclusive cutoff (in particular RBO=9/10 passes the stable RBO test).
  This boundary arithmetic was made explicit on review. Use common available
  depth for short lists; empty/constant-rank rho is undefined. Lexical tie-break is deterministic,
  not evidence of substantive separation. Rho is a union-rank convention,
  not Spearman restricted to the surviving intersection.
- Primary screen: k=20. An abrupt-change flag requires Jaccard <=0.50,
  RBO <=0.70 and rho <=0.50 together. A stable step requires Jaccard >=0.80,
  RBO >=0.90 and rho >=0.90 together; other steps are intermediate. A local
  *nodal candidate* additionally needs three preceding stable steps and the
  two following results to remain beyond all abrupt thresholds relative to
  the pre-boundary result. Require enough observations on each side; report
  boundary flags separately. Large unit/population contrasts can show
  sensitivity, but cannot meet this local-node test by themselves.
- Top_n+1 is a display perturbation: test whether existing ranks/scores change.
  Membership gained solely by enlarging a prefix is not a leap. No thresholds
  will be tuned after outcomes. Summarize all local steps, not only extremes.
- Report only isolated normalized words, aggregate counts/statistics and
  provenance; no source sentences, passages, contextual token sequences, PDFs,
  corpus files, workspaces or study exports enter Git. The task-specific
  analysis program and intermediate numeric output stay in /tmp.

## Results

The report below retains the numerical cutoffs and uses the amended capped
rank k+1 for all missing items, except where the original average-rank reading
is explicitly compared. This is a modified rank correlation, rather than
ordinary full-vocabulary Spearman. The amendment is numerically consequential.
For a common list depth k and union size U, the original average-rank reading assigns missing words the mean
of positions k+1 through U, namely (k+1+U)/2, rather than k+1.

RBO is the finite extrapolated statistic in the protocol, with equal common
depth, not a claim about unseen ranking tails. “Stable”, “intermediate” and
“abrupt” below mean only the operational screen. Large contrasts labeled abrupt
are not local nodal candidates. The review recomputation uses exact rational
Jaccard/RBO arithmetic and exact comparisons of rank correlation to the cutoffs
(by comparing squared integer covariance and variances, with signs retained);
display rounding does not decide classes.

### Source and execution

All computations use the checked public `core.load_snapshot`, `CoreProvider`,
`analyze_words`, `compare_words` and `analyze_tfidf` APIs. The only file-provider
inputs are temporary joins of public `prose_text(record["markdown"])` output
for the IDs admitted by the CORE word receipt. Their complete word/count maps
are checked equal before comparing units, and the temporary directory is
removed. This prevents headings, editorial matter, flagged text or facsimile
labels from confounding the unit test. No new provider or TF-IDF engine is
introduced. Native comparison order remains unchanged; the research program
sorts its returned signed measures for the rank comparisons.

The eligible “book” means the provider's three-doctrine Hegel main-text
projection, not every page of the edition. There are 1,757 input rows, all
paragraphs, 312,481 tokens and 7,317 types. Standard exclusions are 2,541 records
for attribution, 285 for record type and 46 for pending review; no eligible
reader-path exclusions or masked facsimile tokens. These are record counts,
not estimates of missing words.

The task-specific script, numeric intermediate output and execution logs live
only under `/tmp/sol-e2-*`; they are not Git deliverables. Reproduction requires
the private corpus generation identified below and the public API calls and
selection/metric rules above. No corpus access is needed to review the formulas
and aggregate evidence here.

### Supported units and selected scopes

`CoreProvider(..., {"kind": "within", "path": ...})` chooses a population;
it does **not** turn a section/chapter into one TF-IDF document. Native rows
remain paragraphs. `FileProvider` supplies exactly one document, so the paired
collapse is N=paragraph count versus N=1 over identical words. Multiple section
or chapter documents in a single TF-IDF population are **not supported** by the
existing public providers and were not simulated by editing receipts or
calling private engine functions. This limits the document-unit result to the
supported collapsed-document endpoint.

A “section” here is a leaf virtual `.txt` scope, which can be an introduction
or remark. A “chapter” is the first three reader-path components. Selection
uses floor(n/2) with zero-based indices in canonical order. This is a
reproducible convenience sample, not a claim that the selected sections are
representative of all chapters.

### Corpus binding and counts

- Manifest SHA-256: `3ac1f6dd1bbbc73124cff625cd3898adb76b91d4470083dde53a63e4421d8dab`.
- Index SHA-256: `91b1d25a60a914bd3644df038179583c8690b396cecb2e676ddfc2d6a6f36269`.
- Index-metadata SHA-256: `c193832c84a357eecb50968938ade4758328aece18f2634c14c9d6d3b1f87c8f`.
- Edition SHA-256: `e9e05e58104e9d9d4fd58c9b28eff607f09bd59f5129d98e1177e83313a0755a`.
- Source SHA-256: `f48a2272a6daa80f2742de91e271a2b4b8a93d0a29193b6f02a6e3c010fc0e26`; 863 PDF pages; no PDF opened.
- Corpus ID: `d798fc13-455b-45ff-b88f-deb14c727ea6`.

| Population | Paragraphs | Tokens | Types |
| --- | --- | --- | --- |
| BEING | 776 | 131267 | 5622 |
| BEING+CONCEPT | 1289 | 239801 | 6889 |
| BEING+ESSENCE | 1244 | 203947 | 6211 |
| BEING+ESSENCE+CONCEPT | 1757 | 312481 | 7317 |
| CONCEPT | 513 | 108534 | 4128 |
| ESSENCE | 468 | 72680 | 2576 |
| ESSENCE+CONCEPT | 981 | 181214 | 4849 |

Selected scopes (paths are provenance identifiers, not quoted prose):

- BEING chapter: `/BEING/ii-magnitude-quantity/1-quantity` (62 paragraphs).
  Section: `/BEING/ii-magnitude-quantity/1-quantity/a-pure-quantity/2-remark-2.txt` (42 paragraphs).
- CONCEPT chapter: `/CONCEPT/i-subjectivity/3-the-syllogism` (96 paragraphs).
  Section: `/CONCEPT/i-subjectivity/3-the-syllogism/b-the-syllogism-of-reflection/00-introduction.txt` (4 paragraphs).
- ESSENCE chapter: `/ESSENCE/ii-appearance/1-concrete-existence` (35 paragraphs).
  Section: `/ESSENCE/ii-appearance/1-concrete-existence/a-the-thing-and-its-properties/b-property/00-introduction.txt` (3 paragraphs).

All following metrics are rounded to four decimal places for display; screens
use unrounded values. O = overlap, J = Jaccard, ρ = capped union-rank correlation,
R = RBO. Every primary comparison has common depth 20 unless stated otherwise.

### Document-unit contrast

Each row compares the overall paragraph-document ranking with the single-file
document ranking for exactly the same eligible words. All ten complete count-map
equality checks passed. No depth-20 abrupt flag occurred. At N=1 every
observed term has IDF=1; the file result is L2-normalized raw frequency.
This unit change preserves counts while jointly changing N, document frequency,
per-document normalization and averaging; it does not isolate those factors
from one another.

| Scope | Paragraphs | Tokens | Types | O | J | ρ | R | Screen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BEING:section | 42 | 3606 | 788 | 1.0000 | 1.0000 | 0.8406 | 0.9109 | intermediate |
| ESSENCE:section | 3 | 708 | 183 | 0.9500 | 0.9048 | 0.9169 | 0.9334 | stable |
| CONCEPT:section | 4 | 369 | 130 | 0.9000 | 0.8182 | 0.9110 | 0.9264 | stable |
| BEING:chapter | 62 | 5786 | 1046 | 0.9500 | 0.9048 | 0.8818 | 0.9370 | intermediate |
| ESSENCE:chapter | 35 | 7704 | 881 | 0.9500 | 0.9048 | 0.9506 | 0.9505 | stable |
| CONCEPT:chapter | 96 | 16277 | 1441 | 1.0000 | 1.0000 | 0.9549 | 0.9617 | stable |
| BEING:doctrine | 776 | 131267 | 5622 | 0.9500 | 0.9048 | 0.9403 | 0.9639 | stable |
| ESSENCE:doctrine | 468 | 72680 | 2576 | 0.8500 | 0.7391 | 0.9339 | 0.9208 | intermediate |
| CONCEPT:doctrine | 513 | 108534 | 4128 | 0.9000 | 0.8182 | 0.9769 | 0.9709 | stable |
| book | 1757 | 312481 | 7317 | 0.9000 | 0.8182 | 0.9596 | 0.9233 | stable |

### TF-IDF reference-population contrasts

The population is the TF-IDF context, not an extra reference argument. The
following table keeps each passage fixed and changes the context from its own
doctrine to a two-doctrine union or the eligible book. Values are medians; the
class counts summarize every passage comparison rather than the median alone.

| Fixed passage population → context | n | Stable | Intermediate | Abrupt | Median O | Median J | Median ρ | Median R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BEING -> BEING+CONCEPT | 776 | 514 | 262 | 0 | 0.9500 | 0.9048 | 0.9597 | 0.9359 |
| BEING -> BEING+ESSENCE | 776 | 574 | 202 | 0 | 0.9500 | 0.9048 | 0.9675 | 0.9464 |
| BEING -> BEING+ESSENCE+CONCEPT | 776 | 361 | 415 | 0 | 0.9500 | 0.9048 | 0.9403 | 0.9137 |
| CONCEPT -> BEING+CONCEPT | 513 | 197 | 316 | 0 | 0.9500 | 0.9048 | 0.9260 | 0.8994 |
| CONCEPT -> BEING+ESSENCE+CONCEPT | 513 | 119 | 394 | 0 | 0.9500 | 0.9048 | 0.9078 | 0.8754 |
| CONCEPT -> ESSENCE+CONCEPT | 513 | 278 | 235 | 0 | 0.9500 | 0.9048 | 0.9465 | 0.9171 |
| ESSENCE -> BEING+ESSENCE | 468 | 152 | 316 | 0 | 0.9500 | 0.9048 | 0.9267 | 0.8891 |
| ESSENCE -> BEING+ESSENCE+CONCEPT | 468 | 129 | 339 | 0 | 0.9500 | 0.9048 | 0.9192 | 0.8775 |
| ESSENCE -> ESSENCE+CONCEPT | 468 | 260 | 208 | 0 | 0.9500 | 0.9048 | 0.9536 | 0.9226 |

For overall rankings, all 21 unordered pairs of the seven populations were
compared at each depth. These contrasts also change the averaged documents;
they are not pure fixed-target context perturbations. The table shows the full
contrast set, including depths where the primary-screen conclusion differs.

| k | Pairs | Stable | Intermediate | Abrupt | Min J | Median J | Min ρ | Min R | Median R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 21 | 15 | 6 | 0 | 0.6667 | 1.0000 | 0.7714 | 0.8056 | 0.9550 |
| 10 | 21 | 15 | 6 | 0 | 0.6667 | 0.8182 | 0.8420 | 0.8180 | 0.9115 |
| 20 | 21 | 10 | 11 | 0 | 0.6000 | 0.8182 | 0.8614 | 0.8280 | 0.9133 |
| 50 | 21 | 1 | 20 | 0 | 0.4925 | 0.7241 | 0.5794 | 0.8213 | 0.9115 |
| 100 | 21 | 2 | 19 | 0 | 0.4286 | 0.6667 | 0.5386 | 0.8212 | 0.9115 |

Matched-passage and unit contrasts are primary depth-20 screens. Unit
contrasts were also measured at all five depths:

| k | Stable | Intermediate | Abrupt | Min J | Min ρ | Min R |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 6 | 4 | 0 | 0.6667 | 0.8286 | 0.8506 |
| 10 | 8 | 2 | 0 | 0.8182 | 0.8455 | 0.9017 |
| 20 | 7 | 3 | 0 | 0.7391 | 0.8406 | 0.9109 |
| 50 | 4 | 6 | 0 | 0.7241 | 0.8861 | 0.8991 |
| 100 | 7 | 3 | 0 | 0.6667 | 0.8142 | 0.8992 |

### Comparison: signed rate differences and defined log ratios

For each fixed doctrine, four reference choices give six contrasts. Every
contrast is listed below; each metric cell is J/ρ/R at depth 20. “Other two”
excludes the target; “book” includes it. These are large context changes, so
even abrupt screens are not local nodal candidates.

| Target | Reference contrast | Rate J/ρ/R | Screen | Log J/ρ/R | Screen |
| --- | --- | --- | --- | --- | --- |
| BEING | ESSENCE → CONCEPT | 0.4286/-0.0695/0.3436 | abrupt | 0.1429/-0.1801/0.2528 | abrupt |
| BEING | ESSENCE → other_two | 0.6000/0.4638/0.5409 | intermediate | 0.1429/-0.0540/0.2856 | abrupt |
| BEING | ESSENCE → book | 0.6000/0.4638/0.5409 | intermediate | 0.0000/-0.6238/0.0000 | abrupt |
| BEING | CONCEPT → other_two | 0.7391/0.4877/0.6353 | intermediate | 0.4286/0.4819/0.5776 | abrupt |
| BEING | CONCEPT → book | 0.7391/0.4877/0.6353 | intermediate | 0.0000/-0.6238/0.0000 | abrupt |
| BEING | other_two → book | 1.0000/1.0000/1.0000 | stable | 0.0000/-0.6238/0.0000 | abrupt |
| ESSENCE | BEING → CONCEPT | 0.6667/0.7550/0.8683 | intermediate | 0.1111/-0.5793/0.0526 | abrupt |
| ESSENCE | BEING → other_two | 0.9048/0.9273/0.9535 | stable | 0.1765/-0.4648/0.1033 | abrupt |
| ESSENCE | BEING → book | 0.9048/0.9273/0.9535 | stable | 0.0000/-0.6238/0.0000 | abrupt |
| ESSENCE | CONCEPT → other_two | 0.7391/0.8919/0.8893 | intermediate | 0.3793/0.1084/0.5611 | abrupt |
| ESSENCE | CONCEPT → book | 0.7391/0.8919/0.8893 | intermediate | 0.0000/-0.6238/0.0000 | abrupt |
| ESSENCE | other_two → book | 1.0000/1.0000/1.0000 | stable | 0.0000/-0.6238/0.0000 | abrupt |
| CONCEPT | BEING → ESSENCE | 0.6000/0.4241/0.7647 | intermediate | 0.2500/0.1796/0.2833 | abrupt |
| CONCEPT | BEING → other_two | 0.6000/0.6447/0.8615 | intermediate | 0.6000/0.6637/0.7205 | intermediate |
| CONCEPT | BEING → book | 0.6000/0.6447/0.8615 | intermediate | 0.0000/-0.6238/0.0000 | abrupt |
| CONCEPT | ESSENCE → other_two | 0.8182/0.7654/0.8561 | intermediate | 0.2500/0.1977/0.3274 | abrupt |
| CONCEPT | ESSENCE → book | 0.8182/0.7654/0.8561 | intermediate | 0.0000/-0.6238/0.0000 | abrupt |
| CONCEPT | other_two → book | 1.0000/1.0000/1.0000 | stable | 0.0000/-0.6238/0.0000 | abrupt |

The log-ratio ranking has a changing domain. Counts below are for the
word-union returned by comparison.py; undefined statuses are not smoothed or
ranked. No empty-denominator status occurs in these twelve runs.

| Target | Reference | Defined | Zero reference | Zero target |
| --- | --- | --- | --- | --- |
| BEING | CONCEPT | 2861 | 2761 | 1267 |
| BEING | ESSENCE | 1987 | 3635 | 589 |
| BEING | book | 5622 | 0 | 1695 |
| BEING | other_two | 3154 | 2468 | 1695 |
| ESSENCE | BEING | 1987 | 589 | 3635 |
| ESSENCE | CONCEPT | 1855 | 721 | 2273 |
| ESSENCE | book | 2576 | 0 | 4741 |
| ESSENCE | other_two | 2148 | 428 | 4741 |
| CONCEPT | BEING | 2861 | 1267 | 2761 |
| CONCEPT | ESSENCE | 1855 | 2273 | 721 |
| CONCEPT | book | 4128 | 0 | 3189 |
| CONCEPT | other_two | 3022 | 1106 | 3189 |

Across all 18 comparison contrasts, the depth dependence is:

| Measure | k | Stable | Intermediate | Abrupt | Min J | Median J | Median ρ | Median R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| difference | 5 | 5 | 12 | 1 | 0.4286 | 0.6667 | 0.9000 | 0.8688 |
| difference | 10 | 5 | 12 | 1 | 0.2500 | 0.6667 | 0.7592 | 0.8424 |
| difference | 20 | 5 | 12 | 1 | 0.4286 | 0.7391 | 0.7602 | 0.8615 |
| difference | 50 | 5 | 12 | 1 | 0.3889 | 0.6954 | 0.7413 | 0.8562 |
| difference | 100 | 5 | 13 | 0 | 0.3423 | 0.7029 | 0.6908 | 0.8562 |
| ratio | 5 | 0 | 1 | 17 | 0.0000 | 0.0000 | -0.6923 | 0.0000 |
| ratio | 10 | 0 | 2 | 16 | 0.0000 | 0.0000 | -0.6471 | 0.0000 |
| ratio | 20 | 0 | 1 | 17 | 0.0000 | 0.0556 | -0.6015 | 0.0263 |
| ratio | 50 | 0 | 2 | 16 | 0.0000 | 0.0747 | -0.4996 | 0.0267 |
| ratio | 100 | 0 | 2 | 16 | 0.0000 | 0.0650 | -0.4381 | 0.0267 |


### Matched-passage depth and short-list audit

There are 5,271 matched-passage contrasts at each requested depth. At k=20,
5,040 have twenty terms on each side; 231 use a shorter common prefix
(77 distinct short paragraphs, each tested in three changed contexts). Nine
contrasts involve a one-word paragraph and have undefined rho. They are in
the intermediate bucket, never treated as stable or abrupt. The primary
per-context table includes these shorter lists. The full-depth-only audit
below avoids treating short lists as full-depth evidence.

| Requested k | Full-depth n | Stable | Intermediate | Abrupt | Median J | Median ρ | Median R | Shorter n | Undefined ρ, all n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 5238 | 2013 | 3161 | 64 | 1.0000 | 0.8857 | 0.8818 | 33 | 9 |
| 10 | 5193 | 2194 | 2999 | 0 | 0.8182 | 0.9152 | 0.9062 | 78 | 9 |
| 20 | 5040 | 2412 | 2628 | 0 | 0.9048 | 0.9414 | 0.9119 | 231 | 9 |
| 50 | 3972 | 2257 | 1715 | 0 | 0.9231 | 0.9668 | 0.9140 | 1299 | 9 |
| 100 | 1500 | 992 | 508 | 0 | 0.9608 | 0.9776 | 0.9225 | 3771 | 9 |

The k=10 stable/intermediate totals correct the earlier 2,178/3,015 to
**2,194/2,999**. All 16 reclassified cases have RBO exactly 9/10. The earlier
floating evaluation of the displayed formula returned 0.8999999999999999,
placing them below the inclusive stable boundary. Exact rational arithmetic
puts equality on the stable side when J and rho also pass. No primary k=20
class or headline local count changes from this arithmetic correction.

At k=5, 64 full-depth matched-passage contrasts meet the abrupt thresholds;
none do at k=10, 20, 50 or 100. Thus the negative primary screen does not
establish stability of a five-word display. These are large population
contrasts, not local nodal candidates. Repeated observations of the same
paragraphs are not independent trials or a statistical significance test.

Under the original average-rank reading, full-depth k=5 abrupt flags are
**98 rather than 64**, and k=10 has **one rather than zero**; k=20, 50 and 100
still have no abrupt flags. These convention comparisons use the same exact
boundary arithmetic as the corrected table. Full-depth class totals under the
original average-rank reading are:

| Requested k | Full-depth n | Stable | Intermediate | Abrupt |
| --- | --- | --- | --- | --- |
| 5 | 5238 | 2013 | 3127 | 98 |
| 10 | 5193 | 2194 | 2998 | 1 |
| 20 | 5040 | 2400 | 2640 | 0 |
| 50 | 3972 | 2248 | 1724 | 0 |
| 100 | 1500 | 991 | 509 | 0 |

The 64 k=5 flags concern 42 distinct paragraphs. Counts by own-doctrine
baseline and changed context are:

| Baseline | Changed context | k=5 flags |
| --- | --- | --- |
| BEING | BEING+ESSENCE | 2 |
| BEING | BEING+CONCEPT | 4 |
| BEING | BEING+ESSENCE+CONCEPT | 8 |
| ESSENCE | BEING+ESSENCE | 5 |
| ESSENCE | ESSENCE+CONCEPT | 4 |
| ESSENCE | BEING+ESSENCE+CONCEPT | 10 |
| CONCEPT | BEING+CONCEPT | 8 |
| CONCEPT | ESSENCE+CONCEPT | 3 |
| CONCEPT | BEING+ESSENCE+CONCEPT | 20 |

The lowest-RBO example is paragraph `25862694-5581-4f79-9d29-2b155d244380`,
ESSENCE → book: O=0.4000, J=0.2500, ρ=−0.8605, R=0.2624.
Only isolated words and ranks are shown, alphabetically by word; a dash means
absent from the displayed top five.

| Word | Own-doctrine rank | Book-context rank |
| --- | --- | --- |
| `accepted` | 4 | — |
| `customarily` | 5 | 4 |
| `indemonstrable` | — | 1 |
| `indisputably` | — | 2 |
| `said` | 2 | — |
| `singled` | — | 3 |
| `thought` | 1 | — |
| `were` | 3 | 5 |

This is a lexical profile change under a chosen context, not an observed
change of the source paragraph or a validated change in its philosophical
character. It disappears as an abrupt flag when the displayed depth grows.

### Why the whole-book log-ratio ranking changes sharply

The other-two → book contrast is especially diagnostic. Write t and o for
normalized target and other-two rates, and α for the target token fraction
of the book. The book rate is αt+(1−α)o, so the target-minus-book difference
is (1−α)(t−o). The unrounded difference ranking is therefore unchanged.
The actual rounded implementation also retains identical top rankings at
all five tested depths for all three doctrines (O=J=ρ=R=1). This is an
algebraic invariance, not a finding of intrinsic lexical quality.

On words with nonzero counts on both sides, the log ratio against the book
is monotone in the ratio against the other two. But target-only words had
undefined log ratios against the other two; adding the target to the book
makes them defined at the shared maximum log2(1/α). The measured tie sizes are:

| Target | Maximum log2 ratio | Words tied at maximum | Top-20 words with target count = book count | Top-20 singletons |
| --- | --- | --- | --- | --- |
| BEING | 1.251264 | 2468 | 20 | 16 |
| ESSENCE | 2.104138 | 428 | 20 | 14 |
| CONCEPT | 1.525621 | 1106 | 20 | 16 |

All twenty displayed words in each book-reference log ranking are target-only
words; alphabetical tie-breaking selects among the tied maxima. For example,
`abandonment` (1 occurrence) and `abscissa` (23 occurrences) both have the
BEING maximum 1.251264. Their equality is created by the reference overlap
and formula, not by equal frequency or a demonstrated shared concept. The
other-two and book log top-20 lists are disjoint for all three doctrines
(J=R=0, ρ=−0.6238). This is a real change in the defined ranking domain.
It is a large context change with a known zero/tie mechanism, not evidence
of a local, intrinsic nodal transition. This diagnostic was added after
observing the population results; it does not change the screen.

### Actual integer top_n sweep

Every integer from 5 through 100 was executed on each selected section:
288 public-engine calls, 288 overall lists and 4,704 document lists checked
against exact top_n=100 prefixes, including returned scores. There were
**zero** prefix/membership, rank or score failures. All 285 adjacent overall
comparisons have O=J=ρ=R=1 at their common depth (floating error below 10⁻¹⁵).
No leap was found from changing top_n itself. This agrees with the method:
normalization and overall averaging happen before truncation. This comparison
uses a common prefix depth. For the literal unequal display sets, the verified
nested lists instead have J(n,n+1)=n/(n+1): 0.8333 at 5 → 6, increasing to
0.9900 at 99 → 100; top-5 versus top-100 has J=0.0500 and overlap=1. These
are mechanical additions to a ranked prefix, with no rearrangement of the
existing terms.

| Section doctrine | Runs | Document lists checked | Prefix/score failures |
| --- | --- | --- | --- |
| BEING | 96 | 4032 | 0 |
| CONCEPT | 96 | 384 | 0 |
| ESSENCE | 96 | 288 | 0 |

### One-paragraph perturbations: drift and abrupt flags

A state contains the first 5…N canonical eligible chapter paragraphs. Each
step adds one paragraph. TF-IDF overall changes its averaged document set;
comparison keeps the full chapter target fixed and changes only the reference.
There are 178 transitions, each assessed in three ranking views (534 screens).
All have twenty available terms. This is not uniformly small in token size:

| Chapter | Steps | Min added tokens / previous tokens | Median | Max | Steps ≤1% | Steps ≤5% |
| --- | --- | --- | --- | --- | --- | --- |
| BEING | 57 | 0.0972% | 2.2379% | 36.6972% | 11 | 41 |
| CONCEPT | 91 | 0.0746% | 1.4587% | 34.8978% | 32 | 78 |
| ESSENCE | 30 | 0.4731% | 5.8721% | 16.5394% | 1 | 10 |

The percentage bins are descriptive follow-up summaries, not additional
criteria for the declared screen. Full step distributions are summarized
below; medians alone must not hide the abrupt flags.

| Chapter | Ranking | Steps | Stable | Intermediate | Abrupt | Median O | Median J | Median ρ | Median R | Min R | Nodal candidates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BEING | tfidf | 57 | 56 | 1 | 0 | 1.0000 | 1.0000 | 0.9895 | 0.9835 | 0.8891 | 0 |
| BEING | difference | 57 | 23 | 31 | 3 | 0.9500 | 0.9048 | 0.9130 | 0.8777 | 0.0673 | 0 |
| BEING | ratio | 57 | 12 | 37 | 8 | 0.9000 | 0.8182 | 0.8036 | 0.8910 | 0.0000 | 0 |
| CONCEPT | tfidf | 91 | 89 | 2 | 0 | 1.0000 | 1.0000 | 0.9961 | 0.9913 | 0.9158 | 0 |
| CONCEPT | difference | 91 | 33 | 56 | 2 | 0.9000 | 0.8182 | 0.9078 | 0.8917 | 0.0000 | 0 |
| CONCEPT | ratio | 91 | 28 | 55 | 8 | 0.9000 | 0.8182 | 0.7733 | 0.8701 | 0.0000 | 0 |
| ESSENCE | tfidf | 30 | 29 | 1 | 0 | 1.0000 | 1.0000 | 0.9925 | 0.9832 | 0.9042 | 0 |
| ESSENCE | difference | 30 | 5 | 23 | 2 | 0.9000 | 0.8182 | 0.8821 | 0.7916 | 0.0260 | 0 |
| ESSENCE | ratio | 30 | 1 | 25 | 4 | 0.8000 | 0.6667 | 0.5634 | 0.7472 | 0.0000 | 0 |

Every abrupt flag is located below by reference passage count before →
after. The added token fraction is relative to the preceding reference. A
dash in a surrounding-evidence column means there are not enough preceding
or following states to assess that requirement. “Persistence” compares both
following results with the pre-boundary result, not just with each other.

| Chapter | Ranking | Paragraphs | Added tokens | Added % | O | J | ρ | R | Three prior stable | Persists two states |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BEING | difference | 59 → 60 | 113 | 2.0527% | 0.6500 | 0.4815 | 0.4954 | 0.5781 | no | yes |
| BEING | difference | 60 → 61 | 95 | 1.6910% | 0.4500 | 0.2903 | 0.3526 | 0.5339 | no | — |
| BEING | difference | 61 → 62 | 73 | 1.2778% | 0.0500 | 0.0256 | -0.4662 | 0.0673 | no | — |
| BEING | ratio | 5 → 6 | 200 | 36.6972% | 0.5500 | 0.3793 | 0.1499 | 0.4285 | — | yes |
| BEING | ratio | 8 → 9 | 166 | 19.1908% | 0.6500 | 0.4815 | 0.2504 | 0.4405 | no | yes |
| BEING | ratio | 21 → 22 | 306 | 15.0665% | 0.6000 | 0.4286 | 0.2085 | 0.4702 | no | yes |
| BEING | ratio | 50 → 51 | 316 | 7.0757% | 0.5000 | 0.3333 | 0.3229 | 0.6602 | no | yes |
| BEING | ratio | 55 → 56 | 171 | 3.3754% | 0.6500 | 0.4815 | 0.2787 | 0.4651 | no | yes |
| BEING | ratio | 58 → 59 | 99 | 1.8313% | 0.5000 | 0.3333 | 0.3171 | 0.6325 | no | yes |
| BEING | ratio | 60 → 61 | 95 | 1.6910% | 0.5500 | 0.3793 | -0.1095 | 0.2257 | no | — |
| BEING | ratio | 61 → 62 | 73 | 1.2778% | 0.0000 | 0.0000 | -0.6238 | 0.0000 | no | — |
| CONCEPT | difference | 93 → 94 | 148 | 0.9338% | 0.6500 | 0.4815 | 0.4817 | 0.5992 | no | yes |
| CONCEPT | difference | 95 → 96 | 152 | 0.9426% | 0.0000 | 0.0000 | -0.6238 | 0.0000 | no | — |
| CONCEPT | ratio | 6 → 7 | 220 | 22.0662% | 0.6000 | 0.4286 | 0.0301 | 0.4408 | — | yes |
| CONCEPT | ratio | 8 → 9 | 461 | 34.8978% | 0.6000 | 0.4286 | 0.3452 | 0.5511 | no | yes |
| CONCEPT | ratio | 9 → 10 | 322 | 18.0696% | 0.6000 | 0.4286 | 0.0981 | 0.3404 | no | yes |
| CONCEPT | ratio | 13 → 14 | 706 | 26.0133% | 0.5500 | 0.3793 | 0.4234 | 0.6222 | no | yes |
| CONCEPT | ratio | 25 → 26 | 607 | 12.4769% | 0.6500 | 0.4815 | 0.0248 | 0.4359 | no | yes |
| CONCEPT | ratio | 93 → 94 | 148 | 0.9338% | 0.6500 | 0.4815 | 0.2981 | 0.6131 | no | yes |
| CONCEPT | ratio | 94 → 95 | 127 | 0.7938% | 0.6500 | 0.4815 | 0.4695 | 0.6038 | no | — |
| CONCEPT | ratio | 95 → 96 | 152 | 0.9426% | 0.0000 | 0.0000 | -0.6238 | 0.0000 | no | — |
| ESSENCE | difference | 33 → 34 | 423 | 6.0231% | 0.4000 | 0.2500 | -0.2421 | 0.1991 | no | — |
| ESSENCE | difference | 34 → 35 | 258 | 3.4649% | 0.0500 | 0.0256 | -0.5237 | 0.0260 | no | — |
| ESSENCE | ratio | 14 → 15 | 390 | 16.5394% | 0.5500 | 0.3793 | 0.1670 | 0.3823 | no | yes |
| ESSENCE | ratio | 31 → 32 | 445 | 6.9046% | 0.4500 | 0.2903 | 0.0279 | 0.2607 | no | yes |
| ESSENCE | ratio | 33 → 34 | 423 | 6.0231% | 0.3500 | 0.2121 | 0.0611 | 0.3846 | no | — |
| ESSENCE | ratio | 34 → 35 | 258 | 3.4649% | 0.0000 | 0.0000 | -0.6238 | 0.0000 | no | — |

There are 27 abrupt flags, including interior changes as well as endpoints.
**Zero** meets the complete plateau-plus-persistence nodal screen: 25 fail the
three-step stable lead-in and two lack enough preceding observations. All 16
flags with two following observations pass persistence; 11 lack enough following
observations. The negative nodal result therefore is not absence of persistent
abrupt change. The rule is deliberately demanding and its negative result is
conditional on that rule.

Under the original average-rank reading, there are **28 local flags** (7 rate
differences, 21 log ratios), still zero nodal candidates. BEING log ratio
56 → 57 additionally passes: rho changes from 0.5593 (capped) to 0.4472
(average ranks). Its stable/intermediate/abrupt totals become 12/36/9 rather
than 12/37/8. Two CONCEPT steps change from stable to intermediate: rate
difference 64 → 65 and log ratio 40 → 41, each with rho 0.9076 → 0.8989.
The corresponding CONCEPT totals become 32/57/2 and 27/56/8 rather than
33/56/2 and 28/55/8. All other local class totals are unchanged. This checks
the original reading without hiding the effect of amending the convention.

#### Endpoint mechanism

At the last step, reference and target become identical. All returned rate
differences and log ratios become zero, leaving one giant alphabetical tie.
The following post-result diagnostic confirms the mechanism; it is not a
new screen. **Six of the 27 flags** are final self-comparison endpoints (two
per chapter); **21 flags remain** when they are excluded. A small final input
increment can therefore change the displayed ranking sharply while reducing
every measured lexical difference to zero.

| Chapter | Final added tokens | Added % | Rate distinct scores before → after | Log distinct scores before → after | Words tied at zero after |
| --- | --- | --- | --- | --- | --- |
| BEING | 73 | 1.2778% | 71 → 1 | 35 → 1 | 1046 |
| CONCEPT | 152 | 0.9426% | 123 → 1 | 52 → 1 | 1441 |
| ESSENCE | 258 | 3.4649% | 101 → 1 | 56 → 1 | 881 |

Five flagged ranking comparisons occur across three increments of at most 1%
in reference tokens; fourteen flags occur across nine increments of at most
5%. Two of the five ≤1% flags are endpoints; three remain across two
nonterminal increments. The smallest is CONCEPT log-ratio 94 → 95: 127 added
tokens on 15,998
(0.7938%), J=0.4815, ρ=0.4695, R=0.6038. It lacks the preceding stable plateau
and enough following states. Small input changes can therefore cause marked
rank changes here; the stronger nodal claim remains unestablished.

The comparison sweep intentionally permits overlapping scopes, as the
public engine does. Its self-reference endpoint is a calculational limit,
not a claim that the source chapter changes its philosophical determination.
Interior flags also exist; the endpoint does not explain away all volatility.
No exhaustive mechanistic or linguistic classification of interior flags was
performed.

### Adjacent sibling-section references

BEING: 3 direct sibling leaf scopes; 2 tested reference scope(s).

- `/BEING/ii-magnitude-quantity/1-quantity/a-pure-quantity/1-remark-1.txt`
- `/BEING/ii-magnitude-quantity/1-quantity/a-pure-quantity/2-remark-2.txt`

| Ranking | Reference index | Depth | O | J | ρ | R | Screen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| difference | 1 → 2 | 20 | 0.0000 | 0.0000 | -0.6238 | 0.0000 | abrupt |
| ratio | 1 → 2 | 20 | 0.0000 | 0.0000 | -0.6238 | 0.0000 | abrupt |

CONCEPT: 4 direct sibling leaf scopes; 2 tested reference scope(s).

- `/CONCEPT/i-subjectivity/3-the-syllogism/b-the-syllogism-of-reflection/00-introduction.txt`
- `/CONCEPT/i-subjectivity/3-the-syllogism/b-the-syllogism-of-reflection/a-the-syllogism-of-allness.txt`

| Ranking | Reference index | Depth | O | J | ρ | R | Screen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| difference | 1 → 2 | 20 | 0.2000 | 0.1111 | -0.4091 | 0.0811 | abrupt |
| ratio | 1 → 2 | 20 | 0.3000 | 0.1765 | -0.3948 | 0.1527 | abrupt |

ESSENCE: 2 direct sibling leaf scopes; 2 tested reference scope(s).

- `/ESSENCE/ii-appearance/1-concrete-existence/a-the-thing-and-its-properties/b-property/00-introduction.txt`
- `/ESSENCE/ii-appearance/1-concrete-existence/a-the-thing-and-its-properties/b-property/remark.txt`

| Ranking | Reference index | Depth | O | J | ρ | R | Screen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| difference | 1 → 2 | 20 | 0.1000 | 0.0526 | -0.5946 | 0.0239 | abrupt |
| ratio | 1 → 2 | 20 | 0.1000 | 0.0526 | -0.6420 | 0.0160 | abrupt |

All three selected scopes have a neighbor. Each nearest-neighbor contrast
above includes the target itself as one reference, so self-comparison ties
are a material limitation. These are discrete section replacements, not
one-parameter local nodes.


#### Additional adjacent references excluding the target

To distinguish section sensitivity from self-comparison, an explanatory
follow-up extends the reference window to all direct sibling leaves and
excludes the target. The thresholds stay unchanged. Only pairs still adjacent
in the original sibling order are compared. Reference indices below refer
only to this follow-up list.

BEING:

- 1: `/BEING/ii-magnitude-quantity/1-quantity/a-pure-quantity/00-introduction.txt` — 4 paragraphs, 463 tokens, 154 types; log statuses: 100 defined, 688 zero-reference, 54 zero-target.
- 2: `/BEING/ii-magnitude-quantity/1-quantity/a-pure-quantity/1-remark-1.txt` — 6 paragraphs, 792 tokens, 325 types; log statuses: 161 defined, 627 zero-reference, 164 zero-target.

CONCEPT:

- 1: `/CONCEPT/i-subjectivity/3-the-syllogism/b-the-syllogism-of-reflection/a-the-syllogism-of-allness.txt` — 6 paragraphs, 875 tokens, 235 types; log statuses: 88 defined, 42 zero-reference, 147 zero-target.
- 2: `/CONCEPT/i-subjectivity/3-the-syllogism/b-the-syllogism-of-reflection/b-the-syllogism-of-induction.txt` — 6 paragraphs, 855 tokens, 237 types; log statuses: 77 defined, 53 zero-reference, 160 zero-target.
- 3: `/CONCEPT/i-subjectivity/3-the-syllogism/b-the-syllogism-of-reflection/c-the-syllogism-of-analogy.txt` — 6 paragraphs, 1494 tokens, 334 types; log statuses: 87 defined, 43 zero-reference, 247 zero-target.

ESSENCE:

- 1: `/ESSENCE/ii-appearance/1-concrete-existence/a-the-thing-and-its-properties/b-property/remark.txt` — 1 paragraphs, 536 tokens, 200 types; log statuses: 74 defined, 109 zero-reference, 126 zero-target.

| Target | References | Ranking | O | J | ρ | R | Screen |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BEING | 1 → 2 | difference | 0.6500 | 0.4815 | 0.2342 | 0.3505 | abrupt |
| BEING | 1 → 2 | ratio | 0.2500 | 0.1429 | -0.2161 | 0.2045 | abrupt |
| CONCEPT | 1 → 2 | difference | 0.8000 | 0.6667 | 0.7085 | 0.5924 | intermediate |
| CONCEPT | 1 → 2 | ratio | 0.5500 | 0.3793 | 0.0988 | 0.4806 | abrupt |
| CONCEPT | 2 → 3 | difference | 0.8000 | 0.6667 | 0.7017 | 0.7326 | intermediate |
| CONCEPT | 2 → 3 | ratio | 0.2500 | 0.1429 | -0.1435 | 0.2723 | abrupt |

This adds three contrasts without a self-reference: one abrupt and two
intermediate rate-difference screens; three abrupt log-ratio screens. Thus
self-comparison does not explain every adjacent-section change. ESSENCE has
only one non-target sibling, so no two-reference contrast can be made there.
No plateau/persistence claim follows from this small discrete reference set.


### What this shows about Reflection and Measure

The empirical evidence supports a bounded claim: these are reproducible
lexical profiles relative to explicitly chosen units, populations, lexical
eligibility and ranking conventions. Some changes are mild by the screen;
others materially change a very short displayed profile, or change which
log ratios exist. The paired count controls and exact top_n prefix checks
separate grouping effects and display effects from changed source words.
They do not establish that the text itself acquires a new determination.

This is consistent with the comparing standpoint argued in
[READING_BEING §9](READING_BEING.md#9-comparison-series-and-elective-affinity-stage-f-22-october-2026)
and the more qualified verdict in [REEVALUATION §3.3](REEVALUATION.md#33-comparative-word-measures-real-measure-or-reflection).
The sweep adds empirical distinctions to that argument; it does not deduce
a philosophical placement from a stability score. High stability would not
make the chosen population intrinsic. High sensitivity would not by itself
refute Measure, since a genuine measure relation could have transitions.
A top-term list is also not an independently validated account of a text's
philosophical character.

The prominent discontinuity mechanisms have calculational explanations:
rounded-score ties, changing eligibility for unsmoothed ratios, and selection
of a very short ranked display. Even an abrupt rank transition under a small
input increment would require a separate linguistic or philological argument
that the transition constitutes a specified quality, rather than a convenient
analyst's profile. No such domain argument or independently judged quality
labels were tested here. The declared numerical screen is a research device,
not a definition of Hegel's nodal line.

Limits matter: one private English edition and one eligibility policy; three
deterministically sampled chapters and their leaf scopes; only supported
paragraph documents and the single-file collapsed endpoint; canonical prefix
order, not randomized order; raw TF with no stop-word removal; no claim about
other languages, editions, authors, segmenters, full multi-section document
populations or all possible parameters. Common function words can make top
TF-IDF ranks look stable while less frequent terms change. Correlated
observations of the same paragraphs supply no significance test or confidence
interval. Common-depth handling can make short lists look more stable; the
full-depth audit exposes this limitation. RBO's p=0.9 emphasizes early ranks,
whereas Jaccard treats the whole displayed set equally.

A subsequent inquiry could predefine a linguistic quality, justify the
population belonging to it, and test predictions against independent human
judgments and other segmentations. That would be a new study. This task
introduces no ESSENCE method, public API, schema, dependency, persistent study,
register edit, module move or new Measure occupant. E2 remains *Provisional*
under Reflection; the stronger Measure claim remains unproved.

### Reproduction and verification

The study was run with `/home/dima/Projects/code/sol/.venv/bin/python -B` from
this checkout. The public API call recipe is:

1. `core.load_snapshot(Path(corpus))`; `analyze_words(CoreProvider(snapshot))`
   gives eligible IDs, canonical order, reader paths and token counts. Group
   those IDs by doctrine; determine the median-based chapter/section scopes
   as specified above. Retain the same verified snapshot throughout.
2. `analyze_tfidf(CoreProvider(snapshot, {"kind": "passages", "ids": ids}),
   top_n=100)` supplies each of the seven populations and selected unit scopes.
   Match document rows by receipt input ID, never by a new positional order
   across different scopes. Compute the stated rank metrics on returned words.
3. Join `prose_text` for exactly the receipt IDs to a temporary UTF-8 file;
   call `analyze_tfidf(FileProvider(path), top_n=100)` and verify full word/count
   equality before comparing to the paragraph population. Delete temporary
   files. Repeat for the ten scopes reported above.
4. Call `compare_words(target, reference=reference)` for the twelve doctrine
   pairs/populations. Sort the returned signed differences and defined signed
   ratios descending, with normalized-word tie-breaks. Count all undefined
   statuses. Do not reimplement or smooth the native measures.
5. For each selected section, call `analyze_tfidf` at every integer top_n
   5…100 and compare every returned overall/document list, including scores,
   with the corresponding prefix of the top_n=100 result. For each chapter,
   call the public engines on prefixes of 5…N eligible paragraphs; hold the
   full chapter target fixed for comparison. Apply the local screen to each
   consecutive pair and its surrounding observations. Run available sibling
   references in canonical order, with the target section held fixed.
6. Recheck with `core.verify_snapshot_current(snapshot)`. The engine also
   verifies sources for each study. Compute no prose similarity and emit only
   isolated words, counts, numerical summaries and provenance.

The declaration in `fe1aeef` precedes results commit `30ef3d8`; Git history
does not establish that it precedes the first private corpus read. The
numerical cutoffs were not adjusted, but `30ef3d8` amended the missing-rank
convention from the original average-rank wording to capped rank k+1. The
review-response recomputation reports both readings and corrects the RBO
equality boundary using exact rational arithmetic, as specified above. The k=5
example, whole-book tie explanation, expanded sibling window and token-increment/
endpoint diagnostics are explanatory follow-ups, not changes to the primary
cutoffs or nodal requirements. The task-specific script stays out of Git
as requested; these public calls, complete formulas, selection rules and corpus
binding support independent reproduction without distributing private inputs.

- Full suite: `python -B -m unittest discover -s tests` — **1,259 tests OK**,
  7 skipped, 4 expected failures, 119.882 s, isolated XDG configuration/data/
  state/cache paths. Source and tests are unchanged from the tested baseline.
- Local synthetic arithmetic/screen checks — 11 assertions passed, including
  identical/disjoint/reversed rankings, the finite RBO value 0.55 for a known
  two-word pair, missing-rank rho 0.5, and plateau/persistence versus boundary
  cases. These are checks on the research program, not new product tests.
- Review response (23 October 2026): fresh public-provider computations verify
  all 178 local transitions / 534 screens and all 5,271 matched-passage
  contrasts at each of five depths under both rank conventions. Exact rational
  Jaccard/RBO and signed covariance/variance threshold comparisons verify the
  convention effects and inclusive boundary correction reported above. Corpus
  bindings match the original run and final snapshot verification passes.
  Full suite repeated: **1,259 tests OK**, 7 skipped, 4 expected failures,
  118.279 s, with isolated XDG paths. Verification code and numeric outputs
  remain under `/tmp/sol-e2-revision-*`, outside Git.
- `scripts/check_docs.py` and `git diff --check` — results recorded in HANDOFF
  after the final report edit. External links are not network-checked.
