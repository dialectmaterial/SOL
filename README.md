# `sol` — Soul Organizes Logic

## Hegel's *Science of Logic* in the terminal

SOL reads a local, human-editable Markdown corpus through its generated JSONL
index. The corpus preserves book structure, paragraphs, emphasis, notes,
editorial material, bibliography, index, and source provenance. Ordinary reading
does not extract the PDF every time the program starts.

The default terminal view contains Hegel's main text, prefaces, introduction,
and Remarks under `/BEING`, `/ESSENCE`, and `/CONCEPT`. Editorial prose, notes,
and references remain in the complete corpus, but are not mixed into random
Hegel quotations. Ordered reading includes separately flagged formulas.

Each passage shows its virtual location, heading, book/PDF page range, and
permanent corpus UUID. Text wraps to the terminal width. The conversion is a
candidate transcription with an audit trail—not a claim that every paragraph,
italic span, note attribution, or mathematical expression has been proofread.

See [the corpus contract](CORPUS.md) for the complete format, correction workflow,
provenance, note relationships, and validation limits.

## Keep this edition's corpus private

The supplied Cambridge/di Giovanni translation is not licensed for public
redistribution. Keep its PDF, generated Markdown, JSONL, source crops, and
conversion cache local and excluded from Git. Publish SOL's code and synthetic
tests, not the copyrighted corpus. Your lawful access conditions still apply.

## One-time local conversion

Python 3.10 or newer is required. Conversion additionally needs Poppler's PDF
tools and `markdown-it-py`; reading an existing index uses only Python's standard
library and the accompanying SOL modules.

On Debian/Ubuntu, from the project directory:

```sh
sudo apt install poppler-utils
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-corpus.txt
python3 sol_corpus.py convert --pdf sources/georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf
```

If `local-corpus/` already exists, do not convert again. Edit its canonical
Markdown and rebuild the index instead:

```sh
python3 sol_corpus.py index local-corpus
python3 sol_corpus_contract.py local-corpus --check
```

The converter refuses to overwrite an existing corpus. It records source
coverage and review issues, including the supplied PDF's missing front-matter
printed pages **l** and **lxix**. Accounting for the available PDF is not proof
that it contains the complete published edition.

## Make `sol` available in the terminal

Keep the project files together. `sol.py` is the executable, but it is no longer
a self-contained single file: its corpus reader requires
`sol_corpus_contract.py` beside it. The converter's other helper modules must
also remain in the project directory.

Replace `/absolute/path/to/SOL/sol.py` below with your script's actual path:

```sh
chmod +x /absolute/path/to/SOL/sol.py
mkdir -p ~/.local/bin
ln -s /absolute/path/to/SOL/sol.py ~/.local/bin/sol
```

If that link already points to your script, leave it alone; edits update the
command too. Ensure `~/.local/bin` is in your `PATH`, then open a new terminal.
You can also use `python3 /absolute/path/to/SOL/sol.py` directly.

`sol` looks for `local-corpus/corpus.json` in the **current working directory**,
not beside the script. Run it from the project directory for flag-free reading.
From elsewhere, select the corpus explicitly:

```sh
sol --corpus /absolute/path/to/SOL/local-corpus
```

## Read and navigate

```sh
sol
sol --width 72
sol --structure
sol --read /being/i-determinateness-quality/existence
sol --first /being/i-determinateness-quality/being
sol --cat /concept/foreword
sol --shell
```

`--read` chooses a random prose paragraph within a directory or file. `--first`
starts at its first passage in book order. `--cat` prints a complete virtual
file in order. `--width` accepts 20–240 columns. Formula-only records are retained
for ordered reading but excluded from random quotation selection. A paragraph
mixing prose and uncertain mathematics remains a paragraph; when flagged
`random_eligible: false`, it stays in sequential reading and `cat` but is also
excluded from random quotations. Its source facsimile supports visual review.

An interactive example:

```text
sol:/$ cd being
sol:/BEING$ cd i-determinateness-quality
sol:/BEING/i-determinateness-quality$ cd existence
sol:/BEING/i-determinateness-quality/2-existence$ ls
sol:/BEING/i-determinateness-quality/2-existence$ first
sol:/BEING/i-determinateness-quality/2-existence$ next
sol:/BEING/i-determinateness-quality/2-existence$ previous
```

