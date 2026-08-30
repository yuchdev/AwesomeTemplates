# 02 - Relocate `claude`'s adapter out of `headless.py`

**Parent task:** 01.0 `harnesses.py` + `claude` relocation
**State:** ⬜ Not started
**Depends on:** 01
**Blocks:** 03 (this task); tasks
[02.0](/docs/roadmap/0001-alternative-harness-support/02.0-copilot-adapter/README.md),
[03.0](/docs/roadmap/0001-alternative-harness-support/03.0-junie-adapter/README.md)
(register beside `_CLAUDE` in the same module),
[04.0](/docs/roadmap/0001-alternative-harness-support/04.0-cli-wiring/README.md)
(CLI wiring calls `harnesses.find_harness`/`get`, not `headless.find_claude`),
[06.0](/docs/roadmap/0001-alternative-harness-support/06.0-port-to-pipeline/README.md)
(`port.py` reuses the same `Harness.build_command` contract)

## Objective

Move [`headless.py`](/src/awesome_templates/headless.py)'s `find_claude()`
(lines 91-95), `build_command()` (lines 290-329), and `HEADLESS_MODEL` (line
52) into `harnesses.py` as `_CLAUDE`'s registration - `_build_claude_command`,
byte-identical in the argv it produces for the `stdin` prompt path. Update
`headless.py`'s one internal call site (`resolve_tree_headless`) and `cli.py`'s
one call site (`headless.find_claude()` in the `generate` command body) to go
through the registry instead.

## File: `src/awesome_templates/harnesses.py` (additions)

