from __future__ import annotations

from awesome_templates.templating import (
    apply_subs,
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
