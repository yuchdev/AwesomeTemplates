# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A generator (`awesome-claude` CLI, source in `src/awesome_claude`) that copies a project-specific
*preset* — a complete, self-contained `.claude/` kit (`agents`, `hooks`, `loops`, `skills`,
`settings.json`) plus its own starter `docs/` tree — from a template catalog under `templates/`.
Templates use flat `{{PLACEHOLDER}}` substitution (`PROJECT_NAME`, `PROJECT_PACKAGE`,
`PROJECT_PURPOSE`, `PROJECT_SLUG_UPPER`) so a preset can be dropped into another project after a
single find/replace.

A preset is a directory shaped exactly like what lands in the target project:
`templates/<preset>/.claude/` and `templates/<preset>/docs/` as siblings. There are currently two:
`python` and `java`. Generating one is *just* a recursive copy with substitution applied to every
text file (see `presets.py`) — there is no runtime composition step, no category selection, no
per-entity include/exclude. This is deliberate: `.claude/` and `docs/` used to be generated
independently (`generate` and `docs copy` as separate invocations, or even separate categories
composed at generate-time), which meant an agent's `@docs/foo.md` reference could point at a doc that
never got copied, with nothing to catch it. Baking both halves into one preset tree, authored and
reviewed together, makes that class of bug structurally impossible instead of runtime-checked — see
`docs/roadmap/0001-docs-claude-connectivity.md` for the fuller design history (that RFC's Phase 0 was
a runtime `--strict` connectivity check; the preset-tree model superseded it with the same guarantee
by construction).

