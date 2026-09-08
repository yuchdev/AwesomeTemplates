# Task 10.0 - Credential flags + `--backend` removal

**Parent milestone:** [Milestone 0001 - Alternative Headless Harness Support](/docs/roadmap/0001-alternative-harness-support/plan.md)
**Status:** ✅ Complete - see [status.md](/docs/roadmap/0001-alternative-harness-support/status.md).
**Category:** feature.

## Scope

`--backend {anthropic-api,openai-api,jetbrains-api}` existed alongside this milestone's
`--harness` work as a second, mutually-exclusive "AI engine" - a direct vendor API call this
package would place itself, via `resolver.resolve_tree`/`ai/client.py`. Every backend was
permanently `implemented=False`, and `generate` never called `resolver.resolve_tree` as a
fallback either, so the flag never did real work: selecting one always exited with a
"not implemented" notice before anything ran.

This task removes `--backend` and `src/awesome_templates/backends.py` entirely and replaces
them with `--api-key`/`--api-key-env`: two flags that pair with `--harness` and only change
**how** the chosen harness's CLI subprocess authenticates, never what runs. `claude` still does
all the actual work either way. See [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s
"Credential flags (`--api-key` / `--api-key-env`)" subsection for the full design this task
implements, and its "Task 10.0's own acceptance criteria" for the exit bar - including a
**≥ 90% coverage floor for this task specifically**, an explicit exception to this repo's
usual no-coverage-floor default.

`resolver.py`'s direct-API code (`resolve_tree`, `resolve_one`, `gather_context`,
`load_api_key`) and `ai/client.py` are **not** touched by this task - they were already
unreachable from `generate` before `--backend` existed in a runnable form, and removing
`--backend` doesn't change that. They stay exactly as they are.

## Subtasks

| # | Document | Depends on | Blocks |
|---|----------|------------|--------|
| 01 | [Generalize `Harness.api_key_env`](01-generalize-harness-api-key-env.md) ✅ | task 01.0's registry | 02, 03 |
| 02 | [`cli.py` flags + `--backend` removal](02-cli-flags-and-backend-removal.md) ✅ | 01; task 04.0's `sanity_check`/`generate` | 03 |
| 03 | [Tests + coverage to ≥ 90%](03-tests-and-coverage.md) ✅ | 01, 02 | - |

## Key constraints

- `Optional[T]` from `typing`, never `T | None`; `from __future__ import annotations` at the
  top of every touched file (unchanged repo convention).
- `ruff check src/ tests/` stays clean.
- No behavior change to the *default* case: omitting `--api-key`/`--api-key-env` must still
  authenticate exactly as today's hardcoded `api_key=None` did (strip `ANTHROPIC_API_KEY`,
  let the installed CLI's own login take over).
- `--api-key` never gets a config-file fallback (a literal secret has no business in a
  checked-in config file); `--api-key-env` does (it only ever names a variable).
- `resolver.py`/`ai/client.py` are out of scope - do not touch them as part of "cleanup".

## Files created or modified by this task

```
src/awesome_templates/
├── harnesses.py          ← modified: forwards_anthropic_key: bool → api_key_env: Optional[str]
│                            (subtask 01)
├── headless.py           ← modified: env construction generalized to api_key_env (subtask 01)
├── port.py                ← modified: porting-target guard checks api_key_env is None (subtask 01)
├── backends.py            ← DELETED (subtask 02)
├── cli.py                 ← modified: --backend removed, --api-key/--api-key-env added,
│                            sanity_check rewritten (subtask 02)
└── CLAUDE.md               ← modified: harnesses.py/headless.py/cli.py entries updated,
                              backends.py entry removed (subtask 02)

CLAUDE.md (repo root)      ← modified: "AI-engine choice" section rewritten (subtask 02)

tests/
├── test_backends.py       ← DELETED (subtask 02)
├── test_harnesses.py      ← modified: field rename (subtask 01)
├── test_headless.py       ← modified: field rename (subtask 03)
├── test_port.py            ← modified: field rename (subtask 03)
└── test_cli.py             ← modified: backend tests removed, credential-flag tests added
                              (subtask 03)
```
