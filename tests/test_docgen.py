from __future__ import annotations

import json
from pathlib import Path

from awesome_templates.docgen import (
    AgentInfo,
    list_agents,
    list_hooks,
    list_skills,
    list_test_files,
    render_agents_doc,
    render_test_layout_section,
    write_agent_docs,
    write_test_layout_doc,
)

# --- list_agents -------------------------------------------------------------


def test_list_agents_parses_name_and_description_from_frontmatter(tmp_path: Path):
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "python-expert.md").write_text(
        "---\nname: python-expert\ndescription: Implements features.\n"
        "model: claude-opus-4-8\n---\n\nBody.\n"
    )
    (agent,) = list_agents(tmp_path)
    assert agent.name == "python-expert"
    assert agent.description == "Implements features."
    assert agent.model == "claude-opus-4-8"


def test_list_agents_defaults_missing_frontmatter_fields_to_empty(fixture_workspace):
    # widget-verifier.md in the demo preset carries only `name:` in frontmatter.
    (agent,) = list_agents(fixture_workspace.path("demo"))
    assert agent.name == "widget-verifier"
    assert agent.description == ""
    assert agent.model == ""


# --- list_skills ---------------------------------------------------------


def test_list_skills_reads_skill_md_per_directory(fixture_workspace):
    # adr-write's SKILL.md in the demo preset has no frontmatter at all - name
    # must fall back to the directory name, other fields to "".
    (skill,) = list_skills(fixture_workspace.path("demo"))
    assert skill.name == "adr-write"
    assert skill.description == ""
    assert skill.invocation == ""


# --- list_hooks ------------------------------------------------------------


def test_list_hooks_derives_trigger_event_from_settings_json(fixture_workspace):
    hooks = list_hooks(fixture_workspace.path("demo"))
    # _common.py is a shared helper, never wired directly - must not appear.
    assert [h.name for h in hooks] == ["guard"]
    assert hooks[0].trigger == "PreToolUse: Bash"


def test_list_hooks_flags_unwired_hook_file_rather_than_dropping_it(fixture_workspace):
    hooks_dir = fixture_workspace.path("demo", ".claude") / "hooks"
    (hooks_dir / "orphan.py").write_text('"""An orphaned hook, never wired."""\n')

    hooks = list_hooks(fixture_workspace.path("demo"))
    by_name = {h.name: h for h in hooks}
    assert by_name["orphan"].trigger == "(unwired)"
    assert by_name["guard"].trigger == "PreToolUse: Bash"


def test_list_hooks_empty_when_no_hooks_dir(tmp_path: Path):
    assert list_hooks(tmp_path) == []


# --- rendering ---------------------------------------------------------------


def test_render_agents_doc_produces_stable_markdown_table():
    agents = [
        AgentInfo(name="python-expert", description="Implements features.", model="claude-opus-4-8"),
        AgentInfo(name="widget-verifier", description="", model=""),
    ]
    assert render_agents_doc(agents) == (
        "# Agent Reference\n"
        "\n"
        "| Agent | Model | Description |\n"
        "|-------|-------|-------------|\n"
        "| `python-expert` | claude-opus-4-8 | Implements features. |\n"
        "| `widget-verifier` | - | - |\n"
    )


def test_render_agents_doc_empty_list():
    assert render_agents_doc([]) == "# Agent Reference\n\nNo agents are currently defined.\n"


# --- write_agent_docs ---------------------------------------------------------


def _build_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    (project / ".claude" / "agents").mkdir(parents=True)
    (project / ".claude" / "agents" / "a.md").write_text(
        "---\nname: a\ndescription: does a thing.\nmodel: claude-opus-4-8\n---\n\nBody.\n"
    )
    (project / ".claude" / "skills").mkdir(parents=True)
    (project / ".claude" / "hooks").mkdir(parents=True)
    (project / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}}))
    (project / "docs" / "agent").mkdir(parents=True)
    for name in ("agents.md", "skills.md", "hooks.md"):
        (project / "docs" / "agent" / name).write_text(f"# {name} stub\n")
    return project


def test_write_agent_docs_preserves_existing_h1_heading(tmp_path: Path):
    project = _build_project(tmp_path)
    (project / "docs" / "agent" / "agents.md").write_text(
        "# My Custom Agents Doc\n\nold stale content\n"
    )

    warnings: list[str] = []
    write_agent_docs(project, warnings)

    result = (project / "docs" / "agent" / "agents.md").read_text()
    assert result.startswith("# My Custom Agents Doc\n")
    assert "old stale content" not in result
    assert "`a`" in result
    assert warnings == []


def test_write_agent_docs_writes_all_three_files(tmp_path: Path):
    project = _build_project(tmp_path)
    warnings: list[str] = []
    write_agent_docs(project, warnings)

    assert "`a`" in (project / "docs" / "agent" / "agents.md").read_text()
    assert "No skills are currently defined." in (project / "docs" / "agent" / "skills.md").read_text()
    assert "No hooks are currently defined." in (project / "docs" / "agent" / "hooks.md").read_text()
    assert warnings == []


def test_write_agent_docs_warns_when_doc_file_missing(tmp_path: Path):
    project = _build_project(tmp_path)
    (project / "docs" / "agent" / "agents.md").unlink()

    warnings: list[str] = []
    write_agent_docs(project, warnings)
    assert any("agents.md" in w for w in warnings)


# --- list_test_files / render_test_layout_section / write_test_layout_doc ---


def test_list_test_files_lists_real_test_paths(tmp_path: Path):
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "tests" / "test_a.py").write_text("")
    (tmp_path / "tests" / "unit" / "test_b.py").write_text("")
    (tmp_path / "src").mkdir()  # must not be swept in - only tests/
    (tmp_path / "src" / "app.py").write_text("")

    assert list_test_files(tmp_path) == ["tests/test_a.py", "tests/unit/test_b.py"]


def test_list_test_files_empty_when_no_tests_dir(tmp_path: Path):
    assert list_test_files(tmp_path) == []


def test_render_test_layout_section_is_stable_markdown():
    assert render_test_layout_section(["tests/test_a.py", "tests/unit/test_b.py"]) == (
        "## Actual Test Layout\n\n"
        "```\n"
        "tests/test_a.py\n"
        "tests/unit/test_b.py\n"
        "```\n"
    )


def test_render_test_layout_section_empty():
    assert render_test_layout_section([]) == (
        "## Actual Test Layout\n\nNo test files were found under `tests/`.\n"
    )


def _build_coverage_doc_project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "test_a.py").write_text("")
    (project / "docs" / "test").mkdir(parents=True)
    (project / "docs" / "test" / "code_test_coverage.md").write_text(
        "# Coverage Requirements Checklist\n\nSome static instructions.\n"
    )
    return project


def test_write_test_layout_doc_appends_section(tmp_path: Path):
    project = _build_coverage_doc_project(tmp_path)
    warnings: list[str] = []
    write_test_layout_doc(project, warnings)

    result = (project / "docs" / "test" / "code_test_coverage.md").read_text()
    assert "Some static instructions." in result
    assert "## Actual Test Layout" in result
    assert "tests/test_a.py" in result
    assert warnings == []


def test_write_test_layout_doc_is_idempotent_on_rerun(tmp_path: Path):
    project = _build_coverage_doc_project(tmp_path)
    write_test_layout_doc(project, [])
    write_test_layout_doc(project, [])

    result = (project / "docs" / "test" / "code_test_coverage.md").read_text()
    assert result.count("## Actual Test Layout") == 1
