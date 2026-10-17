# Explicit BEING–ESSENCE handoff

BEING can send its active canonical reference to an ordinary zsh pane, then
inspect and deliberately accept one proposed return. The reference identifies
the text; it does not transfer an actor, workspace, or permission to save personal
work. This optional bridge is included in the existing SOL installation.

## Open from BEING

Use an indexed corpus with a permanent UUID, plus installed kitty, its standalone
`kitten` command, and zsh. Launch the reader through `sol-kitty`:

```sh
sol-kitty --corpus /absolute/path/to/corpus
```

For an older corpus without a UUID, initialize it explicitly first with
`sol-corpus-check /absolute/path/to/corpus --initialize-identity`. To use a
temporary reader without a workspace, add `-n` to the launcher command.

In BEING's reader prompt, select a passage and open the exchange:

```text
first /being
essence open
```

Opening captures the current requested UUID, resolved target, retirement chain,
and verified corpus generation. It does not move the reader or save a visit.
Only one exchange can be active; close it before opening another. The new pane
starts zsh in the selected corpus directory with your normal shell startup files.
Its welcome identifies the reference and source page without displaying passage
text. Ordinary reader use remains available when kitty or zsh is absent.

## Propose a return from zsh

Switch to the ESSENCE pane and inspect the received reference:

```sh
sol reference check "$SOL_REFERENCE_FILE"
sol reference return
```

Check prints a JSON verification result without navigating or saving a visit.
Return publishes one proposal with `status: "proposed"`; omitted `ID` retains the
original requested UUID, including an explicit retirement redirect. To propose a
different canonical record, use `sol reference return ID`, replacing `ID` with a
UUID or unambiguous prefix. A second proposal cannot overwrite the first.

The bootstrap pins `SOL_CORPUS`, `SOL_HANDOFF_DIR`, and `SOL_REFERENCE_FILE` to
the validated local exchange. Its private `sol` wrapper uses the current SOL
code and interpreter. The CLI also accepts explicit `--corpus DIRECTORY` and
`--handoff-dir DIRECTORY` on return; payload fields cannot choose those locations.
Returning a record outside BEING's readable passage projection is refused by
BEING even when CORE can verify that canonical record.

## Accept once in BEING

Switch back to the reader prompt:

```text
essence check
essence return
```

Check reports the proposed IDs and source evidence, whether the reader position
changed, and whether the return was already accepted. It only inspects.
Return validates again and navigates once through the ordinary reader action.
With a workspace, that action uses BEING's existing checkpoint and conflict
guards; without one, navigation remains temporary. It does not import analysis
results as notes, assertions, or review testimony.

If you changed reading or browsing position after opening the exchange, inspect
the proposal first and deliberately override that position guard:

```text
essence check
essence return --accept-move
```

`--accept-move` does not bypass corpus freshness, reference validation, or workspace
conflict checks. A return is accepted at most once per exchange. Publishing or
accepting it leaves the zsh pane open so its work can continue.

## Finish and close

Save native files and finish running commands before closing the pane or leaving
BEING. Then, in BEING:

```text
essence close
```

Close targets the owned ESSENCE window and ends its temporary exchange. Leaving
the reader also attempts cleanup. Cleanup removes reserved transport files and
the exact fixed wrapper it owns; unexpected files, custom wrapper content, or
replaced directories are retained and reported. Keep research outputs outside
the private transport directory.

## Boundaries

Both sides require the same permanent corpus identity and exact captured manifest
and index generation. Even an unrelated corpus correction invalidates an old
exchange. After correcting and rebuilding a corpus, reopen BEING and start a new
exchange; there is no automatic rebasing. Directory ownership, permissions,
stable files, session nonce, and origin digest are checked around the local
transport. These checks establish integrity and exchange correlation, not the
identity of a human author. The [CORE reference protocol](REFERENCE_PROTOCOL.md)
defines the packet and its limits.

SOL keeps the reader's remote-control credentials out of the ESSENCE environment
and controls only its owned pane. Kitty supplies window launch and per-window,
action-limited remote-control permissions. [Kitty remote-control documentation](https://sw.kovidgoyal.net/kitty/remote-control/),
[Kitty launch documentation](https://sw.kovidgoyal.net/kitty/launch/).

The zsh pane is an ordinary shell, not a sandbox. Its programs have the operating
system access allowed to your account. The handoff itself carries no workspace
address, actor authority, command, source path, or permission for personal writes;
BEING's actor and workspace remain local to BEING. See the [reader action
boundary](READER_ACTIONS.md) and [modularity contract](MODULARITY.md).

The first bounded [ESSENCE term study](TERM_STUDY.md) now exercises the bridge:
an inquiry retains its originating reference, measures eligible prose, and can
return a selected matching UUID through the same explicit navigation guard.
Its result format is versioned and recomputed on check; it grants no permission
to create authored assertions. Automatic result ingestion, workspace
synchronization, independent distributions, and CONCEPT composition remain
separate work.
