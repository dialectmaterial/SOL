# Neovim reader implementation

Neovim now powers the single normal `sol` reader. For setup, controls and known
limits, see [Reading in SOL](READER_VIEW.md). The old `--engine neovim` spelling
is accepted for compatibility but is not needed. The built-in fullscreen engine
has been removed from the installed package; its historical research baseline
remains under `experiments/reader_surfaces/`, outside the wheel.

Python retains corpus verification, source identity, semantic history and guarded
workspace operations. Neovim owns disposable buffers, visual movement, soft
wrapping and terminal styling. SOL runs an isolated native process, not an
embedded editor screen or the user's editor configuration.

Each view contains at most 64 canonical paragraphs. Existing CORE references
bind every displayed record; Lua converts exact Unicode-codepoint positions to
UTF-8 boundaries and back. A result is accepted only after checking the current
generation, record membership, source digests and selection bounds. No terminal
row or editor buffer identifier is durable identity.

Explicit workspace and navigation actions cross two inherited, private pipes.
There is no listening socket, daemon, shell interpolation or separate database
owner. View changes reuse the native process. Native character/row movement
does not send persistence requests. Search and history use the shared ReaderActions
boundary, not Neovim's disposable buffer jumplist. Markers reuse named workspace
bookmarks. A chosen outline node resolves to an existing paragraph reference.

The installer reuses Neovim 0.11+ or supplies a pinned official archive, checked
against a committed SHA-256 digest and installed privately under SOL's user-data
directory. Reading never downloads or installs anything. No personal Neovim,
terminal-emulator or shell configuration is required for the reader.

The research prototypes are not alternative supported product interfaces. In
particular, the old prompt_toolkit fullscreen baseline is not shipped in the
installed package. prompt_toolkit remains useful for the compatibility command
prompt and is included in the full installation.
