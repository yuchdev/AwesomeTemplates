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
        return sorted(self.entries[category][kind])


def discover(workspace: Workspace) -> Catalog:
    """category -> kind -> {entity_name: source_path}."""
    catalog: dict[str, dict[str, dict[str, Path]]] = {}
    for cat in CATEGORIES:
        catalog[cat] = {}
        for kind in KINDS:
            kind_dir = workspace.path(cat, kind)
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
            catalog[cat][kind] = entries
    return Catalog(entries=catalog)
