---
name: implement-subtasks
description: Drive one roadmap task through its subtask queue using the Claude loop as the behavioral source of truth.
agent: agent
---

Read `.claude/loops/implement-subtasks.md` and follow it as the authoritative workflow.
Treat any additional user input as the task argument.
Apply these Copilot adaptations while preserving the Claude behavior:
- Use `.github/copilot/state/implement-subtasks-{task-slug}.json` for any derived cursor or resumable state you create.
- When the Claude loop says to reschedule itself, continue iterating within the current Copilot session until the task completes or you hit a stop-and-ask gate.
- Use the Copilot prompt forms `/verify-subtask`, `/test-gap`, `/pr-review`, and `/update-docs` instead of Claude loop or slash-command names.
- Apply the automation expectations from `.github/copilot-instructions.md` where Claude relied on automatic hooks.
If no input is supplied or the task is ambiguous, stop and ask the user to identify it.
