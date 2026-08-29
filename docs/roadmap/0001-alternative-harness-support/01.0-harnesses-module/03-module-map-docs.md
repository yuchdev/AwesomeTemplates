# 03 - Module-map docs

**Parent task:** 01.0 `harnesses.py` + `claude` relocation
**State:** ⬜ Not started
**Depends on:** 02
**Blocks:** none

## Objective

Update [`src/awesome_templates/CLAUDE.md`](/src/awesome_templates/CLAUDE.md)'s
module map: add a `harnesses.py` entry, and revise the existing `headless.py`
entry so it describes consuming a `Harness` from the registry rather than being
hardcoded to the `claude` binary.

## Changes to `src/awesome_templates/CLAUDE.md`

Insert a new bullet before the existing `headless.py` bullet:

```markdown
- `harnesses.py` — per-backend adapters for headless sessions (marker research
  and, from Milestone 0001's `--port-to` addition, cross-harness porting):
  binary discovery (`find_harness`) and argv construction (`Harness.build_command`)
  for each supported CLI, registered by name in `_REGISTRY` (`get("claude")`, etc).
  `headless.py` and `port.py` own *what* a session does (manifest, prompt,
  reconciliation); this module only owns *how* to invoke a given CLI, so a wrong
  guess about one backend's flags is a one-function fix here, not a rewrite of a
  caller. Never imports `headless`/`port`/`subprocess` — it only locates binaries
  and assembles argv.
```

Revise the `headless.py` bullet's opening clause from "when the `claude` CLI is
installed, runs ONE headless Claude Code session (`claude -p --bare`, ...)" to
name the registry:

```markdown
- `headless.py` — the agentic half of `--resolve-markers`: given a `harness`
  name (`"claude"` by default; see `harnesses.py`), looks up its `Harness`,
  finds its binary, and — when found — runs ONE headless session (tools
  hard-allowlisted to Read/Grep/Glob/Edit/TodoWrite, `+Write` only under
  `--update-guidelines`) over the whole marker manifest rendered from
  `markers.scan_tree`, with cwd set to `detect_project_root`'s answer (out_dir
  when it holds a real project, else the `generate` invocation's cwd — the
  generate-into-a-scratch-dir case). [... rest of the existing paragraph
  unchanged from "Results are reconciled by..." onward, since reconciliation,
  the prompt content, and the fallback story are all harness-agnostic already.]
```

Do not rewrite the whole `headless.py` paragraph - only its opening clause
needs to stop naming `claude` specifically; the rest already describes
harness-agnostic behavior (reconciliation, the `resolver.resolve_tree`
fallback, the `run=` test seam).

## Constraints

- No prose beyond what's needed to describe the new module and correct the
  now-stale claim in the `headless.py` entry - this repo's `CLAUDE.md` files
  are dense reference, not tutorial prose.
- Run `/link-check` (or `python scripts/check_doc_links.py src/`) after
  editing if any new cross-reference is added.

## Success criteria

- [ ] `src/awesome_templates/CLAUDE.md`'s module map lists `harnesses.py`.
- [ ] The `headless.py` entry no longer states or implies `claude` is the only
      possible backend.
- [ ] `scripts/check_doc_links.py src/` reports no new dangling links.