```python
def _build_claude_command(
    claude_bin: str,
    *,
    tools: tuple[str, ...],
    model: str,
    prompt: Optional[str] = None,
) -> list[str]:
    """The headless argv for `claude`. `prompt` is accepted for signature
    parity with `Harness.build_command` but unused - claude's prompt travels
    over stdin (`prompt_via="stdin"`), not argv. See `_CLAUDE.prompt_via`.

    `--setting-sources user` keeps the user's own settings (and their normal
    login - OAuth or ANTHROPIC_API_KEY) while skipping project/local settings:
    with the documented `generate .` usage the generated kit's own
    settings.json sits at the session cwd and its wired hooks would otherwise
    fire on - and could block - every edit the session makes. `--tools` is a
    variadic flag, so it goes last, where the argv ends before anything could
    be swallowed into its value list.

    `--permission-mode bypassPermissions` is required, not a convenience:
    Claude Code's permission layer treats `.claude/**` files as sensitive and
    blocks Edit on them even under acceptEdits and even with an explicit
    `--allowedTools "Edit(<kit>/**)"` rule (verified empirically) - and the
    kit's agent/loop files, the very thing the marker-research session exists
    to edit, all live under `.claude/`. The security boundary is therefore the
    tool allowlist (no Bash, no network tools) plus the caller's closed file
    set named in the prompt, not per-path permission checks.
    """
    return [
        claude_bin,
        "-p",
        "--output-format",
        "text",
        "--setting-sources",
        "user",
        "--permission-mode",
        "bypassPermissions",
        "--no-session-persistence",
        "--model",
        model,
        "--tools",
        *tools,
    ]


_CLAUDE = Harness(
    name="claude",
    binary_names=("claude",),
    default_model="opus",
    prompt_via="stdin",
    forwards_anthropic_key=True,
    build_command=_build_claude_command,
)

_REGISTRY: dict[str, Harness] = {"claude": _CLAUDE}
```

## Changes to `src/awesome_templates/headless.py`

- Delete `find_claude()` (lines 91-95), `build_command()` (lines 290-329), and
  the `HEADLESS_MODEL` constant (line 52); add
  `from awesome_templates import harnesses` and use
  `harnesses.get("claude").default_model` wherever `HEADLESS_MODEL` was the
  default. Keep `HEADLESS_MODEL` re-exported as
  `HEADLESS_MODEL = harnesses.get("claude").default_model` only if anything
  outside this module imports it directly today (`grep -rn HEADLESS_MODEL
  tests/ src/` first - if nothing outside `headless.py` imports it, drop it
  outright rather than keeping a redundant alias).
- `resolve_tree_headless`'s signature gains `harness: str = "claude"`:

  ```python
  def resolve_tree_headless(
      out_dir: Path,
      *,
      api_key: Optional[str],
      warnings: list[str],
      harness: str = "claude",
      claude_bin: Optional[str] = None,
      project_root: Optional[Path] = None,
      update_guidelines: bool = False,
      model: Optional[str] = None,
      run=subprocess.run,
      log: LogHelper = NULL_LOG,
  ) -> tuple[ResolveSummary, list[str]]:
      ...
  ```

  Body changes:
  - `harness_obj = harnesses.get(harness)`.
  - `resolved_model = model or harness_obj.default_model` (today's `model:
    str = HEADLESS_MODEL` default becomes `Optional[str] = None`, resolved
    per-harness - `claude`'s effective default is unchanged).
  - `claude_bin = claude_bin or harnesses.find_harness(harness_obj)` replaces
    `claude_bin = claude_bin or find_claude()`. The parameter name
    `claude_bin` stays for this milestone's task 01.0 (it is still the only
    registered harness); tasks 02.0/03.0/04.0 do not need to rename it since
    callers pass the resolved binary path positionally into the same slot -
    a rename to `harness_bin` is cosmetic and out of scope here.
  - `tools = _BASE_TOOLS + (("Write",) if update_guidelines else ())` (moved
    out of the old `build_command`, computed here instead, since tool
    selection depends on `update_guidelines`, a marker-research concept
    `harnesses.py` has no business knowing about).
  - `cmd = harness_obj.build_command(claude_bin, tools=tools,
    model=resolved_model, prompt=prompt)`.
  - The subprocess-invocation branch on `harness_obj.prompt_via`:

    ```python
    if harness_obj.prompt_via == "stdin":
        run_kwargs = {"input": prompt}
    else:
        run_kwargs = {"input": None}  # prompt is already embedded in cmd
    proc = run(cmd, cwd=str(project_root), env=env, capture_output=True,
               text=True, timeout=_TIMEOUT_SECONDS, **run_kwargs)
    ```

  - `env` gains `ANTHROPIC_API_KEY` only `if api_key and
    harness_obj.forwards_anthropic_key` (today's unconditional `if api_key`
    check gains the second clause; for `harness="claude"` this is a no-op
    since `forwards_anthropic_key=True`).
  - The `claude_bin is None` error message becomes harness-named:
    `f"the `{harness}` CLI is not on PATH"` instead of the hardcoded
    `"the `claude` CLI is not on PATH"`.

## Changes to `src/awesome_templates/cli.py`

The `generate` command's `resolve_value` branch currently reads:

```python
from awesome_templates import headless, resolver

api_key = resolver.load_api_key(Path.cwd())
claude_bin = headless.find_claude()

if claude_bin:
    ...
```

Replace the second line with:

```python
from awesome_templates import harnesses, headless, resolver

api_key = resolver.load_api_key(Path.cwd())
claude_bin = harnesses.find_harness(harnesses.get("claude"))
```

No other change here yet - task 04.0 replaces this whole block with the
harness-parameterized version once `--harness` exists.

## Constraints

- `_build_claude_command`'s returned argv for `tools=("Read","Grep","Glob",
  "Edit","TodoWrite")`, `model="opus"` must be byte-identical, element for
  element, to today's `headless.build_command(claude_bin,
  update_guidelines=False)` output - this is the "relocation, not rewrite"
  claim the milestone's [plan.md](/docs/roadmap/0001-alternative-harness-support/plan.md) rests on.
- `from __future__ import annotations`; `Optional[T]`, never `T | None`.
- No new `# type: ignore`.

## Success criteria

- [ ] `_build_claude_command(bin, tools=("Read","Grep","Glob","Edit",
      "TodoWrite"), model="opus")` output equals today's
      `headless.build_command(bin, update_guidelines=False)` output exactly.
- [ ] `_build_claude_command(bin, tools=(...,"Write"), model="opus")` equals
      today's `build_command(bin, update_guidelines=True)` output exactly.
- [ ] `headless.find_claude` and `headless.build_command` no longer exist;
      every caller goes through `harnesses`.
- [ ] `resolve_tree_headless(out_dir, api_key=None, warnings=[])` (no
      `harness` argument) behaves identically to today - existing
      `tests/test_headless.py` calls with no `harness=` kwarg pass unmodified.
- [ ] `cli.py`'s `generate` command still resolves and runs the `claude`
      session exactly as before this change (manual smoke: `uv run
      awesome-templates generate . --preset python --name x --resolve-markers
      --dry-run`).
- [ ] `ruff check src/` clean.
