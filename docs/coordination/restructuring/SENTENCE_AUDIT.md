# Experiment A: sentence-boundary audit — 23 October 2026

The private Cambridge English-translation corpus was read **only**. This report
contains aggregate counts, error categories and abbreviation strings, with no
source sentences/passages. The audit concerns punctuation-based segmentation,
not Hegel's German syntax or the philosophical validity of sentence units.

## Sample and review procedure

- Population: **1,757** records accepted by the unchanged v1 `_selection` with
  corpus scope, in `core.load_snapshot(...).records` canonical order. This
  excludes pending-review records and non-Hegel/non-main-text records. No
  selected record had a facsimile-label mask. The population is not all book
  records and does not measure excluded transcriptions.
- Draw: `random.Random(20261023).sample(eligible, 60)`, without replacement,
  Python **3.14.8**; **60 passages**, **73,966 codepoints**. No rejection,
  substitution, punctuation-based enrichment or seed search.
- Codex read all 60 complete passages in draw order, marking the ends of every
  sentence and checking every punctuation mark, including punctuation that
  does **not** divide sentences. Codepoint end positions were displayed for
  navigation, but v1 predictions were not displayed until gold was frozen.
  This is a **single agent's hand-style reading**, not independent human
  adjudication. No second annotator or agreement estimate is claimed.
- Frozen annotations contain only ordered record IDs, UTF-8 text SHA-256s and
  sorted internal end offsets. They remain outside Git at
  `/tmp/sentence-audit-gold.json`; private review text also remains outside Git.
  The public sampling/scoring script prints aggregates and digests only.

Reproduction identities (not source text):

| Item | SHA-256 |
| --- | --- |
| Corpus manifest | `3ac1f6dd1bbbc73124cff625cd3898adb76b91d4470083dde53a63e4421d8dab` |
| Corpus index, before and after | `91b1d25a60a914bd3644df038179583c8690b396cecb2e676ddfc2d6a6f36269` |
| Ordered sample identity | `0d2c2efe71c730c7caae9e6d151904c00cf3521d97ba90b41c1ef9a04b54b262` |
| Frozen annotation JSON bytes | `3c6f69a61980f89d0d4b37debf07841ffeb5f4375a196ccdd53ea96944708d25` |

The sample digest hashes the concatenation, in draw order, of
`record_id + ":" + sha256(plain_text UTF-8) + "\n"`. Use the same corpus
generation and Python sampling implementation to reselect exactly:

```sh
python -B scripts/sentence_audit.py --corpus /absolute/path/to/local-corpus
python -B scripts/sentence_audit.py --corpus /absolute/path/to/local-corpus \
  --annotations /tmp/sentence-audit-gold.json
```

The first command reproduces selection and coverage without annotations. The
second reproduces scores when the local annotation file is available. To
independently repeat the review, use `sample_records(snapshot)` from that script,
read each row privately, and create a JSON array in draw order, each object with
`id`, `text_sha256` and `ends` (sorted distinct internal half-open codepoint end
offsets, excluding `len(plain_text)`). Do not derive gold from either segmenter.
Gold is deliberately not published as a corpus-derived artifact; another
reviewer can reproduce the draw and challenge the aggregate result by rereading.

## Hand-style boundary rules

1. A full stop, question mark or exclamation mark ends a sentence when the
   surrounding syntax ends an utterance. Closing quotation marks/brackets and
   immediately attached footnote callouts belong to that sentence. Boundaries
   are **after** these characters, before intervening whitespace. Capitalization
   is evidence, not a necessary condition of the hand judgment.
2. A lexical/citation abbreviation, a person's initial, a decimal point or an
   enumerator is not itself a sentence end. An abbreviation can also end a
   sentence when the syntax warrants it. Opening Arabic list numbers stay
   attached to their item; a section sign and its number do not divide prose.
3. Ellipses divide only when they finish an utterance, not when they denote
   omission, hesitation within an utterance or continuation of a series.
4. Quotations may contain multiple sentences. Citation abbreviations inside
   brackets do not divide sentences; genuine complete sentences in a
   parenthetical passage do. Brackets alone are not boundary evidence.
5. Semicolons and colons are **not** sentence boundaries, including before a
   capitalized clause or a list. A physical wrap alone is not a boundary.
   Record ends terminate the available segment; do not infer continuation into
   another record or manufacture a sentence at a list marker.
6. Final fragments remain available segments. A terminal punctuation boundary
   preceding a stranded punctuation-only tail is retained. Score raw segmenter
   spans, before the study drops zero-word segments; do not silently remove
   numeral-only false splits. Forced record-final ends are excluded from the
   precision/recall denominator, avoiding automatic credit for 60 ends.

## Results and coverage

Exact internal end-offset matching: TP is a predicted end also in gold, FP an
extra predicted end, FN a gold end omitted. Precision = TP/(TP+FP); recall =
TP/(TP+FN). End-position shifts count as both FP and FN; none occurred here.

| Method | Gold ends | Predicted ends | TP | FP | FN | Precision | Recall | Passages with errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `punctuation-rules-v1` | 282 | 286 | 281 | 5 | 1 | 98.25% | 99.65% | 6/60 |
| `punctuation-rules-v2` | 282 | 282 | 282 | 0 | 0 | 100.00% | 100.00% | 0/60 |

