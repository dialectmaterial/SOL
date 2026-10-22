# Stage E: re-evaluation after relocation

**Date:** 22 October 2026. **Reviewer:** Codex A, for the maintainer.
**Code baseline:** `origin/main` at `fd9b6b160f4a6294df05185d199e542f04d98fd5`.
This review includes stage D's BEING,
ESSENCE and CORE moves (#95, #97, #98), the composition root (#99) and launch
exchange (#100). Paths and line numbers below refer to that baseline.

This is a review under [SPECULATIVE §7, stage E](../../SPECULATIVE.md#7-implementation-sequence),
not another relocation. **No code moves or new logical subdivisions are
proposed now.** Most placements retain useful distinctions. Two engineering
seams merit later revision: CORE's edition-shaped reader projection, and the
source viewer's use of private CORE verification helpers. Literal search and
tokenization remain provisional placements; comparative word measures stay in
Reflection. These judgments do not establish computation's adequacy to the Idea.

## 1. Reading and evidence

Primary edition, checked against the local CORE manifest: G. W. F. Hegel,
*The Science of Logic*, translated and edited by George di Giovanni
(Cambridge University Press, 2010), ISBN 9780521832557. No alternative
translation or secondary commentary supplies the judgments here.

I reread the sections below through the current checkout, using the supplied
interpreter and the read-only private corpus:

```sh
/home/dima/Projects/code/sol/.venv/bin/python -B -m sol read PATH --corpus /home/dima/Projects/code/sol/local-corpus --plain
```

This is `sol read PATH --corpus … --plain`, using the checkout's command rather
than an installed command that could select another checkout. Directory paths
include their children. Page ranges below were checked against indexed records'
`sources[].printed_page`; they are printed edition pages, not inferred PDF
offsets. The private text and temporary reading outputs are not committed.
All accounts of the text below are paraphrases; architectural interpretations
are explicitly distinguished. Reading the transcription is not new facsimile
or transcription acceptance. This pass builds on, but does not silently rewrite,
[READING_BEING](READING_BEING.md) (especially §8) and
[READING_ESSENCE](READING_ESSENCE.md).

| Key | Section in the CORE edition | Reader path | Pages used |
| --- | --- | --- | --- |
| B1 | Being → General division of being | `/BEING/general-division-of-being.txt` | 56–57 |
| B2 | Being → Quality → Existence → Finitude → Determination, constitution, and limit | `/BEING/i-determinateness-quality/2-existence/b-finitude/b-determination-constitution-and-limit.txt` | 95–101 |
| B3 | Being → Quantity, introduction | `/BEING/ii-magnitude-quantity/00-introduction.txt` | 152–153 |
| B4 | Being → Quantity → Quantity → Continuous and discrete magnitude | `/BEING/ii-magnitude-quantity/1-quantity/b-continuous-and-discrete-magnitude/00-introduction.txt` | 165–166 |
| B5 | Being → Quantity → Quantum → Number | `/BEING/ii-magnitude-quantity/2-quantum/a-number/00-introduction.txt` | 168–170 |
| B6 | Being → Measure → Specific quantity → Specifying measure → The rule | `/BEING/iii-measure/1-specific-quantity/b-specifying-measure/a-the-rule.txt` | 291–292 |
| B7 | Being → Measure → Real measure, introduction; The relation of independent measures, introduction | `/BEING/iii-measure/2-real-measure/00-introduction.txt`; `/BEING/iii-measure/2-real-measure/a-the-relation-of-independent-measures/00-introduction.txt` | 302–303 |
| B8 | Being → Measure → Real measure → The relation of independent measures → Measure as a series of measure-relations | `/BEING/iii-measure/2-real-measure/a-the-relation-of-independent-measures/b-measure-as-a-series-of-measure-relations.txt` | 305–308 |
| B9 | Being → Measure → Real measure → Nodal lines of measure-relations, introduction | `/BEING/iii-measure/2-real-measure/b-nodal-lines-of-measure-relations/00-introduction.txt` | 318–320 |
| R1 | Essence, doctrine opening and division | `/ESSENCE/essence.txt` | 337–339 |
| R2 | Essence → Reflection within itself → Shine → Reflection → External reflection; Determining reflection | `/ESSENCE/i-essence-as-reflection-within/1-shine/c-reflection` | 348–353 (read with the preceding positing reflection) |
| R3 | Essence → Reflection within itself → The essentialities or the determinations of reflection → Difference → Diversity | `/ESSENCE/i-essence-as-reflection-within/2-the-essentialities-or-the-determinations-of-reflection/b-difference/2-diversity/00-introduction.txt` | 362–365; comparison especially 363–364 |
| A1 | Essence → Appearance, section introduction; Appearance, chapter introduction | `/ESSENCE/ii-appearance/00-introduction.txt`; `/ESSENCE/ii-appearance/2-appearance/00-introduction.txt` | 418–419; 437–438 |
| A2 | Essence → Appearance → The essential relation → Relation of outer and inner | `/ESSENCE/ii-appearance/3-the-essential-relation/c-relation-of-outer-and-inner` | 460–464 |
| X1 | Essence → Actuality, section introduction; Actuality, chapter introduction | `/ESSENCE/iii-actuality/00-introduction.txt`; `/ESSENCE/iii-actuality/2-actuality/00-introduction.txt` | 465; 477–478 |
| X2 | Essence → Actuality → The absolute relation → Reciprocity of action | `/ESSENCE/iii-actuality/3-the-absolute-relation/c-reciprocity-of-action.txt` | 503–505 |

The Measure introduction (p. 282 onward) and *Combination of two measures*
(pp. 303–305) were also reread as context for B7–B9. The latter explains
reciprocal specification through weight/volume relations; a library function
returning a ratio is not thereby such a relation.

## 2. Mechanical cross-division import map

### 2.1 Method, scope and judgment rule

This regenerates [INVENTORY_ESSENCE_CORE §10](INVENTORY_ESSENCE_CORE.md#10-reproducing-the-mechanical-ledger)'s
standard-library AST ledger for the new layout. The complete adapted script is
in §2.4. It parses `sol/**/*.py`, `scripts/*.py` and `tests/*.py` without importing
SOL or opening the corpus; resolves relative imports; records a known
`from` base plus each known child module; walks imports inside functions and
conditionals too; and collapses repetitions to one directed module pair with
all import-line numbers. Only product/tool source edges are printed. Tests are
parsed to preserve the inventory's known-module universe, but test-origin
edges are outside this requested product map.

Buckets: **BEING root** includes `neovim` and `workspace`; **Quality**,
**Quantity**, **Measure** are distinguished from it. **ESSENCE root** includes
the facade, CLI, catalogs and TUI; **Reflection**, **Appearance**, **Actuality**
are separate. **CORE** includes both `sol.core` and `sol.corpus`, including
conversion, onboarding and extraction maintenance; imports between those two
packages are therefore internal, not omitted cross-division edges. **APP**,
**PRESENTATION**, **INTERCHANGE**, **SCRIPTS**, **CONCEPT** are separate buckets.
**BOOT** is `sol` and `sol.__main__`, needed to account for the entry-point glue
and imports of `sol.__version__` or `from sol import core`.

An edge means a syntactic dependency, not proof of eager loading or execution.
For example, `from sol import core` generates both a BOOT base edge and a CORE
child edge; it does not invoke `sol.cli()`. Parent package edges from
`from package import module` are intentionally retained, as in the inventory.
Implicit Python parent loading is not expanded into extra edges. External and
standard-library imports, imports encoded in strings, facade attribute
resolution, Lua, subprocess command lines and runtime reachability are not
resolved by this method. §2.3 inspects the material omissions separately.

Every edge below carries one of these judgments against
[ARCHITECTURE §2](../../ARCHITECTURE.md#dependency-direction):

| Code | Direction and judgment |
| --- | --- |
| D | **Conforms:** BEING/Quality or ESSENCE/Reflection → CORE requests data, references, configuration or source evidence. CORE has no reverse product edge. Private helper and projection qualifications are in §§3.5–3.6. |
| L | **Conforms:** a division root → its own subdivision. Reading adapters share actions; ESSENCE adapters invoke engines. This charter supplies no ban on such internal edges and no requirement that logical order equal Python import order. |
| P | **Conforms provisionally:** BEING, ESSENCE or APP → shared PRESENTATION data/utilities. No reverse import; the bounded exception requires the scrutiny in §3.8. |
| I | **Conforms provisionally:** BEING and ESSENCE → INTERCHANGE's private launch envelope/probe, without either interface importing the other. Format validation is not source verification (§§2.3, 3.8). |
| C | **Conforms:** APP → the components it composes, or BOOT → APP on command invocation. This is dispatch, not CORE depending on an interface, and not implementation of CONCEPT (§3.7). |
| V | **Conforms:** imports of `sol.__version__` or a syntactic `sol` base used to reach `sol.core`; BOOT has no eager application import. Do not read the resulting syntactic cycle as runtime startup. |
| T | **Conforms:** SCRIPTS → product APIs for installation or diagnostics, under SPECULATIVE §6. Product code does not import scripts. |

### 2.2 Complete crossing-edge ledger

177 Python files parsed; **139 crossing module pairs** (all line sites retained).
Source cells give repository file paths and import lines; targets are Python
module names. The final column applies the judgment rule above to every pair.

| Source file and import line(s) | Imported module | Direction | Judgment |
| --- | --- | --- | --- |
| `scripts/install.py`:25 | `sol.being.neovim.runtime` | SCRIPTS → BEING root | T |
| `scripts/reader_timings.py`:65 | `sol` | SCRIPTS → BOOT | T |
| `scripts/reader_timings.py`:30 | `sol.app` | SCRIPTS → APP | T |
| `scripts/reader_timings.py`:30 | `sol.app.main` | SCRIPTS → APP | T |
| `scripts/reader_timings.py`:68 | `sol.being.actions` | SCRIPTS → BEING root | T |
| `scripts/reader_timings.py`:31,32,72,73 | `sol.being.neovim` | SCRIPTS → BEING root | T |
| `scripts/reader_timings.py`:31,72 | `sol.being.neovim.host` | SCRIPTS → BEING root | T |
| `scripts/reader_timings.py`:73 | `sol.being.neovim.reader` | SCRIPTS → BEING root | T |
| `scripts/reader_timings.py`:32 | `sol.being.neovim.splash` | SCRIPTS → BEING root | T |
| `scripts/reader_timings.py`:71 | `sol.being.quality.typography` | SCRIPTS → Quality | T |
| `scripts/reader_timings.py`:69 | `sol.being.render` | SCRIPTS → BEING root | T |
| `scripts/reader_timings.py`:70 | `sol.being.surface` | SCRIPTS → BEING root | T |
| `scripts/reader_timings.py`:74 | `sol.being.workspace.reader` | SCRIPTS → BEING root | T |
| `scripts/reader_timings.py`:75 | `sol.being.workspace.store` | SCRIPTS → BEING root | T |
| `scripts/reader_timings.py`:65 | `sol.core` | SCRIPTS → CORE | T |
| `scripts/reader_timings.py`:66 | `sol.core.paths` | SCRIPTS → CORE | T |
| `scripts/reader_timings.py`:67 | `sol.corpus` | SCRIPTS → CORE | T |
| `scripts/reader_timings.py`:67 | `sol.corpus.contract` | SCRIPTS → CORE | T |
| `sol/__init__.py`:8 | `sol.app.main` | BOOT → APP | C |
| `sol/app/commands.py`:54 | `sol.core.config` | APP → CORE | C |
| `sol/app/commands.py`:55 | `sol.core.corpus` | APP → CORE | C |
| `sol/app/commands.py`:10 | `sol.core.files` | APP → CORE | C |
| `sol/app/commands.py`:66,71 | `sol.presentation.text` | APP → PRESENTATION | P |
| `sol/app/launch.py`:16 | `sol.being.neovim` | APP → BEING root | C |
| `sol/app/launch.py`:16 | `sol.being.neovim.splash` | APP → BEING root | C |
| `sol/app/launch.py`:79 | `sol.being.workspace.catalog` | APP → BEING root | C |
| `sol/app/launch.py`:27 | `sol.being.workspace.launch` | APP → BEING root | C |
| `sol/app/launch.py`:28 | `sol.being.workspace.profiles` | APP → BEING root | C |
| `sol/app/launch.py`:29 | `sol.being.workspace.reader` | APP → BEING root | C |
| `sol/app/launch.py`:30 | `sol.being.workspace.store` | APP → BEING root | C |
| `sol/app/launch.py`:7 | `sol.core.models` | APP → CORE | C |
| `sol/app/main.py`:31 | `sol.being.actions` | APP → BEING root | C |
| `sol/app/main.py`:241 | `sol.being.neovim` | APP → BEING root | C |
| `sol/app/main.py`:237 | `sol.being.neovim.host` | APP → BEING root | C |
| `sol/app/main.py`:60,319 | `sol.being.neovim.reader` | APP → BEING root | C |
| `sol/app/main.py`:241 | `sol.being.neovim.splash` | APP → BEING root | C |
| `sol/app/main.py`:34 | `sol.being.render` | APP → BEING root | C |
| `sol/app/main.py`:41 | `sol.being.shell` | APP → BEING root | C |
| `sol/app/main.py`:304 | `sol.being.workspace.diagnostics` | APP → BEING root | C |
| `sol/app/main.py`:94,186 | `sol.being.workspace.launch` | APP → BEING root | C |
| `sol/app/main.py`:78 | `sol.being.workspace.lifecycle` | APP → BEING root | C |
| `sol/app/main.py`:187 | `sol.being.workspace.profiles` | APP → BEING root | C |
| `sol/app/main.py`:79,124,305 | `sol.being.workspace.reader` | APP → BEING root | C |
| `sol/app/main.py`:123 | `sol.being.workspace.store` | APP → BEING root | C |
| `sol/app/main.py`:20 | `sol.core.config` | APP → CORE | C |
| `sol/app/main.py`:47 | `sol.core.corpus` | APP → CORE | C |
| `sol/app/main.py`:24 | `sol.core.models` | APP → CORE | C |
| `sol/app/main.py`:25,26 | `sol.core.paths` | APP → CORE | C |
| `sol/app/main.py`:222 | `sol.core.reference_cli` | APP → CORE | C |
| `sol/app/main.py`:295 | `sol.core.source` | APP → CORE | C |
| `sol/app/main.py`:19 | `sol.corpus.edition` | APP → CORE | C |
| `sol/app/main.py`:284 | `sol.corpus.onboarding` | APP → CORE | C |
| `sol/app/main.py`:219 | `sol.essence.cli` | APP → ESSENCE root | C |
| `sol/app/main.py`:33 | `sol.presentation.text` | APP → PRESENTATION | P |
| `sol/app/main.py`:27 | `sol.presentation.theme` | APP → PRESENTATION | P |
| `sol/app/options.py`:10 | `sol` | APP → BOOT | V |
| `sol/app/options.py`:12 | `sol.presentation.theme` | APP → PRESENTATION | P |
| `sol/being/actions.py`:519,737,755 | `sol.being.quality.search` | BEING root → Quality | L |
| `sol/being/actions.py`:415,452 | `sol.being.quantity.navigation` | BEING root → Quantity | L |
| `sol/being/actions.py`:836,845 | `sol.core` | BEING root → CORE | D |
| `sol/being/actions.py`:16,779 | `sol.core.models` | BEING root → CORE | D |
| `sol/being/actions.py`:17 | `sol.core.paths` | BEING root → CORE | D |
| `sol/being/actions.py`:162,613,715 | `sol.core.references` | BEING root → CORE | D |
| `sol/being/neovim/host.py`:21 | `sol.being.quality.typography` | BEING root → Quality | L |
| `sol/being/neovim/host.py`:337 | `sol.core.config` | BEING root → CORE | D |
| `sol/being/neovim/host.py`:22 | `sol.presentation.text` | BEING root → PRESENTATION | P |
| `sol/being/neovim/host.py`:24 | `sol.presentation.theme` | BEING root → PRESENTATION | P |
| `sol/being/neovim/reader.py`:18 | `sol.being.quality.structure` | BEING root → Quality | L |
| `sol/being/neovim/reader.py`:15,561 | `sol.core.protocol` | BEING root → CORE | D |
| `sol/being/neovim/reader.py`:91,326 | `sol.core.source` | BEING root → CORE | D |
| `sol/being/neovim/reader.py`:436 | `sol.interchange.essence` | BEING root → INTERCHANGE | I |
| `sol/being/neovim/reader.py`:20 | `sol.presentation.text` | BEING root → PRESENTATION | P |
| `sol/being/neovim/reader.py`:21 | `sol.presentation.theme` | BEING root → PRESENTATION | P |
| `sol/being/neovim/splash.py`:22 | `sol.presentation.theme` | BEING root → PRESENTATION | P |
| `sol/being/neovim/window.py`:20,21 | `sol.presentation.theme` | BEING root → PRESENTATION | P |
| `sol/being/quality/structure.py`:2 | `sol.core.models` | Quality → CORE | D |
| `sol/being/quality/structure.py`:3 | `sol.core.paths` | Quality → CORE | D |
| `sol/being/quality/typography.py`:195 | `sol.corpus.errors` | Quality → CORE | D |
| `sol/being/quality/typography.py`:48,196 | `sol.corpus.markdown` | Quality → CORE | D |
| `sol/being/render.py`:10 | `sol` | BEING root → BOOT | V |
| `sol/being/render.py`:12 | `sol.core.models` | BEING root → CORE | D |
| `sol/being/render.py`:13 | `sol.core.paths` | BEING root → CORE | D |
| `sol/being/render.py`:11 | `sol.corpus.edition` | BEING root → CORE | D |
| `sol/being/render.py`:15 | `sol.presentation.text` | BEING root → PRESENTATION | P |
| `sol/being/shell.py`:12 | `sol.core.models` | BEING root → CORE | D |
| `sol/being/shell.py`:13 | `sol.core.paths` | BEING root → CORE | D |
| `sol/being/shell.py`:15 | `sol.presentation.text` | BEING root → PRESENTATION | P |
| `sol/being/source_view.py`:13 | `sol.core.source` | BEING root → CORE | D |
| `sol/being/surface.py`:14 | `sol.core.models` | BEING root → CORE | D |
| `sol/being/surface.py`:15 | `sol.core.protocol` | BEING root → CORE | D |
| `sol/being/surface.py`:16 | `sol.core.references` | BEING root → CORE | D |
| `sol/being/surface.py`:13 | `sol.corpus.contract` | BEING root → CORE | D |
| `sol/being/workspace/diagnostics.py`:12 | `sol.core.references` | BEING root → CORE | D |
| `sol/being/workspace/reader.py`:17 | `sol.core.references` | BEING root → CORE | D |
| `sol/being/workspace/reader.py`:127 | `sol.corpus.contract` | BEING root → CORE | D |
| `sol/being/workspace/reader.py`:19 | `sol.presentation.text` | BEING root → PRESENTATION | P |
| `sol/essence/cli.py`:145 | `sol.core` | ESSENCE root → CORE | D |
| `sol/essence/cli.py`:146 | `sol.core.wire` | ESSENCE root → CORE | D |
| `sol/essence/cli.py`:147 | `sol.essence.essence_as_reflection_within_itself` | ESSENCE root → Reflection | L |
| `sol/essence/cli.py`:158 | `sol.essence.essence_as_reflection_within_itself.prose` | ESSENCE root → Reflection | L |
| `sol/essence/cli.py`:141,147 | `sol.essence.essence_as_reflection_within_itself.sentences` | ESSENCE root → Reflection | L |
| `sol/essence/cli.py`:135 | `sol.essence.essence_as_reflection_within_itself.tfidf` | ESSENCE root → Reflection | L |
| `sol/essence/cli.py`:125 | `sol.essence.essence_as_reflection_within_itself.words` | ESSENCE root → Reflection | L |
| `sol/essence/essence_as_reflection_within_itself/corpus_inputs.py`:6 | `sol` | Reflection → BOOT | V |
| `sol/essence/essence_as_reflection_within_itself/corpus_inputs.py`:6 | `sol.core` | Reflection → CORE | D |
| `sol/essence/essence_as_reflection_within_itself/prose.py`:13 | `sol` | Reflection → BOOT | V |
| `sol/essence/essence_as_reflection_within_itself/prose.py`:13 | `sol.core` | Reflection → CORE | D |
| `sol/essence/essence_as_reflection_within_itself/prose.py`:14 | `sol.corpus.markdown` | Reflection → CORE | D |
| `sol/essence/essence_as_reflection_within_itself/sentence_inputs.py`:41,194 | `sol` | Reflection → BOOT | V |
| `sol/essence/essence_as_reflection_within_itself/sentence_inputs.py`:41,194 | `sol.core` | Reflection → CORE | D |
| `sol/essence/essence_as_reflection_within_itself/sentences.py`:207,257 | `sol` | Reflection → BOOT | V |
| `sol/essence/essence_as_reflection_within_itself/sentences.py`:207,257 | `sol.core` | Reflection → CORE | D |
| `sol/essence/sentence_cli.py`:64 | `sol.core` | ESSENCE root → CORE | D |
| `sol/essence/sentence_cli.py`:4 | `sol.essence.essence_as_reflection_within_itself.sentences` | ESSENCE root → Reflection | L |
| `sol/essence/sentence_cli.py`:6 | `sol.essence.essence_as_reflection_within_itself.word_inputs` | ESSENCE root → Reflection | L |
| `sol/essence/tfidf_cli.py`:2 | `sol.essence.essence_as_reflection_within_itself.tfidf` | ESSENCE root → Reflection | L |
| `sol/essence/tfidf_cli.py`:4 | `sol.essence.essence_as_reflection_within_itself.word_inputs` | ESSENCE root → Reflection | L |
| `sol/essence/tui/__main__.py`:7 | `sol.interchange.essence` | ESSENCE root → INTERCHANGE | I |
| `sol/essence/tui/__main__.py`:8 | `sol.presentation.theme` | ESSENCE root → PRESENTATION | P |
| `sol/essence/tui/app.py`:26 | `sol.presentation.theme` | ESSENCE root → PRESENTATION | P |
| `sol/essence/tui/sentences.py`:52 | `sol` | ESSENCE root → BOOT | V |
| `sol/essence/tui/sentences.py`:52 | `sol.core` | ESSENCE root → CORE | D |
| `sol/essence/tui/sentences.py`:37 | `sol.essence.essence_as_reflection_within_itself` | ESSENCE root → Reflection | L |
| `sol/essence/tui/sentences.py`:37 | `sol.essence.essence_as_reflection_within_itself.sentences` | ESSENCE root → Reflection | L |
| `sol/essence/tui/tfidf.py`:23 | `sol` | ESSENCE root → BOOT | V |
| `sol/essence/tui/tfidf.py`:23 | `sol.core` | ESSENCE root → CORE | D |
| `sol/essence/tui/words.py`:104,110 | `sol` | ESSENCE root → BOOT | V |
| `sol/essence/tui/words.py`:104,110 | `sol.core` | ESSENCE root → CORE | D |
| `sol/essence/tui/words.py`:66,75 | `sol.core.paths` | ESSENCE root → CORE | D |
| `sol/essence/tui/words.py`:47,55 | `sol.essence.essence_as_reflection_within_itself` | ESSENCE root → Reflection | L |
| `sol/essence/tui/words.py`:55 | `sol.essence.essence_as_reflection_within_itself.comparison` | ESSENCE root → Reflection | L |
| `sol/essence/tui/words.py`:215 | `sol.essence.essence_as_reflection_within_itself.tokenization` | ESSENCE root → Reflection | L |
| `sol/essence/tui/words.py`:47 | `sol.essence.essence_as_reflection_within_itself.word_inputs` | ESSENCE root → Reflection | L |
| `sol/essence/tui/words.py`:47 | `sol.essence.essence_as_reflection_within_itself.words` | ESSENCE root → Reflection | L |
| `sol/essence/word_cli.py`:88 | `sol` | ESSENCE root → BOOT | V |
| `sol/essence/word_cli.py`:88 | `sol.core` | ESSENCE root → CORE | D |
| `sol/essence/word_cli.py`:141 | `sol.essence.essence_as_reflection_within_itself.comparison` | ESSENCE root → Reflection | L |
| `sol/essence/word_cli.py`:7 | `sol.essence.essence_as_reflection_within_itself.word_inputs` | ESSENCE root → Reflection | L |
| `sol/essence/word_cli.py`:8 | `sol.essence.essence_as_reflection_within_itself.words` | ESSENCE root → Reflection | L |

Neither Measure, Appearance, Actuality nor CONCEPT has a crossing edge; their
Python packages contain only markers. Quantity's navigation has no outgoing
crossing edge. `scripts/check_docs.py` has no product import. CORE,
PRESENTATION and INTERCHANGE have **no outgoing cross-bucket AST edge**;
there is **no direct BEING ↔ ESSENCE import** at this baseline. This is a
scoped mechanical result, not a claim that the components never communicate.

### 2.3 Dependencies the AST map cannot settle

- **ESSENCE's dynamic facade:** `sol/essence/__init__.py:16–31` selects
  `prose`, `word_inputs`, `words`, `comparison`, `sentences` or `tfidf` inside
  Reflection and calls `import_module`. These are six additional dynamic
  ESSENCE-root → Reflection module pairs, judged **L**; the AST cannot infer
  them from literal module strings. In particular TUI calls through
  `from sol.essence import analyze_tfidf` rely on this facade, although their
  direct import edge stays within ESSENCE root. CORE's analogous export table
  (`sol/core/__init__.py:14–54`) resolves only CORE/corpus modules, so it adds
  no crossing direction. Neither facade starts an interface.
- **Process launch:** `sol/being/neovim/reader.py:436–472` uses INTERCHANGE,
  checks a CORE reference, writes the temporary context, and returns the
  `python -m sol.essence.tui` command. That BEING → ESSENCE execution relation
  remains intentional under ARCHITECTURE §4. Removing the Python import did
  not remove knowledge of the other component's launch contract.
- **Return path:** `sol/essence/tui/__main__.py:7–27` reads the envelope through
  INTERCHANGE; study adapters obtain current text through CORE, not BEING.
  The return OSC is parsed in
  `sol/being/neovim/neovim_essence.lua:124–166`, then handled through actions
  by `sol/being/neovim/reader.py:548–587`'s `essence_source` branch. It is a checked
  request to navigate, not authority for ESSENCE to write reader state. This
  semantic relation is permitted; it is not a reverse data-provider import.
- **Packaging, Lua and command strings:** `sol/__main__.py:3–6` calls `cli`;
  `sol/__init__.py:6–10` lazily delegates to APP. Installed commands and the
  Neovim host's Lua resources are not Python AST edges. Existing packaging,
  CORE-only, file-only analysis and reader exchange tests must still protect
  these routes; the static graph does not replace those tests.

### 2.4 Reproduction script

Run from the repository root with the supplied Python interpreter. This is
the inventory's import resolution with bucket classification, import-line
collection and judgment columns added. It writes only to stdout. Counts are
module pairs, not symbols, unique import statements or executed imports.

```python
import ast
from collections import Counter
from pathlib import Path

paths = sorted([
    *Path('sol').rglob('*.py'),
    *Path('scripts').glob('*.py'),
    *Path('tests').glob('*.py'),
])
modules = {
    p: str(p.with_suffix('')).replace('/', '.').removesuffix('.__init__')
    for p in paths
}
known = set(modules.values())
files = {module: str(path) for path, module in modules.items()}

def division(module):
    for prefix, label in (
        ('sol.being.quality', 'Quality'),
        ('sol.being.quantity', 'Quantity'),
        ('sol.being.measure', 'Measure'),
        ('sol.being', 'BEING root'),
        ('sol.essence.essence_as_reflection_within_itself', 'Reflection'),
        ('sol.essence.appearance', 'Appearance'),
        ('sol.essence.actuality', 'Actuality'),
        ('sol.essence', 'ESSENCE root'),
        ('sol.core', 'CORE'),
        ('sol.corpus', 'CORE'),
        ('sol.app', 'APP'),
        ('sol.presentation', 'PRESENTATION'),
        ('sol.interchange', 'INTERCHANGE'),
        ('sol.concept', 'CONCEPT'),
        ('scripts', 'SCRIPTS'),
    ):
        if module == prefix or module.startswith(prefix + '.'):
            return label
    if module in {'sol', 'sol.__main__'}:
        return 'BOOT'
    if module == 'tests' or module.startswith('tests.'):
        return 'TESTS'
    return 'OTHER'

def judgment(left, right):
    if left == 'SCRIPTS':
        return 'T'
    if right == 'BOOT':
        return 'V'
    if right == 'PRESENTATION':
        return 'P'
    if right == 'INTERCHANGE':
        return 'I'
    if left == 'APP' or (left == 'BOOT' and right == 'APP'):
        return 'C'
    if right == 'CORE' and left in {'BEING root', 'Quality', 'ESSENCE root', 'Reflection'}:
        return 'D'
    if (left, right) in {('BEING root', 'Quality'), ('BEING root', 'Quantity'),
                         ('ESSENCE root', 'Reflection')}:
        return 'L'
    return 'REVIEW'  # A new direction needs a judgment, not automatic acceptance.

edges = {}
for path, module in modules.items():
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        deps = set()
        if isinstance(node, ast.Import):
            deps.update(item.name for item in node.names if item.name in known)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                package = module.split('.')
                if path.name != '__init__.py':
                    package = package[:-1]
                base = '.'.join(package[:len(package) - node.level + 1]
                                + ([base] if base else []))
            if base in known:
                deps.add(base)
            for item in node.names:
                child = base + '.' + item.name
                if child in known:
                    deps.add(child)
        for target in deps:
            if division(module) != 'TESTS' and division(module) != division(target):
                edges.setdefault((module, target), set()).add(node.lineno)

counts = Counter()
for (source, target), lines in sorted(edges.items()):
    left, right = division(source), division(target)
    counts[left, right] += 1
    print(f'| `{files[source]}`:{",".join(map(str, sorted(lines)))} | `{target}` | {left} → {right} | {judgment(left, right)} |')
print('\nSUMMARY')
for (left, right), count in sorted(counts.items()):
    print(f'{left} -> {right}: {count}')
print(f'{len(paths)} Python files; {len(edges)} crossing module pairs')
```

## 3. Ambiguities, retained content and verdicts

### 3.1 The reading session binds Quality and Quantity

**Code facts.** `sol/being/actions.py:414–428` asks Quantity for layout and
vertical offsets; `:517–535` asks Quality for exact occurrence projections.
`ReadingSession`'s scope and cursor (`:21–77`) refer to definite passages,
while `_transition` (`:299–330`) integrates selection validity, history and
workspace checkpoints. This is more than cursor arithmetic. The map shows
outgoing root → subdivision edges, with neither subdivision importing actions.

**Text.** B1, pp. 56–57, distinguishes quality's immediate determinateness
from quantitative variation indifferent to being; its division is preliminary
and requires justification through development. B2, pp. 95–101, makes limit
constitutive of what something is. B3, pp. 152–153, develops indifferent
determinateness into quantum and ratio.

**Interpretation and verdict — keep.** The coherent content to preserve is a
single reading action that changes position *in this selected text* while
retaining passage identity and checkpoint semantics. The BEING root binds
these responsibilities without making Quality depend on Quantity or hiding
them in a numeric cursor class. Their binding alone is not Measure: a row
width does not constitute the passage's quality. A split becomes useful only
if independently changing boundary policies and geometry accumulate their own
callers; the present fact of two imports does not establish that need. Preserve
rollback and staged-checkpoint behavior (`tests/test_reader_actions.py:283–354`)
in any future extraction. No register revision is warranted for this row.

### 3.2 Search in Quality and comparison in Reflection

**Code facts.** Quality's `sol/being/quality/search.py:33–34,78–151` applies
NFC/casefold matching and proves the return to canonical source spans; it
reports unmappable normalized matches explicitly. Selection of matching
passages actually also lives in `sol/core/models.py:98–117` and
`sol/being/actions.py:773–796`. The package named search is not the whole
search pipeline. In contrast,
`sol/essence/essence_as_reflection_within_itself/comparison.py:18–26,38–71`
computes declared rates and ratios over separately scoped, verified providers.

**Text.** B2, pp. 95–101, explains qualitative limit; R3, pp. 362–365,
especially 363–364, makes likeness/unlikeness depend on a comparing standpoint
and then criticizes keeping those sides externally apart. R2, pp. 348–353,
does not stop at external reflection but develops its relation to positing
and determining reflection.

**Interpretation and verdict — keep, provisionally.** Literal retrieval is a
defensible reading responsibility: return the occurrence of a requested form
to its unchanged source. Comparative analysis makes its reference population,
denominators and method part of the investigation. This functional difference
supports Quality versus Reflection more than the bare presence of an equality
test does. Nevertheless normalization already abstracts from differences;
Quality cannot mean a wholly unmediated computation, and Reflection cannot
mean every implementation that compares bytes. The retained content is exact
source return plus inspectable analytical standpoint. A future semantic or
statistical search would need fresh classification rather than inheriting
Quality from the command name. The register's outstanding request to confirm
this against the Essence reading can now be closed, while confidence remains
provisional. Unicode/partial-span behavior is protected in
`tests/test_reader_search_projection.py`; read-only search is protected in
`tests/test_reader_actions.py:107–120`.

### 3.3 Comparative word measures: Real measure or Reflection?

**Code facts.** `comparison.py:18–26,55–71` in Reflection derives per-10,000
rate differences and unsmoothed log ratios from the two populations; zeros
have explicit undefined statuses. `tfidf.py:13–23,32–56,77–85` in the same
directory declares each provider row a document, counts empty rows in N,
computes IDF and L2 normalization over the whole vocabulary, then truncates
the output. It takes **one** provider, not a separate reference provider;
the selected document population supplies its comparison context. Paragraphs
and whole files are therefore different document units even when their bytes
can describe the same prose. Tests make these choices observable:
`tests/test_word_comparison.py:40–82,108–124` and
`tests/test_tfidf.py:30–40,136–175`.

**Text.** B7, pp. 302–303, concerns measures that constitute qualities and
relate to other such measures. B8, pp. 305–308, develops characteristic series
and a common unit in the ratios of those series. This makes
[READING_BEING §8.2](READING_BEING.md#82-consequences)'s alternative substantive:
a profile only determined through relations is closer than a solitary count.
But B6, pp. 291–292, distinguishes the externally applied rule, and R3,
pp. 363–364, examines the standpoint of comparison.

**Interpretation and verdict — keep Reflection; the stronger Measure claim
is an open question.** A chosen standpoint is not by itself a decisive
objection to Measure: real measures are also compared, and the text explicitly
develops their externality. The present limitation is more definite. These
methods stipulate document units, eligibility and normalization without
showing that their relations constitute the qualitative determination of the
texts. L2 normalization supplies a calculational norm; it does not demonstrate
the common unit derived from characteristic series in B8. A series of lexical
weights is consequently not yet Hegel's series of real measures.

Choosing the whole corpus of a doctrine or an author can improve the
*argument for the research scope*. It does not remove the analyst's decision
about documents or prove intrinsic measure. The same doctrine admits different
segmentations and lexical policies. Revisit this placement only if an inquiry
articulates which qualitative determination is constituted by which relations,
why those reference units belong to that object, and what evidence would
defeat that interpretation. Sensitivity to segmentation and population would
be useful evidence, not proof of an immanent transition. Preserve current
receipts, explicit zeros, provenance and reproducible formulas either way.
The register status now records that this cross-reading was done; it does not
move E2 to Measure or close the research question.

### 3.4 Empty Measure, Appearance and Actuality

**Code facts.** `sol/being/measure/__init__.py:1`,
`sol/essence/appearance/__init__.py:1` and
`sol/essence/actuality/__init__.py:1` contain only explanatory docstrings.
`sol/being/surface.py:41–43` bounds footnote traversal; source locations are
captured in `sol/core/source.py:289–312`; a result is presented and saved by
ESSENCE's TUI (`sol/essence/tui/app.py:25,334–353`). None is a hidden
implementation of the empty logical divisions.

**Text.** B6–B9, pp. 291–292, 302–308, 318–320, distinguish applied standards,
qualitatively constitutive relations and nodal changes. A1, pp. 418–419,
437–438, develops essence's appearance and rejects making it an external
observer's label. A2, pp. 460–464, develops inner/outer into their mediated
unity. X1, pp. 465, 477–478, distinguishes actuality from mere being or
concrete existence.

**Interpretation and verdict — keep empty.** Resource caps, terminal-size
branches and top-N cutoffs do not by themselves establish a nodal line of the
text's qualities. They warrant inquiry into the procedure's sensitivity.
Likewise a visible screen is not yet Appearance, nor a recomputed or persisted
artifact Actuality. Preserve useful source-linked presentation and verified
publication without making successful execution stand for those determinations.
The empty markers expose where no current positive interpretation is supported;
filling them for symmetry would conceal that result. E5–E7's unresolved
subdivision statuses stay unresolved. This does not rule out future analyses
of how an analytical determination's expression changes the determination.

### 3.5 CORE's edition-shaped projection (C3)

**Code facts.** `sol/core/corpus.py:42–74` constructs a named three-doctrine
tree with fixed starting pages and accepts only Arabic printed-page labels;
`:107–132` selects Hegel-attributed main text and builds reader `Passage`s.
`:144–151` retains the complete verified record graph alongside that view.
`sol/core/models.py:12–58` exposes `Node`, `Passage`, mutable `Book` collections
and integer printed pages. This is a real edition/reader projection inside a
shared service. It is not CORE importing BEING. ESSENCE engines access
snapshots directly, while TUI adapters obtain their snapshot and display labels
through this `Book` loader (`sol/essence/tui/words.py:104–111`;
`sol/essence/tui/sentences.py:52–65`). ESSENCE's separate, explicitly versioned
main-text eligibility also uses doctrine-shaped `reader_path`s
(`sol/essence/essence_as_reflection_within_itself/corpus_inputs.py:9,51–58`;
`words.py:20–29`). A package move would not eliminate all edition assumptions.

**Text.** B1, pp. 56–57, says the preliminary division needs justification
through the movement of its determinations. R1, pp. 337–339, criticizes an
abstraction that leaves excluded determinations standing unchanged outside an
empty essence. Neither text supplies a proof that an edition tree is the
logical development or that CORE is a metaphysical substrate.

**Interpretation and verdict — revise later.** Keep verified snapshots,
canonical addressing and the complete attributed graph as shared services;
make the named Hegel reader projection a more explicit adapter boundary in a
future design. Moving the entire models/corpus cluster into BEING would discard
its shared content and jeopardize the public CORE API. The stronger successor
would distinguish the edition view from source custody while preserving IDs,
metadata and current callers, possibly by delegation behind the existing API.
No generic multi-corpus model, cache or immutable snapshot is introduced here.
The existing reader/TUI use makes this a shared projection, not solely a
BEING concern. A second projection or a contract proposal that can state how
compatibility is preserved would make a split actionable. The C3 status is revised to
record that direction; the API/contract design remains reserved if changed.

### 3.6 The source viewer imports private CORE helpers

**Code facts.** `sol/being/source_view.py:13` imports `_request_current` and
`_verify_file` from CORE. `:68–73,113–116` checks the captured request and
verified PDF before display/follow. `sol/core/source.py:315–341` rechecks
generation, identity chain, record metadata and PDF binding. CORE imports no
viewer. Thus the direction is right but a private implementation interface
has become a dependency across the boundary.

**Text.** B6, pp. 291–292, and B7, pp. 302–303, distinguish locating by an
external standard from relations that constitute qualitative determination.
The record and printed page are not independent measures that reciprocally
specify one another merely because a bounding box connects them.

**Interpretation and verdict — revise later at the interface; keep the
CORE/BEING split.** Preserve the shared validation and viewer independence.
A deliberately supported request-validation operation in CORE could replace
the private imports; copying validators into BEING would produce competing
trust rules. Any public API addition needs the separate contract review
required by CLAUDE.md. Also close the register's stale source-viewer Measure
hypothesis: [READING_BEING §8](READING_BEING.md#8-real-measure-read-in-full-addendum-22-october-2026)
already rejected it, and this pass confirms that conclusion. The older
rationale cell is provenance, not a reopening of that hypothesis. Existing
`tests/test_source_viewer.py` protects stale requests, PDF binding and viewer
behavior; new interfaces would have to retain those checks.

**Follow-up proposal (22 October 2026):**
[SOURCE_VALIDATION](SOURCE_VALIDATION.md) inventories the complete capture,
validation and viewer call chain, distinguishes existing guarantees from gaps,
and proposes a combined public CORE validator with immutable page locations.
It includes alternatives and an exact test/guard plan. The interface and
API-version interpretation are **maintainer decisions (reserved: public
contract)**; the proposal implements no code or API change.

### 3.7 Composition root and reserved CONCEPT

**Code facts.** `sol/__init__.py:6–10` delegates lazily to `sol.app.main`.
`sol/app/main.py:219–223` dispatches ESSENCE/reference commands; the rest
wires reading, source access and workspace launch. `sol/app/commands.py:54–71`
loads and prints CORE-retrieved text. APP is intentionally not dependency-free;
CORE and the analytical engines do not import it. `sol/concept/__init__.py:1`
is only the reservation marker.

**Text.** X2, pp. 503–505, develops reciprocity beyond an external bringing
together of independent substances, arriving at universal, singular and
particular determinations. R1, pp. 337–339, likewise does not identify unity
with a common container. SPECULATIVE §§4.1 and 7 defer CONCEPT until a
concrete requirement calls for its development.

**Interpretation and verdict — keep APP outside; CONCEPT remains an open
research lead.** Invocation and routing do integrate components operationally.
That preserves the useful entry-point seam, but supplies neither the logical
transition nor the research requirement for calling it CONCEPT. A future shared
inquiry lifecycle might motivate that reading; a common CLI parser presently
does not. The successful launch/return loop must not count as evidence that
software has realized reciprocity, freedom or the Idea. No CONCEPT subdivision
or application move follows, and the composition row needs no revised status.

### 3.8 INTERCHANGE and PRESENTATION outside the hierarchy

**Code facts.** `sol/interchange/essence.py:19–71` owns an exact-field private
context envelope, owner-only exclusive files, bounded reads and basic shape
checks; `:74–80` contains Textual's hint/probe. It does not validate a canonical
reference's truth: receiver adapters still use CORE. ESSENCE keeps investigation
state in `sol/essence/tui/context.py`. `sol/presentation/text.py:22–45` escapes
terminal controls without altering canonical strings; `theme.py:12–33` holds
width, presets and highlight names. Both packages use only standard-library
imports. The map shows shared callers and no reverse dependency.

**Text.** A1, pp. 437–438, makes Appearance more specific than something
displayed; R1, pp. 337–339, exposes the weakness of collecting determinations
externally without accounting for their unity. The practical exemption in
SPECULATIVE §6 and the dumping-ground warning in §9 must therefore be read
together. §6 is not an automatic exemption for any product code that can be
called a utility.

**Interpretation and verdict — keep, narrowly and provisionally.** Their
positive content is a small shared envelope and terminal data, removing the
need for ESSENCE to import a reader parser or BEING to import ESSENCE's UI.
They earn that location by this concrete seam, not by being philosophically
neutral. The Textual probe and reader-specific width are particularly clear
signs that the packages are bounded practical accommodations, not universal
abstractions. State ownership, study policies and canonical validation should
not migrate there simply because both components use them. If a future
envelope begins resolving IDs, selecting study material or saving investigations,
re-evaluate the owner and dependency direction; if presentation begins deriving
textual features, ask whether it is a reading or analytical policy. No future
API, generic event bus or new shared persistence layer is authorized here.
The register's existing I1 and presentation rows remain provisional; this review
adds no competing placement row.

### 3.9 The tokenizer's unit: limit, discrete magnitude or reflection?

**Follow-up research:** [WORD_UNIT](WORD_UNIT.md) specifies both current
definitions, measures their disagreement on the read-only private corpus, and
compares the four policy/ownership options. It recommends keeping and explaining
the distinction, explicitly for a maintainer decision; no behavior is changed.

**Code facts.**
`sol/essence/essence_as_reflection_within_itself/tokenization.py:10–32` starts
on a Unicode letter, admits letters/marks and internal apostrophes, and returns
NFC/casefold/apostrophe-normalized tokens with original codepoint offsets.
`words.py:20–29` in the same directory records that policy in the method;
its providers and sentence studies use that shared tokenizer. The token is
neither an arbitrary whitespace split nor a word's philosophical meaning.
`tests/test_word_frequencies.py:54–63,94–107` fixes Unicode, offsets, span and
byte-binding behavior; changing unit policy cannot be smuggled in as relocation.

There is already a concrete difference in the reader's unit:
`sol/being/quality/search.py:100–103` uses regular-expression `\w` boundaries
for its whole-word option, not the tokenizer's letter/apostrophe rules. An
invented-text probe with `can't 123` gives the study tokenizer one token
(`can't`, offsets 0–5), but reader whole-word queries match `can` at 0–3 and
`123` at 6–9. These names do not currently designate one universal lexical
unit. Whether the reader's option should expose or change that distinction
is an open behavior question, not settled by placing either helper.

**Text.** B2, pp. 95–101, concerns a something's limit; B4, pp. 165–166,
develops discrete magnitude as many ones of a shared unity, inseparable from
continuity. B5, pp. 168–170, distinguishes amount and unit in number. R2,
pp. 348–353, develops posited/reflected determination; R3, pp. 362–365,
questions the standpoint from which things count as like or unlike.

**Interpretation and verdict — keep the cohesive E1 group in Reflection;
the unit question stays open.** Cutting boundaries has a qualitative aspect;
counting occurrences abstracts them into repeatable units, a quantitative
aspect; deciding which forms are equivalent is a methodological determination.
An occurrence is one countable item, yet normalized *types* can unite different
source spellings. These are distinct questions about this one algorithm, not
three independent services already demanding three directories. Reflection
currently keeps the chosen equivalence relation with the receipt and scope
that make it inspectable. This does not identify normalized string equality
with essential identity or claim that the method performs determining
reflection in Hegel's full sense.

The preserved content is reproducible boundaries, admission rules and exact
source return. A future reader reuse or competing unit policy may justify
separating a boundary primitive from method-specific equivalence; neither
exists as a demonstrated need in this import map. Avoid moving the tokenizer
to CORE merely because it is shared by word and sentence studies: those are
both ESSENCE investigations, not consumers of a canonical lexical truth.
E1's existing provisional placement and alternatives remain; no status rewrite
is needed just to append a second endorsement.

## 4. Further subdivisions and register consequences

**Further logical subdivisions: none.** Quality has three small/cohesive
modules, Quantity one geometry module, and Reflection a cooperating ten-module
engine/provider group. The map exposes service/projection boundaries and policy
questions, not a demonstrated new logical determination requiring another
directory. More depth would currently classify individual operations rather
than explain a concrete, independently changing responsibility. Measure,
Appearance, Actuality and CONCEPT should not be populated for symmetry.

Later work has specific tests of adequacy: a second reader projection can test
C3's boundary; an explicit CORE validation interface can remove private-helper
coupling; competing unit policies or substantive reader reuse can test E1;
document/population sensitivity can investigate E2. None requires a deeper
logical directory in advance, and none is implemented by this review.

Only **Status** cells are changed in
[ARCHITECTURE §9](../../ARCHITECTURE.md#9-placement-register): search's pending
cross-reading is completed; the source Measure hypothesis is closed and its
private-interface seam flagged; E2 records the Reflection/Real-measure review;
C3 records the later projection-boundary revision. Existing location, rationale,
evidence and technical-consequence cells retain their history; the linked
verdict here supplies the qualification. All other statuses, including the
maintainer's workspace decision, remain untouched. No Decision statement,
public contract, dependency, schema, algorithm or corpus material changes.