Sections, chapters, subdivisions, and Remarks are explicit virtual nodes.
Divisions with children are directories; their own prose appears as
`00-introduction.txt`. Leaf divisions are text files. These are navigation
paths, not a requirement to create a separate physical file for every heading.
The canonical Markdown retains the edition's fuller volume/shared-preface
hierarchy behind the three-doctrine convenience view.

The corpus paths follow the book's labels—for example `i-`, `1-`, and `a-`—rather
than the legacy reader's artificial `05-` and `02-` prefixes. Paths are
case-insensitive. Arabic-number and A–D prefixes and `.txt` may be omitted when
the remaining name is unambiguous: `existence` resolves to `2-existence`.
The examples retain Roman section prefixes as listed by `ls`. Tab completion
is available with Python's optional standard-library `readline` module.

| Shell command | Meaning |
| --- | --- |
| `ls [PATH]` | List a location. |
| `cd PATH` | Change location; `/` and `..` work. |
| `pwd` | Show the current virtual path. |
| `tree [PATH]` | Show a location and its descendants. |
| `read [PATH]` | Select a random prose passage and start a reading sequence. |
| `first [PATH]` | Start the selection in book order. |
| `next` | Read the next passage in the selection. |
| `previous` or `prev` | Read the previous passage. |
| `cat FILE` | Print the complete file in source order. |
| `help` | Show help. |
| `exit` or `quit` | Leave SOL. |

`read` and `first` establish the scope for `next` and `previous`. Changing
directory resets that selection. With no selection, `next` starts at the first
passage in the current directory; `previous` asks you to start first. Reaching
an end reports it without jumping elsewhere. `cat` leaves the cursor unchanged.

## Legacy PDF fallback

If the default local corpus has no manifest, SOL can still use the original
Cambridge PDF. It looks for this filename in the working directory, then in
its `sources/` subdirectory:

```text
georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf
```

Explicitly choose that mode with:

```sh
sol --pdf /absolute/path/to/file.pdf
```

`--pdf` and `--corpus` cannot be combined. A present but invalid/stale corpus
produces a correction/reindexing error; it never silently falls back to the PDF.
The legacy mode requires Poppler, has a less complete hierarchy, and omits the
footnote apparatus. Its page-based paragraph IDs are deterministic for that
extractor version but can change with extraction improvements. They are not the
permanent UUIDs embedded in canonical Markdown.

## Project layout and verification

| File | Responsibility |
| --- | --- |
| `sol.py` | CLI, reader model, virtual filesystem, wrapping, and legacy PDF fallback. |
| `sol_corpus.py` | One-time importer and indexing command. |
| `sol_corpus_contract.py` | Canonical records, CommonMark indexing, graph/provenance validation, and integrity checks. |
| `sol_corpus_structure.py` | Edition-specific structural anchors and hierarchy audit. |
| `sol_corpus_notes.py` | Footnote segmentation. |
| `sol_corpus_references.py` | Bibliography/index segmentation and column reading order. |
| `tests/` | Synthetic fixtures and optional checks against the local PDF. |

`load_corpus_book(corpus_path)` returns a `Book` with its tree and ordered
`Passage` records. The full JSONL includes additional canonical content categories
for scripts and classifiers, with attribution, parents, source spans, and links.

Run the synthetic tests:

```sh
python3 -m unittest discover -s tests -v
```

Source-specific tests can be enabled locally without putting book excerpts in
the test files:

```sh
SOL_TEST_PDF="$PWD/sources/georg_wilhelm_friedrich_hegel__the_science_of_logic.pdf" python3 -m unittest discover -s tests -v
```

Coverage, graph, and formatting tests are safeguards, not substitutes for human
proofreading. Complex mathematics remains flagged for visual review; inspect
the preserved source facsimile/PDF when its layout matters. Corrections can retain
retired UUIDs as `retired_record` tombstones with redirects rather than silently
reusing or deleting their identities. Exclude tombstones from classifier text.

## Future packaging

A later `pyproject.toml` can package these modules and expose
`sol = "sol:main"` as a console-script entry. The copyrighted corpus must not be
bundled without redistribution rights. Search, annotations, and evaluated
classification should build on the stable corpus contract before expanding the
shell or operating-system ambitions.
