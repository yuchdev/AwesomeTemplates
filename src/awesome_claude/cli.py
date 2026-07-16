"""Typer CLI for awesome-claude: generate project-specific Claude Code kits
and starter documents from this repo's templates.

Command tree:
  awesome-claude list
  awesome-claude graph [...]
  awesome-claude generate [...]
  awesome-claude docs copy [...]
  awesome-claude docs new adr "<title>"
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from awesome_claude.catalog import CATEGORIES, KINDS, PRESETS, discover
from awesome_claude.config import ConfigError, load_config
from awesome_claude.dependencies import build_dependency_graph, render_doc, write_inline_dependencies
from awesome_claude.dependencies import to_json as graph_to_json
from awesome_claude.docs_scaffold import copy_docs_tree
from awesome_claude.doctemplates import DOC_TYPES, DocTemplateError, render_new_document
from awesome_claude.requirements import check_target_requirements
from awesome_claude.selection import Selection, SelectionError
from awesome_claude.settings import build_settings
from awesome_claude.templating import copy_entity, slugify_package, slugify_upper
from awesome_claude.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
# The template tree (core/helpers/java/orchestrators/python/docs) lives under
# templates/, kept separate from this package's own source/docs so the two
# are never confused with each other.
TEMPLATES_ROOT = REPO_ROOT / "templates"

app = typer.Typer(add_completion=False, help=__doc__)
docs_app = typer.Typer(add_completion=False, help="Copy or scaffold docs/ content.")
app.add_typer(docs_app, name="docs")

console = Console()


def _workspace() -> Workspace:
    return Workspace(root=TEMPLATES_ROOT)


def _fail(message: str) -> None:
    console.print(f"[bold red]error:[/bold red] {message}")
    raise typer.Exit(code=1)


@app.command("list")
def list_cmd(
    json_out: bool = typer.Option(False, "--json", help="emit machine-readable JSON"),
) -> None:
    """List presets, categories, and the entities available in each."""
    catalog = discover(_workspace())

    if json_out:
        payload = {
            "presets": PRESETS,
            "categories": {
                cat: {kind: catalog.names(cat, kind) for kind in KINDS} for cat in CATEGORIES
            },
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    table = Table(title="Presets")
    table.add_column("Name", style="bold")
    table.add_column("Categories")
    for preset_name, cats in PRESETS.items():
        table.add_row(preset_name, ", ".join(cats))
    console.print(table)

    for cat in CATEGORIES:
        console.print(f"\n[bold cyan]{cat}/[/bold cyan]")
        for kind in KINDS:
            names = catalog.names(cat, kind)
            if names:
                console.print(f"  [bold]{kind}[/bold]: {', '.join(names)}")


@app.command("graph")
def graph_cmd(
    out: str = typer.Option(
        "docs/dependency-graph.md", "--out", help="where to write the rendered graph doc"
    ),
    json_out: bool = typer.Option(
        False, "--json", help="print the raw graph as JSON instead of writing the doc"
    ),
    inline: bool = typer.Option(
        False,
        "--inline",
        help="also upsert a per-file 'Dependencies' block into every templates/** entity - "
        "MUTATES templates/** in place; review `git diff` before committing",
    ),
) -> None:
    """Render this repo's own agent/hook/loop/skill reference graph (maintainer tool, docs-only)."""
    if json_out and inline:
        _fail("--inline is not supported together with --json")
        return
    workspace = _workspace()
    catalog = discover(workspace)
    graph = build_dependency_graph(workspace, catalog)
    if json_out:
        typer.echo(json.dumps(graph_to_json(graph), indent=2))
        return
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_doc(graph), encoding="utf-8")
    console.print(f"Wrote dependency graph to {out_path} ({len(graph.nodes)} nodes, {len(graph.edges)} edges)")
    if inline:
        updated = write_inline_dependencies(workspace, catalog)
        console.print(
            f"Updated inline Dependencies block in {updated} template file(s) under templates/** "
            "- review `git diff` before committing."
        )


