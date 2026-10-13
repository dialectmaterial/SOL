# SOL modularity contract

SOL is one project developed in one repository. Its modularity goal is three independently selectable stages: **BEING**, the reader and philosophical workspace; **ESSENCE**, applications and experiments; and **CONCEPT**, operating-system composition. **CORE** names the shared software foundation. It is not a fourth philosophical stage, a replacement for the three doctrines, or a second canonical book.

Independent selection is the architectural destination. The first implemented step is an internal public boundary, `sol.core`, so applications can use the corpus without importing the interactive shell. Separately released `sol-core`, `sol-being`, and future application distributions do **not** exist yet. The current `sol-organizes-logic` package, commands, and installation instructions remain in place.

## Responsibilities and dependency direction

| Component | Responsibility | Boundary |
| --- | --- | --- |
| CORE | Shared book and passage models, verified corpus loading, canonical reference resolution, virtual paths, and corpus configuration | Does not import reader command loops, workspace storage, terminal adapters, or machine-learning frameworks |
| BEING | Scholarly reading, continuity, attributed notes, comparison, review testimony, and relations | Consumes shared corpus APIs; owns reader actions and personal workspace operations; the virtual shell is one optional interface |
| ESSENCE | Optional applications, terminal-host integrations, linguistic experiments, classifiers, and other research tools | Consumes shared APIs or an explicit data protocol; does not redefine passage identity or require the BEING shell to start |
| CONCEPT | Future reproducible environment and operating-system composition | Selects applications and configuration deliberately; installing the reader must not require a SOL operating system |

Dependency direction is toward shared contracts, not toward another application's entry point. An experiment should not import `sol.reader.app` just to find a passage. A terminal launcher should not import the shell to inspect CLI options. The launcher can use `sol.core.config` for corpus discovery and `sol.reader.options` for option definitions, without starting a reader session.

Current folders are implementation units, not a claim that each already forms an independently installable product. In particular, `sol.terminal` contains optional adapters in the aggregate distribution; its placement does not make CORE dependent on kitty or prompt_toolkit.

The architecture handoff sets the reader and scholarly workspace, not a simulated
POSIX environment, as BEING's governing purpose. ESSENCE computation belongs in
a real Unix shell and replaceable applications, with deliberate movement back to
BEING. Existing virtual navigation remains compatible; it is not a second shell
language or the canonical meaning of a passage.

### The shared corpus contract

`sol.corpus.contract` remains the implementation of canonical validation and verified snapshots. It is a shared-domain dependency, not reader application code: it does not import the reader, workspace, or terminal layers. `sol.core` exposes its snapshot and error types through the public boundary rather than duplicating the contract.

Corpus maintenance and initial PDF conversion remain explicit tooling in `sol.corpus.convert` and related extraction modules. Ordinary loading of an existing index does not perform conversion, require the optional Markdown parser, or download a source. A future package split must include the shared contract wherever CORE requires it while keeping conversion-only dependencies optional.

The first handoff implementation adds a replaceable OpenDataLoader extraction
adapter. Physical extraction yields unreviewed, source-bound candidate artifacts;
only explicit mappings and reviewed Markdown can enter a separate canonical copy.
SOL preserves existing identities and semantic metadata rather than deriving them
from an engine's headings, element IDs, or rectangles. This is not a from-scratch
generic book importer. [Extraction workflow](EXTRACTION.md).

## Public CORE API, version 1

`sol.core.API_VERSION` is `1`. This describes the public Python boundary, not the installed distribution version, corpus contract version, or workspace schema version. Those are separate compatibility decisions.

| Public surface | Purpose |
| --- | --- |
| `Book`, `Node`, `Passage` | Shared reader projection and passage data, retaining the full canonical record graph alongside the three-doctrine view |
| `load_corpus_book(directory)` | Load a verified existing corpus as a book without opening or extracting the PDF |
| `CorpusError`, `CorpusSnapshot`, `load_snapshot`, `verify_snapshot_current` | Existing contract verification and explicit generation checks |
| `Reference`, `resolve_reference(book, identifier)` | Resolve canonical references while retaining requested UUIDs, resolved targets, and retirement chains; do not guess by textual similarity |
| Virtual-path helpers | Resolve locations against an explicitly supplied book root, rather than an implicit edition-global tree |
| `sol.core.config` | Shared corpus discovery and explicit configuration operations, using the existing settings and source-checkout discovery rules |

A small client can inspect a supplied local corpus directly:

```python
from pathlib import Path
from sol.core import API_VERSION, load_corpus_book, resolve_reference

assert API_VERSION == 1
book = load_corpus_book(Path("local-corpus"))
passage = book.passages[0]
reference = resolve_reference(book, passage.identifier)
print(reference.target_id, reference.record["sources"])
```

The example selects a record in book order; it does not claim that displaying a passage counts as reading it, create a workspace, or verify its transcription. `Book.passages` is the convenient Hegel main-text projection, not the complete classifier corpus. Applications needing editorial material, edition notes, formulas, or references must inspect canonical metadata and choose their inclusion policy explicitly.

