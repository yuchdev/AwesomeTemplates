from __future__ import annotations

import json
from pathlib import Path

from awesome_templates.presets import copy_preset, load_preset_vars
from awesome_templates.workspace import Workspace


def _make_workspace_with_common(tmp_path: Path) -> Workspace:
    """A preset plus a templates/common/ tree, the shape presets.copy_preset
    expects - isolated from fixture_workspace (which has no common/ dir, by
    design, to pin that copy_preset stays backward-compatible without one)."""
    root = tmp_path / "repo"

    (root / "common" / ".claude" / "hooks").mkdir(parents=True)
    (root / "common" / ".claude" / "hooks" / "shared_hook.py").write_text("# shared for {{PROJECT_NAME}}\n")
    (root / "common" / "docs").mkdir(parents=True)
    (root / "common" / "docs" / "shared.md").write_text("Fleet: {{EXPERT_AGENT_NAME}}\n")

    (root / "demo" / ".claude" / "agents").mkdir(parents=True)
    (root / "demo" / ".claude" / "agents" / "own-agent.md").write_text("own agent for {{PROJECT_NAME}}\n")
    (root / "demo" / "docs").mkdir(parents=True)
    (root / "demo" / "preset_vars.json").write_text(json.dumps({"EXPERT_AGENT_NAME": "demo-expert"}))

    return Workspace(root=root)


def test_copy_preset_layers_common_tree_ahead_of_preset(tmp_path):
    workspace = _make_workspace_with_common(tmp_path)
    project_dir = tmp_path / "proj"
    warnings: list[str] = []
    count = copy_preset(workspace, "demo", project_dir, False, {"PROJECT_NAME": "Acme"}, warnings)

    assert (project_dir / ".claude" / "hooks" / "shared_hook.py").read_text() == "# shared for Acme\n"
    assert (project_dir / ".claude" / "agents" / "own-agent.md").is_file()
    assert count == 3  # shared_hook.py + shared.md + own-agent.md
    assert warnings == [
        "unresolved placeholder {{EXPERT_AGENT_NAME}} left in " + str(project_dir / "docs" / "shared.md")
    ]


def test_copy_preset_unaffected_when_no_common_tree(fixture_workspace, tmp_path):
    # fixture_workspace (conftest.py) has no templates/common/ - copy_preset must
    # still behave exactly as before its introduction.
    project_dir = tmp_path / "proj"
    count = copy_preset(fixture_workspace, "demo", project_dir, False, {"PROJECT_NAME": "Acme"}, [])
    assert (project_dir / ".claude" / "agents" / "widget-verifier.md").is_file()
    assert count > 0


def test_load_preset_vars_missing_file_returns_empty_dict(fixture_workspace):
    assert load_preset_vars(fixture_workspace, "demo") == {}


def test_load_preset_vars_reads_json_file(tmp_path):
    workspace = _make_workspace_with_common(tmp_path)
    assert load_preset_vars(workspace, "demo") == {"EXPERT_AGENT_NAME": "demo-expert"}


def test_preset_vars_resolve_common_placeholders_end_to_end(tmp_path):
    # Mirrors what cli.py's generate command does: merge load_preset_vars into
    # subs before calling copy_preset, so a common/ file's {{EXPERT_AGENT_NAME}}
    # resolves using the calling preset's own metadata.
    workspace = _make_workspace_with_common(tmp_path)
    project_dir = tmp_path / "proj"
    warnings: list[str] = []
    subs = {**load_preset_vars(workspace, "demo"), "PROJECT_NAME": "Acme"}
    copy_preset(workspace, "demo", project_dir, False, subs, warnings)

    assert (project_dir / "docs" / "shared.md").read_text() == "Fleet: demo-expert\n"
    assert warnings == []
