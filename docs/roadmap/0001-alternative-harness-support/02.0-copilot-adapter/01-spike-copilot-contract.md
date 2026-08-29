# 01 - Spike: confirm `copilot`'s non-interactive contract

**Parent task:** 02.0 `copilot` adapter
**State:** ⬜ Not started
**Depends on:** task 01.0 (needs `harnesses.Harness`'s shape to know what to confirm)
**Blocks:** 02 (this task)

## Objective

Against a real, installed GitHub Copilot CLI (`copilot --help`, and its
published docs), answer every open question
[plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s "`copilot`
(GitHub Copilot CLI)" section lists, with no guessing. This is research, not
implementation - no source file changes.

## Questions to answer

1. **Non-interactive/print-mode flag and exit-code contract.** `claude`'s is
   `-p` plus a normal `0`/non-`0` exit code. What is `copilot`'s equivalent?
   Does it print machine-readable output on success, and does a failed session
   exit non-zero reliably (needed for the same try/except-around-`run()`
   pattern `resolve_tree_headless` already uses)?
2. **Tool-allowlist syntax.** `claude`'s is a trailing `--tools A B C ...`
   flag. GitHub's own docs describe per-tool allow/deny controls for Copilot -
   confirm the exact flag syntax, and whether `Read`/`Grep`/`Glob`/`Edit`/
   `TodoWrite`/`Write` (the tool names `_BASE_TOOLS` and
   `--update-guidelines`/porting use) have 1:1 Copilot equivalents, or need a
   translation table.
3. **Permission-bypass equivalent.** `claude`'s `--permission-mode
   bypassPermissions` exists specifically because Claude Code's permission
   layer blocks `Edit` on `.claude/**` as "sensitive files" even under normal
   auto-accept modes (verified empirically - see task 01.0 subtask 02's
   docstring). Does `copilot` have an equivalent special-case for any path
   pattern, and if so what unattended-run flag disables it?
4. **Prompt-delivery mechanism.** Stdin (matching `claude`) or a
   `--prompt`/positional argument? This decides `_COPILOT.prompt_via`
   (`"stdin"` or `"arg"` - see task 01.0 subtask 01's `Harness.prompt_via`
   docstring).
5. **Model selection.** GitHub Copilot brokers multiple model providers
   (including Anthropic models) behind one subscription - does `copilot`
   expose a `--model` flag, and if so what value selects a capability tier
   comparable to `claude`'s `opus` alias? If no such flag exists,
   `_COPILOT.default_model` should be `None` and `_build_copilot_command` must
   not attempt to pass a `--model`-shaped argument.

## Constraints

- Confirm against the actual installed CLI (`copilot --help`, `copilot
  --version`) and GitHub's own published documentation - not by inference from
  `claude`'s flags or from this document's own phrasing.
- If a question cannot be confirmed (the CLI isn't installed in this
  environment, or the docs are ambiguous), record that explicitly as an open
  blocker in this file and in `status.md` rather than filling in a guess -
  subtask 02 must not proceed past an unconfirmed answer.

## Success criteria

- [ ] All five questions above have a recorded, sourced answer (or an
      explicit "could not confirm, blocked on X" note) in this file.
- [ ] `status.md` reflects the spike's outcome before subtask 02 starts.