Keep `src/awesome_claude` (the generator's own code) and `templates/` (the content it distributes)
mentally separate — most bugs are in one or the other, rarely both.

## Commands

```bash
# one-time setup - creates .venv and uv.lock
uv sync

# run the CLI
uv run awesome-claude list
uv run awesome-claude generate --preset python --name "Acme Sync" --package acme_sync --out .
uv run awesome-claude docs copy --preset python --name "Acme Sync" --package acme_sync --out docs
uv run awesome-claude docs new adr "Adopt structured logging" --preset python

# maintainer-only: render this repo's own agent/hook/loop/skill reference graph
uv run awesome-claude graph                      # every preset, side by side
uv run awesome-claude graph templates/python      # one preset's own graph + doc connectivity
uv run awesome-claude graph --inline --force
uv run awesome-claude graph --remove

# tests
uv run pytest --cov=awesome_claude
uv run pytest tests/test_catalog.py::test_name_here   # single test
uv run pytest tests/test_integration_real_repo.py     # exercises the real templates/ tree

# lint
uv run ruff check src/ tests/
```

`generate` also accepts `--config <file.json|file.toml>` (CLI flags override matching config values)
and `--dry-run --json` for a machine-readable preview. `--out` is the project root that gets a
`.claude/` and a `docs/` subdirectory (default: `.`); pass `--force` to overwrite existing content in
either.

**Ruff config note:** both `ruff.toml` (repo root) and `pyproject.toml`'s `[tool.ruff]` section exist
and disagree (different `line-length`, `target-version`, `select`/`ignore` sets). `ruff.toml` takes
precedence when both are present in the same directory, so it — not the `pyproject.toml` block — is
what `ruff check` actually applies.

## Architecture

### The template catalog (`templates/`)

Fixed shape: `templates/<preset>/.claude/<agents|hooks|loops|skills>/` and `templates/<preset>/docs/`.
A preset is *any* immediate subdirectory of `templates/` with both a `.claude/` and a `docs/` child —
`catalog.list_presets` discovers them dynamically, so adding a third preset (e.g. a `node` set) is a
matter of dropping a new tree in, not a code change. `skills` entities are directories (containing
`SKILL.md` + assets); every other kind is a single `.md` or `.py` file, keyed by filename stem.

The two presets are independent and self-contained by design, not two views onto shared source: each
has its own `settings.json` (already trimmed to reference only hooks that exist in that preset — e.g.
`java`'s has no `pytest`/`ruff` permissions or `post_edit_format`/`style_fixes`/`dep_audit`/`run_tests`
wiring, since those hooks are Python-only) and its own copy of anything both presets need (e.g.
`_common.py`, `session_start.py`, the `pr-review` skill). This means the same content can legitimately
differ between presets — `python/.claude/hooks/_common.py` and `java/.claude/hooks/_common.py` are not
required to be identical — so don't "deduplicate" them back into a shared location without checking
whether they've actually diverged.

### Generator pipeline (`src/awesome_claude`)

- `workspace.py` — `Workspace(root)` wraps the template tree root; every other module takes a
  `Workspace` instead of reading a global constant, so tests can point it at a synthetic `tmp_path`
  tree instead of this repo's real `templates/`. `cli.py` constructs the real one once
  (`TEMPLATES_ROOT = REPO_ROOT / "templates"`).
- `catalog.py` — `list_presets(workspace)` finds preset directories; `discover(workspace)` walks one
  into a `Catalog` (`kind -> {name: path}`, wrapped under category `"."`). Pointed at the `templates/`
  root itself (no `.claude`/kind dirs directly there), it instead recurses into each preset subdirectory
  and keys the result by preset name, so `graph` run against the whole tree can show every preset's
  catalog at once.
- `presets.py` — `copy_preset` copies a whole `templates/<preset>/` tree (both `.claude/` and `docs/`)
  into a target project directory; `copy_preset_docs` copies just the `docs/` half. Both apply the same
  `{{PLACEHOLDER}}` substitution as every other template file (via `templating.py`). This is the entire
  generation mechanism — there is no per-entity loop, no selection to resolve.
- `templating.py` — the substitution engine: a flat regex find/replace over the small fixed placeholder
  glossary, with an "unresolved placeholder left in <path>" warning rather than a hard failure.
- `doctemplates.py` — a *separate*, Jinja2-based engine used only by `docs new <type> <title>
  --preset <preset>` to render one new document (e.g. an ADR) into `templates/<preset>/docs/...` with
  sequencing/slugging logic. Different job from `templating.py` (loops/conditionals over a doc
  skeleton vs. flat substitution) — don't conflate them. Currently only `adr` is wired up in
  `DOC_TYPES`.
- `dependencies.py` — a maintainer-only tool for *this* repo's own catalog, not part of the `generate`
  flow: scans every entity's content for whole-word mentions of every other entity's name, builds a
  graph, and can render it as Mermaid/Markdown (`awesome-claude graph`), or upsert a per-file
  "Dependencies" block directly into `templates/**` (`--inline`), or remove them (`--remove`). Point
  `graph` at a single preset directory (or an already-generated project) to see that tree's own
  `.claude` <-> `docs` connectivity; both mutating flags edit the template tree in place — review
  `git diff` before committing.
- `cli.py` — Typer app; command tree is `list`, `graph`, `generate`, `docs copy`, `docs new`. Each
  `generate` flag has a config-file fallback (`--config file.json|.toml`) merged before CLI flags,
  which always win.

No `Selection`/category-composition layer exists anymore (the `selection.py`, `settings.py`, and
`requirements.py` modules were removed along with it) — a preset has nothing to select, compose, or
warn about missing target-project requirements for; it is what it is.

### Tests

`tests/conftest.py`'s `fixture_workspace` builds two tiny synthetic presets ("demo" and "other") under
`tmp_path`, each shaped like a real preset (`<preset>/.claude/<kind>/`, `<preset>/docs/`), for most
unit tests. `real_workspace` points at this repo's actual `templates/`, used by
`test_integration_real_repo.py` to catch real breakage a synthetic fixture can't — including a
parametrized regression test that generates each real preset and asserts zero dangling `@docs/`
references in the result. `test_dependencies.py` hand-builds a `Catalog` directly (bypassing
`catalog.discover()`'s filesystem walk) for its graph-matching-logic tests, since those exercise
`build_dependency_graph` against an arbitrary multi-category layout that isn't meant to model a real
preset.
