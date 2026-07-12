from __future__ import annotations

import json
from pathlib import Path

import pytest

from awesome_claude.workspace import Workspace

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
    """A tiny synthetic core/python/... tree, isolated from the real repo."""
    root = tmp_path / "repo"

    (root / "core" / "agents").mkdir(parents=True)
    (root / "core" / "agents" / "widget-verifier.md").write_text(
        "---\nname: widget-verifier\n---\n\nUse this agent for {{PROJECT_NAME}}.\n"
    )
    (root / "core" / "hooks").mkdir(parents=True)
    (root / "core" / "hooks" / "_common.py").write_text("# shared helpers for {{PROJECT_NAME}}\n")
    (root / "core" / "hooks" / "guard.py").write_text("# guard hook\n")
    (root / "core" / "skills" / "adr-write").mkdir(parents=True)
    (root / "core" / "skills" / "adr-write" / "SKILL.md").write_text("# adr-write skill\n")
    (root / "core" / "loops").mkdir(parents=True)

    (root / "python" / "agents").mkdir(parents=True)
    (root / "python" / "agents" / "python-expert.md").write_text(
        "---\nname: python-expert\n---\n\n{{PROJECT_PACKAGE}} implementation agent.\n"
    )
    (root / "python" / "hooks").mkdir(parents=True)
    (root / "python" / "hooks" / "_common.py").write_text("# shared helpers (python copy)\n")
    (root / "python" / "loops").mkdir(parents=True)
    (root / "python" / "skills").mkdir(parents=True)

    for cat in ("helpers", "java", "orchestrators"):
        for kind in ("agents", "hooks", "loops", "skills"):
            (root / cat / kind).mkdir(parents=True)

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
    (root / "core" / "settings.json").write_text(json.dumps(settings))

    (root / "docs" / "adr").mkdir(parents=True)
    (root / "docs" / "adr" / "template.md").write_text(
        "# {{ seq }} - {{ title }}\n\n"
        "> **Status:** {{ status }}\n"
        "> **Date:** {{ date }}\n\n"
        "## Context\n"
    )
    (root / "docs" / "adr" / "0001-existing.md").write_text("# 0001 - Existing\n")

    return Workspace(root=root)
