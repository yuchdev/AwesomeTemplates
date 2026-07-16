# 0001 - Template ADR Record

> **Status:** Implemented
>
> **Date:** 2026-01-12
>
> **Supersedes:** _(none)_
>
> **Superseded by:** _(none)_

## Context

The CLI's long-running commands only printed a final result, with no
feedback while work was in progress. Users running multi-step or
multi-second commands couldn't tell whether the process had stalled or was
progressing normally, and had no visibility into which step was currently
running.

## Decision

Adopt a live-updating terminal UI, built on a rich-text terminal library,
for any CLI command that takes more than a couple of seconds. The view
subscribes to the same in-process event stream the command already emits
for logging, and renders a scrolling activity log plus a per-step status
panel, refreshed on a fixed tick rather than once per event (so bursts of
events don't cause flicker).

## Alternatives Considered

| Alternative | Pros | Cons | Reason rejected |
|-------------|------|------|-----------------|
| Plain sequential `print()` progress lines | Simplest, no new dependency | No sense of overall progress, clutters scrollback | Rejected - poor UX for multi-step commands |
| A separate `--verbose` log file, silent stdout | Keeps stdout clean | User has to `tail` a second file to see progress | Rejected - adds friction for the common case |
| Live-updating terminal UI (chosen) | Good in-terminal feedback, reuses existing event stream | Extra terminal-library dependency; needs a narrow-terminal fallback | **Accepted** |

## Consequences

### Positive

- Users see real-time progress without extra flags or a second window.
- The event stream that already exists for logging becomes the single
  source of truth for both the log file and the live view.

### Negative

- Terminals narrower than a minimum width need a simpler fallback view
  (plain sequential lines) since the panel layout doesn't fit.
- One more third-party dependency to keep updated.

## Validation / Rollout

- Manual check across a few common terminal emulators and widths.
- Unit tests for the view's pure formatting helpers and its event-to-state
  transitions; a render smoke test that the view doesn't raise on a full
  event sequence.

## Links

- **Roadmap task:** _(link to the task that introduced this, once you have one)_
- **Supporting specs:** _(none)_
- **Diagrams:** [assets/0001-example-view.mmd](assets/0001-example-view.mmd)
