# SOL — SOL Organizes Logic

SOL is a terminal-native philosophical reading and research workspace centered
on Hegel's *Science of Logic*. Read, mark and question the text, investigate
patterns, and return to identifiable passages. The organizing concern is the
Idea in Hegel's technical sense, not a claim that statistical similarity proves
logical necessity.

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
