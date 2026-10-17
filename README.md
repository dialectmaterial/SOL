# SOL — SOL Organizes Logic

SOL is a recursive acronym that stands for SOL Organizes Logic. It is a reader and research workspace centered on Hegel’s *Science of Logic*. Its larger ambition is to become an encyclopedic system for studying how texts, concepts, and the Idea are organized, bringing philosophical science into conversation with computational linguistics, machine learning, deep learning and operating systems.

The organizing concern is the Idea in Hegel’s technical sense: the articulation and derivation of logical determinations through Being, Essence, and Concept. SOL makes this movement accessible for reading and investigation. The interfaces and classifications are the instruments which themselves are also subject to the inquiry.

SOL’s ambition is not only to investigate philosophical texts but also the computational organization of philosophical research. Therefore, a fully specified system environment
is a methodological requirement.

## The three stages

SOL is being organized as one repository with independently selectable BEING, ESSENCE, and CONCEPT components. A shared CORE library is their foundation.

### BEING: reader and workspace (determinate object)

The present foundation is careful reading: a dependable corpus, clear navigation, continuity, attributed annotations, comparison, source review, and relations beyond the published tree. The reader should remain small enough to inspect and understand.

### ESSENCE: applications and experiments (investigation of relations)

Computational linguistics, classification, concordances, topic modeling, machine learning, and deep learning can investigate explicit and discovered organizations of the text. Every method should answer a research question and retain its connection to the passages that produced it.

For model input, `sol analyze prose --json` exports prose separately from headings,
canonical ancestry, and source metadata. See the [prose input policy](docs/legacy/PROSE_INPUTS.md).

### CONCEPT: an operating system (organization of the inquiry)

The long-term ambition is a NixOS distribution with a distinctive philosophical and computational purpose. A useful reader and reproducible applications come first; a curated environment is the bridge toward the operating system. 

The necessity concerns systematic control of the research environment. The choice of NixOS is a technical judgment about how best to achieve it.

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
downloaded. Use `b/n` for paragraphs, `p` for reading mode, `?` for keys, and
`q` to save and leave; `sol guide` is a compact introduction.

## Documentation

These four documents distinguish implemented behavior from decisions and proposals:

| Document | Scope |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Purpose, responsibilities and development direction |
| [BEING](docs/BEING.md) | Reader, presentation and scholarly workspace |
| [ESSENCE](docs/ESSENCE.md) | Implemented analyses and proposed research workflows |
| [CORE](docs/CORE.md) | Corpus, identity, provenance and interchange contracts |

This README is a gateway, not another design authority. See
[CONTRIBUTING](CONTRIBUTING.md) for development checks,
[CHANGELOG](CHANGELOG.md) for changes, and the [legacy archive](docs/legacy/README.md)
for preserved earlier documentation and the original README.
