# Codex proposal: dependable reading and scholarly work

**Status:** Proposed for review. No implementation is authorized by this document.

**Prepared:** 17 October 2026, by Codex, preserving the implementation plan from the preceding ChatGPT review.

**Reviewers:** the maintainer, ChatGPT, Claude Code and Codex.

**Proposal branch:** `codex/reader-workspace-proposal`.

**Current code baseline:** `dfe075a9ce861fd7f3bafdeb901471452e77a071`, containing application changes through `92fa35fe1ec4588ef19cb583501073966a9e67e5`.

**Original review baseline:** `d817714`, before Claude's subsequent rebase and sentence-study work; the search change now appears as `1eec2b8` in the shared history.

This is a reviewable implementation proposal within the existing coordination
system. It neither supersedes the four authorities nor assigns the next active
task. The governing documents remain [Architecture](../../ARCHITECTURE.md),
[BEING](../../BEING.md), [CORE](../../CORE.md) and [ESSENCE](../../ESSENCE.md).
Historical evidence remains in the [legacy archive](../../legacy/README.md).

## Coordination and integration

Read [CLAUDE.md](../../../CLAUDE.md), [CURRENT_TASK](../CURRENT_TASK.md) and the
latest [handoff report](../HANDOFF.md) before acting. Claude's coordination
introduction was merged through PR #1 as `dfe075a` while this proposal was being
prepared. Its later contribution-policy clarification, `59602dd`, was present
on `claude/coordination-workflow` but was not an ancestor of this baseline.
This proposal does not copy, replace or merge that follow-up.

The live working copy remains on Claude's branch. This proposal was prepared in
a separate linked worktree, branching from the fetched `origin/main`. Only this
proposal and its handoff report are intended changes. `CLAUDE.md`,
`CURRENT_TASK.md`, the four authorities, the archive and `AGENTS.md` stay as found.

For integration:

1. Review this proposal's pull request against `main`. Merging the proposal
   preserves a backlog; it does not approve every stage for implementation.
2. The maintainer chooses one bounded task, resolves its blocking decisions,
   and records it in `CURRENT_TASK.md` using the existing template. A candidate
   first task is supplied below, but is not installed as the active task.
3. Assign an implementer and a separate implementation branch. Preserve the
   branch/PR/review/maintainer-merge procedure. This PR does not redefine agent
   roles or grant an agent authority to approve its own design decisions.
4. Before each stage, compare this baseline with current code, tests and
   handoffs. Mark completed work explicitly instead of recreating it.
5. Each implementation PR updates the relevant authority and changelog when
   behavior changes, runs its checks, and records a short handoff. Keep this
   proposal accessible even when individual stages move into task history.

The existing `CURRENT_TASK.md` still describes the coordination task as
`In review`. Its lifecycle and next assignment remain with the maintainer.

## Original recommendation and progress

The recommendation was to make the existing reader dependable enough for
sustained annotated reading, then connect it to one complete ESSENCE
investigation. The separation between canonical text, semantic positions,
workspace operations and Neovim presentation was sound and remains the basis
of this proposal.

At the original review, the implemented progress was:

- Terminal, Dark and Paper themes through presentation settings.
- Fingerprint-checked printed-source crops through `s`, without Kitty.
- Attributed passage notes through `a` and the existing workspace service.
- Full footnote bodies and inline callouts.
- Verified search-match highlighting.
- A private audit covering mathematics corrections to 30 records; all 47
  mathematics-containing records still pending visual review. These were
  corpus-maintenance observations, not independently certified transcriptions.

The original review identified four concrete deficiencies:

- Failed next-view preparation could leave the saved position at the destination
  while the screen retained the previous passage.
- Escape dismissed search marks, but switching reading mode restored them.
- The reader omitted the stale-source warning and revision information that
  the shell provided for personal notes.
- Footnote styles were prepared but discarded by the context popup; further
  note links inside seven private footnote-body records were not conveniently
  accessible. That count was an observation of the private corpus at review time.

