# Native Neovim reader experiment

This command remains an opt-in, checkout-only comparison trial, not a replacement
for `sol`. Its implementation is now shared with the optional installed
[`sol --engine neovim` backend](../NEOVIM_READER.md), which connects to normal
workspace persistence. The research commands below remain temporary.
Neovim supplies its own terminal interface. SOL supplies verified corpus records,
semantic typography and source-bound selection/position validation. Nothing is
embedded inside prompt_toolkit, and neither Neovim nor an editor distribution is
forked. No installation or personal configuration change is required by the
experiment. An existing Neovim 0.11 or newer is required.

## Try the same text

From the repository root, in Alacritty or another capable terminal:

```sh
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus --trial opening nvim
```

Replace `opening` with `beginning` for the complete supplied first chapter,
including remarks and linked notes. The same named selectors work with the
existing `baseline`, `tui` and `html` experiments. No passage UUID copying is
required. Incompatible source structure is refused rather than substituted.

The reader displays the source's own headings. A research sample name is not a
new philosophical heading. Consecutive records remain separate canonical
objects even though their prose shares one scrollable projection.

Use `--width 64` after `nvim` to change the maximum measure. Resizing changes
presentation only; do not use formatting commands to insert source line breaks.

## Reading keys

| Key | Meaning in this experiment |
| --- | --- |
| `j` / `k` | Move through visual wrapped lines |
| `h` / `l`, `w` / `b` | Native character/word movement |
| `Ctrl-D` / `Ctrl-U` | Native half-screen movement |
| `gg` / `G` | Beginning/end of the loaded sample, not the whole corpus |
| `/`, `n` / `N` | Native search within the loaded sample |
| `[p` / `]p` | Previous/next canonical passage |
| `v` | Characterwise selection within one passage |
| `c` | Inspect source context and available attributed notes |
| `?` | Key help |
| `q` / `Ctrl-Q` | Capture the current position or selection and leave |

The normal SOL reader still uses its existing bindings. In particular, `n` means
search repetition here, not SOL's next-passage shortcut. This difference is
deliberate and should be evaluated during reading, not hidden as compatibility.

## Export and restore a position or selection

Choose a new private filename outside the corpus:

```sh
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus --trial opening nvim --export /tmp/sol-nvim-position.json
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus validate /tmp/sol-nvim-position.json
.venv/bin/python -B -m experiments.reader_surfaces --corpus local-corpus --trial opening nvim --restore /tmp/sol-nvim-position.json
```

This is the existing research packet around a CORE reference and optional
`TextSelection`, not an annotation, a new identity scheme or a workspace save.
Its exact source text, digests, current corpus generation and sample membership
must agree before restoration. Exports are independently checked in Python
after Neovim exits. Existing files, symlinks and corpus-directory destinations
are refused; successful explicit exports are owner-only. Selected text is private
book material and must remain outside Git.

## Identity and isolation

Neovim's byte-based buffer columns are translated to the same Unicode-codepoint
offsets used by SOL. A selection is converted from supported characterwise Vim
endpoints to the existing half-open source span. Display headings, separators and
notes are not silently given passage identity. Unsupported selection shapes or
uncertain coordinates are refused, never repaired by normalizing source text.

The source is an unnamed, nonmodifiable, non-file buffer. Canonical Markdown is
never an editor write target. Semantic highlights derive from SOL's existing
Markdown projection; no alternate Markdown parser or conceal-based identity is
introduced. Source-review and typography-fallback warnings remain visible.

Launch configuration, caches, state and logs live in a private temporary
directory. User init files, plugins, modelines, swap and ShaDa persistence are
disabled. Native Neovim may create its normal local server during startup; the
launcher isolates its runtime directory and stops servers before loading the
reader. This is not a sandbox against a malicious local user or editor binary.

This research command does not change an actor, personal workspace, annotation
schema or normal SOL default.
There is no tree/sidebar, analytical method or operating-system work in this
proof. Initial corpus verification/export still has a cost; the experiment does
not bypass CORE checks to make startup look faster.

## Adoption test

Read the same portion in this view and the current reader. Compare continuity,
wrapping, emphasis, selection, search/return and relocation after resizing or
reopening. Record a concrete interruption, not a feature count. Automated source
mapping and native-terminal checks cannot establish sustained reading quality.
Only adopt a Neovim-backed interface if it improves actual reading and replaces
maintenance work without compromising source identity.
