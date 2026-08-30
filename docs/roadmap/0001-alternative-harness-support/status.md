# Milestone 0001 - Alternative Headless Harness Support - Status

Tracks progress against [plan.md](plan.md). **✅ Complete as of 2026-08-30** - all 9 tasks
delivered, reviewed, and merged into this status record; see the gate-status line below the
table and each task's own summary section for details. (Corrected the header above from "0002"
to "0001" at milestone close, matching this folder's actual name and `docs/roadmap/README.md`'s
now-corrected index entry - both were stale from before this milestone's numbering settled.)

## Current status

| Task | Name                                     | Status         | Tests |
|------|---------------------------------------------|----------------|-------|
| 01.0 | `harnesses.py` + `claude` relocation         | ✅ Complete    | `tests/test_headless.py` |
| 02.0 | `copilot` adapter                            | ✅ Complete    | -     |
| 03.0 | `junie` adapter                              | ✅ Complete    | -     |
| 04.0 | `cli.py` wiring                              | ✅ Complete    | -     |
| 05.0 | Tests                                        | ✅ Complete    | `tests/test_harnesses.py`, `tests/test_headless.py`, `tests/test_cli.py` |
| 06.0 | `--port-to` pipeline orchestration           | ✅ Complete    | -     |
| 07.0 | Copilot porting session                      | ✅ Complete    | -     |
| 08.0 | Junie porting session (headless)             | ✅ Complete    | -     |
| 09.0 | Porting pipeline tests                       | ✅ Complete    | `tests/test_port.py`, `tests/test_cli.py` |

**Legend:** ✅ Complete · 🔶 In progress / partial · ⬜ Not started

**Gate status (2026-08-30):** `uv run pytest --cov=awesome_templates` - **249 passed**, coverage
**87%** (baseline at milestone authoring: 191 tests). `uv run ruff check src/ tests/` - clean.
No real `copilot`/`junie` binary ever invoked by the test suite. `/link-check docs/roadmap/` -
clean except pre-existing, unrelated dangling links (tracked in Notes & decisions below, not
introduced by this milestone). Every item in `plan.md`'s Acceptance criteria checklist is
satisfied - see the per-task Delivered/Tests summaries below for the specific evidence each one
rests on. All milestone exit gates pass.

## Before starting task 02.0 or 03.0

