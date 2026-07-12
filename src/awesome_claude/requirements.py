"""Warn (never fail) about files a selected category's hooks/skills assume exist
in the project a kit is being generated into."""

from __future__ import annotations

from pathlib import Path

from awesome_claude.selection import Selection

# See SUGGESTED_CONFIGURATION.md's "GENERAL STRUCTURE" section.
REQUIRED_FILES: dict[str, list[str]] = {
    "python": ["pyproject.toml", "ruff.toml", ".mcp.json", ".env.example", ".coveragerc"],
}


def check_target_requirements(
    selection: Selection, warnings: list[str], project_root: Path | None = None
) -> None:
    project_root = project_root or Path.cwd()
    for cat, required in REQUIRED_FILES.items():
        if not any(selection.entries[cat].values()):
            continue
        for fname in required:
            if not (project_root / fname).exists():
                warnings.append(
                    f"requirement check: '{fname}' not found in {project_root} "
                    f"(assumed by {cat}-category hooks/skills)"
                )
