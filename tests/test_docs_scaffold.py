from __future__ import annotations

from awesome_claude.docs_scaffold import copy_docs_tree


def test_copy_docs_tree_copies_all_files(fixture_workspace, tmp_path):
    dest = tmp_path / "out-docs"
    count = copy_docs_tree(fixture_workspace, dest, force=False, subs={}, warnings=[])
    assert count == 2  # template.md + 0001-existing.md
    assert (dest / "adr" / "template.md").is_file()
    assert (dest / "adr" / "0001-existing.md").is_file()


def test_copy_docs_tree_skips_existing_without_force(fixture_workspace, tmp_path):
    dest = tmp_path / "out-docs"
    copy_docs_tree(fixture_workspace, dest, force=False, subs={}, warnings=[])
    (dest / "adr" / "template.md").write_text("locally modified")
    count = copy_docs_tree(fixture_workspace, dest, force=False, subs={}, warnings=[])
    assert count == 0  # both files already exist in dest, neither is re-copied
    assert (dest / "adr" / "template.md").read_text() == "locally modified"


def test_copy_docs_tree_overwrites_with_force(fixture_workspace, tmp_path):
    dest = tmp_path / "out-docs"
    copy_docs_tree(fixture_workspace, dest, force=False, subs={}, warnings=[])
    (dest / "adr" / "template.md").write_text("locally modified")
    count = copy_docs_tree(fixture_workspace, dest, force=True, subs={}, warnings=[])
    assert count == 2
    assert "locally modified" not in (dest / "adr" / "template.md").read_text()


def test_copy_docs_tree_missing_source_returns_zero(tmp_path):
    from awesome_claude.workspace import Workspace

    empty_ws = Workspace(root=tmp_path)
    assert copy_docs_tree(empty_ws, tmp_path / "out", force=False, subs={}, warnings=[]) == 0


def test_copy_docs_tree_substitutes_placeholders(tmp_path):
    from awesome_claude.workspace import Workspace

    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "file.md").write_text("Project: {{PROJECT_NAME}} ({{PROJECT_PACKAGE}})\n")
    ws = Workspace(root=root)

    dest = tmp_path / "out-docs"
    warnings: list[str] = []
    count = copy_docs_tree(
        ws, dest, force=False, subs={"PROJECT_NAME": "Acme", "PROJECT_PACKAGE": "acme"},
        warnings=warnings,
    )
    assert count == 1
    text = (dest / "file.md").read_text()
    assert text == "Project: Acme (acme)\n"
    assert "{{" not in text
    assert warnings == []


def test_copy_docs_tree_warns_on_unresolved_placeholder(tmp_path):
    from awesome_claude.workspace import Workspace

    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "file.md").write_text("Value: {{UNKNOWN_VAR}}\n")
    ws = Workspace(root=root)

    dest = tmp_path / "out-docs"
    warnings: list[str] = []
    copy_docs_tree(ws, dest, force=False, subs={}, warnings=warnings)
    assert len(warnings) == 1
    assert "{{UNKNOWN_VAR}}" in warnings[0]
    assert (dest / "file.md").read_text() == "Value: {{UNKNOWN_VAR}}\n"


def test_copy_docs_tree_skips_binary_file_gracefully(tmp_path):
    from awesome_claude.workspace import Workspace

    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    binary_content = b"\xff\xfe\x00binary"
    (root / "docs" / "image.bin").write_bytes(binary_content)
    ws = Workspace(root=root)

    dest = tmp_path / "out-docs"
    count = copy_docs_tree(ws, dest, force=False, subs={"PROJECT_NAME": "Acme"}, warnings=[])
    assert count == 1
    assert (dest / "image.bin").read_bytes() == binary_content


def test_copy_docs_tree_mmd_like_file_left_unmodified(tmp_path):
    from awesome_claude.workspace import Workspace

    root = tmp_path / "repo"
    (root / "docs" / "assets").mkdir(parents=True)
    content = "---\ntitle: Example\n---\ngraph LR\n  a --> b\n"
    (root / "docs" / "assets" / "example.mmd").write_text(content)
    ws = Workspace(root=root)

    dest = tmp_path / "out-docs"
    count = copy_docs_tree(ws, dest, force=False, subs={"PROJECT_NAME": "Acme"}, warnings=[])
    assert count == 1
    assert (dest / "assets" / "example.mmd").read_text() == content
