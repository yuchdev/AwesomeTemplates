from __future__ import annotations

from awesome_claude.templating import (
    apply_subs,
    copy_entity,
    slugify_package,
    slugify_upper,
    template_file,
)


def test_apply_subs_replaces_known_placeholders():
    text = "Hello {{PROJECT_NAME}}, package {{PROJECT_PACKAGE}}."
    result = apply_subs(text, {"PROJECT_NAME": "Acme", "PROJECT_PACKAGE": "acme"})
    assert result == "Hello Acme, package acme."


def test_apply_subs_leaves_unknown_placeholder():
    assert apply_subs("{{UNKNOWN}}", {"PROJECT_NAME": "Acme"}) == "{{UNKNOWN}}"


def test_template_file_warns_on_unresolved_placeholder(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("{{PROJECT_NAME}} and {{MYSTERY}}")
    warnings: list[str] = []
    template_file(f, {"PROJECT_NAME": "Acme"}, warnings)
    assert f.read_text() == "Acme and {{MYSTERY}}"
    assert any("MYSTERY" in w for w in warnings)


def test_template_file_no_warning_when_fully_resolved(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("{{PROJECT_NAME}}")
    warnings: list[str] = []
    template_file(f, {"PROJECT_NAME": "Acme"}, warnings)
    assert f.read_text() == "Acme"
    assert warnings == []


def test_slugify_package():
    assert slugify_package("Acme Sync!") == "acme_sync"
    assert slugify_package("") == "project"


def test_slugify_upper():
    assert slugify_upper("Acme Sync") == "ACME_SYNC"
    assert slugify_upper("") == "PROJECT"


def test_copy_entity_templates_a_single_file(tmp_path):
    src = tmp_path / "src" / "widget.md"
    src.parent.mkdir(parents=True)
    src.write_text("Agent for {{PROJECT_NAME}}.")
    dst = tmp_path / "out" / "agents" / "widget.md"
    warnings: list[str] = []
    copy_entity(src, dst, "agents", {"PROJECT_NAME": "Acme"}, warnings)
    assert dst.read_text() == "Agent for Acme."
    assert warnings == []


def test_copy_entity_skill_directory_excludes_migration_report(tmp_path):
    src = tmp_path / "src" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("{{PROJECT_NAME}} skill")
    (src / "MIGRATION_REPORT.md").write_text("internal notes, never shipped")
    (src / "references").mkdir()
    (src / "references" / "guide.md").write_text("{{PROJECT_PACKAGE}} guide")

    dst = tmp_path / "out" / "skills" / "my-skill"
    warnings: list[str] = []
    copy_entity(src, dst, "skills", {"PROJECT_NAME": "Acme", "PROJECT_PACKAGE": "acme"}, warnings)

    assert (dst / "SKILL.md").read_text() == "Acme skill"
    assert (dst / "references" / "guide.md").read_text() == "acme guide"
    assert not (dst / "MIGRATION_REPORT.md").exists()
