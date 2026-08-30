"""Cross-harness porting: after Claude authors `.claude/{agents,hooks,loops,
skills}` (via `presets.copy_preset` plus, optionally, `headless.py`'s marker
research), this module builds the manifest and prompt for a second, optional
headless session - run by Copilot or Junie, never Claude itself - that
re-authors those four kinds in that harness's own idiom. Deliberately separate
from headless.py: headless.py's contract (marker manifest, per-marker
resolution rules, reconciliation via before/after `markers.scan_tree` diffing)
is specific to *resolving markers in place*; porting neither reads nor edits
markers, and reconciliation isn't meaningful here in the same way (the target
harness's own output location is not something this codebase controls or
knows in advance - see harnesses.Harness.porting_target_hint). What the two
modules share - a headless CLI session driven through `harnesses.py`'s
registry - is exactly the surface `harnesses.Harness` factors out, so both
modules depend on it rather than on each other.

See docs/roadmap/0001-alternative-harness-support/plan.md's "Cross-harness
porting pipeline" section for the design this module implements.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from awesome_templates import harnesses
from awesome_templates.catalog import KINDS, discover
from awesome_templates.harnesses import Harness
from awesome_templates.log_helper import NULL_LOG, LogHelper
from awesome_templates.workspace import Workspace

_TIMEOUT_SECONDS = 3600  # same budget as headless.py's marker-research session

# Read-only inspection of the Claude-authored tree, plus Write for the target
# harness's own new files - no Edit (porting creates new artifacts, it never
# modifies Claude's own .claude/ files) and no Bash/network tools, mirroring
# headless.py's _BASE_TOOLS posture.
PORTING_TOOLS = ("Read", "Grep", "Glob", "Write")


def _rel(path: Path, base: Path) -> str:
    """Same contract as headless._rel_or_abs - path relative to base when it
    sits under base, else absolute. A deliberate separate copy, not a shared
    import (harnesses.py has no path-handling knowledge and port.py must not
    import headless) - keep the two behaviourally identical if either changes."""
    try:
        rel = path.resolve().relative_to(base.resolve())
    except ValueError:
        return str(path.resolve())
    return "." if str(rel) == "." else rel.as_posix()


def render_porting_manifest(out_dir: Path) -> tuple[str, dict[str, int]]:
    """The closed set of Claude-authored entities to port: one row per
    agent/hook/loop/skill found under out_dir's `.claude/` (or out_dir itself,
    if it already points at a `.claude/`-shaped tree - see catalog.discover's
    three-shape resolution). Reuses catalog.py rather than a second directory
    walk, the same way docgen.py reuses its own list_agents/list_skills for
    doc rendering instead of re-deriving the file list.

    :param out_dir: the generated kit root (same directory `--resolve-markers`
        operated on).
    :return: (manifest markdown table, {kind: entity count}) - the counts are
        used for the --dry-run "would port N agent(s), M skill(s), ..." line
        and for `PortSummary.manifest_kinds`.
    """
    catalog = discover(Workspace(root=out_dir))
    entries = catalog.entries.get(".", {kind: {} for kind in KINDS})
    counts = {kind: len(entries.get(kind, {})) for kind in KINDS}

    rows = ["| Kind | Name | Path |", "|------|------|------|"]
    for kind in KINDS:
        for name, path in sorted(entries.get(kind, {}).items()):
            rows.append(f"| `{kind}` | `{name}` | `{_rel(path, out_dir)}` |")
    return "\n".join(rows), counts


_PROMPT_INTRO = """\
You are running non-interactively to port an existing Claude Code kit into
your own native form. `awesome-templates generate --resolve-markers` already
produced and researched a Claude Code kit at the project root below -
`.claude/agents/`, `.claude/skills/`, `.claude/loops/`, and `.claude/hooks/`,
listed in full in the manifest. Your job is NOT to copy these files. It is to
read each one, understand what it does and when it runs, and re-author your
own equivalent using your own conventions for how an agent, skill, loop, or
hook is structured, discovered, and invoked - because you know your own design
better than a Claude-authored template does.
"""

_PROMPT_RULES = """\
## Porting rules

- Preserve intent, not format: what each agent/skill/loop/hook does and when
  it runs must carry over; its file layout, frontmatter shape, and prompt
  structure should not - use whatever shape is idiomatic for you.
- Read the Claude-authored file before porting it. Do not infer behavior from
  its filename alone.
- {target_hint}
- Do not edit, move, or delete anything under `.claude/` - it is the source of
  truth for this session and for any future re-run of this porting step, and
  it may still be read by Claude Code itself. Write only your own new files.
- If something in `.claude/` has no equivalent concept in your own tool (e.g.
  a hook trigger you have no lifecycle event for), say so explicitly in your
  final summary rather than silently dropping it or fabricating a matching
  feature you don't actually have.

The manifest above is the closed set of source files you may read for this
purpose. Do not scan for further Claude configuration beyond it.
"""

_PROMPT_OUTRO = """\
## When you are done

