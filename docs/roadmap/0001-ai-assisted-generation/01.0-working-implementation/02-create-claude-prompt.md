# Create Claude Prompts to Generate from Templates

## Goal (from the original task)

After deterministic `{{PLACEHOLDER}}` replacement, call the Claude API to (in addition to existing
actions):

* Deeply research the project via `../../../../CLAUDE.md`, `../../../../README.md`, `../../../../AGENTS.md`
* Replace tags in Markdown such as `<!-- TEMPLATE-INIT: ... -->`, `<!-- SME REVIEW NEEDED: ... -->`
  and others
* Update the list of actual agents in `../../../agent/agents.md`
* Update the list of actual skills in `../../../agent/skills.md`
* Update the list of actual hooks in `../../../agent/hooks.md`
* Create a project tutorial in `../../../agent/tutorial.md`
* Replace the roadmap example with a "good first task"
* Describe the actual test structure in `docs/test/*.md`

## Current state — most of the AI-resolution plumbing already exists

Before designing new work, it's worth being precise about what's already shipped, because two of
the eight bullets above are **done**, and a third is **half done**:

* `../../../../src/awesome_templates/markers.py` scans generated Markdown for `<!-- TEMPLATE-INIT: ... -->`
  and knows how to splice a replacement back in (inline vs. block, list-bullet vs. plain).
* `src/awesome_templates/resolver.py::gather_context` **already** reads `../../../../README.md`, `../../../../CLAUDE.md`,
  and `../../../../AGENTS.md` from the target project (plus a dependency manifest, the `../../../../src`/`../../../../tests` tree,
  and any `docs/adr/*.md` / `docs/specs/*.md`), all folded into one budgeted context bundle. The
  first bullet above is satisfied today.
* `../../../../src/awesome_templates/ai/client.py` is the one module allowed to import `anthropic`, lazily.
* `resolver.resolve_tree` drives the whole thing end-to-end, wired to `generate --resolve-markers`
  in `cli.py`, gated behind the optional `ai` extra and `ANTHROPIC_API_KEY` — fully covered by
  `../../../../tests/test_resolver.py` against a fake client (no real network call in the suite).

So this task is **not** "build an AI-resolution feature from scratch" — it's five additions on top
of an existing, tested pipeline, plus one generalization. Each is scoped below with a concrete
design, code sketch, and its own acceptance criteria, so they can land as five separate PRs against
`resolver.py`/`markers.py`/a new `docgen.py`.

