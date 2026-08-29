# Awesome Templates

The goal of the project is to create easily deployable sets of Claude Code agents, skills, hooks, loops obtained from the set of templates with easily substituted values.

The idea is as follows:

Replace explicit project name and other project-specific values in files with a template that is easy to misrepresent in Markdown, e.g. `{{PROJECT_NAME}}`, `{{PROJECT_PURPOSE}}` and so on.
After this step, with simple replacement artifacts can be added to another Python project.

Each preset is a complete, self-contained tree, shaped exactly like what lands in the target project:

```
templates/python/.claude
templates/python/docs
templates/python/scripts
templates/java/.claude
templates/java/docs
templates/java/scripts
```

`.claude/` contains

```
agents
hooks
loops
skills
settings.json
```

Generating a preset is a plain recursive copy of `templates/<preset>/` into the target project's root,
with `{{PLACEHOLDER}}` substitution applied to every text file. `.claude/`, `docs/`, and `scripts/`
always land together, from the same source tree, so agents and scripts cannot reference template
content that was not generated.

1. Markdown files contain multiple document links. Rather than introducing templates, create `MIGRATION_REPORT.md` per each entity with all document references. Perhaps will be introduced templates for documents, or special documents conventions across projects, e.g. `docs/adr` and `docs/roadmap`. The following design will be the subject of further design steps

2. Analyze any project or technology-dependent entities aside from names and links and provide then in each `MIGRATION_REPORT.md`

This would be the gate for the next design round or the first implementation round.

## Usage

The generator lives in `src/awesome_templates` and installs as the `awesome-templates` console script via `uv`.

Setup and test the application works

```bash
# One-time setup - creates .venv and uv.lock
uv sync

# See every preset and what it contains (including any specializations each one offers)
uv run awesome-templates list

# Full suite, if you want to confirm nothing else broke
uv run pytest --cov=awesome_templates
```

Possible CLI option sets for preset deployment from templates

```bash
# Generate a generic Python preset
uv run awesome-templates generate . --preset python --name "Acme Sync" --package acme_sync

# Layer a specialization's agents/skills on top of the preset (repeatable)
uv run awesome-templates generate . --preset python --name "Acme Sync" --specialization django

# Plain preview, no specialization (originally into /tmp; now into the in-project .scratch/)
uv run awesome-templates generate . --preset python --name "Awesome Templates" --package awesome_templates --output-dir .scratch/plain

# Preview with a specialization layered on top - verifies it merges into .claude/, no stray top-level folder
uv run awesome-templates generate . --preset python --name "Awesome Templates" --package awesome_templates --output-dir .scratch/django --specialization django

# Full AI-resolution pass: markers, tutorial.md, test-conventions paragraph (needs ANTHROPIC_API_KEY; makes real, billed API calls), debug logging
uv run awesome-templates generate . --preset python --name "Awesome Templates" --package awesome_templates --output-dir .scratch/resolved --resolve-markers --json --log-severity debug

# Targeted regression tests for the specialization-copy bug
uv run pytest tests/test_specializations.py tests/test_integration_real_repo.py -q
```

A few things worth knowing before you run these yourself:

* `--output-dir .scratch/...` works because `.scratch/` is now in `.gitignore` - anything you generate there won't show up in the git status clutter.
* Add `--specialization <name>` more than once to layer several (awesome-templates list shows valid choices per preset - `django`, `ml-ai`, `webscraping` for python; `spring`, `android` for java).
* Command 3 costs real API usage every time you run it - each `<!-- TEMPLATE-INIT -->/<!-- SME REVIEW NEEDED -->` marker, plus the calls are `tutorial/test-conventions` a separate request. Skip `--resolve-markers` if you just want to inspect the deterministic output.
* Rerunning any of these into an existing `.scratch/{name}` will fail unless you also pass `--force` (or delete the directory first) - generate refuses to overwrite non-empty output by default.
* `generate` also accepts `--config-file {file.json|file.toml}` (any flag passed alongside overrides the matching config value), `--output-dir <path>` (defaults to `TARGET_DIR`), and `--dry-run --json` for a machine-readable preview. `TARGET_DIR` is the project root analyzed by marker resolution, and generation writes `.claude/`, `docs/`, and `scripts/` under `--output-dir` (or `TARGET_DIR` when omitted). Pass `--force` to overwrite existing content in any of them. `--specialization {name}` is repeatable and passing it at all replaces a config file's `specializations` list wholesale rather than merging with it. Run `uv run awesome-templates generate --help` for the full flag reference.

### Config file

[`awesome-templates.example.toml`](awesome-templates.example.toml) is a documented example of the file
`--config-file` accepts - copy it into your own project, edit the values, and run:

```bash
uv run awesome-templates generate . --config-file awesome-templates.example.toml
```

JSON works the same way (picked by file extension); the schema is the same shape either way:

```json
{
  "preset": "python",
  "out": ".",
  "force": false,
  "specializations": ["django"],
  "project": {
    "name": "Acme Sync",
    "package": "acme_sync",
    "purpose": "Synchronizes Acme customer records nightly.",
    "slug_upper": "ACME_SYNC"
  }
}
```

| Field                | Substitutes              | Default if omitted                                     |
|----------------------|--------------------------|--------------------------------------------------------|
| `preset`             | -                        | none - required (or pass `--preset`)                   |
| `out`                | -                        | `TARGET_DIR`                                           |
| `force`              | -                        | `false`                                                |
| `specializations`    | -                        | `[]` - see `uv run awesome-templates list` for choices |
| `project.name`       | `{{PROJECT_NAME}}`       | none - required (or pass `--name`)                     |
| `project.package`    | `{{PROJECT_PACKAGE}}`    | slugified `project.name`                               |
| `project.purpose`    | `{{PROJECT_PURPOSE}}`    | a `TODO: describe what this project does` placeholder  |
| `project.slug_upper` | `{{PROJECT_SLUG_UPPER}}` | upper-slugified `project.name`                         |
| `resolve_markers`    | -                        | `false` (or pass `--resolve-markers`)                  |

Any CLI flag passed alongside `--config-file` overrides the matching value from the file.

### Resolving `TEMPLATE-INIT` markers with AI

`{{PLACEHOLDER}}` substitution fills the deterministic gaps. Some agent and loop files carry a second
kind: `<!-- TEMPLATE-INIT: <instruction> -->` markers describing a project-specific fact no find/replace
can supply. Pass `--resolve-markers` (or `resolve_markers = true` in the config) to have `generate`
resolve every such marker across the generated Markdown by calling Anthropic against the target
project's own code and docs - writing grounded prose, or a visible `> **TODO (fill in ...)**` blockquote
when it can't answer confidently.

This is opt-in: plain `generate` stays fully offline. It needs the optional `ai` extra and an API key:

```bash
uv pip install 'awesome-templates[ai]'    # pulls in the anthropic SDK
export ANTHROPIC_API_KEY=sk-ant-...       # or put it in a .env in the cwd
uv run awesome-templates generate . --config-file awesome-templates.toml --resolve-markers
```

`--dry-run` reports how many markers *would* be resolved without calling the API.

### Development

Test suite and lint

```bash
uv run pytest --cov=awesome_templates
uv run ruff check src/ tests/
```
