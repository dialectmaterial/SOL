# SOL: Sol Organizes Logic

## Hegel’s *Science of Logic* in the terminal

SOL begins with a reader for Hegel’s *Science of Logic*. Its larger ambition is to become an environment for studying how texts, concepts, and knowledge are organized, bringing philosophy into conversation with computational linguistics, machine learning, and operating systems.

The reader uses a human editable Markdown corpus and a generated JSONL index. Ordinary reading does not extract the PDF every time SOL starts. The corpus preserves the book’s structure, paragraph boundaries, emphasis, notes, editorial material, bibliography, index, and source references.

The terminal presents Hegel’s text through three roots: `/BEING`, `/ESSENCE`, and `/CONCEPT`. Editorial prose, notes, and references remain available in the complete corpus but are kept separate from random Hegel quotations.

Each passage displays its location, heading, printed and PDF page references, and permanent identifier. Text wraps to fit the terminal. The transcription remains reviewable, particularly where mathematical notation or note attribution needs attention.

See [the corpus contract](CORPUS.md) for the format, indexing rules, and correction workflow.

## Getting started

Python 3.10 or newer is required. Reading an existing corpus uses Python’s standard library and the accompanying SOL modules.

Keep the project files together. The executable is `sol.py`, but its corpus reader also needs `sol_corpus_contract.py`. The conversion helpers should remain alongside them.

To make `sol` available in the terminal, replace the example path with your project’s actual location:

```sh
chmod +x /absolute/path/to/SOL/sol.py
mkdir -p ~/.local/bin
ln -s /absolute/path/to/SOL/sol.py ~/.local/bin/sol
```

If that link already points to your script, leave it unchanged. Ensure `~/.local/bin` is in your `PATH`.

SOL looks for `local-corpus/corpus.json` in the current working directory. Run it from the project directory to read without supplying a flag:

```sh
sol
```

From another directory, select the corpus explicitly:

```sh
sol --corpus /absolute/path/to/SOL/local-corpus
```

You can also run `python3 sol.py` directly from the project directory.

## Preparing and maintaining the corpus

Conversion requires Poppler’s PDF tools and `markdown-it-py`. Rebuilding the index requires the Markdown parser but does not need to extract the PDF again.

On Debian or Ubuntu, run these commands from the project directory:

```sh
sudo apt install poppler-utils python3-venv
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-corpus.txt
python3 sol_corpus.py convert --pdf sources/georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf
```

The importer is tied to the specifically audited source PDF. Other editions or files need deliberate adaptation.

If `local-corpus/` already exists, do not convert it again. Make corrections in its canonical Markdown, then rebuild and validate:

```sh
python3 sol_corpus.py index local-corpus
python3 sol_corpus_contract.py local-corpus --check
```

The converter refuses to overwrite an existing corpus. Permanent identifiers must survive corrections so that references, annotations, and experiments remain meaningful.

The source PDF is missing printed front matter pages **l** and **lxix**. These gaps are recorded explicitly rather than filled with invented text. Complex mathematical passages retain source images for review.

## Reading and navigation

```sh
sol
sol --width 72
sol --structure
sol --read /being/i-determinateness-quality/existence
sol --first /being/i-determinateness-quality/being
sol --cat /concept/foreword
sol --shell
```

`--read` selects a random paragraph within a location. `--first` begins in book order. `--cat` prints a complete virtual file. `--width` accepts values between 20 and 240 columns.

Some paragraphs containing uncertain mathematics are excluded from random quotations but remain available through ordered reading. Their source images support checking the transcription.

The interactive reader treats the book as a virtual filesystem:

```text
sol:/$ cd being
sol:/BEING$ cd i-determinateness-quality
sol:/BEING/i-determinateness-quality$ cd existence
sol:/BEING/i-determinateness-quality/2-existence$ ls
sol:/BEING/i-determinateness-quality/2-existence$ first
sol:/BEING/i-determinateness-quality/2-existence$ next
sol:/BEING/i-determinateness-quality/2-existence$ previous
```

Sections, chapters, subdivisions, and Remarks appear as explicit nodes. Divisions containing other divisions are directories. Their introductory prose appears as `00-introduction.txt`; divisions without children become text files.

These paths organize navigation. They do not require a separate physical file for every heading. The canonical corpus preserves the fuller volume and preface hierarchy behind the three doctrine view.

