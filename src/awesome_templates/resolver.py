"""Resolve `<!-- KIND: ... -->` markers by asking Anthropic to write
project-grounded prose - the business-logic half of the AI-resolution feature.

This is the programmatic sibling of `.claude/agents/create-from-template.md`:
the agent does an interactive, agents-only pass inside Claude Code; this module
does an all-Markdown pass from `generate --resolve-markers`, deciding what to
ask (the prompts, the context bundle, the confidence/TODO fallback) once per
marker. The actual API round-trip is ai/client.py's job - this module never
imports `anthropic` or touches the SDK directly, so it stays a plain function
of (marker, context) -> prose regardless of which client backs it, and is easy
to unit-test with a fake client. markers.py does the pure scan/splice; this
module decides what each marker should say.

The two marker kinds carry opposite resolution policies: a `TEMPLATE-INIT`
marker is fully resolved away on confident output (or left as a visible TODO
on low confidence), while a `SME REVIEW NEEDED` marker is never resolved
away - render() always keeps its output flagged as an unreviewed AI draft,
and resolve_tree counts it under ResolveSummary.human_review rather than
resolved/todos, regardless of the model's own confidence score.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from awesome_templates.ai import client as ai_client
from awesome_templates.docgen import (
    TEST_COVERAGE_DOC,
    AgentInfo,
    SkillInfo,
    list_agents,
    list_files_under,
    list_skills,
    list_test_files,
)
from awesome_templates.log_helper import NULL_LOG, LogHelper
from awesome_templates.markers import Marker, apply_replacements, scan_tree

MODEL = "claude-opus-4-8"

# Manifests that identify what kind of project the target is, most-specific
# first. Only the first that exists is included in the context bundle.
_MANIFESTS = ("pyproject.toml", "pom.xml", "build.gradle.kts", "build.gradle", "package.json")

_SYSTEM = """\
You are the Template Initializer for a generated Claude Code kit. Each request
gives you one TEMPLATE-INIT instruction from a generated Markdown file plus the
prose surrounding it, and a bundle describing the target project the kit was
generated into.

Treat the target as a real, existing project - the bundle's README/CLAUDE.md,
manifest, and source tree describe a codebase that is already there. Write
declarative, present-tense prose that states the project's actual facts:
name its real modules, files, schemas, entry points, and data flows exactly
as the bundle spells them (`core/orchestrator.py`-style paths, class and
schema names in backticks). Extract aggressively: an architecture summary in
the README or CLAUDE.md, a dependency in the manifest, or a directory name in
the source tree is evidence you are expected to use, not merely permitted to.

Never restate, paraphrase, or summarize the instruction itself - the reader
must see project facts, not a description of what ought to be researched.
Prose containing phrases like "this project's actual ...", "identify the ...",
or "once the codebase ..." is a failure. Ground every claim in the bundle;
do not invent architecture, domain terms, or risk categories that aren't
evidenced there.

Match the voice and format of the surrounding prose. If the marker is inline
in a sentence, return a fragment that reads naturally where the comment sat;
if it stands alone, you may return one or more sentences or a short list.

Return prose only: no `<!-- ... -->` comment syntax and no `{{PLACEHOLDER}}`
tokens. Set confident=true whenever the bundle names the concrete things the
instruction asks about, even if you'd learn more from reading full source
files. Reserve confident=false for a genuinely skeletal target (no real code
or design docs yet) - and even then put your best partial, bundle-grounded
guidance in prose rather than restating the instruction.
"""

_SME_REVIEW_ADDENDUM = """

This marker is kind SME REVIEW NEEDED, not TEMPLATE-INIT: draft a starting
point (e.g. a threat model outline) grounded in the project bundle, but do
not write as though this is a completed review. Your output will always be
displayed as an explicitly unreviewed AI draft regardless of your confidence,
so set confident based only on how well-grounded your draft is.
"""

_USER_TEMPLATE = """\
The marker is {placement}.

Instruction: {instruction}

Prose immediately before the marker:
---
{before}
---

