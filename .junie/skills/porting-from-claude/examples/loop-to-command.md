# Example: wrap a Claude loop as a Junie command

Use the `update-docs` port already present in this repository as the model:

- Claude source: [../../../../.claude/loops/update-docs.md](../../../../.claude/loops/update-docs.md)
- Junie target: [../../../commands/update-docs.md](../../../commands/update-docs.md)

## What stayed the same

- The Claude loop remains the authoritative workflow.
- The command still takes the loop argument through `$prompt`.
- The workflow still converges by repeated passes until only review-only leftovers remain.

## What changed for Junie

- The Junie file is short and declarative rather than duplicating the whole loop.
- State, if needed, moves under `.junie/state/...`.
- Claude loop or slash-command names are translated into Junie command forms such as `/link-check`
  and `/doc-xref`.
- Hook-driven expectations are pointed at [../../../playbook.md](../../../playbook.md) instead of a
  copied hook directory.

## Reusable wrapper template

```markdown
Read `.claude/loops/<name>.md` and follow it as the authoritative workflow.
Treat `$prompt` as the loop argument.
Apply these Junie adaptations while preserving the Claude behavior:
- Use `.junie/state/<state-file>` for derived cursor or resumable state.
- When the Claude loop says to reschedule itself, keep iterating in the current Junie session.
- Replace Claude loop or slash-command spellings with Junie command forms.
- Keep `.junie/playbook.md` in mind for hook-parity checks Claude would have received automatically.
```

## When to use this pattern

Use it when the Claude source is already a good workflow document and Junie only needs a thin entry
point. If you find yourself rewriting the whole loop from scratch, stop and ask whether you are
duplicating maintainership burden for no benefit.