@app.command()
def generate(
    config: str | None = typer.Option(
        None, "--config", help="JSON or TOML config file; CLI flags override it"
    ),
    preset: str | None = typer.Option(
        None, help=f"start from a predefined category set ({', '.join(sorted(PRESETS))})"
    ),
    categories: str | None = typer.Option(
        None, help="comma-separated category list, e.g. core,python"
    ),
    include: list[str] = typer.Option(
        [], "--include", help="add one entity: agent|hook|loop|skill:NAME (repeatable)"
    ),
    exclude: list[str] = typer.Option(
        [], "--exclude", help="remove one entity, same form (repeatable)"
    ),
    name: str | None = typer.Option(None, help="PROJECT_NAME substitution value"),
    package: str | None = typer.Option(
        None, help="PROJECT_PACKAGE value (default: slugified --name)"
    ),
    purpose: str | None = typer.Option(None, help="PROJECT_PURPOSE value"),
    slug: str | None = typer.Option(
        None, help="PROJECT_SLUG_UPPER value (default: derived from --name)"
    ),
    out: str | None = typer.Option(None, help="output directory (default: .claude)"),
    force: bool | None = typer.Option(
        None, "--force/--no-force", help="overwrite a non-empty --out/--docs-out"
    ),
    no_settings: bool | None = typer.Option(
        None, "--no-settings/--settings", help="skip writing settings.json"
    ),
    copy_docs: bool | None = typer.Option(
        None, "--copy-docs/--no-copy-docs", help="also copy docs/ (with {{PLACEHOLDER}} substitution)"
    ),
    docs_out: str | None = typer.Option(None, help="where --copy-docs writes to (default: docs)"),
    check_requirements: bool | None = typer.Option(
        None,
        "--check-requirements/--no-check-requirements",
        help="warn about files the selection assumes exist",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="print the plan without writing anything"
    ),
    json_out: bool = typer.Option(False, "--json", help="emit dry-run/summary output as JSON"),
) -> None:
    """Generate a project-specific .claude/ kit (and optionally docs/)."""
    workspace = _workspace()
    catalog = discover(workspace)

    try:
        cfg = load_config(config) if config else {}
    except ConfigError as exc:
        _fail(str(exc))
        return

    project_cfg = cfg.get("project", {})
    docs_cfg = cfg.get("docs", {})

    preset = preset or cfg.get("preset")
    out_value = out if out is not None else cfg.get("out", ".claude")
    force_value = force if force is not None else bool(cfg.get("force", False))
    no_settings_value = (
        no_settings if no_settings is not None else bool(cfg.get("no_settings", False))
    )
    copy_docs_value = copy_docs if copy_docs is not None else bool(docs_cfg.get("copy", False))
    docs_out_value = docs_out if docs_out is not None else docs_cfg.get("out", "docs")
    check_requirements_value = (
        check_requirements
        if check_requirements is not None
        else bool(cfg.get("check_requirements", False))
    )
    name_value = name or project_cfg.get("name")
    package_value = package or project_cfg.get("package")
    purpose_value = purpose or project_cfg.get("purpose")
    slug_value = slug or project_cfg.get("slug_upper")
    include_tokens = list(cfg.get("include", [])) + include
    exclude_tokens = list(cfg.get("exclude", [])) + exclude

    selection = Selection.empty()
    try:
        if preset:
            if preset not in PRESETS:
                raise SelectionError(
                    f"unknown preset '{preset}' (choices: {', '.join(sorted(PRESETS))})"
                )
            for cat in PRESETS[preset]:
                selection.add_category(catalog, cat)
        for cat in cfg.get("categories", []):
            selection.add_category(catalog, cat)
        if categories:
            for cat in (c.strip() for c in categories.split(",") if c.strip()):
                selection.add_category(catalog, cat)
        selection.apply_tokens(catalog, include_tokens, adding=True)
        selection.apply_tokens(catalog, exclude_tokens, adding=False)
    except SelectionError as exc:
        _fail(str(exc))
        return

    if selection.is_empty():
        _fail("nothing selected - use --preset, --categories, and/or --include (flags or --config)")
        return
    if not name_value:
        _fail("--name (or config project.name) is required")
        return

    subs = {
        "PROJECT_NAME": name_value,
        "PROJECT_PACKAGE": package_value or slugify_package(name_value),
        "PROJECT_SLUG_UPPER": slug_value or slugify_upper(name_value),
        "PROJECT_PURPOSE": purpose_value or "TODO: describe what this project does",
    }

    plan = {
        cat: {kind: sorted(names) for kind, names in kinds.items() if names}
        for cat, kinds in selection.entries.items()
        if any(kinds.values())
    }

    warnings: list[str] = []
    if check_requirements_value:
        check_target_requirements(selection, warnings)

    if dry_run:
        payload = {
            "out": out_value,
            "substitutions": subs,
            "plan": plan,
            "copy_docs": copy_docs_value,
            "docs_out": docs_out_value if copy_docs_value else None,
            "warnings": warnings,
        }
        if json_out:
            typer.echo(json.dumps(payload, indent=2))
        else:
            console.print(f"Would write to: {out_value}")
            console.print(f"Substitutions: {subs}")
            console.print("Plan:")
            for cat, kinds in plan.items():
                console.print(f"  {cat}/")
                for kind, names in kinds.items():
                    console.print(f"    {kind}: {', '.join(names)}")
            if not no_settings_value and workspace.path("core", "settings.json").exists():
                console.print("  settings.json: yes")
            if copy_docs_value:
                console.print(f"  docs/ -> {docs_out_value} (templated with substitutions)")
            if warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for w in warnings:
                    console.print(f"  - {w}")
        return

    out_dir = Path(out_value)
    if out_dir.exists() and any(out_dir.iterdir()) and not force_value:
        _fail(f"'{out_dir}' is not empty - pass --force to overwrite")
        return

    written: dict[str, dict[str, list[str]]] = {}
    for cat, kinds in selection.entries.items():
        for kind in KINDS:
            for entity_name in sorted(kinds[kind]):
                src = catalog.entries[cat][kind][entity_name]
                dst = (
                    out_dir / kind / entity_name if kind == "skills" else out_dir / kind / src.name
                )
                copy_entity(src, dst, kind, subs, warnings)
                written.setdefault(kind, {}).setdefault(cat, []).append(entity_name)

    settings_written = False
    if not no_settings_value:
        settings = build_settings(workspace, selection, subs, warnings)
        if settings is not None:
            (out_dir / "settings.json").write_text(
                json.dumps(settings, indent=2) + "\n", encoding="utf-8"
            )
            settings_written = True

    docs_written: int | None = None
    if copy_docs_value:
        docs_out_dir = Path(docs_out_value)
        if docs_out_dir.exists() and any(docs_out_dir.iterdir()) and not force_value:
            warnings.append(
                f"docs copy skipped: '{docs_out_dir}' is not empty - pass --force to overwrite"
            )
        else:
            docs_written = copy_docs_tree(workspace, docs_out_dir, force_value, subs, warnings)

    summary = {
        "out": str(out_dir),
        "written": written,
        "settings.json": settings_written,
        "docs_copied": docs_written,
        "warnings": warnings,
    }
    if json_out:
        typer.echo(json.dumps(summary, indent=2))
    else:
        console.print(f"Wrote kit to {out_dir}")
        for kind, by_cat in written.items():
            for cat, names in by_cat.items():
                console.print(f"  {kind}/ <- {cat}: {', '.join(names)}")
        console.print(f"  settings.json: {'written' if settings_written else 'skipped'}")
        if docs_written is not None:
            console.print(f"  docs/: {docs_written} file(s) copied to {docs_out_value}")
        if warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for w in warnings:
                console.print(f"  - {w}")


