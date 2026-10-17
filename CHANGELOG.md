# Changes

## Unreleased

The reader remains the default `sol` interface. This cleanup separates startup,
onboarding, command validation, book-shell behavior and text rendering. Reader
and shell selection now have distinct internal execution modes; contradictory
`--reader --shell` flags are refused explicitly.

Workspace bookmark, annotation, comparison, review and relation writes have
service methods independent of shell argument parsing. Existing workspace
schemas, histories and author/source guards are retained.

Terminal text escaping and POSIX view utilities have shared owners. One-shot
source prose is escaped when displayed in a terminal, while raw piped output
retains its text. Selecting a PDF with `--set-corpus` explains the required
conversion and directory selection.

CORE adds bounded capture/check batch APIs using ordinary version-1 reference
envelopes. HTML and Neovim sample exports capture their passages and linked notes
together, retaining final generation and rendering checks.

Canonical Markdown reads preserve newline bytes for hashing. JSONL uses LF
record boundaries and permits Unicode line separators within JSON strings.
Corpus indexing and reader typography share a dedicated Markdown semantics
module instead of importing the validator's private parser helpers.

Public corpus fixtures, source-archive checks and GitHub Actions improve the
repeatability of development. The source archive includes the research adapters
needed by its tests; the installed wheel still contains application modules only.
