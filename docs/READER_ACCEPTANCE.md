# Reader refinement and acceptance record

14 October 2026. Review baseline: `ab6df517917c48c40d0e629a439f47699985c9e4`.

This is an engineering acceptance record, not a claim that BEING has passed the
test of sustained philosophical reading. The three cumulative handoffs retain
their respective roles: architecture, reader experience, and critical research
direction. This pass preserves those boundaries; it adds no ESSENCE analyses,
investigation schema, tree sidebar, Neovim embedding, or operating-system work.

## Already sound at the baseline

Canonical Markdown and indexed plain text were separate from terminal styling.
Semantic emphasis spans, a source-codepoint cursor and selection, independent
passage/search/history movement, guarded schema-3 position persistence, a maximum
reading measure, and focus/context modes were already implemented. CORE identity,
workspace conflict guards, and the optional host boundary did not need replacing.

The resumed working tree already contained the word-aware projection, shared
rendering/navigation geometry, 72-column default, generic-terminal style fix,
aligned title/page context, and initial reflow/host tests. Those changes were
preserved. The continuation finished regressions for narrow help and warning
visibility, dismissed search panes, and preferred-column reset after resize;
completed the test runs; and corrected misleading documentation.

## Problems removed

The old terminal renderer split ordinary words at arbitrary cells. Title/path
metadata competed with a differently aligned prose column. Automatic emphasis
did not recognize `TERM=alacritty` and consulted `KITTY_WINDOW_ID`. Narrow help
hints were clipped; cached search results could reappear during ordinary reading.
A preferred column from a wide layout could survive reflow and influence the next
vertical move. Warnings needed priority over routine passage metadata.

There was no mandatory Kitty runtime dependency in the baseline reader. The
accidental assumptions were a styling heuristic and Kitty-biased live coverage,
not a requirement to open a Kitty application. `sol --reader` remains direct
generic-terminal reading, with Alacritty a first-class host. `sol-kitty --reader`
remains an optional host for the same adapter.

## Text, typography, and presentation

`sol.terminal.reading_layout.LineLayout` supplies one projection for rendering and
visual motion. It pads the display before a word that fits a row but not the
remaining space, making the existing renderer wrap there. Padding is neutral,
not emphasized or selected. Separators at a wrap edge may be invisible in the
display but remain in the canonical source. Existing hyphens/dashes and CJK
boundaries permit breaks; overlong unbreakable sequences fall back to character
wrapping. Styled-span boundaries do not create word breaks.

No canonical newline, whitespace, ANSI sequence, Markdown marker, ID, digest,
cursor, or selection offset is changed. Mappings connect display characters and
cell coordinates to original Unicode insertion boundaries. Resizing changes
only this presentation projection. Unsafe controls are visibly escaped with
source-bound mappings.

Semantic CommonMark emphasis still maps to source spans before terminal styling:
Alacritty and Kitty use ordinary italics, strong emphasis uses bold, inline code
uses underline, and quotation records/spans receive a context label. An unknown
terminal uses underline for emphasis; explicit overrides remain available.
`TERM` recognition is a heuristic, not a capability probe. Font and emulator
configuration still determine actual glyph appearance. A semantic projection
mismatch produces plain text with an explicit warning rather than guessed styles.

The title and subtle printed-page provenance now align with the prose column.
Full virtual path, PDF pages, workspace, and scope are behind `c`. Bottom status
and help are secondary and responsive; important warnings remain in focus mode.
Default measure is 72 columns, centered where possible and narrowed to fit;
`--width 20..240` still configures the maximum. This is a provisional reading
choice, not a pixel value or a proven optimum.

## Navigation, selection, and continuity

No new Vim command family was added. `j/k` and Ctrl-D/U use displayed rows;
`h/l` use exact source codepoints; `}` / `{` move semantic passages; `gg/G` address
the current scope, identified by `c`. `/` searches the book; `n/N` move through
matching passages, not individual occurrences. History restores the source cursor,
viewport anchor, selected span, scope, and query/results. Presentation does not
force the old result pane back onto the reading surface.

Selection keeps its existing contract: requested and resolved UUIDs, half-open
codepoint span, exact selected text, and content/plain-text digests. Future
annotation, comparison, relation, export, or investigation must consume that
same identity, not introduce another selection scheme. Selection remains transient.

