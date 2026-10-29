# Model upgrade matrix

Which model `awesome-templates upgrade` moves an outdated agent pin to, by **agent role** and
**vendor**. The source of truth is
[`models.template.json`](../src/awesome_templates/data/models.template.json) (seed of the per-user
`~/.local/state/awesome/models.json`, see `awesome-templates init`); the table below is generated from it
and must stay equal to it.

```bash
uv run awesome-templates model-matrix            # print the table
uv run awesome-templates model-matrix --write    # refresh the block below after editing the template
uv run awesome-templates model-matrix --check    # exit 1 on drift (the test suite runs this too)
```

## How a model is chosen

A role is an agent's file stem (`cpp-expert.md` -> `cpp-expert`). It resolves in this order, per vendor:

1. `upgrade.<vendor>.roles` - an explicit override for that role, if any.
2. `upgrade.<vendor>.tiers` at the role's tier from `roles` (`deep` = flagship work such as design,
   security and hard-domain implementation; `standard` = review, documentation, verification;
   `light` = mechanical work, unused so far).
3. For an agent that is not a known role (a project's own): the old model's family, then the vendor
   `default` - shown on the last row.

The flagship model is deliberately not the answer for everything: `cpp-expert` goes to the vendor's
top tier, `docs-updater` to its cheaper one. Only a pin that is **outdated** is rewritten; a pin
already in `recommended` is left alone even if a different tier would now be chosen for the role.

Adding a new agent role means adding it to `roles` in the template; a test fails until you do. Copilot's
`GPT-6.1 Sol` and `GPT-6 Luna` are the display names from GitHub's supported-models page; the runtime IDs are not documented, so verify the exact string in the Copilot CLI.

## Matrix

<!-- model-matrix:begin (generated from models.template.json; run `awesome-templates model-matrix --write`) -->
| Role | Tier | anthropic | copilot |
| --- | --- | --- | --- |
| `agent-orchestrator` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `android-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `app-architect` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `appkit-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `background-reviewer` | standard | `claude-sonnet-5-5` | `GPT-6 Luna` |
| `boost-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `cpp-code-documenter` | standard | `claude-sonnet-5-5` | `GPT-6 Luna` |
| `cpp-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `django-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `docs-updater` | standard | `claude-sonnet-5-5` | `GPT-6 Luna` |
| `docs-writer` | standard | `claude-sonnet-5-5` | `GPT-6 Luna` |
| `feature-reviewer` | standard | `claude-sonnet-5-5` | `GPT-6 Luna` |
| `frontend-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `incident-analyst` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `java-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `javascript-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `ml-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `python-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `qt-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `react-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `release-engineer` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `scraping-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `security-auditor` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `spring-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `swift-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `swiftdata-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `swiftui-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `task-verifier` | standard | `claude-sonnet-5-5` | `GPT-6 Luna` |
| `test-documenter` | standard | `claude-sonnet-5-5` | `GPT-6 Luna` |
| `testing-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `typescript-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `vite-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| `vue-expert` | deep | `claude-opus-5-5` | `GPT-6.1 Sol` |
| *any other role* | - | `claude-opus-5-5` | `GPT-6 Luna` |
<!-- model-matrix:end -->
