# SOL: SOL Organizes Logic

## Hegel’s *Science of Logic* in the terminal

SOL is a reader and philosophical workspace for Hegel’s *Science of Logic*. Its name is a recursive acronym: **SOL Organizes Logic**.

The organizing concern is the Idea in Hegel’s technical sense: the articulation and development of logical determinations through Being, Essence, and Concept. SOL makes this movement accessible for reading and investigation. Its interfaces and classifications are instruments of inquiry, not substitutes for the argument.

> “The concept is concrete and the richest in determination”

> “It is essentially only spirit that can grasp the concept as concept”

Hegel, *Science of Logic*, “The particular concept,” Remark.

The book appears as a virtual filesystem rooted in `/BEING`, `/ESSENCE`, and `/CONCEPT`. Sections become directories; their introductory prose and terminal subdivisions become text files. These paths belong to the book, not your computer’s filesystem. SOL runs inside a terminal; its book shell is not Bash or Zsh.

Readable Markdown is the canonical text, with a generated JSONL index for the reader and other tools. Passages retain permanent identifiers, attribution, structural context, and printed and PDF page references. Ordinary reading does not extract the PDF again.

## Install

Python 3.10 or newer and [pipx](https://pipx.pypa.io/) are required.

~~~sh
git clone https://github.com/dialectmaterial/SOL.git
cd SOL
pipx install '.[shell]'
pipx ensurepath
~~~

Open a new terminal if `sol` is not yet on your path. The `shell` extra adds the optional enhanced prompt: completion, Emacs or Vi editing, and multiline annotation drafts. Use `pipx install .` for the standard-library reader and basic shell instead. Corpus conversion and index rebuilding use the separate `corpus` extra; see the [usage manual](docs/USAGE.md#install-with-pipx).

After updating a local checkout, refresh an existing installation with:

~~~sh
pipx reinstall sol-organizes-logic
~~~

In the kitty reading workspace, `compare PATH_A PATH_B` opens two complete files
with related personal notes. Tab completes paths; `a` / `b` selects the text to
scroll. `compare open` refreshes the last desk; `compare close` closes it.
See [the comparison desk](docs/USAGE.md#open-a-comparison-desk) for the workflow.

## Choose a local corpus

Installing SOL does not supply or download the book. Point it at an existing SOL corpus once:

~~~sh
sol --set-corpus /absolute/path/to/SOL/local-corpus
~~~

A local pipx installation can also discover `local-corpus` in its source checkout. The saved setting makes your chosen text explicit and works from any directory. If you only have the PDF, follow the [conversion instructions](docs/USAGE.md#maintain-and-review-the-corpus) before ordinary reading.

## Start reading

~~~sh
sol           # Open or create a workspace and choose an actor
sol -n        # Open a temporary shell without workspace or actor
sol -r        # Print one random passage
sol guide     # Show the beginner guide
~~~

An actor is your local attribution label, not a login account. A workspace remembers your reading position, bookmarks, notes, comparisons, review testimony, and relations between passages. Existing annotation bodies remain inspectable after an edit.

Try this inside the shell:

~~~text
cd /being
ls
first
bookmark add beginning
note add "What does this beginning presuppose?"
next
where
search "infinity" --word --limit 5
open 1
context 1
help
~~~

Bookmark and note commands require a workspace. Use `guide` for examples, `tree --depth 2` for the book’s structure, and `exit` to leave. With the enhanced prompt, `note draft` opens a multiline note: Ctrl-S saves and Ctrl-C cancels. Use `sol --ui basic` if you prefer basic input.

One-shot commands work without opening a workspace:

~~~sh
sol --structure --depth 2
sol --search "ground" --within /essence --word --limit 8
sol --passage ID --context 1
sol -r --plain
sol -r --json
~~~

Replace `ID` with an identifier displayed by your own corpus. Passage output shows its location and source pages; `--plain` and `--json` support pipelines and scripts.

## The three stages

SOL is being organized as one repository with independently selectable BEING, ESSENCE, and CONCEPT components. A shared CORE library is their foundation, not a fourth stage; the first internal API boundary is in place, while separate distributions remain future work. See the [modularity contract](docs/MODULARITY.md).

### BEING: reader and virtual shell

The present foundation is careful reading: a dependable corpus, clear navigation, continuity, attributed annotations, comparison, source review, and relations beyond the published tree. The reader should remain small enough to inspect and understand.

### ESSENCE: applications and experiments

Concordances, computational linguistics, classification, topic modeling, machine learning, and deep learning can investigate explicit and discovered organizations of the text. Every method should answer a research question and retain its connection to the passages that produced it. Terminal-host integration belongs here; the optional `sol-kitty` launcher and verified source-page viewer are documented in the [manual](docs/USAGE.md#read-in-kitty-and-inspect-the-source).

### CONCEPT: an operating system

The long-term ambition is a NixOS distribution with a distinctive philosophical and computational purpose. A useful reader and reproducible applications come first; a curated environment is the bridge toward the operating system.

## Documentation and development

~~~text
sol/            Application code
docs/           Manuals, contracts, and research
tests/          Regression tests
local-corpus/   Your local edition, excluded from Git
~~~

The [usage manual](docs/USAGE.md) covers navigation, configuration, workspace history, annotation editing, backup, export, and source viewing. The [corpus contract](docs/CORPUS.md) defines text, identifiers, provenance, and validation. The [workspace plan](docs/WORKSPACE_PLAN.md) separates implemented behavior from future work; [workspace export](docs/WORKSPACE_EXPORT.md) explains readable inquiry reports.

[Interface research](docs/research/INTERFACE_RESEARCH.md) and the [OpenDataLoader investigation](docs/research/OPENDATALOADER_RESEARCH.md) record options without making them reader dependencies.

From the checkout, run `python -m sol` to use the current source. See the [development checks](docs/USAGE.md#development-checks) for an isolated environment and the test suite.

For normal shell commands and pipes, use `sol-kitty --zsh`. It opens zsh in the
corpus directory. `sol read FILE --plain | less` reads canonical text;
`sol compare FILE_A FILE_B` opens a comparison and returns to zsh with `q`.
See [native shell usage](docs/USAGE.md#use-normal-zsh-commands).
