# Task 04.0 - `cli.py` wiring

**Parent milestone:** [Milestone 0001 - Alternative Headless Harness Support](/docs/roadmap/0001-alternative-harness-support/plan.md)
**Status:** ⬜ Not started - see [status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
**Category:** feature.

## Scope

Wires `--harness {claude,copilot,junie}` into `generate` per
[plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s "CLI
wiring" section, replacing today's hardcoded `claude`-only branch in
[`cli.py`](/src/awesome_templates/cli.py) (the block starting
`claude_bin = headless.find_claude()`, updated once already by task 01.0
subtask 02 to call through `harnesses`). Depends on task
[01.0](/docs/roadmap/0001-alternative-harness-support/01.0-harnesses-module/README.md)'s
registry; tasks
[02.0](/docs/roadmap/0001-alternative-harness-support/02.0-copilot-adapter/README.md)
and
[03.0](/docs/roadmap/0001-alternative-harness-support/03.0-junie-adapter/README.md)
can land before or after this task without blocking it, since `--harness
copilot`/`--harness junie` simply resolve to whatever `harnesses.get(...)`
currently returns (a working adapter, or - before those tasks land - a
harness whose binary is never found, correctly reported as unavailable).

## Subtasks

| # | Document | Depends on | Blocks |
|---|----------|------------|--------|
| 01 | [`--harness` option + validation](01-harness-option.md) ✅ | task 01.0 | 02, 03 |
| 02 | [Dry-run output](02-dry-run-output.md) ✅ | 01 | - |
| 03 | [Missing-binary branching, no silent fallback for non-claude](03-missing-binary-branching.md) ✅ | 01 | task 06.0 (reuses this branch's shape) |
| 04 | [Docs: root `CLAUDE.md` Commands section](04-root-claude-md-docs.md) ✅ | 03 | - |

## Key constraints

- `--harness` defaults to `"claude"` - no behavior change for a `generate
  --resolve-markers` call that doesn't pass it.
- The one-shot API fallback (`resolver.resolve_tree`) stays `claude`/Anthropic-
  only, per [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s explicit non-goal: it is unreachable for
  `--harness copilot`/`--harness junie`.
- `--harness` is rejected outright when passed without `--resolve-markers`,
  mirroring `--seed-roadmap`'s existing check
  (`test_generate_rejects_seed_roadmap_without_resolve_markers` in
  `tests/test_cli.py` is the pattern to match).

## Files created or modified by this task

```
src/awesome_templates/
└── cli.py    ← modified: `--harness` option, dry-run output, missing-binary
                 branching (subtasks 01-03)

CLAUDE.md      ← modified (repo root): Commands section documents `--harness`
                 (subtask 04)
```
