# SOL: SOL Organizes Logic

## Hegel’s *Science of Logic* in the terminal

SOL is a recursive acronym that stands for SOL Organizes Logic. It is a reader and workspace for Hegel’s *Science of Logic*. Its larger ambition is to become an encyclopedic system for studying how texts, concepts, and the Idea are organized, bringing philosophical science into conversation with computational linguistics, machine learning, deep learning and operating systems.

The organizing concern is the Idea in Hegel’s technical sense: the articulation and derivation of logical determinations through Being, Essence, and Concept. SOL makes this movement accessible for reading and investigation. The interfaces and classifications are the instruments which themselves are also subject to the inquiry.

SOL’s ambition is not only to investigate philosophical texts but also the computational organization of philosophical research. Therefore, a fully specified system environment
is a methodological requirement.

The book appears as a virtual filesystem rooted in `/BEING`, `/ESSENCE`, and `/CONCEPT`. Sections become directories; their introductory prose and terminal subdivisions become text files. These paths belong to the book, not your computer’s filesystem. SOL runs inside a terminal; its book shell is not Bash or Zsh.

Readable Markdown is the canonical text, with a generated JSONL index for the reader and other tools. Passages retain permanent identifiers, attribution, structural context, and printed and PDF page references.

## Install

Python 3.10 or newer is required. From a checkout, the complete installer checks
native tools, installs missing Debian/Ubuntu packages after asking permission,
and installs SOL and all its Python feature dependencies through pipx:

~~~sh
git clone https://github.com/dialectmaterial/SOL.git
cd SOL
python3 scripts/install.py
~~~

Open a new terminal if `sol` is not yet on your path, then run `sol`. The installer
reuses a suitable Neovim or installs a checksum-verified private copy without
changing personal editor settings. Kitty tools are included in the complete
setup, but reading never requires using Kitty. On other operating systems,
provide the reported native tools with your package manager first. Use
`python3 scripts/install.py --check` to inspect requirements without changes.
The reader works in ordinary capable terminal emulators, not one preferred host.

After updating a local checkout, refresh an existing installation with:

~~~sh
python3 scripts/install.py
~~~

## Choose a local corpus

On first launch, if no corpus is configured, SOL welcomes you and asks for the
PDF's location. It imports the supported Cambridge / George di Giovanni source
once, validates the resulting Markdown and index, and remembers their location.
The current importer supports the exact audited source PDF, not arbitrary
editions, scans or re-encoded copies; unsupported files receive an explanation
without creating a corpus. The converted book stays in your SOL user-data
directory, separately from the installation. Importing is not full proofreading.

If you already have a prepared corpus, select it once:

~~~sh
sol --set-corpus /absolute/path/to/local-corpus
~~~

