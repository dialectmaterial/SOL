# Continuous reading with Neovim

The optional native Neovim reader is part of the SOL installation. Bare `sol`
still opens the built-in reader; adopting a new default is a separate decision.
Both readers run in Alacritty or another capable terminal. Neither requires Kitty.

Refresh SOL from a checkout, with Neovim 0.11 or newer already on your PATH:

```sh
pipx install --force .
sol --engine neovim
```

SOL does not install Neovim or load your Neovim/LazyVim configuration. To try
without an actor or workspace:

```sh
sol -n --engine neovim
sol -n --engine neovim --width 64 --emphasis underline
```

Normal corpus discovery applies. Nothing reconverts or rereads a PDF. The
backend and terminal are checked before actor/workspace onboarding.

## Continuous or one-paragraph reading

Adjacent paragraphs share a scrollable, read-only buffer, with supplied source
headings, semantic emphasis and unobtrusive context/help. Native `wrap` and
`linebreak` reflow prose without inserting source newlines. The maximum measure
is 72 terminal columns by default, centered and narrowed to fit the terminal.

The current corpus identifies chapters through supplied level-4 headings. SOL
groups their actual descendants; where that ancestry is absent it uses the
passage's parent section. It does not infer philosophical divisions from words
or invent headings. Extents longer than 64 passages are loaded in bounded
reading sections. Each canonical paragraph keeps its own identity.

Press `p` to switch between continuous reading and an isolated paragraph. The
same source cursor or selected span is retained. In paragraph mode, `j/k`, paging
and native search cannot move into another paragraph. Use `[p` / `]p` explicitly
to change paragraph. `n/N` retain Neovim's search-repeat meaning. Reading mode is
a session presentation choice; a new session starts in continuous mode.

| Key | Meaning |
| --- | --- |
| `j` / `k` | Visual rows; never leave the paragraph in paragraph mode |
| `h` / `l`, `w` / `b` | Native character and word movement |
| `Ctrl-D` / `Ctrl-U` | Native half-window scrolling |
| `gg` / `G` | Start/end of the loaded reading section, not the book |
| `/`, `n` / `N` | Native search and matches within this section |
| `[p` / `]p` | Previous/next passage; continue across section boundaries |
| `[c` / `]c` | Previous/next reading section; enter its end/start respectively |
| `p` | Toggle continuous/paragraph mode without changing source position |
| `m1`, `m2`, `m3` | Place or move one of three paragraph markers |
| `'1`, `'2`, `'3` | Return to the marked paragraph |
| `dm1`, `dm2`, `dm3` | Clear that marker |
| `y` | Copy the exact selection, or the current paragraph, to the system clipboard |
| `t` | Open the interactive structure view |
| `v` | Characterwise selection within one canonical passage |
| `c` | Source pages, attribution, path and linked notes |
| `?` | Local help; Escape returns to reading |
| `q` / `Ctrl-Q` | Validate and save the current position, then quit |
| `:qa!` | Leave without saving the current cursor |

`n` repeats search and `b` moves by word here, unlike the built-in reader's
passage shortcuts. Search is Neovim's native search syntax, not SOL's literal
whole-corpus search. These are deliberate, visible backend differences.

## Three book markers

Markers attach to paragraphs, not screen coordinates. They save immediately,
independently of quitting or saving the reading cursor. Press `c` to see all three
slots, source location and a short opening excerpt; press `1`, `2` or `3` from
that panel to return. Setting an occupied slot moves that marker. Returning lands
at the paragraph's beginning, even after resizing or reopening.

Slots are ordinary workspace bookmarks named `sol:reader-marker:1` through `:3`;
existing named bookmarks remain untouched. No schema migration or second
identity system is introduced. In `-n` mode they are explicitly temporary and
disappear when the reader exits.

## Clipboard

