# Task 02.0 - `copilot` adapter

**Parent milestone:** [Milestone 0001 - Alternative Headless Harness Support](/docs/roadmap/0001-alternative-harness-support/plan.md)
**Status:** ⬜ Not started - see [status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
**Category:** feature.

## Scope

Registers `copilot` (GitHub Copilot CLI) as a second `Harness` in
[`harnesses.py`](/src/awesome_templates/harnesses.py) (depends on task
[01.0](/docs/roadmap/0001-alternative-harness-support/01.0-harnesses-module/README.md)).
Unlike task 01.0's relocation, none of `copilot`'s actual CLI flags are known
with confidence yet - [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s
"`copilot` (GitHub Copilot CLI)" section lists five specific open questions
(non-interactive flag, tool-allowlist syntax, permission-bypass equivalent,
prompt-delivery mechanism, model-selection flag). This task opens with a spike
against the real, installed `copilot --help`/docs to answer them before any
`_build_copilot_command` code is written - do not guess flag names from the
plan's own placeholder text.

## Subtasks

| # | Document | Depends on | Blocks |
|---|----------|------------|--------|
| 01 | [Spike: confirm `copilot`'s non-interactive contract](01-spike-copilot-contract.md) | task 01.0 | 02 |
| 02 | [`_build_copilot_command` + `_COPILOT` registration](02-copilot-command-registration.md) | 01 | tasks 04.0, 07.0 |

## Key constraints

- No `_build_copilot_command` code is written before subtask 01's findings are
  recorded - a wrong guess here is a silent correctness bug (a malformed argv
  that either fails loudly, which is fine, or - worse - runs with different
  scope/permissions than intended).
- `forwards_anthropic_key=False` on `_COPILOT` - Copilot authenticates via the
  user's GitHub account/token (`gh auth login`, or `GH_TOKEN`/`GITHUB_TOKEN` in
  CI), never `ANTHROPIC_API_KEY`.
- Same coding constraints as task 01.0: `Optional[T]`, `from __future__ import
  annotations`, `ruff` clean.

## Files created or modified by this task

```
src/awesome_templates/
└── harnesses.py    ← modified: `_build_copilot_command`, `_COPILOT`,
                       `_REGISTRY["copilot"] = _COPILOT` (subtask 02)
```

Subtask 01 produces no code - its output is the confirmed contract recorded in
its own subtask document and in this milestone's `status.md`, consumed by
subtask 02.
