# Task 08.0 - Junie porting session (headless)

**Parent milestone:** [Milestone 0001 - Alternative Headless Harness Support](/docs/roadmap/0001-alternative-harness-support/plan.md)
**Status:** ⬜ Not started - see [status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
**Category:** feature.

## Scope

Mirrors task
[07.0](/docs/roadmap/0001-alternative-harness-support/07.0-copilot-porting-session/README.md)
for Junie: confirms Junie's own convention for where ported agent/skill-like
configuration should live, and wires it into
`harnesses.Harness.porting_target_hint` for `_JUNIE` (task
[03.0](/docs/roadmap/0001-alternative-harness-support/03.0-junie-adapter/README.md)).

**This task is strictly gated on task 03.0's outcome.** The milestone requires
the Junie porting stage to run headless (see the "Headless mode" paragraph in
[plan.md#cross-harness-porting-pipeline-claude-copilot-junie](/docs/roadmap/0001-alternative-harness-support/plan.md#cross-harness-porting-pipeline-claude-copilot-junie)),
so:

- **If task 03.0 landed on outcome 1** (a confirmed headless CLI mode): this
  task proceeds exactly like 07.0 - a spike for the porting-target convention,
  then wiring the hint.
- **If task 03.0 landed on outcome 2** (no headless mode exists): this task
  ships nothing beyond what task 03.0's own stub already provides. `--port-to
  junie` fails with the same honest "Junie has no supported headless CLI mode
  yet" message `--harness junie` already gives (task 04.0 subtask 03), with
  **no silent fallback** to an interactive session. There is no
  `porting_target_hint` spike to run in this branch - there is no session to
  target a hint at.

## Subtasks

| # | Document | Depends on | Blocks |
|---|----------|------------|--------|
| 01 | [Spike: Junie's own agent/skill config convention (outcome 1 only)](01-spike-junie-porting-target.md) | task 03.0 outcome 1 | 02 |
| 02 | [Wire the confirmed hint into `_JUNIE`, or confirm the honest-rejection path](02-wire-junie-porting-hint.md) | 01 | - |

## Key constraints

- Under outcome 2, do not build a workaround that quietly drops `--port-to
  junie` into an interactive IDE session instead of failing - the milestone's
  explicit non-goal is "no silent fallback."
- Same constraints as task 07.0 otherwise.

## Files created or modified by this task

```
src/awesome_templates/
└── harnesses.py    ← modified (outcome 1): `_JUNIE.porting_target_hint` set;
                       `_build_junie_command` adjusted if needed for porting's
                       Write scope (subtask 02)
                     ← unchanged beyond task 03.0's own stub (outcome 2)
```
