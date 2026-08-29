# Milestone 0002 - Alternative Headless Harness Support

**Status:** not started, not scheduled. Design only - see [status.md](status.md).

## Why this milestone exists

`generate --resolve-markers`'s primary resolution path,
[`headless.py`](/src/awesome_templates/headless.py) (shipped in
[0001-ai-assisted-generation](/docs/roadmap/0001-ai-assisted-generation/plan.md), task 01.0
subtask 03), is hard-wired to exactly one external tool: the `claude` CLI. That CLI's own
design doc already names the dependency as a deliberate trade -
[`0001.../03-agentic-marker-research.md#prerequisites-and-detection`](/docs/roadmap/0001-ai-assisted-generation/01.0-working-implementation/03-agentic-marker-research.md) -
and flags exactly the scenario this milestone answers: *"a CI environment that can install a
Python package via the `ai` extra but cannot install a Node-based CLI, or a policy that
forbids it."* An organization standardized on GitHub Copilot or JetBrains tooling instead of
Claude Code hits that wall today with no alternative but the weaker one-shot API fallback
(`resolver.resolve_tree`), which the same document diagnoses as producing instruction-echo on
exactly the markers that need real research.

This milestone adds two more headless backends - **GitHub Copilot CLI** (`copilot`) and
**JetBrains Junie** (`junie`) - selectable alongside `claude` via a new `--harness` flag, so a
site that has one of those installed and licensed instead of Claude Code gets the same
manifest-driven research pass `headless.py` already does for `claude`, not a downgrade to the
one-shot fallback.

## What `headless.py` does today that must stay harness-agnostic

Re-reading `headless.py` with an eye for "what depends on `claude` specifically" versus "what
is genuinely generic":

**Already generic - unchanged by this milestone:**
- `render_manifest` / `build_prompt` (the marker table + research method + resolution rules
  text handed to the session) - plain prose, no CLI-specific syntax.
- Reconciliation (`_count_fallbacks`, the before/after `markers.scan_tree` diff) - reads the
  edited files, not anything the CLI itself reports.
- `detect_project_root` - filesystem heuristics, no CLI involvement.

**`claude`-specific today - this is what the abstraction below isolates:**
- `find_claude()` - one hardcoded binary name.
- `build_command()` - `claude`'s own flag names (`-p`, `--output-format text`,
  `--setting-sources user`, `--permission-mode bypassPermissions`,
  `--no-session-persistence`, `--model`, `--tools`).
- `HEADLESS_MODEL = "opus"` - a `claude`-specific model alias.
- The prompt-delivery mechanism (`input=prompt` to `subprocess.run`, i.e. stdin) - happens to
  be how `claude -p` takes a piped prompt; not yet verified as universal.
- The `ANTHROPIC_API_KEY` forwarding in `resolve_tree_headless`'s `env` construction - only
  meaningful for a `claude`/Anthropic-backed session; `copilot` and `junie` authenticate
  through entirely different mechanisms (see "Auth" below).

## Proposed architecture: a `Harness` per backend, one small registry

New module `src/awesome_templates/harnesses.py` (flat, not a subpackage - three ~20-30 line
adapters plus a registry doesn't yet need "one file per concern" the way `markers.py`/
`resolver.py`/`ai/client.py` do; split it out later if a real adapter grows past that):

```python
"""Per-backend adapters for the headless marker-research session: binary
discovery and argv construction for each supported CLI. headless.py stays
responsible for *what* the session needs to do (the manifest, the prompt,
reconciliation) - this module is only responsible for *how* to ask a given
CLI to do it, so a wrong guess about one backend's flag names is a
one-function fix here, not a rewrite of resolve_tree_headless.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Callable, Optional

HARNESS_NAMES = ("claude", "copilot", "junie")


@dataclass(frozen=True)
class Harness:
    name: str
    binary_names: tuple[str, ...]        # candidates tried in order via shutil.which
    default_model: Optional[str]         # None when the backend has no CLI model flag
    prompt_via: str                      # "stdin" | "arg" - how the prompt reaches the CLI
    forwards_anthropic_key: bool         # only True for claude
    build_command: Callable[..., list[str]]  # (binary, *, model, tools, update_guidelines) -> argv


def find_harness(harness: Harness) -> Optional[str]:
    """Absolute path of the first installed candidate binary, or None -
    same contract headless.find_claude() has today, generalized."""
    for candidate in harness.binary_names:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def get(name: str) -> Harness:
    """Look up a harness by --harness value; raises KeyError on an unknown
    name - cli.py turns that into the same _fail(...) shape _resolve_preset
    already uses for an unknown preset."""
    return _REGISTRY[name]


_REGISTRY: dict[str, Harness] = {
    "claude": _CLAUDE,
    "copilot": _COPILOT,
    "junie": _JUNIE,
}
```

