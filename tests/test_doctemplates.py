from __future__ import annotations

import pytest

import awesome_claude.doctemplates as doctemplates
from awesome_claude.doctemplates import (
    DocTemplateError,
    next_sequence,
    render_new_document,
    slugify_title,
)


def test_slugify_title():
    assert slugify_title("My Great Decision!") == "my-great-decision"
    assert slugify_title("") == "untitled"


def test_next_sequence_finds_max_plus_one(fixture_workspace):
    out_dir = fixture_workspace.path("docs", "adr")
    assert next_sequence(out_dir, "[0-9][0-9][0-9][0-9]-*.md") == 2  # only 0001-existing.md present


def test_render_new_document_fills_header(fixture_workspace):
    path = render_new_document(fixture_workspace, "adr", "A New Decision")
    text = path.read_text()
    assert "# 0002 - A New Decision" in text
    assert "**Status:** Proposed" in text
    assert path.name == "0002-a-new-decision.md"


def test_render_new_document_unknown_type_raises(fixture_workspace):
    with pytest.raises(DocTemplateError, match="unknown doc type"):
        render_new_document(fixture_workspace, "bogus", "Title")


def test_render_new_document_refuses_overwrite(fixture_workspace, monkeypatch):
    monkeypatch.setattr(doctemplates, "next_sequence", lambda out_dir, glob: 5)
    render_new_document(fixture_workspace, "adr", "Same Title")
    with pytest.raises(DocTemplateError, match="refusing to overwrite"):
        render_new_document(fixture_workspace, "adr", "Same Title")