The original verification was 1,527 tests run successfully, including 11 skipped,
plus the documentation check and synthetic failure probes. It included no
manual terminal reading trial. Those results describe that earlier baseline,
not an automatic acceptance of later work.

### Reconciliation with Claude's newer work

| Area | Current evidence | Effect on this plan |
| --- | --- | --- |
| Sentence-length method | `d43e09b` adds `sol analyze sentences`, declared punctuation rules, source offsets/digests and recomputation through `sol analyze check`. | Stage 7's first method exists. Preserve it and evaluate it; do not build a duplicate. |
| Reader inquiry round trip | `04dcebc` adds `S`, a loaded-section study, owner-only artifacts for persistent sessions, result opening and history return. | The first in-process, terminal-independent round trip exists. Stage 7 now concerns correctness and acceptance before broader integration. |
| Authority updates | `92fa35f` records the above, the pending mathematics review, and remaining segmentation and UX limits. | Use these newer statements rather than the original plan's future-tense feature claims. |
| General investigation interface | The Kitty exchange remains the cross-terminal path; durable research context and a general experiment interface remain proposed. | Keep these distinct from the implemented `S` workflow. |
| Method choice | The original plan preferred an established segmentation tool; the implemented method is the explicitly declared `punctuation-rules-v1`. | Retain the baseline while evaluating a human-checked sample. A method/dependency replacement requires a separate decision and versioned output. |

### Rechecked deficiencies at the current baseline

Disposable synthetic probes were rerun from the isolated proposal worktree,
using existing corpus fixtures and isolated XDG config/data/cache/state paths.
They changed no application files or personal data:

| Probe | Observed result | Proposed response |
| --- | --- | --- |
| Fail `neovim.build_payload` while accepting `passage_next`. | An error is returned, but the workspace's saved passage changes. | Stage 1: validate the destination before committing its navigation. |
| Hide an inline search mark with Escape, then toggle reading mode. | Mark count changes `1 -> 0 -> 1`. | Stage 2: retain dismissal as transient presentation state. |
| Display a synthetic note bound to an older content digest. | Shell warns; reader payload contains only `id`, `author`, `created_at`, `lines`. | Stage 3: expose revision and source-binding status. |
| Move natively to another paragraph within the loaded section, then request `sentence_study`. | The supplied study origin remains Python's earlier passage rather than the live request's paragraph. | Stage 7: derive origin from the verified request without creating a navigation checkpoint. |

These probes identify reproducible failure cases; they are not fixes or manual
reading acceptance. The new study-origin case supplements the preserved plan.

## Technical decisions carried forward

These are proposed implementation choices within the existing authority
constraints. A proposal cannot approve a public-contract or policy change.

1. Keep the single isolated Neovim reader and its inherited private action pipes.
   Ordinary capable terminals remain supported; Alacritty is the main manual
   acceptance host and Kitty is an optional integration host.
2. Keep canonical Markdown and generated JSONL separate from presentation.
   Wrapping, themes, callouts, headings and search marks may not change source
   strings, UUIDs, content digests or semantic codepoint offsets.
3. Reuse CORE API/reference v1, strict generation validation and the existing
   `TextSelection` identity. Preserve requested/retired IDs, exact half-open
   Unicode spans and source bindings. Do not substitute buffer positions,
   screen cells, fuzzy matching or a second selection scheme.
4. Keep workspace schema 3 and supported legacy behavior for stages 1–6.
   Existing actor, freshness, expected-revision and backup/upgrade guards apply.
   Durable selected-span work requires a separately approved compatibility plan.
5. Route notes and review testimony through `WorkspaceReader` services, not SQL
   from Lua or reconstructed shell command strings. Viewing, search, styling
   and completion must not create visits or attributed claims.
6. Preserve the 64-record/chapter loading boundary, paragraph/continuous modes,
   passage-local selection, three markers and source-based resume. A general
   whole-book buffer is not part of this proposal.
