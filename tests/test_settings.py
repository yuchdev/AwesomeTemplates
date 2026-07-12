from __future__ import annotations

from awesome_claude.catalog import discover
from awesome_claude.selection import Selection
from awesome_claude.settings import build_settings


def test_build_settings_keeps_hook_wiring_present_in_selection(fixture_workspace):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    sel.add_category(catalog, "core")  # includes "guard" hook
    warnings: list[str] = []
    settings = build_settings(fixture_workspace, sel, {"PROJECT_NAME": "Acme"}, warnings)
    assert settings is not None
    assert "PreToolUse" in settings["hooks"]


def test_build_settings_drops_python_tooling_permissions_when_python_not_selected(
    fixture_workspace,
):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    sel.add_category(catalog, "core")
    warnings: list[str] = []
    settings = build_settings(fixture_workspace, sel, {"PROJECT_NAME": "Acme"}, warnings)
    assert not any("uv run pytest" in p for p in settings["permissions"]["allow"])
    assert any("uv run pytest" in w for w in warnings)


def test_build_settings_keeps_python_tooling_permissions_when_python_selected(fixture_workspace):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    sel.add_category(catalog, "core")
    sel.add_category(catalog, "python")
    warnings: list[str] = []
    settings = build_settings(fixture_workspace, sel, {"PROJECT_NAME": "Acme"}, warnings)
    assert any("uv run pytest" in p for p in settings["permissions"]["allow"])


def test_build_settings_returns_none_without_settings_json(tmp_path):
    from awesome_claude.workspace import Workspace

    empty_ws = Workspace(root=tmp_path)
    sel = Selection.empty()
    assert build_settings(empty_ws, sel, {"PROJECT_NAME": "Acme"}, []) is None