Both adapters open with a spike against the real `copilot` / `junie` CLI (see [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s
per-harness sections) - their exact flags are explicitly unconfirmed in the plan, not guessed.
Do not begin writing `_build_copilot_command` or `_build_junie_command` from the plan's
placeholder flag names without first running that spike; the plan documents *what* to confirm,
not the confirmed answer.

**Copilot spike (02.0 subtask 01): done, 2026-08-30.** Confirmed against the real installed
`copilot` CLI (`GitHub Copilot CLI 1.0.81`) - see
[01-spike-copilot-contract.md](02.0-copilot-adapter/01-spike-copilot-contract.md#findings-2026-08-30)
for full sourcing. Headline outcomes for subtask 02 (as finally shipped, post-`/pr-review`
corrections - see Notes & decisions below): `prompt_via="arg"` (not `"stdin"` like `claude`; raises
`ValueError` if `prompt` is `None`); tool gating is `--allow-all-tools --deny-tool=shell
--deny-tool=url` (`--allow-all-tools` is the confirmed unattended-mode requirement; both denials
claw the grant back down to parity with `claude`'s no-shell, no-network allowlist); no
`.claude/**`-specific bypass exists or is needed - default path permissions already cover the kit
root; `default_model=None` (no confirmed opus-comparable alias for the default GitHub-hosted
routing - BYOK's `COPILOT_PROVIDER_TYPE=anthropic` is a different auth path, out of scope).

**Junie spike (03.0 subtask 01): done, 2026-08-30. Outcome 1 - headless mode confirmed.**
Confirmed against the installed standalone `junie` CLI (`Junie version: 26.8.24 (2929.5)`, a
genuine CLI product, not IDE-only) via `--help` and two live non-interactive invocations - see
[01-spike-junie-headless-mode.md](03.0-junie-adapter/01-spike-junie-headless-mode.md#findings-2026-08-30---outcome-1-headless-mode-confirmed)
for full sourcing. Headline outcomes for subtask 02: `prompt_via="arg"` (`--task=<text>`/
positional, no stdin); `default_model=None` (default routing is OpenAI-family multi-model, not
Anthropic, confirmed via live `llmUsage` output; `--provider anthropic` is a separate opt-in BYOK
path, out of scope); `forwards_anthropic_key=False` confirmed correct (own JetBrains-account auth
via `-a`/cached token); recommend `--output-format json` over `text` (the latter emits raw ANSI
escape codes). **Design concern carried to subtask 02 and task 04.0's docs:** unlike `claude`/
`copilot`, Junie's CLI exposes **no tool/permission-restriction flags at all** - a headless Junie
session's blast radius is bounded only by `--project <dir>`, not by an allowlist; this must be
stated plainly in `_JUNIE`'s docstring and in `--harness junie`'s help text, not silently assumed
equivalent to the other two harnesses.

**Copilot porting-target spike (07.0 subtask 01): done, 2026-08-30.** Confirmed against the real
installed `copilot` CLI's own `--help` text (which cites GitHub's published docs URLs directly) -
see [01-spike-copilot-porting-target.md](07.0-copilot-porting-session/01-spike-copilot-porting-target.md#findings-2026-08-30)
for full sourcing. Headline outcomes for subtask 02: concrete targets confirmed for agents
(`.github/agents/`) and skills (`.github/skills/`/`.agents/skills/` - notably Copilot already
auto-discovers `.claude/skills/` too); no project-level convention exists for hooks or loops
(hooks only exist as something a *plugin* bundles, not a scanned directory) - the porting prompt
should say so explicitly rather than invent one; no additional tool-allowlist work needed since
`--allow-all-tools` (task 02.0's confirmed posture) already covers `Write` to every confirmed
target path.

## Before starting task 07.0 or 08.0

Both porting sessions depend on their adapter task's spike outcome (07.0 on 02.0, 08.0 on
03.0), plus 06.0's `--port-to` plumbing existing first. 08.0 additionally requires that 03.0
landed on outcome 1 (a confirmed headless Junie mode) - if 03.0 landed on outcome 2, 08.0 ships
only the honest-failure path for `--port-to junie`, per [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s acceptance criteria.

**Update 2026-08-30:** 03.0's spike landed on outcome 1 (confirmed above), so task 08.0 builds the
full headless Junie porting session per [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md)'s outcome-1 path, not the honest-failure stub.

**Junie porting-target spike (08.0 subtask 01): done, 2026-08-30.** Confirmed both via the
installed `junie` CLI's own `--help` text AND by direct filesystem inspection of real, populated
`.junie/` directories already present in several independent projects on this machine (this
repo's own included) - see
[01-spike-junie-porting-target.md](08.0-junie-porting-session/01-spike-junie-porting-target.md#findings-2026-08-30)
for full sourcing. Headline outcomes for subtask 02: `.junie/agents/<name>.md` for agents (flat,
mirrors `.claude/agents/` 1:1), `.junie/skills/<name>/SKILL.md` for skills (mirrors
`.claude/skills/` 1:1), `.junie/commands/` as an unconfirmed-shape candidate for loop-like
content, `.junie/guidelines.md` as the catch-all; no `.junie/hooks/` convention observed in any
sampled project - leave hooks with the same explicit "no fixed convention" escape hatch Copilot's
hint uses; no additional tool/permission grant needed (Junie has no restriction mechanism to
begin with, per task 03.0's outcome-1 finding).

## Notes & decisions

- 2026-08-30: `/pr-review` on task 02.0 went two rounds. Round 1 (feature-reviewer
  REQUEST_CHANGES): `_build_copilot_command`/`_build_junie_command` silently dropped the prompt
  when `None` instead of raising, producing malformed argv for copilot (its `-p` takes an adjacent
  value) and a worse silent fallback to interactive mode for junie (no separate non-interactive
  flag exists) - both fixed with an early `raise ValueError`. Also: the copilot tool-gating pair
  `--deny-tool=shell --allow-tool=write` was an untested substitution for `--allow-all-tools`, the
  only combination the spike's live test actually ran (copilot's `--help` documents
  `--allow-all-tools` as required for non-interactive mode) - corrected to
  `--allow-all-tools --deny-tool=shell`. Round 2 re-review (feature-reviewer LGTM) then triggered a
  narrow security follow-up that caught a second issue the flag correction introduced:
  `--allow-all-tools` also grants copilot's `url()` network tool, which `claude`'s own allowlist has
  no equivalent of - closed with `--deny-tool=url` (deny still precedes `--allow-all-tools`). Full
  history in `02.0-copilot-adapter/01-spike-copilot-contract.md`'s two dated correction notes under
  Q3 and `02-copilot-command-registration.md`'s "Post-review amendment" section.

- 2026-08-30: `/link-check docs/roadmap/` after task 01.0's close reports 9 pre-existing dangling
  links, none introduced by this task: `07.0-copilot-porting-session/README.md` links
  `src/awesome_templates/port.py` (doesn't exist yet - task 06.0's own deliverable);
  `plan.md` and `docs/roadmap/README.md` link `docs/roadmap/0001-ai-assisted-generation/plan.md`
  and `docs/roadmap/0002-alternative-harness-support/` (stale paths predating this milestone's
  folder settling as `0001-`). Left as-is - out of scope for this task, tracked here so a future
  cleanup pass has a starting point.

- 2026-08-30: Tasks 01.0-04.0 and 06.0-08.0 skip the generic per-subtask `/test-gap` gate -
  [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md) consolidates all new tests into dedicated tasks 05.0 and 09.0, whose own subtask specs
  already name the exact test files/cases. Regression tests for bugs found during `/pr-review`
  are still written immediately (see below) - this only defers coverage-gap/exploratory test
  authoring.
- 2026-08-30: `/pr-review` on task 01.0 (`security-auditor`) found a HIGH-severity credential-
  isolation defect: `resolve_tree_headless`'s env-construction copied the full parent
  environment in both branches, so a shell-exported `ANTHROPIC_API_KEY` was forwarded to any
  harness regardless of `forwards_anthropic_key`, defeating the exact isolation the milestone's
  acceptance criteria require for Copilot/Junie. Fixed in the same task close: the key is now
  explicitly popped from the copied environment when not forwarded, with a regression test
  (`tests/test_headless.py::test_non_forwarding_harness_strips_exported_key`) asserting it.
  Not a scope fork - no ratification needed, just recorded for traceability.

### Task 01.0 - `harnesses.py` + `claude` relocation (✅ 2026-08-30)

**Delivered:** New `src/awesome_templates/harnesses.py` module (`Harness` frozen dataclass,
`HARNESS_NAMES`, `find_harness`, `get`, `_REGISTRY`); `claude`'s adapter relocated out of
`headless.py` as `_build_claude_command` + `_CLAUDE` registration, byte-identical argv to the
pre-relocation `build_command`; `resolve_tree_headless` gained `harness: str = "claude"` and now
resolves the binary, model default, and prompt-delivery mode through the registry;
`ANTHROPIC_API_KEY` forwarding gated on `harness_obj.forwards_anthropic_key` (and now correctly
stripped, not just left unadded, when `False` - see Notes above); `cli.py`'s one call site
updated to go through `harnesses.find_harness`/`get`; `src/awesome_templates/CLAUDE.md`'s module
map documents `harnesses.py` and the now harness-agnostic `headless.py` entry.

**Tests / gate:** `uv run pytest --cov=awesome_templates` - 194 passed (baseline was 191 at
milestone authoring), coverage 86%. `uv run ruff check src/ tests/` clean. `/pr-review`:
feature-reviewer LGTM (non-blocking suggestions on `prompt_via` validation and additional
`find_harness`/`get` edge-case coverage deferred to task 05.0); security-auditor
PASS_WITH_FOLLOWUP, the one HIGH finding fixed before close as noted above. No deferred
subtasks.

### Task 02.0 - `copilot` adapter (✅ 2026-08-30)

**Delivered:** Subtask 01 - a live research spike against the actually-installed GitHub Copilot
CLI (`1.0.81`) confirming its non-interactive contract (recorded in
[01-spike-copilot-contract.md](02.0-copilot-adapter/01-spike-copilot-contract.md#findings-2026-08-30),
including two post-review corrections - see Notes above). Subtask 02 - `_build_copilot_command` +
`_COPILOT` registered in `src/awesome_templates/harnesses.py`: `prompt_via="arg"` (raises
`ValueError` if `prompt` is `None`), tool gating `--allow-all-tools --deny-tool=shell
--deny-tool=url`, `--secret-env-vars=ANTHROPIC_API_KEY` defense-in-depth, `default_model=None`
with `--model` omitted when unset, `forwards_anthropic_key=False`. A shared fix in `headless.py`
(from `/pr-review`'s security findings) now redacts the prompt from `log.debug`'s command-log line
for any `prompt_via="arg"` harness and gracefully degrades instead of crashing on an `OSError`
(`ARG_MAX`) from an oversized argv-embedded prompt - benefits `junie` (03.0) equally.

**Tests / gate:** `uv run pytest --cov=awesome_templates` - 196 passed (2 new regression tests from
the shared `headless.py` fix: prompt redaction in debug logs, graceful `OSError` degradation),
coverage 86%. `uv run ruff check src/ tests/` clean. `/pr-review` went two rounds - see Notes &
decisions above for the full history (prompt=None malformed argv, then an untested tool-flag
substitution, then a follow-up security catch on network-tool over-grant) - final verdict LGTM /
no new CRITICAL or HIGH. No deferred subtasks.

### Task 09.0 - Porting pipeline tests (✅ 2026-08-30) - final task of this milestone

**Delivered:** New `tests/test_port.py` (14 tests: 6 pure `render_porting_manifest`/`build_porting_prompt`
tests, plus 8 subprocess-boundary `port_tree_headless` tests parametrized across both `copilot`
and `junie`) - `port.py` coverage 0% -> 84% (remaining gap: timeout/`OSError` degradation branches,
explicitly deferred). `tests/test_cli.py` gained 5 `--port-to` validation/gating/dispatch tests,
including the milestone's single most load-bearing negative test (`--harness copilot --port-to
junie` must fail on the strict "harness must be claude" rule, not merely a self-port check) -
`cli.py`'s `--port-to` branches now covered. Three corrections to the subtask specs' own code
samples, all independently verified during `/verify-subtask`: a missing-binary test uses the
established `find_harness`-monkeypatch fix instead of the flaky `PATH=""` pattern; the dispatch
test reconstructs the expected prompt via the real `render_porting_manifest`/`build_porting_prompt`
functions rather than the spec's incorrect `input`-derived assertion; the final CLI test patches
`awesome_templates.headless.resolve_tree_headless` directly (cli.py imports `headless` lazily
inside the function body, so `cli_module.headless` doesn't exist as an attribute).

**Tests / gate:** `uv run pytest --cov=awesome_templates` - **249 passed**, coverage **87%**
(milestone-final aggregate, up from the 191-test baseline at authoring). `uv run ruff check src/
tests/` clean. `/pr-review`: feature-reviewer LGTM. Follow-ups noted, not fixed (out of this
task's stated scope, no coverage floor exists in this project): a happy-path port-dispatch CLI
test (exit 0 with a populated `summary["ported_to"]`) isn't covered; `port_tree_headless`'s
`forwards_anthropic_key=True` `ValueError` guard has no dedicated regression test; two structurally
identical `test_cli.py` tests (copilot/junie missing-binary, from task 05.0) could be parametrized
like `test_port.py` does; a stale comment in `test_port.py` was flagged for wording only, not
substance. No deferred subtasks.

### Task 08.0 - Junie porting session (✅ 2026-08-30, Outcome 1)

**Delivered:** Subtask 01 - a research spike combining the installed `junie` CLI's own `--help`
text with unusually strong empirical evidence: real, populated `.junie/` directories already
existed on the researching machine in several independent projects (including this repo's own
working directory), directly confirming `.junie/agents/<name>.md` (flat files, mirrors
`.claude/agents/` 1:1) and `.junie/skills/<name>/SKILL.md` (mirrors `.claude/skills/` 1:1) as
real, in-use conventions - not just documented flags. Also observed: `.junie/commands/` (shape
unconfirmed, a candidate for loop-like content) and `.junie/guidelines.md` (catch-all), with an
honest, sample-scoped "no fixed convention" conclusion for hooks. Subtask 02 - `_JUNIE
.porting_target_hint` set from those findings; `_build_junie_command` unchanged, since subtask
01 confirmed Junie has no tool/permission-restriction mechanism to additionally grant against.

**Tests / gate:** `uv run pytest --cov=awesome_templates` - 230 passed (unchanged), ruff clean.
`/pr-review`: feature-reviewer LGTM. One factual error caught by `/verify-subtask` and fixed
before `/pr-review` (subtask 01's agent-file-count claim was off by 2 - corrected to match the
actual directory contents); one tracking oversight caught by `/pr-review` and fixed after (the
subtask 02 spec file's own State/checkboxes weren't updated, same recurring class of oversight as
earlier tasks in this milestone - worth remembering to check the spec file itself, not just
README.md/status.md, at every subtask close). No deferred subtasks.

### Task 07.0 - Copilot porting session (✅ 2026-08-30)

**Delivered:** Subtask 01 - a research spike against the real installed `copilot` CLI's own
`--help` text (which cites GitHub's published docs URLs directly), confirming concrete porting
targets: `.github/agents/` for agents, `.github/skills/`/`.agents/skills/` for skills (Copilot
already auto-discovers `.claude/skills/` too), `.github/copilot-instructions.md`/`AGENTS.md` as a
catch-all - and confirming no project-level convention exists for hooks or loops (a genuine,
disclosed absence, not guessed). Subtask 02 - `_COPILOT.porting_target_hint` set to a sentence
built from those findings; `_build_copilot_command` unchanged, since the spike found
`--allow-all-tools` already covers `Write` to every confirmed target path.

**Tests / gate:** `uv run pytest --cov=awesome_templates` - 230 passed (unchanged - the hint is a
static string with no dedicated test; `port.build_porting_prompt`'s existing verification already
covers hint-embedding mechanically), ruff clean. `/pr-review`: feature-reviewer LGTM. Two
non-blocking text-fidelity gaps fixed before close: the hint initially omitted the `.agents/skills/`
alternative the spike itself found, and initially overstated confidence on `.github/agents/`'s
cwd-auto-discovery (the spike only confirmed this via `--add-dir`'s help text, not independently
for the session's own cwd) - both corrected to match the spike doc exactly. Two more suggestions
tracked, not fixed: `_REGISTRY`'s module-level dict-mutation pattern (pre-existing since task 01.0,
spans all three harnesses, not something to refactor mid-milestone) and the missing dedicated test
for `porting_target_hint` (deferred - this hint was authored after tasks 05.0/09.0's named test
lists were written; a future test-gap pass can pin it). No deferred subtasks.

### Task 06.0 - `--port-to` pipeline orchestration (✅ 2026-08-30)

**Delivered:** New module `src/awesome_templates/port.py`: a pure manifest builder
(`render_porting_manifest`, reusing `catalog.discover` for the four Claude-authored kinds) and
prompt builder (`build_porting_prompt`, degrading to a generic instruction when a harness's
`porting_target_hint` is unset), plus the subprocess-boundary orchestrator `port_tree_headless`
(finds the target binary, builds its command via the same `harnesses.Harness.build_command`
contract, runs it with the established soft-failure posture - timeout/`OSError`/non-zero-exit
all degrade to a warning, never a crash). `cli.py` gains `--port-to {copilot,junie}` (enum-backed
Typer option, same deliberate `click.Choice` substitution as `--harness`), gated on
`--resolve-markers` and `--harness claude` (the default) even for a non-self-port combination,
dispatched after the initial Claude-authoring stage's summary is fully populated, with a hard
`_fail` (not a warning) if the target binary is missing.

**Tests / gate:** `uv run pytest --cov=awesome_templates` - 230 passed (unchanged - `port.py`
itself is 0% covered; CLI-level and unit-level porting tests are task 09.0's explicit scope, not
this task's), `port.py`/`cli.py` both ruff-clean. `/pr-review`: feature-reviewer LGTM (non-blocking:
missing console-output line for the porting stage - added; `PortToChoice` needing manual sync
with `HARNESS_NAMES` - commented; `_rel`'s duplication of `headless._rel_or_abs` - cross-referenced
in its docstring; `PortSummary.command_ok`'s `False`-as-default ambiguity for the never-ran case -
left as a tracked follow-up, not fixed, since resolving it changes the JSON summary's shape and is
better decided alongside task 09.0's tests). security-auditor PASS_WITH_FOLLOWUP: confirmed the
credential-isolation boundary (`env.pop("ANTHROPIC_API_KEY", None)`, unconditional) is sound
regardless of the `assert` guard beside it, but recommended converting that `assert` to a
non-strippable `raise ValueError` for defense-in-depth (`python -O` would elide an `assert`) - done.
Two more follow-ups tracked, not fixed: the porting session inherits the full ambient environment
minus one key (same posture `headless.py` already has, and Junie has no CLI-level tool sandbox to
narrow it further - a pre-existing, already-accepted pattern, not new to this task), and the
manifest's Markdown table doesn't escape `|` in entity names/paths the way `headless.render_manifest`
does (low-severity, bounded by needing write access to the generator's own output tree already).
No deferred subtasks.

### Task 05.0 - Tests (✅ 2026-08-30)

**Delivered:** New `tests/test_harnesses.py` (23 tests, `harnesses.py` 70%→100% coverage) covering
`find_harness`/`get` contracts, `_build_claude_command`'s byte-identical argv pin, and
`_build_copilot_command`/`_build_junie_command`'s real confirmed argv shapes including the
load-bearing `ValueError`-on-missing-prompt regression tests. `tests/test_headless.py` gained 5
harness-dispatch tests (claude/copilot/junie paths, unknown-harness `KeyError`, claude-missing-
binary `RuntimeError`), each pinning the `ANTHROPIC_API_KEY` env boundary and stdin-vs-argv
delivery per harness. `tests/test_cli.py` gained 6 tests: the 4 the plan's acceptance criteria
name explicitly, plus a junie-flavored missing-binary variant (task 03.0's Outcome 1) and a
regression test for the task 04.0 config-file-harness-validation fix. No real `copilot`/`junie`
binary invoked anywhere.

**Tests / gate:** `uv run pytest --cov=awesome_templates` - 230 passed (up from 196 at task 04.0's
close), coverage 87%. `uv run ruff check src/ tests/` clean. `/pr-review`: feature-reviewer only
(pure test-authoring task, no production code changed, so no new auth/secret/integration surface
for security-auditor to threat-model) - LGTM, non-blocking style suggestions only (two redundant
assertion-subset tests worth trimming later, a cosmetic `tmp_path.resolve()` nit, general brittle-
ness-vs-contract-freeze tradeoff notes). No deferred subtasks.

### Task 04.0 - `cli.py` wiring (✅ 2026-08-30)

**Delivered:** `generate` gains `--harness {claude,copilot,junie}` (default `claude`, config-file
fallback `cfg.get("harness", "claude")`, CLI wins), rejected without `--resolve-markers` when
non-default; implemented as an enum-backed Typer option (`HarnessChoice`, derived from
`harnesses.HARNESS_NAMES`) rather than `click.Choice`, since this environment has no standalone
`click` package - an explicitly permitted alternative per the subtask's own Implementation Notes,
mirroring the existing `LogVerbosity` pattern. Dry-run output gains a `Harness: ...` console line /
`"harness"` JSON key. The `if resolve_value:` block's missing-binary branching is now a three-way
exhaustive split: binary found → run the session; binary missing and non-`claude` → hard failure
naming the harness (with a Junie-specific "no headless CLI mode yet" message when
`binary_names` is empty - currently unreachable since 03.0 confirmed Outcome 1, kept as
defensive/future-proof code, not dead-code-removed); binary missing and `claude` → today's
unchanged graceful fallback to `resolver.resolve_tree`. `summary["harness"]` added to the
non-dry-run JSON summary. Root `CLAUDE.md`'s Commands section documents `--harness` with an
example and a note (including Junie's no-tool-restriction caveat).

**Tests / gate:** `uv run pytest --cov=awesome_templates` - 196 passed, coverage 85%. `uv run ruff
check src/ tests/` clean. `/pr-review` went two rounds: round 1 (feature-reviewer and
security-auditor both, in parallel) found the same real gap independently - a config-file-sourced
`harness` value bypassed the CLI's enum validation entirely and reached `harnesses.get()`
unguarded, risking an uncaught `KeyError`/traceback instead of a clean `_fail(...)` (violating
`harnesses.get`'s own docstring contract). Fixed with a validation guard mirroring
`_resolve_preset`'s unknown-choice pattern, verified live (a bogus config-file harness now fails
cleanly with exit 1 instead of a traceback). Round 2 (feature-reviewer) confirmed the fix and
accepted two judgment-call responses to non-blocking suggestions: the junie dead-code branch stays
implemented (strengthened comment explaining why, and warning against "fixing" it by breaking real
Junie support), and the `--update-guidelines` + non-claude harness combination is confirmed a
functional no-op (not a bug) since copilot/junie already grant unconditional write access
regardless of the flag. Final verdict LGTM / PASS_WITH_FOLLOWUP, no CRITICAL or unresolved HIGH.
No deferred subtasks.

### Task 03.0 - `junie` adapter (✅ 2026-08-30)

**Delivered:** Subtask 01 - a live research spike against the actually-installed standalone Junie
CLI (`26.8.24`) confirmed **Outcome 1**: a genuine, documented non-interactive mode exists
(recorded in
[01-spike-junie-headless-mode.md](03.0-junie-adapter/01-spike-junie-headless-mode.md#findings-2026-08-30---outcome-1-headless-mode-confirmed)).
Subtask 02 - `_build_junie_command` + `_JUNIE` registered: `prompt_via="arg"` (raises `ValueError`
if `prompt` is `None`, mirroring copilot's fix), `--output-format json` (avoids ANSI-code noise
`text` emits), `--skip-update-check`, `default_model=None`, `forwards_anthropic_key=False`.
**Notable design concern carried forward:** Junie's CLI exposes no tool/permission-restriction
flag at all (unlike `claude`/`copilot`) - documented prominently in `_build_junie_command`'s
docstring and flagged for task 04.0's `--harness junie` help text, since a headless Junie
session's blast radius is bounded only by its working directory, not by an allowlist.

**Tests / gate:** covered by task 02.0's shared full-suite run (196 passed, coverage 86%, ruff
clean) since both tasks landed together against the same `harnesses.py`/`headless.py` diff.
`/pr-review` covered the shared `headless.py` fix as part of task 02.0's review; junie's own
registration subtask passed `/verify-subtask` cleanly with no defects raised against it directly.
No deferred subtasks.