7. Keep source previews tied to the fingerprint-checked PDF. Workspace testimony
   cannot clear canonical review flags or certify image/metadata fields outside
   its current binding. Unverified converter image assets stay outside that path.
8. Reuse shipped ESSENCE methods and artifacts before generalizing the bridge.
   Keep computations and reader assertions distinguishable. Model output grants
   no authority to author notes, relations or canonical corrections.
9. Integrate mature analytical tools where justified. Do not change the current
   dependency set or method version without review, silently download models,
   or introduce NLP/ML runtimes into ordinary reader startup or CORE imports.
10. Keep the scope to the audited Cambridge/di Giovanni book. Preserve all
    private corpus, PDF, crop, workspace and result files outside Git and packages.

## Stages, dependencies and acceptance

The seven stages below preserve the original implementation order and wording.
Newer implementation is identified beside the relevant stage. They are a backlog
for review, not seven simultaneously active assignments.

| Stage | Dependency | Authority |
| --- | --- | --- |
| 1. Navigation failure recovery | Maintainer assigns a bounded implementation task. | BEING §§2–3, 8; CORE §§5–7 |
| 2. Transient reader state | Stage 1's transition/reload semantics settled. | BEING §§2, 4, 8; CORE §5 |
| 3. Personal notes | Stages 1–2; reuse existing annotation services. | BEING §§3, 7–8; CORE §7 |
| 4. Book footnotes | Stages 1–2; stage 3's panel separation where useful. | BEING §§2, 4, 7; CORE §§2, 5 |
| 5. Sustained reading acceptance | Before/after observations throughout; final pass after stages 1–4. | Architecture §§1, 6; BEING §§4, 8 |
| 6. Source review | Stages 1–4 and source/viewer evidence from stage 5. | BEING §§3, 5, 8; CORE §§3, 7 |
| 7. ESSENCE round trip | Existing study already shipped; correctness can be checked alongside stage 1, expansion follows stages 1–6. | Architecture §6C; BEING §6; ESSENCE §§3–5, 8 |

### 1. Fix navigation failure recovery first

**Original proposal:** Prepare and validate the destination before committing
its reading transition. Add failure tests for payload preparation, stale sources
and workspace conflicts. A refused move must leave the displayed and saved
reading contexts coherent.

**Implementation boundary:** `sol/terminal/neovim_reader.py`,
`sol/reader/actions.py` only where the existing action boundary needs support,
and their focused tests. Stage a candidate destination and validated view before
the existing guarded commit. Avoid saving outgoing and destination checkpoints
as independent side effects that make a failed request appear successful.
Do not roll back a concurrent author's committed work or bypass compare-and-swap.
Editor-side failure after publication needs an explicit recovery behavior;
prevalidation alone is not proof of atomicity across Python, SQLite and Neovim.

**Acceptance:** injected projection/CORE/storage failures do not leave an
unacknowledged destination as the saved current passage; the reader can retry or
quit coherently; search/history/marker/tree/study moves retain source identity;
successful navigation preserves meaningful history and reopens at its accepted
UUID/codepoint. Include a competing workspace save and stale-generation refusal.

### 2. Stabilize transient reader state

**Original proposal:** Make highlight dismissal survive mode/focus changes and
resizing. Check selections and cursor restoration alongside inline footnote
callouts. These changes should preserve all existing source offsets.

**Implementation boundary:** `sol/terminal/neovim.lua`, the controller's
presentation payload and relevant typography/motion tests. Represent dismissed
marks consistently when reloading a disposable view; keep that state transient.
Preserve native word wrapping and semantic emphasis under search styling.

**Acceptance:** Escape then `p`, `f`, resize or a theme switch cannot resurrect
dismissed marks. A deliberate new result may reveal them again. Forward/reverse
selection and `y` return exact source slices around callouts, multibyte characters,
combining marks and wrapped emphasized text. Verify both reading modes and
reopen at a different width. No new workspace fields or canonical strings.

