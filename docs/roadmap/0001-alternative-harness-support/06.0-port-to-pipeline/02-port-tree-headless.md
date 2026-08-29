# 02 - `port.py`: `port_tree_headless` orchestrator

**Parent task:** 06.0 `--port-to` pipeline orchestration
**State:** ⬜ Not started
**Depends on:** 01 (this task), task 01.0 (`harnesses.get`/`find_harness`)
**Blocks:** task 04.0's missing-binary message pattern is reused here; task
09.0 (tests exercise this function directly)

## Objective

Add `port_tree_headless` to `src/awesome_templates/port.py`: the subprocess-
boundary function that finds the target harness's binary, builds its command
via `harnesses.Harness.build_command`, runs it, and returns a minimal summary.
Mirrors `headless.resolve_tree_headless`'s shape (`run=` injection, harness
env gating) without inheriting its marker-specific reconciliation, since
porting has no equivalent of "diff the before/after marker count" - the
target harness's own output location is not something this codebase controls
(see `Harness.porting_target_hint`'s docstring in task 01.0 subtask 01).

## File: `src/awesome_templates/port.py` (additions)

```python
import os
import subprocess
from dataclasses import dataclass, field

from awesome_templates import harnesses
from awesome_templates.log_helper import NULL_LOG, LogHelper

_TIMEOUT_SECONDS = 3600  # same budget as headless.py's marker-research session


@dataclass
class PortSummary:
    """Result of one porting session - deliberately thin: this codebase has
    no way to verify what the target harness actually wrote (it doesn't know
    its own output convention beyond the porting_target_hint it was given),
    so this is a report of what was ASKED, not what was VERIFIED - unlike
    ResolveSummary, which can verify via the before/after marker scan.

    :ivar harness: the `--port-to` value this session ran for.
    :ivar manifest_kinds: per-kind entity counts handed to the session (from
        `render_porting_manifest`).
    :ivar command_ok: whether the subprocess exited zero. `False` on a
        non-zero exit or a timeout - the caller (`cli.py`) turns that into a
        warning, not a hard failure, the same soft-failure posture
        `resolve_tree_headless` already takes for the marker-research session.
    """

    harness: str
    manifest_kinds: dict[str, int] = field(default_factory=dict)
    command_ok: bool = False


def port_tree_headless(
    out_dir: Path,
    *,
    harness: str,
    warnings: list[str],
    project_root: Optional[Path] = None,
    run=subprocess.run,
    log: LogHelper = NULL_LOG,
) -> PortSummary:
    """Run one porting session for `harness` against the Claude-authored tree
    at `out_dir`. Never called for `harness == "claude"` - cli.py enforces
    that `--port-to` requires `--harness claude` for the INITIAL stage, which
    is the opposite constraint (this function's `harness` argument is always
    the *target*, always non-claude).

    :param out_dir: the generated kit root containing the Claude-authored
        `.claude/` tree.
    :param harness: `"copilot"` or `"junie"` - never `"claude"`.
    :param warnings: appended to on a harness-missing or non-zero-exit
        condition, same threading convention as every other warnings-list
        parameter in this codebase.
    :param project_root: cwd for the session; defaults to `out_dir` (unlike
        headless.py's `detect_project_root`, porting only ever reads
        `.claude/` under `out_dir` itself, so there is no separate
        "project vs. kit root" distinction to make here).
    :param run: injected for testing, defaulting to `subprocess.run`.
    :param log: optional `LogHelper`, defaulting to a no-op.
    :return: a `PortSummary`.
    :raises RuntimeError: if `harness`'s binary is not found - cli.py catches
        this the same way it catches the equivalent from
        `headless.resolve_tree_headless`.
    """
    harness_obj = harnesses.get(harness)
    manifest, counts = render_porting_manifest(out_dir)
    summary = PortSummary(harness=harness, manifest_kinds=counts)
    if not any(counts.values()):
        log.info(f"no agents/hooks/loops/skills found under {out_dir} - nothing to port")
        return summary

    binary = harnesses.find_harness(harness_obj)
    if binary is None:
        raise RuntimeError(f"the `{harness}` CLI is not on PATH")

    root = (project_root or out_dir).resolve()
    prompt = build_porting_prompt(manifest, kit_root=root, harness=harness_obj)
    cmd = harness_obj.build_command(
        binary,
        tools=PORTING_TOOLS,
        model=harness_obj.default_model,
        prompt=prompt,
    )
    env = {**os.environ, "ANTHROPIC_API_KEY": ...} if False else {**os.environ}
    # forwards_anthropic_key is False for every valid --port-to target
    # (copilot, junie) - no branch needed here, unlike resolve_tree_headless,
    # since this function is never invoked with harness="claude".

    log.debug(f"porting command ({harness}): {' '.join(cmd)}")
    run_kwargs = {"input": prompt} if harness_obj.prompt_via == "stdin" else {"input": None}
    try:
        proc = run(cmd, cwd=str(root), env=env, capture_output=True, text=True,
                   timeout=_TIMEOUT_SECONDS, **run_kwargs)
    except subprocess.TimeoutExpired:
        message = f"porting session for {harness} timed out after {_TIMEOUT_SECONDS}s"
        warnings.append(message)
        log.warning(message)
        return summary

    summary.command_ok = proc.returncode == 0
    if not summary.command_ok:
        tail = (proc.stderr or proc.stdout or "").strip()[-500:]
        message = f"porting session for {harness} exited with code {proc.returncode}" + (
            f": {tail}" if tail else ""
        )
        warnings.append(message)
        log.warning(message)
    elif proc.stdout:
        log.info(f"porting session summary ({harness}):\n" + proc.stdout.strip()[-2000:])
    return summary
```

## Implementation notes

- The `env = {**os.environ, "ANTHROPIC_API_KEY": ...} if False else
  {**os.environ}` line is written deliberately verbose above to make the "this
  is never conditional here" invariant visible in the diff - simplify to plain
  `env = {**os.environ}` in the actual implementation; the point is that no
  `ANTHROPIC_API_KEY` branch exists in this function at all, unlike
  `resolve_tree_headless`, because `harness` is always a `forwards_anthropic_key
  =False` target by construction (cli.py never calls this with `"claude"`).
  If a review prefers an explicit assertion over relying on the caller's
  discipline, add `assert not harness_obj.forwards_anthropic_key` at the top
  instead of a dead conditional.
- No reconciliation/scan-diff step exists here (contrast with
  `resolve_tree_headless`'s before/after `markers.scan_tree` diff) - this
  codebase has no way to know where Copilot/Junie wrote their output, so
  `command_ok` (exit code only) is the full extent of what can be verified
  without a harness-specific convention. Tasks 07.0/08.0 may extend
  `PortSummary` with a verified file count IF their spike finds a confirmed,
  fixed output location worth checking - not required by this subtask.
- `render_porting_manifest`/`build_porting_prompt`/`PORTING_TOOLS` are the
  subtask 01 names this subtask imports from within the same module - no
  cross-module import needed since they're both in `port.py`.

## Constraints

- Never invoked with `harness="claude"` - if a caller does so by mistake,
  `harnesses.get("claude").forwards_anthropic_key` is `True`, which would
  silently forward the key if the dead-conditional shortcut above were ever
  un-commented incorrectly; prefer the explicit `assert` guard mentioned above
  to make this a loud failure instead of a silent one.
- Same soft-failure posture as `resolve_tree_headless`: a timeout or non-zero
  exit is a warning, not a raised exception - the caller (cli.py) keeps
  exit 0 for the overall `generate` command unless it chooses otherwise.

## Success criteria

- [ ] `port_tree_headless` with an empty manifest (no `.claude/` entities)
      returns immediately with `command_ok=False`, `manifest_kinds` all zero,
      and never calls `run`.
- [ ] `port_tree_headless` with `harness` binary missing raises `RuntimeError`
      naming that harness.
- [ ] A scripted `run=` returning a non-zero exit code produces a warning
      containing the harness name and the process's stderr tail, and
      `command_ok=False`, without raising.
- [ ] The constructed `env` never contains `ANTHROPIC_API_KEY` for any valid
      `--port-to` target.
- [ ] `ruff check src/` clean.
