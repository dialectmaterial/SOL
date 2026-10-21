# Working on SOL with Claude Code

This file tells Claude Code how to work in this repository. It is operational
guidance, not a design authority. What SOL should be is governed only by the five
documents in `docs/`, led by [SPECULATIVE](docs/SPECULATIVE.md): [Architecture](docs/ARCHITECTURE.md), [BEING](docs/BEING.md),
[ESSENCE](docs/ESSENCE.md) and [CORE](docs/CORE.md). Development procedure is in
[CONTRIBUTING](CONTRIBUTING.md). Earlier documents are in Git history, not in the
tree.

## Roles

- **Claude Code** implements its current task on a `claude/` branch and reports.
- **Codex** implements its own current task on a `codex/` branch, in parallel,
  following the same procedure; its task never touches the same files.
- **Reviewers:** each implementing agent reviews, and if the rules below allow,
  merges the other's pull request; nobody merges their own. ChatGPT may also
  review through GitHub (the pull request, its diff and the coordination files)
  and drafts next tasks. Nobody needs a conversation transcript.
- **The maintainer** assigns tasks, approves reserved decisions, merges the pull
  requests that wait for them, and may overrule any merged default later.

## Before starting

1. Check `gh pr list`. If the other agent has an open pull request you have not
   reviewed since its last push, review it first (see *Reviewing and merging*).
2. Read [`docs/coordination/CURRENT_TASK.md`](docs/coordination/CURRENT_TASK.md).
   Work only on the task assigned to you; if it is unclear or conflicts with the five governing documents,
   ask instead of guessing.
3. Read the latest entry in [`docs/coordination/HANDOFF.md`](docs/coordination/HANDOFF.md)
   and the authority sections the task names.
4. Run `git status` and `git log --oneline -10`; never discard uncommitted work.

## While working

- Branch from up-to-date `main` as `claude/<short-task-name>`. Never commit to
  or push `main` directly; `main` changes only through merged pull requests.
- Keep commits small, each with a message saying what changed and why.
- Run focused tests, then the full checks before reporting:

  ```sh
  .venv/bin/python -B scripts/check_docs.py
  .venv/bin/python -B -m unittest discover -s tests
  ```

- When behaviour changes, update the relevant authority document and
  `CHANGELOG.md` in the same pull request. Never commit the private corpus,
  source PDF, workspaces or analysis exports.
- **Structural decisions are yours to make, provisionally** ([SPECULATIVE §5.3](docs/SPECULATIVE.md#53-autonomy-and-final-authority)):
  creating a logical directory, moving a significant module or regrouping a
  cohesive cluster needs no approval for each move, but follows the reasoning
  protocol of [SPECULATIVE §5.2](docs/SPECULATIVE.md#52-required-reasoning-protocol):
  read the pertinent part of the *Science of Logic* in the CORE edition (German
  or other translations as aids), interpret the determination against its
  neighbours, inspect what the code does and what its tests protect, propose the
  placement and why it beats the alternatives, implement without rewriting
  working logic, verify, and record a row in the
  [placement register](docs/ARCHITECTURE.md#9-placement-register). Never fabricate
  quotations, page numbers or textual evidence; name the edition and location,
  and separate the passage from your interpretation. Tests, configuration, CI,
  packaging and tooling stay outside the logical hierarchy for now.
- SPECULATIVE is the maintainer's document: never edit it; keep the other four
  consistent with it and report any disagreement.
- A **reserved decision** changes a governing document's **Decision**
  statements, a public contract (CORE API, reference protocol, corpus contract,
  workspace schema), the dependency set, or how personal work or the canonical
  corpus can be deleted or overwritten. It is not yours to make: implement
  nothing that depends on it, and list it under *Decisions requiring approval*
  marked **(reserved)**. Other choices are defaults: make them, and list them.

## Finishing a task

1. Add a report at the top of `docs/coordination/HANDOFF.md` using its template.
   The report names the last implementation commit; commit the report itself
   last, as `Record handoff: <task>`.
2. Set your task's status in `CURRENT_TASK.md` to `In review`. If `main` moved
   meanwhile (the other agent's pull request merged), rebase onto it; conflicts
   at the top of `HANDOFF.md` are resolved by keeping both reports, newest first.
3. Push the branch and open a pull request against `main` with
   `gh pr create --base main`, whose description links the handoff entry. If
   that is not possible, say so in the report and give the exact commands.

## Reviewing and merging the other agent's pull request

1. Read the diff and its handoff report; run the documentation check and the
   full suite on the branch in a separate worktree, plus whatever real-corpus or
   headless check the change invites.
2. If something must change, say what and why with `gh pr comment <n>` and stop;
   the author fixes it and you review again.
3. Wait for GitHub's tests: `gh pr checks <n> --watch` must end with every check
   passing.
4. If the report lists a **(reserved)** decision, comment "Approved; waiting for
   the maintainer's decision on …" and leave the merge to the maintainer.
5. If GitHub reports a conflict and it is only the stacked entries at the top of
   `HANDOFF.md` or `CHANGELOG.md`, merge `origin/main` into the branch, keep both
   entries (newest first), rerun the checks, push, and wait for the tests again.
   Ask the author to resolve any other conflict.
6. Otherwise merge with `gh pr merge <n> --merge --delete-branch`, then post a
   comment with what you checked and the defaults the maintainer may overrule.
   The merged task counts as done; its slot in `CURRENT_TASK.md` is replaced
   when the next task is assigned.
