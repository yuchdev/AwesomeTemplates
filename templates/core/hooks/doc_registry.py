#!/usr/bin/env python3
"""Doc registry: build a corpus-wide map of every `.md` file's headings and
report every broken relative link/anchor across the whole `docs/` + `.claude/`
tree in one pass. Backs the `/doc-registry` skill and `update-docs` loop's
scan mode.

CLI:
    python doc_registry.py [--json] [--cursor <path>]

``--json`` prints the full registry + broken-link list as JSON instead of a
human summary. ``--cursor <path>`` additionally writes that same JSON to
<path> (the `update-docs` loop reads this back on its next iteration instead
of re-scanning the whole corpus from a cold start).

Exit code 0 if no broken links were found, 1 otherwise - so it composes with
CI and with the loop's convergence check.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from _common import REPO_ROOT, find_broken_links, heading_slugs, iter_markdown_files


def build_registry() -> dict:
    files: dict[str, list[str]] = {}
    broken: list[str] = []
    for md in iter_markdown_files(None):
        rel = str(md.relative_to(REPO_ROOT))
        files[rel] = sorted(heading_slugs(md))
        broken.extend(find_broken_links(md))
    return {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_count": len(files),
        "files": files,
        "broken_links": broken,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the registry as JSON")
    parser.add_argument("--cursor", help="also write the registry JSON to this path")
    args = parser.parse_args()

    registry = build_registry()

    if args.cursor:
        cursor_path = Path(args.cursor)
        if not cursor_path.is_absolute():
            cursor_path = REPO_ROOT / cursor_path
        cursor_path.parent.mkdir(parents=True, exist_ok=True)
        cursor_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(registry, indent=2))
    else:
        print(f"doc_registry: {registry['file_count']} Markdown file(s) scanned.")
        if registry["broken_links"]:
            print(f"{len(registry['broken_links'])} broken link(s)/anchor(s):")
            for problem in registry["broken_links"]:
                print(f"  {problem}")
        else:
            print("0 problems.")

    sys.exit(1 if registry["broken_links"] else 0)


if __name__ == "__main__":
    main()
