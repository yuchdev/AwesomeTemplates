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
import os
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


def _not_implemented(message: str) -> None:
    """Report a valid-but-unbuilt request and exit non-zero.

    Deliberately distinct from `_fail`, which means "you asked for something
    invalid". This means "you asked for something this version cannot do yet" -
    a different thing to tell a user, and the reason `HARNESS_NAMES` stays
    wider than what actually runs (see `harnesses.IMPLEMENTED_HARNESS_NAMES`).
    The exit code is still 1, so a script driving `generate` sees a failure
    either way and never mistakes an unbuilt path for a completed run.
    """
    console.print(f"[bold yellow]not implemented:[/bold yellow] {message}")
    raise typer.Exit(code=1)


def sanity_check(
    *,
    harness_value: Optional[str],
    api_key: Optional[str],
    api_key_env: Optional[str],
    resolve_markers: bool,
    seed_roadmap: bool,
    update_guidelines: bool,
    port_to: Optional[str],
) -> None:
    """Validate every AI-stage flag combination, or exit.

    Extracted out of `generate`'s body as a single named function so the
    precedence between the gates is explicit and testable in isolation rather
    than emerging from where each `if` happens to sit between config
    resolution and the dry-run branch. The order below is deliberate and
    fundamental-first - each check may assume the ones above it passed:

    1. **Known names.** The Typer enum already rejects an unknown `--harness`
       on the command line, but a value sourced from `--config-file` bypasses
       it entirely (`config.py` returns the raw parsed dict with no schema
       check), so it is re-checked here.
    2. **AI-stage prerequisites.** `--seed-roadmap`, `--update-guidelines` and
       `--port-to` are all riders on `--resolve-markers`; they cannot be
       satisfied without it.
    3. **`--harness` is mandatory for an AI run** and meaningless without one.
       There is no default: a silent default is exactly how a run ends up
       quietly picking a vendor, or quietly authenticating a way the user
       never chose.
    4. **`--api-key`/`--api-key-env` are credential flags, not an engine
       choice** - they only ever change how the *same* harness subprocess
       authenticates (see `headless.resolve_tree_headless`'s `api_key`
       parameter), never what runs. So they: are mutually exclusive with each
       other; require `--harness` to be given (there is no session to
       authenticate otherwise); and are rejected for a harness whose
       `api_key_env` is `None` (copilot/junie authenticate only via their own
       login, with no env-var slot for a key to fill).
    5. **`--port-to` needs the reference harness.** Porting always reads a
       Claude-authored `.claude/` tree.
    6. **Not-implemented last**, so a user who asks for an unbuilt harness
       *and* makes a flag mistake hears about the mistake first - the more
       actionable of the two.

    :param harness_value: resolved `--harness` value (CLI, then config), or None.
    :param api_key: resolved `--api-key` value, or None.
    :param api_key_env: resolved `--api-key-env` value (a variable *name*, not
        its value - see `generate`'s body for where that's read), or None.
    :param resolve_markers: resolved `--resolve-markers`.
    :param seed_roadmap: `--seed-roadmap`.
    :param update_guidelines: `--update-guidelines`.
    :param port_to: `--port-to` value, or None.
    :raises typer.Exit: via `_fail` / `_not_implemented` on any violation.
    """
    # 1. Known names (a config-file value never passed through the Typer enum).
    if harness_value is not None and harness_value not in harnesses.HARNESS_NAMES:
        _fail(f"unknown harness '{harness_value}' (choices: {', '.join(harnesses.HARNESS_NAMES)})")
        return

    # 2. Riders on the AI stage.
    if seed_roadmap and not resolve_markers:
        _fail("--seed-roadmap requires --resolve-markers (it needs the same project research)")
        return
    if update_guidelines and not resolve_markers:
        _fail("--update-guidelines requires --resolve-markers (it rides the same research session)")
        return
    if port_to and not resolve_markers:
        _fail(f"--port-to {port_to} requires --resolve-markers")
        return

    # 3. No default harness, in either direction.
    if resolve_markers and harness_value is None:
        _fail(
            "--resolve-markers requires --harness "
            f"{'|'.join(harnesses.HARNESS_NAMES)}. There is no default: which CLI runs, and "
            "how it authenticates, is always your choice to state"
        )
        return
    if not resolve_markers and harness_value is not None:
        _fail(
            f"--harness {harness_value} has no effect without --resolve-markers - plain `generate` "
            "is fully offline and calls no model; drop --harness or add --resolve-markers"
        )
        return

    # 4. Credential flags pair with --harness; they never select an engine.
    if api_key is not None and api_key_env is not None:
        _fail("--api-key and --api-key-env are mutually exclusive - pass at most one")
        return
    if (api_key is not None or api_key_env is not None) and harness_value is None:
        flag = "--api-key" if api_key is not None else "--api-key-env"
        _fail(f"{flag} requires --harness - it authenticates that harness's session, nothing else")
        return
    if (api_key is not None or api_key_env is not None) and harnesses.get(harness_value).api_key_env is None:
        flag = "--api-key" if api_key is not None else "--api-key-env"
        _fail(f"--harness {harness_value} authenticates via its own login only - {flag} doesn't apply to it")
        return

    # 5. Porting reads a Claude-authored tree.
    if port_to and harness_value != "claude":
        _fail(f"--port-to {port_to} requires --harness claude - porting always reads a Claude-authored .claude/ tree")
        return

    # 6. Valid, but not built yet.
    if harness_value is not None and harness_value not in harnesses.IMPLEMENTED_HARNESS_NAMES:
        _not_implemented(
            f"--harness {harness_value} is not implemented yet - the only working harness "
            f"today is --harness {'|'.join(harnesses.IMPLEMENTED_HARNESS_NAMES)}"
        )
        return


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
        help="AI-resolve <!-- TEMPLATE-INIT --> markers in the generated Markdown - "
        "requires --harness; plain generate is offline",
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
        help="which installed headless CLI runs the marker-research session: claude, "
        "copilot, or junie. Mandatory for --resolve-markers; there is no default. Only "
        "'claude' is implemented today - the others exit with a not-implemented notice",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="authenticate the --harness session with this literal credential instead "
        "of the CLI's own login (e.g. an Anthropic API key for --harness claude). Never "
        "read from --config-file - pass it on the command line only. Note: a value passed "
        "this way is visible to other processes on this machine (e.g. `ps`) for the life "
        "of the command - prefer --api-key-env where that matters",
    ),
    api_key_env: Optional[str] = typer.Option(
        None,
        "--api-key-env",
        help="authenticate the --harness session with the value of this variable, read "
        "from YOUR shell environment (e.g. --api-key-env ANTHROPIC_API_KEY, or any "
        "variable name you've put the key in). Mutually exclusive with --api-key; "
        "omitting both means the harness authenticates however it already does (its own "
        "login) - this is the default and never changes what runs, only how it "
        "authenticates",
    ),
    port_to: Optional[PortToChoice] = typer.Option(  # noqa: B008 - Typer requires the call in the default position
        None,
        "--port-to",
        help="after the initial Claude-authored .claude/ tree is ready, launch this "
        "harness in its own headless session and task it with porting every agent/ "
        "skill/loop/hook into its own native form - requires --resolve-markers and "
        "--harness claude; the target harness re-authors each kind in its own idiom, "
        "it does not copy files",
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
    # `.value` collapses the enum member to its plain name so this is always a
    # `str` (its f-string form and equality checks read cleanly); the
    # config-file fallback follows the same "CLI wins" semantics as every other
    # scalar option (not the `--specialization` list-merge exception).
    #
    # No default. A default harness is what let a run silently pick a vendor
    # the user never named; the absence of one here is load-bearing, not an
    # oversight. `sanity_check` below is what turns "not given, but the AI
    # stage was requested" into an error, and what re-validates a
    # config-file-sourced name that never passed through the Typer enum.
    harness_value = harness.value if harness is not None else cfg.get("harness")
    # --api-key never has a config-file fallback - a literal credential has no
    # business living in a checked-in config file (this repo's own secret-scan
    # hook exists for exactly this reason). --api-key-env only ever names a
    # variable, not a secret, so it gets the same CLI-wins config fallback
    # every other scalar option has.
    api_key_env_value = api_key_env or cfg.get("api_key_env")

    preset_value = _resolve_preset(workspace, preset_value)
    if not name_value:
        _fail("--name (or config project.name) is required")
        return
    specializations_value = _resolve_specializations(workspace, preset_value, specializations_value)
    sanity_check(
        harness_value=harness_value,
        api_key=api_key,
        api_key_env=api_key_env_value,
        resolve_markers=resolve_value,
        seed_roadmap=seed_roadmap,
        update_guidelines=update_guidelines,
        port_to=port_to.value if port_to else None,
    )

    # Resolve the actual credential to forward (never logged/printed - only
    # `auth_label` below, which names the *source*, is ever surfaced) now that
    # sanity_check has confirmed the flag combination itself is coherent. This
    # runs before the `if dry_run:` branch below on purpose: a --dry-run with a
    # broken --api-key-env should fail the same way a real run would, not
    # silently defer the check to whenever the run is actually made real.
    api_key_value = api_key
    if api_key_env_value:
        resolved = os.environ.get(api_key_env_value)
        if not resolved:
            _fail(f"--api-key-env {api_key_env_value} names a variable that isn't set")
            return
        api_key_value = resolved
    auth_label = "login"
    if api_key is not None:
        auth_label = "api-key"
    elif api_key_env_value:
        auth_label = f"api-key-env:{api_key_env_value}"

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
            "auth": auth_label,
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
                console.print(f"Auth: {auth_label}")
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
    summary["auth"] = auth_label

    if resolve_value:
        from awesome_templates import headless

        # sanity_check has already guaranteed --harness was named and that it
        # is an implemented one (today: `claude`), so there is no
        # harness-selection logic left to do here - only "is it installed?".
        harness_obj = harnesses.get(harness_value)
        harness_bin = harnesses.find_harness(harness_obj)
        if harness_bin is None:
            # A missing binary is a hard failure, never a quiet substitution -
            # there is no other engine to fall back to.
            _fail(f"the `{harness_value}` CLI was not found on PATH - install it (or check its authentication)")
            return

        rsum, guidelines_updated = headless.resolve_tree_headless(
            out_dir,
            # api_key_value is None unless --api-key/--api-key-env was given
            # (see above); passing None here makes headless.py strip the
            # relevant env var from the inherited environment, so the session
            # authenticates however the installed CLI already does (typically
            # its own login) rather than ever reading an ambient credential
            # implicitly. Forwarding a key is only ever an explicit request.
            api_key=api_key_value,
            warnings=warnings,
            harness=harness_value,
            claude_bin=harness_bin,
            project_root=target_dir,
            update_guidelines=update_guidelines,
            log=log,
        )
        if update_guidelines:
            summary["guidelines_updated"] = guidelines_updated
        summary["markers_resolved"] = rsum.resolved
        summary["markers_todo"] = rsum.todos
        summary["markers_human_review"] = rsum.human_review
        summary["markers_failed"] = rsum.failed

        # The three remaining increments (tutorial, roadmap seed,
        # test-conventions paragraph) are direct Messages API calls in
        # resolver.py, with no wiring into any headless harness session and no
        # other engine to run them through - `generate` only ever executes a
        # --harness session now. They are reported as skipped rather than
        # silently omitted.
        summary["tutorial_written"] = False
        summary["test_conventions_described"] = False
        if seed_roadmap:
            summary["roadmap_seeded"] = False
        message = (
            "skipped the tutorial/test-conventions"
            + ("/roadmap-seed" if seed_roadmap else "")
            + f" increment(s): they are direct Messages API calls, and --harness {harness_value} "
            "runs no API calls of its own. Nothing was sent to any vendor API."
        )
        warnings.append(message)
        log.warning(message)

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
