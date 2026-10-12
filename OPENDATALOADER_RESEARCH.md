# OpenDataLoader as a second opinion for SOL

Research checked on 2026-10-12. This evaluates documented capabilities, not a
runtime trial: no packages, Java archives or models were installed; no book pages
were converted, uploaded or changed.

## Recommendation

Keep SOL's canonical Markdown, UUIDs and generated index. OpenDataLoader is worth
a controlled local comparison when an unresolved passage needs another extraction
or source rectangle. It should produce review candidates beside the existing
corpus, not replace the converter automatically or become a dependency of ordinary
reading. A future review desk could show the facsimile, canonical passage and
alternative extraction together without treating either extraction as ground truth.

## What runs locally

The Python interface requires Python 3.10+ and Java 11+ on `PATH`.
`opendataloader_pdf.convert()` launches a JVM per invocation. It supports Markdown,
JSON, text, HTML, annotated PDF and tagged PDF outputs. Java and Node.js APIs are
also documented; Node.js requires version 20+. This is not a Python-only library.
[Python quick start](https://opendataloader.org/docs/quick-start-python),
[Java quick start](https://opendataloader.org/docs/quick-start-java),
[Node.js quick start](https://opendataloader.org/docs/quick-start-nodejs).

With `hybrid=off`, the documented path is local Java extraction, without an AI
server. Born-digital pages with reliable embedded text should be assessed this way
first. Scanned pages need the separate hybrid OCR backend. The documented local
Docling backend uses roughly 2–4 GB RAM and 1–2 GB cached models; CPU execution is
supported, with optional GPU acceleration. Dependencies and models must be obtained
before an offline run. [Hybrid documentation](https://opendataloader.org/docs/hybrid-mode).

Formula enrichment is a separate feature: the server enables `--enrich-formula`
and the client uses `--hybrid-mode full`. It emits candidate LaTeX, not verified
mathematical transcription. [Repository capability and formula examples](https://github.com/opendataloader-project/opendataloader-pdf).

## Privacy, maintenance and cost

“Local first” is configuration dependent. Hybrid URLs can point to remote servers.
The server's documented default bind address is `0.0.0.0`; a private local trial
should explicitly bind loopback and select its local URL. Do not send this edition
to the website's demo or a hosted backend. [Hybrid server options](https://opendataloader.org/docs/hybrid-mode).

There is documentation drift: the hybrid overview labels cloud providers planned,
while the current option reference already lists `hancom-ai`. Java fallback on
backend failure is opt-in. Pin the exact release and inspect its actual backend
configuration before relying on privacy promises.
[Current CLI reference](https://opendataloader.org/docs/reference/cli-options).

The latest release checked was v2.5.12, with recent OCR, image and table fixes:
evidence of ongoing maintenance, not a guarantee for this book.
[Release v2.5.12](https://github.com/opendataloader-project/opendataloader-pdf/releases/tag/v2.5.12).
Version 2.0 onward uses Apache-2.0; optional commercial add-ons and model/engine
licenses need separate consideration. Core extraction has no advertised service
fee, but local computation/storage still cost resources. Remote-provider prices
and terms were not evaluated. [License documentation](https://opendataloader.org/docs/license).

## Fit with SOL's corpus contract

JSON provides hierarchical elements, one-based PDF page numbers, typography and
bounding boxes. Its optional integer element IDs are not documented as permanent
across conversions. PDF `author` metadata does not identify a paragraph's author.
The reviewed schema does not establish SOL's translator-note attribution,
footnote callouts/backlinks or permanent paragraph UUIDs. Font names alone do not
guarantee retained CommonMark italic spans. These require explicit sample tests,
not assumptions. [JSON reference](https://opendataloader.org/docs/reference/json-schema)
and [published schema](https://raw.githubusercontent.com/opendataloader-project/opendataloader-pdf/main/schema.json).

The homepage describes rectangles as `[left, bottom, right, top]` in PDF points.
Calibrate coordinate origin, rotation and crop boxes before adapting them to SOL;
preserve the manifest's printed-page inventory rather than assuming a universal
page offset. [Coordinate example](https://opendataloader.org/).

XY-Cut++ infers reading order; tagged structure can override it, depending on tag
quality. Neither detected headings nor model descriptions establish Hegel's
logical hierarchy. Generated descriptions must remain labelled as generated, never
Hegel's prose. [Reading-order documentation](https://opendataloader.org/docs/reading-order).

SOL's [corpus contract](CORPUS.md) remains authoritative. An alternative extractor
must not allocate replacement IDs, change `corpus_id`, silently reconcile passages,
or transfer workspace reviews. Current workspace reviews bind text and declared
PDF fingerprints, not complete page/attribution/rectangle metadata; a new rectangle
is not automatically covered by an existing “verified” event.
[Workspace boundaries](WORKSPACE_PLAN.md).

## Claims that still need testing

The vendor benchmark reports overall scores of 0.907 for hybrid and 0.831 for
local mode across reading order, tables and headings. These are aggregate metrics,
not a demonstrated percentage of correctly transcribed Hegel paragraphs, italics,
notes or formulas. [Benchmark overview](https://opendataloader.org/docs/benchmark).
Free auto-tagging and enterprise PDF/UA export are distinct offerings; tagging
claims do not prove textual accuracy or SOL's accessibility.
[Accessibility offering](https://opendataloader.org/accessibility).

## A bounded experiment, if justified

1. Use a fresh private output directory outside `sources/` and the canonical
   corpus. Explicitly set it: OpenDataLoader otherwise writes beside the input PDF.
   Record source SHA-256, pinned version, Java version, options and any model/backend
   versions. [Output and extraction options](https://opendataloader.org/docs/reference/cli-options).
2. Begin with local mode, JSON plus Markdown, one worker and a small page selection.
   Include known italics, a footnote, a paragraph crossing pages and mathematical
   trouble spots: printed 209–210/PDF 282–283, 224–225/PDF 297–298, 252/PDF 325 and
   374/PDF 447. These are review samples, not benchmark ground truth.
3. Compare against facsimiles for completeness, reading order, hyphenation,
   superscripts, fractions, note separation and rectangles. Audit tiny/hidden-text
   filters and invalid-character replacement, which can obscure meaningful symbols;
   do not silently sanitize the text or disable every filter.
4. Save explicit candidate-element-to-existing-UUID mappings with evidence and
   unresolved cases. Treat mismatches as review questions, never automatic edits.
5. Only human-approved corrections enter canonical Markdown, preserving IDs and
   followed by reindexing. Consider a separately authorized, loopback-only formula
   trial only if local extraction cannot answer the specific problem.

No experiment or integration was performed by this research.
