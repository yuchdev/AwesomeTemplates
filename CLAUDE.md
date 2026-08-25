# CLAUDE.md

Guidance for Claude Code working in the Awesome Templates repository.

## Three things that are easy to confuse

Hold this separation before touching anything - most confusion in this repo comes from
collapsing these:

1. **`src/awesome_templates/`** - the generator's own Python code. This is what tests and
   ruff apply to.
2. **`templates/<preset>/`** - the *content* the generator distributes. It is Markdown, hook
   scripts, and starter docs meant to land in someone else's project. Bugs here are
   authoring bugs, not code bugs.
3. **The repo root `.claude/`** - this repo's own maintainer tooling, distributed to nobody.
   `create-from-template.md` is the one agent in it: the interactive sibling of
   `generate --resolve-markers`, run from outside a target project to research it and fill
   in markers.

Most bugs live in exactly one of these. Say which one you are in before you start.

## Commands

```bash
uv sync                                              # one-time setup

uv run awesome-templates list
uv run awesome-templates generate . --preset python --name "Acme Sync" --package acme_sync
uv run awesome-templates generate . --preset python --name "Acme Sync" --specialization django
uv run awesome-templates generate . --preset python --name "Acme Sync" --resolve-markers
uv run awesome-templates generate . --preset python --name "Acme Sync" --resolve-markers --seed-roadmap

uv run awesome-templates graph                       # maintainer-only reference graph
uv run awesome-templates graph templates/python
uv run awesome-templates graph --inline --force      # MUTATES templates/** in place
uv run awesome-templates graph --remove

uv run pytest --cov=awesome_templates                # full suite
uv run pytest tests/test_catalog.py::test_name_here  # single test
uv run pytest tests/test_integration_real_repo.py    # exercises the real templates/ tree
uv run ruff check src/ tests/
```

**Ruff config note:** `ruff.toml` (repo root) and `pyproject.toml`'s `[tool.ruff]` section
both exist and disagree - different `line-length` (120 vs 100), `target-version` (py312 vs
py311), and `select`/`ignore` sets. `ruff.toml` wins when both are present in the same
directory, so it is what `ruff check` actually applies. Notably it *disables* `UP007`, which
is what keeps `Optional[T]` legal in this codebase.

There is no `.github/` and no CI. There is no coverage floor (`pyproject.toml` sets no
`fail_under`, no `addopts`, only `testpaths = ["tests"]`), so report coverage deltas but do
not gate on a number.

## Architecture map

### Generator pipeline (`src/awesome_templates/`)

- **`workspace.py`** - `Workspace(root)`, a frozen dataclass wrapping the template tree root.
  Every other module takes one instead of reading a global constant, so tests can point at a
  synthetic `tmp_path` tree. `cli.py` constructs the real one once.
- **`catalog.py`** - `list_presets` finds preset directories; `discover` walks one into a
  `Catalog` (`category -> kind -> {name: path}`). `KINDS` is fixed at `agents`, `hooks`,
  `loops`, `skills`. `skills` entities are directories containing a `SKILL.md`; every other
  kind is a single `.md` or `.py` keyed by filename stem. `discover` resolves three tree
  shapes through one function - see its docstring before adding a fourth.
- **`presets.py`** - `copy_preset` is the entire generation mechanism: a recursive copy of
  `{.claude,docs,scripts}` plus substitution, then zero or more specializations layered on
  top. A name collision raises `ValueError` (an authoring bug in `templates/`, not a runtime
  condition to warn-and-skip).
- **`specializations.py`** - discovery for the opt-in add-on layer, restricted to `agents/`
  and `skills/` via `ALLOWED_KINDS`. `disallowed_kinds_present` flags a specialization that
  ships a `hooks/`, `loops/`, or `settings.json` it may not.
- **`templating.py`** - the flat `PLACEHOLDER_RE` find/replace plus `slugify_package` /
  `slugify_upper`. Leftovers warn rather than fail.
- **`config.py`** - `--config` JSON/TOML loading, dispatched on file extension.
- **`docgen.py`** - deterministic, no-network doc generation that runs on *every* `generate`.
  Regenerates `docs/agent/{agents,skills,hooks}.md` and the "Actual Test Layout" section.
  Must never import `anthropic`.
