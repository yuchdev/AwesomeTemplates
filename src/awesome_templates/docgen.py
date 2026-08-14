"""Deterministic "what actually shipped" doc generation - no network, no AI.

Every agent/skill already carries a name and description in its YAML
frontmatter, and every hook's trigger is already spelled out in
`.claude/settings.json`; turning that into `docs/agent/{agents,skills,hooks}.md`
is a glob and a render, not a research task. Runs on every `generate`,
unconditionally, right after `copy_preset` writes the tree. The genuinely
AI-authored docs (tutorial, roadmap seed, test-convention paragraph) live in
resolver.py instead, gated behind `--resolve-markers`, because those synthesize
content no file states outright.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from awesome_templates.log_helper import NULL_LOG, LogHelper

_FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)

# The command a hook is wired under always ends in `.../hooks/<stem>.py`
# regardless of which of the two presets it's in - see settings.json in either.
_HOOK_COMMAND_RE = re.compile(r"hooks/(?P<stem>[\w-]+)\.py")

# module docstring's first sentence/line, e.g. '"""PreToolUse / Bash guard.\n\n...'
_DOCSTRING_RE = re.compile(r'"""(?P<body>.*?)(?:\n\n|""")', re.DOTALL)

_DEFAULT_HEADINGS = {
    "agents.md": "# Agent Reference",
    "skills.md": "# Skills Reference",
    "hooks.md": "# Hooks Reference",
}

_TEST_LAYOUT_HEADING = "## Actual Test Layout"
TEST_COVERAGE_DOC = ("docs", "test", "code_test_coverage.md")


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Hand-rolled, not full YAML: every frontmatter block in templates/ is
    flat `key: value` lines (see any agents/*.md or skills/*/SKILL.md).
    Adding a pyyaml dependency for that is the same call resolver.py already
    made for .env parsing - one variable's worth of syntax doesn't need a
    library."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group("body").splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def _docstring_first_line(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = _DOCSTRING_RE.search(text)
    if not m:
        return ""
    body = m.group("body").strip()
    return body.splitlines()[0].strip() if body else ""


@dataclass(frozen=True)
class AgentInfo:
    name: str
    description: str
    model: str


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    invocation: str


@dataclass(frozen=True)
class HookInfo:
    name: str
    description: str
    trigger: str  # e.g. "PreToolUse: Bash" - derived from settings.json, or "(unwired)"


def list_agents(project_dir: Path) -> list[AgentInfo]:
    agents_dir = project_dir / ".claude" / "agents"
    if not agents_dir.is_dir():
        return []
    agents = []
    for path in sorted(agents_dir.glob("*.md")):
        fm = _parse_frontmatter(path.read_text(encoding="utf-8"))
        agents.append(
            AgentInfo(
                name=fm.get("name", path.stem),
                description=fm.get("description", ""),
                model=fm.get("model", ""),
            )
        )
    return agents


def list_skills(project_dir: Path) -> list[SkillInfo]:
    skills_dir = project_dir / ".claude" / "skills"
    if not skills_dir.is_dir():
        return []
    skills = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        fm = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        skills.append(
            SkillInfo(
                name=fm.get("name", skill_md.parent.name),
                description=fm.get("description", ""),
                invocation=fm.get("invocation", ""),
            )
        )
    return skills


def _hook_triggers(settings_path: Path) -> dict[str, list[str]]:
    if not settings_path.is_file():
        return {}
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    triggers: dict[str, list[str]] = {}
    for event, groups in settings.get("hooks", {}).items():
        for group in groups:
            matcher = group.get("matcher")
            label = f"{event}: {matcher}" if matcher else event
            for hook in group.get("hooks", []):
                m = _HOOK_COMMAND_RE.search(hook.get("command", ""))
                if m:
                    triggers.setdefault(m.group("stem"), []).append(label)
    return triggers


def list_hooks(project_dir: Path) -> list[HookInfo]:
    hooks_dir = project_dir / ".claude" / "hooks"
    if not hooks_dir.is_dir():
        return []
    triggers = _hook_triggers(project_dir / ".claude" / "settings.json")

    hooks = []
    for path in sorted(hooks_dir.glob("*.py")):
        # A leading underscore marks a shared helper module (e.g. _common.py),
        # never a hook wired directly in settings.json - it would never appear
        # as a `hooks/<stem>.py` command, so flagging it "(unwired)" would be
        # noise, not a real finding.
        if path.stem.startswith("_"):
            continue
        labels = triggers.get(path.stem)
        hooks.append(
            HookInfo(
                name=path.stem,
                description=_docstring_first_line(path),
                trigger="; ".join(labels) if labels else "(unwired)",
            )
        )
    return hooks


