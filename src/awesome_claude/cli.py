"""Typer CLI for awesome-claude: generate a project-specific preset
(`.claude/` kit + `docs/` + `scripts/`) from this repo's templates.

\b
Command tree:
  awesome-claude list
  awesome-claude graph [...]
  awesome-claude generate [...]
"""

from __future__ import annotations

import enum
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

from awesome_claude.catalog import KINDS, discover, list_presets
from awesome_claude.config import ConfigError, load_config
from awesome_claude.dependencies import (
    build_dependency_graph,
    render_doc,
    write_inline_dependencies,
)
from awesome_claude.dependencies import to_json as graph_to_json
from awesome_claude.presets import copy_preset
from awesome_claude.templating import slugify_package, slugify_upper
from awesome_claude.workspace import Workspace


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
app = typer.Typer(
    add_completion=False, help=__doc__, cls=FullHelpTyperGroup, rich_markup_mode=None
)

console = Console()


class LogVerbosity(str, enum.Enum):
    """Named levels for `graph --log-verbosity`. Absence of the flag is the
    quiet default (level 0); `info` and `debug` map to 1 and 2 respectively."""

    info = "info"
    debug = "debug"


# Ordering used by the `>= 1` / `>= 2` progress gates. The flag being unset
# (None) is level 0 - summary output only.
_LOG_LEVELS: dict[LogVerbosity | None, int] = {
    None: 0,
    LogVerbosity.info: 1,
    LogVerbosity.debug: 2,
}


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
                kind: discover(Workspace(root=workspace.path(preset))).names(".", kind)
                for kind in KINDS
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


@app.command("graph")
def graph_cmd(
    target: Path = typer.Argument(
        TEMPLATES_ROOT,
        help="path to the directory to analyze (default: templates/)",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    out: str = typer.Option(
        "docs/dependency-graph.md", "--out", help="where to write the rendered graph doc"
    ),
    json_out: bool = typer.Option(
        False, "--json", help="print the raw graph as JSON instead of writing the doc"
    ),
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
    force: bool = typer.Option(
        False, "--force", help="overwrite existing inline dependency blocks"
    ),
    log_verbosity: Optional[LogVerbosity] = typer.Option(
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
        f"Wrote dependency graph for {target} to {out_path} "
        f"({len(graph.nodes)} nodes, {len(graph.edges)} edges)"
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
    config: Optional[str] = typer.Option(
        None, "--config", help="JSON or TOML config file; CLI flags override it"
    ),
    preset: Optional[str] = typer.Option(
        None, help="which preset to generate (see `awesome-claude list`)"
    ),
    name: Optional[str] = typer.Option(None, help="PROJECT_NAME substitution value"),
    package: Optional[str] = typer.Option(
        None, help="PROJECT_PACKAGE value (default: slugified --name)"
    ),
    purpose: Optional[str] = typer.Option(None, help="PROJECT_PURPOSE value"),
    slug: Optional[str] = typer.Option(
        None, help="PROJECT_SLUG_UPPER value (default: derived from --name)"
    ),
    out: Optional[str] = typer.Option(
        None, help="project directory to generate into (default: .); "
        "gets .claude/, docs/, and scripts/ subdirectories"
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
    dry_run: bool = typer.Option(
        False, "--dry-run", help="print the plan without writing anything"
    ),
    json_out: bool = typer.Option(False, "--json", help="emit dry-run/summary output as JSON"),
) -> None:
    """Generate a project-specific preset (.claude/ kit + docs/ + scripts/)."""
    workspace = _workspace()

    try:
        cfg = load_config(config) if config else {}
    except ConfigError as exc:
        _fail(str(exc))
        return

    project_cfg = cfg.get("project", {})

    preset_value = preset or cfg.get("preset")
    out_value = out if out is not None else cfg.get("out", ".")
    force_value = force if force is not None else bool(cfg.get("force", False))
    resolve_value = (
        resolve_markers
        if resolve_markers is not None
        else bool(cfg.get("resolve_markers", False))
    )
    name_value = name or project_cfg.get("name")
    package_value = package or project_cfg.get("package")
    purpose_value = purpose or project_cfg.get("purpose")
    slug_value = slug or project_cfg.get("slug_upper")

    preset_value = _resolve_preset(workspace, preset_value)
    if not name_value:
        _fail("--name (or config project.name) is required")
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
        }
        if resolve_value:
            from awesome_claude.markers import scan_tree

            payload["markers_to_resolve"] = len(scan_tree(workspace.path(preset_value)))
        if json_out:
            typer.echo(json.dumps(payload, indent=2))
        else:
            console.print(f"Would generate preset '{preset_value}' into: {out_dir}")
            console.print(f"Substitutions: {subs}")
            if resolve_value:
                console.print(f"Would AI-resolve {payload['markers_to_resolve']} marker(s)")
        return

    existing = [
        d
        for d in (".claude", "docs", "scripts")
        if (out_dir / d).exists() and any((out_dir / d).iterdir())
    ]
    if existing and not force_value:
        _fail(
            f"{', '.join(str(out_dir / d) for d in existing)} already has content - "
            "pass --force to overwrite"
        )
        return

    warnings: list[str] = []
    written = copy_preset(workspace, preset_value, out_dir, force_value, subs, warnings)

    summary = {
        "preset": preset_value,
        "out": str(out_dir),
        "files_written": written,
        "warnings": warnings,
    }

    if resolve_value:
        try:
            from awesome_claude import resolver
        except ModuleNotFoundError:
            _fail("--resolve-markers needs the 'ai' extra: pip install awesome-claude[ai]")
            return
        api_key = resolver.load_api_key(Path.cwd())
        if not api_key:
            _fail("--resolve-markers needs ANTHROPIC_API_KEY (in the environment or a .env in the cwd)")
            return
        rsum = resolver.resolve_tree(out_dir, api_key=api_key, warnings=warnings)
        summary["markers_resolved"] = rsum.resolved
        summary["markers_todo"] = rsum.todos
        summary["markers_failed"] = rsum.failed

    if json_out:
        typer.echo(json.dumps(summary, indent=2))
    else:
        console.print(f"Wrote preset '{preset_value}' to {out_dir} ({written} file(s))")
        if resolve_value:
            console.print(
                f"Resolved {summary['markers_resolved']} marker(s); "
                f"left {summary['markers_todo']} as TODO; "
                f"{summary['markers_failed']} failed"
            )
        if warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for w in warnings:
                console.print(f"  - {w}")


if __name__ == "__main__":
    app()
