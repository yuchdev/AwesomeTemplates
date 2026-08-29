# Improvement Proposals

**Status:** proposal - not implemented. This is an intake document, not a milestone: each
item below is written with enough detail (problem, evidence, proposed approach, size,
dependencies) to be lifted directly into a `docs/roadmap/{NNNN}-{milestone-slug}/plan.md`
once the maintainer decides which to schedule and in what order. Sizes are rough:
**S** = a single focused PR, **M** = a few PRs / one task with subtasks, **L** = milestone-
sized, likely several tasks.

Hallucination detection/prevention is **out of scope here** - that is
[hallucination-mitigation.md](hallucination-mitigation.md) and its two subarticles, already
proposed separately. Everything below was found by directly reading the current code and
docs (not proposed from memory or general best-practice); every file:line citation was
re-verified against the working tree before writing this document, not just taken from
first-pass notes.

## How to read this document

Groups are ordered by a rough "fix this before that becomes expensive" logic, not by
importance - Group A (doc hygiene) is cheap and unblocks trusting citations in every other
group; Group B (a real correctness bug) is small but arguably the highest-priority single
item on this list, since it means a shipped feature silently doesn't do what its own tests
imply. Read groups independently; nothing here requires adopting the whole list.

## Group A - Documentation hygiene

These are bugs in this repo's *own* maintainer docs, not in `templates/` content. Fixing
them is cheap and load-bearing: several citations elsewhere in this repo (including in this
document) depend on the roadmap index being accurate.

### A1. `docs/roadmap/README.md`'s milestone index is broken in two independent ways

**Problem:** The index table lists three milestones - `0001`, `0002`, `0003` - but the
directory tree contains only two: `0001-ai-assisted-generation/` and
`0003-api-based-marker-research/`.

- **Phantom milestone:** row `0002` links to
  `/docs/roadmap/0002-alternative-harness-support/plan.md` and `status.md` - this directory
  does not exist on disk at all.
- **Missing files for a real milestone:** row `0001` links to
  `/docs/roadmap/0001-ai-assisted-generation/plan.md` and `status.md` - neither file exists;
  `0001-ai-assisted-generation/` contains only a `01.0-working-implementation/` subfolder
  with three numbered docs, not the `plan.md`/`status.md` pair the index promises and the
  convention section of the same README documents as the expected shape.

