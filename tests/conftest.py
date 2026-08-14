from __future__ import annotations

import json
from pathlib import Path

import pytest

from awesome_templates.workspace import Workspace

REAL_REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_TEMPLATES_ROOT = REAL_REPO_ROOT / "templates"


@pytest.fixture
def real_workspace() -> Workspace:
    """Points at THIS repo's actual template tree (templates/) - for
    integration tests that need to catch real breakage (e.g. a
    TEMPLATES_ROOT resolution bug)."""
    return Workspace(root=REAL_TEMPLATES_ROOT)


@pytest.fixture
def fixture_workspace(tmp_path: Path) -> Workspace:
    """Two tiny synthetic presets ("demo" and "other"), each a self-contained
    `.claude/` + `docs/` + `scripts/` tree, isolated from the real repo."""
    root = tmp_path / "repo"

    demo = root / "demo"
    (demo / ".claude" / "agents").mkdir(parents=True)
    (demo / ".claude" / "agents" / "widget-verifier.md").write_text(
        "---\nname: widget-verifier\n---\n\nUse this agent for {{PROJECT_NAME}}.\n"
    )
    (demo / ".claude" / "hooks").mkdir(parents=True)
    (demo / ".claude" / "hooks" / "_common.py").write_text("# shared helpers for {{PROJECT_NAME}}\n")
    (demo / ".claude" / "hooks" / "guard.py").write_text("# guard hook\n")
    (demo / ".claude" / "skills" / "adr-write").mkdir(parents=True)
    (demo / ".claude" / "skills" / "adr-write" / "SKILL.md").write_text("# adr-write skill\n")
    (demo / ".claude" / "loops").mkdir(parents=True)

    settings = {
        "permissions": {
            "allow": ["Bash(git status:*)", "Bash(uv run pytest:*)"],
            "deny": [],
        },
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python $CLAUDE_PROJECT_DIR/.claude/hooks/guard.py",
                        }
                    ],
                }
            ],
        },
    }
    (demo / ".claude" / "settings.json").write_text(json.dumps(settings))

    (demo / "docs" / "agent").mkdir(parents=True)
    (demo / "docs" / "agent" / "agents.md").write_text("# Agent Reference\n")
    (demo / "docs" / "agent" / "skills.md").write_text("# Skills Reference\n")
    (demo / "docs" / "agent" / "hooks.md").write_text("# Hooks Reference\n")

    (demo / "docs" / "adr").mkdir(parents=True)
    (demo / "docs" / "adr" / "template.md").write_text(
        "# {{ seq }} - {{ title }}\n\n"
        "> **Status:** {{ status }}\n"
        "> **Date:** {{ date }}\n\n"
        "## Context\n"
    )
    (demo / "docs" / "adr" / "0001-existing.md").write_text("# 0001 - Existing\n")
    (demo / "scripts").mkdir()
    (demo / "scripts" / "check_docs.py").write_text("# {{PROJECT_NAME}} documentation check\n")

    (demo / "specializations" / "widgets" / ".claude" / "agents").mkdir(parents=True)
    (demo / "specializations" / "widgets" / ".claude" / "agents" / "widget-specialist.md").write_text(
        "---\nname: widget-specialist\n---\n\nSpecialist for {{PROJECT_NAME}}.\n"
    )
    (demo / "specializations" / "empty-scaffold" / ".claude" / "agents").mkdir(parents=True)

    other = root / "other"
    (other / ".claude" / "agents").mkdir(parents=True)
    (other / ".claude" / "agents" / "python-expert.md").write_text(
        "---\nname: python-expert\n---\n\n{{PROJECT_PACKAGE}} implementation agent.\n"
    )
    (other / ".claude" / "hooks").mkdir(parents=True)
    (other / ".claude" / "loops").mkdir(parents=True)
    (other / ".claude" / "skills").mkdir(parents=True)
    (other / "docs").mkdir(parents=True)

    return Workspace(root=root)
