"""Typer CLI for awesome_templates: generate a project-specific preset
(`.claude/` kit + `docs/` + `scripts/`) from this repo's templates.

\b
Command tree:
  awesome_templates list
  awesome_templates graph [...]
  awesome_templates generate [...]
"""

from __future__ import annotations

import enum
import json
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

from awesome_templates import docgen, harnesses
from awesome_templates.catalog import KINDS, discover, list_presets
from awesome_templates.config import ConfigError, load_config
from awesome_templates.dependencies import (
    build_dependency_graph,
    render_doc,
    write_inline_dependencies,
)
from awesome_templates.dependencies import to_json as graph_to_json
from awesome_templates.log_helper import LogHelper, LogSeverity
from awesome_templates.presets import copy_preset
from awesome_templates.specializations import list_specializations
from awesome_templates.templating import slugify_package, slugify_upper
from awesome_templates.workspace import Workspace


class FullHelpTyperGroup(TyperGroup):
    """Print top-level help plus all nested command help blocks."""

    def get_help(self, ctx: typer.Context) -> str:
        help_text = super().get_help(ctx)
        sections = _collect_subcommand_help(self, ctx)
        if not sections:
            return help_text
        return f"{help_text}\n\n" + "\n\n".join(sections)


def _collect_subcommand_help(group: TyperGroup, ctx: typer.Context) -> list[str]:
    sections: list[str] = []
    for command_name in group.list_commands(ctx):
        command = group.get_command(ctx, command_name)
        if command is None:
            continue
        command_ctx = command.make_context(
            command_name,
            [],
            parent=ctx,
            resilient_parsing=True,
        )
        sections.append(command.get_help(command_ctx))
        if isinstance(command, TyperGroup):
            sections.extend(_collect_subcommand_help(command, command_ctx))
    return sections


REPO_ROOT = Path(__file__).resolve().parents[2]
# The template tree (one self-contained {.claude,docs} tree per preset) lives
# under templates/, kept separate from this package's own source/docs so the
# two are never confused with each other.
TEMPLATES_ROOT = REPO_ROOT / "templates"

# rich_markup_mode=None forces classic Click help rendering (plain text into
# the formatter buffer) instead of typer's default Rich-panel help, which
# prints straight to the live console as a side effect and leaves get_help()
# returning near-empty text - that's what FullHelpTyperGroup needs to be able
# to actually capture and concatenate each subcommand's help text below.
app = typer.Typer(add_completion=False, help=__doc__, cls=FullHelpTyperGroup, rich_markup_mode=None)

console = Console()


class LogVerbosity(str, enum.Enum):
    """Named levels for `graph --log-verbosity`. Absence of the flag is the
    quiet default (level 0); `info` and `debug` map to 1 and 2 respectively."""

    info = "info"
    debug = "debug"


# Ordering used by the `>= 1` / `>= 2` progress gates. The flag being unset
# (None) is level 0 - summary output only.
_LOG_LEVELS: dict[Optional[LogVerbosity], int] = {
    None: 0,
    LogVerbosity.info: 1,
    LogVerbosity.debug: 2,
}


# Enum-backed choices for `generate --harness`, derived from the single source
# of truth in `harnesses.HARNESS_NAMES` so the two never drift. Typer turns an
# enum-typed option into a Click choice, giving free "invalid value" rejection
# (exit code 2) before the command body runs - the same mechanism `LogVerbosity`
# relies on above. It is a `str` enum so each member compares equal to its plain
# name, and `.value` yields that name for the resolved `harness_value`.
HarnessChoice = enum.Enum(  # type: ignore[misc]
    "HarnessChoice",
    {name: name for name in harnesses.HARNESS_NAMES},
    type=str,
)

# Enum-backed choices for `generate --port-to`, following the same pattern as
# HarnessChoice above (the spec's own sample used click.Choice, but this
# environment ships no standalone `click`, only the copy vendored privately
# inside typer). The two porting targets are fixed - claude is never a valid
# `--port-to` value, since it is always the reference harness porting reads
# *from*, never a target. Being a `str` enum, each member compares equal to its
# plain name and `.value` yields that name for dispatch/payload use.
#
# Unlike HarnessChoice, this is NOT derived from harnesses.HARNESS_NAMES -
# keep it manually in sync with the non-claude subset of that tuple if a
# future harness registers as a valid --port-to target.
PortToChoice = enum.Enum(  # type: ignore[misc]
    "PortToChoice",
    {"copilot": "copilot", "junie": "junie"},
    type=str,
)


