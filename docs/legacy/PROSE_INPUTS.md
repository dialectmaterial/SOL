# Prose as model input; headings as context

SOL already distinguishes canonical `section` records from `paragraph`,
`quotation`, and `list_item` records. Section titles, passage `heading` fields,
reader titles, paths, and canonical parent links describe organization. They
are not additional sentences of the passage. Canonical `plain_text` means
visible text, however: it also renders headings and image labels when these
occur in a record's Markdown. It is not by itself a prose-only feature policy.

## Prepare input in ESSENCE

```sh
sol analyze prose
sol analyze prose --json > prose.sol-analysis.json
sol analyze prose --corpus /path/to/local-corpus --json > prose.sol-analysis.json
```

The first command summarizes eligibility. The JSON export supplies one row per
eligible passage. Model inputs must read **only `passages[].text`**:

```python
import json

with open("prose.sol-analysis.json", encoding="utf-8") as stream:
    dataset = json.load(stream)

texts = [row["text"] for row in dataset["passages"]]
ids = [row["id"] for row in dataset["passages"]]
contexts = [row["metadata"]["ancestry"] for row in dataset["passages"]]
# Pass texts to a vectorizer or embedding model. Retain ids to recover sources.
```

Do not vectorize serialized rows, the complete JSON, or whole canonical Markdown
documents. Those include organizational labels and provenance alongside prose.
The equivalent Python API is `sol.essence.export_prose(snapshot)`; the standalone
`sol.essence.prose_text(markdown)` performs just the structural text projection.
Importing either API starts no reader, workspace, or model.

## What the export includes

The version-1 `sol.prose-input` view selects Hegel-attributed `main_text` records
of types `paragraph`, `quotation`, and `list_item`. It excludes explicit generated
text and transcriptions flagged `needs_review` or `needs_visual_review`.
Section headings, title displays, contents entries, editorial text, notes,
formulas, indexes, and retired records are outside this default prose selection.
An exclusion summary accounts for every input record once.

Unlike the existing three-doctrine term experiment, this export includes all
eligible Hegel main prose, including prefatory material. It does not require a
reader path or guess a doctrine label from one. Its name describes a text
selection, not a claim that the entire edition has been transcribed or reviewed.

The text projection uses the existing CommonMark parser and visible-text
renderer with explicit exclusions:

- Markdown headings, including ATX, setext, and headings nested in quotations or
  lists, contribute no text. HTML `h1`–`h6` headings are also omitted.
- Markdown and HTML image labels contribute no text. This includes converter
  facsimile captions.
- Emphasis and visible link text remain prose. Existing SOL note callouts remain
  omitted; ordinary superscripts and authored literal blocks remain visible.
- No word blacklist, stemming, casefolding, or stop-word removal is applied.
  “Being” in a sentence remains available even if “Being” is also a heading.

This follows recorded structure. A heading mistakenly transcribed as an ordinary
prose sentence needs a canonical record correction; capitalization or familiar
category words are not reliable substitutes for that distinction.

Each row keeps its existing UUID, the derived text and its SHA-256, plus separate
`metadata`: exact canonical Markdown digest, type, parent, order, document,
attribution, source pages, available heading/title/path fields, and root-first
ancestry reconstructed from canonical parent IDs. The export does not concatenate
any of that metadata into `text`. Embedded headings remain recoverable from the
canonical record even when they are excluded from the derived text.

The corpus/edition/source identity, manifest/index generation, and projection
version accompany the export. It checks the generation before and after preparing
the view and refuses a caller-modified snapshot. It does not rewrite or reindex
the corpus, open its PDF, or save a workspace. Output uses ordinary shell
redirection; files named `*.sol-analysis.json` are already excluded from Git and
release archives. `sol analyze check` continues to verify term-study artifacts;
it is not an importer or verifier for this prose export. Re-export after corpus
corrections.

## Preserve Hegel's categorization as a separate research dimension

Keep canonical ancestry for navigation, grouping, and explicitly chosen
supervised labels. A future classifier should receive prose as `X` and a
deliberately derived category as `y`; neither category names nor their paths
should be prefixed to `X`. Passage grouping and held-out splits also need an
explicit experimental policy. The export supplies context without choosing that
policy or silently treating every passage as a labeled example.

A separate, explicit heading study can examine the category tree or vectorize
its titles. Such vectors answer a different question from vectors of Hegel's
exposition. Keeping these inputs separate lets ESSENCE compare textual
relationships with the published organization while preserving both.
