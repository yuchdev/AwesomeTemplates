# 01 - Spike: does Junie have a headless CLI mode?

**Parent task:** 03.0 `junie` adapter
**State:** ✅ Complete (2026-08-30) - Outcome 1 confirmed
**Depends on:** task 01.0
**Blocks:** 02 (this task); indirectly gates task 08.0 (Junie porting session,
which the milestone requires to run headless)

## Objective

Determine, against JetBrains' own current Junie documentation and (if
installable in this environment) the product itself, whether Junie exposes a
supported, documented, **non-interactive** invocation mode suitable for
unattended use in `generate`'s pipeline - as opposed to only an IDE-embedded,
interactive agent experience. This is research, not implementation - no source
file changes.

## Questions to answer

1. Does JetBrains publish a CLI or headless/CI mode for Junie at all, under
   any name? (Check current JetBrains documentation and release notes - this
   is a fast-moving product area, so re-verify rather than relying on
   knowledge that may predate a relevant release.)
2. If yes: what is its invocation contract - binary name, non-interactive
   flag, prompt-delivery mechanism (stdin vs. argument), tool/permission
   configuration, model selection (if any), and exit-code/output contract?
   Answer the same five categories of question task 02.0 subtask 01 asks for
   Copilot, adapted to whatever Junie's actual surface turns out to be.
3. If no: is there a stated roadmap or public signal that one is planned? Not
   load-bearing for this task's outcome, but worth recording for whoever
   revisits this later.

## Outcome and next step

- **Outcome 1 (headless mode exists and is documented):** record its
  confirmed contract in this file; subtask 02 builds `_build_junie_command` +
  a fully-functional `_JUNIE` registration from it, following task 02.0
  subtask 02's pattern.