`headless.py` changes shape only at its edges:
- `find_claude()` is replaced by `harnesses.find_harness(harnesses.get(name))`; `cli.py`'s one
  call site (`headless.find_claude()`) becomes `harnesses.find_harness(harnesses.get(harness_value))`.
- `build_command()` moves into `harnesses.py` as `_build_claude_command`, registered on `_CLAUDE`.
- `resolve_tree_headless` gains a `harness: str = "claude"` parameter, uses it to look up the
  `Harness`, and only forwards `ANTHROPIC_API_KEY` in `env` when
  `harness_obj.forwards_anthropic_key` is true.
- Everything else in `resolve_tree_headless` (manifest, prompt, reconciliation) is untouched -
  this is the whole point of the split.

### `claude` (baseline - already shipped, just relocated)

```python
_CLAUDE = Harness(
    name="claude",
    binary_names=("claude",),
    default_model="opus",
    prompt_via="stdin",
    forwards_anthropic_key=True,
    build_command=_build_claude_command,  # today's headless.build_command, byte-for-byte
)
```

No behavior change for existing users - `--harness` defaults to `claude`, and
`_build_claude_command` is a rename, not a rewrite, of the function `headless.py` already has.

### `copilot` (GitHub Copilot CLI) - new, with explicit open questions

GitHub Copilot's agentic CLI (`copilot`) is a plausible second backend: it runs locally, can be
scripted non-interactively, and (per its own design) is meant to operate with tool permissions
similar in spirit to Claude Code's. What this document does **not** claim to know with
confidence - and what task 02 below must confirm against `copilot --help` and its own docs
before writing `_build_copilot_command`, the same posture `0001.../03-agentic-marker-research.md`
already took toward pinning `claude`'s exact flags:

