# Task 05.0 - Tests

**Parent milestone:** [Milestone 0001 - Alternative Headless Harness Support](/docs/roadmap/0001-alternative-harness-support/plan.md)
**Status:** ⬜ Not started - see [status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
**Category:** test.

## Scope

Covers the `--harness` surface (tasks
[01.0](/docs/roadmap/0001-alternative-harness-support/01.0-harnesses-module/README.md)-
[04.0](/docs/roadmap/0001-alternative-harness-support/04.0-cli-wiring/README.md))
per [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s
"Testing strategy" section, extending the existing subprocess-boundary pattern
(`tests/test_headless.py`'s `_fake_run_factory`, `run=` injection) per harness
rather than inventing a new one. No real `copilot` or `junie` binary is ever
invoked, matching how no real `claude` is invoked today.

## Subtasks

| # | Document | Depends on | Blocks |
|---|----------|------------|--------|
| 01 | [`tests/test_harnesses.py`](01-test-harnesses.md) | tasks 01.0-03.0 | - |
| 02 | [`tests/test_headless.py` additions](02-test-headless-additions.md) | task 01.0 (harness param) | - |
| 03 | [`tests/test_cli.py` additions](03-test-cli-additions.md) | task 04.0 | - |

## Key constraints

- No real `copilot`/`junie` binary invoked - `monkeypatch` `shutil.which` or
  inject a fake `binary_names`/`run=` the same way existing tests fake
  `claude`.
- Tests for tasks 02.0/03.0's adapters only exercise `_build_copilot_command`/
  `_build_junie_command`'s **argv shape** once those tasks confirm real flags
  - they do not (and cannot) assert against a live CLI's actual behavior.

## Files created or modified by this task

```
tests/
├── test_harnesses.py    ← NEW (subtask 01)
├── test_headless.py     ← modified: harness= plumbing tests (subtask 02)
└── test_cli.py           ← modified: --harness validation/dry-run/fallback
                             tests (subtask 03)
```
