# Reading in SOL

`sol` opens one terminal-native reader, powered by Neovim 0.11 or newer with an
isolated SOL configuration. There is no engine to choose. Your Neovim/LazyVim
settings are not loaded or modified. `sol --reader` remains an explicit alias.

Install or update a checkout with `python3 scripts/install.py`. The installer
includes all current Python feature dependencies, checks native tools, and asks
before installing missing system packages. Debian/Ubuntu native setup is automated;
other systems should supply the reported tools through their package manager.
If necessary, the installer supplies a pinned, checksum-verified private Neovim.

## First launch and returning

Without a configured corpus, interactive `sol` asks for your local PDF, converts
the supported source once, validates it and remembers the corpus location.
The current importer accepts the exact audited Cambridge / George di Giovanni
PDF, not arbitrary editions, scans or re-encoded copies. The source is unchanged.
Converted text lives under `$XDG_DATA_HOME/sol/corpora/` (normally
`~/.local/share/sol/corpora/`), outside the application installation.

An existing corpus can instead be selected with `sol --set-corpus DIRECTORY`.
It is never regenerated. A broken selected corpus produces an error rather than
silently replacing your source or allocating new passage identifiers. Scripts
and piped commands never answer interactive setup questions.

SOL remembers the last actor and that actor's workspace. Missing choices are
requested after corpus setup. `sol --actor NAME --workspace NAME` selects them
explicitly. `sol -n` uses the same reader without actor/workspace storage; its
markers are temporary. `sol -r` prints one random passage without opening the UI.

## Read, mark, copy and orient yourself

| Key | Action |
| --- | --- |
| `j/k`, `h/l`, `w` | Wrapped rows, source characters, next word |
| `b/n` | Previous/next paragraph, at its beginning |
| `p` | Switch continuous / one-paragraph reading, retaining the source cursor |
| Ctrl-D / Ctrl-U | Half-window scrolling |
| `gg/G` | Start/end of the loaded section, not the whole book |
| `/`, then Enter | Literal, case-insensitive search across the whole book |
| Ctrl-P / Ctrl-N | Previous/next search-result passage |
| Alt-Left / Alt-Right | Back/forward through the session's semantic reading trail |
| `v`, then movement | Select within one canonical paragraph; Escape clears |
| `y` | Copy the exact selected span, otherwise the current paragraph |
| `m1`, `m2`, `m3` | Place/move one of three immediately saved paragraph markers |
| `'1`, `'2`, `'3` | Return to a marker; `dm1` / `dm2` / `dm3` clears it |
| `c` | Context, path, source pages, attributed notes and marker slots |
| `t` | Book outline: `j/k` move, `h/l` parent/collapse or expand/child |
| `f`, `?` | Quiet focus mode / help |
| `q`, Ctrl-Q | Validate/save the semantic position and quit |
| `:qa!` | Quit without saving the current cursor; earlier successful saves remain |

In paragraph mode, `j/k` cannot move into another paragraph. Use `b/n` explicitly.
In continuous mode, adjacent paragraphs share a scrollable view; at a section
edge another outward `j/k` loads the neighboring section. Selections stay local
to their paragraph. Clear a selection before ordinary paragraph/section changes.

Search displays up to 20 matching passages. Choose one with `j/k` and Enter;
Escape returns without changing the reading position. Ctrl-N/P cycles those
result passages. Search does not alter canonical strings. Native regex searching
is not the primary SOL search, and `n` always means next paragraph.

Markers reuse ordinary workspace bookmarks, not a second identity system.
Press `c` to see source locations and excerpts, then `1`, `2` or `3` to return.
They attach to paragraphs and survive quit/reopen independently of cursor saves.

The outline highlights the current branch and reveals its ancestry. It starts
at a readable depth, with one vertical layout. `h` can move above the initial
doctrine root to the whole book. Enter reads a selected branch; Escape leaves
the reading cursor unchanged. `sol --dynamic-structure` opens this same outline
in a temporary reader. `sol --structure` prints the static hierarchy.

## Terminals and presentation

BEING is not an Alacritty or Kitty application. It uses Neovim's ordinary terminal
interface and requires interactive input/output and a usable `TERM` description.
Alacritty, Kitty, xterm, GNOME Terminal, WezTerm and other capable terminals are
hosts, not different SOL editions. A dumb terminal or redirected stream cannot
host fullscreen interaction; one-shot output such as `sol -r` remains available.

Prose uses a centered maximum measure of 72 terminal columns, narrowing on small
windows. Change it with `--width 64` (20–240). Native word-aware soft wrapping
reflows presentation without inserting canonical newlines or changing source
codepoint offsets. Titles align with prose, a top margin separates reading from
the window bar, and context stays behind `c`. Focus mode hides ordinary headings;
important source and typography warnings remain visible.

CommonMark semantics produce emphasis, bold and inline-code styles; ANSI is never
stored in the corpus. `--emphasis auto` uses standard italics for recognized
terminal descriptions, including Alacritty and Kitty, and visible underline for
unknown/basic descriptions. This is a heuristic, not a guarantee about fonts.
`--emphasis underline` explicitly selects the fallback. Projection mismatches
are reported instead of guessing styled offsets. Unsafe source controls are
refused rather than changing canonical text; C1 characters use native visible escapes.

Clipboard copying uses Neovim's standard providers: desktop helpers such as
`wl-clipboard` or `xclip`, macOS's clipboard tools, or detected OSC 52 support.
Availability depends on the host/session, especially over SSH or a multiplexer.
A missing provider is reported honestly; the text remains in the editor register.
The complete Debian/Ubuntu installer includes both desktop helpers.

`sol-kitty` remains a compatibility host launcher. Its source-image, comparison
and ESSENCE panes are separate integrations; none is required to read in another
terminal. `--shell` is a compatibility command interface, not the reader.

## Durable identity and current limits

The workspace stores passage identity, source digests and Unicode-codepoint
positions, never buffer numbers, byte columns or screen coordinates. Resizing
or reopening in another terminal restores the same meaningful textual location
when the corpus is unchanged. Width changes only reflow presentation.
CORE verification and guarded workspace saves remain in Python. Selections are
transient source-bound spans suitable for future workspace operations; they do
not automatically create annotations. Old schemas warn if only a paragraph can
be saved. No corpus or workspace migration is required for this reader change.

Continuous loading is still bounded to source chapters, split at 64 paragraphs;
it is not yet a seamless whole-book buffer. `gg/G` are section-local. Search
results open at the first verified occurrence, without per-occurrence highlighting.
An unmappable normalized match produces an explicit warning and opens its paragraph.
Reading mode and focus are session choices, while markers and position persist.
Horizontal tree navigation is withdrawn until a simple outline is dependable.

Headless editor tests and programmatic terminal checks do not establish sustained
human reading comfort. Acceptance should include long prose, styled selection,
`b/n` in both modes, markers, search and history return, outline navigation,
resize, clipboard sharing and workspace reopen in the user's normal terminal.