- **`markers.py`** - the pure, network-free scan and splice of marker comments. `MARKER_KINDS`
  is `TEMPLATE-INIT` and `SME REVIEW NEEDED`. `Marker` is frozen and carries character
  offsets, so `apply_replacements` splices by exact position in descending order.
- **`resolver.py`** - the business logic of resolution: prompts, `gather_context`'s bundle,
  the confidence/TODO fallback, `render`'s exact output formats, and the three extra
  AI-authored increments (tutorial, roadmap seed, test-conventions paragraph). Never imports
  the SDK, so every model-calling function takes a `client` parameter and is unit-tested
  against a fake one.
- **`headless.py`** - the agentic backend: one `claude -p` session over the whole marker
  manifest, tools hard-allowlisted, reconciled by a before/after scan diff. Takes `run=`
  (defaulting to `subprocess.run`) so tests assert on argv and prompt with no real CLI.
- **`ai/client.py`** - the only module allowed to import `anthropic`, and only lazily inside
  its functions. It knows nothing about markers or prose; it places one request and returns
  parsed JSON.
- **`log_helper.py`** - `LogSeverity` and `LogHelper`, threaded as an optional `log=` keyword
  (defaulting to `NULL_LOG`) through every writing function, the same way `warnings:
  list[str]` already is. Writes to stderr.
- **`dependencies.py`** - maintainer-only graph tool for this repo's own catalog. Not part of
  `generate`; never invoke it implicitly from another command.
- **`cli.py`** - the Typer app. Commands: `list`, `graph`, `generate`.

`src/flake8_project_rules/` is a separate, standalone package: a flake8 plugin implementing
custom AST rules X001-X011, covered by `tests/flake8_lint/`. It is unrelated to the generator
pipeline.

### The template catalog (`templates/`)

The two presets are **independent, self-contained copies, not two views onto shared source**.
Each has its own `settings.json`, already trimmed to wire only hooks that exist in that preset
(`java`'s has no pytest/ruff permissions and no `post_edit_format`/`style_fixes`/`dep_audit`/
`run_tests` wiring, since those hooks are Python-only), and its own copy of anything both need
(`_common.py`, `session_start.py`, the `pr-review` skill). The same file may legitimately
differ between presets - do **not** "deduplicate" `python/.claude/hooks/_common.py` and its
`java` twin into a shared location without first checking whether they have diverged.

#### `.claude/hooks/` vs `scripts/` - two tiers, one rule each

Which tier an executable belongs in is decided by **what triggers it**, not by what it does.

|                  | `.claude/hooks/`                                              | `scripts/`                                          |
|------------------|---------------------------------------------------------------|------------------------------------------------------|
| **Trigger**      | Wired in `settings.json`; runs automatically on a matching event | Invoked by explicit path from agent/skill/loop prose |
| **Contract**     | Event JSON on stdin, exit `0` allow / `2` block               | Ordinary CLI: argv in, exit code out; must have `--help` |
| **Cost budget**  | Must stay cheap - runs on *every* matching call               | May be slow; runs on request                         |
| **Dependencies** | Stdlib + `_common.py` only. **Never** imports from `scripts/`  | Stdlib only; independent of `_common.py`             |

Two consequences that are easy to get wrong:

1. A hook may also expose a CLI escape hatch (`doc_link_check.py --check`, `style_fixes.py
   --check`, `secret_scan.py <paths>`) so a skill can re-run the same gate on demand. That
   does not make it a `scripts/` tool - `settings.json` still owns its trigger.
2. A fast hook and a thorough `scripts/` tool may deliberately overlap. Because the hook
   cannot import from `scripts/`, that logic is genuinely duplicated, so `_common.slugify`
   and `check_doc_links.slugify` **must stay behaviourally identical** - otherwise the
   auto-gate and `/link-check` return contradictory verdicts for the same anchor.

What is not allowed - every one of these has shipped here as a real bug: a hook and a script
implementing the same job under different names with no documented split; prose naming a tool
the preset does not ship; a hook importing a name its `_common.py` does not define.

