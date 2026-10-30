# Working on SOL with Claude Code

This file tells Claude Code how to work in this repository. It is operational
guidance, not a design authority. What SOL should be is governed only by the five
documents in `docs/`, led by [SPECULATIVE](docs/SPECULATIVE.md): [Architecture](docs/ARCHITECTURE.md), [BEING](docs/BEING.md),
[ESSENCE](docs/ESSENCE.md) and [CORE](docs/CORE.md). Development procedure is in
[CONTRIBUTING](CONTRIBUTING.md). Earlier documents are in Git history, not in the
tree.

## Roles

- **The maintainer** owns SOL, sets the work, decides reserved decisions and may
  overrule any merged default later. All pull requests are opened and merged
  through the maintainer's GitHub account.
- **Claude Code** works on `claude/` branches.
- **Codex** works on `codex/` branches, in parallel, on files the other is not
  touching.

GitHub cannot record a review from the account that opened a pull request, so
review is a comment on the pull request, not a GitHub approval.

## Before starting

1. Check `gh pr list` and `gh issue list`. Open work lives in
   [GitHub issues](https://github.com/dialectmaterial/SOL/issues).
2. Read the authority sections the task touches.
3. Run `git status` and `git log --oneline -10`; never discard uncommitted work.

## While working

- Branch from up-to-date `main` as `claude/<short-task-name>`. Never commit to
  or push `main` directly; GitHub refuses it, because `main` requires the
  tests to pass on a pull request.
- Keep commits small, each with a message saying what changed and why. Do not
  add commits that only record status.
- Run focused tests, then the full checks before opening a pull request:

  ```sh
  .venv/bin/python -B scripts/check_docs.py
  .venv/bin/python -B -m unittest discover -s tests
  ```

- When behaviour changes, update the relevant authority document in the same
  pull request. Add a line under *Unreleased* in `CHANGELOG.md` only for a change
  a user would notice. Never commit the private corpus, source PDF, workspaces
  or analysis exports.
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

1. For application changes, install the verified checkout into the maintainer's
   existing launcher environment and verify the installed package from outside
   the checkout. This is standing authorization, not a per-task approval step;
   follow [the local installation procedure](CONTRIBUTING.md#install-verified-changes-for-the-maintainer).
2. Push the branch and open a pull request against `main` with
   `gh pr create --base main`. Its description is the report: what changed and
   why, what was checked, the defaults the maintainer may overrule and any
   *Decisions requiring approval*. Name issues it closes.
3. File anything found but not fixed as an issue, not as a note in a document.

## Reviewing and merging

1. A pull request that changes application behaviour gets a review by the other
   agent: read the diff, run the documentation check and the full suite on the
   branch, plus whatever real-corpus or headless check the change invites.
2. If something must change, say what and why with `gh pr comment <n>` and stop;
   the author fixes it and the review repeats.
3. Merge only when `gh pr checks <n> --watch` ends with every check passing.
4. If the description lists a **(reserved)** decision, comment "Approved; waiting
   for the maintainer's decision on …" and leave the merge to the maintainer.
5. Merge each pull request on its own with
   `gh pr merge <n> --merge --delete-branch`, then comment with what you checked.
   Do not bundle independent pull requests into one integration merge.
