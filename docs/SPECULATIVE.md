# SOL — Speculative Architecture and Development Methodology

**Date:** 21 October 2026  
**Document type:** Architectural decision record and methodological specification  
**Status:** Agreed direction; repository restructuring has **not** been performed by this document  
**Scope:** The philosophical and architectural decisions reached in the design conversation

## 1. Executive statement

SOL is conceived as **both a computational investigation into philosophy and a philosophical investigation into computation**. These are not two independent projects. Computational procedures provide new ways of investigating philosophical texts and categories; philosophical inquiry, in turn, interrogates the assumptions, methods, and limitations of those procedures. Each side may require revisions to the other.

Hegel's *Science of Logic* is therefore more than an inspiration for SOL's terminology. Its **speculative** movement—not contradiction taken in isolation—defines the architectural ambition. Its logical determinations are to serve as an **analogical, determinative, and revisable principle of software organization**. The architecture is not assumed to be correct from the outset. It is to be developed through sustained engagement with the primary text, concrete implementation, and critical reconsideration.

The immediate practical decision is to restructure substantive SOL modules under the logical divisions **BEING**, **ESSENCE**, and—when active development requires it—**CONCEPT**. **CORE** remains a separate service layer for corpus management and shared infrastructure. Ordinary development infrastructure may remain outside the logical hierarchy for now.

## 2. The philosophical problem

### 2.1 The reciprocal investigation

SOL pursues two linked directions:

- **Computation investigating philosophy:** reading, corpus analysis, tokenization, comparison, statistical methods, and eventually machine learning can disclose patterns and relations in philosophical material.
- **Philosophy investigating computation:** concepts such as determination, quality, quantity, identity, difference, mediation, and objectivity can be used to interrogate computational operations themselves.

A simple word tokenizer illustrates this reciprocity. Computationally, it segments a text into discrete units. Philosophically, that operation invites questions about what makes something a unit, where its boundaries come from, which distinctions the procedure presupposes, and what is lost by abstraction. Such questions may alter the tokenizer or its role in a broader analysis. Its revised implementation can then yield further philosophical questions.

Neither philosophy nor computation is treated as immune to criticism.

### 2.2 Analogy and determination are compatible

The conversation rejected a false opposition between *analogy* and *determination*. The analogy to evolutionary computation is instructive: biological categories can inspire computational operations while also supplying principles for constructing algorithms. Likewise, the *Science of Logic* can furnish SOL's conceptual vocabulary **and** help determine how its modules are organized and how they interact.

This analogy is not automatically successful merely because a module has a Hegelian name. Its adequacy must be tested in the work. SOL's implementation of Hegelian categories is less settled than the established computational uses of evolutionary concepts; that is a difference in maturity, not necessarily in methodological kind.

The practical test of **computational productivity** is necessary but insufficient. A philosophically revealing structure might also expose limitations of the computational approach itself.

### 2.3 Adequacy to the Concept—and the Idea

A deeper question guides the project: **can computation become adequate not merely to an externally supplied concept, but to the Idea in Hegel's sense?** The Idea should not be reduced to a concept that is simply self-consistent. In Hegel's *Science of Logic*, the Idea concerns the unity of Concept and objectivity, with objectivity adequate to the Concept.

Accordingly, SOL cannot assume that arranging code in a logical tree—or even enabling self-modifying algorithms—constitutes speculative thought. The adequacy of computation to speculative logic remains an **open object of investigation**, not a claim established in advance.

This is the project's strongest methodological formulation:

> **SOL investigates philosophy computationally and investigates computation philosophically. The two inquiries reciprocally condition and revise one another, while the question of computation's adequacy to the Idea remains open.**

### 2.4 Why the architecture is speculative, not merely dialectical

**Speculative** is the governing term for SOL's architectural method. The distinction is methodological rather than cosmetic. Hegel differentiates the moment of the **understanding**, which fixes determinations as if they could stand on their own; the **dialectical** or negatively rational moment, in which finite determinations reveal their own instability, self-sublation, and transition into their opposites; and the **speculative** or positively rational moment, which grasps the affirmative unity arising through that negative movement. Speculative thought does not simply detect contradictions, reject the original determinations, or mechanically resolve conflict into consistency. It comprehends how the opposed determinations are preserved and transformed in a concrete result.

