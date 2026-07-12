"""Copy this repo's docs/ tree verbatim - no placeholder substitution.

Document *content* templating is out of scope here; --copy-docs/`docs copy`
just ships the scaffold as-is. See doctemplates.py for generating a single
new document (e.g. an ADR) from a real template.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from awesome_claude.workspace import Workspace


def copy_docs_tree(workspace: Workspace, docs_out: Path, force: bool) -> int:
    """Returns the number of files written; existing files are left alone
    unless force is set."""
    src_docs = workspace.path("docs")
    if not src_docs.is_dir():
        return 0
    count = 0
    for f in src_docs.rglob("*"):
        if not f.is_file():
            continue
        dst = docs_out / f.relative_to(src_docs)
        if dst.exists() and not force:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        count += 1
    return count
