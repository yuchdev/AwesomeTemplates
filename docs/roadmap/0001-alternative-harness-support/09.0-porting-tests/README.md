# Task 09.0 - Porting pipeline tests

**Parent milestone:** [Milestone 0001 - Alternative Headless Harness Support](/docs/roadmap/0001-alternative-harness-support/plan.md)
**Status:** ⬜ Not started - see [status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
**Category:** test.

## Scope

Covers the `--port-to` surface (tasks
[06.0](/docs/roadmap/0001-alternative-harness-support/06.0-port-to-pipeline/README.md)-
[08.0](/docs/roadmap/0001-alternative-harness-support/08.0-junie-porting-session/README.md)),
same subprocess-boundary pattern as task
[05.0](/docs/roadmap/0001-alternative-harness-support/05.0-tests/README.md).
No real `copilot` or `junie` binary is ever invoked.

## Subtasks

| # | Document | Depends on | Blocks |
|---|----------|------------|--------|
| 01 | [`tests/test_port.py`: manifest + prompt tests](01-test-port-manifest-prompt.md) | task 06.0 subtask 01 | - |
| 02 | [`tests/test_port.py`: `port_tree_headless` fake-run tests](02-test-port-tree-headless.md) | task 06.0 subtask 02 | - |
| 03 | [`tests/test_cli.py`: `--port-to` validation tests](03-test-cli-port-to.md) | task 06.0 subtask 03 | - |

## Key constraints

- No real `copilot`/`junie` binary invoked.
- Reuses `tests/conftest.py`'s `fixture_workspace` where a generated tree with
  real agent/skill/loop/hook files is needed, rather than building a bespoke
  fixture that duplicates it.

## Files created or modified by this task

```
tests/
├── test_port.py    ← NEW (subtasks 01-02)
└── test_cli.py      ← modified: --port-to validation/dry-run tests (subtask 03)
```
