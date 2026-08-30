"""Headless-Claude-Code marker research - the agentic half of
`generate --resolve-markers`.

Design: docs/roadmap/0001-ai-assisted-generation/03.Agentic_marker_research.md.
Instead of one stateless Messages API call per marker (resolver.resolve_one,
kept as the fallback when the `claude` CLI is absent), this module runs ONE
headless Claude Code session over the whole marker manifest: the model gets
real Read/Grep/Glob access to the researched project, edits every marker file
in place, and facts learned resolving one marker stay in context for the next.
Results are reconciled by diffing markers.scan_tree before/after the session -
never by trusting the model's self-report.

The research method and hard rules embedded in _PROMPT_* below are a re-embed
of `.claude/agents/create-from-template.md` (this repo's interactive agent),
not a runtime read of that file - a pip-installed copy of this package has no
clone of the repo on disk, and two files that read each other drift less
obviously than one string owned here. Keep the two aligned when either changes.

Two roots matter and are usually the same directory:

- the *kit root* (`out_dir`): the generated `.claude/` + `docs/` + `scripts/`
  tree whose Markdown carries the markers - the only place the session edits;
- the *project root*: the codebase the markers ask about. With the documented
  `generate .` usage they coincide; when the target directory is a scratch
  directory that contains no project of its own (no manifest, no `src/`),
  detect_project_root falls back to the `generate` invocation's cwd, so the
  research still reads the real project the kit was generated for.

Testability mirrors resolver.py's fake-client pattern at the subprocess
boundary: resolve_tree_headless takes `run=` (defaulting to subprocess.run),
so tests assert on the constructed argv/prompt and simulate the session's
edits without a real `claude` on PATH.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from awesome_templates import harnesses
from awesome_templates.log_helper import NULL_LOG, LogHelper
from awesome_templates.markers import Marker, scan_tree
from awesome_templates.resolver import ResolveSummary

# The guideline docs --update-guidelines maintains at the kit root, in the
# order the prompt presents them.
GUIDELINE_FILES = ("README.md", "CLAUDE.md", "AGENTS.md")

# Hard tool allowlist for the unattended session - the same grant
# create-from-template.md's own `allowed-tools:` frontmatter carries, no
# Bash and no network tools regardless of the ambient install's defaults.
# Write is added only under --update-guidelines (guideline files may not
# exist yet at the kit root; marker files always do, so markers need Edit only).
_BASE_TOOLS = ("Read", "Grep", "Glob", "Edit", "TodoWrite")

_TIMEOUT_SECONDS = 3600

# Signals the fallback markers-turned-TODO / SME-draft conventions leave in
# resolved files. Reconciliation counts these before and after the session,
# so it must match the exact formats _PROMPT_RULES dictates below (which are
# themselves resolver.render's formats, so both resolution paths produce
# byte-identical fallbacks).
_TODO_RE = re.compile(r"> \*\*TODO \(fill in\): (?P<instruction>.*?)\*\*")
_SME_RE = re.compile(r"> \*\*SME REVIEW NEEDED \(AI-drafted")

# A directory "looks like a project" when it carries a dependency manifest or
# a populated src/ tree. Deliberately a superset of resolver's _MANIFESTS:
# that list picks ONE manifest to inline into a context bundle, this one only
# answers "is there a real project here at all".
_PROJECT_HINTS = (
    "pyproject.toml",
    "setup.py",
    "pom.xml",
    "build.gradle.kts",
    "build.gradle",
    "package.json",
    "Cargo.toml",
    "go.mod",
)


def _looks_like_project(root: Path) -> bool:
    if any((root / hint).is_file() for hint in _PROJECT_HINTS):
        return True
    src = root / "src"
    return src.is_dir() and any(src.iterdir())


def detect_project_root(out_dir: Path, cwd: Path) -> Path:
    """The project the research session should read: out_dir itself when it
    holds a real project (the documented `generate .` usage), else the `generate`
    invocation's cwd when *that* does (the generate-into-a-scratch-dir case),
    else out_dir - a genuinely skeletal target, which the prompt tells the
    model to answer honestly with TODOs rather than fabrication."""
    out_dir = out_dir.resolve()
    cwd = cwd.resolve()
    if _looks_like_project(out_dir):
        return out_dir
    if _looks_like_project(cwd):
        return cwd
    return out_dir


def _rel_or_abs(path: Path, base: Path) -> str:
    """path relative to base when it sits under base, else absolute - the
    session runs with cwd=base, so relative paths resolve there."""
    try:
        rel = path.resolve().relative_to(base.resolve())
    except ValueError:
        return str(path.resolve())
    return "." if str(rel) == "." else rel.as_posix()


def render_manifest(markers: list[Marker], kit_root: Path, project_root: Path) -> str:
    """The closed work list embedded in the prompt: one row per marker, paths
    as the session (cwd=project_root) will address them. Handing the model
    the complete set up front - rather than letting it grep for markers - is
    both what shares research across markers and what closes the unattended
    scope-creep hole (see the design doc's "Scope and safety" section)."""
    rows = ["| # | File | Kind | Instruction |", "|---|------|------|-------------|"]
    for i, marker in enumerate(markers, start=1):
        path = _rel_or_abs(marker.path, project_root)
        instruction = marker.instruction.replace("|", "\\|")
        rows.append(f"| {i} | `{path}` | {marker.kind} | {instruction} |")
    return "\n".join(rows)


_PROMPT_INTRO = """\
You are the Template Initializer, running non-interactively. `awesome-templates
generate` produced a Claude Code kit (`.claude/` agents/skills/hooks/loops plus
`docs/` and `scripts/`) for a target project. Deterministic placeholder
substitution already ran; what remains are markers - facts about *this specific
project's* domain, architecture, or risk surface that no find-and-replace could
fill in, because they only exist once someone actually reads the project's code.
Your job is to research the project for real and write what you find directly
into the marker locations listed below.
"""

_PROMPT_METHOD = """\
## Research the project first

Before answering any marker, build a real mental model of the project at the
project root, grounded in what is actually there, not what its name suggests:

1. **Shape**: Glob the source tree (`src/**`, `tests/**`, or the equivalent) to
   see what modules exist and how they are organized. Read the dependency
   manifest (`pyproject.toml`, `pom.xml`, `package.json`, or equivalent) - it is
   a strong signal of what kind of system this is.
2. **Intent**: Read the project's `README.md`, `CLAUDE.md`, `AGENTS.md`,
   `ARCHITECTURE.md`, `docs/adr/*.md`, and `docs/specs/*.md` where present -
   these carry the *why*, which agent prose needs more than a directory listing
   gives you.
3. **Entry points and data flow**: find the main entry points (CLI command, API
   app, worker loop) and trace what data enters and leaves the system, and
   through what untrusted boundary.
4. **Risk surface**: note anything handling secrets, PII, external or
   attacker-influenced input, or money/compliance-sensitive data - markers about
   security or review priorities need this.

Then read each marker file itself and open whatever source files each marker's
instruction requires - markers asking for "concrete modules", "hot paths", or
"specific input categories" must be answered from files you actually opened.
If the project is genuinely skeletal (no real logic yet), say so honestly per
the rules below - never fabricate specifics from a thin signal.
"""

_PROMPT_RULES = """\
## Resolution rules

For each marker, edit its file and replace the entire `<!-- ... -->` comment
(nothing else) with prose answering its instruction:

- Write declarative, present-tense facts naming real modules, files, schemas,
  and data flows, with paths and identifiers in backticks. Every fact must
  trace to something you actually read - never invent architecture, domain
  terms, or risk categories.
- Never restate or paraphrase the instruction. Output containing "this
  project's actual ...", "identify the ...", or "once the codebase ..." is a
  failure.
- Match the surrounding voice and format: an inline marker (mid-sentence) gets
  a fragment on the same line that reads naturally in place; a block marker may
  become one or more sentences or a short list at the same indentation (keep
  any leading list bullet).
- A `TEMPLATE-INIT` marker you cannot answer with real confidence (the project
  genuinely lacks the signal) becomes exactly:
  `> **TODO (fill in): <the marker's instruction>**`
  optionally followed by `> `-prefixed lines of your best partial facts.
- A `SME REVIEW NEEDED` marker is never resolved silently: draft a grounded
  starting point, but it must begin with exactly:
  `> **SME REVIEW NEEDED (AI-drafted - verify before relying on this):**`
  followed by `> `-prefixed draft lines, regardless of your confidence.
- Leave no `<!-- ... -->` marker comments and no `{{PLACEHOLDER}}` tokens in
  any file you touch; leave every line you were not asked to change untouched.

The manifest above is the closed set of files you may edit. Do not edit any
file not listed there, do not scan for further markers beyond the list, and
never write outside the kit root.
"""

_PROMPT_GUIDELINES = """\
## Guideline docs

After the markers, create or update these three files at the kit root, each
grounded in the same research (never invented): {files}.

- `README.md`: what the project is and does, how it is organized, how to build
  and test it. If one already exists at the kit root, update it in place -
  correct what research contradicts, fill gaps, keep its structure and any
  content research confirms.
- `CLAUDE.md`: guidance for Claude Code working in this project - a concise
  architecture map (real modules and their roles), the actual build/test/lint
  commands, and project-specific conventions or invariants you observed.
- `AGENTS.md`: the same guidance in agent-agnostic form for other coding
  agents; keep it briefer than CLAUDE.md and do not simply duplicate it.

Where the kit root and the project root differ, these files describe the
*project* but are written at the *kit root* - never overwrite the project's
own top-level docs.
"""

_PROMPT_OUTRO = """\
## When you are done

Print a short per-file summary: for each manifest file, how many markers you
resolved, left as TODO, or drafted for SME review{guidelines_summary}. This
summary is logged for a human; the files themselves are the deliverable.
"""


def build_prompt(
    markers: list[Marker],
    *,
    kit_root: Path,
    project_root: Path,
    update_guidelines: bool,
) -> str:
    """Assemble the whole session prompt: intro, roots, manifest, method,
    rules, optional guidelines section. Pure function - unit-tested directly,
    and what a future --dry-run would print."""
    kit = _rel_or_abs(kit_root, project_root)
    if kit == ".":
        roots = "Project root and kit root are both the current working directory: research here, edit here."
    else:
        roots = (
            "The project root is the current working directory - research there "
            f"(read-only evidence). The kit root is `{kit}` - the generated tree "
            "whose files you edit. The kit's own `.claude/` and `docs/` content "
            "is generic scaffolding, not evidence about the project."
        )

    sections = [
        _PROMPT_INTRO,
        roots,
        "## Marker manifest\n\n"
        + (
            render_manifest(markers, kit_root, project_root)
            if markers
            else "(no markers - see the guideline docs section below)"
        ),
        _PROMPT_METHOD,
        _PROMPT_RULES,
    ]
    if update_guidelines:
        files = ", ".join(f"`{_rel_or_abs(kit_root / f, project_root)}`" for f in GUIDELINE_FILES)
        sections.append(_PROMPT_GUIDELINES.format(files=files))
    sections.append(
        _PROMPT_OUTRO.format(
            guidelines_summary=("; then which guideline docs you created or updated" if update_guidelines else "")
        )
    )
    return "\n\n".join(section.rstrip() for section in sections) + "\n"


def _count_fallbacks(paths: set[Path]) -> tuple[dict[str, int], int]:
    """(TODO-instruction multiset, SME-draft count) across paths - the
    before/after halves of reconciliation both use this."""
    todos: dict[str, int] = {}
    sme = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for m in _TODO_RE.finditer(text):
            key = m.group("instruction")
            todos[key] = todos.get(key, 0) + 1
        sme += len(_SME_RE.findall(text))
    return todos, sme


def resolve_tree_headless(
    out_dir: Path,
    *,
    api_key: Optional[str],
    warnings: list[str],
    harness: str = "claude",
    claude_bin: Optional[str] = None,
    project_root: Optional[Path] = None,
    update_guidelines: bool = False,
    model: Optional[str] = None,
    run=subprocess.run,
    log: LogHelper = NULL_LOG,
) -> tuple[ResolveSummary, list[str]]:
    """Run the headless research session and reconcile what it did.

    Returns (summary, guideline files created/updated). Idempotent the same
    way resolve_tree is: a tree with no markers (and no --update-guidelines)
    skips the subprocess entirely. A failed or partial session is soft - the
    already-valid offline tree is preserved, remaining markers are counted as
    failed with a warning, and the caller keeps exit 0."""
    summary = ResolveSummary()
    before = scan_tree(out_dir)
    if not before and not update_guidelines:
        log.info(f"no markers found under {out_dir} - nothing to resolve")
        return summary, []

    harness_obj = harnesses.get(harness)
    resolved_model = model or harness_obj.default_model
    claude_bin = claude_bin or harnesses.find_harness(harness_obj)
    if claude_bin is None:
        raise RuntimeError(f"the `{harness}` CLI is not on PATH")

    project_root = (project_root or detect_project_root(out_dir, Path.cwd())).resolve()
    log.info(
        f"found {len(before)} marker(s); researching project at {project_root} "
        f"via one headless {harness} session (model={resolved_model})"
    )

    marker_files = {m.path for m in before}
    guideline_paths = {out_dir / f for f in GUIDELINE_FILES} if update_guidelines else set()
    watched = marker_files | guideline_paths
    snapshot = {}
    for path in watched:
        try:
            snapshot[path] = path.read_text(encoding="utf-8")
        except OSError:
            snapshot[path] = None  # doesn't exist yet (guideline files)

    todos_before, sme_drafts_before = _count_fallbacks(marker_files)
    prompt = build_prompt(
        before,
        kit_root=out_dir,
        project_root=project_root,
        update_guidelines=update_guidelines,
    )
    # Tool selection depends on update_guidelines, a marker-research concept the
    # harness registry has no business knowing about, so it is computed here and
    # handed to the harness's build_command rather than inside it.
    tools = _BASE_TOOLS + (("Write",) if update_guidelines else ())
    cmd = harness_obj.build_command(claude_bin, tools=tools, model=resolved_model, prompt=prompt)
    # An explicit key (env or .env - see resolver.load_api_key) is forwarded
    # only for harnesses that authenticate through ANTHROPIC_API_KEY; without
    # one (or for a harness with its own auth) the session authenticates however
    # the installed CLI already does (typically the user's own login). A
    # non-forwarding harness must have the key stripped from the inherited env,
    # not merely left unset - the developer may already have it exported.
    env = {**os.environ}
    if api_key and harness_obj.forwards_anthropic_key:
        env["ANTHROPIC_API_KEY"] = api_key
    else:
        env.pop("ANTHROPIC_API_KEY", None)

    # claude receives its prompt over stdin (prompt_via="stdin"); a harness that
    # takes the prompt as an argv element instead embeds it in cmd already.
    run_kwargs = {"input": prompt} if harness_obj.prompt_via == "stdin" else {"input": None}

    # For prompt_via="arg" the prompt (marker manifest + gathered project
    # context) is an argv element, so it must be redacted before the command is
    # logged; the stdin case never carries it in cmd.
    if harness_obj.prompt_via == "arg":
        logged_cmd = [f"<prompt: {len(prompt)} chars>" if part == prompt else part for part in cmd]
    else:
        logged_cmd = cmd
    log.debug(f"headless command: {' '.join(logged_cmd)}")
    try:
        proc = run(
            cmd,
            cwd=str(project_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            **run_kwargs,
        )
    except subprocess.TimeoutExpired:
        message = f"headless research session timed out after {_TIMEOUT_SECONDS}s - reconciling whatever it completed"
        warnings.append(message)
        log.warning(message)
        proc = None
    except OSError as exc:
        # An oversized argv (prompt_via="arg" with many markers / large context)
        # can exceed ARG_MAX and raise E2BIG; degrade gracefully like the
        # timeout path rather than crashing the whole generate run.
        message = (
            f"headless research session failed to start ({exc}) - the prompt may be too large "
            "for this harness's argv limits; falling back to no session"
        )
        warnings.append(message)
        log.warning(message)
        proc = None

    if proc is not None:
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-500:]
            message = (
                f"headless research session exited with code {proc.returncode}"
                + (f": {tail}" if tail else "")
                + " - reconciling whatever it completed"
            )
            warnings.append(message)
            log.warning(message)
        elif proc.stdout:
            log.info("session summary:\n" + proc.stdout.strip()[-2000:])

    # Reconciliation: the before/after scan diff is the source of truth, not
    # the model's self-report (see the design doc).
    after = scan_tree(out_dir)
    after_by_kind: dict[str, int] = {}
    for marker in after:
        if marker.path in marker_files:
            after_by_kind[marker.kind] = after_by_kind.get(marker.kind, 0) + 1
            message = f"marker left unresolved in {marker.path.name}: {marker.instruction}"
            warnings.append(message)
            log.warning(message)
            summary.failed += 1

    todos_after, sme_drafts_after = _count_fallbacks(marker_files)
    for instruction, count in todos_after.items():
        new = count - todos_before.get(instruction, 0)
        for _ in range(new):
            summary.todos += 1
            message = f"low confidence for a marker - left a TODO: {instruction}"
            warnings.append(message)
            log.info(message)

    summary.human_review = max(0, sme_drafts_after - sme_drafts_before)
    if summary.human_review:
        message = f"drafted {summary.human_review} SME REVIEW NEEDED marker(s) - still need human review"
        warnings.append(message)
        log.info(message)

    before_ti = sum(1 for m in before if m.kind == "TEMPLATE-INIT")
    after_ti = after_by_kind.get("TEMPLATE-INIT", 0)
    summary.resolved = max(0, before_ti - after_ti - summary.todos)
    if summary.resolved:
        log.info(f"resolved {summary.resolved} marker(s) from research")

    guidelines_updated: list[str] = []
    for path in sorted(watched):
        try:
            now = path.read_text(encoding="utf-8")
        except OSError:
            now = None
        if now == snapshot[path]:
            continue
        if path in marker_files:
            summary.files_touched += 1
        if path in guideline_paths and now is not None:
            guidelines_updated.append(path.name)
            log.info(f"guideline doc created/updated: {path}")

    if update_guidelines:
        missing = [f for f in GUIDELINE_FILES if f not in guidelines_updated and snapshot.get(out_dir / f) is None]
        for name in missing:
            message = f"--update-guidelines: session did not produce {name}"
            warnings.append(message)
            log.warning(message)

    return summary, guidelines_updated
