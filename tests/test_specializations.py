from __future__ import annotations

import pytest

from awesome_templates.presets import copy_preset
from awesome_templates.specializations import (
    disallowed_kinds_present,
    list_specializations,
    specialization_root,
)

# --- list_specializations ---------------------------------------------------


def test_list_specializations_returns_only_valid_addons(fixture_workspace):
    assert list_specializations(fixture_workspace, "demo") == ["widgets"]


def test_list_specializations_empty_when_no_specializations_dir(fixture_workspace):
    assert list_specializations(fixture_workspace, "other") == []


def test_list_specializations_skips_dir_with_no_agents_or_skills(fixture_workspace):
    # "empty-scaffold" has a .claude/agents/ directory but no files in it -
    # not a usable specialization, and must not appear in the list.
    names = list_specializations(fixture_workspace, "demo")
    assert "empty-scaffold" not in names


def test_specialization_root_points_at_the_right_directory(fixture_workspace):
    root = specialization_root(fixture_workspace, "demo", "widgets")
    assert root == fixture_workspace.root / "demo" / "specializations" / "widgets"
    assert (root / ".claude" / "agents" / "widget-specialist.md").is_file()


# --- disallowed_kinds_present ------------------------------------------------


def test_disallowed_kinds_present_is_empty_for_a_clean_specialization(fixture_workspace):
    assert disallowed_kinds_present(fixture_workspace, "demo", "widgets") == []


def test_disallowed_kinds_present_flags_hooks_and_settings_json(fixture_workspace, tmp_path):
    root = fixture_workspace.root / "demo" / "specializations" / "dirty"
    (root / ".claude" / "agents").mkdir(parents=True)
    (root / ".claude" / "agents" / "x.md").write_text("---\nname: x\n---\n")
    (root / ".claude" / "hooks").mkdir(parents=True)
    (root / ".claude" / "hooks" / "guard.py").write_text("# hook\n")
    (root / ".claude" / "loops").mkdir(parents=True)  # present but empty - must not be flagged
    (root / ".claude" / "settings.json").write_text("{}")

    found = disallowed_kinds_present(fixture_workspace, "demo", "dirty")
    assert set(found) == {"hooks", "settings.json"}


# --- copy_preset merging ------------------------------------------------------


def test_copy_preset_merges_specialization_agent_into_claude_agents(fixture_workspace, tmp_path):
    warnings: list[str] = []
    project_dir = tmp_path / "proj"
    copy_preset(
        fixture_workspace, "demo", project_dir, False,
        {"PROJECT_NAME": "Acme"}, warnings, specializations=["widgets"],
    )
    assert (project_dir / ".claude" / "agents" / "widget-verifier.md").is_file()  # base preset, untouched
    addon = project_dir / ".claude" / "agents" / "widget-specialist.md"
    assert addon.is_file()
    assert addon.read_text() == "---\nname: widget-specialist\n---\n\nSpecialist for Acme.\n"
    assert warnings == []


def test_copy_preset_no_specializations_is_unaffected(fixture_workspace, tmp_path):
    warnings: list[str] = []
    project_dir = tmp_path / "proj"
    count = copy_preset(
        fixture_workspace, "demo", project_dir, False, {"PROJECT_NAME": "Acme"}, warnings,
    )
    assert not (project_dir / ".claude" / "agents" / "widget-specialist.md").exists()
    assert not (project_dir / "specializations").exists()
    assert count == copy_preset(  # calling again with specializations=() explicitly matches
        fixture_workspace, "demo", tmp_path / "proj2", False, {"PROJECT_NAME": "Acme"}, [],
        specializations=(),
    )


def test_copy_preset_never_copies_specializations_dir_itself(fixture_workspace, tmp_path):
    # The base preset copy must only ever produce .claude/, docs/, and
    # scripts/ - templates/<preset>/specializations/ is an opt-in add-on
    # layer, never part of the blanket tree copy, regardless of whether a
    # specialization was requested.
    project_dir = tmp_path / "proj"
    copy_preset(
        fixture_workspace, "demo", project_dir, False, {"PROJECT_NAME": "Acme"}, [],
        specializations=["widgets"],
    )
    assert not (project_dir / "specializations").exists()


def test_copy_preset_specialization_name_collision_raises(fixture_workspace, tmp_path):
    # Redefine the base preset's own agent under a second specialization.
    root = fixture_workspace.root / "demo" / "specializations" / "colliding"
    (root / ".claude" / "agents").mkdir(parents=True)
    (root / ".claude" / "agents" / "widget-verifier.md").write_text("---\nname: widget-verifier\n---\n")

    warnings: list[str] = []
    with pytest.raises(ValueError, match="widget-verifier"):
        copy_preset(
            fixture_workspace, "demo", tmp_path / "proj", False,
            {"PROJECT_NAME": "Acme"}, warnings, specializations=["colliding"],
        )


def test_copy_preset_two_specializations_colliding_with_each_other_raises(fixture_workspace, tmp_path):
    for name in ("dup-a", "dup-b"):
        root = fixture_workspace.root / "demo" / "specializations" / name
        (root / ".claude" / "agents").mkdir(parents=True)
        (root / ".claude" / "agents" / "shared-name.md").write_text("---\nname: shared-name\n---\n")

    with pytest.raises(ValueError, match="shared-name"):
        copy_preset(
            fixture_workspace, "demo", tmp_path / "proj", False,
            {"PROJECT_NAME": "Acme"}, [], specializations=["dup-a", "dup-b"],
        )
