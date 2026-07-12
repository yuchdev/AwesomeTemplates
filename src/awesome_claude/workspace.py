"""The template repo root, injected explicitly instead of a module-global.

Every other module takes a Workspace instead of reading a REPO_ROOT constant,
so tests can point at a synthetic tmp_path fixture instead of mutating or
depending on this repo's real content.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workspace:
    root: Path

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)