Schema-3 persistence still stores a semantic cursor and source viewport anchor,
not terminal row, column, width, or emulator. Reopening an unchanged corpus at a
different measure restores the same cursor. Scroll placement is approximate;
cursor visibility takes priority over reproducing the old screen arrangement.
Existing freshness, exact-text binding, revision/conflict, and save-refusal
guards remain. Old workspace versions need an explicit separate-copy upgrade.

## Checks and their limits

The reader-enabled suite collected 1,091 tests: all enabled tests passed, with
three opt-in live-host tests skipped. The lean installation also collected 1,091:
all enabled tests passed, with 39 optional tests skipped. The two reader host
checks were run separately and passed; the unrelated Kitty/Zsh handoff was not
rerun because this iteration changed no ESSENCE handoff behavior.

Automated regressions exercise word boundaries, long tokens, physical source
newlines, Unicode, escaped controls, styled selections, 40/72/100-column reflow,
responsive context alignment, narrow warnings, motion, search/history, and
schema-3 reopen. Generic-host checks prohibit Kitty imports/processes and remove
Kitty environment variables. Packaging checks include the new layout module.
The local corpus also passed 982,290 ordinary-token wrapping checks at 40, 72,
and 100 columns, with no unexpected word splits. Its manifest and index SHA-256
fingerprints are unchanged from the start of this iteration.

An independent renderer-level audit compared 58,822 source-boundary coordinates
against actual prompt_toolkit window geometry at eight widths, including
randomized whitespace, dashes, Greek, CJK, combining marks, and escaped controls.
No coordinate mismatch was found. This is not manual terminal acceptance.

The earlier part of this iteration visually inspected a real Alacritty reader
using the local Hegel corpus: a long first-edition preface passage on printed
page 10 with multiple italic spans, centered prose, selection, search, context,
focus, and a 40-column reflow. The grid change used isolated font zoom, not a
physical window-drag test. Navigation sequences were supplied programmatically
to the real reader key processor: `j/k`, Ctrl-D/U, `gg/G`, passage movement,
styled selection, search with `n/N`, and history return. Selection retained the
same source span after reflow and return.

A saved source cursor at offset 1860 reopened at the same textual location in
a narrower ordinary Alacritty CLI reader. The viewport reflowed to keep that
cursor visible. Separate opt-in real Alacritty/PTY tests exercised two fresh
100/40-column hosts and schema-3 reopen; the smaller real Kitty run checked
optional hosting, standard italic output, selection, search, and return.

These host tests use invented text and private temporary storage. They are real
emulator tests with programmatic bindings, not human keyboard acceptance.
Focus-based desktop key injection was unreliable and is not counted as a
successful physical-keyboard check. No personal workspace or global terminal
configuration was changed. The user has not yet performed the sustained reading
session required by the latest handoff; the core usability milestone remains open.

## Remaining reading limitations

The display still presents one canonical record at a time rather than seamless
multi-passage scrolling. Search shows at most 20 matching passages; opening a
match starts at the passage beginning, without occurrence-level navigation or
highlighting. Selected-span workspace operations are not integrated into this
view. The source-review/comparison desks remain separate interfaces.

A prompt_toolkit edge case can visually omit a decomposed combining mark at the
rightmost cell of a full row. Its source codepoint and identity remain intact;
this is a glyph-rendering limitation, not a coordinate mismatch. The inspected
local Hegel index has no decomposed combining codepoints. General-corpus support
needs a deliberate rendering fix rather than canonical normalization to hide it.

Very short windows and long titles/context need further human evaluation. A
physical-keyboard session, ordinary drag resize, and sustained reading in the
user's actual Alacritty setup remain necessary. A book/PDF still offers stable
page memory, richer source typography, facsimiles, and continuous text without
the current passage boundary. Those differences are research evidence, not
reasons to declare the present medium successful.

## Small reading-friction log

Keep personal reading entries locally; avoid committing private annotations or
book excerpts. Record observed needs before adding features or schemas:

```text
Date and host:
Reading context / activity:
Friction (what made book/PDF/another tool preferable):
Desired action:
Object involved (passage, span, facsimile, comparison, ...):
Current workaround:
Evidence (one-off or recurrent):
Resolution or consciously accepted limitation:
```

The next decision should come from these sessions. Investigation remains a
future hypothesis; ESSENCE should reuse mature tools; CONCEPT stays deferred.
