# Reader gaps measured against Zathura

**Status:** Accepted as the reader backlog by the maintainer (20 October 2026).
Each item becomes work only through a task in [CURRENT_TASK](../CURRENT_TASK.md).

**Prepared:** 20 October 2026, by Codex (comparison) and Claude Code (this
summary), against SOL `efaa887` and the installed Zathura 2026.10.4 with
MuPDF. Documentation and code were inspected; no timed side-by-side reading
trial was run.

This is coordination, not design authority: what SOL should be remains in
[Architecture](../../ARCHITECTURE.md), [BEING](../../BEING.md),
[ESSENCE](../../ESSENCE.md) and [CORE](../../CORE.md).

## What SOL keeps

Zathura is a strong model for the *reading surface*, not for the workspace.
Attributed, versioned notes, stable passage identities, verified source
bindings and reproducible ESSENCE results have no Zathura equivalent and must
survive every change below. SOL's reflowing text is also a real advantage over
a fixed page that has to be panned.

## Gaps, most important first

| Priority | Gap | Where it shows today |
|---|---|---|
| Highest | **Complete reader search.** `/` asks for at most 20 matching passages, `Ctrl-N`/`Ctrl-P` step between passages rather than occurrences, and each opens at its first match. Later passages of a common word cannot be reached; there is no result count. | `sol/terminal/neovim_reader.py` (search request), `sol/reader/actions.py` (result navigation and opening) |
| Highest | **The printed page beside the text, zoomable.** `s` renders fixed 144 dpi crops (120 dpi pages) into a separate image viewer, which loses page context and cannot be enlarged sharply. The reader called it "helpful but awkward" (BEING §7). SOL already knows the verified PDF and the physical page, so it can open a PDF viewer such as Zathura at that page. | `sol/terminal/source.py` |
| High | **Whole-book and printed-page navigation.** `gg`/`G` mean the loaded section, a view holds at most 64 paragraphs, and although the status line shows the printed page there is no "go to page 240". | `sol/terminal/neovim_*.lua`, `sol/reader/actions.py` |
| High | **Measured navigation latency.** Recorded medians: 1.21 s from Python start to the first payload, 462 ms for an ordinary payload, 868 ms with many footnotes (HANDOFF, before #47). Measure time to readable text and the delay of crossing a section in real use; the opening screen hides waiting but removes none of it. | `sol/reader/`, `sol/terminal/neovim_reader.py` |
| Medium | **Named landmarks.** Only three quick markers in the reader, although the workspace already stores named bookmarks: name, list and jump to them from the reader. | reader controls; workspace unchanged |
| Medium | **User keymaps.** The reader runs a private Neovim configuration on purpose; a small documented file of key remappings would let readers adapt controls (`n`/`b` are paragraph moves, not Vim's) without editing SOL. | `sol/terminal/` |
| Scope decision | **Other books and editions.** The first-run import accepts only the audited Cambridge/di Giovanni PDF. Reading a German edition or an article beside it needs either a second corpus or a plain PDF companion; this is a reserved decision for the maintainer, larger than reader polish. | `sol/reader/onboarding.py` |

## Not adopted

- **SyncTeX, automatic reload, printing and attachments.** They serve TeX
  toolchains and changing documents; SOL's corpus is fixed and verified, and
  refusing a silently changed corpus protects annotations.
- **Rotation, dual-page and presentation layouts** inside the text reader.
  They belong to the PDF companion, not to reflowed text.
- **Native 2-D mathematics in the terminal.** Still out of reach (BEING §5);
  the zoomable printed page is the answer for now.

## Validation still missing

Automated tests cannot show that an hour of reading is comfortable. Each item
above is done only after the maintainer has used it in a real session, as
BEING §8 requires.