### 3. Complete the personal-note workflow inside the reader

**Original proposal:** Let users select a note from `c`, view its revision
history and edit it through `prepare_annotation_edit` and
`save_annotation_edit`. Show author, revision and stale-source status. Audited
notes currently prohibit deletion; removal needs an explicit retention policy
before implementation.

**Implementation boundary:** the existing Lua note editor, controller panel
actions, `WorkspaceReader.prepare_annotation_edit` /
`save_annotation_edit`, and annotation-history reads. Preserve `a` as add, and
distinguish personal notes from the edition's notes. Use the note's existing ID;
do not introduce a parallel identity or retarget an old note on edit.

**Acceptance:** the original actor can edit an identified note; another actor,
a competing revision, changed source or changed corpus is refused. A no-op save
adds no revision. Retired references and stale bindings are disclosed; history
retains earlier bodies and the original inspected digest. Failed saves keep
recoverable process-local drafts and preserve reading position/selection.
Temporary sessions refuse durable notes. Legacy workspaces retain their explicit
separate-copy upgrade requirement. Drafts are not described as restart-persistent.

### 4. Give book footnotes a proper reading view

**Original proposal:** Open an individual footnote without scrolling through
all implementation metadata. Preserve emphasis, attribution, warnings and nested
links, with a reliable return to the original cursor. Reuse existing canonical
note IDs.

**Implementation boundary:** `sol/reader/surface.py`, `sol/reader/typography.py`,
`sol/terminal/neovim.py` and the Lua panels. Reuse the new direct
`note_paragraph` loading, ordered by canonical `order`; do not regress to displaying
the container heading. Resolve further note links through the same verified
canonical graph with explicit bounds and cycle handling. Keep callouts as display
marks. Separate source notes, personal notes and technical context visibly.

**Acceptance:** multi-paragraph footnotes retain style offsets, numbering,
attribution and review warnings; nested/unresolved references have clear outcomes.
Opening/closing a note restores cursor, selection and reading mode. Narrow-window
and wrapped-callout cases retain exact prose selection and clipboard content.
No note navigation creates fabricated Hegel prose, new IDs or verification claims.

### 5. Run a sustained reading acceptance pass

**Original proposal:** Exercise a substantial chapter in Alacritty at narrow
and wide sizes, across the three themes. Include notes, search, source viewing,
clipboard, resize and reopen. Use observed interruptions to adjust spacing,
status hints and popup size. Automated checks cannot settle reading comfort.

**Implementation boundary:** small evidenced presentation changes inside the
current adapter; acceptance observations in BEING and the task handoff. Compare
the same chapter with the historical prompt_toolkit surface if needed; it remains
a research comparison, not another installed reader. A 30–45 minute session is
an invitation for useful evidence, not an automated completion claim.

**Acceptance:** human observations at 80x24 and a wider terminal cover long prose,
several italic spans, `j/k`, `b/n`, Ctrl-D/U, `gg/G`, markers, tree, context/focus,
search/return, `a` including physical Ctrl-S and `:w`, source preview, selection,
clipboard and quit/reopen. Record interruption, recovery effort and one concrete
correction. Check optional Kitty and unknown-terminal underline/no-color fallbacks
separately. Record skipped/unavailable hosts honestly. Keep private reading notes
local; publish only nonprivate observations. Do not equate programmed keys with
human acceptance.

### 6. Bring source review into that workflow

**Original proposal:** Allow attributed inspection or correction-needed
testimony from the source/context view through the existing review service.
Human verification of the retyped mathematics remains necessary; displaying a
crop must never clear a canonical warning automatically.

**Implementation boundary:** expose the existing `WorkspaceReader.record_review`
and read-only queue/inspection functions in reader panels. Retain PDF fingerprint,
record, printed/PDF pages, declared source rectangles and existing testimony
binding. Keep reviewed canonical corrections as explicit Markdown maintenance
followed by reindexing; a workspace operation cannot perform that promotion.

