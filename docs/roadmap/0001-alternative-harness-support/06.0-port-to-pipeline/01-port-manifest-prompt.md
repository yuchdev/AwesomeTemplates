# 01 - `port.py`: manifest + prompt builder

**Parent task:** 06.0 `--port-to` pipeline orchestration
**State:** ⬜ Not started
**Depends on:** task 01.0 (`harnesses.py` exists, though this subtask itself
only needs `catalog.py`/`workspace.py`)
**Blocks:** 02 (this task); tasks 07.0, 08.0 (their `porting_target_hint`
values are consumed by this subtask's prompt builder)

## Objective

Create `src/awesome_templates/port.py`'s pure, harness-agnostic half: a
manifest builder that enumerates the four Claude-authored kinds
(`agents`/`hooks`/`loops`/`skills`) already on disk under the generated tree,
and a prompt builder that turns that manifest into the session instructions
handed to whichever harness `--port-to` names. No subprocess code yet - that
is subtask 02.

## File: `src/awesome_templates/port.py` (new)

```python
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

from pathlib import Path

from awesome_templates.catalog import KINDS, discover
from awesome_templates.harnesses import Harness
from awesome_templates.workspace import Workspace

# Read-only inspection of the Claude-authored tree, plus Write for the target
# harness's own new files - no Edit (porting creates new artifacts, it never
# modifies Claude's own .claude/ files) and no Bash/network tools, mirroring
# headless.py's _BASE_TOOLS posture.
PORTING_TOOLS = ("Read", "Grep", "Glob", "Write")


def _rel(path: Path, base: Path) -> str:
    """Same contract as headless._rel_or_abs - path relative to base when it
    sits under base, else absolute."""
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
        "Use whatever location and structure is idiomatic for your own tool - "
        "there is no prescribed output path."
    )
    sections = [
        _PROMPT_INTRO,
        f"The Claude-authored kit is at `{_rel(kit_root, kit_root)}` "
        "(the current working directory).",
        "## Claude-authored manifest\n\n" + manifest,
        _PROMPT_RULES.format(target_hint=target_hint),
        _PROMPT_OUTRO,
    ]
    return "\n\n".join(section.rstrip() for section in sections) + "\n"
```

## Implementation notes

- `render_porting_manifest` deliberately returns raw `(kind, name, path)`
  rows, not `docgen.py`'s richer `AgentInfo`/`SkillInfo`/`HookInfo`
  (name+description+extra) - those are tailored to rendering human-facing
  reference docs and don't cover `loops` at all (`docgen.py` has no
  `list_loops`). `catalog.discover` is the right shared primitive here since
  it already handles all four kinds generically and is the one used by
  `awesome-templates graph`/`list` for the same "what entities exist"
  question.
- `PORTING_TOOLS` is `Write`, not `Edit` - porting produces new files in the
  target harness's own convention; it never edits the Claude-authored files
  it reads.
- `harness.porting_target_hint` is `None` until tasks 07.0/08.0 land (task
  01.0 subtask 01 gives it a `None` default) - the prompt degrades gracefully
  to a generic instruction in that case, so this subtask is fully usable and
  testable before 07.0/08.0 confirm anything harness-specific.

## Constraints

- Pure functions only - no subprocess, no I/O beyond `discover`'s existing
  filesystem read.
- `from __future__ import annotations`; `Optional[T]`, never `T | None`
  (`build_porting_prompt` doesn't need `Optional` itself, but keep the
  convention in mind for subtask 02's additions to this file).
- `port.py` must not import `headless` - the dependency runs through
  `harnesses.py` only, per this task's module docstring.

## Success criteria

- [ ] `render_porting_manifest(out_dir)` returns one row per real agent/hook/
      loop/skill entity under `out_dir`'s `.claude/` tree, with correct
      per-kind counts.
- [ ] `render_porting_manifest` on a tree with no `.claude/` at all returns an
      empty manifest and all-zero counts, without raising.
- [ ] `build_porting_prompt` embeds the manifest verbatim and the harness's
      `porting_target_hint` when set, or a generic fallback sentence when not.
- [ ] `ruff check src/` clean.
