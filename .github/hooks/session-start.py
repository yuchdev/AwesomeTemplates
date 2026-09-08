#!/usr/bin/env python3
"""Adapt the shared Claude session-start hook to Copilot's JSON output.

The live-context collection remains in one implementation under
``.claude/hooks``; this wrapper only translates stdout into Copilot's
``additionalContext`` response shape.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_hook = repo_root / ".claude" / "hooks" / "session_start.py"
    proc = subprocess.run(
        [sys.executable, str(source_hook)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        print("{}")
        return
    print(json.dumps({"additionalContext": proc.stdout.strip()}))


if __name__ == "__main__":
    main()