## Invariants a change must not break

- **Non-destructiveness.** `generate` refuses to write into a non-empty `.claude/`, `docs/`,
  or `scripts/` without `--force`; `_copy_tree` skips existing files unless forced; every
  AI-authored increment has an idempotency guard (a stub comparison or a sentinel string) so
  a repeat run never clobbers user edits. `seed_first_milestone` is the one function that
  calls `shutil.rmtree`, which is why it is gated behind its own separate flag.
- **Corpus completeness.** `.claude/`, `docs/`, and `scripts/` are always generated together,
  so a generated file never references something that was not generated.
- **No leftovers.** No unsubstituted placeholder token and no unresolved marker comment may
  survive into a generated tree.
- **The offline path stays offline.** `anthropic` is imported only from `ai/client.py`, only
  lazily; `cli.py` imports `resolver`/`headless` lazily inside the `--resolve-markers` branch.
  Pinned by `tests/test_markers.py::test_cli_import_does_not_pull_anthropic` and
  `::test_docgen_import_does_not_pull_anthropic`.
- **`SME REVIEW NEEDED` is never silently resolved.** `resolver.render` emits the unreviewed
  draft blockquote regardless of the model's confidence, and counts it under
  `ResolveSummary.human_review` rather than `resolved`/`todos`.
- **The two resolution backends stay equivalent.** They must return the same `ResolveSummary`
  shape and emit byte-identical TODO / SME-draft fallbacks, because `headless._TODO_RE` and
  `_SME_RE` parse exactly what `resolver.render` writes.
- **Idempotent regeneration.** A second `generate --force` produces byte-identical output;
  `docgen`'s writers and `dependencies.upsert_marked_block` are pure functions of the current
  tree for exactly this reason.

## Conventions

- Python `>= 3.11`. `Optional[T]` and `Union[...]`, never the `X | None` shorthand - `UP007`
  is disabled in `ruff.toml` deliberately.
- `from __future__ import annotations` at the top of every module.
- Every module carries a docstring stating its purpose *and its rationale* - why it is
  separate from its neighbours. This is the dominant documentation style here; match it. The
  cross-module map that individual docstrings cannot provide lives in
  `src/awesome_templates/CLAUDE.md`, which loads automatically when working in that directory.
- Threading, not globals: `Workspace`, `warnings: list[str]`, and `log: LogHelper` are all
  passed as parameters. Do not introduce module-level state.
- Testability at the boundary: `resolver.py` takes a `client`, `headless.py` takes a `run=`.
  Preserve that pattern when adding anything that reaches outside the process.
- Conventional Commits. Never push directly to `master`.

## Tests

The suite is flat under `tests/` - there is **no** `tests/unit/` directory, so any instruction
mentioning one is stale. `tests/conftest.py` provides two fixtures: `fixture_workspace` builds
two tiny synthetic presets ("demo" and "other") under `tmp_path` for most unit tests, and
`real_workspace` points at this repo's actual `templates/`.

`tests/test_integration_real_repo.py` is the load-bearing file: it generates each real preset
and asserts zero dangling `@docs/` references, no links outside the preset's own tree, no
unresolved placeholders when generating from the example config, and that the generated agent
docs list every real agent file. Changes to `templates/` should run it even when no Python
changed.

## Design documents

This repo has **no `docs/adr/` directory** - `docs/adr/` exists only inside the presets it
distributes. Design rationale lives in `docs/roadmap/{NNNN}-{slug}/`, in two shapes:
`0001-ai-assisted-generation/` is a set of numbered documents named
`{NN}.{Title_With_Underscores}.md`, while `0002-api-based-marker-research/` uses a `plan.md` +
`status.md` pair. A rejected alternative is preserved as its own deferred milestone rather
than deleted - milestone `0002` exists solely to keep the in-house research-harness design
buildable should the `claude`-CLI dependency ever become unacceptable. Cite these as
`path#heading-slug`, never the file alone.

The root `AGENTS.md` is a near-duplicate of an older revision of this file; prefer `CLAUDE.md`
where they differ.