def _workspace() -> Workspace:
    return Workspace(root=TEMPLATES_ROOT)


def _fail(message: str) -> None:
    console.print(f"[bold red]error:[/bold red] {message}")
    raise typer.Exit(code=1)


def _resolve_preset(workspace: Workspace, preset: Optional[str]) -> str:
    presets = list_presets(workspace)
    if not preset:
        _fail(f"--preset is required (choices: {', '.join(presets)})")
    if preset not in presets:
        _fail(f"unknown preset '{preset}' (choices: {', '.join(presets)})")
    return preset


def _resolve_specializations(workspace: Workspace, preset: str, requested: list[str]) -> list[str]:
    available = list_specializations(workspace, preset)
    unknown = [name for name in requested if name not in available]
    if unknown:
        _fail(
            f"unknown specialization(s) for preset '{preset}': {', '.join(unknown)} "
            f"(choices: {', '.join(available) or 'none'})"
        )
    return requested


@app.command("list")
def list_cmd(
    json_out: bool = typer.Option(False, "--json", help="emit machine-readable JSON"),
) -> None:
    """List presets and the entities each one contains."""
    workspace = _workspace()
    presets = list_presets(workspace)

    if json_out:
        payload = {
            preset: {
                **{kind: discover(Workspace(root=workspace.path(preset))).names(".", kind) for kind in KINDS},
                "specializations": list_specializations(workspace, preset),
            }
            for preset in presets
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    table = Table(title="Presets")
    table.add_column("Name", style="bold")
    for preset in presets:
        table.add_row(preset)
    console.print(table)

    for preset in presets:
        catalog = discover(Workspace(root=workspace.path(preset)))
        console.print(f"\n[bold cyan]{preset}/[/bold cyan]")
        for kind in KINDS:
            names = catalog.names(".", kind)
            if names:
                console.print(f"  [bold]{kind}[/bold]: {', '.join(names)}")
        specializations = list_specializations(workspace, preset)
        if specializations:
            console.print(f"  [bold]specializations[/bold]: {', '.join(specializations)}")


@app.command("graph")
def graph_cmd(
    target: Path = typer.Argument(  # noqa: B008 - Typer requires the call in the default position
        TEMPLATES_ROOT,
        help="path to the directory to analyze (default: templates/)",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    out: str = typer.Option("docs/dependency-graph.md", "--out", help="where to write the rendered graph doc"),
    json_out: bool = typer.Option(False, "--json", help="print the raw graph as JSON instead of writing the doc"),
    inline: bool = typer.Option(
        False,
        "--inline",
        help="also upsert a per-file 'Dependencies' block into every template entity - "
        "MUTATES files in place; review `git diff` before committing",
    ),
    remove: bool = typer.Option(
        False,
        "--remove",
        help="remove per-file 'Dependencies' blocks from every template entity - "
        "MUTATES files in place; review `git diff` before committing",
    ),
    force: bool = typer.Option(False, "--force", help="overwrite existing inline dependency blocks"),
    log_verbosity: Optional[LogVerbosity] = typer.Option(  # noqa: B008 - Typer requires the call in the default position
        None,
        "--log-verbosity",
        "-v",
        help="progress detail: omit for summary only, 'info' for phase progress + "
        "warnings, 'debug' for per-file inline block details",
    ),
) -> None:
    """Render a reference graph and analyze external dependencies.

    Point it at a single preset (e.g. `templates/python`) or an already
    generated project to see that tree's own graph, including its `.claude`
    <-> `docs` connectivity; the default (`templates/`) shows every preset's
    catalog side by side (see catalog.discover)."""
    level = _LOG_LEVELS[log_verbosity]
    if json_out and inline:
        _fail("--inline is not supported together with --json")
        return

    workspace = Workspace(root=target)
    catalog = discover(workspace)
    # If the target has a docs/ dir, scan it for references too.
    docs_dir = workspace.path("docs")
    graph = build_dependency_graph(workspace, catalog, extra_scan_path=docs_dir)
    if json_out:
        typer.echo(json.dumps(graph_to_json(graph), indent=2))
        return
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_doc(graph), encoding="utf-8")
    console.print(
        f"Wrote dependency graph for {target} to {out_path} ({len(graph.nodes)} nodes, {len(graph.edges)} edges)"
    )
    if level >= 1 and graph.missing:
        console.print(f"{len(graph.missing)} unresolved reference(s) in the graph:")
        for ref in sorted(graph.missing, key=lambda r: (r.kind, r.name)):
            console.print(f"  [!] missing {ref.kind}: {ref.name}")
    if inline or remove:
        if inline and remove:
            _fail("--inline and --remove are mutually exclusive")
            return

        action_verb = "Removing" if remove else "Updating"
        if level >= 1:
            console.print(f"{action_verb} inline dependencies in {target}...")
        try:
            updated = write_inline_dependencies(
                workspace,
                catalog,
                log_verbosity=level,
                extra_scan_path=docs_dir,
                force=force,
                remove=remove,
            )
        except RuntimeError as exc:
            _fail(str(exc))
            return

        target_verb = "Removed" if remove else "Updated"
        console.print(
            f"{target_verb} inline Dependencies block in {updated} template file(s) "
            "- review `git diff` before committing."
        )


@app.command()
def generate(
    target_dir: Path = typer.Argument(  # noqa: B008 - Typer requires the call in the default position
        ...,
        help="project directory to analyze (required), e.g. `.`",
    ),
    config_file: Optional[str] = typer.Option(
        None,
        "--config-file",
        help="JSON or TOML config file; CLI flags override it",
    ),
    output_dir: Optional[Path] = typer.Option(  # noqa: B008 - Typer requires the call in the default position
        None,
        "--output-dir",
        help="directory to generate into (default: TARGET_DIR; config `out` when set)",
    ),
    preset: Optional[str] = typer.Option(None, help="which preset to generate (see `awesome_templates list`)"),
    name: Optional[str] = typer.Option(None, help="PROJECT_NAME substitution value"),
    package: Optional[str] = typer.Option(None, help="PROJECT_PACKAGE value (default: slugified --name)"),
    purpose: Optional[str] = typer.Option(None, help="PROJECT_PURPOSE value"),
    slug: Optional[str] = typer.Option(None, help="PROJECT_SLUG_UPPER value (default: derived from --name)"),
    specialization: Optional[List[str]] = typer.Option(  # noqa: B008 - Typer requires the call in the default position
        None,
        "--specialization",
        help="add a specialization's agents/skills on top of the preset "
        "(repeatable; see `awesome-templates list` for choices per preset)",
    ),
    force: Optional[bool] = typer.Option(
        None, "--force/--no-force", help="overwrite existing .claude/, docs/, or scripts/ content"
    ),
    resolve_markers: Optional[bool] = typer.Option(
        None,
        "--resolve-markers/--no-resolve-markers",
        help="AI-resolve <!-- TEMPLATE-INIT --> markers in the generated Markdown "
        "(needs the 'ai' extra and ANTHROPIC_API_KEY)",
    ),
    seed_roadmap: bool = typer.Option(
        False,
        "--seed-roadmap",
        help="replace the example roadmap milestone with an AI-proposed first milestone for "
        "this project - requires --resolve-markers; deletes the example milestone's content",
    ),
    update_guidelines: bool = typer.Option(
        False,
        "--update-guidelines",
        help="create or update README.md, CLAUDE.md, and AGENTS.md at the output root from "
        "the marker-research session - requires --resolve-markers and the `claude` CLI",
    ),
    harness: Optional[HarnessChoice] = typer.Option(  # noqa: B008 - Typer requires the call in the default position
        None,
        "--harness",
        help="which headless CLI runs the marker-research session: claude (default), "
        "copilot, or junie - requires --resolve-markers and that CLI installed/authenticated",
    ),
    port_to: Optional[PortToChoice] = typer.Option(  # noqa: B008 - Typer requires the call in the default position
        None,
        "--port-to",
        help="after the initial Claude-authored .claude/ tree is ready, launch this "
        "harness in its own headless session and task it with porting every agent/ "
        "skill/loop/hook into its own native form - requires --resolve-markers and "
        "--harness claude (the default); the target harness re-authors each kind in "
        "its own idiom, it does not copy files",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="print the plan without writing anything"),
    json_out: bool = typer.Option(False, "--json", help="emit dry-run/summary output as JSON"),
    log_severity: LogSeverity = typer.Option(  # noqa: B008 - Typer requires the call in the default position
        LogSeverity.warning,
        "--log-severity",
        help="live console tracing detail on stderr: error, warning, info, or debug "
        "(each level also shows every louder one; 'info' narrates each copy/docgen/marker/"
        "API-call step, 'debug' adds per-file copy detail; default 'warning' matches the "
        "previous quiet-by-default behavior)",
    ),
) -> None:
    """Generate a project-specific preset (.claude/ kit + docs/ + scripts/) from
    an analysis of TARGET_DIR (e.g. `awesome-templates generate .`)."""
    workspace = _workspace()
    log = LogHelper(severity=log_severity)

    try:
        cfg = load_config(config_file) if config_file else {}
    except ConfigError as exc:
        _fail(str(exc))
        return

    project_cfg = cfg.get("project", {})

    preset_value = preset or cfg.get("preset")
    out_value = str(output_dir) if output_dir is not None else cfg.get("out") or str(target_dir)
    force_value = force if force is not None else bool(cfg.get("force", False))
    resolve_value = resolve_markers if resolve_markers is not None else bool(cfg.get("resolve_markers", False))
    name_value = name or project_cfg.get("name")
    package_value = package or project_cfg.get("package")
    purpose_value = purpose or project_cfg.get("purpose")
    slug_value = slug or project_cfg.get("slug_upper")
    # A repeatable flag replaces the config list wholesale when passed at all -
    # it never merges with config's list. There is no "explicitly zero" via the
    # flag; not passing it is the only way to defer to config.
    specializations_value = specialization if specialization is not None else list(cfg.get("specializations", []))
    # `.value` collapses the enum member to its plain name so `harness_value` is
    # always a `str` (its f-string form and equality checks read cleanly);
    # config-file fallback follows the same "CLI wins" semantics as every other
    # scalar option (not the `--specialization` list-merge exception).
    harness_value = harness.value if harness is not None else cfg.get("harness", "claude")
    # The `--harness` flag itself is gated by the HarnessChoice enum before this
    # point ever runs; only a config-file-sourced value can still be unvalidated
    # (config.py returns the raw parsed dict with no schema check), so it must be
    # checked here too - harnesses.get() has no try/except around it below, and
    # its own docstring already promises callers turn an unknown name into this
    # same _fail(...) shape (mirroring _resolve_preset's unknown-preset case).
    if harness_value not in harnesses.HARNESS_NAMES:
        _fail(f"unknown harness '{harness_value}' (choices: {', '.join(harnesses.HARNESS_NAMES)})")
        return

    preset_value = _resolve_preset(workspace, preset_value)
    if not name_value:
        _fail("--name (or config project.name) is required")
        return
    specializations_value = _resolve_specializations(workspace, preset_value, specializations_value)
    if seed_roadmap and not resolve_value:
        _fail("--seed-roadmap requires --resolve-markers (it needs the same project context/API key)")
        return
    if update_guidelines and not resolve_value:
        _fail("--update-guidelines requires --resolve-markers (it rides the same research session)")
        return
    if harness_value != "claude" and not resolve_value:
        _fail(f"--harness {harness_value} requires --resolve-markers")
        return
    # The two --port-to gates run in fundamental-first order: --resolve-markers
    # (porting has nothing to read without the initial authoring stage) before
    # the --harness claude gate (Claude is always the reference harness porting
    # reads from). Both must be reachable in isolation - see the subtask spec's
    # implementation notes.
    if port_to and not resolve_value:
        _fail(f"--port-to {port_to.value} requires --resolve-markers")
        return
    if port_to and harness_value != "claude":
        _fail(
            f"--port-to {port_to.value} requires --harness claude (the default) - "
            "porting always reads a Claude-authored .claude/ tree"
        )
        return

    subs = {
        "PROJECT_NAME": name_value,
        "PROJECT_PACKAGE": package_value or slugify_package(name_value),
        "PROJECT_SLUG_UPPER": slug_value or slugify_upper(name_value),
        "PROJECT_PURPOSE": purpose_value or "TODO: describe what this project does",
    }

    out_dir = Path(out_value)

    if dry_run:
        payload = {
            "preset": preset_value,
            "out": out_value,
            "substitutions": subs,
            "specializations": specializations_value,
            "harness": harness_value,
            "port_to": port_to.value if port_to else None,
        }
        if resolve_value:
            from awesome_templates.markers import scan_tree

            payload["markers_to_resolve"] = len(scan_tree(workspace.path(preset_value)))
        if json_out:
            typer.echo(json.dumps(payload, indent=2))
        else:
            console.print(f"Would generate preset '{preset_value}' into: {out_dir}")
            console.print(f"Substitutions: {subs}")
            if specializations_value:
                console.print(f"Specializations: {', '.join(specializations_value)}")
            if resolve_value:
                console.print(f"Harness: {harness_value}")
                console.print(f"Would AI-resolve {payload['markers_to_resolve']} marker(s)")
            if port_to:
                console.print(f"Port to: {port_to.value}")
        return

    existing = [d for d in (".claude", "docs", "scripts") if (out_dir / d).exists() and any((out_dir / d).iterdir())]
    if existing and not force_value:
        _fail(f"{', '.join(str(out_dir / d) for d in existing)} already has content - pass --force to overwrite")
        return

    warnings: list[str] = []
    try:
        written = copy_preset(
            workspace,
            preset_value,
            out_dir,
            force_value,
            subs,
            warnings,
            specializations=specializations_value,
            log=log,
        )
    except ValueError as exc:
        _fail(str(exc))
        return

    docgen.write_agent_docs(out_dir, warnings, log=log)
    docgen.write_test_layout_doc(out_dir, warnings, log=log)

    summary = {
        "preset": preset_value,
        "out": str(out_dir),
        "files_written": written,
        "specializations": specializations_value,
        "warnings": warnings,
    }
    summary["harness"] = harness_value

    if resolve_value:
        from awesome_templates import headless, resolver

        api_key = resolver.load_api_key(Path.cwd())
        harness_obj = harnesses.get(harness_value)
        harness_bin = harnesses.find_harness(harness_obj)

        if harness_bin:
            rsum, guidelines_updated = headless.resolve_tree_headless(
                out_dir,
                api_key=api_key,
                warnings=warnings,
                harness=harness_value,
                claude_bin=harness_bin,
                project_root=target_dir,
                update_guidelines=update_guidelines,
                log=log,
            )
            if update_guidelines:
                summary["guidelines_updated"] = guidelines_updated
        elif harness_value != "claude":
            # No silent fallback for a non-default harness (plan.md non-goal):
            # substituting a different vendor's model for the one the user
            # explicitly asked for would be a surprising, unrequested behavior
            # change.
            #
            # The junie sub-branch below is unreachable with today's real
            # registry: task 03.0's spike confirmed Junie DOES have a headless
            # mode, so `_JUNIE.binary_names == ("junie",)` is non-empty and this
            # harness falls through to the generic "not found on PATH" message
            # like copilot. It stays implemented (not dead-code-removed) because
            # `binary_names=()` is the *signal* task 03.0 subtask 02's registration
            # contract defines for "no headless mode exists" - if a future change
            # ever re-registers junie that way (a JetBrains regression, or this
            # milestone's outcome-2 path if ever revisited), this branch is what
            # turns that back into the honest message instead of a misleading
            # generic one. Do not flip `_JUNIE.binary_names` to `()` to "make this
            # reachable" - that would incorrectly disable working Junie support.
            if harness_value == "junie" and not harness_obj.binary_names:
                _fail(
                    "Junie has no supported headless CLI mode yet - "
                    "see docs/roadmap/0001-alternative-harness-support/03.0-junie-adapter/ "
                    "or use --harness claude"
                )
            else:
                _fail(
                    f"{harness_value} CLI not found on PATH - install it (or check "
                    f"authentication), or use --harness claude"
                )
            return
        else:
            # harness_value == "claude": today's unchanged fallback behavior.
            if update_guidelines:
                _fail(
                    "--update-guidelines needs the `claude` CLI on PATH "
                    "(it runs a headless Claude Code research session)"
                )
                return
            if not api_key:
                _fail(
                    "--resolve-markers needs the `claude` CLI on PATH, or ANTHROPIC_API_KEY "
                    "(in the environment or a .env in the cwd) for the one-shot API fallback"
                )
                return
            message = (
                "claude CLI not found on PATH - falling back to one-shot API marker "
                "resolution (weaker research); install Claude Code for the full research pass"
            )
            warnings.append(message)
            log.warning(message)
            try:
                from awesome_templates.ai import client as ai_client

                fallback_client = ai_client.build_client(api_key)
            except ModuleNotFoundError:
                _fail("--resolve-markers needs the 'ai' extra: pip install awesome_templates[ai]")
                return
            rsum = resolver.resolve_tree(
                out_dir,
                api_key=api_key,
                warnings=warnings,
                context_root=target_dir,
                make_client=lambda: fallback_client,
                log=log,
            )
        summary["markers_resolved"] = rsum.resolved
        summary["markers_todo"] = rsum.todos
        summary["markers_human_review"] = rsum.human_review
        summary["markers_failed"] = rsum.failed

        # The remaining increments are still one-shot Messages API calls (see
        # the design doc's follow-up note) - they need an explicit API key and
        # the 'ai' extra, and are skipped softly without them since the
        # research pass above already did the load-bearing work.
        summary["tutorial_written"] = False
        summary["test_conventions_described"] = False
        if seed_roadmap:
            summary["roadmap_seeded"] = False
        client = None
        if api_key:
            try:
                from awesome_templates.ai import client as ai_client

                client = ai_client.build_client(api_key)
            except ModuleNotFoundError:
                message = (
                    "the 'ai' extra is not installed - skipped the tutorial/test-conventions"
                    + ("/roadmap" if seed_roadmap else "")
                    + " increments (pip install awesome_templates[ai])"
                )
                warnings.append(message)
                log.warning(message)
        else:
            message = (
                "ANTHROPIC_API_KEY not set - skipped the tutorial/test-conventions"
                + ("/roadmap" if seed_roadmap else "")
                + " increments (they call the Messages API directly)"
            )
            warnings.append(message)
            log.warning(message)
        if client is not None:
            context_bundle = resolver.gather_context(target_dir)
            summary["tutorial_written"] = resolver.maybe_write_tutorial(
                out_dir,
                client,
                context_bundle,
                warnings,
                log=log,
            )
            if seed_roadmap:
                summary["roadmap_seeded"] = resolver.seed_first_milestone(
                    out_dir,
                    client,
                    context_bundle,
                    warnings,
                    log=log,
                )
            summary["test_conventions_described"] = resolver.maybe_describe_test_conventions(
                out_dir,
                client,
                warnings,
                log=log,
            )

        # Chained porting stage: only reached once the initial Claude authoring/
        # marker-research session above has run and `summary` is fully populated
        # (this milestone's one-invocation pipeline shape). A missing target
        # binary is a hard failure - the user explicitly asked for the port, so a
        # warn-and-skip would silently drop it. `port` is imported lazily here to
        # keep the offline `generate` path free of it, matching headless/resolver.
        if port_to:
            from awesome_templates import port

            try:
                port_summary = port.port_tree_headless(
                    out_dir,
                    harness=port_to.value,
                    warnings=warnings,
                    project_root=target_dir,
                    log=log,
                )
            except RuntimeError as exc:
                _fail(str(exc))
                return
            summary["ported_to"] = port_to.value
            summary["ported_kinds"] = port_summary.manifest_kinds
            summary["port_command_ok"] = port_summary.command_ok

    if json_out:
        typer.echo(json.dumps(summary, indent=2))
    else:
        console.print(f"Wrote preset '{preset_value}' to {out_dir} ({written} file(s))")
        if specializations_value:
            console.print(f"Specializations: {', '.join(specializations_value)}")
        if resolve_value:
            console.print(
                f"Resolved {summary['markers_resolved']} marker(s); "
                f"left {summary['markers_todo']} as TODO; "
                f"{summary['markers_human_review']} drafted for human review; "
                f"{summary['markers_failed']} failed"
            )
            if summary["tutorial_written"]:
                console.print("Wrote docs/agent/tutorial.md")
            if seed_roadmap and summary.get("roadmap_seeded"):
                console.print("Seeded the first roadmap milestone")
            if update_guidelines and summary.get("guidelines_updated"):
                console.print(f"Guideline docs created/updated: {', '.join(summary['guidelines_updated'])}")
            if port_to and summary.get("ported_to"):
                ported = ", ".join(f"{n} {k}" for k, n in summary["ported_kinds"].items() if n)
                status = "ok" if summary["port_command_ok"] else "see warnings"
                console.print(f"Ported to {summary['ported_to']} ({ported or 'nothing to port'}) - {status}")
        if warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for w in warnings:
                console.print(f"  - {w}")


if __name__ == "__main__":
    app()
