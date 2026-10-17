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
the current scope, identified by `c`. At that stage `/` searched the book and `n/N` moved through
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
multi-passage scrolling. Search shows at most 20 matching passages. The latest
follow-up below adds verified match landing and highlighting, but repeat search
still moves between passages rather than between occurrences within a passage.
Selected-span workspace operations are not integrated into this
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

## Follow-up: reading through passage boundaries

Review baseline for this follow-up: `1159fa44b0240d6e98fe003a5f7dc7cfcf0c7137`.
The completed wrapping, typography, terminal independence, and persistence work
was preserved. Existing uncommitted README changes were left untouched.

The concrete friction was that ordinary row movement stopped at each canonical
passage boundary. `j/k`, arrows, and Ctrl-D/U now continue from an outer wrapped
row into one adjacent passage within the current reading scope. Forward entry
uses source offset zero; backward entry uses the previous passage's end. A large
movement from inside a passage first reaches its edge, rather than skipping its
tail or carrying a row budget across several records. Scope ends remain quiet
and create no visit. Explicit `{`/`}` jumps and passage-local action APIs remain
unchanged.

An active selection blocks automatic crossing, including an empty `v` or
Shift-arrow anchor. Crossing makes one guarded checkpoint, with the final source
entry offset set before saving. New passage IDs trigger a full text/style
projection; history preserves the origin, and reopening at another width retains
the saved source location. No global multi-passage string or selection identity
was introduced.

The checks also exposed an existing storage-error recovery gap: the interface
caught `OSError`, but the action transaction did not roll back its local state.
It now does, with regressions proving that a failed checkpoint preserves the
visible and semantic reading context. This does not claim reversal of arbitrary
external effects or bypass workspace conflict guards.

Twenty-two new regressions cover boundaries, scopes, empty/nonempty selection
anchors, identical prose with distinct IDs, Unicode layout, history, error
rollback, styling, reflow, and atomic saved end-position restoration. Full suites
collected 1,113 tests: all enabled checks passed, with three opt-in host checks
skipped in the reader-enabled run and 46 optional checks skipped in the lean
run. Real Alacritty/PTY and optional Kitty reader tests were run separately and
passed; Alacritty now also exercises forward/backward edge continuation and
checks the saved backward offset before a separate quit/save. Corpus manifest
and index fingerprints remain unchanged.

This follow-up adds programmatic real-host coverage, not a new physical-keyboard
or sustained human reading acceptance claim. The display still shows one record
at a time; boundary continuation is not seamless multi-passage scrolling.
Occurrence-level search and integrated selected-span actions remain deferred.
The next useful evidence is whether these gestures reduce friction during actual
reading without making passage transitions surprising.

## Follow-up: navigation and spacing from actual reading feedback

All three PDFs were reread cumulatively before this change. Their shared reader
priority and the third handoff's use-led criterion were retained. Planned
search-location work was deferred when the user supplied a more immediate
example: `{`/`}` were awkward for back/next, and the title and text began too
close to the terminal's upper edge.

`b/n` now jump to the previous/next canonical passage, with `{`/`}` retained as
aliases. Ctrl-P/Ctrl-N move through search-result passages. The bindings are
reader-body-specific: `b` and `n` remain ordinary letters in the query field,
and `n` never changes meaning merely because an earlier search exists. These
are passage units, not newly invented fixed-page identities. Shared actions,
scope limits, selection isolation, and checkpoint behavior are unchanged.

The centered column has a responsive top margin (two rows at a normal 24-row
height, up to three on taller terminals) and one blank lead after title/context
where space permits. Padding recedes when panels or warnings need room, and
short terminals receive none. Focus mode retains a quiet top margin without a
hidden-title reservation. This is not paragraph-dependent vertical centering.
Offsets, source geometry, selected spans, and persistence remain body-relative
and unchanged; half-page motion uses the actual smaller reading height.

Eight new regressions cover keys/query isolation, heights 12/18/24/40,
context/focus/warnings, panel pressure, cursor visibility on the freshly rendered
screen, styled selection through vertical resize, and half-page distances.
Full suites collected 1,121 tests: enabled checks passed, with three opt-in host
tests skipped in the reader-enabled run and 54 optional checks skipped in the
lean run. Updated real Alacritty/PTY checks and the optional Kitty reader check
passed separately. Corpus manifest and index fingerprints remain unchanged.
An unrelated pre-existing SQLite test-fixture warning was traced to a transaction
context that did not close its connection; the fixture now closes it explicitly.
The full reader-enabled rerun passed without that resource warning.

