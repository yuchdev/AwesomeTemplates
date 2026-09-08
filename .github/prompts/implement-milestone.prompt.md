---
name: implement-milestone
description: Drive a roadmap milestone to completion using the Claude loop as the behavioral source of truth.
agent: agent
---

Read `.claude/loops/implement-milestone.md` and follow it as the authoritative workflow.
Treat any additional user input as the milestone argument.
Apply these Copilot adaptations while preserving the Claude behavior:
- Use `.github/copilot/state/implement-milestone-{milestone-slug}.json` for any derived cursor or resumable state you create.
- When the Claude loop says to reschedule itself, continue iterating within the current Copilot session until the milestone completes or you hit a stop-and-ask gate.
- Invoke the Copilot prompt forms `/implement-subtasks`, `/verify-subtask`, `/test-gap`, `/pr-review`, and `/update-docs` instead of Claude `/loop ...` or slash-command spellings.
- Keep `.claude/settings.json` and `.github/copilot-instructions.md` in mind for hook-parity checks that Claude would have received automatically.
If no input is supplied or the milestone is ambiguous, stop and ask the user to disambiguate it.
