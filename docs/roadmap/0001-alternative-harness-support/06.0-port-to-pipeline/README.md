# Task 06.0 - `--port-to` pipeline orchestration

**Parent milestone:** [Milestone 0001 - Alternative Headless Harness Support](/docs/roadmap/0001-alternative-harness-support/plan.md)
**Status:** ⬜ Not started - see [status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
**Category:** feature.

## Scope

Adds the second, optional stage described in
[plan.md#cross-harness-porting-pipeline-claude-copilot-junie](/docs/roadmap/0001-alternative-harness-support/plan.md#cross-harness-porting-pipeline-claude-copilot-junie):
a new `--port-to {copilot,junie}` option on `generate`, backed by a new
module, `src/awesome_templates/port.py`.

**Claude stays the reference harness.** `--port-to` never changes what
authors `.claude/` itself - that is still `--harness claude`'s (the default's)
job, unchanged by this task. What `--port-to` adds is a *follow-up* headless
session, chained in the same `generate` invocation right after the initial
Claude-authored `.claude/agents/`, `.claude/skills/`, `.claude/loops/`, and
`.claude/hooks/` already exist, that tasks the chosen harness with porting
those four kinds into its own native equivalents.

Concretely:

- Gated on `--resolve-markers` (same requirement `--harness` already has).
- Requires `--harness` to be `claude` (its default) - rejected outright for
  any other value, not only the exact self-port case (`--harness copilot
  --port-to copilot`). Porting always reads a Claude-authored `.claude/` tree,
  per the milestone's "Claude is always the reference harness" principle -
  `--harness copilot --port-to junie` is rejected too, even though it isn't a
  literal self-port.
- Builds a manifest of the four Claude kinds by reusing `catalog.discover`
  (the same primitive `awesome-templates list`/`graph` already use to
  enumerate a tree's entities) and a porting-specific prompt that instructs
  the target harness to *re-author*, not copy.
- Dispatches to the chosen harness via `harnesses.py`'s registry (task
  [01.0](/docs/roadmap/0001-alternative-harness-support/01.0-harnesses-module/README.md)):
  task [07.0](/docs/roadmap/0001-alternative-harness-support/07.0-copilot-porting-session/README.md)
  confirms Copilot's own porting-target conventions, task
  [08.0](/docs/roadmap/0001-alternative-harness-support/08.0-junie-porting-session/README.md)
  does the same for Junie (strictly headless).
- `--dry-run` gains a `Port to: ...` line, mirroring `Harness: ...` from task
  [04.0](/docs/roadmap/0001-alternative-harness-support/04.0-cli-wiring/README.md).

## Subtasks

| # | Document | Depends on | Blocks |
|---|----------|------------|--------|
| 01 | [`port.py`: manifest + prompt builder](01-port-manifest-prompt.md) | task 01.0 | 02 |
| 02 | [`port.py`: `port_tree_headless` orchestrator](02-port-tree-headless.md) | 01 | 03 |
| 03 | [`cli.py`: `--port-to` flag + validation + dispatch](03-cli-port-to-wiring.md) | 02, task 04.0 | task 09.0 |

## Key constraints

- `port.py` never imports `headless` - both depend on `harnesses.py`, not on
  each other (see `port.py`'s own module docstring in subtask 01).
- The porting session's tool set is `Read`/`Grep`/`Glob`/`Write` (no `Edit`) -
  it creates new files in the target harness's own idiom, it never modifies
  the Claude-authored files it reads.
- Same coding constraints as every other task in this milestone: `Optional[T]`,
  `from __future__ import annotations`, `ruff` clean, no new `# type: ignore`.

## Files created or modified by this task

```
src/awesome_templates/
├── port.py    ← NEW: render_porting_manifest, build_porting_prompt,
│                PORTING_TOOLS, PortSummary, port_tree_headless (subtasks 01-02)
└── cli.py     ← modified: --port-to option, validation, dry-run output,
                 dispatch (subtask 03)
```
