# E2 sensitivity study — stage F

Research only. E2 methods, schemas and the placement register are unchanged.

## Prospective protocol

Written on 22 October 2026 before reading corpus statistics or rankings; code
baseline `729ff24475e0743c86491efe14e1b2e6a4dd35f5`. The thresholds below are
operational screening conventions, not definitions of philosophical quality or
statistical significance. Negative screens will be reported.

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
  ranks on the union, missing words tied at k+1 (average ranks for that tie);
  RBO with p=0.9 = (1-p) sum[d=1..k] p^(d-1) A_d + p^k A_k,
  A_d = prefix intersection/d. Use common available depth for short lists;
  empty/constant-rank rho is undefined. Lexical tie-break is deterministic,
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

Pending execution of the prospective protocol.
