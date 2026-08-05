# Generator source (`src/awesome_claude`)

Loaded only when working under `src/awesome_claude/` — migrated out of the root `CLAUDE.md`
so it stops costing context in every session. Each module also carries a docstring stating
its own purpose and rationale; this file is the cross-module map those can't provide.

## Module map

- `workspace.py` — `Workspace(root)` wraps the template tree root; every other module takes a
  `Workspace` instead of reading a global constant, so tests can point it at a synthetic `tmp_path`
  tree instead of this repo's real `templates/`. `cli.py` constructs the real one once
  (`TEMPLATES_ROOT = REPO_ROOT / "templates"`).
- `catalog.py` — `list_presets(workspace)` finds preset directories; `discover(workspace)` walks one
  into a `Catalog` (`kind -> {name: path}`, wrapped under category `"."`). Pointed at the `templates/`
  root itself (no `.claude`/kind dirs directly there), it instead recurses into each preset subdirectory
  and keys the result by preset name, so `graph` run against the whole tree can show every preset's
  catalog at once.
- `presets.py` — `copy_preset` copies a whole `templates/<preset>/` tree (`.claude/`, `docs/`, and
  `scripts/`) into a target project directory. It applies the same `{{PLACEHOLDER}}` substitution as
  every other template file (via `templating.py`). This is the entire generation mechanism — there is no
  per-entity loop, no selection to resolve.
- `templating.py` — the substitution engine: a flat regex find/replace over the small fixed placeholder
  glossary, with an "unresolved placeholder left in <path>" warning rather than a hard failure.
- `dependencies.py` — a maintainer-only tool for *this* repo's own catalog, not part of the `generate`
  flow: scans every entity's content for whole-word mentions of every other entity's name, builds a
  graph, and can render it as Mermaid/Markdown (`awesome-claude graph`), or upsert a per-file
  "Dependencies" block directly into `templates/**` (`--inline`), or remove them (`--remove`). Point
  `graph` at a single preset directory (or an already-generated project) to see that tree's own
  `.claude` <-> `docs` connectivity; both mutating flags edit the template tree in place — review
  `git diff` before committing.
- `cli.py` — Typer app; command tree is `list`, `graph`, `generate`. Each `generate` flag has a
  config-file fallback (`--config file.json|.toml`) merged before CLI flags, which always win.

No `Selection`/category-composition layer exists anymore (the `selection.py`, `settings.py`, and
`requirements.py` modules were removed along with it) — a preset has nothing to select, compose, or
warn about missing target-project requirements for; it is what it is.
