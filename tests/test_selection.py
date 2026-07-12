from __future__ import annotations

import pytest

from awesome_claude.catalog import discover
from awesome_claude.selection import Selection, SelectionError


def test_add_category(fixture_workspace):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    sel.add_category(catalog, "core")
    assert sel.entries["core"]["agents"] == {"widget-verifier"}
    assert not sel.is_empty()


def test_add_unknown_category_raises(fixture_workspace):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    with pytest.raises(SelectionError):
        sel.add_category(catalog, "bogus")


def test_include_single_hit(fixture_workspace):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    sel.apply_tokens(catalog, ["agent:widget-verifier"], adding=True)
    assert sel.entries["core"]["agents"] == {"widget-verifier"}


def test_include_ambiguous_name_requires_qualification(fixture_workspace):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    with pytest.raises(SelectionError, match="more than one category"):
        sel.apply_tokens(catalog, ["hook:_common"], adding=True)


def test_include_qualified_ambiguous_name(fixture_workspace):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    sel.apply_tokens(catalog, ["hook:python/_common"], adding=True)
    assert sel.entries["python"]["hooks"] == {"_common"}
    assert sel.entries["core"]["hooks"] == set()


def test_exclude_removes_from_category(fixture_workspace):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    sel.add_category(catalog, "core")
    sel.apply_tokens(catalog, ["agent:widget-verifier"], adding=False)
    assert sel.entries["core"]["agents"] == set()


def test_include_missing_name_raises(fixture_workspace):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    with pytest.raises(SelectionError, match="no agent named"):
        sel.apply_tokens(catalog, ["agent:does-not-exist"], adding=True)


def test_include_malformed_token_raises(fixture_workspace):
    catalog = discover(fixture_workspace)
    sel = Selection.empty()
    with pytest.raises(SelectionError, match="expects 'type:name'"):
        sel.apply_tokens(catalog, ["not-a-valid-token"], adding=True)
