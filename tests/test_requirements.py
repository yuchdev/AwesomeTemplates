from __future__ import annotations

from awesome_claude.catalog import discover
from awesome_claude.requirements import check_target_requirements
from awesome_claude.selection import Selection


def test_no_warning_when_python_not_selected(fixture_workspace, tmp_path):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    sel.add_category(catalog, "core")
    warnings: list[str] = []
    check_target_requirements(sel, warnings, project_root=tmp_path)
    assert warnings == []


def test_warns_on_missing_python_requirements(fixture_workspace, tmp_path):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    sel.add_category(catalog, "python")
    warnings: list[str] = []
    check_target_requirements(sel, warnings, project_root=tmp_path)
    assert any("pyproject.toml" in w for w in warnings)
    assert len(warnings) == 5


def test_no_warning_when_requirements_present(fixture_workspace, tmp_path):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    sel.add_category(catalog, "python")
    for fname in ("pyproject.toml", "ruff.toml", ".mcp.json", ".env.example", ".coveragerc"):
        (tmp_path / fname).write_text("")
    warnings: list[str] = []
    check_target_requirements(sel, warnings, project_root=tmp_path)
    assert warnings == []