Hegel makes this explicit in the *Science of Logic*, Introduction, §69, identifying speculative thought with **the unity of opposites and the positive in the negative**. The corresponding distinction is articulated in the *Encyclopaedia Logic*, §§79–82, especially §82 on the speculative or positively rational moment. These references are supplementary aids for this document; **the edition held in SOL CORE remains the agents' primary working text**.

The architectural consequence is substantive. When an arrangement proves inadequate, an agent must not stop at identifying the contradiction or treat the old module as a disposable mistake. The agent should investigate **what determinate content of the prior design survives**, what relation the conflict discloses, and what new arrangement can positively integrate those moments without concealing their tension. This result is a provisional proposal, not proof that computation has realized speculative reason. Whether software construction can achieve an adequate expression of speculative logic remains a question internal to SOL's philosophical and computational inquiry.

**Textual pointers:** [*Science of Logic*, Introduction §69](https://openstax.marxists.info/reference/archive/hegel/works/hl/hlintro.htm); [*Encyclopaedia Logic*, §§79–82](https://openstax.marxists.info/reference/archive/hegel/works/sl/sl_divis.htm). Agents must confirm wording and location against the primary CORE edition before citing its passages in code-placement decisions.

## 3. The Science of Logic as architectural principle

### 3.1 From external resemblance to productive correspondence

The aim is not to decorate a conventional codebase with philosophical labels. A category should do explanatory and organizing work: it should help clarify what a module does, how it relates to adjacent modules, and why a given architectural arrangement is preferable to alternatives.

The book is the **primary conceptual authority for interpreting the logical determinations**, not because a cited passage automatically settles an engineering decision, but because categorization must begin from the determinations and their relations in the text rather than from arbitrary naming preferences. The agents' interpretations remain contestable.

### 3.2 An asymptotic, revisable method

The mapping from computational function to logical category is **provisional and asymptotic**: one interpretation may presently be the best available fit, and later work may show a better one. Revisions are part of the method rather than evidence that the entire project has failed.

In particular:

1. Begin with the shallow divisions already available in the *Science of Logic*.
2. Assign existing modules based on defensible readings of relevant categories.
3. Preserve cohesive groups of related definitions; **one file per function is not a requirement**.
4. Add deeper subdivisions **only when the growth or internal differentiation of the code calls for them**.
5. Document interpretive decisions so they can be revisited when conceptual or technical tensions emerge.

This is not a command to enforce threes everywhere. In Hegel, the necessity of transitions between determinations matters more than a mechanically repeated triadic template.

## 4. Initial repository hierarchy

The following is the **target conceptual layout**, not a claim that the current repository already implements it. Exact package paths are to be adapted to the existing Python packaging conventions.

```text
SOL/
├── sol/                           # Python package (illustrative)
│   ├── being/
│   │   ├── quality/
│   │   ├── quantity/
│   │   └── measure/
│   ├── essence/
│   │   ├── essence_as_reflection_within_itself/
│   │   ├── appearance/
│   │   └── actuality/
│   ├── concept/                   # Reserved; no deeper implementation yet
│   └── core/                      # Corpus management and shared services
├── tests/                         # Conventional development infrastructure
├── docs/
├── pyproject.toml
└── .github/                        # CI and repository workflows, if used
```

**BEING — immediate first-level divisions:**

- **Quality**
- **Quantity**
- **Measure**

**ESSENCE — immediate first-level divisions:**

- **Essence as Reflection within Itself**
- **Appearance**
- **Actuality**

**CONCEPT:** Retain as a top-level division but **do not prematurely develop its internal tree**. When CONCEPT becomes active, its next divisions are to be read from the *Science of Logic*, not improvised for the sake of symmetry.

**CORE:** Maintain a separate layer for shared corpus and state services. Its exception from the logical package hierarchy is an agreed **practical boundary**, not a philosophical declaration that CORE can never be rethought.

### 4.1 What belongs where?

The working functional boundaries from earlier SOL discussions remain relevant:

| Area | Current responsibility | Architectural qualification |
| --- | --- | --- |
| **BEING** | Reading environment and immediate encounter with texts, including the Neovim reader. | Internal placement under Quality, Quantity, or Measure must be argued from the text; do not assign functions by superficial associations. |
| **ESSENCE** | Computation, analytic methods, comparison, and the Textual analysis interface. | Analytical work is ESSENCE's responsibility; the underlying corpus is requested from CORE. |
| **CONCEPT** | Future integration of SOL's research activities and environment, potentially including the Omarchy-to-NixOS trajectory. | Its precise functional scope and substructure remain open; no new development is required in this phase. |
| **CORE** | Corpus organization, retrieval, metadata, addressability, and shared persistent research state. | CORE serves other components; it should not silently absorb the computational responsibilities assigned to ESSENCE. |

A reader selection, a chapter, an entire book, an author's body of work, or several composed corpora may become an analysis target or reference corpus. ESSENCE specifies the intended analysis and scope; CORE resolves and provides the underlying material. This preserves the distinction between **data organization** and **computational investigation**.

### 4.2 Technical implications already established

- The **Neovim reader** remains primary for reading. A Textual-based ESSENCE interface may be opened on demand, not left running as an idle parallel process.
- ESSENCE should eventually support **full-screen** and **side-by-side** presentation with the reader.
- A **word tokenizer** is a suitable minimal computational starting point; its philosophical placement must still be investigated.
- Corpus scopes should be **hierarchical and composable**, allowing comparison beyond a selected passage: sections, books, collections, authors, and multiple bibliographies.
- Shared research state must survive transitions between BEING and ESSENCE without requiring either user interface to own the corpus.

These are existing functional intentions, **not** evidence that specific Hegelian subfolder assignments have already been justified.

## 5. Reading obligations for Claude Code and Codex

The purpose of the restructuring is partly **pedagogical and methodological for coding agents**: they must engage the *Science of Logic* in order to build SOL. The text is not merely a repository of quotations used after decisions have already been made.

### 5.1 Source hierarchy

1. **Primary working edition:** the *Science of Logic* already held in **SOL CORE**.
2. **Permitted interpretive aids:** the German original and alternative translations, especially where terminology or conceptual transitions are difficult.
3. **Secondary commentary:** potentially useful, but not a substitute for reading the logical passages themselves.

For substantive placements, agents should identify the edition and logical location used and distinguish a passage's content from their own interpretation. **No fabricated quotations, page numbers, or textual evidence.**

### 5.2 Required reasoning protocol

Before creating a new logical directory, moving a significant module, or reorganizing a cohesive cluster of functions, an agent should:

1. **Read:** Retrieve the pertinent part of the primary *Science of Logic* corpus and, where helpful, nearby transitions and alternative-language witnesses.
2. **Interpret:** Explain the relevant determination in relation to neighboring determinations; avoid keyword matching between code and chapter titles.
3. **Inspect:** Establish what the existing code actually does, what it depends on, and what its tests protect.
4. **Propose:** State the provisional architectural placement and why it is preferable to plausible alternatives.
5. **Implement:** Perform the structural change without gratuitously rewriting working logic; adjust imports and interfaces as required.
6. **Verify:** Run appropriate tests, static checks, and entry-point checks; identify regressions rather than concealing them.
7. **Record and reconsider:** Preserve a concise reasoning trail and revise the classification if subsequent conceptual or technical evidence warrants it. In cases of conflict, record both the determinate limitation of the prior arrangement and the positive content retained in its proposed successor.

This protocol applies to **meaningful module-level decisions**, not a new philosophical essay for every helper function.

### 5.3 Autonomy and final authority

**Decision:** Claude Code and Codex **may make provisional structural decisions and implement them without requesting approval for every move**. They must make their reasoning traceable and keep changes reviewable. The project owner retains the final say and may override or revise any decision.

Practical implementation safeguards are recommendations, not additional philosophical authorities: work in a dedicated Git branch, keep changes in coherent commits, preserve public behavior where possible, and run the test suite before merging.

A compact placement record can use this schema:

| Field | Required content |
| --- | --- |
| Module or function group | Name, previous location, relevant responsibilities |
| Proposed location | New Hegelian directory path |
| Textual grounding | Edition plus section or stable corpus reference |
| Interpretive rationale | How the determination bears on this code; alternatives considered |
| Technical consequences | Imports, dependencies, interface changes, tests |
| Status | Provisional, reviewed, revised, or superseded |

This record is an instrument of revision, **not proof that a philosophical interpretation is correct**.

## 6. Limits of the logical hierarchy

The agreed initial position is to keep **ordinary engineering infrastructure outside** the Hegelian hierarchy:

- tests and test fixtures;
- project configuration and dependency declarations;
- CI workflows and build or packaging machinery;
- general documentation and development tooling.

For instance, the tokenizer's implementation might be placed under a BEING determination once justified; its unit tests may continue to live in `tests/`. A `pyproject.toml` file does not become philosophically significant merely because it is placed in `quality/`.

**This is a provisional organizational exemption, not immunity from philosophical scrutiny.** SOL can later investigate whether testing, dependency management, platform constraints, or reproducibility have conceptual significance. Until a convincing reason for moving them emerges, conventional locations reduce friction and preserve the integrity of the engineering workflow.

## 7. Implementation sequence

The initial migration should be **incremental and behavior-preserving**:

**Stage A — Baseline and inventory.** Establish a clean repository snapshot. Inventory packages, imports, entry points, existing tests, and the current CORE/BEING/ESSENCE boundaries. Avoid pretending the existing code is conceptually homogeneous.

**Stage B — Shallow structure.** Establish the agreed BEING and ESSENCE threefold divisions. Retain CONCEPT as reserved. Keep CORE and ordinary infrastructure separate.

**Stage C — Interpretive mapping.** Have agents read relevant logical sections before proposing placements. Group closely related definitions into coherent modules. Record textual references, rationale, alternatives, and any unresolved classifications.

**Stage D — Gradual relocation.** Move modules in small, testable groups; update imports and entry points; protect reader, corpus access, and analytic workflows. Do not substitute wholesale rewrites for a directory reorganization.

**Stage E — Re-evaluation.** Review ambiguities and mismatches revealed by the new arrangement. Only introduce further logical subdivisions where the work produces a concrete need and a defensible interpretation.

**Stage F — Continued reciprocal research.** Use the results of computational work to interrogate philosophical assumptions and philosophical analysis to question computational techniques. Develop CONCEPT only when it becomes a concrete research and architectural requirement.

## 8. Decision register

| Topic | Decision | Status |
| --- | --- | --- |
| Overall aim | Computational investigation of philosophy **and** philosophical investigation of computation | Agreed |
| Organizing authority | *Science of Logic* guides a **speculative** architecture through productive analogy, determinate negation, positive integration, and revisable determination | Agreed |
| Philosophical adequacy | Whether computation is adequate to the Concept and the Idea is a question, **not a presupposed result** | Open research problem |
| Initial BEING divisions | Quality / Quantity / Measure | Agreed |
| Initial ESSENCE divisions | Essence as Reflection within Itself / Appearance / Actuality | Agreed |
| CONCEPT | Keep top-level division; defer deeper implementation | Agreed |
| CORE | Separate layer for corpus and shared services | Agreed for now |
| Source priority | Existing SOL CORE edition primary; German and other translations permitted | Agreed |
| Agent initiative | Provisional structural changes allowed with recorded justifications; owner retains final authority | Agreed |
| Ordinary infrastructure | Tests, configs, CI, packaging outside logical hierarchy for now | Agreed for now |
| Deeper directory branching | Introduce only as conceptually and technically warranted | Agreed |
| File granularity | Cohesive groups of related functions; no one-function-per-file rule | Agreed |
| Specific module assignments | To be determined from text and actual code inspection | Pending implementation |

## 9. Risks and criteria of success

**Risks:** superficial keyword-based classification; imposing triadic symmetry where no logical transition has been established; philosophical justifications written retrospectively to excuse arbitrary design; unnecessary code churn; turning CORE into an undifferentiated dumping ground; and treating a successful algorithm as proof of adequacy to the Idea.

**Near-term engineering criteria:** the existing SOL functionality still works; the package resolves correctly; tests and entry points run; the first-level logical structure is understandable; and major placement decisions carry traceable textual and technical reasons.

**Longer-term philosophical criteria:** the architecture makes the affirmative content of contradictions intelligible, rather than merely cataloguing design conflicts; the logical distinctions genuinely illuminate design choices; conceptual difficulties can cause architectural revision; computational results create questions for philosophical interpretation; and the project can articulate limitations of its methods rather than assuming philosophical success.

## 10. Working thesis

> **SOL's speculative architecture should develop through the reciprocal determination of philosophy and computation. Hegel's *Science of Logic* supplies a productive, revisable conceptual organization for substantive software modules. Coding agents must read and interpret the primary text as part of development, make traceable provisional decisions, and revise those decisions when new conceptual or technical necessities emerge, seeking the positive content disclosed through determinate contradiction rather than merely removing inconsistency. The ultimate adequacy of computation to the Idea remains an open question investigated through the project itself.**

---

**Provenance and interpretation:** This document synthesizes the SOL architectural conversation of 21 October 2026. It distinguishes decisions actually made from proposed implementation practices and open philosophical problems. It does not attest that repository files have been changed or that any particular module has been assigned to a logical category after primary-text analysis.
