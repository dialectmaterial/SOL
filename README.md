# SOL: SOL Organizes Logic

## Hegel’s *Science of Logic* in the terminal

SOL stands for SOL Organizes Logic, a recursive acronym in the style of GNU. The project is a reader and virtual shell for Hegel’s *Science of Logic*. Its larger ambition is an environment for investigating how texts, concepts, and knowledge are organized, connecting philosophy with computational linguistics, machine learning, and operating systems.

The reader uses readable Markdown and a generated JSONL index. Each passage retains its permanent identifier, location, attribution, printed pages, and PDF pages. Ordinary reading does not extract the PDF again.

The shell presents the book through `/BEING`, `/ESSENCE`, and `/CONCEPT`. Sections and subdivisions become directories; their own introductory prose appears as `00-introduction.txt`. Divisions without children become virtual text files. The canonical corpus preserves the fuller volume hierarchy, editorial material, notes, bibliography, and index.

## Install with pipx

Python 3.10 or newer is required. From your project directory, install SOL into its own environment:

~~~sh
pipx install .
pipx ensurepath
sol --version
~~~

If pipx is not installed, Debian and Ubuntu users can install it with `sudo apt install pipx`. After `ensurepath`, open a new terminal if necessary.

The reader uses Python’s standard library. To include the Markdown parser for conversion and index rebuilding, install the optional corpus dependencies instead:

~~~sh
pipx install '.[corpus]'
~~~

An existing installation can be refreshed with `pipx reinstall sol-organizes-logic`. The package supplies three commands: `sol`, `sol-corpus`, and `sol-corpus-check`.

If you previously created a `~/.local/bin/sol` symlink, inspect it before installing:

~~~sh
readlink ~/.local/bin/sol
~~~

If its target is your previous SOL script, preserve that link under another name, then install:

~~~sh
mv -n ~/.local/bin/sol ~/.local/bin/sol-before-pipx
pipx install '.[corpus]'
~~~

The rename preserves the old link and does not overwrite an existing backup. If the name is still occupied, inspect it before proceeding.

After this release has been pushed to GitHub, installation directly from the repository will also work:

~~~sh
pipx install git+https://github.com/dialectmaterial/SOL.git
~~~

## Choose the text

SOL looks for `local-corpus/corpus.json` in the working directory. From the project directory, simply run:

~~~sh
sol
~~~

From elsewhere, select your corpus:

~~~sh
sol --corpus /absolute/path/to/SOL/local-corpus
~~~

When no default corpus exists, SOL looks for `georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf` in the working directory, then in `sources/`. You can select a PDF with `--pdf PATH`. PDF extraction requires Poppler, and its reader has a less complete hierarchy and different identifiers.

An existing invalid or stale corpus produces an actionable error. `--corpus` and `--pdf` cannot be combined.

## Read, search, and inspect

~~~sh
sol
sol --width 72
sol --structure --depth 2
sol --read /being/i-determinateness-quality/existence
sol --first /being/i-determinateness-quality/being
sol --cat /concept/foreword
sol --search "ground" --within /essence --word --limit 8
sol --info /concept/iii-the-idea
sol visual-help
sol --shell
~~~

`--read` selects a random paragraph within a location. `--first` starts in book order, and `--cat` prints a complete virtual file. `--width` controls wrapping between 20 and 240 columns. Default output keeps the heading, path, source pages, and full identifier visible. Meaningful list and schema lines remain separate.

Search is literal and case insensitive. `--word` matches whole words rather than fragments; `--within` restricts the search to a subtree, and `--limit` bounds the displayed results.

Use `--passage ID` to return to a passage by its identifier or an unambiguous prefix. Add `--context 2` to read neighboring paragraphs in book order, including across subdivision boundaries. Context accepts 0 to 10 passages on each side. `--info PATH` summarizes a location.

For other terminal tools, `--plain` prints passage text without decorative formatting or ANSI codes. `--json` supplies structured output:

~~~sh
sol --cat /concept/foreword --plain | less
sol --search "infinity" --within /being --json
~~~