- The non-interactive/print-mode flag and exit-code contract (`claude`'s is `-p`).
- How a tool allowlist is expressed (`claude`'s is a trailing `--tools A B C ...`) - GitHub's
  own docs describe per-tool allow/deny controls, but the exact flag syntax and whether
  `Read`/`Grep`/`Glob`/`Edit`/`TodoWrite`-equivalent names exist 1:1 needs verifying, not
  guessing.
- Whether an unattended run needs an equivalent of `--permission-mode bypassPermissions` (the
  `claude` flag exists because Claude Code's permission layer specifically blocks `Edit` on
  `.claude/**` as "sensitive files" even under normal auto-accept modes - `copilot` may or may
  not have the same special-case).
- Whether the prompt is best delivered via stdin (matching `claude`) or a `--prompt`/positional
  argument.
- Model selection: GitHub Copilot now brokers multiple model providers (including Anthropic
  models) behind one subscription: whether `copilot` exposes a `--model` flag, and what value
  would select a capability tier comparable to `claude`'s `opus` alias, is unconfirmed.

**Auth** is a materially different story from `claude`: Copilot CLI authenticates via the
user's GitHub account/token (`gh auth login`, or `GH_TOKEN`/`GITHUB_TOKEN` in CI), not
`ANTHROPIC_API_KEY`. `forwards_anthropic_key=False` for this harness; `resolve_tree_headless`
must not inject an Anthropic key into its `env`, and the "needs the `claude` CLI on PATH, or
ANTHROPIC_API_KEY for the fallback" error message in `cli.py` needs a harness-specific variant
(see "CLI wiring" below).

### `junie` (JetBrains Junie) - new, higher uncertainty flagged explicitly

Junie ships primarily as an agent embedded in JetBrains IDEs. Whether it currently exposes a
supported, documented **non-interactive CLI contract** suitable for unattended use in
`generate`'s pipeline is genuinely unconfirmed as of this document - unlike `claude` (already
integrated and empirically verified in `headless.py`'s own comments) and `copilot` (a CLI
product is confirmed to exist, only its exact flags are unconfirmed). Rather than fabricate
flags for a product surface that may not exist in the form this design assumes, task 03 below
starts with a spike whose explicit possible outcomes are:

1. A headless/CI mode exists and is documented → build `_build_junie_command` following the
   same pattern as `copilot`, with its own confirmed flags.
2. No such mode exists yet → ship `junie` as a registered-but-unavailable harness: `--harness
   junie` is accepted by the CLI (so scripts don't break if JetBrains ships one later), but
   `find_harness` returning `None` produces a clear "Junie has no supported headless CLI mode
   yet" message rather than a generic "not on PATH" one - honest about the gap instead of
   silently pretending support that doesn't exist.

This milestone does not pre-decide which outcome applies; the spike decides it, and the
resulting task 03 acceptance criteria differ accordingly (see below).

## CLI wiring (`cli.py`)

```python
harness: str = typer.Option(
    "claude", "--harness",
    help="which headless CLI runs the marker-research session: claude (default), "
    "copilot, or junie - requires --resolve-markers and that CLI installed/authenticated",
    click_type=click.Choice(harnesses.HARNESS_NAMES),
),
```

- Config-file fallback: `cfg.get("harness", "claude")`, same override-wins semantics every
  other scalar `generate` option already has (not the `--specialization` list exception).
- Rejected outright (mirroring `--seed-roadmap`'s existing check) when passed without
  `--resolve-markers`.
- **The one-shot API fallback (`resolver.resolve_tree`) stays `claude`/Anthropic-only.** It
  calls the Messages API directly - there is no "one-shot Copilot API" or "one-shot Junie API"
  equivalent in this codebase, and inventing one is out of scope here (it would be a fourth,
  unrelated integration, not a headless-harness adapter). So the fallback behavior changes by
  harness:
  - `--harness claude` (default): unchanged today's behavior - `claude` missing falls back to
    `resolver.resolve_tree` with a warning, exactly as now.
  - `--harness copilot` / `--harness junie`: binary missing is a hard failure with an
    actionable, harness-named message (`"copilot CLI not found on PATH - install GitHub
    Copilot CLI, or use --harness claude"` / the `junie`-specific message from outcome 2
    above if that's what the spike finds) - **no silent fallback to a different harness or to
    the Anthropic-only one-shot path**, since silently substituting a different vendor's model
    for the one the user explicitly asked for would be a surprising, unrequested behavior
    change, not a graceful degradation.
- `--update-guidelines` keeps working per-harness: it only changes which extra tool
  (`Write`) is requested and which files are watched, both harness-agnostic already.
- `--dry-run` output gains a `Harness: ...` line (console) / `"harness"` key (JSON), the same
  shape `Specializations: ...` already has.

## Testing strategy

Extends the existing subprocess-boundary pattern
(`tests/test_headless.py`'s `_fake_run_factory`, `run=` injection) per harness rather than
inventing a new one:

- `tests/test_harnesses.py` (new): `find_harness` resolves the right binary name per harness
  from a fake `PATH`; `get("bogus")` raises `KeyError` (or whatever `cli.py` catches);
  `_build_claude_command` output is byte-identical to today's `headless.build_command` (pinning
  the "relocation, not rewrite" claim above); `_build_copilot_command` /
  `_build_junie_command` argv shape once task 02/03 confirm real flags.
- `tests/test_headless.py` additions: `resolve_tree_headless(..., harness="copilot", ...)` with
  a fake `copilot` binary on `PATH` and a scripted `run=` - assert the constructed command uses
  `harnesses.get("copilot").build_command`'s output and that `ANTHROPIC_API_KEY` is absent from
  the subprocess `env` (the `forwards_anthropic_key=False` behavior).
- `tests/test_cli.py` additions: `test_generate_rejects_harness_without_resolve_markers`,
  `test_generate_rejects_unknown_harness`, `test_generate_dry_run_json_includes_harness`,
  `test_generate_harness_binary_missing_fails_hard_no_fallback_for_non_claude`.

No real `copilot` or `junie` binary is ever invoked in the suite, matching how no real `claude`
is invoked today.

## Non-goals

- No auto-detection or "use whichever harness is installed" default - `--harness` stays an
  explicit, single choice, defaulting to `claude` for backward compatibility. Silently picking
  a different vendor's model on the user's behalf is exactly the kind of surprising default
  this repo's own conventions (`--seed-roadmap` requiring explicit opt-in for its own, smaller
  reason) already argue against.
- No attempt to unify `copilot`'s or `junie`'s own tool-permission model into a shared
  cross-harness abstraction beyond the flat `tools: tuple[str, ...]` parameter `build_command`
  already takes - if a backend's permission model turns out to need materially more structure
  (e.g. a generated MCP config file instead of CLI flags), that's follow-up scope for that
  harness's own task, not a redesign of `Harness` itself.
- No one-shot (non-agentic) fallback for `copilot`/`junie` - see "CLI wiring" above.
- `awesome-templates graph` / `dependencies.py` (maintainer-only tooling) are unaffected -
  this milestone touches only the `--resolve-markers` runtime path.

## Tasks

| Task | Name                                              | Category  | Output |
|------|-----------------------------------------------------|-----------|--------|
| 01   | `harnesses.py` + `claude` relocation                | refactor  | New module with `Harness`, `find_harness`, `get`, `_REGISTRY`; `headless.py`'s `find_claude`/`build_command`/`HEADLESS_MODEL` become `_CLAUDE`'s registration, behavior unchanged; `resolve_tree_headless` gains `harness: str = "claude"` |
| 02   | `copilot` adapter                                    | feature   | Spike confirming `copilot`'s non-interactive flag set, tool-allowlist syntax, permission-bypass equivalent, and prompt-delivery mechanism against the installed CLI's own `--help`/docs; `_build_copilot_command` + `_COPILOT` registration once confirmed |
| 03   | `junie` adapter                                      | feature   | Spike confirming whether Junie has a supported non-interactive CLI mode at all; either `_build_junie_command` + `_JUNIE` registration (outcome 1) or a registered-but-unavailable stub with an honest error message (outcome 2) |
| 04   | `cli.py` wiring                                      | feature   | `--harness` flag, config fallback, validation, dry-run output, harness-specific missing-binary messaging, docs (`generate --help`, root `CLAUDE.md`'s Commands section) |
| 05   | Tests                                                | test      | `tests/test_harnesses.py`; `tests/test_headless.py` and `tests/test_cli.py` additions per "Testing strategy" above |

Tasks 02 and 03 are independent of each other and of task 04's flag plumbing beyond needing
task 01's registry to exist first; they can land in either order, or only one of them, without
blocking the other.

## Acceptance criteria

- [ ] `src/awesome_templates/harnesses.py` as designed: `Harness`, `find_harness`, `get`,
      `HARNESS_NAMES`, `_REGISTRY` with all three backends registered (task 03's `junie` entry
      may be the "unavailable, honest error" stub if its spike lands on outcome 2).
- [ ] `headless.py`'s `resolve_tree_headless` accepts `harness: str = "claude"`, looks up the
      `Harness`, and forwards `ANTHROPIC_API_KEY` only when `forwards_anthropic_key` is true.
      Calling it with no `harness` argument (existing call sites) is behavior-identical to today.
- [ ] `cli.py`'s `generate` gains `--harness {claude,copilot,junie}` (default `claude`);
      rejected without `--resolve-markers`; unknown value rejected with the valid-choices list;
      dry-run JSON/console output updated; the `claude`-missing → one-shot-fallback branch is
      reachable only when `harness == "claude"` - `copilot`/`junie` missing fails hard with a
      harness-named, actionable message and no silent fallback.
- [ ] `src/awesome_templates/CLAUDE.md` module map gains a `harnesses.py` entry; `headless.py`'s
      own entry is updated to describe it as consuming a `Harness` rather than being
      `claude`-specific.
- [ ] Root `CLAUDE.md`'s "Commands" section documents `--harness`.
- [ ] `tests/test_harnesses.py` and the `tests/test_headless.py` / `tests/test_cli.py`
      additions listed under "Testing strategy" all pass; `uv run pytest -q` stays green with no
      regression to the 191 tests passing as of this milestone's authoring (2026-08-26).
- [ ] `uv run ruff check src/ tests/` clean.
- [ ] No behavior change for an existing `--resolve-markers` call that doesn't pass `--harness`
      (the default-`claude` path) - covered by task 01's "byte-identical argv" test.

See [status.md](status.md) for progress (all tasks Not started - this milestone has not begun).