**Acceptance:** viewing evidence adds no review; explicit testimony records
actor, issue, outcome and the currently supported text/PDF binding. Missing or
changed PDF and stale corpus/record refusals remain visible. Demonstrate mixed
math and an unreviewed complex passage, plus reviewed/corrected examples only
when a human has actually supplied them. The 30 retyped records are not marked
reviewed by an agent; all private text, audit data and crops stay outside Git.

### 7. Build the first terminal-independent ESSENCE round trip

**Original proposal:** First exercise the connection using the existing term
study. Then implement the planned sentence-length experiment using an established
segmentation tool, explicit inputs and a versioned artifact. Support both returning
to a result's source and resuming the original reading position.

**Current status:** the sentence-length method and reader round trip have since
shipped. Preserve this original objective and the alternative lexical smoke test,
but do not recreate either method or replace `punctuation-rules-v1` silently.
The immediate work is validating the existing implementation, including the
live-origin discrepancy above, and assessing segmentation error before deciding
whether an established external segmenter is needed.

**Implementation boundary:** `sol/essence/sentences.py`, `sol/essence/cli.py`,
the reader's study panel/result actions and existing sentence-study tests. Use
the verified request's current UUID for the computation origin without saving a
visit just to run analysis. Keep loaded-section scope explicit, including sections
split at 64 records. Saved artifacts must disclose input order, digests, method,
parameters/versions, exclusions and strict generation binding. A computation
artifact is separate from a CORE navigation envelope and authored workspace work.

**Acceptance:** natively move to a different paragraph before `S`; its artifact
names the actual origin. Opening a result and Alt-Left returning restore the
correct source cursor and selection, including same-passage results. A cancelled
or failed study does not move reading position. Persistent-session artifacts
remain owner-only and non-overwriting; temporary sessions publish none. Verify
artifacts with `sol analyze check`; reject tampering, changed corpus, bad scopes,
Unicode-offset errors and interrupted writes. A declared human-checked sample
reports segmentation errors, including the known mid-sentence-parenthesis case.
Any subsequent method comparison uses the same sample and a separately versioned
method/artifact. Formal syntax, general external process handoff, durable research
context and embeddings remain separately reviewed work.

## Cleanup alongside the stages

The original proposal also recommended extracting cohesive popup/editor
functions from the roughly 1,000-line Lua adapter and removing repeated
typography parsing as those areas change. Larger performance changes should
follow measurements. Durable span annotations, independent distributions and
additional reader engines were explicitly deferred.

Apply that cleanup incrementally: preserve one owner for semantic state, one for
workspace writes and one for visual presentation. Share already prepared
typography/callout data rather than parsing twice. Prefer a small panel helper
where it removes repeated logic; avoid a new generic framework or broad rewrite.
Measure startup, section transitions, note-heavy views and study latency before
adding caches. Caller-mutable CORE collections prohibit caching trust without
an invalidation design. Preserve current generation checks during optimization.

## Common verification and delivery gates

- Add meaningful regression coverage for each accepted behavior, using synthetic
  fixtures. Run focused checks, then the documentation checker and normal suite:
  `.venv/bin/python -B scripts/check_docs.py` and
  `.venv/bin/python -B -m unittest discover -s tests`.
- Isolate `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`,
  `XDG_STATE_HOME` and `NVIM_LOG_FILE` for tests and probes. Do not open personal
  workspaces or download models as test setup. Opt-in desktop checks use owned
  temporary windows and report their actual execution mode.
- Confirm Unicode/codepoint identity, canonical nonmutation, CORE generation
  guards, workspace author/revision checks, legacy reopen, archive integrity and
  package privacy for affected areas. Run packaging checks when adding Lua assets
  or moving modules; do not package private corpus or study outputs.
- Report automated results, programmatic real-host results, human reading
  observations and remaining limits separately. A passing suite cannot clear a
  human acceptance gate or certify transcription.