`★ Insight ─────────────────────────────────────`
`resolver.py`'s own docstring already calls it "the programmatic sibling of
`../../../../.claude/agents/create-from-template.md`" — the interactive agent and this CLI pipeline solve the
same problem (fill in project-specific facts a template can't know) for two different audiences:
someone driving Claude Code interactively vs. someone scripting `generate` in CI. Every prompt
designed below should stay consistent with what that agent already does, not invent a second voice.
`─────────────────────────────────────────────────`

### A key distinction the original task blurs: not everything here needs the API

Three of the eight bullets ("update list of actual agents/skills/hooks") ask for **facts that
already exist as data on disk** — every agent/skill's YAML frontmatter already has a `name:` and
`description:`. Turning that into a table is a glob + a tiny parser, not a research task. Spending
an LLM call to re-derive information already sitting in a file's frontmatter would be slower, cost
money, and risk the model paraphrasing (or hallucinating) a description that's already written
verbatim. That work is designed below as **increment B: deterministic, no network, runs on every
`generate`** — separated sharply from the increments that genuinely need the model to synthesize
something no file states outright (a tutorial narrative, a first milestone, a threat model draft).

## Increment A — generalize markers beyond `TEMPLATE-INIT`

### What's in `../../../../templates` today

```
$ grep -rhoE '<!--\s*[A-Z][A-Z -]+:' templates/ | sort -u
<!-- SME REVIEW NEEDED:
<!-- TEMPLATE-INIT:
<!-- TODO:
```

Two of these are the same *kind* of thing (a project-specific fact only a target-project read can
fill in) but with **opposite resolution policy**:

* `TEMPLATE-INIT` (12 occurrences across both presets' agents/loops) — safe to auto-fill with
  confident AI prose; low-confidence already falls back to a `> **TODO (fill in): ...**`
  blockquote via `resolver.render`.
* `SME REVIEW NEEDED` (`../../../security/README.md`, both presets) — this one marks a spot that
  **needs a human security reviewer**, e.g. "populate with this project's first real threat
  model." Auto-resolving this the same way `TEMPLATE-INIT` is resolved would be actively harmful:
  it would replace a visible "a human hasn't looked at this yet" flag with fabricated-sounding
  prose that reads as already reviewed. **This marker must never be silently resolved away** — the
  model may *draft* a starting point, but the output must stay flagged as unreviewed regardless of
  the model's own confidence score.

The bare `<!-- TODO: describe ruff, mypy, Flake8 -->` in `../../../dev/python_language_rules.md` is a
**third, unrelated thing** — an ordinary authoring TODO, not a `<!-- KIND: instruction -->`-shaped
marker at all, and its content (describe the *lint tool config*) is answerable by reading
`../../../../pyproject.toml`/`../../../../ruff.toml` directly rather than asking a model to guess. **Out of scope for this
task** — flagging it here only so "and others" in the original task isn't read as "sweep every
HTML comment that looks TODO-ish," which this design deliberately does not do.

### Design

Generalize `markers.py`'s regex and `Marker` dataclass to carry a `kind`, keeping `TEMPLATE-INIT`
behavior byte-identical:

```python
MARKER_KINDS = ("TEMPLATE-INIT", "SME REVIEW NEEDED")

MARKER_RE = re.compile(
    r"<!--\s*(?P<kind>" + "|".join(re.escape(k) for k in MARKER_KINDS) + r"):\s*"
    r"(?P<instruction>.*?)\s*-->",
    re.DOTALL,
)

@dataclass(frozen=True)
class Marker:
    ...
    kind: str  # one of MARKER_KINDS
```

`find_markers` sets `kind=m.group("kind")` on every `Marker` it builds; everything else about the
function (block vs. inline detection, context slicing) is unchanged.

`resolver.render` branches on `marker.kind` instead of only on confidence:

```python
def render(resolved: ResolvedMarker) -> str:
    marker = resolved.marker
    if marker.kind == "SME REVIEW NEEDED":
        head = f"{marker.indent}> **SME REVIEW NEEDED (AI-drafted - verify before relying on this):**"
        body = [f"{marker.indent}> {line}" for line in resolved.prose.splitlines() if line.strip()]
        return head + ("\n" + "\n".join(body) if body else "")
    # ... existing TEMPLATE-INIT confident/TODO branches, unchanged
```

`resolver.resolve_one` passes a kind-specific instruction addendum for `SME REVIEW NEEDED` (e.g.
"draft a starting threat model outline; be explicit this is a draft, not a completed review") —
same `_SYSTEM` prompt, one extra paragraph appended when `marker.kind != "TEMPLATE-INIT"`.

`ResolveSummary` gains a `human_review: int` counter (markers resolved into a flagged draft,
distinct from `resolved` and `todos`), so `generate`'s console/JSON summary can report it
separately — a caller scripting CI can treat "N markers still need a human" very differently from
"N markers are genuinely done."

### Acceptance criteria

**Code**
- [ ] `markers.py`: `MARKER_KINDS`, generalized `MARKER_RE`, `Marker.kind`.
- [ ] `resolver.py`: `render` branches on `marker.kind`; `_SYSTEM`/`resolve_one` add the
      kind-specific addendum; `ResolveSummary.human_review` added; `resolve_tree` increments it
      instead of `resolved`/`todos` for `SME REVIEW NEEDED` markers.
- [ ] `cli.py`'s `generate` summary output (console + `--json`) reports `human_review` alongside
      the existing `markers_resolved` / `markers_todo` / `markers_failed`.

**Tests**
- [ ] `../../../../tests/test_markers.py`: extend existing marker-shape tests (block/inline/list-bullet/
      multiline) to also assert `.kind == "TEMPLATE-INIT"` — these must keep passing unmodified in
      spirit, only gaining an assertion.
- [ ] `tests/test_markers.py::test_find_markers_recognizes_sme_review_needed_kind`
- [ ] `tests/test_resolver.py::test_render_sme_review_needed_always_flagged_even_when_confident` —
      feed `confident=True`, assert the output still starts with `> **SME REVIEW NEEDED`.
- [ ] `tests/test_resolver.py::test_resolve_tree_counts_sme_markers_as_human_review_not_resolved`
- [ ] `tests/test_resolver.py::test_bare_todo_comment_is_left_untouched` — regression pin for the
      explicit non-goal above (a `<!-- TODO: ... -->` comment must not match `MARKER_RE` at all).

**Docs**
- [ ] `resolver.py`'s module docstring gains one sentence distinguishing the two marker policies.
- [ ] No `templates/**` content changes required for this increment — existing markers already use
      the right tags; only the resolution *code* changes.

## Increment B — deterministic doc listings (agents/skills/hooks)

Runs unconditionally on every `generate` (no `--resolve-markers`, no API key, no `ai` extra) — this
is plain filesystem introspection over what `copy_preset` just wrote, in the same spirit as
`markers.py` being "the pure, network-free half" of the marker feature.

### New module: `../../../../src/awesome_templates/docgen.py`

```python
"""Deterministic 'what actually shipped' doc generation - no network, no AI.
Every agent/skill already carries name+description in YAML frontmatter;
turning that into docs/agent/{agents,skills,hooks}.md is a glob and a render,
not a research task. Runs on every `generate`, unconditionally. The genuinely
AI-authored docs (tutorial, roadmap seed, test-structure narrative) live in
resolver.py instead, gated behind --resolve-markers, because they synthesize
content no file states outright.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Hand-rolled, not full YAML: every frontmatter block in templates/ is
    flat `key: value` lines (see any agents/*.md or skills/*/SKILL.md).
    Adding a pyyaml dependency for that is the same call resolver.py already
    made for .env parsing - one variable's worth of syntax doesn't need a
    library."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group("body").splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


@dataclass(frozen=True)
class AgentInfo:
    name: str
    description: str
    model: str


@dataclass(frozen=True)
class SkillInfo:
    name: str
    description: str
    invocation: str


@dataclass(frozen=True)
class HookInfo:
    name: str
    description: str
    trigger: str  # e.g. "PreToolUse: Bash" - derived from settings.json


def list_agents(project_dir: Path) -> list[AgentInfo]: ...
def list_skills(project_dir: Path) -> list[SkillInfo]: ...
def list_hooks(project_dir: Path) -> list[HookInfo]: ...

def render_agents_doc(agents: list[AgentInfo]) -> str: ...
def render_skills_doc(skills: list[SkillInfo]) -> str: ...
def render_hooks_doc(hooks: list[HookInfo]) -> str: ...
```

`list_hooks` is the one non-trivial case: a hook `.py` file has no frontmatter, only a module
docstring, and doesn't say *what triggers it* — that's `settings.json`'s `hooks` section (event +
matcher). `list_hooks` reads `../../../../.claude/settings.json`, walks `hooks.<Event>[].hooks[].command`,
extracts the filename (`.../hooks/dep_audit.py` → `dep_audit`), and pairs it with that hook file's
first module-docstring line for the description. A hook file present but not wired in
`settings.json` (which should never happen in a shipped preset — that's exactly the dead-hook bug
class root `../../../../CLAUDE.md` documents) surfaces as `trigger: "(unwired)"` rather than being silently
dropped, so it's visible in the generated docs instead of only in a maintainer test.

### Wiring into `cli.py`

Called unconditionally right after `copy_preset` returns, writing into
`out_dir/docs/agent/{agents,skills,hooks}.md`, replacing everything below each file's existing `#
X Reference` heading:

```python
written = copy_preset(workspace, preset_value, out_dir, force_value, subs, warnings, specializations=spec_values)
docgen.write_agent_docs(out_dir, warnings)  # agents.md, skills.md, hooks.md
```

Idempotent by construction (pure function of what's on disk) — running `generate --force` again
just regenerates the same three files from the current tree, no drift, no marker/sentinel bookkeeping needed here (unlike Increments C/D below, which touch content a user may have since edited).

### Acceptance criteria

**Code**
- [ ] `../../../../src/awesome_templates/docgen.py` as sketched: `list_agents`/`list_skills`/`list_hooks`,
      `render_*_doc`, and a `write_agent_docs(project_dir, warnings)` orchestrator.
- [ ] `cli.py`'s `generate` calls `docgen.write_agent_docs` unconditionally after `copy_preset`
      (works with zero flags, zero API key, zero `ai` extra).
- [ ] `../../../../src/awesome_templates/CLAUDE.md` module map gets a `docgen.py` entry.

**Tests**

New `../../../../tests/test_docgen.py` (using `fixture_workspace`'s `demo` preset — it already has
`widget-verifier.md` with `name: widget-verifier` frontmatter, `_common.py` + `guard.py` hooks
wired to `PreToolUse: Bash` in its `settings.json`, and an `adr-write` skill directory):

- [ ] `test_list_agents_parses_name_and_description_from_frontmatter`
- [ ] `test_list_skills_reads_skill_md_per_directory`
- [ ] `test_list_hooks_derives_trigger_event_from_settings_json`
- [ ] `test_list_hooks_flags_unwired_hook_file_rather_than_dropping_it`
- [ ] `test_render_agents_doc_produces_stable_markdown_table` (snapshot-style exact-string assert,
      since this is pure rendering)
- [ ] `test_write_agent_docs_preserves_existing_h1_heading`

`../../../../tests/test_cli.py` addition:
- [ ] `test_generate_populates_agents_doc_without_resolve_markers_flag` — run plain `generate`
      (no `--resolve-markers`, no API key set), assert `../../../agent/agents.md` contains
      `widget-verifier` and is no longer just the stub header.

`../../../../tests/test_integration_real_repo.py` addition:
- [ ] `test_real_preset_agents_doc_lists_every_real_agent_file` — generate the real `python`
      preset, assert `../../../agent/agents.md` mentions all 12 real agent stems (regression pin, same
      style as the existing zero-dangling-reference test).

**Docs**
- [ ] This *is* the docs deliverable: `../../../agent/agents.md` / `skills.md` / `hooks.md` go from a
      one-line stub header to real, generated content in every project `generate` produces, for
      **every** preset (no `--resolve-markers` required).
- [ ] If task 01 has landed, specialization-provided agents/skills appear in the same listing
      (`list_agents`/`list_skills` just glob `out_dir/.claude/agents` and `skills` after
      specialization merge — no extra code needed here, since increment B runs after the full copy
      including any specialization layer).

## Increment C — AI-assisted tutorial (`../../../agent/tutorial.md`)

`../../../agent/tutorial.md` currently ships as literally `# Agentic Tutorial\n` — a stub for this
increment to fill in. This genuinely needs the model: "how does someone new to this project
actually use the agents/skills/hooks that shipped" is a synthesis task, not a fact lookup.

### Design

Add to `resolver.py`, reusing `gather_context` and the doc listings increment B just produced (so
the tutorial names *real* agents/skills instead of inventing plausible-sounding ones):

```python
_TUTORIAL_SYSTEM = """\
You are writing the onboarding tutorial for a generated Claude Code kit, at
docs/agent/tutorial.md. Audience: a developer joining this specific project
who has never used this kit before. Ground every claim in the project bundle
and the actual agent/skill/hook list below - never invent an agent, skill, or
workflow that isn't in that list. Structure: a short "why this exists"
paragraph, then a walkthrough of the 2-3 most useful agents/skills for this
project's actual domain (pick from the real list, don't cover all of them
exhaustively), each with one concrete example invocation. End with "where to
go next" pointing at docs/agent/agents.md, skills.md, and hooks.md.
"""

def generate_tutorial(client, context_bundle: str, agents: list[AgentInfo],
                       skills: list[SkillInfo], *, model: str = MODEL) -> str:
    ...
```

Schema-constrained output (`{"markdown": "..."}`) rather than free text, consistent with every
other `ai_client.request_json` call in this codebase.

**Idempotency guard:** only write if the current `tutorial.md` is still exactly the stub
(`# Agentic Tutorial\n`, or matches an allow-listed set of untouched-stub strings for each preset).
If a user already wrote their own tutorial, `--resolve-markers` must never clobber it — same
non-destructive posture `resolve_tree` already has toward markers (it only ever touches marker
spans, never surrounding prose). Skipping is reported as a warning, not silently: `"tutorial.md
already customized - left as-is"`.

### Acceptance criteria

**Code**
- [ ] `resolver.py`: `_TUTORIAL_SYSTEM`, `_TUTORIAL_SCHEMA`, `generate_tutorial`, and a
      `maybe_write_tutorial(out_dir, client, context_bundle, warnings)` entry point wired into
      `resolve_tree`'s caller in `cli.py` (same `--resolve-markers` flag, no new flag needed).

**Tests**
- [ ] `tests/test_resolver.py::test_generate_tutorial_writes_content_referencing_real_agent_names`
      (fake client returns a payload naming the fixture's actual agent; assert it lands in the
      file).
- [ ] `tests/test_resolver.py::test_maybe_write_tutorial_skips_when_already_customized` — pre-seed
      `tutorial.md` with non-stub content, assert it's unchanged and a warning is recorded.
- [ ] `tests/test_resolver.py::test_maybe_write_tutorial_overwrites_the_stub`

**Docs**
- [ ] `../../../agent/tutorial.md` acceptance is the generated output itself — reviewed manually once
      against the real `python` preset generated for a small sample project, since prose quality
      isn't something a unit test can assert beyond "isn't the stub" and "mentions real names."

## Increment D — replace the roadmap example with a "good first task"

`../../../../templates/python/docs/roadmap/0001-working-implementation/plan.md` already says outright:

> Replace this whole milestone with your own project's first real milestone once you adopt this
> template — it exists to show the shape, not to be extended.

This increment automates exactly that sentence, for both presets. It is the riskiest increment
here — it deletes example content — so it gets its own explicit opt-in flag rather than piggy-backing
silently on `--resolve-markers`.

**Recommendation:** a new `--seed-roadmap` flag, only meaningful (and only accepted) together with
`--resolve-markers` (needs the same API key/context). Reviewer should confirm this split before
implementation — the alternative (folding it into `--resolve-markers` unconditionally) trades a
flag for a bigger blast radius on an otherwise-conservative flag that today only ever edits inline
comment spans, never deletes whole files.

### Design

* **Idempotency guard**: before doing anything, check whether the literal sentinel sentence above
  is still present in `plan.md`. If it's gone, the user (or a previous run) already replaced this
  milestone — no-op, warn `"roadmap milestone already customized - left as-is"`. This mirrors
  Increment C's stub-detection guard.
* **Structured generation, deterministic rendering** — same split `markers.py`/`resolver.py`
  already use (model decides *content*, plain code decides *formatting*). Ask the model for a
  small structured plan, not raw files:

```python
_ROADMAP_SCHEMA = {
    "type": "object",
    "properties": {
        "milestone_title": {"type": "string"},
        "task_slug": {"type": "string"},
        "task_name": {"type": "string"},
        "subtasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["slug", "title", "summary"],
            },
        },
    },
    "required": ["milestone_title", "task_slug", "task_name", "subtasks"],
}

def propose_first_milestone(client, context_bundle: str, *, model: str = MODEL) -> dict: ...

def render_milestone(plan: dict) -> dict[str, str]:
    """Pure function: structured plan -> {relative_path: file_content}, following
    the exact taxonomy plan.md documents (plan.md + status.md at the milestone
    root, one `{TT.t}-{slug}/README.md` + numbered `{NN}-{slug}.md` subtask
    files). No model call - this is the same content/format split render() in
    resolver.py already does for markers."""
```

* `seed_first_milestone(out_dir, client, context_bundle, warnings) -> bool` deletes the existing
  `docs/roadmap/0001-working-implementation/` tree and writes `render_milestone(...)`'s output in
  its place, returning whether it acted (for the CLI summary).

### Acceptance criteria

**Code**
- [ ] `resolver.py`: `_ROADMAP_SYSTEM`, `_ROADMAP_SCHEMA`, `propose_first_milestone`,
      `render_milestone` (pure, independently testable with no fake client), `seed_first_milestone`.
- [ ] `cli.py`: new `--seed-roadmap` flag, validated to require `--resolve-markers`, threaded to
      `seed_first_milestone`; summary output reports whether it acted or was skipped.

**Tests**
- [ ] `tests/test_resolver.py::test_render_milestone_produces_expected_file_tree` — no AI mock
      needed; feed a fixed plan dict, assert exact relative paths (`plan.md`, `status.md`,
      `01.0-<slug>/README.md`, `01.0-<slug>/01-<slug>.md`, ...) and that `status.md`'s table row
      matches the task name.
- [ ] `tests/test_resolver.py::test_seed_first_milestone_replaces_example_when_sentinel_present`
- [ ] `tests/test_resolver.py::test_seed_first_milestone_noop_when_sentinel_already_gone`
- [ ] `tests/test_cli.py::test_generate_rejects_seed_roadmap_without_resolve_markers`

**Docs**
- [ ] No hand-written doc changes — the generated milestone *is* the artifact. `plan.md`'s own
      "replace this" sentence doubles as the machine-checkable sentinel, so no separate marker
      syntax needs inventing for this one file.

## Increment E — describe the actual test structure (`docs/test/*.md`)

`../../../test/code_test_coverage.md` is already mostly deterministic today (its `{{PROJECT_PACKAGE}}`
placeholders resolve at copy time via the existing `templating.py` pass, with zero new code). What
it's missing is the actual test-directory *shape* of the target project, since it currently only
gives generic pip/pytest instructions.

### Design

Deterministic first, thin AI layer second — same split as increment B vs. C:

* `docgen.py` gains `list_test_files(project_dir) -> list[str]`, reusing the same `../../../../tests` glob
  `resolver.gather_context` already builds internally (extract that walk into a shared helper
  both modules call, rather than duplicating it).
* Append a "## Actual Test Layout" section listing the real files/dirs — no API call needed for
  this part.
* Optionally (still under `--resolve-markers`), one short AI-drafted paragraph summarizing
  conventions *observed from file names only* (e.g. "tests mirror `../../../../src` package structure;
  fixtures centralized in `conftest.py`") — deliberately fed only the file-name listing, not file
  contents, keeping this prompt cheap and fast regardless of project size.

### Acceptance criteria

**Code**
- [ ] `docgen.py::list_test_files`; `resolver.gather_context` refactored to call it instead of its
      own inline walk (no behavior change to `gather_context`'s existing output — covered by the
      existing `test_gather_context_includes_headings_and_respects_budget` test continuing to pass
      unmodified).
- [ ] `docgen.py::render_test_layout_section`.
- [ ] `resolver.py::maybe_describe_test_conventions` (AI paragraph, same stub/idempotency guard
      pattern as increment C, keyed off a sentinel or an appended-once marker).

**Tests**
- [ ] `tests/test_docgen.py::test_list_test_files_lists_real_test_paths`
- [ ] `tests/test_docgen.py::test_render_test_layout_section_is_stable_markdown`
- [ ] `tests/test_resolver.py::test_describe_test_conventions_uses_filenames_only_not_contents` —
      assert the prompt sent to the fake client contains file *names* but not the fixture test
      files' actual source text.

**Docs**
- [ ] `../../../test/code_test_coverage.md` gains a real "Actual Test Layout" section per generated
      project; this is the deliverable.

## Cross-cutting acceptance criteria (apply to all five increments)

- [ ] `uv run pytest tests/test_integration_tooling_tiers.py` keeps passing untouched — none of
      this introduces a new hook/script-tier violation (all new code lives in `../../../../src/awesome_templates`,
      not `../../../../.claude/hooks` or `../../../../scripts`).
- [ ] `uv run ruff check src/ tests/` clean.
- [ ] `tests/test_markers.py::test_cli_import_does_not_pull_anthropic` (or an equivalent new test)
      confirms `docgen.py` (increment B) never imports `anthropic`, directly or transitively — it
      must stay usable with zero `ai` extra installed, since it now runs unconditionally on every
      `generate`.
- [ ] `awesome-templates generate --help` documents every new flag (`--specialization` from task
      01, `--seed-roadmap` from increment D) — covered by root `../../../../CLAUDE.md`'s "Commands" section
      needing a one-line update once these land.
- [ ] `uv run pytest --cov=awesome_templates` — new modules (`docgen.py`, and the new functions in
      `resolver.py`) held to the same coverage discipline the existing modules already meet (no
      numeric threshold is enforced in `../../../../pyproject.toml` today; match what's already there rather
      than introduce a new gate as part of this task).
