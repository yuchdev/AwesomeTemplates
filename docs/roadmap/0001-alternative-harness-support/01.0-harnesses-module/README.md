# Task 01.0 - `harnesses.py` + `claude` relocation

**Parent milestone:** [Milestone 0001 - Alternative Headless Harness Support](/docs/roadmap/0001-alternative-harness-support/plan.md)
**Status:** ⬜ Not started - see [status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
**Category:** refactor.

## Scope

Introduces `src/awesome_templates/harnesses.py`, the registry every other task in
this milestone builds on: a `Harness` dataclass, `find_harness`, `get`, and a
`_REGISTRY` seeded with `_CLAUDE`. [`headless.py`](/src/awesome_templates/headless.py)'s
`find_claude()`, `build_command()`, and `HEADLESS_MODEL` are relocated into this
module as `_CLAUDE`'s registration - a rename, not a rewrite, of behavior that
already ships. `resolve_tree_headless` gains a `harness: str = "claude"`
parameter that defaults to exactly today's behavior, and its prompt-delivery
branch (stdin vs. argv) becomes explicit instead of hardcoded, since
[plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md) leaves open
that Copilot might need argv-based prompt delivery instead of stdin.

This is the foundation task. Tasks
[02.0](/docs/roadmap/0001-alternative-harness-support/02.0-copilot-adapter/README.md),
[03.0](/docs/roadmap/0001-alternative-harness-support/03.0-junie-adapter/README.md),
[04.0](/docs/roadmap/0001-alternative-harness-support/04.0-cli-wiring/README.md),
and the porting pipeline
([06.0](/docs/roadmap/0001-alternative-harness-support/06.0-port-to-pipeline/README.md)-
[08.0](/docs/roadmap/0001-alternative-harness-support/08.0-junie-porting-session/README.md))
all need this registry to exist before they can register a harness, wire a CLI
flag, or dispatch a porting session.

## Subtasks

| # | Document | Depends on | Blocks |
|---|----------|------------|--------|
| 01 | [`Harness` dataclass + registry skeleton](01-harnesses-registry.md) | none | 02, 03 |
| 02 | [Relocate `claude`'s adapter out of `headless.py`](02-relocate-claude-adapter.md) | 01 | 03; tasks 02.0, 03.0, 04.0, 06.0 |
| 03 | [Module-map docs](03-module-map-docs.md) | 02 | - |

## Key constraints

- `Optional[T]` from `typing`, never `T | None`; `from __future__ import
  annotations` at the top of every new/touched file.
- `ruff check src/ tests/` stays clean.
- No behavior change to an existing call with no `harness` argument - subtask
  02's success criteria pin byte-identical argv for the `claude` path.
- `harnesses.py` never imports from `headless.py` or `port.py` (the dependency
  runs the other way: sessions call into the registry, not vice versa).

## Files created or modified by this task

```
src/awesome_templates/
├── harnesses.py          ← NEW (subtask 01, extended by subtask 02)
├── headless.py           ← modified: find_claude/build_command/HEADLESS_MODEL
│                            removed; resolve_tree_headless gains `harness=`
│                            (subtask 02)
├── cli.py                ← modified: one call site (`headless.find_claude()`)
│                            becomes `harnesses.find_harness(harnesses.get("claude"))`
│                            (subtask 02)
└── CLAUDE.md              ← modified: module map gains harnesses.py; headless.py
                             entry updated (subtask 03)
```