- Stage only task-related files. Leave synced `sources/` and untracked
  `AGENTS.md` untouched. Use small commits with a `Co-Authored-By` trailer, push
  the implementation branch, open a PR and leave merging to the maintainer.
- Keep the four authorities current with verified behavior; preserve the legacy
  archive. This operational proposal does not add a fifth design authority.

## Outstanding questions and decisions requiring approval

| Question | Proposed interim treatment |
| --- | --- |
| Which agent implements the next task, and who may update `CURRENT_TASK.md`? | Maintainer assigns one task and owner. The existing Claude/ChatGPT role description does not yet define Codex's standing role. This proposal does not change it. |
| Should dismissed search marks reappear on deliberate result navigation? | Proposed: yes for an explicit new/next result; no for mode/focus/theme/layout changes. Confirm during stage 2 review. |
| Which note-selection/edit/history bindings belong in `c`? | Review a compact interaction before binding keys; preserve marker-number shortcuts and `a` for adding a note. |
| Can an audited note be hidden, retracted or deleted? | Preserve the current no-deletion rule. A retention/retraction policy and any schema change need explicit approval. |
| Should unpublished note drafts survive restarting SOL? | Keep honest process-local recovery; durable private drafts require a separately reviewed storage/lifecycle design. |
| When should selected spans become durable? | Defer schema v4 and quotation/version binding until the maintainer approves a compatibility design. Do not silently store span notes as whole-passage notes. |
| Are agent-retyped mathematical transcriptions acceptable pending human review? | Preserve the current audited, flagged corpus and source crops. The coordination handoff explicitly leaves this policy for maintainer approval. |
| What review sample and error tolerance make sentence segmentation useful? | Specify a hand-checked sample before changing the method; disclose errors and translation scope. No new dependency or method version is approved here. |
| Should study scope be the loaded section, full chapter, paragraph or selected span? | Keep the shipped loaded-section scope. Smaller spans/full-chapter expansion require an explicit scope policy; a 64-record section is not always a whole chapter. |
| When is a general terminal-independent external investigation interface justified? | Accept the existing in-process `S` loop first. A persistent context or new cross-process result contract needs its own bounded task and review. |
| Do comparisons/relations need frozen endpoint quotations or new bindings? | Preserve current live-reference behavior and disclose it. Design endpoint versioning before claiming historical quotation fidelity. |

Embeddings/UltraBERT/Projector, new NLP methods, universal PDF import, multiple
books/translations, a second reader engine, independent distributions and
CONCEPT/NixOS work are outside the next bounded reader task. Their longer-term
direction remains in the authorities rather than being silently removed.

## Candidate first task for maintainer assignment

This is a draft for review, not a replacement for `CURRENT_TASK.md`.

**Title:** Preserve reading state when navigation is refused.

**Status:** Proposed; maintainer changes to `Ready` only when assigned.

**Implementer / branch:** to be assigned on a separate task branch.

**Authority:** BEING §§2–3, 8 and CORE §§5–7.

**Goal:** an unsuccessful destination preparation or guarded save leaves a
coherent current screen, saved reading position and return history.

**Scope:** stage 1 above, its regression tests, and the relevant authority and
changelog updates describing verified outcomes. Include `study_open` among the
existing navigation routes. Capture other findings as follow-up tasks unless
they are necessary for this acceptance criterion.

**Constraints:** keep canonical text, source offsets, UUIDs, CORE/reference v1,
workspace schemas, actor/revision guards, 64-record loading and the single
Neovim frontend unchanged. Do not resolve failure by force-saving, automatic
reconversion or rolling back another session's work.

**Acceptance:** reproduce the injected next-payload failure before fixing it;
then cover preparation failure, stale generation, competing workspace save,
successful retry, history return and reopen. Pass focused tests and the normal
checks. State which real-terminal checks were run and which remain outstanding.
Submit a PR and handoff; the maintainer decides completion and the next task.