**Why it matters:** `scripts/check_doc_links.py` already reports these exact two dangling
links every time it scans the whole corpus (confirmed by running it directly), so this is a
standing, known-but-unfixed finding, not a hypothetical. A roadmap index that cites
nonexistent milestones and missing files undermines every other doc's citation discipline
this repo otherwise takes seriously (`CLAUDE.md`, "Cite these as `path#heading-slug`, never
the file alone").

**Proposed approach:** either (a) write the missing `0001-ai-assisted-generation/plan.md` +
`status.md` retroactively, summarizing the milestone the `01.0-working-implementation/` docs
already describe, and delete the phantom `0002` row (folding any real "alternative headless
harness support" intent into a freshly-numbered future milestone if still wanted), or (b) if
`0001` was always meant to stay in the `01.0-working-implementation/`-only shape, update the
README's own convention section to document that as a legitimate third shape alongside the
two it already lists (`CLAUDE.md` already accepts this via its own note: "`0002-api-based-
marker-research` uses a `plan.md` + `status.md` pair" - implying at least one milestone is
allowed to differ in shape from another). Either way, remove the `0002` phantom row or
replace it with a real, intentionally-empty placeholder milestone the way `0003` itself
started.

**Size:** S. **Depends on:** nothing - do this first, since later groups below cite roadmap
paths and should cite the corrected index.

### A2. `docs/test/code_test_coverage.md` contradicts `CLAUDE.md`'s explicit invariant

**Problem:** This doc states "This project requires **85% test coverage** on all code,"
describes tests failing automatically below that threshold, an `.htmlcov/` report, and
coverage failures "block merging to main branches." `CLAUDE.md` states the opposite as fact:
"There is no `.github/` and no CI. There is no coverage floor (`pyproject.toml` sets no
`fail_under`, no `addopts`, only `testpaths = ["tests"]`)."

**Why it matters:** this is a stale/aspirational doc masquerading as current policy - a
contributor (or an AI agent, including a `testing-expert` run) reading only
`docs/test/code_test_coverage.md` would enforce a gate that provably does not exist, wasting
effort or blocking work on a phantom requirement.

**Proposed approach:** rewrite the doc to state the actual current policy (report coverage
deltas, no enforced floor - per `CLAUDE.md`), or, if an 85% floor is actually wanted, land it
for real (`pyproject.toml`'s `[tool.pytest.ini_options]` `addopts = ["--cov-fail-under=85"]`
or equivalent) and update `CLAUDE.md` to match - but the two documents must agree either way.

**Size:** S. **Depends on:** a maintainer decision on which direction is authoritative.

### A3. `docs/dev/python_language_rules.md` carries a stale placeholder TODO

**Problem:** Line 32 is a bare `<!-- TODO: describe ruff, mypy, Flake8 -->`. Per `markers.py`'s
own docstring, a bare `<!-- TODO: ... -->` is "an ordinary authoring TODO... not a
project-specific fact only a target-project read could answer" - i.e. this is squarely a
human (or `docs-writer`) authoring task, not something `--resolve-markers` will ever touch.

**Why it matters:** small, but it's a real content gap in a doc that's presumably read by
contributors trying to understand this repo's own lint stack - doubly relevant since Group C
below documents that stack has real inconsistencies worth writing up accurately once fixed.

**Size:** S. **Depends on:** ideally sequenced *after* Group C, so the description written
here is of the corrected lint stack, not the current inconsistent one.

## Group B - A real correctness bug: the flake8 plugin cannot be discovered by real flake8

**Problem:** `src/flake8_project_rules/` implements `ProjectRulesPlugin` (`plugin.py`), but
`pyproject.toml` has no `[project.entry-points."flake8.extension"]` (or equivalent) group
registering it - confirmed by grepping `pyproject.toml` for any entry-points declaration and
finding none. Flake8 discovers third-party checks exclusively through that entry-point
mechanism; without it, installing this package and running `flake8` does not run `X001`-`X012`
at all. The plugin currently only executes through direct calls to `check_tree()`/`check_file()`
inside `tests/flake8_lint/` - which is also why this went unnoticed: the tests exercise the
rule *logic* without ever exercising *discoverability*.

**Compounding evidence this is a live problem, not theoretical:**

- `pyproject.toml`'s `[tool.flake8_lint_tests]` `select` list stops at `X011` - `X012`
  (`Type1 | Type2` -> `Union[...]`, the newest rule) is in neither this select list nor any
  test file (`grep -rl X012 tests/` returns nothing). A rule with zero enforcement anywhere.
- `[tool.flake8_lint_tests] include` scopes checking to exactly one fixture file
  (`tests/flake8_lint/samples/valid_clean_module.py`) - the plugin has never actually been
  run against this repo's own `src/` or `templates/**` content, real or synthetic.
- `log_helper.py:62` (`console: Console | None = None`) uses PEP 604 union syntax - a direct
  `X011` violation, in this repo's *own* generator code, that nothing currently catches,
  because nothing runs `X011` against `src/` for real.

**Why it matters:** this is the single highest-priority item in this document by a wide
margin, precisely because it's small to fix and currently silently broken - every commit
since the plugin was introduced has shipped believing `X001`-`X012` gate the codebase, when
in fact they gate nothing outside one fixture file and one direct-call test harness.

**Proposed approach:**

1. Add the entry-points group to `pyproject.toml` so real `flake8 src/ tests/` picks up the
   plugin (a `[project.entry-points."flake8.extension"] X = "flake8_project_rules.plugin:ProjectRulesPlugin"`
   -shaped declaration, per flake8's plugin discovery contract).
2. Run `flake8 src/ tests/` for real once wired, fix what it finds (starting with the known
   `log_helper.py:62` `X011` violation), and decide per-violation whether to fix the code or
   add a `# noqa` with a rationale comment (the suppression mechanism already exists and is
   tested).
3. Add `X012` to `[tool.flake8_lint_tests] select` and give it the same fixture/edge-case
   coverage `X001`-`X011` already have (folds naturally into Group E's test-hardening work).

**Size:** S for the entry-point wiring itself; M once "fix everything it newly finds in
`src/`/`tests/`" is included. **Depends on:** nothing technically, but do Group C's
`ruff.toml`/`pyproject.toml` reconciliation alongside it - both are "the lint config doesn't
say what actually runs" bugs and are cheaper to reason about together.

## Group C - Developer tooling & dependency hygiene

### C1. `ruff.toml` / `pyproject.toml` disagreement (already flagged in `CLAUDE.md`, not yet resolved)

**Problem:** `CLAUDE.md` itself documents this: `ruff.toml` and `pyproject.toml`'s
`[tool.ruff]` disagree on `line-length` (120 vs 100) and `target-version` (py312 vs py311),
and `ruff.toml` wins. This means any tool or editor integration that reads `pyproject.toml`
alone (common for IDE ruff integrations that don't know to check for a sibling `ruff.toml`)
enforces a different standard than `ruff check` on the command line actually applies.

**Proposed approach:** delete one of the two config sources and keep the other as the single
source of truth (deleting `pyproject.toml`'s `[tool.ruff]` section is the lower-risk
direction, since `ruff.toml` is what's documented as authoritative today) - or, if both must
exist for tooling reasons, make them textually identical for the overlapping keys and add a
one-line comment in each pointing at the other, so a future edit to one is a visible prompt
to check the other.

**Size:** S. **Depends on:** nothing.

### C2. No static type checker

**Problem:** the codebase has heavy, disciplined typing (`Optional[T]`/`Union[...]`
throughout, per `CLAUDE.md`'s conventions), but nothing verifies annotations are internally
consistent - `ruff`'s configured rule set (`E`, `F`, `I`, `UP`, `B`, `SIM`) catches style and
some correctness issues, not type mismatches.

**Proposed approach:** add `mypy` (or `pyright`) as a dev dependency, start in a lenient mode
(e.g. `--ignore-missing-imports`, no `--strict`) to establish a baseline without a large
upfront fix-everything cost, then tighten incrementally per-module using the same discipline
`ruff.toml` already uses for its own rule selection.

**Size:** M (tool integration is S; fixing what it finds across `src/` is the variable part).
**Depends on:** nothing, but sequences naturally after Group B/C1 so the lint stack is
described accurately in one pass (see A3).

### C3. No pre-commit hook wiring

**Problem:** `ruff check` and the flake8 plugin (once Group B fixes it) both run only on
demand (`uv run ruff check`, or manually) - nothing stops a commit with a lint violation from
landing locally before a human remembers to run the check.

**Proposed approach:** add a `.pre-commit-config.yaml` running `ruff check` (and, once wired,
the flake8 plugin) on `pre-commit`. This is intentionally *not* a CI gate (the repo has none
by design, per `CLAUDE.md`) - it's a local, opt-in convenience, consistent with this repo's
existing preference for Claude Code hooks over CI for automated gating.

**Size:** S. **Depends on:** Group B (wiring the flake8 plugin for real) should land first,
so the pre-commit config references a check that actually works.

## Group D - Generator performance (redundant work, not complexity bugs)

None of the following are algorithmic (`O(n^2)`) problems - the catalog is small and linear
scans are fine at current scale. These are "the same file gets read/walked more than once
per invocation for no reason" findings, worth fixing opportunistically rather than urgently.

- **`cli.py`'s `list_cmd`** calls `discover()` once per `KINDS` entry (4x per preset) in its
  `--json` branch, and separately repeats a `discover()` call for the same preset in the
  non-JSON branch below it - one `discover()` call per preset, reused for both branches,
  would remove the duplication. **Size:** S.
- **`dependencies.py`'s `write_inline_dependencies`** reads every target file twice per run:
  once inside `build_dependency_graph`'s `_entity_text` helper, again in its own per-file
  loop. Caching the first read (a `dict[Path, str]` built once, reused by both) removes the
  double I/O. **Size:** M (the function is part of the largest module in `src/`, 544 lines,
  so this touches a dense piece of code - test coverage should land first, see Group E).
- **`presets.py`'s `copy_preset`** re-walks the tree (`_entity_names`/`discover()`) once for
  the base preset and once per specialization layered on top - fine at 2-3 specializations
  per preset today, but worth a single shared walk if the catalog grows. **Size:** S.

**Depends on:** the `dependencies.py` fix specifically should follow Group E's proposal to
add dedicated unit tests for that module first - it currently has none, and this is exactly
the kind of module where a "harmless" caching refactor can silently change behavior around
edge cases (`--remove`, `--inline`) with no test to catch a regression.

## Group E - Test suite hardening

### E1. Untested or thinly-tested modules

- **`presets.py`** - "the entire generation mechanism" per `CLAUDE.md`'s own architecture
  map - has no dedicated `test_presets.py`; it's exercised only incidentally through
  `test_cli.py` and `test_integration_real_repo.py`. Edge cases like the name-collision
  `ValueError` and partial specialization layering have no isolated unit test.
- **`workspace.py`** - the `Workspace` frozen dataclass every other module threads through -
  has no dedicated test of its own contract (path resolution, frozenness).
- **`ai/client.py`** - the one module allowed to import `anthropic`, and only lazily - has
  zero references anywhere in `tests/`. Even a smoke test mirroring the existing lazy-import
  guarantee (`tests/test_markers.py::test_cli_import_does_not_pull_anthropic`) is missing for
  this module specifically.
- **`dependencies.py`** (544 lines, the largest module in `src/`) has no dedicated unit test
  file - only incidental coverage via `test_integration_real_repo.py` smoke calls. This is
  the module Group D's performance fix touches, making pre-existing test coverage here a
  prerequisite, not a nice-to-have.

**Size:** M overall (one focused test file per module, S each, but four of them).

### E2. `tests/test_integration_real_repo.py` - "the load-bearing file" - excludes `cpp`

**Problem:** every `@pytest.mark.parametrize("preset", ["python", "java"])` block in this
file omits `cpp`. `cpp` was added later (per the commit history: "feat: add cpp preset with
boost and qt specializations") and was never folded into this file's parametrization, even
though `list --json`-style preset discovery already reports `cpp` correctly.

**Why it matters:** `CLAUDE.md` calls this file out explicitly as the file that "generates
each real preset and asserts zero dangling `@docs/` references, no links outside the preset's
own tree, no unresolved placeholders" - `cpp` currently gets none of those guarantees exercised
by the repo's own load-bearing safety net.

**Proposed approach:** add `"cpp"` to every parametrization in this file. This will likely
immediately surface real findings, since Group F below already documents at least one
concrete `cpp`-specific authoring bug (F3) that this test's "no unresolved placeholder / no
prose naming an unshipped tool"-style assertions might well have caught had `cpp` been
included from the start.

**Size:** S to add the parametrization; likely M once whatever it surfaces is fixed.
**Depends on:** nothing - do this early, since Group F's parity work benefits from having
this safety net cover all three presets before more content changes land in any of them.

### E3. `X012` has zero test coverage (ties to Group B)

Already covered in Group B's proposed approach (step 3) - listed here too since it's
squarely a test-suite gap in its own right, not only a consequence of the plugin-wiring bug.

### E4. Test infrastructure improvements

- **`fixture_workspace`** (`tests/conftest.py`) hand-builds two synthetic presets ("demo",
  "other") via ~50 lines of imperative `mkdir`/`write_text` calls. A small builder/factory
  helper (e.g. `make_synthetic_preset(tmp_path, name, agents=[...], hooks=[...])`) would make
  adding a third synthetic preset - useful for exercising `cpp`-shaped structure without
  touching the real `templates/cpp/` tree - far cheaper than hand-editing the fixture.
- No fixture currently wraps `real_workspace` with a `tmp_path` copy for tests that need to
  *mutate* a real-preset-shaped tree without touching `templates/` itself; each test that
  needs this improvises its own copy today. A `real_workspace_copy` fixture would remove that
  repetition.
- **`test_headless.py`** (316 lines) exercises `headless.py`'s subprocess path; worth a
  follow-up audit confirming every test case goes through the injected `run=` parameter
  (the documented testability seam) rather than any path that could shell out to a real
  `claude` binary if one happens to be on `PATH` in CI-less local runs.

**Size:** S each.

## Group F - Template catalog cross-preset parity

Per `CLAUDE.md`, the three presets (`python`, `java`, `cpp`) are "independent, self-contained
copies, not two views onto shared source" - so parity gaps below are not automatically bugs,
but they are worth an explicit maintainer decision per item (add the missing coverage, or
document why that preset doesn't need it) rather than leaving them as silent asymmetry.

### F1. `java` and `cpp` lack `python`'s dependency/quality-gate hook coverage

Neither `templates/java/.claude/hooks/` nor `templates/cpp/.claude/hooks/` ships a
`dep_audit.py`, `post_edit_format.py`, `style_fixes.py`, or `run_tests.py` equivalent -
`python`'s `settings.json` wires all four; java's and cpp's do not (consistent with
`CLAUDE.md`'s own note that java's settings.json is "already trimmed to wire only hooks that
exist in that preset"). Each is plausibly implementable for the other ecosystems (a Maven/
Gradle dependency-audit and formatter equivalent for java; a CMake/Conan-or-vcpkg dependency
audit and `clang-format`/`clang-tidy` equivalent for cpp) but that's real, ecosystem-specific
work per hook, not a shared refactor.

**Proposed approach:** one milestone per preset (or per hook, if the maintainer prefers
smaller units), each scoped to "port `dep_audit.py`'s trigger/shape to `<ecosystem>`'s
equivalent tool," explicitly *not* attempting to share implementation with `python`'s copy
(hooks are Python-only per-file, per CLAUDE.md's table: "`.claude/hooks/` ... Never imports
from `scripts/`" and are independent per preset by design).

**Size:** L overall (M per hook per preset - roughly 4 hooks x 2 presets = up to 8 candidate
tasks, likely to be prioritized rather than all landed at once).

### F2. `java` and `cpp` lack a `test-gap` and `dep-audit` skill, and `python`'s third loop

Neither preset ships a `.claude/skills/test-gap/` or `.claude/skills/dep-audit/` (`python`
has both), and neither ships an `implement-milestone.md` loop (both have
`implement-subtasks.md` + `update-docs.md`; `python` additionally has a milestone-level
loop). Notably, `templates/java/.claude/loops/implement-subtasks.md:209` already
self-documents this exact gap in its own prose ("compare templates/python's `/test-gap` and
`/dep-audit`. If this project adds equivalents, add...") - so this omission is at least
partly intentional/acknowledged already in java's case, not purely an oversight.

**Size:** M per preset. **Depends on:** F1 for `dep-audit` specifically (the skill needs a
hook or script to invoke).

### F3. Authoring bug: `java` and `cpp` advertise a `/test-gap` flow they don't ship

**Problem:** this is the concrete bug CLAUDE.md warns about by name ("prose naming a tool the
preset does not ship"), found in both non-python presets:

- `templates/cpp/.claude/agents/testing-expert.md` frontmatter's `description` says "Use for
  test generation, test-gap analysis" and its body has a full `## Test-gap analysis (the
  /test-gap flow)` section (line 80) - but `templates/cpp/.claude/skills/` ships no
  `test-gap` directory (confirmed: `adr-write`, `doc-xref`, `document-tests`, `link-check`,
  `pr-review`, `secret-scan`, `verify-subtask` only).
  `templates/java/.claude/agents/testing-expert.md` frontmatter's `description` similarly
  says "test-gap analysis" with the same missing skill in `templates/java/.claude/skills/`.

**Why it matters:** a project generated from either preset gets an agent that tells a future
developer (or a future Claude Code session) to run `/test-gap`, which does not exist in that
generated project - the exact failure class this repo's own conventions section names as a
real, previously-shipped bug.

**Proposed approach:** either add the `test-gap` skill to both presets (folds into F2, and
is the more useful fix - `python`'s existing `test-gap` skill is a reasonable model to port),
or, if not adding it yet, edit both `testing-expert.md` files to remove the `/test-gap`
references until the skill actually ships - the second option is a same-day fix and should
land regardless of when/whether F2 is scheduled.

**Size:** S for the prose fix; M if bundled with actually shipping the skill (F2).
**Depends on:** nothing for the prose-only fix; F2 if doing the full port.

### F4. Drifted shared hook logic: `cpp`'s `_common.py` fixed a bug `python`'s and `java`'s copies still have

**Problem:** `CLAUDE.md` already flags that `_common.py` is duplicated per-preset by design
and specifically warns `slugify` "must stay behaviourally identical" across copies. Direct
comparison shows the link-resolution logic itself has already diverged, not just as a
theoretical risk: `templates/cpp/.claude/hooks/_common.py` (confirmed at lines ~108-113)
skips glob/template-shaped paths (`/docs/adr/*.md`, `{NN}-{slug}.md`) and correctly resolves
a leading-`/` absolute-from-repo-root path against `REPO_ROOT` before checking existence;
`templates/python/.claude/hooks/_common.py` and `templates/java/.claude/hooks/_common.py`
have neither behavior - confirmed by diffing the two directly against each other: they are
byte-identical (module code, not just docstrings) apart from one docstring paragraph, so
both non-cpp presets share the exact same gap, not two independent instances of it.

**Why it matters:** a doc in a python- or java-generated project that uses the
absolute-from-repo-root link convention (`docs/roadmap/README.md`'s own "Linking convention"
section mandates exactly this style: "Always a leading `/` (repo root), never relative
`../../` chains") will be misjudged by `doc_link_check.py` in those two presets, while the
same doc is judged correctly in a cpp-generated project. This is a real, currently-shipping
behavioral inconsistency between presets' otherwise-supposed-to-be-independent copies of the
same logic, not a cosmetic drift.

**Proposed approach:** backport `cpp`'s glob-skip and absolute-path-resolution fix into
`python`'s and `java`'s `_common.py`, or, if there's a reason cpp alone needs it (e.g. cpp
docs use the absolute-link convention more than python/java docs do), document that reason
explicitly in a comment in all three copies so a future reader knows the divergence is
deliberate rather than assuming (as this document initially had to investigate) that it's
unintentional drift.

**Size:** S. **Depends on:** nothing - a quick, well-scoped fix; both non-cpp presets need
the identical backport, so it's one patch applied twice, not two separate investigations.

### F5. Specialization richness is uneven across presets

`python` ships three specializations (`django`, `ml-ai`, `webscraping`); `java` and `cpp`
ship two each (`android`, `spring`; `boost`, `qt`). Not inherently a bug - `specializations.py`
restricts specializations to `agents/`+`skills/` content and this is genuinely optional,
opt-in richness - but worth an explicit maintainer decision on whether e.g. a `junit5`/
`quarkus`-shaped java specialization or a `cmake-modern`-shaped cpp specialization is wanted,
rather than leaving it as an unexamined asymmetry.

**Size:** M per new specialization, if any are wanted. **Depends on:** nothing; purely a
scope decision, not a bug fix.

## Group G - Already-queued work worth re-prioritizing (not new proposals)

These are not new findings - they're already written down elsewhere in this repo and are
included here only so a maintainer scheduling new milestones from this document sees the
full picture in one place, rather than re-discovering them later or accidentally treating
this document as the complete backlog.

- **Milestone `0003`** (`docs/roadmap/0003-api-based-marker-research/status.md`) - all five
  tasks "Not started": `ai/researcher.py` + `request_agentic()`; rewiring `resolve_one`/
  `resolve_tree` onto a fact sheet; the echo-detector + identifier-presence quality gate
  (already recommended for near-term, standalone extraction in
  [hallucination-mitigation-docs.md#1-ship-the-designed-but-deferred-quality-gate-now](hallucination-mitigation-docs.md#1-ship-the-designed-but-deferred-quality-gate-now));
  pointing the other AI increments at the fact sheet; a fixture-repo integration test.
- **`docs/roadmap/0001-ai-assisted-generation/01.0-working-implementation/03-agentic-marker-research.md#other-improvements-to-fold-in`**
  lists, verbatim as its own "follow-up, not scope creep" items: re-embedding
  `create-from-template.md`'s prompt into `resolver.py` directly rather than a runtime file
  read (a packaging correctness issue for a pip-installed copy of this package); extending
  the headless research prompt to cover `loops/` markers, not only `agents/`; a `claude
  --version` drift/compatibility check; non-interactive/CI-environment verification of the
  headless CLI path; and giving the other three AI increments (`maybe_write_tutorial`,
  `maybe_describe_test_conventions`, `propose_first_milestone`) the same quality treatment as
  marker resolution, since they're currently thin one-shot calls.
- **Explicitly rejected/deferred alternatives - do not re-propose without new justification:**
  a hand-rolled in-house Messages-API tool-loop research harness (deliberately deferred in
  favor of the `claude`-CLI headless approach, preserved only as milestone `0003`); the
  `claude-agent-sdk` as a *replacement* implementation strategy (explicitly out of scope per
  `0003/plan.md`'s options table - a cleaner implementation of the chosen direction, not a
  competing one, and "not this milestone's concern").

## Suggested milestone slate

A candidate mapping from the groups above to `docs/roadmap/` milestones, for the maintainer
to accept, reject, merge, or re-split. Real `{NNNN}` numbers should be assigned only after
Group A1 fixes the index, since the next free number depends on whether `0002` is deleted,
reused, or renumbered:

| Candidate milestone | Groups folded in | Rough size |
|---|---|---|
| Doc-hygiene cleanup | A1, A2, A3 | S |
| Lint stack correctness & hygiene | B, C1, C2, C3, E3 | M |
| Generator test hardening | E1, E2, E4 | M |
| Generator performance pass | D | S-M |
| Preset parity: hook/skill coverage | F1, F2, F3 | L |
| Preset parity: shared-logic drift audit | F4 (plus a one-time full diff of all shared files across all three presets, not only the one pair spot-checked here) | S-M |
| Specialization expansion (scope decision, not a fix) | F5 | M, per specialization |

Groups B and E2 in particular are recommended as near-term, low-risk, high-leverage starting
points: both are small, both currently have zero downside (fixing them changes nothing for
code that already passes), and both close gaps in this repo's own safety net rather than
adding new surface area to maintain.
