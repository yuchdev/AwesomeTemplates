"""Scan generated Markdown for `<!-- TEMPLATE-INIT: <instruction> -->` markers
and splice resolved prose back in - the pure, network-free half of the
AI-resolution feature (the API calls live in resolver.py).

A marker is the second kind of gap `generate` fills: not a deterministic
`{{PLACEHOLDER}}` (that is templating.py's job), but a project-specific fact
that only exists once someone reads the target project. This module finds every
marker and knows how to replace it; deciding *what* to write is resolver.py.

The markers in templates/ take several shapes this module must all handle:
- a whole section on its own line (agents/app-architect.md)
- inline mid-sentence, with prose before and after (feature-reviewer.md)
- multiline, spanning several lines (loops/implement-milestone.md)
- a list bullet with hanging indent (loops/implement-subtasks.md)
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

# `.*?` + DOTALL so a marker whose instruction wraps across lines collapses into
# a single match. Only the comment itself is matched; the line's leading
# indent/bullet is classified separately (see find_markers) so an inline marker
# never swallows the inter-word space in front of it. Kept deliberately distinct
# from templating.py's PLACEHOLDER_RE ({{WORD}}) - the two passes never overlap.
MARKER_RE = re.compile(
    r"<!--\s*TEMPLATE-INIT:\s*(?P<instruction>.*?)\s*-->",
    re.DOTALL,
)

# A line prefix that is *only* indentation and an optional list bullet - the
# signature of a block marker that owns its line(s).
_PREFIX_RE = re.compile(r"(?P<indent>[ \t]*)(?P<bullet>[-*]\s+)?\Z")

# How much surrounding prose to hand the model as context for each marker.
_CONTEXT_CHARS = 600


@dataclass(frozen=True)
class Marker:
    """One TEMPLATE-INIT marker located in a file.

    `start`/`end` are character offsets of the *full* match (indent + bullet +
    comment) so apply_replacements can splice by exact position. `inline` is
    True when non-whitespace precedes the marker on its own line - an inline
    marker sits inside a sentence and must be replaced without introducing a
    line break, whereas a block marker owns its line(s)."""

    path: Path
    start: int
    end: int
    raw: str
    instruction: str
    indent: str
    bullet: str | None
    before: str
    after: str
    inline: bool


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def find_markers(text: str, path: Path) -> list[Marker]:
    """Locate every marker in one file's text, in document order.

    A block marker (its line is nothing but indentation + optional bullet before
    the comment) extends its span back to the line start, so its replacement can
    reproduce that prefix. An inline marker keeps its span on the comment alone,
    so surrounding sentence spacing is preserved on replacement."""
    markers: list[Marker] = []
    for m in MARKER_RE.finditer(text):
        cstart, end = m.start(), m.end()
        line_start = text.rfind("\n", 0, cstart) + 1
        prefix = _PREFIX_RE.fullmatch(text[line_start:cstart])
        if prefix is not None:  # block: nothing but indent/bullet precedes it
            start = line_start
            indent = prefix.group("indent") or ""
            bullet = prefix.group("bullet")
            inline = False
        else:  # inline: sits inside a sentence
            start = cstart
            indent = ""
            bullet = None
            inline = True
        markers.append(
            Marker(
                path=path,
                start=start,
                end=end,
                raw=text[start:end],
                instruction=_collapse(m.group("instruction")),
                indent=indent,
                bullet=bullet,
                before=text[max(0, cstart - _CONTEXT_CHARS) : cstart],
                after=text[end : end + _CONTEXT_CHARS],
                inline=inline,
            )
        )
    return markers


def iter_markdown_files(root: Path) -> Iterator[Path]:
    """Every `.md` file under root, sorted for deterministic ordering."""
    yield from sorted(p for p in root.rglob("*.md") if p.is_file())


def scan_tree(root: Path) -> list[Marker]:
    """Find markers across every Markdown file in a generated tree.

    Mirrors templating.template_file's binary-skip: a file that isn't valid
    UTF-8 is skipped rather than crashing the scan."""
    markers: list[Marker] = []
    for path in iter_markdown_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        markers.extend(find_markers(text, path))
    return markers


def apply_replacements(text: str, repls: list[tuple[Marker, str]]) -> str:
    """Splice each marker's replacement into text.

    Replacements are applied in descending start order so that earlier offsets
    stay valid as later spans are rewritten."""
    for marker, replacement in sorted(repls, key=lambda r: r[0].start, reverse=True):
        text = text[: marker.start] + replacement + text[marker.end :]
    return text
