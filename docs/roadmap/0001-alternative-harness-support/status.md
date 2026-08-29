# Milestone 0002 - Alternative Headless Harness Support - Status

Tracks progress against [plan.md](plan.md). Not started - this is a design-only milestone as
of its authoring (2026-08-26); no code under `src/awesome_templates/` implements any part of it
yet (confirmed: no `harnesses.py` module exists in the tree).

## Current status

| Task | Name                                | Status         | Tests |
|------|---------------------------------------|----------------|-------|
| 01   | `harnesses.py` + `claude` relocation   | ⬜ Not started | -     |
| 02   | `copilot` adapter                      | ⬜ Not started | -     |
| 03   | `junie` adapter                        | ⬜ Not started | -     |
| 04   | `cli.py` wiring                        | ⬜ Not started | -     |
| 05   | Tests                                  | ⬜ Not started | -     |

**Legend:** ✅ Complete · 🔶 In progress / partial · ⬜ Not started

## Before starting task 02 or 03

Both adapters open with a spike against the real `copilot` / `junie` CLI (see plan.md's
per-harness sections) - their exact flags are explicitly unconfirmed in the plan, not guessed.
Do not begin writing `_build_copilot_command` or `_build_junie_command` from the plan's
placeholder flag names without first running that spike; the plan documents *what* to confirm,
not the confirmed answer.
