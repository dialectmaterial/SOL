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

## One continuous reading surface

Adjacent paragraphs share a scrollable, read-only buffer, with supplied source
headings, semantic emphasis and unobtrusive context/help. Native `wrap` and
`linebreak` reflow prose without inserting source newlines. The maximum measure
is 72 terminal columns by default, centered and narrowed to fit the terminal.

The current corpus identifies chapters through supplied level-4 headings. SOL
groups their actual descendants; where that ancestry is absent it uses the
passage's parent section. It does not infer philosophical divisions from words
or invent headings. Extents longer than 64 passages are loaded in bounded
reading sections. Each canonical paragraph keeps its own identity.

| Key | Meaning |
| --- | --- |
| `j` / `k` | Visual wrapped rows; continue to a neighbouring section at the outer edge |
| `h` / `l`, `w` / `b` | Native character and word movement |
| `Ctrl-D` / `Ctrl-U` | Native half-window scrolling |
| `gg` / `G` | Start/end of the loaded reading section, not the book |
| `/`, `n` / `N` | Native search and matches within this section |
| `[p` / `]p` | Previous/next passage; continue across section boundaries |
| `[c` / `]c` | Previous/next reading section; enter its end/start respectively |
| `v` | Characterwise selection within one canonical passage |
| `c` | Source pages, attribution, path and linked notes |
| `?` | Local help; Escape returns to reading |
| `q` / `Ctrl-Q` | Validate and save the current position, then quit |
| `:qa!` | Leave without saving the current cursor |

`n` repeats search and `b` moves by word here, unlike the built-in reader's
passage shortcuts. Search is Neovim's native search syntax, not SOL's literal
whole-corpus search. These are deliberate, visible backend differences.

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

Section transitions restart the isolated native view. This can briefly flash;
native search history, jump lists and registers do not survive that transition.
This is continuous prose within a section, not a claim of seamless whole-book
scrolling or cross-chapter search. In-reader annotation/comparison actions,
focus mode and a logical tree/sidebar remain future work.

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