With `--json`, a single passage is an object; search, complete file, and context results are arrays in book order. Context includes the selected passage. Each passage carries its identifier, path, text, page references, and review status.

`visual-help` and `--visual-help` open an ASCII guide containing the project roadmap, book outline, and navigation examples. Use `--depth` from 0 to 32 to control how much of an outline appears.

## Work inside the virtual shell

Start with `sol --shell`. Paths accept lowercase names and omit numbering prefixes when the result is unambiguous. Tab completion is available through Python’s optional `readline` module.

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

`read` and `first` establish a reading selection. `next` and `previous` move within it; changing directory resets that selection. Reaching its boundary does not jump elsewhere. `cat FILE` prints a complete file without moving the cursor.

Search the current subtree, then open a result and inspect its surroundings:

~~~text
cd /essence
search "ground" --word --limit 6
open 1
context 2
next
~~~

`search QUERY [PATH]` also accepts an explicit subtree. `open` accepts a full identifier, a unique prefix, or a result number from the latest search. `context [N]` defaults to one neighboring paragraph on each side, accepts 0 to 10, and leaves the cursor unchanged. `where` displays the current passage and its position within the reading selection.

Use `info [PATH]` for a location summary, `visual-help [PATH] --depth N` for a scoped guide, `help` for command syntax, and `exit` or `quit` to leave.

A useful comparison workflow is to search a term in one doctrine, inspect the surrounding prose, then repeat the search in another. Permanent identifiers let you record those observations and return to exactly the same passages.

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
sol-corpus convert --pdf sources/georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf
~~~

Conversion refuses to overwrite an existing corpus. Other editions require deliberate adaptation. The source is missing printed front matter pages l and lxix; these gaps are recorded explicitly.

Mathematical passages awaiting review remain available through ordered reading and direct opening, with a warning. They are excluded from random quotations. Their Markdown records include source images.

Four useful places to begin checking are printed pages 209 to 210, PDF pages 282 to 283, on fractions and infinite series; printed pages 224 to 225, PDF pages 297 to 298, on Newton’s differential product; printed page 252, PDF page 325, on Lagrange, Kepler, and powers; and printed page 374, PDF page 447, on signs in Opposition.

For the Newton passage:

~~~sh
sol --passage acb6db0e-f9af-4e5f-8053-913bc542ad0b --context 1
~~~

Compare the prose with its Markdown facsimile before correcting a symbol or exponent. Preserve the identifier, then rebuild the index. Mathematical display improvements should follow checked transcriptions.

For development checks, use a separate environment in the project directory:

~~~sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-corpus.txt
python3 -m unittest discover -s tests -v
~~~

## Where SOL is going

The roadmap follows the three doctrines as a way of organizing development.

### BEING: the reader and virtual shell

The current focus is SOL as a command line application: random quotations, careful formatting, reading, search, and a virtual terminal interface for navigating the book.

Next come saved reading sequences, bookmarks, annotations, and richer links between passages. Permanent identifiers provide their foundation. Exact textual searches should remain distinguishable from any future conceptual search.

This stage should make reading more productive while keeping the corpus inspectable and the interface small enough to understand and modify.

### ESSENCE: applications and experiments

SOL can become a text laboratory through concordances, word frequencies, vocabulary comparisons, and recurring expressions. Classification, topic modeling, machine learning, and deep learning can follow clear research questions.

Can a model recover Being, Essence, or Concept from a paragraph? What organization emerges when chapter labels are withheld? Where do statistical similarities cross Hegel’s explicit divisions?

Each experiment should record its corpus version, preprocessing, settings, and evaluation. The results support interpretation and comparison. They should remain connected to the passages and questions that produced them.

An actual terminal emulator, or a modification of an existing one, belongs here once the reading and research workflows clarify what it needs to provide.

### CONCEPT: an operating system

The longer ambition is a NixOS distribution, with Hyprland as a possible desktop foundation, bringing the reader and selected applications into a coherent environment.

A reproducible development environment is the bridge: first a useful application, then a curated collection of tools, and eventually an operating system with a distinctive purpose.

For now, development stays with BEING. Each improvement should provide a usable result and an opportunity to learn the systems beneath it.
