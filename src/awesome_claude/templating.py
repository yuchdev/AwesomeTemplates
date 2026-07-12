"""Entity {{PLACEHOLDER}} substitution - unchanged behavior from the round-1/2 script.

Deliberately NOT Jinja2: this is a flat find/replace over a small fixed
glossary (PROJECT_NAME, PROJECT_PACKAGE, PROJECT_PURPOSE, PROJECT_SLUG_UPPER)
with an explicit "leftover placeholder" warning. See doctemplates.py for the
Jinja2-based engine used for document generation, which is a different job
(loops/conditionals over a document skeleton) with different failure needs.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from awesome_claude.catalog import SKIP_NAMES

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def apply_subs(text: str, subs: dict[str, str]) -> str:
    return PLACEHOLDER_RE.sub(lambda m: subs.get(m.group(1), m.group(0)), text)


def template_file(path: Path, subs: dict[str, str], warnings: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return  # binary file (e.g. an image under a skill's examples/) - copy as-is
    new_text = apply_subs(text, subs)
    for m in PLACEHOLDER_RE.finditer(new_text):
        warnings.append(f"unresolved placeholder {{{{{m.group(1)}}}}} left in {path}")
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")


def copy_entity(src: Path, dst: Path, kind: str, subs: dict[str, str], warnings: list[str]) -> None:
    if kind == "skills":
        shutil.copytree(
            src,
            dst,
            dirs_exist_ok=True,
            ignore=lambda _dir, names: [
                n for n in names if n in SKIP_NAMES or n.endswith("MIGRATION_REPORT.md")
            ],
        )
        for f in dst.rglob("*"):
            if f.is_file():
                template_file(f, subs, warnings)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        template_file(dst, subs, warnings)


def slugify_package(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip()).strip("_").lower()
    return s or "project"


def slugify_upper(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip()).strip("_").upper()
    return s or "PROJECT"
