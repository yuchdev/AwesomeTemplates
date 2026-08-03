"""Tests that exercise the package against THIS repo's real template tree.

These exist because round 2's REPO_ROOT-resolution bug (an off-by-one
`.parent` after `generate.py` moved) was only caught by manual smoke testing.
A synthetic-fixture unit test can't catch "the real repo layout doesn't
match what the code assumes" - only running against the real tree can.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from awesome_claude.catalog import discover, list_presets
from awesome_claude.cli import app
from awesome_claude.dependencies import build_dependency_graph
from awesome_claude.templating import PLACEHOLDER_RE
from awesome_claude.workspace import Workspace

REAL_REPO_ROOT = Path(__file__).resolve().parents[1]

runner = CliRunner()


def test_templates_root_is_separate_from_the_package_root(real_workspace):
    # templates/ holds the generated-kit source material; pyproject.toml and
    # src/ are this package's own files and must NOT live under templates/.
    assert real_workspace.root == REAL_REPO_ROOT / "templates"
    assert (REAL_REPO_ROOT / "pyproject.toml").is_file()
    assert not (real_workspace.root / "pyproject.toml").exists()


def test_workspace_root_resolves_to_the_actual_preset_trees(real_workspace):
    assert list_presets(real_workspace) == ["java", "python"]
    assert (real_workspace.root / "python" / ".claude").is_dir()
    assert (real_workspace.root / "python" / "docs" / "adr" / "template.md").is_file()


def test_discover_against_real_repo_finds_expected_entities(real_workspace):
    python_catalog = discover(Workspace(root=real_workspace.path("python")))
    assert "python-expert" in python_catalog.names(".", "agents")
    assert "subtask-verifier" in python_catalog.names(".", "agents")
    assert "post-mortem" not in python_catalog.names(".", "skills")  # deleted in round 2


@pytest.mark.parametrize("preset", ["python", "java"])
def test_generated_preset_has_no_dangling_doc_references(preset, tmp_path):
    # A preset is one self-contained tree copied verbatim (see presets.py) -
    # there is no separate "docs copy" step to fall out of sync with, so a
    # freshly generated project must never have a dangling @docs/ reference.
    proj = tmp_path / "proj"
    result = runner.invoke(
        app,
        ["generate", "--preset", preset, "--name", "Big", "--package", "big", "--out", str(proj)],
    )
    assert result.exit_code == 0, result.stdout
    assert (proj / ".claude").is_dir()
    assert (proj / "docs").is_dir()

    workspace = Workspace(root=proj)
    catalog = discover(workspace)
    graph = build_dependency_graph(workspace, catalog, extra_scan_path=workspace.path("docs"))
    broken_docs = [r for r in graph.missing if r.kind == "doc"]
    assert broken_docs == []


def test_example_config_generates_with_no_unresolved_markdown_placeholders(tmp_path):
    # awesome-claude.example.toml is the documented --config example (see
    # README.md's "Config file" section) - it must actually work end to end,
    # and every deterministic {{PLACEHOLDER}} token it fills in must leave no
    # trace in the generated Markdown. docs/adr/template.md's own `{{ seq }}`
    # / `{{ title }}` Jinja tokens are a deliberate exception (a different
    # engine - see doctemplates.py - renders those later, at `docs new adr`
    # time, not at generate time) and PLACEHOLDER_RE correctly ignores them
    # since they aren't the all-caps `{{WORD}}` shape it matches.
    config_path = REAL_REPO_ROOT / "awesome-claude.example.toml"
    proj = tmp_path / "proj"
    result = runner.invoke(app, ["generate", "--config", str(config_path), "--out", str(proj)])
    assert result.exit_code == 0, result.stdout
    assert "Warnings:" not in result.stdout

    md_files = list(proj.rglob("*.md"))
    assert md_files  # sanity: didn't just generate an empty tree

    leftover = [f for f in md_files if PLACEHOLDER_RE.search(f.read_text(encoding="utf-8"))]
    assert leftover == []
