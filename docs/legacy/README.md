# Historical documentation archive

Archived 17 October 2026 from commit `1d200e4fcbff1ca69f48b5dc96c55765f215f303`.
These documents are historical and superseded; their commands, hypotheses and
feature claims are not current instructions. The only long-form design authorities
are [Architecture](../ARCHITECTURE.md), [BEING](../BEING.md),
[ESSENCE](../ESSENCE.md) and [CORE](../CORE.md).

## Path mapping

| Original path | Preserved archive |
| --- | --- |
| `README.md` | [root/README.md](root/README.md) |
| `CONTRIBUTING.md` | [root/CONTRIBUTING.md](root/CONTRIBUTING.md) |
| `CHANGELOG.md` | [root/CHANGELOG.md](root/CHANGELOG.md) |
| `docs/CORPUS.md` | [CORPUS.md](CORPUS.md) |
| `docs/EXTRACTION.md` | [EXTRACTION.md](EXTRACTION.md) |
| `docs/HANDOFF.md` | [HANDOFF.md](HANDOFF.md) |
| `docs/MODULARITY.md` | [MODULARITY.md](MODULARITY.md) |
| `docs/NEOVIM_READER.md` | [NEOVIM_READER.md](NEOVIM_READER.md) |
| `docs/PROSE_INPUTS.md` | [PROSE_INPUTS.md](PROSE_INPUTS.md) |
| `docs/READER_ACCEPTANCE.md` | [READER_ACCEPTANCE.md](READER_ACCEPTANCE.md) |
| `docs/READER_ACTIONS.md` | [READER_ACTIONS.md](READER_ACTIONS.md) |
| `docs/READER_VIEW.md` | [READER_VIEW.md](READER_VIEW.md) |
| `docs/REFERENCE_PROTOCOL.md` | [REFERENCE_PROTOCOL.md](REFERENCE_PROTOCOL.md) |
| `docs/TERM_STUDY.md` | [TERM_STUDY.md](TERM_STUDY.md) |
| `docs/USAGE.md` | [USAGE.md](USAGE.md) |
| `docs/WORKSPACE_EXPORT.md` | [WORKSPACE_EXPORT.md](WORKSPACE_EXPORT.md) |
| `docs/WORKSPACE_PLAN.md` | [WORKSPACE_PLAN.md](WORKSPACE_PLAN.md) |
| `docs/research/INTERFACE_RESEARCH.md` | [research/INTERFACE_RESEARCH.md](research/INTERFACE_RESEARCH.md) |
| `docs/research/NEOVIM_READER.md` | [research/NEOVIM_READER.md](research/NEOVIM_READER.md) |
| `docs/research/OPENDATALOADER_RESEARCH.md` | [research/OPENDATALOADER_RESEARCH.md](research/OPENDATALOADER_RESEARCH.md) |
| `docs/research/READER_ENGINES.md` | [research/READER_ENGINES.md](research/READER_ENGINES.md) |
| `docs/research/READER_SURFACES.md` | [research/READER_SURFACES.md](research/READER_SURFACES.md) |
| `docs/research/READING_TRIAL.md` | [research/READING_TRIAL.md](research/READING_TRIAL.md) |

## Preservation and operational exceptions

All 20 old documentation pages were moved, including the six research pages;
no documentation assets were present to move. Original filenames and research
nesting are retained. Eighteen pages are byte-exact. Only `USAGE.md` and
`READER_ACTIONS.md` have link-destination repairs back to the frozen root copies;
their prose and commands are unchanged. The [integrity inventory](inventory.json)
records original SHA-256 hashes and every reversible destination rewrite.

The three `root/` snapshots are byte-for-byte copies, including the original
README. Eleven tiny link-only files under `root/docs/` preserve the snapshots'
original relative links and requested anchors without modifying those snapshots.
These redirects contain no competing guidance. No symlinks are used.

Root `README.md` remains a short GitHub/package gateway. `CONTRIBUTING.md` retains
test instructions, ownership pointers and the authorized commit/push procedure;
`CHANGELOG.md` remains a chronological change log with obsolete feature descriptions
in its archived copy. These operational files are not additional design authorities.
Package manifests, CI, code, fixtures, tool metadata and any license stay in their
operational locations. There are no compatibility stubs at the old `docs/*.md`
paths: no code/test assets depended on those locations.

## Adoption findings, not a new roadmap

The supplied documents' baseline was exactly the current repository revision;
there was no newer tracked implementation to overwrite. Local `AGENTS.md` was
untracked and left untouched. Small factual/link clarifications in the adopted
four documents are explicit:

| Area | Verified implementation / clarification |
| --- | --- |
| Reader | One Neovim default; prompt_toolkit fullscreen baseline is research-only; chapter/64-record loading remains bounded. Arrow keys retain native buffer-line behavior; `j/k` are visual-row keys. No horizontal tree switch is shipped. |
| Presentation | Three themes remain a decision, not a feature. Arbitrary 2-D math rendering and terminal-independent formula preview remain unimplemented. CORE wording no longer implies clickable links or native sup/sub typesetting. |
| Setup | First interactive `sol`, not the installer, requests and converts the exact audited Cambridge PDF. OpenDataLoader 2.5.13 is included in the full install; its explicit extraction operation still produces review candidates only. |
| Identity | CORE API/reference protocol v1 and generation binding are unchanged; workspaces remain schema 3, with supported legacy versions and no silent upgrade. Read-only snapshots are a usage contract, not deeply immutable collections. |
| Workspace and handoff | Canonical Markdown is local and identity-managed, not publicly committed book text. The existing Kitty/Zsh handoff is host-specific; the terminal-independent target remains proposed. |
| ESSENCE | Term study and prose exports ship. Syntax, UltraBERT, model/projector integration and durable investigation contexts remain proposals. The stale prose-policy path now links to its archived page. |

Code evidence: [reader](../../sol/terminal/neovim_reader.py),
[controls](../../sol/terminal/neovim.lua), [first run](../../sol/reader/onboarding.py),
[installer](../../scripts/install.py), [dependencies](../../pyproject.toml),
[CORE protocol](../../sol/core/protocol.py), [workspace schema](../../sol/workspace/store.py),
[ESSENCE commands](../../sol/essence/cli.py) and [prose export](../../sol/essence/prose.py).
The original supplied files' fingerprints are recorded in the inventory.
No runtime, corpus/schema, reference validation, installer behavior or ML feature
was changed by this migration. Future implementation must update the four current
documents after verification; archived pages must not be promoted by accident.