Prose immediately after the marker:
---
{after}
---
"""

_SCHEMA = {
    "type": "object",
    "properties": {
        "confident": {"type": "boolean"},
        "prose": {"type": "string"},
    },
    "required": ["confident", "prose"],
    "additionalProperties": False,
}


@dataclass
class ResolvedMarker:
    marker: Marker
    prose: str
    confident: bool


@dataclass
class ResolveSummary:
    resolved: int = 0
    todos: int = 0
    human_review: int = 0
    files_touched: int = 0
    failed: int = 0


def parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal `.env` parser: `KEY=value` and `export KEY=value`, `#` comments,
    surrounding quotes stripped. Deliberately not python-dotenv - the feature
    needs one variable, not a dependency."""
    env: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return env
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            env[key] = value
    return env


def load_api_key(cwd: Path) -> str | None:
    """ANTHROPIC_API_KEY from the environment, else from a `.env` in cwd."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    return parse_dotenv(cwd / ".env").get("ANTHROPIC_API_KEY") or None


def _read_head(path: Path, limit: int) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except (OSError, UnicodeDecodeError):
        return ""


def gather_context(target: Path, *, char_budget: int = 40_000) -> str:
    """Build a one-shot context bundle describing the target project: its intent
    docs, dependency manifest, source-tree shape, and design docs. Each section
    is labelled and truncated so the whole bundle stays within char_budget."""
    sections: list[str] = []

    for name in ("README.md", "CLAUDE.md", "AGENTS.md", "ARCHITECTURE.md", "docs/README.md"):
        body = _read_head(target / name, 6_000)
        if body.strip():
            sections.append(f"## {name}\n{body}")

    for name in _MANIFESTS:
        manifest = target / name
        if manifest.is_file():
            body = _read_head(manifest, 6_000)
            if body.strip():
                sections.append(f"## {name}\n{body}")
            break

    tree: list[str] = []
    for sub in ("src", "tests", "app", "lib"):
        tree.extend(list_files_under(target / sub, target))
    if tree:
        listing = "\n".join(tree[:300])
        if len(tree) > 300:
            listing += f"\n... (+{len(tree) - 300} more files)"
        sections.append(f"## Source tree\n{listing}")

    for label, pattern in (("ADRs", "docs/adr/*.md"), ("Specs", "docs/specs/*.md")):
        docs = sorted(target.glob(pattern))
        chunks = [f"### {d.relative_to(target).as_posix()}\n{_read_head(d, 2_000)}" for d in docs]
        chunks = [c for c in chunks if c.strip()]
        if chunks:
            sections.append(f"## {label}\n" + "\n\n".join(chunks))

    bundle = "\n\n".join(sections)
    if len(bundle) > char_budget:
        bundle = bundle[:char_budget] + "\n... (context truncated)"
    return bundle or "(the target project has no README, manifest, or source tree yet)"


def resolve_one(client, marker: Marker, context_bundle: str, *, model: str = MODEL) -> ResolvedMarker:
    """Decide what one marker should say: builds the prompt, delegates the
    actual round-trip to ai_client.request_json, and parses the confidence
    signal out of the structured response."""
    placement = "inline within a sentence" if marker.inline else "on its own line"
    user = _USER_TEMPLATE.format(
        placement=placement,
        instruction=marker.instruction,
        before=marker.before or "(start of file)",
        after=marker.after or "(end of file)",
    )
    system = _SYSTEM
    if marker.kind != "TEMPLATE-INIT":
        system += _SME_REVIEW_ADDENDUM
    system += "\n\n# Target project context\n\n" + context_bundle
    data = ai_client.request_json(client, model=model, system=system, user=user, schema=_SCHEMA)
    return ResolvedMarker(
        marker=marker,
        prose=str(data["prose"]).strip(),
        confident=bool(data["confident"]),
    )


def render(resolved: ResolvedMarker) -> str:
    """Turn a resolved marker into the exact text that replaces the comment,
    honouring inline vs block placement, the low-confidence TODO fallback, and
    the SME-review policy (always flagged as an unreviewed draft, regardless
    of confidence - see the module docstring)."""
    marker = resolved.marker
    prose = resolved.prose

    if marker.kind == "SME REVIEW NEEDED":
        head = f"{marker.indent}> **SME REVIEW NEEDED (AI-drafted - verify before relying on this):**"
        body_lines = [f"{marker.indent}> {line}" for line in prose.splitlines() if line.strip()]
        return head + ("\n" + "\n".join(body_lines) if body_lines else "")

    if not resolved.confident:
        head = f"{marker.indent}> **TODO (fill in): {marker.instruction}**"
        body_lines = [f"{marker.indent}> {line}" for line in prose.splitlines() if line.strip()]
        return head + ("\n" + "\n".join(body_lines) if body_lines else "")

    if marker.inline:
        # Stay on one line so the surrounding sentence isn't broken.
        return re.sub(r"\s+", " ", prose).strip()

    bullet = marker.bullet or ""
    lines = prose.splitlines() or [""]
    out = [f"{marker.indent}{bullet}{lines[0]}"]
    for line in lines[1:]:
        out.append(f"{marker.indent}{line}" if line.strip() else "")
    return "\n".join(out)


def resolve_tree(
    out_dir: Path,
    *,
    api_key: str,
    warnings: list[str],
    context_root: Optional[Path] = None,
    make_client=None,
    log: LogHelper = NULL_LOG,
) -> ResolveSummary:
    """Resolve every marker in a generated tree in place.

    Idempotent: a tree with no markers returns a zeroed summary and writes
    nothing. Per-marker API errors are soft (leave the marker, warn, continue);
    an auth error aborts the loop with a single clear warning - in both cases
    the already-valid offline tree is preserved and the caller keeps exit 0.
    make_client lets tests inject a fake client with no network."""
    summary = ResolveSummary()
    markers = scan_tree(out_dir)
    if not markers:
        log.info(f"no markers found under {out_dir} - nothing to resolve")
        return summary
    log.info(f"found {len(markers)} marker(s) to resolve")

    auth_errors, api_errors = ai_client.error_classes()

    log.info("gathering target-project context (README/CLAUDE.md/manifest/source tree)...")
    context_bundle = gather_context(context_root or out_dir)
    client = make_client() if make_client is not None else ai_client.build_client(api_key)

    by_file: dict[Path, list[Marker]] = {}
    for marker in markers:
        by_file.setdefault(marker.path, []).append(marker)

    aborted = False
    for path, file_markers in by_file.items():
        if aborted:
            break
        repls: list[tuple[Marker, str]] = []
        for marker in file_markers:
            log.info(
                f"resolving marker in {path.name} (kind={marker.kind}) - "
                f"calling Anthropic API (model={MODEL})..."
            )
            try:
                resolved = resolve_one(client, marker, context_bundle)
            except auth_errors as exc:  # abort the whole run
                message = (
                    f"marker resolution aborted (authentication error: {exc}) - "
                    "check ANTHROPIC_API_KEY and re-run --resolve-markers"
                )
                warnings.append(message)
                log.error(message)
                summary.failed += 1
                aborted = True
                break
            except api_errors as exc:  # soft: leave this marker, keep going
                message = f"could not resolve a marker in {path.name} ({exc}) - left in place"
                warnings.append(message)
                log.warning(message)
                summary.failed += 1
                continue
            except Exception as exc:  # bad/unexpected response - soft too
                message = f"could not resolve a marker in {path.name} ({exc}) - left in place"
                warnings.append(message)
                log.warning(message)
                summary.failed += 1
                continue

            repls.append((marker, render(resolved)))
            if marker.kind == "SME REVIEW NEEDED":
                summary.human_review += 1
                message = (
                    f"drafted a starting point for a SME REVIEW NEEDED marker in {path.name} - "
                    "still needs human review"
                )
                warnings.append(message)
                log.info(message)
            elif resolved.confident:
                summary.resolved += 1
                log.info(f"resolved marker in {path.name} confidently")
            else:
                summary.todos += 1
                message = (
                    f"low confidence for a marker in {path.name} - left a TODO: {marker.instruction}"
                )
                warnings.append(message)
                log.info(message)

        if repls:
            log.debug(f"writing {len(repls)} replacement(s) back to {path}")
            text = path.read_text(encoding="utf-8")
            path.write_text(apply_replacements(text, repls), encoding="utf-8")
            summary.files_touched += 1

    return summary


# --- AI-assisted tutorial (docs/agent/tutorial.md) --------------------------

# Both presets ship this exact stub - see templates/{python,java}/docs/agent/tutorial.md.
# Compared after stripping, so trailing-whitespace differences don't matter.
_TUTORIAL_STUB = "# Agentic Tutorial"

_TUTORIAL_SYSTEM = """\
You are writing the onboarding tutorial for a generated Claude Code kit, at
docs/agent/tutorial.md. Audience: a developer joining this specific project
who has never used this kit before. Ground every claim in the project bundle
and the actual agent/skill list below - never invent an agent, skill, or
workflow that isn't in that list. Structure: a short "why this exists"
paragraph, then a walkthrough of the 2-3 most useful agents/skills for this
project's actual domain (pick from the real list, don't cover all of them
exhaustively), each with one concrete example invocation. End with "where to
go next" pointing at docs/agent/agents.md, skills.md, and hooks.md.

