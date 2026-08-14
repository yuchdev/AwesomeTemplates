"""Discovery of the presets/kinds/entities a Workspace's template tree offers.

A preset is a complete, self-contained tree - an immediate subdirectory of
the workspace root containing both `.claude/` and `docs/` (e.g.
templates/python, templates/java). Generating a preset is a plain recursive
copy (see presets.py) - never a runtime composition of pieces pulled from
elsewhere - so adding a new preset is a matter of dropping a new
templates/<name>/{.claude,docs} tree in, not a code change here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from awesome_templates.workspace import Workspace

KINDS = ["agents", "hooks", "loops", "skills"]
KIND_ALIAS = {"agent": "agents", "hook": "hooks", "loop": "loops", "skill": "skills"}
SKIP_NAMES = {"README.md", "MIGRATION_REPORT.md"}


@dataclass
class Catalog:
    entries: dict[str, dict[str, dict[str, Path]]]

    def names(self, category: str, kind: str) -> list[str]:
        return sorted(self.entries.get(category, {}).get(kind, {}))


def list_presets(workspace: Workspace) -> list[str]:
    """Every immediate child directory of the workspace root that is a
    complete preset (has both .claude/ and docs/)."""
    if not workspace.root.is_dir():
        return []
    return sorted(
        p.name
        for p in workspace.root.iterdir()
        if p.is_dir() and (p / ".claude").is_dir() and (p / "docs").is_dir()
    )


def discover(workspace: Workspace) -> Catalog:
    """kind -> {entity_name: source_path}, wrapped in one of three shapes
    depending on what workspace.root points at:

    - A generated project or a preset's `.claude/` dir has kind directories
      directly at its root (`agents/`, `hooks/`, ...): returned under the
      single category ".".
    - A preset directory (e.g. templates/python) has them nested one level
      under `.claude/`: also returned under ".", via the same fallback a
      generated project's root would use.
    - The templates/ root itself has no kind directories at any of the above
      locations, but has one or more preset subdirectories: each preset's
      entities are returned keyed by that preset's own name, so `graph` run
      against the whole templates/ tree can show every preset's catalog at
      once.
    """
    catalog = _discover_from_root(workspace)
    if catalog.entries:
        return catalog

    claude_dir = workspace.path(".claude")
    if claude_dir.is_dir():
        catalog = _discover_from_root(Workspace(root=claude_dir))
        if catalog.entries:
            return catalog

    presets = list_presets(workspace)
    if presets:
        merged: dict[str, dict[str, dict[str, Path]]] = {}
        for preset in presets:
            preset_catalog = discover(Workspace(root=workspace.path(preset)))
            merged[preset] = preset_catalog.entries.get(".", {kind: {} for kind in KINDS})
        return Catalog(entries=merged)

    return Catalog(entries={})


def _discover_from_root(workspace: Workspace) -> Catalog:
    flat_catalog: dict[str, dict[str, Path]] = {}
    found_any_kind = False
    for kind in KINDS:
        kind_dir = workspace.path(kind)
        entries = _discover_kind(kind, kind_dir)
        if entries:
            found_any_kind = True
        flat_catalog[kind] = entries

    if found_any_kind:
        # "." is a placeholder category name for a single self-contained tree
        # (as opposed to the templates/ root, where each preset gets its own
        # name as the category - see discover()).
        return Catalog(entries={".": flat_catalog})

    return Catalog(entries={})


def _discover_kind(kind: str, kind_dir: Path) -> dict[str, Path]:
    entries: dict[str, Path] = {}
    if kind_dir.is_dir():
        if kind == "skills":
            for d in sorted(p for p in kind_dir.iterdir() if p.is_dir()):
                entries[d.name] = d
        else:
            for f in sorted(kind_dir.iterdir()):
                if not f.is_file() or f.name in SKIP_NAMES:
                    continue
                if f.name.endswith("MIGRATION_REPORT.md"):
                    continue
                if f.suffix in (".md", ".py"):
                    entries[f.stem] = f
    return entries
