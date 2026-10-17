# Working on SOL with Claude Code

This file tells Claude Code how to work in this repository. It is operational
guidance, not a design authority. What SOL should be is governed only by the four
documents in `docs/`: [Architecture](docs/ARCHITECTURE.md), [BEING](docs/BEING.md),
[ESSENCE](docs/ESSENCE.md) and [CORE](docs/CORE.md). Development procedure is in
[CONTRIBUTING](CONTRIBUTING.md). `docs/legacy/` is historical evidence: read it,
never edit it.

## Roles

- **Claude Code** implements its current task on a `claude/` branch and reports.
- **Codex** implements its own current task on a `codex/` branch, in parallel,
  following the same procedure; its task never touches the same files.
- **Reviewers:** each implementing agent reviews the other's pull request when
  the maintainer asks; ChatGPT reviews through GitHub (the pull request, its diff
  and the coordination files) and drafts next tasks. Nobody needs a conversation
  transcript.
- **The maintainer** assigns tasks, approves decisions and merges pull requests.

## Before starting

1. Read [`docs/coordination/CURRENT_TASK.md`](docs/coordination/CURRENT_TASK.md).
   Work only on the task assigned to you; if it is unclear or conflicts with the four authorities,
   ask instead of guessing.
2. Read the latest entry in [`docs/coordination/HANDOFF.md`](docs/coordination/HANDOFF.md)
   and the authority sections the task names.
3. Run `git status` and `git log --oneline -10`; never discard uncommitted work.

## While working

- Branch from up-to-date `main` as `claude/<short-task-name>`. Never commit to
  or push `main` directly.
- Keep commits small, each with a message saying what changed and why.
- Run focused tests, then the full checks before reporting:

  ```sh
  .venv/bin/python -B scripts/check_docs.py
  .venv/bin/python -B -m unittest discover -s tests
  ```

- When behaviour changes, update the relevant authority document and
  `CHANGELOG.md` in the same pull request. Never commit the private corpus,
  source PDF, workspaces or analysis exports.
- A decision that changes an authority document's **Decision** statements, a
  public contract (CORE API, reference protocol, corpus contract, workspace
  schema) or the dependency set is not yours to make: implement nothing that
  depends on it, and list it under *Decisions requiring approval*.

## Finishing a task

1. Add a report at the top of `docs/coordination/HANDOFF.md` using its template.
   The report names the last implementation commit; commit the report itself
   last, as `Record handoff: <task>`.
2. Set your task's status in `CURRENT_TASK.md` to `In review`. If `main` moved
   meanwhile (the other agent's pull request merged), rebase onto it; conflicts
   at the top of `HANDOFF.md` are resolved by keeping both reports, newest first.
3. Push the branch and open a pull request against `main` whose description
   links the handoff entry. If pushing or opening the pull request is not
   possible, say so in the report and give the exact commands.