Visual-select with `v`, then press `y` to share the selected text; without a
selection, `y` copies the paragraph. It uses Neovim's standard clipboard provider,
not a Kitty-specific facility. A missing provider is reported honestly, retaining
text only in Neovim's register. Depending on the host, install `wl-clipboard`
(Wayland) or `xclip` (X11); supported terminals can also use Neovim's OSC 52
provider. No system package or personal editor configuration is changed by SOL.
See [Neovim clipboard providers](https://neovim.io/doc/user/provider/#clipboard).

## A map of the book

Press `t` while reading, or open it directly:

```sh
sol --dynamic-structure
sol --dynamic-structure --depth 2
```

The standalone command uses a temporary reader, without actor/workspace setup.
The static `--structure` output remains available unchanged.

The default outline is two levels deep. `*` marks the current branch and `>` its
ancestors; the full current path remains visible even when a branch is collapsed.
`Tab` switches between an expandable vertical outline and a horizontal column
tree. Narrow terminals show fewer columns without changing the selected source.

Use `j/k` to move, `h/l` to collapse/expand or move to parent/child, `+/-` to
change depth, `r` for the reading doctrine, `b` for the current branch and its
siblings, and `w` for the whole work. Enter reads the selected branch; Escape
returns without changing the reading position. In the standalone tree, Escape
exits. Tree paths are display keys; opening a branch resolves its existing source
UUID through Python. No artificial philosophical headings or filesystem objects
are created.

## The same workspace, not editor persistence

The normal actor/workspace chooser and remembered launch apply. Both engines
read and write the existing workspace format. Position means requested passage
UUID, source digest and Unicode-codepoint offset, never buffer number, UTF-8
byte column, terminal row or screen width. Quit with `q`, change width or engine,
then reopen: unchanged text restores the same semantic location. The view is
recentered around that location; an exact scroll arrangement is not persisted.

Each returned position is checked against CORE, its exact displayed record and
the current corpus generation before one guarded workspace save. A concurrent
workspace writer or changed source is refused rather than overwritten. Existing
workspace restore rules still handle changed text and retired references;
retired requested UUIDs are retained. Older workspace schemas save the passage
only and emit a warning instead of claiming to save an exact cursor.

Selections use the existing `TextSelection` model. They are transient and do
not create annotations automatically. Cross-passage, linewise and blockwise
selection exports are refused. Changing reading sections requires clearing the
selection. On a heading/separator, a normal-mode quit lands on the nearest
actual prose boundary; visual endpoints are never adjusted this way.

## Current limits and isolation

Section transitions now stay in the same native Neovim process, using private
inherited request/response pipes. Explicit actions execute on the Python thread
that owns the existing workspace; there is no network listener, daemon, shell
command interpolation or second SQLite owner. Marker writes acknowledge success
or failure before quitting. View reloads keep native search history/registers,
but old buffer jump-list entries are not a semantic return trail.

Prose still loads in bounded sections; this is not a claim of seamless whole-book
scrolling or cross-chapter search. In-reader annotation/comparison actions and
focus mode remain future work. Native cursor motion does not issue a database or
channel request for every key.

User init files, plugins, modelines, swap, undo and ShaDa persistence are disabled.
Neovim receives verified text as inert JSON in temporary private files, and the
source buffer is nonmodifiable and is not a canonical Markdown file. This is
isolation from personal configuration, not a security sandbox for Neovim itself.
The corpus's C1 extraction artifacts are visibly escaped as hexadecimal markers
through [Neovim's native display option](https://neovim.io/doc/user/options/#'display'),
while retaining their exact source scalars. Other controls/bidi source characters
that cannot be safely projected are refused; use the built-in reader's visible
escaping for those passages. Alacritty and
Kitty use ordinary italic terminal styles; unknown/basic terminal profiles use
underline. `--emphasis` can explicitly select either presentation.

The installed Lua surface is also reused by the original checkout-only
[comparison experiment](research/NEOVIM_READER.md). Research launches remain
temporary and do not open your personal workspace.

## Verification

The public tests cover source mapping, native motions/selections, exact position
returns, source-change refusals, workspace conflicts, retirement identities,
section transitions, packaging and reopen at different measures. Optional live
acceptance uses invented text, temporary workspaces and owned Alacritty windows:

```sh
SOL_TEST_LIVE_NVIM_ALACRITTY=1 python -B -m unittest discover -s tests -p test_neovim_reader_alacritty.py
```

These are programmatic native-terminal checks, not sustained human reading
acceptance. Compare an actual reading session with the built-in reader before
deciding which engine should become the default.
