"""Copy a preset - templates/<preset>/, containing `.claude/`, `docs/`, and `scripts/` -
into a new project, applying the same {{PLACEHOLDER}} substitution every
other template file gets (see templating.py).

A preset is a complete, self-contained tree (see catalog.py's module
docstring): there is nothing to select or compose, so generation is just a
recursive copy plus substitution - never a per-entity loop.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from awesome_templates.templating import template_file
from awesome_templates.workspace import Workspace


def _copy_tree(
    src_root: Path,
    dest_root: Path,
    force: bool,
    subs: dict[str, str],
    warnings: list[str],
) -> int:
    """Returns the number of files written; existing files are left alone
    unless force is set."""
    if not src_root.is_dir():
        return 0
    count = 0
    for f in src_root.rglob("*"):
        if not f.is_file():
            continue
        dst = dest_root / f.relative_to(src_root)
        if dst.exists() and not force:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        template_file(dst, subs, warnings)
        count += 1
    return count


def copy_preset(
    workspace: Workspace,
    preset: str,
    project_dir: Path,
    force: bool,
    subs: dict[str, str],
    warnings: list[str],
) -> int:
    """Copy the complete templates/<preset>/ tree into project_dir/."""
    return _copy_tree(workspace.path(preset), project_dir, force, subs, warnings)
