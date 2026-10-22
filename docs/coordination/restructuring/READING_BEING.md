# Restructuring stage C — reading the Doctrine of Being

**Prepared:** 22 October 2026, by Claude Code, against `main` at `0f5156a`.
**Edition:** Hegel, *The Science of Logic*, trans. George di Giovanni (Cambridge, 2010): SOL's CORE edition, read in the local verified corpus through `sol read`. Page numbers are the edition's printed pages as the corpus records them for the **start of each section**; a claim about a passage inside a longer section cites that section's start and names the section. No German text was consulted for this pass.
**Method:** [SPECULATIVE §5.2](../../SPECULATIVE.md#52-required-reasoning-protocol): read, interpret, inspect, propose. Nothing is moved. Paraphrase is mine; the few quoted phrases are short and attributed. The module facts come from `INVENTORY_BEING.md` (PR #87) and from the code itself.

**Read for this pass** (corpus paths in §7): the general division of being (p. 56); the introductions to Quality (p. 58), Existence (p. 83), Something (p. 88), *Determination, constitution and limit* (p. 95), Being-for-itself (p. 126), Quantity (p. 152), *Continuous and discrete magnitude* (p. 165), *Number* (p. 168), *Ratio* (p. 271), Measure (p. 282), *The rule* (p. 291), *Nodal lines of measure-relations* (p. 318), *Absolute indifference* (p. 326) and *Transition into essence* (p. 333). Not read in full: the long remarks on mathematics (pp. 155–280 passim), elective affinity (p. 308), the measureless (p. 323). Proposals that would depend on those sections are marked as such.

## 1. What the text says

### 1.1 The division (p. 56)

Being is determined in three ways. **First**, as determinateness as such: quality, a determinateness that is one with the being it determines, so that to change it is to change what the thing is. **Second**, as sublated determinateness: quantity, a determinateness that has become *indifferent* to being. Hegel's gloss is that quantity includes the alterability of being "without altering the fact itself" (p. 56). **Third**, as qualitatively determined quantity: measure, a relation of quality and quantity to each other. Hegel warns that this division is provisional. The determinations must come out of being's own movement, not be laid on it from outside (p. 56). For SOL this is the [SPECULATIVE §3.2](../../SPECULATIVE.md#32-an-asymptotic-revisable-method) warning against applying the three divisions mechanically.

### 1.2 Quality (pp. 58–151)

- **Movement.** Quality moves from indeterminate being, through existence (determinate being, the finite), to being-for-itself (p. 58).
- **Existence and something.** Existence is determinate being, and its determinateness is quality. Through its quality, something stands over against an other, and it is alterable and finite (p. 83). Something is existence that has become self-referring by taking its own distinctions into itself (p. 88).
- **Limit.** In *Determination, constitution and limit* (p. 95), something is what it is only *in its limit*. The limit is where something and its other each both are and are not. It is also the principle of what it delimits: Hegel's example is the point that begins the line. The limit is also a restlessness that drives something beyond itself.
- **Being-for-itself** completes quality: the one, the many ones, then repulsion and attraction (p. 126). Its result passes into quantity.

### 1.3 Quantity (pp. 152–281)

- **Indifference.** Quantity is determinateness indifferent to being: "a limit which is just as much no limit" (p. 152).
- **Continuity and discreteness.** It has two moments, continuity and discreteness. Each is also the whole of quantity: continuous magnitude is self-same connectedness, and discrete magnitude is the same quantity posited as ones (p. 165).
- **Number.** Quantum, quantity with a limit, is completed as number: a unit and an amount. Its limit relates to itself, encloses, and excludes other quanta (p. 168).
- **Ratio.** The infinity of quantum leads to ratio. Here a quantum has its determinateness only in relation to another quantum, so ratio is a first, formal unity of quality and quantity (p. 271).

### 1.4 Measure (pp. 282–336)

- **A quantum with qualitative meaning.** In measure, quality and quantity are united. Measure is first a quantum that has qualitative meaning, then a ratio of specific quanta. It then passes over into the measureless and from there into the indifference that turns into essence (p. 282 ff.).
- **Necessity.** Measure is already the idea of essence, implicitly, without being posited as such. In its developed form it is necessity (p. 282 ff.).
- **Two senses of measure.** *The rule* (p. 291) separates them:
  - an **external** measure: a standard unit applied to a quantum by "an external act" of comparison, with an arbitrary unit (the foot as so many inches);
  - a **specific** measure, which belongs to the thing and relates it to its own quantitative other.
- **Nodal lines.** A measure-relation can be indifferent to quantitative change up to a point where the change produces a qualitative leap (p. 318).
- **Transition into essence.** Absolute indifference is the last determination of being (p. 326). It fails to reach essence while difference remains "external reflection", an indifference applied by a thinking that stands outside the matter. It becomes essence when that reflection is the determination's own (p. 333).

## 2. A working interpretation for SOL

[SPECULATIVE §4.1](../../SPECULATIVE.md#41-what-belongs-where) gives BEING "the reading environment and immediate encounter with texts, including the Neovim reader". Read against §1, the three divisions suggest three questions to put to a piece of reader code:

1. **Quality.** Does it concern what the text *is* in its own determinateness? That covers its forms and boundaries: where a passage or section begins and ends, how it is marked, what distinguishes it from its neighbours. If changing the determination would change which text is meant, it is qualitative.
2. **Quantity.** Does it concern determinations that can change "without altering the fact itself" (p. 56)? Examples are position in a sequence, counts, offsets, width, layout geometry and scrolling. The book stays the same book while these vary; this indifference is the mark of quantity, not the mere presence of numbers.
3. **Measure.** Is a quantity *constitutive* of what something qualitatively is? That means sides that are themselves measures, whose quantitative relation determines a quality (pp. 302–303), or a threshold where quantitative change turns into a qualitative one (p. 318). A number that identifies or locates a thing is addressability, not measure, and applying an external yardstick is only the external rule (p. 291). On this pass no BEING-side module meets the criterion.

Two consequences follow, both in line with [SPECULATIVE §9](../../SPECULATIVE.md#9-risks-and-criteria-of-success)'s risks:

- **Not everything belongs in a subdivision.** The reading environment as a whole, the Neovim reader, *presents* all three determinations at once. Filing it under one of them would be the superficial classification SPECULATIVE warns against. I propose that such code sit at the BEING division root (`sol/being/`), with subdivisions holding only code whose work is one determination.
- **Quantity is the most secure placement here; Measure is the most tempting and the least secure.** Code that merely uses numbers is not quantity in Hegel's sense unless its point is indifference. Code that compares or locates is not measure unless a quantitative relation constitutes what something is. Most "measuring" code falls under the external rule of p. 291 or under CORE's addressability. `sol/being/measure/` stays empty for now; an empty division is preferable to a forced one.

## 3. Proposed placements

All rows are **proposed** (SPECULATIVE's "provisional"). Each names its alternatives and a confidence level. Implementation is stage D, one cohesive group at a time.

### 3.1 Reading state: `reader.actions`, `reader.navigation`, `reader.search`

- **`reader.navigation` → `sol/being/quantity/`** (confidence: medium).
  - *What the code does:* it computes character cells, source layout and vertical offsets, which are pure geometry.
  - *Why Quantity:* its outputs change with width and font while the passage stays the same passage. That is exactly the indifference of quantity to the "fact itself" (p. 56), and the outsideness of continuous magnitude (p. 165).
  - *Alternatives:*
    - stay beside `actions` at the BEING root. It is small and has one importer, so separating it buys little now.
    - treat it as terminal infrastructure outside the hierarchy. Rejected for now: it computes the reader's positions, not terminal I/O.
- **`reader.search` → `sol/being/quality/`** (confidence: low; **coordinate with READING_ESSENCE**).
  - *Why Quality:* literal search asks where *this determinate form* of words occurs. It holds to the text's immediate determinateness and does not interpret it. A match is a something marked off from its other by its form (pp. 88, 95).
  - *Against:* NFC and casefold normalisation deliberately make some differences indifferent, and counting occurrences is quantitative.
  - *Alternative:* ESSENCE. Matching is comparison, and identity and difference are determinations of reflection; [SPECULATIVE §4.1](../../SPECULATIVE.md#41-what-belongs-where) assigns comparison to ESSENCE.
  - *Proposed resolution:* keep literal search in BEING. It is the reader's way of finding a passage and stays inside the immediacy of the text, while ESSENCE's word methods investigate the text. This distinction should be confirmed against Codex's reading of the determinations of reflection.
- **`reader.actions` → `sol/being/` root** (confidence: medium).
  - *What the code does:* it is the reading session. It holds the cursor and sequence position (quantity), sections and their boundaries (quality), checkpoints through the workspace, and reference capture (CORE).
  - *Why the root:* it binds the determinations together rather than being one of them.
  - *Later split:* position arithmetic could go to Quantity and section-boundary logic to Quality, once the module's growth calls for it ([SPECULATIVE §3.2](../../SPECULATIVE.md#32-an-asymptotic-revisable-method), point 4).
  - *Alternative:* Quantity as a whole, since a cursor is a number in a sequence. Rejected: sections, the trail and checkpoints are not indifferent to what is read.

### 3.2 View preparation: `reader.structure`, `reader.typography`, `reader.surface`, the payload in `terminal.neovim`

- **`reader.structure` → `sol/being/quality/`** (confidence: medium-low).
  - *Why Quality:* the outline payload presents the book's articulation into divisions, each delimited by the others and existing only in its limit (p. 95, *limit*). The current section is the limit within which the reader now stands.
  - *Alternatives:*
    - stay with the Neovim reader as part of its payload (26 lines, one importer).
    - CORE, because the tree itself is CORE's canonical data. The payload builder only selects from it.
- **`reader.typography` → `sol/being/quality/`** (confidence: medium).
  - *Why Quality:* emphasis, strong, code and footnote callouts are determinations of the text's own form. Removing an emphasis changes what the edition says, unlike reflowing a line (contrast `navigation`).
  - *Alternatives:*
    - CORE, since it projects canonical Markdown and builds on `corpus.markdown`, and [CORE](../../CORE.md) (§2, with §5 on source-bound positions and typography) already defines the plain-text projection and callout offsets.
    - stay with the frontend.
  - *Why not CORE:* CORE defines the coordinates, while typography decides how the text's form is *presented in reading*.
- **`reader.surface` → `sol/being/` root, with the reader** (confidence: low).
  - *What the code does:* it makes a bounded, verified slice of passages for a view.
  - *Measure alternative, not adopted:* a sample is a quantum whose bound is tied to which passages it is, and it is refused if the underlying text changes. That looks like a quantum with qualitative meaning (p. 282 ff.). Adopting it now would be the "retrospective justification" SPECULATIVE §9 warns against. The bound (at most 64 paragraphs) is an engineering limit, not the text's own measure.
  - *Other alternative:* CORE for its reference-capture half.
- **`terminal.neovim` payload building:** stays with the Neovim reader (see 3.3).

### 3.3 The Neovim reader: `terminal.neovim_reader`, `neovim`, `reader_channel`, `runtime`, the Lua files, `theme`, `splash`, `window`

- **→ `sol/being/` root, as one package** (for example `sol/being/reader/`; confidence: medium-high).
  - *Why the root:* SPECULATIVE §4.1 names the Neovim reader as BEING's. It presents quality, quantity and measure together, so filing it under one subdivision would be classification by association.
  - *Inside the package:*
    - `runtime`, `window` and `splash` are close to infrastructure (installation, terminal window, opening screen) but serve only this reader, so they travel with it.
    - Of `theme`, only the palette data concerns other components; see 3.6.
  - *The splash:* its animation is the opening triad of Quality (being, nothing, becoming, pp. 59–82). That is a depiction, not a reason to file the splash under Quality.
  - *Alternative:* terminal infrastructure outside the hierarchy. Rejected because SPECULATIVE names the reader as BEING's.
  - *Consequence:* ESSENCE already runs as its own process (`python -m sol.essence.tui`, from `essence_panel` in `neovim_reader`). The remaining BEING → ESSENCE imports are the availability probe (`textual_available`, `TEXTUAL_HINT`) and `tui.context.write_context`, which writes the context file ESSENCE reads. Decoupling means moving the context file's format to a neutral module both sides import, and probing availability without importing ESSENCE's interface package. A changed launch command alone removes neither. The return path already uses no import.

### 3.4 Printed source: `terminal.source`

- **Snapshot verification, page capture and crops → CORE; the viewer → `sol/being/` root with the reader. Measure stays an unresolved hypothesis** (confidence: medium for the split; none for Measure).
  - *What the code does:* `SourceService.capture(identifier)` resolves an existing record and copies the source coordinates recorded for it (PDF page, printed page, bounding box); the viewer (Zathura highlight and follow) uses them to locate and mark that record on the printed page.
  - *Why not Measure, for now:* a number that identifies or locates a thing is not by itself measure. *The rule* (p. 291) separates external comparison from specific measure; *Real measure* (p. 302) and *The relation of independent measures* (p. 303) concern sides that are themselves measures, whose quantitative relation *constitutes* a qualitative determination. Here the record's identity is fixed by CORE before any coordinate is read. A wrong bounding box *mislocates the same record*; it does not make a different passage. That is addressability and provenance (SPECULATIVE §4.1, CORE), not a constitutive measure-relation. An earlier draft of this note argued the opposite and overstated it.
  - *The hypothesis kept open:* whether the relation between the typed text and its facsimile could ever be constitutive. For example, mathematics retyped from a crop is held to the crop until a person confirms it ([CORE §2](../../CORE.md#2-actual-artifact-and-identity-layers)). That needs the full reading of *Real measure* (pp. 302–325) before it is argued, not assumed.
  - *Alternatives:* all of it to CORE as provenance; all of it to the BEING root with the reader.

### 3.5 Plain-terminal output: `reader.render`, `reader.shell`, `terminal.text`, `terminal.commands`

- **`reader.render`, `reader.shell` → `sol/being/` root** (confidence: medium).
  - *Why the root:* they are a second, minimal surface of the same reading environment.
  - *Alternative:* outside the hierarchy as presentation infrastructure. Rejected: they read the book, as the Neovim reader does.
- **`terminal.text` → outside the logical hierarchy, as a shared terminal utility** (confidence: medium).
  - *Why outside:* escaping control characters and emphasis fallbacks are properties of terminals, not of reading. It is used by `workspace.reader`, and that dependency should go once the workspace is placed.
  - *Alternative:* the BEING root.
- **`terminal.commands` → path resolution to CORE; printing stays with the CLI** (confidence: medium).
  - *Why:* resolving a virtual or Markdown path to complete, ordered canonical text is retrieval and addressability (SPECULATIVE §4.1, CORE).
  - *Alternative:* keep the whole module with the CLI.

### 3.6 CLI composition: `reader.app`, `reader.options`, `reader.launch`, `reader.onboarding`, `terminal.reference`

- **`reader.app`, `reader.options`, `reader.launch` → outside the logical hierarchy, as the application's composition root** (confidence: medium).
  - *Why outside:* `app` wires BEING, ESSENCE and CORE together and dispatches `sol essence`. Leaving it inside BEING keeps a BEING → ESSENCE import that the divisions should not need. Entry points sit with packaging, which [SPECULATIVE §6](../../SPECULATIVE.md#6-limits-of-the-logical-hierarchy) keeps outside.
  - *Alternatives:*
    - the BEING root, since bare `sol` is `sol being`.
    - CONCEPT. The composition root is where the divisions are brought together, which is what SPECULATIVE §4.1 foresees for CONCEPT ("future integration of SOL's research activities"). This is recorded as a philosophical lead, not acted on: CONCEPT is reserved and undeveloped.
- **Themes in `reader.options` → a shared presentation module outside the hierarchy** (default; confidence: high on the engineering, none claimed philosophically).
  - *Why:* ESSENCE's interface imports the reader's option parser only to learn the theme names.
- **`reader.onboarding` → CORE** (confidence: medium).
  - *Why CORE:* first-run conversion creates the corpus.
  - *Alternative:* keep it with the CLI and call CORE.
- **`terminal.reference` → CORE's command-line face** (confidence: medium).
  - *Why CORE:* it is the reference protocol, which [CORE §6](../../CORE.md) defines.

### 3.7 Workspace: `sol.workspace`

- **→ `sol/being/` root, as one package** — **Decision (maintainer, 22 October 2026): the workspace stays in BEING.**
  - *The question:* SPECULATIVE §4.1 gives CORE "shared persistent research state"; [CORE §7](../../CORE.md#7-workspaces-provenance-and-deliberate-correction) states "Workspaces are **BEING**, not CORE", and item 7 of its §8 checklist keeps CORE independent of "user workspace state". This draft first proposed moving the store to CORE.
  - *Why BEING:*
    - what the workspace holds (notes on passages, named places, markers, reading position, each attributed to its author) is reading work: the immediate encounter with the text that SPECULATIVE §4.1 gives BEING;
    - it is not shared today: only the reader uses it, and ESSENCE keeps its own study state without importing it;
    - CORE stays the verified book and its addressing, avoiding the "dumping ground" SPECULATIVE §9 warns against;
    - SPECULATIVE §3.2 restructures when growth calls for it, not in anticipation.
  - *Root, not a subdivision:* the workspace records work on all three determinations; filing it under one would be classification by association.
  - *When to revisit:* once ESSENCE actually needs to read or write the same research state (notes shown in ESSENCE, analysis results attached to passages), SPECULATIVE's assignment of *shared* state to CORE applies and the store moves or splits then.
  - *Technical consequences:* `workspace.reader`'s import of `terminal.text` is replaced when both are placed (3.5); the schema is unchanged.

## 4. Answers to the inventory's stage C questions

1. **Workspace:** BEING, at the division root, by the maintainer's decision of 22 October 2026; it moves to CORE only once it is actually shared with ESSENCE (3.7).
2. **Reading state:**
   - `navigation` is Quantity;
   - `search` is provisionally Quality, pending Codex's reading of reflection;
   - `actions` stays at the BEING root as the session that binds them (3.1).
3. **Printed source:** the correspondence is a Measure candidate; snapshot verification is CORE's provenance (3.4).
4. **Typography and view preparation:**
   - typography and structure are Quality, as the text's own form and limits;
   - the sample stays at the root (3.2).
5. **Plain terminal, CLI and shell:**
   - the shell and rendering are BEING root;
   - the composition root and terminal escaping are outside the hierarchy;
   - path resolution and the reference CLI are CORE (3.5–3.6).
6. **Word tokenizer:** not answered here; it is ESSENCE's module and should be read with Codex. One observation from p. 165 and p. 168: a tokenizer that cuts a continuous text into equal, countable units performs *discrete magnitude*, and counting them gives number. That points to Quantity. Deciding *what counts as a unit*, the question [SPECULATIVE §2.1](../../SPECULATIVE.md#21-the-reciprocal-investigation) raises, is a question of limit and so of Quality. That tension is a reason to read the tokenizer against both sections before placing it.
7. **Themes:** yes, as shared presentation data outside the hierarchy (3.6).

## 5. Proposed register rows

These are added to [ARCHITECTURE §9](../../ARCHITECTURE.md#9-placement-register) in the same pull request, all with status **provisional (proposed)**.

## 6. Open points

- **Re-reading.** Read *Real measure* (pp. 302–325) and the mathematical remarks before implementing 3.4 or any placement under Measure. Today no module's placement under Measure rests on a full reading of that division.
- **Search and the tokenizer.** Confirm the search and tokenizer questions with READING_ESSENCE (identity and difference).
- **Order for stage D.** Proposed order: the Neovim reader package to the BEING root; `navigation` to Quantity; `typography` and `structure` to Quality; then the CORE-side moves; the workspace with the reader package. Nothing goes under Measure on this pass. Each move gets its own pull request, with tests and the register status updated.

## 7. Corpus paths

Each cited section, its section-start page, and its virtual path in the local corpus (`sol read PATH --plain`). Pages are section starts, not the page of each sentence inside a section.

| Section | Starts | Path |
|---|---:|---|
| General division of being | p. 56 | `/BEING/general-division-of-being.txt` |
| Quality: introduction | p. 58 | `/BEING/i-determinateness-quality/00-introduction.txt` |
| Being, nothing, becoming | p. 59 | `/BEING/i-determinateness-quality/1-being/` |
| Existence: introduction | p. 83 | `/BEING/i-determinateness-quality/2-existence/00-introduction.txt` |
| Something | p. 88 | `/BEING/i-determinateness-quality/2-existence/a-existence-as-such/c-something.txt` |
| Determination, constitution and limit | p. 95 | `/BEING/i-determinateness-quality/2-existence/b-finitude/b-determination-constitution-and-limit.txt` |
| Being-for-itself: introduction | p. 126 | `/BEING/i-determinateness-quality/3-being-for-itself/00-introduction.txt` |
| Quantity: introduction | p. 152 | `/BEING/ii-magnitude-quantity/00-introduction.txt` |
| Continuous and discrete magnitude | p. 165 | `/BEING/ii-magnitude-quantity/1-quantity/b-continuous-and-discrete-magnitude/00-introduction.txt` |
| Number | p. 168 | `/BEING/ii-magnitude-quantity/2-quantum/a-number/00-introduction.txt` |
| Ratio: introduction | p. 271 | `/BEING/ii-magnitude-quantity/3-ratio-or-the-quantitative-relation/00-introduction.txt` |
| Measure: introduction | p. 282 | `/BEING/iii-measure/00-introduction.txt` |
| The rule | p. 291 | `/BEING/iii-measure/1-specific-quantity/b-specifying-measure/a-the-rule.txt` |
| Real measure: introduction | p. 302 | `/BEING/iii-measure/2-real-measure/00-introduction.txt` |
| The relation of independent measures | p. 303 | `/BEING/iii-measure/2-real-measure/a-the-relation-of-independent-measures/00-introduction.txt` |
| Nodal lines of measure-relations | p. 318 | `/BEING/iii-measure/2-real-measure/b-nodal-lines-of-measure-relations/00-introduction.txt` |
| Absolute indifference | p. 326 | `/BEING/iii-measure/3-the-becoming-of-essence/a-absolute-indifference.txt` |
| Transition into essence | p. 333 | `/BEING/iii-measure/3-the-becoming-of-essence/c-transition-into-essence.txt` |