- **Outcome 2 (no such mode exists):** record that finding explicitly in this
  file and in `status.md`; subtask 02 ships the registered-but-unavailable stub
  instead. This is the expected, legitimate outcome per
  [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s own
  framing - do not treat it as a blocker requiring escalation, and do not
  invent a contract to avoid landing on it.

## Constraints

- Confirm against current, dated sources - cite what was checked and when in
  this file, since "Junie has no CLI mode" is exactly the kind of fact that
  can go stale.
- Do not guess a plausible-sounding CLI contract in the absence of
  confirmation - outcome 2 is an acceptable, documented result; a fabricated
  outcome 1 is not.

## Success criteria

- [x] This file records a dated, sourced answer: either outcome 1 with a
      confirmed contract, or outcome 2 with the evidence that no such mode
      exists (or could not be confirmed) as of the check date.
- [x] `status.md` reflects the spike's outcome before subtask 02 starts.

## Findings (2026-08-30) - Outcome 1: headless mode confirmed

Confirmed against the installed standalone Junie CLI (`Junie version: 26.8.24 (2929.5)`,
`/Users/atatat/.local/bin/junie` - a separate binary from the JetBrains IDE plugin, installed via
JetBrains' own distribution, not bundled inside an IDE) via `junie --help` and two live
non-interactive invocations against an isolated scratch project directory (one with
`--output-format text`, one with `--output-format json`).

**Q1. Does JetBrains publish a CLI/headless mode at all?** **Yes.** `--help`'s own usage banner
states it plainly: "Non-interactive mode: `junie \"Fix the bug in the login function\"`" /
"`junie --task \"Fix the bug\"`", and a "System (non-interactive only)" options group exists
specifically for this mode (`--input-format`, `--output-format {text,json,json-stream}`,
`--json-output-file`, `--gateway-status`/`--gateway-stop`/`--gateway`). This is not an
IDE-embedded-only experience - it is a genuine standalone CLI product.

**Q2. Invocation contract**, answered per the same five categories as the Copilot spike:

1. **Non-interactive flag + exit-code contract:** the positional argument or `--task=<text>` IS
   the non-interactive trigger (no separate `-p`-style switch is needed the way claude/copilot
   have one - passing a task string is itself what selects non-interactive mode). Two live runs
   both exited `0` on success. A failure-path exit code was **not observed** in this environment
   (this machine already has valid cached Junie authentication via the JetBrains toolbox
   installation, so no auth-failure path was reachable to test, unlike the Copilot spike which
   happened to hit a real auth error) - noted as an unconfirmed gap, not guessed.
2. **Tool-allowlist syntax:** **no such flag exists anywhere in the CLI surface.** `--help`'s full
   option listing (Core/Authentication/System/Model/MCP/Extensions/Skills/Commands/Custom
   agents/Acp/Misc groups) contains nothing resembling claude's `--tools` or copilot's
   `--allow-tool`/`--deny-tool`. A live task instructed "Do not modify any files" and Junie
   complied (`"### Changes\n- No files were modified."`), but that is prompt-following, not a
   sandboxing guarantee - there is no CLI-level mechanism to *enforce* a read-only or
   restricted-tool posture the way claude/copilot both have one. This is a genuine capability gap,
   not an unconfirmed detail - recorded explicitly as a design concern for subtask 02 and task
   04.0's docs (see "Design concern" below), not something to route around by guessing a
   nonexistent flag.
3. **Permission-bypass equivalent:** not applicable - there is no permission-prompt system in
   non-interactive mode to bypass in the first place (consistent with #2: nothing gates tool use
   at all in this mode). `--brave` ("Turns on Brave Mode") exists but is explicitly marked
   "(interactive only)" in `--help`, so it plays no role in `_build_junie_command`.
4. **Prompt-delivery mechanism:** confirmed **`"arg"`** - `--task=<text>` or the bare positional
   argument, never stdin. `_JUNIE.prompt_via = "arg"`.
5. **Model selection:** `--model=<text>` ("Model to use for the primary agent") exists, plus
   `--effort=<text>` (low/medium/high) and `--provider=<text>` (BYOK: openai/anthropic/google/
   xai/openrouter/copilot/litellm - "If not set, the Junie or Custom model provider is used").
   Live evidence (`--output-format json`'s `llmUsage` array) shows the **default, unconfigured**
   run orchestrates across `gpt-5.4`, `gpt-4.1-2025-04-14`, `gpt-4.1-mini-2025-04-14`, and
   `gpt-5.4-nano` - i.e. Junie's own default routing is OpenAI-family, multi-model, and does
   **not** use Anthropic unless `--provider anthropic --anthropic-api-key <key>` is explicitly
   passed (a separate, opt-in BYOK path, same posture as Copilot's spike finding - out of scope,
   not a substitute for a `default_model` value). No opus-comparable single alias is confirmed for
   the default path. `_JUNIE.default_model = None`; `_build_junie_command` omits `--model` when
   unset, same pattern as `_build_copilot_command`.

**Output format:** `--output-format text` includes ANSI color escape codes in stdout (verified -
raw bytes like `\x1b[38;5;78m`); `--output-format json` gives clean structured JSON with
`sessionId`, `taskName`, `result` (markdown summary text), `changes` (array, empty when nothing
was modified), and `llmUsage` (per-model call/cost/token breakdown) - **recommend
`_build_junie_command` use `--output-format json`**, unlike claude/copilot's `text`, since it is
both cleaner for `log.debug`'s command-result logging and avoids embedding raw ANSI bytes in any
future reconciliation logic. This does not change `resolve_tree_headless`'s reconciliation
mechanism (still a before/after `markers.scan_tree` diff regardless of harness), only what ends up
in logs.

**Design concern for subtask 02 / task 04.0 docs (not a blocker):** unlike `claude` (hard
tool-allowlist) and `copilot` (`--allow-tool`/`--deny-tool` pair), a Junie headless session
currently has **no CLI-level mechanism to restrict which actions it can take** - it runs with
whatever autonomy its own agent mode grants, scoped only by `--project <dir>` (a working-directory
boundary, not a tool boundary). `_JUNIE`'s registration and `_build_junie_command`'s docstring
should say this plainly, and task 04.0's `--harness junie` docs/help text should carry the same
caveat, so a user choosing `--harness junie` knows the blast radius differs from `claude`/`copilot`
before relying on it. This is exactly the kind of per-harness permission-model gap [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s own
Non-goals section anticipates and defers ("follow-up scope for that harness's own task, not a
redesign of `Harness` itself") - not something this milestone needs to solve by inventing a flag
that does not exist.

**Auth:** `-a, --auth=<text>` (JetBrains account token via `https://junie.jetbrains.com/cli`) is
the default auth mechanism - confirms `forwards_anthropic_key=False` is correct for `_JUNIE`
(same reasoning as `_COPILOT`: a different, harness-owned auth mechanism, not `ANTHROPIC_API_KEY`).
Both live test runs authenticated silently using this machine's pre-existing cached credentials
(no prompt, no explicit `-a` passed) - `find_harness`/binary discovery needs no special auth
handling beyond what `resolve_tree_headless` already does per-harness.

**Binary name:** confirmed single name `"junie"` (`/Users/atatat/.local/bin/junie`); no evidence of
alternate install-method names in `--help` or on this system.
