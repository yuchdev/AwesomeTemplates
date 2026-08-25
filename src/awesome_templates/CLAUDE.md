# Generator source (`src/awesome-templates`)

Loaded only when working under `src/awesome-templates/` — migrated out of the root `CLAUDE.md`
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
  every other template file (via `templating.py`). This is the entire generation mechanism for the
  preset itself — there is no per-entity loop, no selection to resolve. The one addition on top is
  layering zero or more selected specializations' `.claude/` trees into the same destination after
  the base copy, raising `ValueError` on an entity-name collision (an authoring bug in `templates/`,
  not a runtime condition to warn-and-skip — see `specializations.py`).
- `specializations.py` — discovery for the opt-in specialization layer: `list_specializations`
  finds every `templates/<preset>/specializations/<name>/` that has a usable `.claude/agents/` or
  `.claude/skills/` entry, reusing `catalog.discover` rather than a second directory walk (a
  specialization directory is exactly the same "kind dirs nested one level under `.claude/`" shape a
  preset directory already is). `disallowed_kinds_present` flags a specialization that ships a
  `hooks/`, `loops/`, or `settings.json` it isn't allowed to — those need wiring only the base
  preset's own `settings.json` owns, so a specialization hook would be dead on arrival.
- `docgen.py` — deterministic, no-network doc generation that runs on every `generate` unconditionally
  (no `--resolve-markers`, no `ai` extra): globs the generated tree's own `.claude/agents`, `skills`,
  and `settings.json`-wired `hooks`, and renders `docs/agent/{agents,skills,hooks}.md` from what's
  actually on disk, plus `list_test_files`/`render_test_layout_section`/`write_test_layout_doc`, which
  append an "Actual Test Layout" section to `docs/test/code_test_coverage.md`. Runs after any
  specialization layer has already been merged in, so specialization-provided agents/skills appear in
  the same listing for free. A pre-existing custom `# ...` heading in `docs/agent/*.md` is preserved
  across regeneration; the test-layout section is replaced in place by its own heading instead. Never
  imports `anthropic` (pinned by
  `tests/test_markers.py::test_docgen_import_does_not_pull_anthropic`) even though `resolver.py`
  imports *it* to reuse `list_agents`/`list_skills`/`list_test_files` rather than re-deriving them.
- `templating.py` — the substitution engine: a flat regex find/replace over the small fixed placeholder
  glossary, with an "unresolved placeholder left in <path>" warning rather than a hard failure.
- `log_helper.py` — `LogSeverity` (error/warning/info/debug) and `LogHelper`, a leveled console tracer
  for `generate`'s own pipeline, built once in `cli.py` from `--log-severity` and threaded as an
  optional `log=` keyword through `copy_preset`/`docgen.write_agent_docs`/`docgen.write_test_layout_doc`/
  `resolver.resolve_tree`/`resolver.maybe_write_tutorial`/`resolver.seed_first_milestone`/
  `resolver.maybe_describe_test_conventions` - the same threading style `warnings: list[str]` already
  uses everywhere. Every function defaults `log` to `NULL_LOG` (a no-op stand-in), so omitting it never
  changes behavior - existing direct calls in tests are unaffected. Writes to stderr, not stdout, so
  `generate --json --log-severity debug` still emits parseable JSON. Separate from `graph`'s own
  `--log-verbosity {info,debug}` flag in `cli.py`, which predates this module and only narrates
  `graph`'s own phases - not unified with it.
- `dependencies.py` — a maintainer-only tool for *this* repo's own catalog, not part of the `generate`
  flow: scans every entity's content for whole-word mentions of every other entity's name, builds a
  graph, and can render it as Mermaid/Markdown (`awesome-templates graph`), or upsert a per-file
  "Dependencies" block directly into `templates/**` (`--inline`), or remove them (`--remove`). Point
  `graph` at a single preset directory (or an already-generated project) to see that tree's own
  `.claude` <-> `docs` connectivity; both mutating flags edit the template tree in place — review
  `git diff` before committing.
