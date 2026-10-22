# SOL Organizes Logic

SOL is a recursive acronym that stands for SOL Organizes Logic. It is a reader and research workspace centered on Hegel’s *Science of Logic*. Its larger ambition is to become an encyclopedic system for studying how texts, concepts, and the Idea are organized, bringing philosophical science into conversation with computational linguistics, machine learning, deep learning and operating systems.

The organizing concern is the Idea in Hegel’s technical sense: the articulation and derivation of logical determinations through Being, Essence, and Concept. SOL makes this movement accessible for reading and investigation. The interfaces and classifications are the instruments which themselves are also subject to the inquiry.

SOL’s ambition is not only to investigate philosophical texts but also the computational organization of philosophical research. Therefore, a fully specified system environment
is a methodological requirement. Each inquiry conditions and revises the other, and whether computation can become adequate to the Idea remains a positedness iterated immanently through the project itself.

## The three divisions

SOL is one repository whose substantive modules are being organized under the logical divisions BEING, ESSENCE and CONCEPT. CORE is a separate service layer beneath them.

### BEING: the reading environment (Quality · Quantity · Measure)

The present foundation is careful reading: a dependable corpus, clear navigation, continuity and attributed personal work, in the immediate encounter with the text. The reader should remain small enough to inspect and understand.

### ESSENCE: computation and analysis (Reflection · Appearance · Actuality)

Computational linguistics, classification, concordances, statistics and, later, machine learning investigate explicit and discovered organizations of the text. Every method answers a research question, keeps its connection to the passages that produced it, and is itself an object of philosophical inquiry.

### CONCEPT: the integration of the inquiry (reserved)

CONCEPT is to integrate SOL's research activities and environment. Its scope is deliberately left open until active work requires it; one possible trajectory is a reproducible system environment, from Omarchy towards NixOS. A useful reader and reproducible applications come first.

### CORE: corpus and shared services

Corpus organization, retrieval, metadata, addressability and shared research state, serving the three divisions.

## Install and start

Python 3.10 or newer is required. From GitHub or an existing checkout:

```sh
git clone https://github.com/dialectmaterial/SOL.git
cd SOL
python3 scripts/install.py
sol
```

Already in the checkout? Start at `python3 scripts/install.py`; use `--check` to
inspect requirements without changes. The complete installer asks before native
system changes on Debian/Ubuntu, installs SOL through pipx, and supplies a private
verified Neovim when needed. On other systems, supply the reported native tools
with your package manager first. With those tools available, `pipx install .` or
`pipx install git+https://github.com/dialectmaterial/SOL.git` also works.

The single Neovim-backed reader runs in ordinary capable terminals; Kitty is not
required. First interactive launch asks for the exact supported Cambridge /
George di Giovanni PDF if no corpus exists, converts it locally once, then sets
up an actor and workspace. An existing corpus can be selected with
`sol --set-corpus /absolute/path/to/local-corpus`. The book is not bundled or
downloaded.

## Reading

`sol` (the same as `sol being`) resumes where you left off; `sol-window` opens the reader in a window of
its own, in a book face (Libertinus Mono) on SOL's Paper theme. Inside, `?`
shows every key and `sol guide` prints a compact introduction. The essentials:

| Keys | What they do |
| --- | --- |
| `j`/`k`, `b`/`n`, `p` | Read by line, by paragraph; one-paragraph mode |
| `t`, `gp 240` | The outline; go to a printed page |
| `/`, `Ctrl-N`/`Ctrl-P` | Search the whole book; step through every occurrence ("4 of 770") |
| `s`, `S` | The printed source as a crop; the whole page in Zathura, passage highlighted, following your reading |
| `a`, `c` | Write a note on the passage; see pages, footnotes, notes and markers beside the text |
| `m1`–`m3`, `M`/`L` | Quick markers; named places |
| `E` | ESSENCE beside the reader: word counts and every occurrence, TF-IDF, sentence lengths |
| `T` | Mocha, Latte, Paper, Night or your terminal's colours |
| `:q` | Save your exact position and leave |

`sol --shell` browses the book in a minimal command line that saves nothing;
`sol read FILE` prints a file, `sol reference` captures and checks references,
and `sol essence` runs the studies from the command line. Reader keys can be moved in `~/.config/sol/keys.json`, for example
`{"version": 1, "keys": {"n": "J"}}`.

## Documentation

Five documents govern SOL. [SPECULATIVE](docs/SPECULATIVE.md) leads: SOL as a computational investigation of philosophy and a philosophical investigation of computation, organized by the *Science of Logic*. The others describe the system in its terms and distinguish implemented behavior from decisions and proposals:

| Document | Scope |
| --- | --- |
| [SPECULATIVE](docs/SPECULATIVE.md) | Leading: aim, speculative method, logical divisions, agent reading protocol |
| [Architecture](docs/ARCHITECTURE.md) | Purpose, responsibilities and development direction |
| [BEING](docs/BEING.md) | Reader, presentation and scholarly workspace |
| [ESSENCE](docs/ESSENCE.md) | Implemented analyses and proposed research workflows |
| [CORE](docs/CORE.md) | Corpus, identity, provenance and interchange contracts |

This README is a gateway, not another design authority. See
[CONTRIBUTING](CONTRIBUTING.md) for development checks,
and [CHANGELOG](CHANGELOG.md) for changes; earlier documents are in Git history.

## License

SOL is free software under the [GNU General Public License, version 3 or
later](LICENSE) (`GPL-3.0-or-later`). The license covers SOL's code and
documentation, not the book: the corpus is the reader's own and is never part
of the repository.
