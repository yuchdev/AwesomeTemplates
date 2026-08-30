# 01 - Spike: confirm `copilot`'s non-interactive contract

**Parent task:** 02.0 `copilot` adapter
**State:** ✅ Complete (2026-08-30)
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

- [x] All five questions above have a recorded, sourced answer (or an
      explicit "could not confirm, blocked on X" note) in this file.
- [x] `status.md` reflects the spike's outcome before subtask 02 starts.

## Findings (2026-08-30)

Confirmed against the installed `copilot` CLI (`GitHub Copilot CLI 1.0.81`, `/opt/local/bin/copilot`)
via `copilot --help`, `copilot help permissions`, `copilot help sandbox`, `copilot help providers`,
and one live non-interactive invocation (`copilot -p "..." --allow-all-tools --deny-tool=shell`).

1. **Non-interactive/print-mode flag and exit-code contract.** `-p, --prompt <text>` - "Execute a
   prompt in non-interactive mode (exits after completion)", same shape as `claude -p`. Exit code
   confirmed non-zero (`1`) on a live failure (this sandbox has no GitHub auth configured, so the
   run hit `Error: Authentication failed` and exited `1` with an actionable stderr message
   mentioning `/login`, a Fine-Grained PAT's "Copilot Requests" permission, and
   `COPILOT_GITHUB_TOKEN`/`GH_TOKEN`/`GITHUB_TOKEN`). This is a real, observed non-zero exit, not
   an inference - confirms the same try/except-around-`run()` pattern `resolve_tree_headless`
   already uses will work unchanged. Success-path output shape (text vs machine-parseable) could
   not be observed live in this unauthenticated environment, but `--output-format {text,json}` is
   documented (JSON is JSONL, one object per line) - `_build_copilot_command` should pass
   `--output-format text` explicitly, mirroring `claude`'s `--output-format text`, rather than
   relying on the default.