Return the tutorial as a single Markdown document under the "markdown" key,
starting with a top-level `# ...` heading. No `<!-- ... -->` comment syntax
and no `{{PLACEHOLDER}}` tokens.
"""

_TUTORIAL_SCHEMA = {
    "type": "object",
    "properties": {"markdown": {"type": "string"}},
    "required": ["markdown"],
    "additionalProperties": False,
}


def _format_entity_list(agents: list[AgentInfo], skills: list[SkillInfo]) -> str:
    agent_lines = [f"- `{a.name}`: {a.description or '(no description)'}" for a in agents]
    skill_lines = [
        f"- `{s.name}` ({s.invocation or 'auto'}): {s.description or '(no description)'}"
        for s in skills
    ]
    return (
        "## Agents\n" + ("\n".join(agent_lines) if agent_lines else "(none)")
        + "\n\n## Skills\n" + ("\n".join(skill_lines) if skill_lines else "(none)")
    )


def generate_tutorial(
    client,
    context_bundle: str,
    agents: list[AgentInfo],
    skills: list[SkillInfo],
    *,
    model: str = MODEL,
) -> str:
    """Ask the model for a tutorial grounded in the real agent/skill list, so
    it names things that actually shipped rather than plausible-sounding
    invented ones."""
    user = (
        "# Target project context\n\n" + context_bundle
        + "\n\n# Actual agents and skills shipped in this project's .claude/\n\n"
        + _format_entity_list(agents, skills)
    )
    data = ai_client.request_json(
        client, model=model, system=_TUTORIAL_SYSTEM, user=user, schema=_TUTORIAL_SCHEMA
    )
    return str(data["markdown"]).strip() + "\n"


def maybe_write_tutorial(
    out_dir: Path, client, context_bundle: str, warnings: list[str], log: LogHelper = NULL_LOG
) -> bool:
    """Write docs/agent/tutorial.md via the model, unless it's missing (this
    preset doesn't ship one) or a user already customized it away from the
    shipped stub - the same non-destructive posture resolve_tree already has
    toward markers, applied here to a whole file instead of a comment span.
    Returns whether it actually wrote anything."""
    path = out_dir / "docs" / "agent" / "tutorial.md"
    if not path.is_file():
        log.info(f"{path} does not exist - skipping tutorial generation")
        return False
    if path.read_text(encoding="utf-8").strip() != _TUTORIAL_STUB:
        message = "tutorial.md already customized - left as-is"
        warnings.append(message)
        log.info(message)
        return False

    log.info(f"drafting {path} via Anthropic API (model={MODEL})...")
    try:
        markdown = generate_tutorial(client, context_bundle, list_agents(out_dir), list_skills(out_dir))
    except Exception as exc:  # soft failure: markers already resolved, don't abort the run
        message = f"could not generate docs/agent/tutorial.md ({exc}) - left as stub"
        warnings.append(message)
        log.warning(message)
        return False

    path.write_text(markdown, encoding="utf-8")
    log.info(f"wrote {path}")
    return True


# --- "good first task" roadmap seeding (--seed-roadmap) ---------------------

# Both presets' example milestone lives at this fixed path (see
# templates/{python,java}/docs/roadmap/0001-working-implementation/) - seeding
# replaces its *content* in place, never renames or moves the directory, so
# docs/roadmap/README.md's own link to it keeps working either way.
_ROADMAP_MILESTONE_DIR = "0001-working-implementation"
_ROADMAP_ID = "0001"

# The literal sentence plan.md itself carries, identical in both presets -
# collapsed whitespace so a future rewrap of the source line doesn't matter.
_ROADMAP_SENTINEL = "Replace this whole milestone with your own project's first real milestone"

_ROADMAP_SYSTEM = """\
You are proposing the first real roadmap milestone for a project that just
adopted this generated Claude Code kit, replacing the kit's illustrative
example milestone. Ground the milestone in the project bundle below: propose
a small, concrete, plausible first slice of real work for THIS project, not
a generic example. Keep it small - one task, broken into 2-4 subtasks, each
independently completable in under a day.

