# SOL’s virtual interface: an investigation

Research checked against primary documentation on 11 October 2026, with the
implemented input-only stage recorded below on 12 October. The broader tools are
possibilities, not adopted SOL interfaces.
The workspace design is separate: see [WORKSPACE_PLAN.md](WORKSPACE_PLAN.md).

## What we are choosing

SOL’s book shell interprets commands against a corpus. A terminal interface
controls input and presentation. A terminal emulator provides the environment
in which that application runs. These are different responsibilities.

Kitty is the chosen eventual terminal host. There is no reason to reopen that
choice here, and this investigation does not configure it. Nor should a richer
interface decide what counts as a passage, an annotation, or a philosophical
relation: those belong to SOL’s corpus and workspace contracts.

The following assessments of fit and implementation effort are design judgments
for the current codebase, not performance measurements.

| Tool | Responsibility | Possible role in SOL | Main tradeoff |
| --- | --- | --- | --- |
| prompt_toolkit | Command input; optionally full-screen applications | Implemented optional command-first prompt | Input stays separate; full-screen work needs more assembly |
| Rich | Styled terminal output | Emphasis, readable results, trees and comparison summaries | Rendering is not an interactive workspace |
| Textual | Full-screen application framework | A multi-pane philosophical reading desk | Larger change to event handling, focus and layout |
| Python curses | Low-level terminal control | An educational route into terminal interfaces | More rendering and interaction infrastructure to build |
| Frogmouth | Standalone Markdown browser | A design reference and browsing experiment | Document navigation is not corpus-level passage identity |
| Glow | Standalone Markdown viewer | Optional presentation of exported passages | Does not understand SOL’s canonical relationships |
| mdcat | Standalone Markdown renderer | An experiment with source images and checked mathematics | Version and terminal capabilities matter |
| fzf, bat, jq | Selection, source viewing, structured-data processing | Composable workflows outside the book shell | SOL must still supply stable IDs and safe exports |

## prompt_toolkit: improve the shell we already have

`PromptSession` supports custom completion, validation, multiline input, Vi or
Emacs editing, and a bottom toolbar. `FileHistory` can persist entered commands.
SOL now uses the input-only subset for virtual-path completion, recalling searches,
entering notes, and displaying path and actor. Command history is not saved
reading position or annotation storage. [Prompt documentation](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html)

Its full-screen layouts could also support a reader and input line, but we would
assemble the layout and focus behavior ourselves. Background output must
cooperate with the renderer rather than print over an active prompt. Its test
facilities offer simulated input and dummy output.
[Full-screen applications](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/full_screen_apps.html),
[testing](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/advanced_topics/unit_testing.html)

The implemented first stage replaces only the input/completion boundary.
It keeps existing command semantics and a simple input fallback, improving input
without turning SOL into a full-screen dashboard.

## Rich: improve presentation without changing the book

