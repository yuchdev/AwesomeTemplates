from __future__ import annotations

from awesome_claude.catalog import discover


def test_discover_finds_entities(fixture_workspace):
    catalog = discover(fixture_workspace)
    assert catalog.names("core", "agents") == ["widget-verifier"]
    assert catalog.names("core", "hooks") == ["_common", "guard"]
    assert catalog.names("core", "skills") == ["adr-write"]
    assert catalog.names("python", "agents") == ["python-expert"]


def test_discover_empty_category_returns_empty_lists(fixture_workspace):
    catalog = discover(fixture_workspace)
    assert catalog.names("helpers", "agents") == []
    assert catalog.names("java", "hooks") == []


def test_discover_real_repo_matches_round_2_state(real_workspace):
    catalog = discover(real_workspace)
    assert set(catalog.names("java", "agents")) >= {"java-expert", "testing-expert"}
    assert catalog.names("java", "hooks") == []
    assert catalog.names("helpers", "agents") == []  # emptied when agents moved to python/
    assert "python-expert" in catalog.names("python", "agents")
