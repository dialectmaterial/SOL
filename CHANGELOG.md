# Changes

## Unreleased

### Printed-source preview — 17 October 2026

Press `s` in the reader to see the printed source of the current passage: the
record's recorded region, cropped from the verified PDF snapshot, opens in a
separate image viewer (`SOL_IMAGE_VIEWER` overrides the desktop default), so
formulas whose typed transcription is unreviewed can be read as printed in any
terminal. The popup shows pages and transcription status; the reading position,
selection and workspace are untouched. The first-run import remembers the PDF;
existing setups use `sol --set-source-pdf PATH`.

### Reader themes — 17 October 2026

The reader has three presentation presets: **Terminal** (inherits the host's
colors; the default), **Dark** and **Paper**. Press `T` to cycle them for a
session, start with `sol --theme NAME`, or save one with `sol --set-theme NAME`.
Dark and Paper degrade to 256 colors or, on basic terminals, to Terminal with a
notice; `NO_COLOR` is honoured. Popups and the outline use a distinct panel color,
and Neovim's `~`/`@@@` filler markers are hidden. Saving a theme now preserves the
saved corpus pointer and vice versa. Canonical text, offsets and workspace
schemas are unchanged.

### Documentation consolidation — 17 October 2026

Adopt four human-facing design documents: [Architecture](docs/ARCHITECTURE.md),
[BEING](docs/BEING.md), [ESSENCE](docs/ESSENCE.md), and [CORE](docs/CORE.md).
The root README is a short setup/navigation gateway. Earlier guides, contracts,
research and root documents remain in the [legacy archive](docs/legacy/README.md),
with an integrity inventory and navigable historical links. This migration changes
documentation and its checks, not application behavior or data contracts.

### Reader consolidation — preceding implementation

Bare `sol` opens the single isolated Neovim reader. The earlier prompt_toolkit
fullscreen baseline is research-only, outside the installed package. Continuous
reading remains chapter/64-record bounded; `b/n` changes paragraphs and `p` toggles
paragraph/continuous mode. The outline is vertical; horizontal navigation is not
shipped. First interactive launch can import the exact audited PDF once. The
checkout installer includes all Python feature dependencies and handles native
requirements with consent. Existing corpus IDs, CORE v1 references and workspace
schemas are preserved.

## Earlier development history

The [previous changelog](docs/legacy/root/CHANGELOG.md) is preserved byte-for-byte.
It includes superseded optional-reader and horizontal-tree descriptions, which
are historical changes rather than current feature claims.
