# Milestone 0002 - Alternative Headless Harness Support - Status

Tracks progress against [plan.md](plan.md). Not started - this is a design-only milestone as
of its authoring (2026-08-26); no code under `src/awesome_templates/` implements any part of it
yet (confirmed: no `harnesses.py` module exists in the tree).

## Current status

| Task | Name                                     | Status         | Tests |
|------|---------------------------------------------|----------------|-------|
| 01.0 | `harnesses.py` + `claude` relocation         | ⬜ Not started | -     |
| 02.0 | `copilot` adapter                            | ⬜ Not started | -     |
| 03.0 | `junie` adapter                              | ⬜ Not started | -     |
| 04.0 | `cli.py` wiring                              | ⬜ Not started | -     |
| 05.0 | Tests                                        | ⬜ Not started | -     |
| 06.0 | `--port-to` pipeline orchestration           | ⬜ Not started | -     |
| 07.0 | Copilot porting session                      | ⬜ Not started | -     |
| 08.0 | Junie porting session (headless)             | ⬜ Not started | -     |
| 09.0 | Porting pipeline tests                       | ⬜ Not started | -     |

**Legend:** ✅ Complete · 🔶 In progress / partial · ⬜ Not started

## Before starting task 02.0 or 03.0

Both adapters open with a spike against the real `copilot` / `junie` CLI (see plan.md's
per-harness sections) - their exact flags are explicitly unconfirmed in the plan, not guessed.
Do not begin writing `_build_copilot_command` or `_build_junie_command` from the plan's
placeholder flag names without first running that spike; the plan documents *what* to confirm,
not the confirmed answer.

## Before starting task 07.0 or 08.0

Both porting sessions depend on their adapter task's spike outcome (07.0 on 02.0, 08.0 on
03.0), plus 06.0's `--port-to` plumbing existing first. 08.0 additionally requires that 03.0
landed on outcome 1 (a confirmed headless Junie mode) - if 03.0 landed on outcome 2, 08.0 ships
only the honest-failure path for `--port-to junie`, per plan.md's acceptance criteria.