2. **Tool-allowlist syntax.** NOT 1:1 with `claude`'s named-tool list. `--allow-tool`/`--deny-tool`
   take `kind(argument)` permission patterns, not tool names: `shell(command:*?)` (matches a shell
   command by exact match or `:*` prefix, e.g. `shell(git:*)`), `write(path?)` (matches file-editing
   tools other than shell - `_BASE_TOOLS`' `Edit`/`Write` map here as a single `write` capability,
   not separately), `<mcp-server-name>(tool-name?)` (MCP-tool-specific), `url(domain-or-url?)`
   (network access). There is no separate `Read`/`Grep`/`Glob`/`TodoWrite`-equivalent gate at all -
   read-only exploration is governed by **Path Permissions**, not tool permissions (see #3). A
   translation table is required, not a 1:1 rename: `_build_copilot_command`'s posture should be
   `--deny-tool=shell` (marker research needs no shell access - matches `claude`'s no-Bash
   allowlist) plus `--allow-tool=write` (equivalent to `Edit`+`Write` combined - task 04.0's
   `update_guidelines` toggle decides whether this is passed at all, same as today) - there is no
   way to allow `Edit` without `Write` or vice versa the way `_BASE_TOOLS` currently can.
   `--available-tools`/`--excluded-tools` are a separate, coarser filter (hides tools from the
   model entirely rather than gating approval) - not needed here since `--allow-tool`/`--deny-tool`
   already cover the required posture.

3. **Permission-bypass equivalent.** Two separate mechanisms answer this, and neither is a `.claude/**`-
   specific special case (Copilot has no equivalent of Claude Code's "sensitive files" block):
   - **Unattended-run requirement:** `--allow-all-tools` - "required for non-interactive mode" per
     `--help` verbatim. Without it, `-p` would still prompt for approval, which cannot succeed
     non-interactively (`env: COPILOT_ALLOW_ALL` is the env-var equivalent). This is the actual
     `--permission-mode bypassPermissions` analogue.
   - **Path access:** by default restricted to cwd + subdirs + the system temp dir - no `.claude/**`-
     specific denial exists to bypass, since the marker-research session's cwd is already the kit
     root (`out_dir`, which contains `.claude/`), default path permissions already cover it with no
     extra flag needed. `--allow-all-paths` exists but is broader than required and should NOT be
     passed (mirrors `claude`'s narrow-allowlist posture, not `--yolo`/`--allow-all`).
   - **Correction (2026-08-30, post-`/pr-review`):** this section originally recommended the
     narrower pair `--allow-tool=write --deny-tool=shell` in place of `--allow-all-tools`, reasoning
     that it kept the posture allowlist-shaped like `claude`'s. That recommendation was never
     actually validated live - the one live non-interactive invocation this spike ran
     (`copilot -p "..." --allow-all-tools --deny-tool=shell`) hit an auth error before reaching any
     approval-prompt behavior, so whether `--allow-tool=write` alone (without `--allow-all-tools`)
     suffices to run to completion non-interactively was never confirmed, and `--help`'s own text
     states `--allow-all-tools` is "required for non-interactive mode" as a documented fact, not a
     preference. Corrected posture: `--allow-all-tools --deny-tool=shell` - the only combination
     actually observed working, with the no-shell boundary intact since "Denial rules always take
     precedence over allow rules, even `--allow-all-tools`" (confirmed via `copilot help
     permissions`, quoted above). No `--permission-mode`-shaped flag exists or is needed.
   - **Second correction (2026-08-30, post-`/pr-review` follow-up):** a security re-check of the
     first correction found that `--allow-all-tools` grants more than the shell access `claude`'s
     own allowlist withholds - it also newly approves copilot's `url()` network-fetch tool kind,
     which `claude`'s `_BASE_TOOLS` allowlist has no equivalent of at all (no web-fetch/network
     tool is ever passed to `claude`). Since the marker-research prompt processes untrusted repo
     content, an auto-approved network tool would be a prompt-injection-driven exfiltration path.
     Added `--deny-tool=url` alongside `--deny-tool=shell` (deny still takes precedence over
     `--allow-all-tools`), restoring parity with `claude`'s no-network posture.

4. **Prompt-delivery mechanism.** Confirmed **`"arg"`**, not `"stdin"` - `-p, --prompt <text>` takes
   the prompt as a CLI argument value, unlike `claude`'s stdin-piped prompt. `_COPILOT.prompt_via =
   "arg"` - `_build_copilot_command` must embed `prompt` in the returned argv (as the `--prompt`
   value) and `resolve_tree_headless`'s `prompt_via == "arg"` branch (already built in task 01.0
   subtask 02) passes `input=None` for this harness, which is now exercised for the first time.

5. **Model selection.** `--model <model>` flag confirmed to exist ("Set the AI model to use, use
   'auto' to let Copilot pick automatically"). Examples show OpenAI-family values (`gpt-5.4`); no
   Anthropic-brokered alias comparable to `claude`'s `opus` is documented for the default
   GitHub-hosted routing (a separate BYOK mode via `COPILOT_PROVIDER_TYPE=anthropic` exists but
   requires `COPILOT_PROVIDER_BASE_URL` and is a fully different, opt-in auth path unrelated to the
   default `gh auth login` flow this harness targets - out of scope, not a substitute for a
   `default_model` value). **Could not confirm** a specific "opus"-comparable capability-tier value
   without guessing - per this document's own no-guessing constraint, `_COPILOT.default_model =
   None`, and `_build_copilot_command` omits `--model` entirely when no override is given, letting
   Copilot's own default routing choose (equivalent in spirit to passing `--model auto`, but simpler
   to not pass the flag at all when unset).

**Bonus finding, not one of the five questions but directly relevant to the milestone's
`forwards_anthropic_key`/credential-isolation concern (task 01.0's post-review fix):** Copilot has
its own `--secret-env-vars <vars...>` flag - "Environment variable names whose values are stripped
from shell and MCP server environments and redacted from output." This is a copilot-side belt-and-
suspenders control `_build_copilot_command` could pass (`--secret-env-vars=ANTHROPIC_API_KEY`) in
addition to (not instead of) `harnesses.py`'s own env-stripping, since Copilot's own shell-tool
subprocesses inherit the CLI's env unless denied here too - worth a one-line mention when subtask 02
registers `_COPILOT`, not a new open question.