Rich supplies Markdown rendering and terminal-aware output, with structures such
as tables and trees. It could render canonical emphasis, separate passage prose
from metadata, and present a compact comparison. Live displays and layouts can
redraw regions, but they do not supply application focus or persistence.
[Markdown](https://rich.readthedocs.io/en/latest/markdown.html),
[console](https://rich.readthedocs.io/en/latest/console.html),
[live displays](https://rich.readthedocs.io/en/latest/live.html),
[layouts](https://rich.readthedocs.io/en/latest/layout.html)

Use it selectively, not as a reason to surround every paragraph with borders.
Literal passage and annotation text must not accidentally become Rich markup.
Also, `NO_COLOR` removes color, not every style: SOL’s `--plain` needs its own
unformatted path. [Console behavior](https://rich.readthedocs.io/en/latest/console.html)

Rich and prompt_toolkit could coexist, but their output boundaries would need
coordination. Adding both immediately would make it harder to identify which
change actually improves reading.

## Textual: a reading desk rather than a command transcript

Textual provides Tree, Markdown/MarkdownViewer and TextArea widgets, keyboard
bindings, a command palette, reactive application state, and workers. These
are promising components for a hierarchy pane, passage pane, annotation editor
and source-review queue. Reactive state synchronizes a running interface; it
does not persist a scholarly workspace.
[Tree](https://textual.textualize.io/widgets/tree/),
[MarkdownViewer](https://textual.textualize.io/widgets/markdown_viewer/),
[TextArea](https://textual.textualize.io/widgets/text_area/),
[input](https://textual.textualize.io/guide/input/),
[command palette](https://textual.textualize.io/guide/command_palette/),
[reactivity](https://textual.textualize.io/guide/reactivity/),
[workers](https://textual.textualize.io/guide/workers/)

SOL would need to move from a blocking command loop to widgets, events and focus
management. Textual’s headless testing tools can exercise interaction and screen
sizes, which would be valuable for that larger change.
[Testing](https://textual.textualize.io/guide/testing/)

Its Markdown widget defaults to a `gfm-like` parser and permits a custom parser
factory. It can report link clicks instead of opening links automatically.
Neither feature proves compatibility with SOL’s CommonMark records, UUID anchors,
note relationships, or mathematical HTML. Those require an adapter and tests.
[Markdown widget](https://textual.textualize.io/widgets/markdown/)

I would choose Textual when simultaneous reading, comparison and source inspection
become useful enough to justify a full-screen desk. It need not replace the
pipe-friendly CLI or command shell.

## “cursus”: assuming Python curses

I have treated “cursus” as a possible reference to `curses`; a different project
would need its own link and investigation. Python curses provides windows, pads,
screen updates and keyboard handling. `curses.wrapper` helps restore the terminal
after the application exits or fails.
[Python curses HOWTO](https://docs.python.org/3/howto/curses.html)

This is attractive if the aim is to learn terminal primitives. For SOL as a
reader, it would leave us building more of the Markdown presentation, completion,
layout and interaction infrastructure. It is not itself a terminal emulator.

## Frogmouth: study an existing reader

Frogmouth is a Textual-based Markdown browser with file/URL reading, a contents
view, navigation history and bookmarks. It offers concrete interaction ideas,
but its document-oriented bookmarks are not a substitute for SOL’s corpus-scoped
paragraph references and attribution.
[Frogmouth](https://github.com/Textualize/frogmouth)

Its current project file pins Textual to `0.53.1`. Modern Textual features should
not therefore be assumed to exist in Frogmouth. That pinned Markdown renderer
also has its own heading-anchor and image behavior; SOL’s paragraph UUID anchors
need explicit compatibility checking.
[Dependency declaration](https://github.com/Textualize/frogmouth/blob/main/pyproject.toml),
[pinned Markdown implementation](https://github.com/Textualize/textual/blob/v0.53.1/src/textual/widgets/_markdown.py)

## Glow: an external Markdown presentation layer

Glow renders files or standard input, supports wrapping and paging, and offers
a Markdown file browser. It could be an optional viewer without becoming a SOL
dependency. Its default browsing configuration excludes hidden/ignored files,
so the ignored `local-corpus` should be opened explicitly rather than relying on
discovery. [Glow](https://github.com/charmbracelet/glow)

Use canonical Markdown, not `--plain`, when testing emphasis. A renderer cannot
recover italics already discarded from its input. Glow’s underlying image
rendering produces textual image/link information; running it in kitty does not
automatically turn those links into facsimiles.
[Glamour image renderer](https://github.com/charmbracelet/glamour/blob/master/ansi/image.go)

## mdcat: worth testing for the source-review desk

The original `swsnr/mdcat` repository is archived. The maintained BIRSAx2 fork
documents footnotes, inline images, and inline/display math rendered through
kitty or iTerm2 image protocols, with Unicode fallback. Its changelog records
the maintenance transfer and the addition of these features.
[Original repository](https://github.com/swsnr/mdcat),
[maintained README](https://raw.githubusercontent.com/BIRSAx2/mdcat/main/README.md),
[changelog](https://raw.githubusercontent.com/BIRSAx2/mdcat/main/CHANGELOG.md)

That is a promising later experiment, not a tested SOL integration. Its Markdown
footnotes need not match SOL’s attributed note records. Math rendering also cannot
repair an incorrect transcription. Check the installed implementation/version;
ordinary `less` pagination can disable image output.
[Pagination changes](https://raw.githubusercontent.com/BIRSAx2/mdcat/main/CHANGELOG.md)

Kitty’s image protocol and `icat` could eventually support a separate source
facsimile view. The viewer and interface must cooperate with terminal graphics;
the terminal choice alone is insufficient.
[icat](https://sw.kovidgoyal.net/kitty/kittens/icat/),
[graphics protocol](https://sw.kovidgoyal.net/kitty/graphics-protocol/)

## Small shell tools remain useful

`fzf` selects text rows and supports previews. SOL could supply rows containing
an opaque ID, a location and an excerpt, then reopen the selected ID. Fuzzy
selection is not conceptual search. Preview commands must not execute annotation
or passage text as shell code. [fzf](https://github.com/junegunn/fzf)

`bat` is useful for viewing the canonical Markdown source with syntax highlighting
and paging, rather than rendering its scholarly meaning.
[bat](https://github.com/sharkdp/bat)

`jq` can inspect JSON/JSONL records and select metadata. SOL’s passage JSON now
includes the canonical record under `canonical`, so scripts can obtain Markdown,
attribution and all source references without reverse-engineering decorated
terminal output. [jq manual](https://jqlang.org/manual/)

## Recommendation and experiment criteria

Keep continuity and scholarly data durable behind an interface-independent
workspace API. The optional prompt_toolkit input stage is now implemented for
the shell. Consider Rich for a small
presentation experiment; consider Textual when the reading desk actually needs
multiple visible panes. Treat external viewers as replaceable tools, not sources
of passage identity.

Before adopting any renderer, test the same small set of synthetic and local
records: emphasis, quotation, lists, notes, two-page provenance, UUID links,
superscripts/subscripts, a checked formula, and an unreviewed formula. Compare
with the source where needed. Test a narrow terminal, resizing, interruption,
Unicode, no color, redirected output, and a genuinely escape-free plain mode.

Keep the book local by default; do not enable remote image/link retrieval merely
because a viewer supports URLs. Assess keyboard-only operation and screen-reader
behavior separately: keyboard focus support does not establish accessibility.
No framework should make SOL’s data unreadable to scripts, agents, or a human
using the canonical Markdown.

## 12 October 2026: the implemented input-first stage

The workspace foundation is now implemented, including structured diagnostics,
review queues, backups and historical resume. `run_shell` also accepts an injected
`read_command(prompt)` and a `write_output` function with `print`'s calling
convention, including `end=`. Supplying a custom reader bypasses standard-library
readline setup. `sol_prompt.py` now implements an optional PromptSession adapter
through this seam. The `shell` extra supplies prompt_toolkit; the base reader still
has no third-party dependency. Rich and Textual have not been adopted. Existing-note
editing is now available through the same input seam, backed by versioned snapshots
and conflict-aware saves rather than editor-only state.

`sol` and `--shell` now open a persistent reader. Onboarding asks only for missing
workspace and actor labels; supplying both flags permits noninteractive command
input. `-n` bypasses workspace and profile storage, and `-r` explicitly retains
the one-shot random quote. Actor labels are local attribution, not authentication;
`sol_profiles.py` stores them separately from workspace databases. Missing workspace
labels now offer a read-only catalog of up to ten matching workspaces, ordered by
latest recorded activity. Typing a displayed number selects it, while a name creates
or opens a workspace. `-n` and `-r` consult neither the catalog nor actor registry.

### Start with an optional prompt, not a new application

The `PromptSession` adapter improves command input and custom completion while
leaving the synchronous command loop, workspace operations and existing string
renderers intact. Completion should understand command position, virtual paths
and saved names. It must tolerate unfinished quoting and must not write reading
state merely because a suggestion is displayed. Keep validation and persistence
in SOL's existing operations. The implemented completer captures virtual paths,
record IDs and saved names before prompting; keypress callbacks do not access
SQLite or create checkpoints. The toolbar exposes the current path and actor.
[Prompt documentation](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html)

Print each result after the command prompt returns, before asking for the next
command. If callbacks later need output while a prompt is active, use the documented
`run_in_terminal` or `patch_stdout` mechanism rather than printing across its
redraws. A future Rich renderer needs the same coordination; adding Rich `Live`
would introduce another redraw owner and is not needed for this input experiment.
[Application API](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/reference.html#prompt_toolkit.application.run_in_terminal),
[async prompting](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html#asyncio),
[Rich live display](https://rich.readthedocs.io/en/latest/live.html)

The current local operations do not need an async rewrite. Prompt-toolkit supports
asyncio if later work justifies it. Complete from loaded data or immutable saved-name
snapshots; do not send SOL's live SQLite connection into a threaded completer.
An enhanced input path must remain offline and must not implicitly enable a host
system prompt or external editor.
[Asyncio documentation](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/advanced_topics/asyncio.html),
[prompt API](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/reference.html#prompt_toolkit.shortcuts.PromptSession)

### Keep drafts and history separate from scholarly records

The implemented command prompt uses in-memory history, never `FileHistory`.
`FileHistory` stores
entered strings in a separate plaintext file, so commands containing annotations,
review issues or relation rationales can duplicate private work outside SQLite.
Its implementation uses the supplied filename verbatim and appends to it; SOL
would need to supply an expanded absolute path, arrange permissions and decide
what can be persisted. A later opt-in history policy should filter at the history
writing layer, not try to scrub a sensitive command after execution.
[History API](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/reference.html#prompt_toolkit.history.FileHistory),
[official implementation](https://github.com/prompt-toolkit/python-prompt-toolkit/blob/main/src/prompt_toolkit/history.py)

Multiline `note draft [--on ID]` is now implemented for new annotations. Enter
inserts a newline; SOL's explicit Ctrl-S binding accepts the draft and Ctrl-C
cancels it. This is a SOL binding, not a claim about every toolkit application's
default keys. The target UUID, actor and inspected text digest are captured before
drafting. The accepted body is passed as data, without reconstructing a shell
command. A DummyHistory buffer is reset after use. Save rechecks the target and
corpus generation before one insert; cancellation changes neither authored
records nor the reading checkpoint. Basic input retains `note add "TEXT"`.
`note edit NOTE_ID` reuses this isolated draft input with the existing body as its
initial value. The workspace captures the original actor, target, source binding
and note revision first. Ctrl-S commits only if these remain valid; Ctrl-C discards
the draft. Basic input requires an explicit `--expect-revision N` alongside the
replacement text. Editing does not silently retarget the note or move a checkpoint,
and an identical body produces no new revision. `note history NOTE_ID` exposes the
stored snapshots independently of the editor.

New workspaces use schema version 2 for annotation audit. Older version-1 workspaces
still open unchanged for ordinary work; editing requires an explicit upgrade into
a separately named copy. `workspace upgrade FILE.sqlite3` does not switch an open
session. Legacy notes gain a baseline of their current body at upgrade, not an
invented sequence of earlier edits or an inferred editor.
[Multiline input](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html#multiline-input),
[DummyHistory](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/reference.html#prompt_toolkit.history.DummyHistory)

### Preserve the linear fallback and test before adoption

The adapter selects basic input before importing prompt_toolkit when
streams are not interactive, `TERM=dumb`, or an escape-free transcript is wanted.
`--ui auto` is the default; `--ui basic` selects the fallback. In an eligible
interactive terminal, `--ui prompt` requests the optional adapter and reports a
missing shell extra instead of silently ignoring it. `--editing-mode` selects
Emacs or Vi keys. Even explicit prompt mode respects plain output, redirected
streams and `TERM=dumb`.
Do not seek another TTY to evade redirected stdin. The library's input API has
an explicit TTY-preference option; SOL need not enable it.
[Input implementation](https://github.com/prompt-toolkit/python-prompt-toolkit/blob/main/src/prompt_toolkit/input/defaults.py)

The PromptSession adapter is covered by command/workspace and injected-input
tests for completion, ephemeral history, resource cleanup, drafts and cancellation.
It must continue to pass the same command and workspace tests as the
simple adapter, plus injected-input tests for Unicode, quoting, completion,
interrupts, EOF, draft acceptance and cancellation. Check that sensitive bodies
never reach persisted history and that a changed corpus generation or competing
workspace save still refuses the operation. Output and storage callbacks must not
turn completion, focus or redraw into a visit or an authored assertion. The
standard-library install, plain/JSON CLI and no-network behavior remain gates.
[Prompt-toolkit testing](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/advanced_topics/unit_testing.html)

Keyboard operation and assistive-technology compatibility require separate
evaluation. The reviewed framework documentation does not establish a
screen-reader guarantee. GitHub's own CLI investigation found repeated visual
redraws and spinners could confuse speech interpretation. Keep static labels and
a linear fallback; test with actual users and screen readers rather than treating
no color or keyboard focus as proof of accessibility.
[GitHub's accessibility investigation](https://github.blog/engineering/user-experience/building-a-more-accessible-github-cli/)

### Textual remains a later, measured choice

Consider Textual when a real workflow needs two comparison passages, an annotation
draft and source-review metadata visible together. Its focus, key bindings and
TextArea can support that desk, but keyboard combinations depend on the terminal
and operating system. Headless Pilot tests would supplement, not replace,
manual accessibility and terminal tests.
[Input and focus](https://textual.textualize.io/guide/input/),
[TextArea](https://textual.textualize.io/widgets/text_area/),
[terminal key limitations](https://textual.textualize.io/FAQ/#why-do-some-key-combinations-never-make-it-to-my-app),
[testing](https://textual.textualize.io/guide/testing/)

Better completion or occasional notes alone do not justify an application rewrite.
Before a multi-pane interface, retain safe drafts and audited annotation revisions,
then prioritize explicit import/restore previews and verified selected-span anchors. Neither
an interface nor a classifier may silently create semantic edges, claim a source
was verified, or turn version-1 text/PDF fingerprint matches into full-record
provenance proof. Those decisions remain in the corpus and workspace contracts.
