from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from awesome_claude.markers import (
    apply_replacements,
    find_markers,
    scan_tree,
)

BLOCK = "## Domain model\n\n<!-- TEMPLATE-INIT: describe the domain model here -->\n\n## Next\n"

INLINE = (
    "is external input ever passed to a shell? "
    "<!-- TEMPLATE-INIT: name the untrusted inputs this project ingests --> "
    "Missing auth checks.\n"
)

MULTILINE = (
    "### R5\n\n"
    "<!-- TEMPLATE-INIT: list this project's own milestone exit gates here so R1\n"
    "can collect them - e.g. a security-review pass, a coverage floor. If there\n"
    "are none, say so explicitly. -->\n\n"
    "## Iteration\n"
)

BULLET = "- <!-- TEMPLATE-INIT: name a design/spec doc path, or delete this bullet -->\n"

INDENT = "prose above\n  <!-- TEMPLATE-INIT: a continuation note -->\n"


def test_block_marker_is_not_inline():
    (marker,) = find_markers(BLOCK, Path("a.md"))
    assert marker.inline is False
    assert marker.bullet is None
    assert marker.instruction == "describe the domain model here"


def test_inline_marker_detected():
    (marker,) = find_markers(INLINE, Path("a.md"))
    assert marker.inline is True
    assert marker.instruction == "name the untrusted inputs this project ingests"


def test_multiline_instruction_collapses_to_one_marker():
    markers = find_markers(MULTILINE, Path("a.md"))
    assert len(markers) == 1
    assert markers[0].inline is False
    # Whitespace/newlines collapsed for the prompt.
    assert "\n" not in markers[0].instruction
    assert markers[0].instruction.startswith("list this project's own milestone exit gates")


def test_bullet_captured():
    (marker,) = find_markers(BULLET, Path("a.md"))
    assert marker.inline is False
    assert marker.bullet is not None and marker.bullet.startswith("-")
    assert marker.indent == ""


def test_indented_block_marker():
    (marker,) = find_markers(INDENT, Path("a.md"))
    assert marker.inline is False
    assert marker.bullet is None
    assert marker.indent == "  "


def test_apply_replacements_reverse_splices_multiple_markers():
    text = "A <!-- TEMPLATE-INIT: one --> B <!-- TEMPLATE-INIT: two --> C"
    m1, m2 = find_markers(text, Path("a.md"))
    out = apply_replacements(text, [(m1, "ONE"), (m2, "TWO")])
    assert out == "A ONE B TWO C"


def test_scan_tree_only_markdown_and_skips_binary(tmp_path: Path):
    (tmp_path / "a.md").write_text("<!-- TEMPLATE-INIT: x -->", encoding="utf-8")
    (tmp_path / "b.txt").write_text("<!-- TEMPLATE-INIT: not scanned -->", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("no marker here", encoding="utf-8")
    # A .md file that isn't valid UTF-8 must be skipped, not crash the scan.
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe<!-- TEMPLATE-INIT: y -->")

    markers = scan_tree(tmp_path)
    assert [m.path.name for m in markers] == ["a.md"]


def test_cli_import_does_not_pull_anthropic():
    # The offline generate path must stay free of the AI client: importing the
    # CLI (and even the resolver module) must not import anthropic at load time -
    # it's pulled in lazily only inside the --resolve-markers branch. Run in a
    # fresh interpreter so it's a true cold-import check.
    code = (
        "import sys; import awesome_claude.cli, awesome_claude.resolver; "
        "assert 'anthropic' not in sys.modules, 'anthropic imported at load time'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_resolved_tree_is_idempotent(tmp_path: Path):
    f = tmp_path / "a.md"
    f.write_text("before <!-- TEMPLATE-INIT: x --> after", encoding="utf-8")
    (marker,) = scan_tree(tmp_path)
    f.write_text(apply_replacements(f.read_text(encoding="utf-8"), [(marker, "RESOLVED")]), encoding="utf-8")
    assert scan_tree(tmp_path) == []