Print a short summary: for each of the four kinds, how many you ported, and
name anything you could not port with a concept mismatch (see the rules
above). This summary is logged for a human; the files you write are the
deliverable.
"""


def build_porting_prompt(
    manifest: str,
    *,
    kit_root: Path,
    harness: Harness,
) -> str:
    """Assemble the whole porting-session prompt. Pure function - unit-tested
    directly, and what a future `--dry-run` could print.

    :param manifest: `render_porting_manifest`'s first return value.
    :param kit_root: the generated tree containing `.claude/` (cwd for the
        session - see port_tree_headless).
    :param harness: the target Harness (`copilot` or `junie`) - never
        `claude`, enforced by cli.py before this is ever called.
    :return: the complete prompt string.
    """
    target_hint = harness.porting_target_hint or (
        "Use whatever location and structure is idiomatic for your own tool - there is no prescribed output path."
    )
    sections = [
        _PROMPT_INTRO,
        f"The Claude-authored kit is at `{_rel(kit_root, kit_root)}` (the current working directory).",
        "## Claude-authored manifest\n\n" + manifest,
        _PROMPT_RULES.format(target_hint=target_hint),
        _PROMPT_OUTRO,
    ]
    return "\n\n".join(section.rstrip() for section in sections) + "\n"


@dataclass
class PortSummary:
    """Result of one porting session - deliberately thin: this codebase has no
    way to verify what the target harness actually wrote (it doesn't know its
    own output convention beyond the porting_target_hint it was given), so this
    is a report of what was ASKED, not what was VERIFIED - unlike
    ResolveSummary, which can verify via the before/after marker scan.

    :ivar harness: the `--port-to` value this session ran for.
    :ivar manifest_kinds: per-kind entity counts handed to the session (from
        `render_porting_manifest`).
    :ivar command_ok: whether the subprocess exited zero. `False` on a non-zero
        exit or a timeout - the caller (`cli.py`) turns that into a warning, not
        a hard failure, the same soft-failure posture `resolve_tree_headless`
        already takes for the marker-research session.
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
    """Run one porting session for `harness` against the Claude-authored tree at
    `out_dir`. Never called for `harness == "claude"` - cli.py enforces that
    `--port-to` requires `--harness claude` for the INITIAL stage, which is the
    opposite constraint (this function's `harness` argument is always the
    *target*, always non-claude).

    :param out_dir: the generated kit root containing the Claude-authored
        `.claude/` tree.
    :param harness: `"copilot"` or `"junie"` - never `"claude"`.
    :param warnings: appended to on a harness-missing or non-zero-exit
        condition, same threading convention as every other warnings-list
        parameter in this codebase.
    :param project_root: cwd for the session; defaults to `out_dir` (unlike
        headless.py's `detect_project_root`, porting only ever reads `.claude/`
        under `out_dir` itself, so there is no separate "project vs. kit root"
        distinction to make here).
    :param run: injected for testing, defaulting to `subprocess.run`.
    :param log: optional `LogHelper`, defaulting to a no-op.
    :return: a `PortSummary`.
    :raises RuntimeError: if `harness`'s binary is not found - cli.py catches
        this the same way it catches the equivalent from
        `headless.resolve_tree_headless`.
    """
    harness_obj = harnesses.get(harness)
    if harness_obj.forwards_anthropic_key:
        # A plain `assert` would be stripped under `python -O`; this invariant
        # is a security boundary (cli.py must never call this for "claude"),
        # not just a logic-error check, so it stays enforced unconditionally.
        raise ValueError(
            f"port_tree_headless must never run for a forwards_anthropic_key=True harness (got {harness!r})"
        )
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
    # forwards_anthropic_key is False for every valid --port-to target (copilot,
    # junie), guaranteed by the assert above - so, unlike resolve_tree_headless,
    # there is no forwarding branch. The key is stripped unconditionally (not
    # merely left unset - the developer may already have it exported), matching
    # headless.py's own "non-forwarding harness must have the key stripped from
    # the inherited env" invariant.
    env = {**os.environ}
    env.pop("ANTHROPIC_API_KEY", None)

    # port_tree_headless is only ever called for prompt_via="arg" harnesses (it
    # never runs for claude), so cmd always embeds the prompt - redact it before
    # logging, same fix headless.py's resolve_tree_headless already needed.
    logged_cmd = [f"<prompt: {len(prompt)} chars>" if part == prompt else part for part in cmd]
    log.debug(f"porting command ({harness}): {' '.join(logged_cmd)}")
    run_kwargs = {"input": prompt} if harness_obj.prompt_via == "stdin" else {"input": None}
    try:
        proc = run(
            cmd,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            **run_kwargs,
        )
    except subprocess.TimeoutExpired:
        message = f"porting session for {harness} timed out after {_TIMEOUT_SECONDS}s"
        warnings.append(message)
        log.warning(message)
        return summary
    except OSError as exc:
        # An oversized argv-embedded prompt (many/large ported entities) can
        # exceed ARG_MAX and raise E2BIG - degrade gracefully like the timeout
        # path rather than crashing the whole generate run.
        message = (
            f"porting session for {harness} failed to start ({exc}) - the prompt may be too large "
            "for this harness's argv limits"
        )
        warnings.append(message)
        log.warning(message)
        return summary

    summary.command_ok = proc.returncode == 0
    if not summary.command_ok:
        tail = (proc.stderr or proc.stdout or "").strip()[-500:]
        message = f"porting session for {harness} exited with code {proc.returncode}" + (f": {tail}" if tail else "")
        warnings.append(message)
        log.warning(message)
    elif proc.stdout:
        log.info(f"porting session summary ({harness}):\n" + proc.stdout.strip()[-2000:])
    return summary
