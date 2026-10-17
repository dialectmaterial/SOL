# One reproducible lexical experiment

The first ESSENCE experiment asks a limited question: how often does one literal
word occur in the eligible prose of Being, Essence, and Concept?

This is a distribution of vocabulary, not a model of the movement of the Idea.
An occurrence of “being” does not establish whether it functions as a logical
determination or an ordinary verb. Counts can locate passages for inquiry; the
interpretation remains yours.

## Use it in an ordinary shell

With an indexed corpus already configured:

```sh
sol analyze term ground
sol analyze term ground --doctrine essence --limit 5
sol analyze term ground --json > ground.sol-analysis.json
sol analyze check ground.sol-analysis.json
```

Use `--corpus DIRECTORY` when you want to select a corpus explicitly. No PDF
extraction, workspace, actor, Kitty, or optional scientific library is required.
The aggregate installation includes this experiment; it is not a separately
published ESSENCE distribution. Help works without a corpus.

The summary shows total occurrences, eligible word tokens, matching passages,
and counts by doctrine. Representative matches retain their existing UUID,
virtual location, printed/PDF pages, and a short context. `--limit` bounds these
representative passages, not the counts: all eligible passages are measured.
Zero matches are a valid result. Exclusion reasons partition the entire input
corpus: attribution, record type/generated text, pending review, invalid reader
location, then the optional doctrine filter. Each excluded record is counted
once, under its first applicable reason.

## Carry an inquiry out of BEING and back

From the BEING reader in `sol-kitty`, select a passage and use `essence open`.
In its native Zsh pane:

```sh
sol analyze term ground --reference "$SOL_REFERENCE_FILE"
sol analyze term ground --reference "$SOL_REFERENCE_FILE" --json > ground.sol-analysis.json
sol analyze check ground.sol-analysis.json
```

The reference records the passage from which the inquiry started. It does not
silently restrict the study to that passage or grant workspace-write authority.
Choose a matching UUID shown in the result, then enter `sol reference return ID`,
replacing `ID` with that UUID. Back in BEING, use `essence check` and deliberately
accept with `essence return`. If you changed your reading position meanwhile,
`essence return --accept-move` acknowledges that move without bypassing validation.

Results never become notes, source-review testimony, or philosophical relations
automatically. An analysis artifact is not a navigation packet. The existing
[handoff](HANDOFF.md) carries a selected canonical reference back to the reader.

## Exactly what is measured

Version 1 includes records attributed to `G. W. F. Hegel` with `role: main_text`,
types `paragraph`, `quotation`, or `list_item`, and a declared reader location in
one of the three doctrines. Editorial records, formulas, retired records,
unmapped or invalid virtual file locations, explicitly generated text, and transcriptions marked `needs_review` or
`needs_visual_review` are excluded. The result discloses exclusions rather than
presenting this subset as every word of the edition. An explicit doctrine filter
restricts the eligible subset further.

Section heading records and heading metadata are therefore already excluded.
This version-1 lexical experiment otherwise counts canonical visible text with
its recorded facsimile mask; it is not the model-input projection. For future
vectorization, use the separate [prose-only input](PROSE_INPUTS.md), which also
removes embedded structural headings and image labels while retaining ancestry
as metadata.

Tokens begin with a Unicode letter and continue through letters and combining
marks. Internal straight or curly apostrophes stay within a token; numbers,
underscores, and hyphens separate tokens. Comparison uses NFC normalization,
casefolding, and a shared apostrophe spelling. There is no stemming,
lemmatization, stop-word removal, substring matching, or conceptual search.
The query must be one complete token under this rule.

The length-adjusted frequency is:

```text
occurrences per 10,000 tokens = 10,000 × occurrences / eligible token count
```

A zero-token group has no rate, represented as `null`, rather than an invented
zero frequency. JSON rates are rounded to six decimal places; human summaries
show three. The exact integer counts remain available. First-match offsets count codepoints in the
canonical `plain_text`, not terminal-wrapped text or UTF-8 bytes. Context is
bounded to 80 codepoints on either side. Converter-generated trailing facsimile
captions are masked according to the recorded method without shifting offsets.

## Reproducible, not authenticated

The version-1 `sol.term-study` artifact records the method and Unicode database
version, normalized query, selection, representative limit, corpus/edition/source
binding, exact manifest/index generation, summaries, exclusions, and source-bound
matches. It contains no timestamp or newly allocated passage identity.

`sol analyze check` recomputes the study against the independently selected local
corpus and requires exact agreement. Altered counts, contexts, provenance, method,
unsupported runtime versions, or a changed corpus are refused. Rebuilding after
even an unrelated correction requires a new study. It never repairs an artifact
or overwrites the corpus. `--json` on check emits a verification receipt, not a
replacement study.

Recomputation shows agreement with this local corpus and declared method. It does
not authenticate an author, verify the physical PDF, or prove transcription
accuracy. The exclusion policy reduces known uncertainty; it does not certify
the remaining prose.

Saved results can contain excerpts. Files named `*.sol-analysis.json` are excluded
from Git and release archives; save them outside the temporary handoff directory.
The CLI prints to standard output and does not choose a storage location. Ordinary
Unix redirection is your explicit save operation and follows ordinary overwrite
rules. No result-ingestion database or machine-generated attribution is introduced.