- `markers.py` / `resolver.py` / `ai/client.py` — the `generate --resolve-markers` feature, split by
  concern: `markers.py` is the pure scan/splice of `<!-- KIND: ... -->` comments (no network) - it
  recognizes two kinds via `MARKER_KINDS`, `TEMPLATE-INIT` and `SME REVIEW NEEDED`, carried on
  `Marker.kind`; `resolver.py` is the business logic that decides what each marker should say (prompts,
  the target-project context bundle, the confident/TODO fallback for `TEMPLATE-INIT`, and an
  always-flagged-as-unreviewed draft for `SME REVIEW NEEDED` regardless of confidence - see
  `ResolveSummary.human_review`); `ai/client.py` is the only module allowed to import `anthropic`, and
  only lazily inside its functions — it just places one Messages API request and returns parsed JSON.
  `resolver.py` never touches the SDK directly, so every one of its model-calling functions takes a
  `client` parameter and is unit-tested against a fake one (`tests/test_resolver.py`). Beyond marker
  resolution, the same `--resolve-markers` call also drives three more AI-authored increments, each
  with its own idempotency guard so a repeat run never clobbers a user's edits or duplicates content:
  `maybe_write_tutorial` (drafts `docs/agent/tutorial.md`, skipped once it's no longer the shipped
  stub), `maybe_describe_test_conventions` (appends one paragraph to `docs/test/code_test_coverage.md`
  from test file *names* only, never contents, skipped once a sentinel comment shows it already ran),
  and `seed_first_milestone` + `propose_first_milestone` + `render_milestone` (only under the separate
  `--seed-roadmap` flag, since it deletes example content: replaces
  `docs/roadmap/0001-working-implementation/`'s illustrative milestone in place, skipped once
  `plan.md`'s own "replace this milestone" sentinel sentence is gone). `cli.py`'s `--resolve-markers`
  branch imports `resolver` (and `ai.client`, to build one client instance shared across all of these
  calls) lazily too, so the offline `generate` path stays free of the `ai` extra (pinned by
  `tests/test_markers.py::test_cli_import_does_not_pull_anthropic`).
- `headless.py` — the agentic half of `--resolve-markers` (design:
  `docs/roadmap/0001-ai-assisted-generation/03.Agentic_marker_research.md`): when the `claude` CLI is
  installed, runs ONE headless Claude Code session (`claude -p --bare`, tools hard-allowlisted to
  Read/Grep/Glob/Edit/TodoWrite, `+Write` only under `--update-guidelines`) over the whole marker
  manifest rendered from `markers.scan_tree`, with cwd set to `detect_project_root`'s answer (out_dir
  when it holds a real project, else the `generate` invocation's cwd — the generate-into-a-scratch-dir
  case). Results are reconciled by a before/after `scan_tree` diff plus TODO/SME-draft pattern counts,
  never the model's self-report, into the same `ResolveSummary` shape `resolver.resolve_tree` returns.
  The research method/rules are a deliberate re-embed of `.claude/agents/create-from-template.md` (a
  pip-installed package can't read that file at runtime) — keep the two aligned. Takes `run=`
  (defaulting to `subprocess.run`) so `tests/test_headless.py` asserts on argv/prompt and simulates
  session edits with no real CLI. `resolver.resolve_tree` stays as the warned fallback when `claude`
  isn't on `PATH`; the tutorial/roadmap/test-conventions increments stay on the one-shot API path.
- `cli.py` — Typer app; command tree is `list`, `graph`, `generate`. Each `generate` flag has a
  config-file fallback (`--config file.json|.toml`) merged before CLI flags, which always win. The
  repeatable `--specialization` flag is the one list-valued exception to "flag wins": passing it at
  all replaces the config file's `specializations` list wholesale rather than merging with it.
  `--seed-roadmap` is rejected unless `--resolve-markers` is also set — it shares that flag's API key
  and project context rather than owning its own. `--log-severity` builds one `LogHelper` (see
  `log_helper.py`) shared across the whole `generate` call, defaulting to `warning` so output is
  unchanged unless a caller opts into `info`/`debug`.

No `Selection`/category-composition layer exists anymore (the `selection.py`, `settings.py`, and
`requirements.py` modules were removed along with it) — a preset has nothing to select, compose, or
warn about missing target-project requirements for; it is what it is. `specializations.py` is not a
reintroduction of that layer: it composes *beside* a preset (add-on agents/skills merged in after
the preset is copied whole), never selects pieces *out of* one.
