# Task 03.0 - `junie` adapter

**Parent milestone:** [Milestone 0001 - Alternative Headless Harness Support](/docs/roadmap/0001-alternative-harness-support/plan.md)
**Status:** ⬜ Not started - see [status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
**Category:** feature.

## Scope

Registers `junie` (JetBrains Junie) as a third `Harness` in
[`harnesses.py`](/src/awesome_templates/harnesses.py) (depends on task
[01.0](/docs/roadmap/0001-alternative-harness-support/01.0-harnesses-module/README.md)).
Junie ships primarily as an agent embedded in JetBrains IDEs, and whether it
currently exposes a supported, documented **non-interactive CLI contract**
suitable for unattended use is genuinely unconfirmed - see
[plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s "`junie`
(JetBrains Junie)" section. This task's spike therefore has two explicit
possible outcomes, and this task's own shape depends on which one holds:

1. **A headless/CI mode exists and is documented** → build
   `_build_junie_command` following the same pattern as task 02.0, with its
   own confirmed flags.
2. **No such mode exists yet** → ship `junie` as a registered-but-unavailable
   harness: `--harness junie` is accepted by the CLI (so scripts don't break if
   JetBrains ships one later), but `find_harness` returning `None` produces a
   clear "Junie has no supported headless CLI mode yet" message rather than a
   generic "not on PATH" one.

This document does not pre-decide which outcome applies. Task
[08.0](/docs/roadmap/0001-alternative-harness-support/08.0-junie-porting-session/README.md)
(the Junie porting session, which the milestone requires to run **headless** -
see the "Headless mode" paragraph in
[plan.md#cross-harness-porting-pipeline-claude-copilot-junie](/docs/roadmap/0001-alternative-harness-support/plan.md#cross-harness-porting-pipeline-claude-copilot-junie))
is only buildable under outcome 1; under outcome 2 it ships only the
honest-failure path.

## Subtasks

| # | Document | Depends on | Blocks |
|---|----------|------------|--------|
| 01 | [Spike: does Junie have a headless CLI mode?](01-spike-junie-headless-mode.md) | task 01.0 | 02 |
| 02 | [`_JUNIE` registration (outcome-dependent)](02-junie-registration.md) | 01 | tasks 04.0, 08.0 |

## Key constraints

- Outcome 2 is not a failure of this task - it is a legitimate, honestly
  documented result. Do not fabricate flags for a product surface that may not
  exist in the assumed form.
- `forwards_anthropic_key=False` on `_JUNIE` regardless of outcome - Junie
  authenticates through JetBrains' own account/license mechanism, never
  `ANTHROPIC_API_KEY`.
- Same coding constraints as tasks 01.0/02.0.

## Files created or modified by this task

```
src/awesome_templates/
└── harnesses.py    ← modified: `_build_junie_command` + `_JUNIE` (outcome 1),
                       or a registered-but-unavailable `_JUNIE` stub with an
                       honest error message (outcome 2); `_REGISTRY["junie"]`
                       either way (subtask 02)
```
