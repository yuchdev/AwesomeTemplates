"""Copy a preset - templates/<preset>/, containing `.claude/`, `docs/`, and `scripts/` -
into a new project, applying the same {{PLACEHOLDER}} substitution every
other template file gets (see templating.py).

A preset is a complete, self-contained tree (see catalog.py's module
docstring): there is nothing to select or compose, so generation is just a
recursive copy plus substitution - never a per-entity loop. The one opt-in
exception is the specialization layer (see specializations.py): zero or more
templates/<preset>/specializations/<name>/.claude/ trees may be layered on top
of the base preset's .claude/ after the main copy, each also going through
the same substitution pass.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from awesome_templates.catalog import KINDS, discover
from awesome_templates.log_helper import NULL_LOG, LogHelper
from awesome_templates.specializations import specialization_root
from awesome_templates.templating import template_file
from awesome_templates.workspace import Workspace

# The only subdirectories a preset contributes to a generated project -
# never `specializations/`, which is an opt-in add-on layer selected via
# --specialization, not part of the base preset's own tree (see this
# module's docstring and specializations.py).
_PRESET_SUBDIRS = (".claude", "docs", "scripts")


def _copy_tree(
    src_root: Path,
    dest_root: Path,
    force: bool,
    subs: dict[str, str],
    warnings: list[str],
    log: LogHelper = NULL_LOG,
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
            log.debug(f"skipped {dst} (already exists, --force not set)")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        template_file(dst, subs, warnings)
        log.debug(f"wrote {dst}")
        count += 1
    return count


def _entity_names(root: Path) -> set[tuple[str, str]]:
    """(kind, name) pairs found by pointing catalog.discover at root - works
    unchanged whether root is a generated project's own root (kind dirs live
    under its .claude/) or a specialization's .claude/ dir directly (kind
    dirs live right there); see catalog.discover's module docstring for why
    both shapes resolve through the same function."""
    catalog = discover(Workspace(root=root))
    entries = catalog.entries.get(".", {})
    return {(kind, name) for kind in KINDS for name in entries.get(kind, {})}


def copy_preset(
    workspace: Workspace,
    preset: str,
    project_dir: Path,
    force: bool,
    subs: dict[str, str],
    warnings: list[str],
    specializations: Sequence[str] = (),
    log: LogHelper = NULL_LOG,
) -> int:
    """Copy the complete templates/<preset>/ tree into project_dir/, then
    layer each selected specialization's agents/skills on top.

    A name collision - between the base preset and a specialization, or
    between two specializations - is an authoring bug in templates/, not a
    runtime condition to warn-and-skip: silently skipping would leave
    project_dir missing content the caller explicitly asked for, and silently
    overwriting would make the outcome depend on --specialization ordering.
    """
    preset_root = workspace.path(preset)
    log.info(f"copying preset '{preset}' from {preset_root} into {project_dir}")
    count = 0
    for subdir in _PRESET_SUBDIRS:
        count += _copy_tree(preset_root / subdir, project_dir / subdir, force, subs, warnings, log=log)
    log.info(f"copied {count} file(s) for preset '{preset}'")
    seen = _entity_names(project_dir)
    for name in specializations:
        log.info(f"layering specialization '{name}' onto {project_dir / '.claude'}")
        spec_claude = specialization_root(workspace, preset, name) / ".claude"
        collisions = _entity_names(spec_claude) & seen
        if collisions:
            described = ", ".join(f"{kind}/{stem}" for kind, stem in sorted(collisions))
            message = (
                f"specialization '{name}' redefines existing entit"
                f"{'y' if len(collisions) == 1 else 'ies'}: {described}"
            )
            log.error(message)
            raise ValueError(message)
        added = _copy_tree(spec_claude, project_dir / ".claude", force, subs, warnings, log=log)
        count += added
        log.info(f"layered specialization '{name}': {added} file(s)")
        seen |= _entity_names(spec_claude)
    return count
