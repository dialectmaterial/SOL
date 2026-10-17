# Handoff reports

Claude Code adds one report per completed task, newest first, so a reviewer can
judge the work from GitHub alone: the report says what to look at, the pull
request shows the diff. Reports describe; they do not change what the four
authorities ([Architecture](../ARCHITECTURE.md), [BEING](../BEING.md),
[ESSENCE](../ESSENCE.md), [CORE](../CORE.md)) say. Keep each report short; the
commit messages and diff carry the detail. Trim reports older than the last few
merged tasks; Git history keeps them.

<!--
Template — copy to the top of the reports and fill in every heading.
Write "None." rather than deleting a heading.

## <Task title> — <date>

**Task:** <link to the CURRENT_TASK version or its title>
**Branch / PR:** `claude/<name>` · <PR link or "not opened: reason">
**Last implementation commit:** `<full SHA>` (this report is committed after it)

### Changed files
- `<path>` — <what and why, one line>

### Tests performed
- <command> — <result, e.g. "1527 passed, 11 skipped">
- <manual or real-corpus check> — <what was observed>

### Outstanding issues
- <known limits, failures, things not done>

### Decisions requiring approval
- <decision, the options, and what was assumed meanwhile>
-->
