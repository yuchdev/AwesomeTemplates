# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A generator (`awesome-claude` CLI, source in `src/awesome_claude`) that assembles project-specific
Claude Code kits (`.claude/agents`, `hooks`, `loops`, `skills`, `settings.json`) and starter `docs/`
trees from a template catalog under `templates/`. Templates use flat `{{PLACEHOLDER}}` substitution
(`PROJECT_NAME`, `PROJECT_PACKAGE`, `PROJECT_PURPOSE`, `PROJECT_SLUG_UPPER`) so they can be dropped
into another project after a single find/replace.

Keep `src/awesome_claude` (the generator's own code) and `templates/` (the content it distributes)
mentally separate — most bugs are in one or the other, rarely both.

## Commands

```bash
# one-time setup - creates .venv and uv.lock
uv sync

# run the CLI
uv run awesome-claude list
uv run awesome-claude generate --preset python-minimal --name "Acme Sync" --package acme_sync --out .claude
uv run awesome-claude docs copy --name "Acme Sync" --package acme_sync --out docs
uv run awesome-claude docs new adr "Adopt structured logging"

# maintainer-only: render this repo's own agent/hook/loop/skill reference graph
uv run awesome-claude graph --out docs/dependency-graph.md

# tests
uv run pytest --cov=awesome_claude
uv run pytest tests/test_selection.py::test_name_here   # single test
uv run pytest tests/test_integration_real_repo.py        # exercises the real templates/ tree

# lint
uv run ruff check src/ tests/
```

`generate` also accepts `--config <file.json|file.toml>` (CLI flags override matching config values),
`--copy-docs`/`--check-requirements`, `--dry-run --json` for a machine-readable preview, and
`--include type:name` / `--exclude type:name` to cherry-pick individual entities on top of a preset.

**Ruff config note:** both `ruff.toml` (repo root) and `pyproject.toml`'s `[tool.ruff]` section exist
and disagree (different `line-length`, `target-version`, `select`/`ignore` sets). `ruff.toml` takes
precedence when both are present in the same directory, so it — not the `pyproject.toml` block — is
what `ruff check` actually applies.

## Architecture

### The template catalog (`templates/`)

Fixed shape: `templates/<category>/<agents|hooks|loops|skills>/`. Categories are `core`, `helpers`,
`java`, `orchestrators`, `python` (`CATEGORIES` in `catalog.py`); `helpers` has no entities in the
tree yet — that's expected, not a bug, since `discover()` just returns an empty dict for a missing
category/kind directory. `skills` entities are directories (containing `SKILL.md` + assets); every
other kind is a single `.md` or `.py` file, keyed by filename stem.

`core/hooks/_common.py` and `python/hooks/_common.py` are deliberately duplicated per category (each
category must stay self-contained/copyable on its own) — `Selection.apply_tokens` requires a
qualified `type:category/name` token to disambiguate any name that exists in more than one category.

`templates/core/settings.json` is the one settings template; `generate` trims it down based on what
was actually selected (see `settings.py` below) rather than shipping unconditional wiring.

`templates/docs/` is a separate, parallel tree (its own `docs new`/`docs copy` commands) — not one of
the four entity kinds above.

### Generator pipeline (`src/awesome_claude`)

- `workspace.py` — `Workspace(root)` wraps the template tree root; every other module takes a
  `Workspace` instead of reading a global constant, so tests can point it at a synthetic `tmp_path`
  tree instead of this repo's real `templates/`. `cli.py` constructs the real one once
  (`TEMPLATES_ROOT = REPO_ROOT / "templates"`).
- `catalog.py` — `discover(workspace)` walks the tree into a `Catalog` (`category -> kind -> {name:
  path}`). Also defines `PRESETS` (named category bundles, e.g. `python-minimal` = `core` + `python`).
- `selection.py` — `Selection` resolves a preset/category/`--include`/`--exclude` request into a
  concrete set of entities to emit; raises `SelectionError` on unknown names/ambiguous cross-category
  matches.
- `templating.py` — the substitution engine used when copying entities into a generated kit: a flat
  regex find/replace over the small fixed placeholder glossary, with an "unresolved placeholder left
  in <path>" warning rather than a hard failure. `copy_entity` handles both single-file entities and
  skill directories (`shutil.copytree` + per-file substitution).
- `doctemplates.py` — a *separate*, Jinja2-based engine used only by `docs new <type> <title>` to
  render one new document (e.g. an ADR) with sequencing/slugging logic. Different job from
  `templating.py` (loops/conditionals over a doc skeleton vs. flat substitution) — don't conflate them.
  Currently only `adr` is wired up in `DOC_TYPES`.
- `docs_scaffold.py` — `copy_docs_tree` copies the whole `templates/docs/` tree verbatim (using
  `templating.py`'s substitution, not Jinja2), for `generate --copy-docs` and `docs copy`.
- `settings.py` — `build_settings` loads `core/settings.json`, then drops any hook wiring whose hook
  name isn't in the selection, and strips Python-tooling permissions (`pytest`/`ruff`/`uv run`) when
  no `python`-category entity was selected — so the emitted `settings.json` never references files the
  kit didn't actually write.
- `requirements.py` — `check_target_requirements` warns (never fails) when a selected category's
  hooks/skills assume files exist in the *target* project (e.g. `python` category assumes
  `pyproject.toml`, `ruff.toml`, `.mcp.json`, `.env.example`, `.coveragerc`). Opt-in via
  `--check-requirements`.
- `dependencies.py` — a maintainer-only tool for *this* repo's own catalog, not part of the `generate`
  flow: scans every entity's content for whole-word mentions of every other entity's name, builds a
  graph, and can render it as Mermaid/Markdown (`awesome-claude graph`) or upsert a per-file
  "Dependencies" block directly into `templates/**` (`--inline`, which mutates the template tree in
  place — review `git diff` before committing after using it).
- `cli.py` — Typer app; command tree is `list`, `graph`, `generate`, `docs copy`, `docs new`. Each
  `generate`/`docs copy` flag has a config-file fallback (`--config file.json|.toml`) merged before CLI
  flags, which always win.

### Tests

`tests/conftest.py` provides two fixtures with different purposes: `fixture_workspace` (a small
synthetic `core`/`python`/`helpers`/`java`/`orchestrators` tree under `tmp_path`, used by most unit
tests) and `real_workspace` (points at this repo's actual `templates/`, used by
`test_integration_real_repo.py` to catch real breakage like a `TEMPLATES_ROOT` resolution bug that a
synthetic fixture would never surface).