Do not invent exact source file paths, package names, or class names - the
project bundle is a summary, not a full read of the codebase, so guessing
specifics risks being wrong. Describe requirements and outcomes in prose;
the developer implementing each subtask decides the concrete specifics once
they start.
"""

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
                "additionalProperties": False,
            },
        },
    },
    "required": ["milestone_title", "task_slug", "task_name", "subtasks"],
    "additionalProperties": False,
}


def propose_first_milestone(client, context_bundle: str, *, model: str = MODEL) -> dict:
    """Ask the model for a small, structured first-milestone plan - content
    only, no file layout. render_milestone turns this into the actual files."""
    user = "# Target project context\n\n" + context_bundle
    return ai_client.request_json(
        client, model=model, system=_ROADMAP_SYSTEM, user=user, schema=_ROADMAP_SCHEMA
    )


def render_milestone(plan: dict) -> dict[str, str]:
    """Pure function: structured plan -> {relative_path: file_content},
    following the exact taxonomy plan.md documents (plan.md + status.md at
    the milestone root, one `{TT.t}-{slug}/README.md` + numbered
    `{NN}-{subtask-slug}.md` subtask files). No model call - this is the same
    content/format split render() in this module already applies to markers.
    Paths are relative to the milestone directory itself (`0001-...-/`)."""
    milestone_title = plan["milestone_title"]
    task_slug = plan["task_slug"]
    task_name = plan["task_name"]
    subtasks = plan["subtasks"]
    task_dir = f"01.0-{task_slug}"

    files: dict[str, str] = {
        "plan.md": (
            f"# Milestone {_ROADMAP_ID} - {milestone_title}\n\n"
            "## Tasks\n\n"
            "| Task | Name |\n"
            "|------|------|\n"
            f"| 01.0 | {task_name} |\n\n"
            f"See [{task_dir}/README.md]({task_dir}/README.md) for the task breakdown.\n"
        ),
        "status.md": (
            f"# Milestone {_ROADMAP_ID} - {milestone_title} - Status\n\n"
            "Tracks progress against [plan.md](plan.md). Updated as each task lands.\n\n"
            "## Current status\n\n"
            "| Task | Name | Status | Tests |\n"
            "|------|------|--------|-------|\n"
            f"| 01.0 | {task_name} | ⬜ Not started | - |\n\n"
            "**Legend:** ✅ Complete · 🔶 In progress / partial · ⬜ Not started\n"
        ),
    }

    subtask_rows = []
    for i, subtask in enumerate(subtasks, start=1):
        num = f"{i:02d}"
        filename = f"{num}-{subtask['slug']}.md"
        subtask_rows.append(f"| {num} | [{subtask['title']}]({filename}) | ⬜ Not started |")
        files[f"{task_dir}/{filename}"] = (
            f"# {num} - {subtask['title']}\n\n"
            "**Parent task:** [README.md](README.md)\n"
            "**Status:** ⬜ Not started\n\n"
            "## Summary\n\n"
            f"{subtask['summary']}\n"
        )

    files[f"{task_dir}/README.md"] = (
        f"# Task 01.0 - {task_name}\n\n"
        "**Parent milestone:** [plan.md](../plan.md)\n"
        "**Status:** ⬜ Not started\n\n"
        "## Subtasks\n\n"
        "| #  | Document | Status |\n"
        "|----|----------|--------|\n" + "\n".join(subtask_rows) + "\n"
    )

    return files


def seed_first_milestone(
    out_dir: Path, client, context_bundle: str, warnings: list[str], log: LogHelper = NULL_LOG
) -> bool:
    """Replace the example milestone's content with an AI-proposed real first
    milestone, unless it's missing (this preset ships none) or the sentinel
    sentence is already gone (a previous run, or the user, already replaced
    it) - mirrors maybe_write_tutorial's idempotency guard. Returns whether it
    actually acted."""
    milestone_dir = out_dir / "docs" / "roadmap" / _ROADMAP_MILESTONE_DIR
    plan_path = milestone_dir / "plan.md"
    if not plan_path.is_file():
        log.info(f"{plan_path} does not exist - skipping roadmap seeding")
        return False
    if _ROADMAP_SENTINEL not in re.sub(r"\s+", " ", plan_path.read_text(encoding="utf-8")):
        message = "roadmap milestone already customized - left as-is"
        warnings.append(message)
        log.info(message)
        return False

    log.info(f"proposing first roadmap milestone via Anthropic API (model={MODEL})...")
    try:
        plan = propose_first_milestone(client, context_bundle)
        files = render_milestone(plan)
    except Exception as exc:  # soft failure: markers/tutorial already resolved, don't abort
        message = f"could not seed the first roadmap milestone ({exc}) - left the example as-is"
        warnings.append(message)
        log.warning(message)
        return False

    log.debug(f"replacing {milestone_dir} with {len(files)} generated file(s)")
    shutil.rmtree(milestone_dir)
    for rel_path, content in files.items():
        target = milestone_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    log.info(f"seeded first roadmap milestone at {milestone_dir}")
    return True


# --- AI-drafted test-convention paragraph (docs/test/code_test_coverage.md) -

# Marks that the paragraph has already been generated once, so a repeat
# `--resolve-markers` run doesn't append a second copy - same append-once
# posture as the marker/tutorial/roadmap guards above, just keyed off a
# sentinel comment instead of a stub string, since this section is additive
# rather than a whole-file replacement.
_CONVENTIONS_SENTINEL = "<!-- test-conventions:generated -->"

_CONVENTIONS_SYSTEM = """\
You are drafting one short paragraph describing the apparent test-authoring
conventions of a project, based ONLY on the list of test file paths below -
you have NOT been given file contents, so never describe what any test
actually does or asserts. Describe only structural patterns observable from
names and layout: e.g. tests mirror the src/ package structure, fixtures are
centralized in a conftest.py, there's one test file per module, integration
tests live in their own directory. If the file list is too sparse to say
anything meaningful, say so plainly instead of guessing.
"""

_CONVENTIONS_SCHEMA = {
    "type": "object",
    "properties": {"paragraph": {"type": "string"}},
    "required": ["paragraph"],
    "additionalProperties": False,
}


def maybe_describe_test_conventions(
    out_dir: Path, client, warnings: list[str], log: LogHelper = NULL_LOG
) -> bool:
    """Append one AI-drafted paragraph of observed test conventions to
    docs/test/code_test_coverage.md, fed only file *names* (never contents) -
    deliberately cheap and fast regardless of project size. No-ops if the doc
    is missing, there are no test files yet, or the paragraph was already
    generated in a previous run (see _CONVENTIONS_SENTINEL)."""
    path = out_dir.joinpath(*TEST_COVERAGE_DOC)
    if not path.is_file():
        log.info(f"{path} does not exist - skipping test-conventions paragraph")
        return False
    text = path.read_text(encoding="utf-8")
    if _CONVENTIONS_SENTINEL in text:
        message = "test conventions paragraph already generated - left as-is"
        warnings.append(message)
        log.info(message)
        return False

    file_names = list_test_files(out_dir)
    if not file_names:
        log.info(f"no test files found under {out_dir / 'tests'} - skipping test-conventions paragraph")
        return False

    log.info(f"drafting test-conventions paragraph via Anthropic API (model={MODEL})...")
    user = "Test file paths:\n" + "\n".join(file_names)
    try:
        data = ai_client.request_json(
            client, model=MODEL, system=_CONVENTIONS_SYSTEM, user=user, schema=_CONVENTIONS_SCHEMA
        )
        paragraph = str(data["paragraph"]).strip()
    except Exception as exc:  # soft failure: earlier increments already ran, don't abort
        message = f"could not describe test conventions ({exc}) - left as-is"
        warnings.append(message)
        log.warning(message)
        return False

    addition = f"\n\n### Observed Conventions\n\n{paragraph}\n\n{_CONVENTIONS_SENTINEL}\n"
    path.write_text(text.rstrip() + addition, encoding="utf-8")
    log.info(f"appended Observed Conventions paragraph to {path}")
    return True