The revised spacing was also visually inspected in an owned Alacritty window
using invented styled text, Greek/CJK, and a long paragraph. The title was below
the upper edge, aligned with prose, and separated by a blank lead. Keys in that
test were driven programmatically, not by physical keyboard input. No personal
workspace or general terminal configuration was changed.

The old all-panels/very-short-terminal layout limitation remains; padding does
not claim to fix an impossible chrome budget. Exact occurrence landing,
seamless multi-passage scrolling, and integrated span actions remain deferred.
Sustained reading by the user is still the deciding validation, not the test count.

## Follow-up: search as a returnable reading detour

The previous boundary, `b/n`, and spacing refinements were preserved, including
unrelated existing README changes. This follow-up completes the bounded search
work deferred for that reading feedback. No corpus, CORE identity, workspace
schema, ESSENCE methods, or terminal integration contract was changed.

Opening a result now places the semantic cursor at its first verified source
occurrence before the single guarded checkpoint. Source-relative match ranges
are derived from the existing literal NFC/casefold search, including whole-word
mode. Captions may be excluded from the temporary matching projection without
being removed from source text. Complete Unicode expansions and compositions map
back to exact source spans; unrepresentable fragments or discontinuous matches
produce an explicit fallback, never guessed offsets. A passage without a
representable match opens at its beginning. A one-entry derived projection cache
is keyed by source text, query, mode, and caption labels, not persisted identity.

Marks combine with semantic emphasis, strong text, and code using ordinary
terminal styling: underline with an optional color accent. Escape hides marks
while preserving the query/results; a new search or Ctrl-P/Ctrl-N reveals them.
Same-passage search jumps now retain the originating cursor, viewport, and
selection in the reading trail. Reopening the unchanged match keeps its viewport
and does not create duplicate history. Ordinary repeated `open()` behavior is
unchanged. Query/mode/selection remain transient; saved positions remain exact
schema-3 source-codepoint offsets.

Review exposed a real display-cache bug that direct lexer tests missed:
prompt_toolkit's TextArea dynamic wrapper identifies the lexer by object identity,
so unchanged text could retain stale styles after a query or mark dismissal.
The reader does not switch lexers; its stable source lexer is now installed
directly and invalidates on semantic typography and current match ranges.
Regressions exercise the actual BufferControl cache and rendered screen styles,
not only independently generated fragments. No ANSI-decorated source is created.
Visual inspection also exposed unused status rows; the status now reserves only
its needed one to three rows, leaving more space for prose.

The added regressions cover Unicode/source alignment, whole-word mode, removed
caption boundaries, styled matches, same-passage history, selection return,
checkpoint atomicity/failure recovery, persistence, mark dismissal/reappearance,
actual cache invalidation, and status height.

Full suites collected 1,175 tests: all enabled checks passed, with three opt-in
host tests skipped in the reader-enabled run and 64 optional checks skipped in
the lean run. The real Alacritty and optional Kitty reader scenarios were run
separately and passed after the cache fix. This follow-up adds 54 regressions to
the previous 1,121-test state.

A read-only check against the actual local Hegel corpus examined 4,713 matching
passage/query pairs for eight philosophical terms in literal and whole-word
modes: all 12,816 resulting spans exactly matched their original source slices,
with no degraded projections. Manifest and index fingerprints remain unchanged.

The real Alacritty/PTY scenario additionally checks exact match landing, cached
styling, rendered marks disappearing/reappearing, history return, `b/n`, boundary
flow, and source-position reopening at a narrower measure without Kitty state.
The smaller optional Kitty reader comparison remains separate. An owned Alacritty
window was visually inspected with invented text: the matching word was
underlined, its caret landed at the source occurrence, and title/page/prose shared
the lowered reading column. Color was not established by that monochrome capture.
Programmatic key driving and screenshot inspection are not a physical-keyboard
or sustained human reading session. Personal workspaces and global emulator
configuration were not changed.

Repeat search remains passage-level, capped at 20 matching passages. Seamless
multi-passage scrolling, durable selected-span operations, and the known extreme
short-window/combining-glyph limitations remain outside this pass. Several long
warnings can exceed the three-row status cap at very narrow widths; context
provides their detail. The next usability decision still belongs to actual reading.
