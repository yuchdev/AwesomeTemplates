# Task 07.0 - Copilot porting session

**Parent milestone:** [Milestone 0001 - Alternative Headless Harness Support](/docs/roadmap/0001-alternative-harness-support/plan.md)
**Status:** ⬜ Not started - see [status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
**Category:** feature.

## Scope

Confirms where Copilot's own conventions expect ported agent/skill-equivalent
configuration to live in a target repository, and wires that confirmed
location into `harnesses.Harness.porting_target_hint` (task
[01.0](/docs/roadmap/0001-alternative-harness-support/01.0-harnesses-module/README.md)
subtask 01) for `_COPILOT` (task
[02.0](/docs/roadmap/0001-alternative-harness-support/02.0-copilot-adapter/README.md)),
so [`port.py`](/src/awesome_templates/port.py)'s prompt builder (task
[06.0](/docs/roadmap/0001-alternative-harness-support/06.0-port-to-pipeline/README.md)
subtask 01) can tell Copilot precisely where to look/write instead of falling
back to the generic "use whatever location is idiomatic for you" sentence.

The porting prompt itself (built once, harness-agnostically, in `port.py`) does
not change per harness - what this task confirms is purely the
`porting_target_hint` string and, if task 02.0's confirmed tool-allowlist
syntax turns out not to already cover it, whatever adjustment `_COPILOT`'s
`build_command` needs so a `Write` to a path outside `.claude/` is actually
permitted during a porting session (marker research never needed `Write`
outside the kit root; porting does).

## Subtasks

| # | Document | Depends on | Blocks |
|---|----------|------------|--------|
| 01 | [Spike: Copilot's own agent/skill config convention](01-spike-copilot-porting-target.md) ✅ | task 02.0 | 02 |
| 02 | [Wire the confirmed hint into `_COPILOT`](02-wire-copilot-porting-hint.md) ✅ | 01 | - |

## Key constraints

- Do not invent a plausible-sounding output convention - if Copilot has no
  fixed convention (e.g. it is fully configurable, or genuinely
  freeform), the honest answer is "no fixed hint" and `porting_target_hint`
  stays `None`, same as its default.
- This task never touches `port.py`'s prompt text itself (that's task 06.0's
  job) - only the harness-specific hint value it consumes.

## Files created or modified by this task

```
src/awesome_templates/
└── harnesses.py    ← modified: `_COPILOT.porting_target_hint` set (or
                       confirmed to stay `None`); `_build_copilot_command`
                       adjusted if task 02.0's tool-allowlist syntax needs a
                       broader `Write` scope for porting (subtask 02)
```
