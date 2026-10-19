# SOL — Architecture and Development Charter

**Status:** authoritative human-facing documentation, adopted 17 October 2026.  
**Repository baseline:** [`dialectmaterial/SOL`](https://github.com/dialectmaterial/SOL), `main` at `1d200e4fcbff1ca69f48b5dc96c55765f215f303`.  
**Companion documents:** [BEING](BEING.md) · [ESSENCE](ESSENCE.md) · [CORE](CORE.md).

**Implementation reviewed through:** `577166b` (17 October 2026); ESSENCE interface and component decisions added 18 October 2026 against `main` at `524878d` (supporting research: [ESSENCE interface brief](coordination/proposals/ESSENCE_INTERFACE_BRIEF_2026-10-18.pdf)). The baseline above records the original documentation adoption, not the latest feature state.

> **Interpretation rule.** A statement marked **Implemented** describes the inspected baseline. A statement marked **Decision** expresses the present design direction; it may require code changes. **Proposed** features are not available merely because they appear here. Code, tests, and the relevant schema control the precise behavior of an implemented function. The Git working tree may be ahead of this snapshot: inspect it before making changes.

**Adoption check:** at the original baseline, Neovim was the single default reader, continuous views were bounded, and the three theme presets were not yet shipped. The documentation migration corrected setup/dependency wording in CORE and a navigation detail in BEING; it implemented no reader features. Subsequent commits added Terminal/Dark/Paper, fingerprint-checked printed-source preview (`s`), passage-level note writing (`a`), footnote text and in-place footnote numbers, search-match marks, and the first BEING→ESSENCE→BEING inquiry (`S`, a sentence-length study). Sustained terminal/visual acceptance remains open. Historical documents and the original migration inventory remain unchanged in the [legacy archive](legacy/README.md).

## 1. What SOL is for

SOL (*SOL Organizes Logic*) is an experimental philosophical-scientific research environment centered **for now exclusively on Hegel's *Science of Logic***. Its immediate goal is not a new operating system, a universal PDF importer, or a better generic ebook reader. It is one continuous practice:

**Read → question → select/contextualize → investigate → inspect evidence → return to the text → revise an interpretation.**

Reading and computational analysis are distinct operations on a shared, identifiable textual object. Their unity consists in preserved source identity, research context, and a reversible path to the text—not in sharing a particular terminal window. The decisive acceptance exercise is concrete: read a substantial stretch of Hegel, encounter a linguistic or philosophical question, analyze exactly the relevant text, inspect the result, return to the passage, and continue reading without reconstructing context by hand.

### Criteria of success

1. **Actual reading:** SOL is pleasant enough to choose voluntarily for a sustained reading session. Visual comfort is judged by a human, not inferred from passing tests or a screenshot.
2. **Fidelity:** source text, editorial material, mathematical passages, hierarchy, and provenance remain distinguishable. Unknowns are visible; uncertainty is not silently repaired.
3. **Continuity:** moving into a computational experiment and back does not lose the passage, selected span, active question, or reader state.
4. **Reproducibility:** analyses disclose input projection, exact corpus generation, method, parameters, dependency/model versions, and results; the system never calls numeric or vector similarity dialectical necessity.
5. **Restraint:** integrate proven tools before creating bespoke interfaces or algorithms. Changes must demonstrably improve the research practice.

## 2. Component responsibilities

| Component | Function | Owns | Must not own |
|---|---|---|---|
| **CORE** | Textual identity and verifiable interchange | Corpus loader and contract, canonical records, hierarchy, source/edition attribution, UUID resolution, reference protocol | GUI/TUI, workspace authoring, ML runtimes, emulators |
| **BEING** | Reading and attributed scholarly work | Reader actions, navigation, search, selection, workspaces, annotations, comparisons, review testimony, presentation adapters | Canonical truth via UI state, model conclusions, terminal dependencies in CORE |
| **ESSENCE** | Reproducible investigation | Prose/method-specific projections, linguistic and statistical tools, model jobs, evaluation, result artifacts and links to source records | Canonical editing, independent passage identity, automatic reader-authored conclusions |
| **CONCEPT** | Future coherent research environment | **Nothing independently implemented or mandated yet** | Premature NixOS/distro construction |

CORE is **not** a fourth Hegelian stage; it is a shared engineering substrate. BEING/ESSENCE/CONCEPT names are a productive philosophical analogy, not a proof that modules derive themselves from Hegel's dialectic. Scholarly interpretation must remain contestable and attributable.

**Implemented:** single repository, `sol.core` public API version 1, canonical corpus contract, reader/action boundary, Neovim frontend, optional Kitty handoff, basic ESSENCE exports and lexical experiment. **Not implemented:** independent published `sol-core`/`sol-being` distributions, generic integrated investigation desk, model registry, NixOS system, fully graphical typeset reader.

**Decision (maintainer, 18 October 2026): independent components without premature packaging.** BEING reads, ESSENCE investigates, CORE provides verified text; each should become usable without the others where that makes sense, but SOL stays **one installable package** until the seams are proven. The path:

1. **Now:** one repository; extract pure-text analysis functions whose tests need neither CORE nor a running interface; specify interface boundaries and optional providers.
2. **Next:** ESSENCE's CLI and interface open ordinary text files; CORE integration becomes an adapter that adds UUID-backed corpus operations.
3. **Later:** BEING opens ordinary Markdown without a prebuilt CORE corpus; audit dependencies before proposing separate distributions.
4. **Only after stable seams:** split into separately installable `sol-being`, `sol-essence` and `sol-core` packages, if the maintenance cost is justified.

Do not describe SOL as "independently installable" before step 4.

### Dependency direction

`sol.corpus` and `sol.core` provide verified snapshots and references; `sol.reader.actions` mediates reading; `sol.terminal` adapts to a host; `sol.workspace` persists attributed work; `sol.essence` uses CORE directly today (every study imports `sol.core`), and by the decision above CORE becomes an optional provider for it. CORE must be importable without starting a reader, shell, interactive prompt, workspace, model download, or network request. Views do not invent IDs. ESSENCE does not import BEING's command loop to obtain data. Reader adapters call the same actions rather than creating parallel navigation semantics.

## 3. One book, not every PDF

**Decision, 17 October:** narrow active development to the existing audited Cambridge/George di Giovanni *Science of Logic* corpus. Do not start an arbitrary-PDF importer, multi-book catalog, or translation alignment project. Maintain the existing edition/source metadata and make no compatibility-breaking shortcuts that would obstruct later versions, but design future ingestion only when the present reader-and-inquiry loop justifies it.

**Implemented:** after installation, first interactive `sol` launch can import the *exact audited source PDF*; it rejects unknown editions, scans, and recoded copies. The installer itself does not import the book. OpenDataLoader produces extraction/review candidates but does **not** make the application a general importer. Canonical Markdown is the text correction surface; JSONL is generated. Source PDFs, private corpora, crops, and analysis exports are not committed publicly. See [CORE](CORE.md).

## 4. User experience: one system, multiple surfaces

The default `sol` enters the **isolated Neovim reader** in an ordinary capable terminal (Alacritty is a first-class host). It has a continuous reading mode, search, structure tree, markers and workspace persistence. Earlier prompt_toolkit reader research remains useful evidence of visual qualities that were lost in the migration. Neovim is chosen provisionally for its native motion/keymap/API and maintainability—not because code editing is philosophically the correct way to read a book.

**Decision:** keep Neovim for the next bounded iteration; improve the reading composition, not just color. Implement three presets: **Terminal** (inherit terminal colors), **Dark** (curated TUI reading theme), and **Paper** (light, high-contrast book-like scheme). Preserve stable positions, current functionality, user Neovim isolation and terminal compatibility. Theme changes are presentation only. Do not make a theme fork or a second editor distribution. **Implemented (17 October):** the three presets, session cycling with `T`, and explicit saving with `sol --set-theme`; the composition audit remains open. See [BEING §4](BEING.md#4-theming-and-typography-next-bounded-task).

The terminal's cell grid cannot render every typographic feature faithfully. **Mathematical passages are a test case:** retain source evidence and show the best verified representation; allow a browser/source image preview where necessary. Do not force mathematical notation into compromised text drawings solely to keep everything inside Alacritty. A temporary auxiliary window is compatible with a unified research workflow.

**Decision:** `sol-kitty` remains an optional compatibility/integration host, not the main SOL interface and not an argument for making ESSENCE a terminal emulator. Preserve working Kitty features; the *semantic* BEING–ESSENCE contract must ultimately be terminal-independent. Terminal splits, browsers, TUI dashboards, CLI output, and TensorFlow Embedding Projector are interchangeable presentation mechanisms, not competing knowledge stores.

**Decision (maintainer, 18 October 2026): hybrid surfaces for reading and investigation.** Neovim stays the persistent BEING reader. ESSENCE gets a separate **Textual** application, started only when ESSENCE is requested, inside a Neovim terminal buffer, either beside the reader or fullscreen; leaving ESSENCE saves the investigation and ends that process. **Neovim owns the outer layout** (split or fullscreen); **Textual owns the layout inside its buffer.** This applies the Kitty decision above: the BEING–ESSENCE contract stays semantic, and the Textual application is a presentation of it, not a terminal emulator. Details, lifecycle and open questions: [ESSENCE §4](ESSENCE.md#4-interaction-model-and-inquiry-contract); reader-side requirements: [BEING §6](BEING.md#6-being--essence-without-terminal-dogma). Nested-terminal keys, alt-key capture, resizing and launch latency must be proven on real terminals before this is called implemented. The reverse arrangement, Textual hosting both modules with Neovim embedded, is recorded as an **open alternative** with a proposed test in [ESSENCE §4](ESSENCE.md#4-interaction-model-and-inquiry-contract).

The former artificial book shell is an optional compatibility experiment (`sol --shell`), not the core mental model. The **dynamic structure tree** within the reader is the useful surviving spatial/navigation idea. Keep it subordinate to uninterrupted reading.

## 5. Scholarly discipline

A paragraph UUID represents a source record; a PDF page is evidence/provenance, not the ontology of a logical determination. Hierarchy records the edition's organization, not an incontestable metaphysical structure. Reader-authored comparisons, comments and relations belong to the workspace; model-derived suggestions are separate evidence and never automatically become claims like *presupposes*, *sublates*, or *necessary transition*. Distinguish quotation, editorial note, translator decision, computation, human interpretation, and proposed philosophical relation.

**Computation** can transform symbol sequences, parse sentences, calculate lexical statistics, or embed passages. A statistical relationship can inform philosophical inquiry; it cannot certify dialectical necessity. Every result must remain inspectable against source and method.

## 6. Immediate development order and acceptance gates

Workstreams can overlap, but must stay bounded:

**A. Reader quality.** Compare historical prompt_toolkit presentation with current Neovim, identify visual regressions, improve actual spacing/flow/semantics, evaluate the shipped Terminal/Dark/Paper presets, and conduct sustained reading trials. A screenshot or headless smoke test is necessary but insufficient. Avoid repetitive migrations. *Status, 17 October:* two regressions found in reading use are fixed — footnotes were invisible (the reader loaded only each note's heading; it now shows their text under `c` and each footnote's number where the book prints it), and search no longer marked matches (it again does, as the prompt_toolkit reader did). The composition audit and sustained trials remain open.

**B. Formula fidelity.** Use the recorded mixed-math inventory and verify the shipped on-demand printed-source preview in the normal terminal/viewer workflow. The scratch import reported no `formula` records and 46 flagged mixed paragraphs; see [BEING §5](BEING.md#5-mathematical-notation-and-source-fidelity). Preserve warnings and provenance. Previews are rendered from the fingerprint-checked PDF, not the converter's unverified image assets. Reviewed LaTeX/MathML rendering remains future work; the reader must never flatten an unverified formula into apparently certain prose. *Status, 17 October:* the reader used `s` in a real terminal and found the separate viewer helpful but awkward as the main way to read mathematics. At the reader's request, the 30 scrambled mathematical records were retyped from the PDF crops as linear Unicode in canonical Markdown, with an audit of every change; they keep `needs_visual_review` until a person confirms each against `s`.

**C. First complete inquiry.** From a chapter or passage context in BEING, launch a **sentence-length / syntactic distribution** experiment in ESSENCE; produce a versioned and source-bound artifact; inspect findings; return to a referenced sentence/passage without losing the reader's prior location. Do this before adding a model zoo. *Status, 17 October:* the sentence-length half is implemented end to end — `sol analyze sentences` and `sol analyze check` (the reader's `S` key was removed on 19 October at the maintainer's request; the study is to move into ESSENCE); see [ESSENCE §5](ESSENCE.md#experiment-a--syntax-and-positionality-highest-priority). Syntactic (POS/dependency) annotation and a human-checked segmentation sample remain open.

**D. ESSENCE interface, then breadth (revised 18 October).** Build the investigation interface in the stages of [ESSENCE §5](ESSENCE.md#5-prioritized-experiments): interface shell, a minimal word-frequency experiment, target/reference comparison, an encyclopedia skeleton, then model adapters. **Embeddings move to the model-adapter stage**: when reached, use the existing prose-only export, select and benchmark an embedding model, record model/checkpoint/input settings, attach UUID metadata, and export vectors + metadata for TensorFlow Embedding Projector. Browser visualization is appropriate; apparent distances do not establish logical categories. *Why the change:* until the reversible interface and the smallest experiment work end to end, a second model would add breadth to a loop that is not yet proven.

**E. Later.** Richer annotation spans and research-context restoration, typeset-reader decision, persistent investigations, additional NLP methods, multilingual/edition handling, and only eventually reproducible Nix-based environment composition. Do not implement an operating-system distribution during this cycle.

Acceptance must include actual normal-terminal trials (Alacritty), failure cases, corpus freshness, resizes, Unicode, math preview, a complete research round trip, source return, and workspace integrity. Report automated pass/fail, integration behavior, manual visual assessment, and known limits **separately**.

### Reader measurements — 18 October 2026

[`scripts/reader_timings.py`](../scripts/reader_timings.py) is an opt-in developer
diagnostic, not an installed reader command or another frontend. It defaults to
invented text; a private corpus must be selected explicitly:

```sh
.venv/bin/python -B scripts/reader_timings.py --repeats 5 --warmups 1
.venv/bin/python -B scripts/reader_timings.py --corpus /absolute/path/to/local-corpus --json
```

It reports `time.perf_counter` medians, min–max, quartiles and raw samples for
load/verification, ordinary and note-heavy payloads, standalone typography,
Python startup to first payload, and controller next/previous, search/open
and history (the section study left with `S` on 19 October). The controller is real; only its Neovim boundary is
replaced. Workspaces, study artifacts and XDG state are temporary. Generation
checks and persistence guards remain enabled; no cache or optimisation is added.
These warm-process measurements exclude imports, Neovim launch, IPC, drawing and
human key-to-screen latency. Stages overlap and differently sized sections are
not a controlled estimate of footnote overhead. Keep real-book reports outside
Git; [handoffs](coordination/HANDOFF.md) may quote measurements and candidates
for later profiling, never adopt optimisations from timing differences alone.

## 7. Agentic development policy

- Start by reading `git status`, `git diff`, recent commits, these four current documents, and the relevant code/tests. Never assume a prior handoff is the current state. Do not discard uncommitted work.
- Treat these four documents as the **human-facing authoritative design description** once adopted. If implementation disagrees, report the discrepancy; do not pretend the planned feature exists. Update the docs alongside verified changes.
- Preserve `docs/legacy/` verbatim as historical evidence; prior reports, hypotheses and failed prototypes are not currently binding merely because they were once written.
- Run focused tests then the available full suite. Do not equate passing tests with good reading, transcription accuracy, historical attribution, or philosophical correctness.
- Commit/push only related verified changes where the project's contribution workflow authorizes it. Never commit copyrighted book material, private workspaces, extracted PDF contents or user data.
- Prefer incremental changes preserving passage IDs, source digests, existing workspaces and public CORE contracts. Any explicit migration must be reversible or publish a new copy.

## 8. Documentation policy

**Only four documents govern the intended product:** this Architecture charter, [BEING](BEING.md), [ESSENCE](ESSENCE.md), [CORE](CORE.md). Research briefs and proposals kept under `docs/coordination/proposals/` (for example the [ESSENCE interface brief](coordination/proposals/ESSENCE_INTERFACE_BRIEF_2026-10-18.pdf)) are supporting evidence: their decisions apply only as recorded in these four documents. Retain a short repository root `README.md` as a navigation/setup gateway if GitHub packaging requires it; it is **not** a fifth architectural source. Keep chronological history, experiment notes and old documents in `docs/legacy/`, still searchable but clearly non-authoritative. A code-level invariant belongs in tests and code as well as a concise statement in CORE. Never erase history to simplify navigation.

**Reconciliation record:** this charter synthesizes the current GitHub README, modularity contract, reader action and view documentation, reference/handoff contracts, corpus and extraction documentation, historical reader-engine experiments, and discussion decisions through 17 October. Model-history notes described as existing only locally were **not inspected** and must not be invented; add them after they are actually available and reviewed.
