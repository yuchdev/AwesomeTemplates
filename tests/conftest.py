from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from awesome_templates.workspace import Workspace

REAL_REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_TEMPLATES_ROOT = REAL_REPO_ROOT / "templates"


@pytest.fixture(autouse=True)
def _which_finds_extensionless_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Windows, `shutil.which` only matches names carrying a `PATHEXT`
    extension, so the extensionless executable stubs the harness tests drop on
    a scoped PATH (they are only ever resolved, never run) are invisible to it.
    Fall back to an exact-name file match on PATH so those tests see the same
    thing they do on POSIX. A no-op elsewhere."""
    if sys.platform != "win32":
        return
    real_which = shutil.which

    def which(cmd, mode=os.F_OK | os.X_OK, path=None):
        found = real_which(cmd, mode, path)
        if found or os.path.splitext(cmd)[1]:
            return found
        for directory in (path if path is not None else os.environ.get("PATH", "")).split(os.pathsep):
            candidate = os.path.join(directory, cmd)
            if directory and os.path.isfile(candidate):
                return candidate
        return None

    monkeypatch.setattr(shutil, "which", which)


@pytest.fixture(autouse=True)
def _isolated_models_state(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the CLI's per-user `models.json` at an empty temp path for every test, so no test reads or
    writes the real `~/.local/state/awesome/` (a missing file falls back to the packaged template)."""
    import awesome_templates.cli as cli_module

    monkeypatch.setattr(cli_module, "MODELS_STATE_PATH", tmp_path_factory.mktemp("state") / "awesome" / "models.json")


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


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("live models")
    group.addoption(
        "--live-models",
        action="store_true",
        default=False,
        help="run tests that call vendor Models APIs (needs API keys and network; off by default)",
    )
    group.addoption(
        "--live-models-strict",
        action="store_true",
        default=False,
        help="with --live-models, a vendor whose API key env var is unset fails instead of skipping",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep the default run offline: `live_models` tests are skipped unless explicitly requested."""
    if config.getoption("--live-models") or os.environ.get("RUN_LIVE_MODELS") == "1":
        return
    skip = pytest.mark.skip(reason="live vendor check; opt in with --live-models (or RUN_LIVE_MODELS=1)")
    for item in items:
        if "live_models" in item.keywords:
            item.add_marker(skip)