def list_files_under(base: Path, root: Path) -> list[str]:
    """Every file under `base` (if it exists), as sorted POSIX paths relative
    to `root`. Shared by list_test_files below and resolver.gather_context's
    source-tree section - both need the exact same "walk a subtree, list its
    files" logic, so it lives once here rather than being duplicated."""
    if not base.is_dir():
        return []
    return sorted(str(p.relative_to(root).as_posix()) for p in base.rglob("*") if p.is_file())


def list_test_files(project_dir: Path) -> list[str]:
    return list_files_under(project_dir / "tests", project_dir)


def render_test_layout_section(files: list[str]) -> str:
    if not files:
        return f"{_TEST_LAYOUT_HEADING}\n\nNo test files were found under `tests/`.\n"
    lines = [_TEST_LAYOUT_HEADING, "", "```"]
    lines.extend(files)
    lines.append("```")
    return "\n".join(lines) + "\n"


def write_test_layout_doc(
    project_dir: Path, warnings: list[str], log: LogHelper = NULL_LOG
) -> None:
    """Append (or refresh) an '## Actual Test Layout' section at the end of
    docs/test/code_test_coverage.md, listing this project's real test files.
    Idempotent by construction: re-running replaces everything from that
    heading onward rather than appending a second copy, so `generate --force`
    stays drift-free the same way write_agent_docs is."""
    path = project_dir.joinpath(*TEST_COVERAGE_DOC)
    if not path.is_file():
        message = f"{path} does not exist - skipped test-layout generation for it"
        warnings.append(message)
        log.warning(message)
        return
    log.info(f"writing Actual Test Layout section to {path}")
    text = path.read_text(encoding="utf-8")
    heading_at = text.find(_TEST_LAYOUT_HEADING)
    kept = text[:heading_at] if heading_at != -1 else text
    section = render_test_layout_section(list_test_files(project_dir))
    path.write_text(kept.rstrip() + "\n\n" + section, encoding="utf-8")


def render_agents_doc(agents: list[AgentInfo]) -> str:
    lines = [_DEFAULT_HEADINGS["agents.md"], ""]
    if not agents:
        lines.append("No agents are currently defined.")
    else:
        lines.append("| Agent | Model | Description |")
        lines.append("|-------|-------|-------------|")
        for a in agents:
            lines.append(f"| `{a.name}` | {a.model or '-'} | {a.description or '-'} |")
    return "\n".join(lines) + "\n"


def render_skills_doc(skills: list[SkillInfo]) -> str:
    lines = [_DEFAULT_HEADINGS["skills.md"], ""]
    if not skills:
        lines.append("No skills are currently defined.")
    else:
        lines.append("| Skill | Invocation | Description |")
        lines.append("|-------|------------|-------------|")
        for s in skills:
            lines.append(f"| `{s.name}` | {s.invocation or '-'} | {s.description or '-'} |")
    return "\n".join(lines) + "\n"


def render_hooks_doc(hooks: list[HookInfo]) -> str:
    lines = [_DEFAULT_HEADINGS["hooks.md"], ""]
    if not hooks:
        lines.append("No hooks are currently defined.")
    else:
        lines.append("| Hook | Trigger | Description |")
        lines.append("|------|---------|-------------|")
        for h in hooks:
            lines.append(f"| `{h.name}` | {h.trigger} | {h.description or '-'} |")
    return "\n".join(lines) + "\n"


def _write_preserving_heading(
    path: Path, rendered: str, warnings: list[str], log: LogHelper = NULL_LOG
) -> None:
    if not path.is_file():
        message = f"{path} does not exist - skipped agent-doc generation for it"
        warnings.append(message)
        log.warning(message)
        return
    log.info(f"writing {path}")
    lines = rendered.splitlines()
    existing_first_line = path.read_text(encoding="utf-8").splitlines()[:1]
    if existing_first_line and existing_first_line[0].startswith("# ") and lines:
        lines[0] = existing_first_line[0]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_agent_docs(
    project_dir: Path, warnings: list[str], log: LogHelper = NULL_LOG
) -> None:
    """Regenerate docs/agent/{agents,skills,hooks}.md from what's actually on
    disk in project_dir/.claude/. Idempotent by construction: a pure function
    of the current tree, so running it again (e.g. on `generate --force`)
    just re-derives the same three files, no drift. A pre-existing custom `#
    ...` heading in any of the three files is preserved; only the body below
    it is replaced."""
    agent_docs_dir = project_dir / "docs" / "agent"
    _write_preserving_heading(
        agent_docs_dir / "agents.md", render_agents_doc(list_agents(project_dir)), warnings, log=log
    )
    _write_preserving_heading(
        agent_docs_dir / "skills.md", render_skills_doc(list_skills(project_dir)), warnings, log=log
    )
    _write_preserving_heading(
        agent_docs_dir / "hooks.md", render_hooks_doc(list_hooks(project_dir)), warnings, log=log
    )
