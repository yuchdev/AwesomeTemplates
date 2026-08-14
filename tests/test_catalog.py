from __future__ import annotations

from awesome_templates.catalog import discover, list_presets
from awesome_templates.workspace import Workspace


def test_list_presets_finds_both(fixture_workspace):
    assert list_presets(fixture_workspace) == ["demo", "other"]


def test_discover_finds_entities_within_a_preset(fixture_workspace):
    catalog = discover(Workspace(root=fixture_workspace.path("demo")))
    assert catalog.names(".", "agents") == ["widget-verifier"]
    assert catalog.names(".", "hooks") == ["_common", "guard"]
    assert catalog.names(".", "skills") == ["adr-write"]


def test_discover_empty_kind_returns_empty_list(fixture_workspace):
    catalog = discover(Workspace(root=fixture_workspace.path("other")))
    assert catalog.names(".", "hooks") == []
    assert catalog.names(".", "skills") == []


def test_discover_at_templates_root_keys_by_preset(fixture_workspace):
    catalog = discover(fixture_workspace)
    assert catalog.names("demo", "agents") == ["widget-verifier"]
    assert catalog.names("other", "agents") == ["python-expert"]


def test_discover_real_repo_presets(real_workspace):
    python_catalog = discover(Workspace(root=real_workspace.path("python")))
    assert "python-expert" in python_catalog.names(".", "agents")
    assert "subtask-verifier" in python_catalog.names(".", "agents")

    java_catalog = discover(Workspace(root=real_workspace.path("java")))
    assert {"java-expert", "testing-expert"} <= set(java_catalog.names(".", "agents"))
