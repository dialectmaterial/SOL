# SOL usage manual

[Back to SOL](../README.md)

This manual covers the reader, virtual shell, personal workspaces, corpus maintenance, and optional source-view integration. Start with the [README](../README.md) for installation and a first reading session. Use `sol guide` for a compact guide in the terminal and `sol --help` for current CLI syntax.

## Contents

1. [Installation and extras](#install-with-pipx)
2. [Corpus selection and configuration](#choose-the-text)
3. [Reading, search, and structured output](#read-search-and-inspect)
4. [Virtual shell](#work-inside-the-virtual-shell)
5. [Workspaces, notes, comparison, backup, and export](#keep-a-reading-workspace)
6. [Source-review queue](#work-through-a-source-review-queue)
7. [Corpus maintenance](#maintain-and-review-the-corpus)
8. [Optional kitty integration and source viewing](#read-in-kitty-and-inspect-the-source)
9. [Development checks](#development-checks)

## Install with pipx

The [README](../README.md#install) gives the initial installation. The base package uses the standard library for reading and basic input. Optional extras are independent:

| Installation | Additional capability |
| --- | --- |
| `pipx install .` | Reader and basic shell |
| `pipx install '.[shell]'` | Enhanced prompt and multiline drafts |
| `pipx install '.[corpus]'` | Markdown parsing for conversion and index rebuilding |
| `pipx install '.[corpus,shell]'` | Both optional extras |

Use one installation command for the capabilities you want. When changing extras on an existing installation, add `--force` to that command. This replaces SOL's environment; it does not authorize overwriting an unrelated `sol` executable. Use `pipx reinstall sol-organizes-logic` after updating an existing source checkout.

The package supplies `sol`, `sol-kitty`, `sol-corpus`, and `sol-corpus-check`. For a fresh GitHub installation without a local checkout, `pipx install git+https://github.com/dialectmaterial/SOL.git` is also supported; configure a local corpus separately.

If you previously created a `~/.local/bin/sol` symlink, inspect it before installing:

~~~sh
readlink ~/.local/bin/sol
~~~

If its target is your previous SOL script, preserve that link under another name, then install:

~~~sh
mv -n ~/.local/bin/sol ~/.local/bin/sol-before-pipx
pipx install '.[shell]'
~~~

The rename preserves the old link and does not overwrite an existing backup. If the name is still occupied, inspect it before proceeding.

## Choose the text

The book is supplied locally; installing SOL does not download it or copy the private corpus into the package. A local pipx installation remembers the source checkout through installer metadata, so its `local-corpus` can be found from another directory. From a project containing the corpus, open the reader:

~~~sh
sol
~~~

If an older corpus lacks its permanent identity, initialize it explicitly before opening a persistent shell:

~~~sh
sol-corpus-check local-corpus --initialize-identity
~~~

This preserves the text and passage IDs. To read without initializing a workspace identity, use `sol -n` or `sol -r`. Select a different corpus for one invocation:

~~~sh
sol --corpus /absolute/path/to/SOL/local-corpus -r
~~~

For an installation from GitHub, or to choose a lasting default, save the corpus location once. SOL validates it and stores an absolute path:

~~~sh
sol --set-corpus /absolute/path/to/SOL/local-corpus
cd ~
sol -r
sol --info /being
sol --workspace reading --actor "Your name"
~~~

The setting lives in `$XDG_CONFIG_HOME/sol/config.json`, or `~/.config/sol/config.json` when that environment variable is unset. If you move the corpus, run `--set-corpus` again. After updating the installed code, use `pipx reinstall sol-organizes-logic` before checking it from home.

Discovery prefers `--corpus`, then the `SOL_CORPUS` environment variable, the working directory's `local-corpus`, the saved default, the source checkout remembered by a local pipx installation, and finally `local-corpus` in a recognized SOL source checkout. The checkout fallback validates the project's identity in `pyproject.toml`; it does not depend on the location of an individual Python file. A missing or stale selected corpus produces an actionable error rather than switching sources silently.

Ordinary reading never extracts a PDF. Renaming the PDF does not require reconverting an existing corpus. Its source fingerprint and permanent passage identifiers do not depend on the filename; the manifest retains the name used at import as historical provenance.

## Read, search, and inspect

~~~sh
sol
sol -r
sol -r --width 72
sol -n
sol --structure --depth 2
sol --read /being/i-determinateness-quality/existence
sol --first /being/i-determinateness-quality/being
sol --cat /concept/foreword
sol --search "ground" --within /essence --word --limit 8
sol --info /concept/iii-the-idea
sol guide
sol --shell
~~~

`--read` selects a random paragraph within a location. `--first` starts in book order, and `--cat` prints a complete virtual file. `--width` controls wrapping between 20 and 240 columns. Default output keeps the heading, path, source pages, and full identifier visible. Meaningful list and schema lines remain separate.

Search is literal and case insensitive. `--word` matches whole words rather than fragments; `--within` restricts the search to a subtree, and `--limit` bounds the displayed results.

Use `--passage ID` to return to a passage by its identifier or an unambiguous prefix. IDs remain permanent within their corpus; an independent initial conversion allocates its own IDs. Add `--context 2` to read neighboring paragraphs in book order, including across subdivision boundaries. Context accepts 0 to 10 passages on each side. `--info PATH` summarizes a location.

For other terminal tools, `--plain` prints passage text without decorative formatting or ANSI codes. `--json` supplies structured output:

~~~sh
sol --cat /concept/foreword --plain | less
sol --search "infinity" --within /being --json
~~~

With `--json`, a single passage is an object; search, complete file, and context results are arrays in book order. Context includes the selected passage. Each passage carries its identifier, path, text, page references, and review status. Corpus-backed passages also include a `canonical` record containing the Markdown, attribution, note links, and full source references. Their `corpus` metadata retains the import identity, edition, and source fingerprint. Scripts can inspect this information without parsing decorated output.

`guide` and `--guide` open a compact ASCII starting guide containing the project roadmap, the three doctrines, and commands to try. Its default depth is 1; `sol guide --depth 2` reveals more detail. Use `--depth` from 0 to 32 to control how much of an outline appears. For random JSON or plain text, name the action explicitly: `sol -r --json` or `sol -r --plain`.

Help, version information, and the guide remain available without a corpus. `--structure` can show an abbreviated outline until the text is configured. One-shot actions such as search, passage opening and inspection do not ask for a workspace or actor. With redirected input, a persistent shell needs both `--workspace NAME` and `--actor NAME`; missing labels cause an actionable error without consuming input. Use `-n`, `-r`, or a one-shot action for scripts that need no saved workspace.

## Work inside the virtual shell

Start with `sol`; `sol --shell` means the same persistent reader. The workspace picker shows up to ten recognized workspaces bound to the current corpus and source fingerprint, ordered by their latest recorded activity. Enter a displayed number to reopen one, or a name to create or select a workspace. Press Enter to choose the first displayed workspace; if none is available, the default is `reading`. The picker inspects candidates without modifying them and skips unrelated, incompatible, symlink, or WAL/sidecar-bearing files. A name entered explicitly still receives normal validation and can open a workspace omitted from suggestions rather than silently choosing another one.

Supplying `--workspace NAME` or `--actor NAME` skips only the corresponding question. `sol --workspace reading --actor "Your name"` skips both. `sol -n` and `sol -r` do not consult the workspace picker or actor registry. Paths accept lowercase names and omit numbering prefixes when the result is unambiguous. The basic input path can use Python's optional `readline` module for Tab completion.

With the shell extra installed, `--ui auto` uses the enhanced prompt in an interactive terminal. `--ui basic` selects basic input; `--ui prompt` requests the enhanced prompt when eligible and explains a missing extra. `--editing-mode vi` selects Vi editing instead of the Emacs default. Plain output, redirected streams and `TERM=dumb` retain basic input without importing prompt_toolkit. Enhanced command history stays in memory, not a separate history file.

~~~text
cd being
cd i-determinateness-quality
cd existence
ls
info
first
next
previous
context 1
where
up
cd -
~~~

`ls` lists the current location, `pwd` displays its path, and `tree [PATH] --depth N` shows descendants. `up` moves to the parent; `cd -` returns to the previous directory. Both `/` and `..` work.

`read` and `first` establish a reading selection. `next` and `previous` move within it. In a persistent workspace, browsing with `cd` preserves the selection and cursor. In the temporary `sol -n` shell, changing directories resets that selection; entering `cd .` or the current directory preserves it. Reaching its boundary does not jump elsewhere. `cat FILE` prints a complete file without moving the cursor.

Search the current subtree, then open a result and inspect its surroundings:

~~~text
cd /essence
search "ground" --word --limit 6
open 1
context 2
next
~~~

`search QUERY [PATH]` also accepts an explicit subtree. `open` accepts a full identifier, a unique prefix, or a result number from the latest search. `context [N]` defaults to one neighboring paragraph on each side, accepts 0 to 10, and leaves the cursor unchanged. `where` displays the current passage and its position within the reading selection.

Use `info [PATH]` for a location summary, `guide [PATH] --depth N` for a scoped guide, `help` for command syntax, and `exit` or `quit` to leave.

A useful comparison workflow is to search a term in one doctrine, inspect the surrounding prose, then repeat the search in another. Permanent identifiers let you record those observations and return to exactly the same passages.

## Keep a reading workspace

The default shell remembers an inquiry. Before its first use with an older corpus, explicitly initialize the corpus identity from the project directory, then select the workspace and actor:

~~~sh
sol-corpus-check local-corpus --initialize-identity
sol --workspace quantity-study --actor "Your name"
~~~

Initialization adds a permanent corpus UUID and updates its index metadata without changing Markdown, passage IDs, or the index text. It does not reconvert the PDF. Ordinary reading never performs this change automatically.

New conversions already include a corpus identity; this command retains it when present and initializes an older corpus once.

A workspace restores its saved passage and reading scope when reopened. Actor labels are remembered separately in `$XDG_DATA_HOME/sol/profiles.sqlite3`, or `~/.local/share/sol/profiles.sqlite3`. Accepting a new name during shell setup records that label locally. This is not authentication; existing notes retain their original author names. Browsing with `cd` does not erase the saved scope or cursor. `workspace history --limit 10` preserves earlier checkpoints as visits, not claims that a passage was understood. `resume REVISION` revisits a historical checkpoint as a new saved revision; it does not erase later history.

~~~text
first /being
bookmark add starting-point
note add "*Question:* What does this beginning presuppose?"
review show
review record inspected --issue "Inspected the canonical record; PDF comparison remains."
cd /essence
where
bookmark open starting-point
workspace history --limit 10
workspace check
~~~

Use `bookmark list`, `bookmark set NAME`, or `bookmark remove NAME` to inspect, deliberately replace, or remove a bookmark. Bookmarks target readable passages. `note list` shows personal annotations, not the edition's notes; `note show NOTE_ID` opens one. Annotation Markdown is stored and displayed literally. Notes target whole records, not selected words. `--on ID` can select an explicit record for a note or review instead of the current passage.

With the enhanced prompt, `note draft` opens a multiline personal note for the current record; `note draft --on ID` chooses another target. Enter inserts a line break, Ctrl-S saves, and Ctrl-C cancels. The target UUID and inspected text digest are captured before drafting, then checked again before one annotation is inserted. Cancelled drafts are discarded and draft bodies never enter command history. Basic input retains `note add "TEXT"`.

New workspaces use schema version 2, which retains a sequence of annotation snapshots. Use `note history NOTE_ID` to inspect them. `note edit NOTE_ID` opens the existing body in the enhanced multiline editor. In basic input, first inspect the note's current revision, then give an explicit expectation:

~~~text
note show NOTE_ID
note edit NOTE_ID "A revised question, retaining its original source binding." --expect-revision 1
note history NOTE_ID
~~~

Replace `NOTE_ID` with the identifier from `note list`. Only the note's original actor can edit it. Saving checks its revision and corpus generation again; a competing edit is refused, and saving an identical body adds no revision. Earlier bodies remain inspectable, while the original author, target, and inspected-source digest remain unchanged. Cancelling the editor changes neither notes nor reading position. This is local application-controlled revision history, not cryptographically tamper-proof evidence or authenticated identity.

Existing version-1 workspaces still open without migration and support reading and new annotations. To enable audited editing, explicitly create a separately named upgraded copy:

~~~sh
sol --workspace quantity-study --workspace-upgrade quantity-study-v2.sqlite3
sol --workspace quantity-study-v2 --workspace-dir . --actor "Your name"
~~~

Inside a shell, `workspace upgrade FILE.sqlite3` creates the same kind of copy but does not switch the running session. The destination parent must exist and the destination must not already exist. The original is left untouched. Legacy notes receive a baseline of their current body; SOL does not invent earlier edits or an editor attribution. New edits in the upgraded copy are audited from there onward.

Notes, comparisons, review decisions, and relations require the actor selected during setup or supplied with `--actor NAME`. Read-only one-shot workspace inspection needs no actor. Comparisons preserve an ordered set of record IDs and a question. Relations are directed, attributed assertions alongside the published tree. Their references point to live canonical records, not frozen quotations or captured endpoint versions:

~~~text
compare save inquiry ID_A ID_B --question "How do these determinations differ?"
compare show inquiry
relate add ID_A compares-with ID_B --reason "A connection to investigate, not an identity claim."
relate list
~~~

Replace `ID_A` and `ID_B` with displayed record UUIDs or unambiguous prefixes. `compare list`, `review list`, and `relate list` inspect saved work without moving the reading cursor. Review outcomes are `inspected`, `correction_needed`, and `verified`. A reader's `verified` testimony never changes canonical transcription status or random eligibility. The current review binding compares the inspected Markdown digest and declared PDF fingerprint, not every attribution or page-location field; workspace version 2 does not expand that binding. Matching fingerprints are not proof of a correct transcription. Missing and retired references remain visible rather than being matched by similar wording.

Resume or export outside the shell:

~~~sh
sol --workspace quantity-study --resume
sol --workspace quantity-study --resume --json
sol --workspace quantity-study --resume --resume-revision 1
sol --workspace quantity-study --workspace-check --json
sol --workspace quantity-study --workspace-backup quantity-study-backup.sqlite3
sol --workspace quantity-study --workspace-export > quantity-study.sol-workspace.json
sol --workspace quantity-study --workspace-export --export-format markdown > quantity-study.sol-workspace.md
~~~

Choose the historical revision from `workspace history`. Health checks report saved-reference issues without repairing them or verifying the source text. If canonical files change while SOL is open, saved-position and authored writes are refused until you reopen it, reindexing explicitly if needed. The generation guard checks the manifest, index and canonical Markdown, not PDF or facsimile image bytes.

Backup uses SQLite's online snapshot mechanism, verifies the result, and never overwrites an existing file. Its destination parent must already exist; new backups use mode `0600` on POSIX systems. To inspect the example backup with the same corpus selected, use `sol --workspace quantity-study-backup --workspace-dir . --resume`. This opens a separate workspace and leaves the original untouched. CLI backup and inspection still require a valid selected corpus. Automatic restore, import, and recovery without that corpus are not implemented.

Export defaults to JSON. `--export-format markdown` produces a readable inquiry report; add `--include-passages` to include current canonical Markdown for its referenced records. Inside the shell, use `workspace export --format markdown`. Both formats write only to standard output and change neither notes nor reading position. The report is derived, not a canonical book or backup, and retained annotation history never becomes invented historical source text. Keep the `.sol-workspace.json` or `.sol-workspace.md` suffix so personal exports remain excluded from Git and source archives. See [the inquiry report](WORKSPACE_EXPORT.md) for examples and provenance boundaries.

Each workspace is a separate local SQLite database under `$XDG_DATA_HOME/sol/workspaces`, or `~/.local/share/sol/workspaces`; `--workspace-dir DIRECTORY` selects another location. It is bound to the corpus UUID and source fingerprint, not merely the PDF filename or directory. A mismatched corpus is refused. The workspace does not edit or automatically synchronize the book. See [the workspace plan](WORKSPACE_PLAN.md) for implemented boundaries and next steps.

## Work through a source-review queue

Inspect pending canonical records without opening a workspace:

~~~sh
sol --review-queue --limit 10
sol --review-queue --within /being --limit 8 --json
sol --workspace quantity-study --review-queue --json
~~~

The unscoped queue includes flagged canonical records across all attribution roles, including edition notes and editorial material. `--within PATH` selects records with matching virtual reader paths; omit it to include records without one. `--limit` accepts 1 to 1000 and defaults to 20. A selected workspace adds reader testimony, but even a reader's `verified` outcome never hides a canonical pending flag. Inside the workspace shell, use `review queue --limit 10` or `review queue --within /being --limit 8`.

## Maintain and review the corpus

Canonical Markdown is the correction surface. The JSONL index is generated from it; see [the corpus contract](CORPUS.md) for the representation and validation rules.

With the corpus dependencies installed, rebuild after a correction:

~~~sh
sol-corpus index local-corpus
sol-corpus-check local-corpus --check
~~~

For an initial conversion, install Poppler and use the audited source PDF:

~~~sh
sudo apt install poppler-utils
sol-corpus convert --pdf Hegel-SOL.pdf
~~~

Conversion refuses to overwrite an existing corpus. Other editions require deliberate adaptation. The source is missing printed front matter pages l and lxix; these gaps are recorded explicitly.

Mathematical passages awaiting review remain available through ordered reading and direct opening, with a warning that also appears in search results. They are excluded from random quotations. Their Markdown records include source images. Source-review status is separate from random eligibility: a reviewed formula is not labelled unreviewed merely because it is excluded from random quotations.

Four useful places to begin checking are printed pages 209 to 210, PDF pages 282 to 283, on fractions and infinite series; printed pages 224 to 225, PDF pages 297 to 298, on Newton’s differential product; printed page 252, PDF page 325, on Lagrange, Kepler, and powers; and printed page 374, PDF page 447, on signs in Opposition.

Find the Newton passage by its text and location, rather than an identifier belonging to someone else's conversion:

~~~sh
sol --search "remarkable procedure of Newton" --within /BEING/ii-magnitude-quantity/2-quantum --limit 5
~~~

Copy the displayed identifier into `sol --passage ID --context 1`, replacing `ID` with that value. The target begins on printed page 224; its continuation reaches page 225. Compare the prose with its Markdown facsimile before correcting a symbol or exponent. Preserve the identifier, then rebuild the index. Mathematical display improvements should follow checked transcriptions.

[The OpenDataLoader investigation](research/OPENDATALOADER_RESEARCH.md) considers an isolated second extractor for difficult source passages. It is research only: the existing corpus was not reconverted, and no book content was uploaded. Candidate text or formula output would need human review before any canonical correction.

## Read in kitty and inspect the source

With kitty installed, `sol-kitty` opens SOL in its own reading profile. It uses the same workspace picker, actors, commands, and annotations as `sol`:

~~~sh
sol-kitty
sol-kitty -n
sol-kitty --workspace study --actor "Your name"
sol-kitty --source-pdf /absolute/path/to/Hegel-SOL.pdf
~~~

The profile belongs to this launch; it does not change your general kitty configuration. Ctrl-Shift-Left and Ctrl-Shift-Right move between reader and source panes; Ctrl-Shift-Plus and Ctrl-Shift-Minus change the font size. Ctrl-S save and Ctrl-C cancel remain available in annotation drafts. Newly displayed output adapts to the pane width unless `--width` is supplied.

After opening a passage, inspect its source:

~~~text
first /being
source show
source show PASSAGE_UUID
source close
~~~

Replace `PASSAGE_UUID` with a displayed identifier. The source pane shows the original PDF page with its printed label and passage identifier. `n` or Right selects the next contributing page; `p` or Left selects the previous one; `q` closes the pane. SOL uses the passage's exact listed pages, including references that are not consecutive. The source stays pinned when you navigate the reader; use `source show` again to refresh it.

Source viewing requires Poppler's `pdftoppm`. SOL verifies the actual local PDF against the corpus fingerprint before display. It can discover the source beside the corpus, accept `--source-pdf` or `SOL_SOURCE_PDF`, or remember a matching file under its fingerprint:

~~~text
source set-pdf /absolute/path/to/Hegel-SOL.pdf
source info
~~~

`--source-pdf` selects evidence for the canonical reader; `--pdf` still selects legacy PDF reading. A missing or mismatched evidence file produces a message without switching editions. Source viewing preserves reading position, notes, and review testimony. It does not mark a transcription as verified.

Verified PDF snapshots and rendered pages are disposable local cache files under `$XDG_CACHE_HOME/sol/source`, or `~/.cache/sol/source`. The remembered source mapping is separate from the corpus pointer, in `$XDG_CONFIG_HOME/sol/sources.json` or `~/.config/sol/sources.json`. Canonical Markdown remains the reading source.

## Development checks

Use a separate environment in the project directory. Editable installation exposes the current package and includes both optional extras for testing:

~~~sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e '.[corpus,shell]'
python3 -m sol guide
python3 -m unittest discover -s tests -v
~~~

Most tests use invented text. To include edition-specific PDF checks when you have the local source available, run `SOL_TEST_PDF=Hegel-SOL.pdf python3 -m unittest discover -s tests -v`. No test should require uploading the book or changing a personal workspace.

The [workspace plan](WORKSPACE_PLAN.md) separates implemented behavior from selected-span annotations and future imports. [Interface research](research/INTERFACE_RESEARCH.md) explains the optional prompt adapter and evaluates alternatives without making them dependencies.

### Code responsibilities

| Directory | Responsibility |
| --- | --- |
| `sol/reader/` | CLI, virtual shell, passage models, navigation, and presentation. Explicit PDF compatibility is isolated in the lazy-loaded `legacy_pdf.py`. |
| `sol/corpus/` | Edition structure and extraction layout, conversion, canonical record validation, and generated indexing. Ordinary reading uses the verified index. |
| `sol/workspace/` | SQLite storage, attribution profiles, reference operations, recent-workspace discovery, diagnostics, and inquiry export. |
| `sol/terminal/` | Optional prompt input, source-page viewing, and kitty launch integration. These adapters do not redefine corpus or workspace semantics. |

`sol/reader/app.py` coordinates commands; shared book and passage objects live in `sol/reader/models.py`. Edition-specific geometry and extraction helpers live in `sol/corpus/edition.py` and `sol/corpus/layout.py`, not the main command loop. The installed `sol` command and `python -m sol` use the same entry point.

## Appendix: Hegel on computational externality

The software's numerical and structural representations are tools for approaching the argument, not a claim to reproduce the Concept by calculation. The earlier README included this passage; it is retained here as philosophical context.

> "But the adequate concept is something higher; it properly denotes the agreement of the concept with reality, and this is not the concept as such but the idea."

> "What first led to this wayward attempt is above all the quantitative relation in which universality, particularity, and singularity are supposed to stand to one another: universal means, more extensive than particular and singular; and particular, more extensive than singular. The concept is concrete and the richest in determination, because it is the ground and the totality of the previous determinations, of the categories of being and the determinations of reflection; these, therefore, are certain also to come up in it. But its nature is totally misunderstood if such determinations are retained in it in their former abstraction – if the wider extent of the universal is understood to mean that the universal is a more, or a greater quantum, than the particular and the singular. As absolute ground, it is the possibility of quantity, but no less so of quality, that is, its determinations are no less qualitatively distinct; therefore they are already viewed in contravention to their truth when they are posited in the form of quantity alone. So, too, a reflective determination is a relative, something in which the opposite shines reflectively; unlike a quantum, its relation is not external. But the concept is more than all this; its determinations are determinate concepts, themselves essentially the totality of all determinations. It is, therefore, entirely inappropriate, in order to grasp such an inner totality, to want to apply numerical and spatial relations in which the terms fall apart; such relations are rather the last and the worst medium that could be used. Natural relations, as for instance “magnetism” or “color tonality” would make infinitely higher and truer symbols for the purpose. Since the human being has in language a means of designation that is appropriate to reason, it is otiose to look for a less perfect means of representation to bother oneself with. It is essentially only spirit that can grasp the concept as concept, for the latter is not just the property of spirit but its pure self. It is futile to want to fix it by means of spatial figures and algebraic signs for the sake of the outer eye and a non-conceptual, mechanical manipulation, such as a calculus. Also anything else that might be supposed to serve as symbol, like the symbols for the nature of God, can at best elicit only intimations and echoes of the concept; if, however, one insists on employing such symbols for expressing and cognizing the concept, then it is not their external nature which is fit for the task; the reverse relation applies, namely that what in the symbols is the echo of a higher determination is recognized to be such only by virtue of the concept, and it is only by shedding the sensuous standbys that were supposed to express it that one comes closer to the concept."

Hegel, *Science of Logic*, `/CONCEPT/i-subjectivity/1-the-concept/b-the-particular-concept/remark.txt`.