The setting stores the corpus location in your user configuration and works from
any working directory. It does not copy or regenerate an existing corpus.
`--set-corpus` accepts an indexed directory, not a PDF. Manual conversion and
review remain documented in the [corpus guide](docs/CORPUS.md#create-inspect-and-index).
Normal reading never extracts the PDF again.

## Start reading

~~~sh
sol                       # Open the reader and resume the remembered workspace
sol --actor "Your name"   # Open that actor's most recently used workspace
sol -n                    # Read without a workspace or actor
sol -r                    # Print one random passage
sol guide                 # Show the beginner's guide
~~~

On first use, SOL asks for an actor and a workspace if none has been selected. An actor is a local attribution label, not a login account. A workspace remembers reading position and supports bookmarks, annotations, comparisons, source review, and relations between passages.

SOL has one reader, powered by Neovim with a private configuration. Use `j/k` for
displayed lines, `b/n` for previous/next paragraphs, and `p` to switch between
continuous and one-paragraph reading. `/` searches the whole book, `m1`–`m3` place
three book markers, `y` copies text, `t` opens the outline, and `c` shows context
and markers. `?` shows the keys; `q` saves and leaves. The same reader runs in
Alacritty, Kitty and other capable terminals. See the [reader guide](docs/READER_VIEW.md).

One-shot commands work without opening the reader:

~~~sh
sol --structure --depth 2
sol --search "ground" --within /essence --word --limit 8
sol --passage ID --context 1
sol -r --plain
sol -r --json
~~~

Replace `ID` with an identifier displayed by your corpus. Passage output includes its location and source pages; `--plain` and `--json` support scripts and pipelines.

## The three stages

SOL is being organized as one repository with independently selectable BEING, ESSENCE, and CONCEPT components. A shared CORE library is their foundation, not a fourth stage; the first internal API boundary is in place, while separate distributions remain future work. See the [modularity contract](docs/MODULARITY.md).

### BEING: reader and workspace (determinate object)

The present foundation is careful reading: a dependable corpus, clear navigation, continuity, attributed annotations, comparison, source review, and relations beyond the published tree. The reader should remain small enough to inspect and understand.

### ESSENCE: applications and experiments (investigation of relations)

Computational linguistics, classification, concordances, topic modeling, machine learning, and deep learning can investigate explicit and discovered organizations of the text. Every method should answer a research question and retain its connection to the passages that produced it. Terminal-host integration belongs here; the optional `sol-kitty` launcher and verified source-page viewer are documented in the [manual](docs/USAGE.md#read-in-kitty-and-inspect-the-source).

For model input, `sol analyze prose --json` exports prose separately from headings,
canonical ancestry, and source metadata. See the [prose input policy](docs/PROSE_INPUTS.md).

### CONCEPT: an operating system (organization of the inquiry)

The long-term ambition is a NixOS distribution with a distinctive philosophical and computational purpose. A useful reader and reproducible applications come first; a curated environment is the bridge toward the operating system. 

The necessity concerns systematic control of the research environment. The choice of NixOS is a technical judgment about how best to achieve it.

## The optional book shell

The book shell offers path-based navigation through the three doctrines. Its paths describe the book and are not real directories on your computer. Open it with `sol --shell`:

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

Bookmark and note commands require a workspace. Use `tree --depth 2` to inspect the book's structure and `exit` to leave. The optional enhanced prompt supports completion, Vi or Emacs editing, and multiline annotation drafts. Use `sol --shell --ui basic` for basic command input.

Manage local workspaces without opening the reader:

~~~sh
sol --workspace-list
sol --workspace-delete NAME
~~~

Close the workspace in every SOL window before deleting it. Deletion removes the named workspace from normal use and retains its database in a private `.trash` archive. The command reports the recovery path. Actor profiles and the corpus are retained. See [workspace management](docs/USAGE.md#list-or-remove-a-workspace).

## Documentation and development

~~~text
sol/            Application code
docs/           Manuals, contracts, and research
tests/          Regression tests
local-corpus/   Your local edition, excluded from Git
~~~

The [usage manual](docs/USAGE.md) covers navigation, configuration, workspaces, annotations, backup, export, and source viewing. The [corpus contract](docs/CORPUS.md) documents the canonical text, identifiers, provenance, and validation. The [workspace plan](docs/WORKSPACE_PLAN.md) separates current behavior from future work, and [workspace export](docs/WORKSPACE_EXPORT.md) explains readable inquiry reports.

[Interface research](docs/research/INTERFACE_RESEARCH.md) and the [OpenDataLoader investigation](docs/research/OPENDATALOADER_RESEARCH.md) document options for later development.

From the checkout, run `python -m sol` to use the current source. The [development checks](docs/USAGE.md#development-checks) describe the isolated environment and test suite.

For ordinary shell commands and pipes, use `sol-kitty --zsh`. It opens zsh in the corpus directory. For example, `sol read FILE --plain | less` reads canonical text and `sol compare FILE_A FILE_B` opens a comparison, returning to zsh when you press `q`. See [native shell usage](docs/USAGE.md#use-normal-zsh-commands).
