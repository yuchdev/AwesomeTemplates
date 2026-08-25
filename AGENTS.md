# AGENTS.md

Orientation for coding agents working in the Awesome Templates repository. 
`CLAUDE.md` in this directory carries the same material in more depth; this file is the short form.

## What this project is

A CLI generator (`awesome-templates`, source in `src/awesome_templates/`) that copies a
*preset* - a complete `.claude/` + `docs/` + `scripts/` tree - from `templates/` into a target
project, substituting a small placeholder glossary. Generation is a recursive copy, not a
composition engine. The output is Markdown and hook scripts that other people's agent fleets
will then act on.

## Orient yourself before editing

Three separate bodies of content share this repo. Identify which one your task is in:

| Location                  | What it is                          | How to judge a change            |
|---------------------------|-------------------------------------|-----------------------------------|
| `src/awesome_templates/`  | the generator's own Python code     | tests + ruff                      |
| `templates/<preset>/`     | content shipped into other projects | authoring correctness; cross-references must resolve |
| `.claude/` (repo root)    | this repo's own maintainer tooling  | not distributed; not covered by the preset rules |

`src/flake8_project_rules/` is a fourth, independent thing: a standalone flake8 plugin
(rules X001-X011) tested under `tests/flake8_lint/`.

## Commands

```bash
uv sync
uv run awesome-templates list
uv run awesome-templates generate . --preset python --name "Acme Sync"
uv run pytest --cov=awesome_templates
uv run pytest tests/test_integration_real_repo.py
uv run ruff check src/ tests/
```

The full local suite plus a clean ruff run is the completion bar. There is no CI, no coverage
floor, and no deployment. Note that the root `ruff.toml` - not `pyproject.toml`'s
`[tool.ruff]` block - is what `ruff check` applies; the two deliberately differ.

## Module orientation

`workspace.py` (injected root) → `catalog.py` (discovery) → `presets.py` (`copy_preset`, the
whole generation mechanism) + `templating.py` (substitution) → `docgen.py` (deterministic doc
regeneration, runs unconditionally). The opt-in AI stack is `markers.py` (pure scan/splice) →
`resolver.py` (what to say) → `headless.py` (agentic backend) / `ai/client.py` (the sole
`anthropic` importer). `dependencies.py` is a maintainer graph tool outside `generate`
entirely. `cli.py` is the Typer entry point: `list`, `graph`, `generate`.

Each module's docstring states its purpose *and why it is separate from its neighbours*. Read
the docstring before the code; match that style when adding one. The cross-module map lives in
`src/awesome_templates/CLAUDE.md`.

## Rules that are not negotiable

- Never make the offline `generate` path import `anthropic`. Only `ai/client.py` imports it,
  only lazily inside functions; `cli.py` imports the resolver modules lazily too. Two tests
  in `tests/test_markers.py` pin this.
- Never let a generated file reference something that was not generated. `.claude/`, `docs/`,
  and `scripts/` ship as one corpus.
- Never weaken the non-destructive defaults: `--force` to overwrite, and an idempotency guard
  on every AI-authored increment. A second `generate --force` must produce byte-identical
  output.
- Never resolve a `SME REVIEW NEEDED` marker into unflagged prose. Its output stays marked as
  an unreviewed AI draft regardless of confidence.
- Keep the two marker-resolution backends emitting byte-identical fallback formats -
  reconciliation in `headless.py` parses exactly what `resolver.render` writes.
- Inside a preset, a `.claude/hooks/` script may never import from `scripts/`, and
  `settings.json` may wire only hooks that actually exist in that preset.
- The `python` and `java` presets are independent copies. Do not deduplicate near-identical
  files between them without checking whether they have diverged on purpose.

## Style

Python `>= 3.11`, `from __future__ import annotations` everywhere. Use `Optional[T]` and
`Union[...]`, never `X | None` - `UP007` is disabled deliberately. Pass dependencies as
parameters (`Workspace`, `warnings: list[str]`, `log: LogHelper`); introduce no module-level
state. Keep external boundaries injectable: `resolver.py` takes a `client`, `headless.py`
takes a `run=`. Conventional Commits; never push directly to `master`.

## Where design decisions live

`docs/roadmap/{NNNN}-{slug}/`. There is no `docs/adr/` and no `docs/specs/` at this repo's
root - `docs/adr/` exists only inside the presets being distributed. Milestone `0001` uses
numbered `{NN}.{Title_With_Underscores}.md` documents; milestone `0002` uses `plan.md` +
`status.md`. Rejected alternatives are preserved as deferred milestones rather than deleted.
Reference them as `path#heading-slug`.
