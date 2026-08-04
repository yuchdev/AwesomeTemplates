"""Scaffold a new document from a real template (Jinja2) - not just a verbatim
docs/ copy (see presets.py for that).

v1 covers one doc-type: ADR (`docs/adr/template.md` is the only doc-type with
a real template file today; `docs/reviews/` and `docs/security/` describe
their naming conventions in prose but have no template file yet). Adding
another doc-type, once its folder gets a real template.md, is one new
DOC_TYPES entry - not a redesign.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import jinja2

from awesome_claude.workspace import Workspace


class DocTemplateError(Exception):
    """Invalid doc-type / rendering failure - the CLI surfaces this as an error message."""


@dataclass(frozen=True)
class DocType:
    key: str
    template: str  # path relative to docs/, e.g. "adr/template.md"
    out_dir: str  # path relative to docs/, e.g. "adr"
    filename: str  # format string, e.g. "{seq:04d}-{slug}.md"
    seq_glob: str  # glob (within out_dir) used to find existing files for sequencing


DOC_TYPES: dict[str, DocType] = {
    "adr": DocType(
        key="adr",
        template="adr/template.md",
        out_dir="adr",
        filename="{seq:04d}-{slug}.md",
        seq_glob="[0-9][0-9][0-9][0-9]-*.md",
    ),
}


def slugify_title(title: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "-", title.strip()).strip("-").lower()
    return s or "untitled"


def next_sequence(out_dir: Path, seq_glob: str) -> int:
    numbers = []
    for f in out_dir.glob(seq_glob):
        m = re.match(r"(\d+)-", f.name)
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers, default=0) + 1


def render_new_document(
    workspace: Workspace, preset: str, doc_type_key: str, title: str, **extra: str
) -> Path:
    """Render doc_type_key's template with {seq, title, date, status, **extra}
    and write it to the doc-type's out_dir under templates/<preset>/docs/.
    Returns the new file's path."""
    doc_type = DOC_TYPES.get(doc_type_key)
    if doc_type is None:
        raise DocTemplateError(
            f"unknown doc type '{doc_type_key}' (choices: {', '.join(sorted(DOC_TYPES))})"
        )

    template_path = workspace.path(preset, "docs", *doc_type.template.split("/"))
    if not template_path.is_file():
        raise DocTemplateError(f"template not found: {template_path}")

    out_dir = workspace.path(preset, "docs", *doc_type.out_dir.split("/"))
    out_dir.mkdir(parents=True, exist_ok=True)
    seq = next_sequence(out_dir, doc_type.seq_glob)
    slug = slugify_title(title)
    filename = doc_type.filename.format(seq=seq, slug=slug)

    context = {
        "seq": f"{seq:04d}",
        "title": title,
        "date": date.today().isoformat(),
        "status": "Proposed",
        **extra,
    }

    env = jinja2.Environment(undefined=jinja2.StrictUndefined, keep_trailing_newline=True)
    try:
        rendered = env.from_string(template_path.read_text(encoding="utf-8")).render(**context)
    except jinja2.UndefinedError as exc:
        raise DocTemplateError(
            f"template '{template_path}' references an unprovided variable: {exc}"
        ) from exc

    out_path = out_dir / filename
    if out_path.exists():
        raise DocTemplateError(f"refusing to overwrite existing file: {out_path}")
    out_path.write_text(rendered, encoding="utf-8")
    return out_path