@docs_app.command("copy")
def docs_copy(
    name: str | None = typer.Option(None, help="PROJECT_NAME substitution value"),
    package: str | None = typer.Option(
        None, help="PROJECT_PACKAGE value (default: slugified --name)"
    ),
    purpose: str | None = typer.Option(None, help="PROJECT_PURPOSE value"),
    slug: str | None = typer.Option(
        None, help="PROJECT_SLUG_UPPER value (default: derived from --name)"
    ),
    out: str = typer.Option("docs", "--out", help="where to copy docs/ to"),
    force: bool = typer.Option(False, "--force", help="overwrite existing files"),
) -> None:
    """Copy this repo's docs/ tree, applying {{PLACEHOLDER}} substitution (same engine as generate)."""
    if not name:
        _fail("--name is required")
        return
    workspace = _workspace()
    out_dir = Path(out)
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        _fail(f"'{out_dir}' is not empty - pass --force to overwrite")
        return
    subs = {
        "PROJECT_NAME": name,
        "PROJECT_PACKAGE": package or slugify_package(name),
        "PROJECT_SLUG_UPPER": slug or slugify_upper(name),
        "PROJECT_PURPOSE": purpose or "TODO: describe what this project does",
    }
    warnings: list[str] = []
    count = copy_docs_tree(workspace, out_dir, force, subs, warnings)
    console.print(f"docs/: {count} file(s) copied to {out_dir}")
    if warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in warnings:
            console.print(f"  - {w}")


@docs_app.command("new")
def docs_new(
    doc_type: str = typer.Argument(
        ..., help=f"doc type to scaffold ({', '.join(sorted(DOC_TYPES))})"
    ),
    title: str = typer.Argument(..., help="document title"),
    status: str = typer.Option("Proposed", help="initial status field"),
) -> None:
    """Scaffold a new document from a real template (e.g. `docs new adr "My decision"`)."""
    workspace = _workspace()
    try:
        out_path = render_new_document(workspace, doc_type, title, status=status)
    except DocTemplateError as exc:
        _fail(str(exc))
        return
    console.print(f"Wrote {out_path}")


if __name__ == "__main__":
    app()