Mutually exclusive error attribution; coverage counts are occurrences, not
independent observations or denominators for category-specific accuracy:

| Category | Observed coverage | V1 FP | V1 FN | V2 FP | V2 FN |
| --- | --- | ---: | ---: | ---: | ---: |
| Abbreviations | 8 abbreviation occurrences, 9 periods (strings below) | 0 | 0 | 0 | 0 |
| Initial chains / section sign | 0 / 0 | 0 | 0 | 0 | 0 |
| Ellipses | 0 | 0 | 0 | 0 | 0 |
| Quotations / brackets | 11 curly double-quote pairs; 34 round and 1 square opening brackets | 0 | 0 | 0 | 0 |
| Semicolons / colons, by design | 156 / 10 | 0 | 0 | 0 | 0 |
| Opening numbered-list markers | 5 | 5 | 0 | 0 | 0 |
| Attached footnote callouts | 1 bare numeric callout after terminal punctuation | 0 | 1 | 0 | 0 |
| Physical newlines | 0 | 0 | 0 | 0 | 0 |
| Other | No additional errors | 0 | 0 | 0 | 0 |

Abbreviation occurrences: `e.g.` ×1, `p.` ×1, `etc.` ×2, `Geom.` ×1,
`Lib.` ×1, `Prop.` ×1, `schol.` ×1. The other requested strings `i.e.`,
`cf.`, `pp.` and initial chains are **absent**, not validated by this sample.
There are also no sentence-final abbreviations or lowercase starts requiring
an exception to v1. Zero errors in an absent category establish no accuracy.

The six errors are material for exact source offsets and sentence-length
measurement. Five are numeral-only false sentences that the downstream token
filter already drops, but the retained first-sentence offsets omit the item
marker. The footnote case merges two word-bearing sentences. On exactly these
60 records the provider studies measure **340 → 341 sentences**, the same
**12,319 word tokens**, and **6 → 1 empty segments** (the remaining segment is a
punctuation-only tail). Both methods' artifacts check by recomputation against
the unchanged corpus. Raw boundary scores above are not token-filtered scores.

## V2 rules, compatibility and limits

`segment(text)` and its v1 metadata remain unchanged. The separate
`segment_v2(text)` adds only:

- Suppress a period after a line-leading Arabic integer followed by horizontal
  whitespace. Keep the marker with its item. Roman/letter enumerators and other
  list conventions receive no new heuristics.
- Consume an attached bare, square-bracketed or superscript numeric footnote
  callout after terminal punctuation/closing quotes or brackets, before testing
  whitespace and the next sentence's opening. Include it in the preceding
  sentence's source span. Do not treat a period immediately after a digit as
  introducing a callout, preserving decimals. Bare numbers in other contexts
  remain ambiguous; this is a deterministic heuristic, not note identification.

Both methods use the same declared abbreviation list (case-folded strings,
without the final period): `approx`, `art`, `cf`, `ch`, `chap`, `cit`, `e.g`,
`ed`, `eds`, `esp`, `ff`, `fig`, `i.e`, `ibid`, `loc`, `mr`, `no`, `nos`,
`op`, `p`, `pp`, `sec`, `st`, `trans`, `viz`, `vol`, `vols`, `vs`.
Single-letter entries apply only in lowercase; logical uppercase letters still
end sentences. Initial chains retain v1's rule. Citation strings not in this
list are handled only by v1's bracket policy; this audit does not expand the
list based on protected citations.

The **interface/API/CLI default stays v1**. V2 is explicit through
`analyze_sentences(provider, segmentation="punctuation-rules-v2")` or
`sol essence sentences --segmentation punctuation-rules-v2 ...`. An explicit
CLI method uses the existing provider artifact protocol **v2**; its algorithm
is `sentence-length-distribution-providers-v2`. Artifact protocol versions and
punctuation-method versions are separate. Checking selects the exact recorded
method, with no user override. Legacy snapshot studies, ordinary corpus CLI
output, protocol-v1 artifacts and old provider-v1-method artifacts keep their
original behavior and encoding. No schema, dependency or canonical data changes.

V2 was designed **after** scoring v1 and remeasured on the **same frozen gold**:
its perfect score is an in-sample correction result, **not a held-out accuracy
claim**. The sample is small, clustered by passage, and rare categories are
missing. No confidence interval assuming independent punctuation marks is
claimed. Bracketed/superscript callouts and most abbreviations have synthetic
coverage only. Both methods still have v1's known limits on mid-sentence
parenthetical sentences, physical line wraps, sentence-final abbreviations and
lowercase starts; the four expected failures remain. A separate human review
and unseen sample should precede changing the interface default.

`tests/test_sentence_v2.py` uses invented text to cover both new rules, decimal
and variable guards, every declared abbreviation, initials, ellipses, quotes,
brackets, semicolons/colons, retained limitations, exact spans, method selection,
artifact checks/tampering and legacy compatibility. The checked-in provider-v1
fixture was captured from main before implementation; four older snapshot
fixtures also continue to check byte-for-byte. `tests/test_sentence_audit.py`
checks scoring denominators and refuses foreign/invalid gold metadata.
