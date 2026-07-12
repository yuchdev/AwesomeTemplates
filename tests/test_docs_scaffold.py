from __future__ import annotations

from awesome_claude.docs_scaffold import copy_docs_tree


def test_copy_docs_tree_copies_all_files(fixture_workspace, tmp_path):
    dest = tmp_path / "out-docs"
    count = copy_docs_tree(fixture_workspace, dest, force=False)
    assert count == 2  # template.md + 0001-existing.md
    assert (dest / "adr" / "template.md").is_file()
    assert (dest / "adr" / "0001-existing.md").is_file()


def test_copy_docs_tree_skips_existing_without_force(fixture_workspace, tmp_path):
    dest = tmp_path / "out-docs"
    copy_docs_tree(fixture_workspace, dest, force=False)
    (dest / "adr" / "template.md").write_text("locally modified")
    count = copy_docs_tree(fixture_workspace, dest, force=False)
    assert count == 0  # both files already exist in dest, neither is re-copied
    assert (dest / "adr" / "template.md").read_text() == "locally modified"


def test_copy_docs_tree_overwrites_with_force(fixture_workspace, tmp_path):
    dest = tmp_path / "out-docs"
    copy_docs_tree(fixture_workspace, dest, force=False)
    (dest / "adr" / "template.md").write_text("locally modified")
    count = copy_docs_tree(fixture_workspace, dest, force=True)
    assert count == 2
    assert "locally modified" not in (dest / "adr" / "template.md").read_text()


def test_copy_docs_tree_missing_source_returns_zero(tmp_path):
    from awesome_claude.workspace import Workspace

    empty_ws = Workspace(root=tmp_path)
    assert copy_docs_tree(empty_ws, tmp_path / "out", force=False) == 0
