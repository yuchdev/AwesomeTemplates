"""Tests that exercise the package against THIS repo's real template tree.

These exist because round 2's REPO_ROOT-resolution bug (an off-by-one
`.parent` after `generate.py` moved) was only caught by manual smoke testing.
A synthetic-fixture unit test can't catch "the real repo layout doesn't
match what the code assumes" - only running against the real tree can.
"""

from __future__ import annotations

from pathlib import Path

from awesome_claude.catalog import discover

REAL_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_templates_root_is_separate_from_the_package_root(real_workspace):
    # templates/ holds the generated-kit source material; pyproject.toml and
    # src/ are this package's own files and must NOT live under templates/.
    assert real_workspace.root == REAL_REPO_ROOT / "templates"
    assert (REAL_REPO_ROOT / "pyproject.toml").is_file()
    assert not (real_workspace.root / "pyproject.toml").exists()


def test_workspace_root_resolves_to_the_actual_templates_tree(real_workspace):
    assert (real_workspace.root / "core").is_dir()
    assert (real_workspace.root / "docs" / "adr" / "template.md").is_file()


def test_discover_against_real_repo_finds_expected_entities(real_workspace):
    catalog = discover(real_workspace)
    assert "python-expert" in catalog.names("python", "agents")
    assert "subtask-verifier" in catalog.names("core", "agents")
    assert "post-mortem" not in catalog.names("core", "skills")  # deleted in round 2
