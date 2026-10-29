# Model migration - preset agents - 2026-10-29

**Scope:** every `templates/*/.claude/agents/*.md` - 59 files across `common`, `cpp`,
`frontend`, `java`, `macos`, `python`. Each was reviewed against the behaviour of the target
models (Claude Opus 5.5, Claude Sonnet 5.5). This is a **content** review (`templates/` is
distributed Markdown, not generator code), so the checks are authoring checks, not code tests.

**Not in scope** (matched neither the glob nor the request, listed under
[Left unchanged](#left-unchanged-out-of-scope) so nothing is silently skipped):
`templates/*/specializations/*/.claude/agents/`, the repo-root `.claude/agents/`, and
`src/awesome_templates/`.

## Model mapping

| Old                 | New                 | Agents | Price per MTok in/out | Change |
|---------------------|---------------------|-------:|-----------------------|--------|
| `claude-opus-4-8`   | `claude-opus-5-5`   |     32 | $5 / $25 -> $4 / $20  | -20%   |
| `claude-sonnet-4-6` | `claude-sonnet-5-5` |     27 | $3 / $15 -> $2 / $10  | -33%   |

Tiers were **preserved**, not re-decided: every agent moved to the current model of the same
tier, so the fleet's cost/quality shape is unchanged and cheaper per token.

*Considered and not chosen:* Claude Fable 5.1 (`claude-fable-5-1`) is more capable but costs
$10 / $50, requires 30-day data retention (400s under zero-data-retention orgs), and has a
different API surface. That is a poor default for templates distributed into other people's
projects. An individual agent such as `security-auditor` can opt in later; it is a one-line change.

## Compatibility with the new models

The agent files are Markdown with `name`, `description`, `model`, `tools`, `allowed-tools`
frontmatter. None sets `thinking`, `tool_choice`, `temperature`, `top_p`, `budget_tokens`, or an
assistant prefill (verified by grep), so none of the new models' request-level breaking changes
apply (thinking cannot be disabled, forced tool use returns 400, sampling parameters are rejected).
No agent asks the model to write out its reasoning, so the `reasoning_extraction` safeguard is
not triggered by any prompt text.

## Findings

| Severity | Finding | Evidence | Action |
|----------|---------|----------|--------|
| MEDIUM | Orchestrator "Model" column contradicts the agent's own frontmatter: `testing-expert` listed `sonnet` but is `opus` in 4 of 5 presets (only `java` was consistent). | `agent-orchestrator.md:26` (cpp, frontend, python), `:29` (macos) | **Fixed** - column now matches frontmatter |
| MEDIUM | Leaked foreign-project content in the Java preset: hard-coded "Verity" and a goal/proof/streak/reward domain instead of `{{PROJECT_NAME}}` and neutral examples. | `java/.../java-expert.md:3,12,48-53,65-69,83,132`; `java/.../testing-expert.md:3,9-11,42,58-76` | **Not fixed** - not model-related, needs an authoring decision (see actions) |
| LOW | `python-expert` baseline step offered two identical alternatives: ``uv run pytest -q` or `uv run pytest -q``. | `python/.../python-expert.md:32-33` (before edit) | **Fixed** -> `` `uv run pytest -q` (or `pytest -q` outside a uv project) `` |
| LOW | `python-expert` carried a "Coding Standard" subsection that says it is "already read in step 2 above", and a vague step 4 ("Adapt Solutions: ... integrate seamlessly") that step 3 already covers. | `python/.../python-expert.md:31,37-40` (before edit) | **Fixed** - removed, steps renumbered |
| LOW | `python-expert` Patterns listed textbook language features and GoF patterns with no project decision in them. | Factory, Strategy, Observer, Async Context Managers, Async Generators, Protocol Classes, Context Managers (explaining `__enter__`/`__exit__`), Sentinel Values, Explicit over Implicit | **Fixed** - 9 bullets removed; project-specific ones kept (Domain Models, Repository, Service Layer, DI, Result/Either, Immutability, thin handlers) |
| LOW | `testing-expert` "Continuous Testing" subsection is generic (CI/CD, fast feedback, reporting, fail-fast) with no project content; byte-identical in four presets. | `cpp`, `frontend`, `macos`, `python` `testing-expert.md` | **Fixed** - removed, next heading renumbered |
| LOW | Orchestrator roster claims "every one of these agents is present" but omits `incident-analyst` and `test-documenter`. | all 5 `agent-orchestrator.md` | Not fixed (not model-related) |
| INFO | Wording "say so loudly" in `feature-reviewer` is mild pressure language; "say so explicitly" does the same job. | `*/.claude/agents/feature-reviewer.md` | Not fixed (low confidence) |

## What was reviewed and deliberately kept

The review standard was: remove text only if the model already does it unprompted *and* the
text carries no project decision. Cutting for length alone was not a goal.

- **Pressure language / thinking steering / word caps / fossils:** a signal scan over all 59
  files found none. The only `CRITICAL` hits are the severity enum and the BLOCK rule in
  `security-auditor`/`agent-orchestrator`, which encode a real merge gate.
- **Output formats and verdict rules** (`feature-reviewer`, `security-auditor`,
  `task-verifier`, `background-reviewer`): contract text the downstream hooks and humans rely on.
- **Traceability tables, Test Contract, "Never weaken a test", Verification Honesty:** these
  counter *overclaiming*. The new models are measurably better at it, but the tables are a
  deliverable format, and Sonnet 5.5 at low effort can still report code as done without running a
  check, so the honesty rules stay. `test-documenter` has an explicit Verification Honesty
  section and `docs-updater` ends with a link-check checklist; I did not audit every Sonnet
  agent for an equivalent.
- **macOS experts** (`swift-expert`, `swiftdata-expert`, `release-engineer`, `cpp-expert`):
  migration data-loss rules, entitlement limits, and the Swift/C++ boundary are hard-won context
  that only the author knows. Kept in full.
- **`testing-expert` "Key Principles" in cpp/frontend/macos:** mixes generic bullets with real
  preset knowledge (`getByRole` over CSS selectors, no `waitForTimeout`, "Valgrind does not
  support current macOS"). Only the fully generic subsection was removed.
- **Frontend design defaults:** Opus 5.5 tends to fall back on a few default styles, and the
  documented fix is to name specific patterns to avoid. `frontend-expert` contains no aesthetic
  direction (only engineering and accessibility rules), so nothing was added. Imposing a style ban
  on every downstream project would be the wrong default.
- **Visual-input scaffolding:** none present, so nothing to remove.

## Left unchanged (out of scope)

| Item | Count / location | Why it matters |
|------|------------------|----------------|
| Specialization agents still on `claude-opus-4-8` | 16 files under `templates/*/specializations/*/.claude/agents/` | A project generated with `--specialization` gets a **mixed fleet** (core agents on 5.5, specialists on 4.8) |
| Repo-root `.claude/agents/` | 12 files on old IDs; `create-from-template.md` is on `claude-opus-5` | Maintainer tooling; distributed to nobody |
| `src/awesome_templates/resolver.py:44` | `MODEL = "claude-opus-4-8"` | Direct-API code unreachable from `generate` (see CLAUDE.md); `ai/client.py:53` docstring repeats the ID |
| `docs/agent/agents.md` | lists old IDs for the root agents | Generated by `docgen`; refreshes on the next `generate` |
| `tests/test_docgen.py` | `claude-opus-4-8` in fixtures | Synthetic frontmatter, deliberately arbitrary; harmless |

## Verification

- `uv run pytest -q` -> **314 passed, 4 skipped**, including `tests/test_integration_real_repo.py`
  (generates each real preset; asserts no dangling `@docs/` refs and no unresolved placeholders).
- 0 occurrences of `claude-opus-4-*` / `claude-sonnet-4-*` remain in the 59 in-scope files.
- Orchestrator model column re-checked against every agent's frontmatter in all 5 presets: no drift.
- Diff: 59 files; 50 are the one-line `model:` bump only, 9 also carry the prose edits above.
- Not verified: behaviour of the new models *running* these agents. This was a read-through, not
  an eval; no agent was executed against Opus 5.5 / Sonnet 5.5.

## Verdict

No CRITICAL or HIGH findings. Safe to merge as is, with the caveat that the fleet is mixed until
the specializations are bumped.

## Recommended actions

1. **Bump the 16 specialization agents** to the same IDs
   (`sed -i '' -e 's/^model: claude-opus-4-8$/model: claude-opus-5-5/'` on those files) so a
   specialized project is not a mixed fleet. Same for the root `.claude/agents/` if desired.
   `uv run awesome-templates check-models` now lists exactly these 16 (policy added after this
   review: `[tool.awesome_templates.model_policy]` in `pyproject.toml`, currently `mode = "warn"`;
   `check-models --live` / `pytest --live-models` additionally verify each ID against the vendor's Models API).
   Once they are bumped, switch the mode to `"error"` so a stale pin can no longer ship.
2. **Fix the Java leak:** replace "Verity" with `{{PROJECT_NAME}}` and swap the goal/proof/streak
   examples for neutral ones in `java-expert.md` and `testing-expert.md`. Then add an integration
   test asserting no preset agent contains a hard-coded project name, because the existing
   "no leftovers" checks only catch unresolved `{{...}}` tokens.
3. **Decide the `testing-expert` tier.** The table said Sonnet, the frontmatter said Opus;
   this change trusts the frontmatter (the behaviour-bearing field). `java` is Sonnet. With
   Sonnet 5.5 stronger at agentic coding, Sonnet may now suffice for the other presets too, and
   the choice is a cost call for the maintainer.
4. **Add `incident-analyst` and `test-documenter` to the orchestrator roster tables**, or reword
   the "every one of these agents is present" claim.
5. **Consider an `effort` setting per agent.** Opus 5.5 defaults to `medium`, and thinking can no
   longer be disabled, so effort is the only depth control. These agents set none. I have not
   verified that Claude Code's agent frontmatter accepts an `effort` key, so confirm before
   adding it, and check that `docgen`'s frontmatter parser tolerates it.
6. **Watch item:** Opus 5.5 and Sonnet 5.5 ship cyber safety classifiers. Finding vulnerabilities
   in source is allowed, but `security-auditor` and `background-reviewer` do dual-use-adjacent
   work, so a false-positive `refusal` is possible and would look like a silent stop.