The public exports are lazy: importing `sol.core` or requesting models and configuration does not load the corpus parser or reader. Importing CORE must not initialize a workspace or actor registry, launch a terminal, or start network activity. Explicit configuration writes remain explicit. Existing imports through `sol.reader.models` and reference exports from `sol.workspace.reader` retain compatibility while consumers move to the public boundary.

Generation verification checks the manifest, index, and canonical Markdown. It is not physical PDF/image verification or proof of accurate transcription. Source evidence and review testimony retain their separately documented scopes.

## One corpus and compatible personal work

Every component must preserve canonical record UUIDs, `corpus_id`, edition and translator attribution, the declared source fingerprint, printed/PDF page distinctions, and unresolved or retired references. Paths and hashes are not replacements for identity. Moving a function between modules must not allocate new record IDs, reconvert the source, or change an existing workspace's schema.

CORE does not bundle the PDF or the local corpus. A future independently installed application must locate an explicitly supplied corpus through the shared discovery/configuration boundary. It must not depend on being run from a particular checkout or silently switch to another edition when a selected source fails validation.

Workspace storage remains the responsibility of BEING's existing operations. Reusing its database requires the same identity, validation, conflict checks, authorship rules, and explicit migration boundaries. A classifier or terminal pane should not write directly to its tables or turn model output into reader-attributed assertions. A saved note remains personal work, distinct from Hegel's prose and the edition's annotations. The [corpus contract](CORPUS.md), [workspace plan](WORKSPACE_PLAN.md), and [export boundary](WORKSPACE_EXPORT.md) remain authoritative.

## Installation is a separate boundary

A Python import package and an installable distribution are different things. Creating `sol/core/` establishes a code boundary; it does not itself create a `sol-core` wheel or make parts of the current wheel independently selectable. Separate build metadata and archive contents must enforce that later. Proposed distribution names are design labels, not instructions to install similarly named projects from a package index. [Python Packaging: distribution versus import packages](https://packaging.python.org/en/latest/discussions/distribution-package-vs-import-package/).

The existing `shell` and `corpus` extras add optional dependencies to the aggregate installation. Extras do not remove application files from its wheel. Future split packages will need deliberate ownership of each module, compatible dependency ranges, and console-script entry points, without two wheels accidentally owning the same file. [Python Packaging: dependencies and extras](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#dependencies-and-requirements).

pipx installs applications into isolated environments. Installing two SOL applications separately with pipx will not make one application's Python imports visible to the other. Each must declare its own compatible CORE dependency. In-process integration can use an explicitly configured shared environment or deliberate injection; communication between separately launched applications needs a documented, versioned protocol, for example JSON carrying corpus identity, record IDs, and provenance. A process protocol is future work, not an implicit feature of this refactor. [How pipx works](https://pipx.pypa.io/stable/explanation/how-pipx-works.html).

## CONCEPT composition remains opt-in

Later NixOS modules or profiles can compose a reader, selected ESSENCE applications, and their configuration. Each service or integration should be enabled deliberately rather than treating CONCEPT as a mandatory runtime dependency for BEING. NixOS provides typed options and enable switches for such composition; the particular SOL options have not been designed or implemented here. No operating-system configuration is changed by this step. [NixOS: writing modules](https://nixos.org/manual/nixos/stable/#sec-writing-modules).

## Handoff priorities and acceptance gates

The immediate order is: an extraction adapter with a reviewed-copy proof,
semantic/interface separation, a minimal CORE reference protocol, one reversible
BEING–ESSENCE handoff, then one substantial experiment. These refine the longer
packaging roadmap below rather than requiring a broad rewrite. Dependencies remain
replaceable, and existing corpus/workspace contracts remain binding. The current
extraction step does not claim that a cross-process protocol or reversible shell
bridge has already shipped.

1. **Establish the internal CORE boundary.** Move shared models, reference/path operations, configuration, and indexed corpus loading behind `sol.core`. Keep compatibility imports and the current aggregate installation. Test that importing CORE and CLI options does not import the shell, workspace, terminal, extraction tooling, or optional frameworks.
2. **Exercise it with real consumers.** The reader and launcher should use this boundary; future ESSENCE applications can do likewise. Preserve existing reader behavior, corpus verification, workspace reopenability, and installed command tests. Add new APIs only for demonstrated cross-component needs.
3. **Build independent distributions deliberately.** Prepare CORE and BEING wheels when their file and dependency ownership is settled. Test CORE-only and BEING-only installs in fresh environments, commands outside the source checkout, and sdist/wheel contents. Installing BEING must not require ESSENCE frameworks or CONCEPT configuration. Build without copying local text, source images, actor profiles, or workspace files.
4. **Add applications and process contracts as needed.** Package actual ESSENCE tools when they exist, not empty placeholder packages. Version cross-process messages, reject incompatible identities or schemas, and test missing applications as ordinary optional cases.
5. **Compose the operating-system layer later.** Test opt-in NixOS modules independently before a combined profile. Shared development in one repository must not become compulsory installation of every stage.

The current acceptance gate is code/import separation plus preserved aggregate behavior. A temporary core-only wheel fixture also checks that the shared API can read and resolve records without any reader, workspace, or terminal files present. This is a dependency-boundary test, not a published SOL product. Passing it is not a claim that independent distributions or a NixOS distribution have shipped. Compatibility, isolated builds, and clean installs are the evidence required before making that claim.
