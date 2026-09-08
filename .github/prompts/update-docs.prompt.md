---
name: update-docs
description: Run the iterative documentation maintenance workflow using the Claude loop as the behavioral source of truth.
agent: agent
---

Read `.claude/loops/update-docs.md` and follow it as the authoritative workflow.
Treat any additional user input as an optional doc path. If omitted, run scan mode.
Apply these Copilot adaptations while preserving the Claude behavior:
- Use `.github/copilot/state/update-docs-scan.json` for any derived cursor or resumable scan state you create.
- When the Claude loop says to reschedule itself, keep iterating within the current Copilot session until the workflow converges or you hit a review-only remainder.
- Use the Copilot prompt forms `/link-check` and `/doc-xref` where the Claude loop refers to Claude slash commands or loops.
- Keep `.github/copilot-instructions.md` in mind for the hook-parity checks that Claude would normally receive automatically.
