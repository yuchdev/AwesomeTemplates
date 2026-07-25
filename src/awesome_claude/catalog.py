"""Discovery of the categories/kinds/entities a Workspace's template tree offers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from awesome_claude.workspace import Workspace

CATEGORIES = ["core", "helpers", "java", "orchestrators", "python"]
KINDS = ["agents", "hooks", "loops", "skills"]
SKIP_NAMES = {"README.md", "MIGRATION_REPORT.md"}

PRESETS: dict[str, list[str]] = {
    "core-only": ["core"],
    "python-minimal": ["core", "python"],
    "python-full": ["core", "helpers", "orchestrators", "python"],
    "java-minimal": ["core", "java"],
    "java-full": ["core", "helpers", "orchestrators", "java"],
}


@dataclass
class Catalog:
    entries: dict[str, dict[str, dict[str, Path]]]

    def names(self, category: str, kind: str) -> list[str]:
        return sorted(self.entries.get(category, {}).get(kind, {}))


def discover(workspace: Workspace) -> Catalog:
    """category -> kind -> {entity_name: source_path}."""
    catalog = _discover_from_root(workspace)
    if catalog.entries:
        return catalog

    # If nothing found at root, try .claude/ subdirectory (common in generated projects)
    claude_dir = workspace.path(".claude")
    if claude_dir.is_dir():
        catalog = _discover_from_root(Workspace(root=claude_dir))
        if catalog.entries:
            return catalog

    return Catalog(entries={})


def _discover_from_root(workspace: Workspace) -> Catalog:
    catalog: dict[str, dict[str, dict[str, Path]]] = {}

    # Try standard layout first (category/kind/entity)
    for cat in CATEGORIES:
        found_any_kind = False
        cat_catalog: dict[str, dict[str, Path]] = {}
        for kind in KINDS:
            kind_dir = workspace.path(cat, kind)
            entries = _discover_kind(kind, kind_dir)
            if entries:
                found_any_kind = True
            cat_catalog[kind] = entries
        if found_any_kind:
            catalog[cat] = cat_catalog

    if catalog:
        return Catalog(entries=catalog)

    # Try flat layout (kind/entity) - common in generated .claude/ dirs
    flat_catalog: dict[str, dict[str, Path]] = {}
    found_any_kind = False
    for kind in KINDS:
        kind_dir = workspace.path(kind)
        entries = _discover_kind(kind, kind_dir)
        if entries:
            found_any_kind = True
        flat_catalog[kind] = entries

    if found_any_kind:
        # We use "." as a special category name for flat layouts
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