Paths are insensitive to case. Numbered, lettered, Roman, and Greek prefixes can be omitted when the result is unambiguous. For example, `existence` resolves to `2-existence`.

Inside the reader, `ls` lists a location, `cd` changes it, `pwd` shows the current path, and `tree` displays its descendants. Both `/` and `..` work.

`read` begins with a random passage; `first` begins in source order. Both establish a selection for `next` and `previous`. Changing directory resets that selection. Reaching its end does not jump elsewhere.

`cat` prints a complete file without moving the reading cursor. Use `help` for guidance and `exit` or `quit` to leave. Tab completion is available through Python’s optional `readline` module.

## PDF fallback

When no default corpus manifest exists, SOL can read the original PDF. It looks in the working directory, then in `sources/`, for:

```text
georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf
```

You can select a PDF explicitly:

```sh
sol --pdf /absolute/path/to/file.pdf
```

The PDF reader requires Poppler and has a less complete hierarchy and note apparatus. Its identifiers are not the permanent corpus UUIDs.

`--pdf` and `--corpus` cannot be combined. An existing but invalid corpus produces an error rather than silently switching to PDF extraction.

## Project organization and verification

`sol.py` contains the reader, command interface, virtual filesystem, text wrapping, and PDF fallback.

`sol_corpus.py` provides conversion and indexing. `sol_corpus_contract.py` defines canonical records, Markdown parsing, validation, and integrity checks.

`sol_corpus_structure.py`, `sol_corpus_notes.py`, and `sol_corpus_references.py` handle the source hierarchy, footnotes, bibliography, and index.

The generated JSONL exposes text, identifiers, attribution, parent relationships, and source references for scripts, classifiers, and agents.

After installing the corpus dependencies, run the tests:

```sh
python3 -m unittest discover -s tests -v
```

To include checks against the source PDF:

```sh
SOL_TEST_PDF="$PWD/sources/georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf" python3 -m unittest discover -s tests -v
```

Validation supports proofreading; it does not replace it. When records need to be merged or retired, their identifiers can remain as tombstones with redirects. Classifiers should exclude those historical records from their input text.

## Future packaging and direction

SOL should develop gradually, with each stage providing something useful and understandable before the next begins. The following are directions for development, not features already implemented.

### A research reader

The next step is searching, bookmarks, annotations, and convenient passage references built on the existing permanent identifiers.

A command such as `search "ground"` could return passages with their locations and page references. Exact word searches, searches for recurring expressions, and conceptual searches should remain distinguishable. A semantic match should explain how it was found rather than presenting similarity as certainty.

Annotations could connect passages without modifying the underlying transcription. Reading sequences and saved selections could make an interpretation reproducible and shareable.

### An experimental text laboratory

Begin with transparent measurements: word frequencies, concordances, vocabulary differences between doctrines, and recurring expressions. Then introduce classification, clustering, and topic modeling.

Each method should answer a research question. Three questions provide a useful foundation:

1. **Can a model recover the book’s explicit organization?** Predicting Being, Essence, or Concept from a paragraph introduces supervised classification and evaluation.

2. **What organization does a model discover independently?** Clustering passages without chapter labels introduces unsupervised learning and the interpretation of discovered patterns.

3. **Where do learned patterns depart from Hegel’s organization?** Comparing similar vocabulary across distant divisions brings statistical relationships into conversation with philosophical structure.

Experiments should record their corpus version, preprocessing, settings, and evaluation procedure. Statistical similarity is evidence to investigate, not a substitute for interpreting Hegel’s argument.

### A reproducible environment

Once the reader and experiments are useful, their dependencies and configuration should become reproducible.

Python packaging can provide a `pyproject.toml`, optional dependencies for conversion and analysis, and a console entry such as `sol = "sol:main"`. Installation should become straightforward without coupling every reader to every experimental tool.

A Nix development environment could then bring the reader, corpus tools, and selected research workflows together. From there, SOL could grow into a curated environment and eventually a NixOS distribution with a distinctive purpose: organizing and investigating knowledge.

The terminal interface may develop into a richer shell for navigating texts and running experiments. An adapted terminal emulator could follow if those workflows genuinely benefit from it.

SOL's ambition is to connect existing tools through an increasingly coherent environment, while keeping its methods inspectable and its development an opportunity to learn.
