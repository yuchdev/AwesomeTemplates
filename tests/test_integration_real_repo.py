"""Tests that exercise the package against THIS repo's real template tree.

These exist because round 2's REPO_ROOT-resolution bug (an off-by-one
`.parent` after `generate.py` moved) was only caught by manual smoke testing.
A synthetic-fixture unit test can't catch "the real repo layout doesn't
match what the code assumes" - only running against the real tree can.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from awesome_templates import model_policy, model_state
from awesome_templates.catalog import discover, list_presets
from awesome_templates.cli import app
from awesome_templates.dependencies import build_dependency_graph
from awesome_templates.markers import scan_tree
from awesome_templates.model_catalog import FETCHERS
from awesome_templates.model_policy import PolicyMode, load_policy, scan_generation
from awesome_templates.specializations import disallowed_kinds_present, list_specializations
from awesome_templates.templating import PLACEHOLDER_RE
from awesome_templates.workspace import Workspace

REAL_REPO_ROOT = Path(__file__).resolve().parents[1]

runner = CliRunner()


def _real_policy() -> model_policy.ModelPolicy:
    """The repo's policy: model-policy.toml (strictness) over the packaged models.template.json (data).
    Never the per-user state file, so these checks cannot depend on whose machine they run on."""
    return load_policy(REAL_REPO_ROOT / "model-policy.toml", fallback=model_state.load_template())


def test_templates_root_is_separate_from_the_package_root(real_workspace):
    # templates/ holds the generated-kit source material; pyproject.toml and
    # src/ are this package's own files and must NOT live under templates/.
    assert real_workspace.root == REAL_REPO_ROOT / "templates"
    assert (REAL_REPO_ROOT / "model-policy.toml").is_file()
    assert not (real_workspace.root / "pyproject.toml").exists()


def test_workspace_root_resolves_to_the_actual_preset_trees(real_workspace):
    # "common" is a non-selectable tree (see presets.COMMON_PRESET_NAME /
    # catalog.RESERVED_PRESET_NAMES) merged into every real preset at generate
    # time - never itself a preset list_presets() should surface.
    assert list_presets(real_workspace) == ["cpp", "frontend", "java", "macos", "python"]
    assert (real_workspace.root / "python" / ".claude").is_dir()
    assert (real_workspace.root / "python" / "docs" / "adr" / "README.md").is_file()
    assert (real_workspace.root / "common" / "docs" / "adr" / "template.md").is_file()


def test_discover_against_real_repo_finds_expected_entities(real_workspace):
    python_catalog = discover(Workspace(root=real_workspace.path("python")))
    assert "python-expert" in python_catalog.names(".", "agents")
    assert "post-mortem" not in python_catalog.names(".", "skills")  # deleted in round 2

    common_catalog = discover(Workspace(root=real_workspace.path("common")))
    assert "task-verifier" in common_catalog.names(".", "agents")


@pytest.mark.parametrize("preset", ["python", "java", "frontend", "macos"])
def test_generated_preset_has_no_dangling_doc_references(preset, tmp_path):
    # A preset is one self-contained tree copied verbatim (see presets.py), so
    # a freshly generated project must never have a dangling @docs/ reference.
    proj = tmp_path / "proj"
    result = runner.invoke(
        app,
        ["generate", str(proj), "--preset", preset, "--name", "Big", "--package", "big"],
    )
    assert result.exit_code == 0, result.stdout
    assert (proj / ".claude").is_dir()
    assert (proj / "docs").is_dir()
    assert (proj / "scripts").is_dir()

    workspace = Workspace(root=proj)
    catalog = discover(workspace)
    graph = build_dependency_graph(workspace, catalog, extra_scan_path=workspace.path("docs"))
    broken_docs = [r for r in graph.missing if r.kind == "doc"]
    assert broken_docs == []


@pytest.mark.parametrize("preset", ["python", "java", "frontend", "macos"])
def test_generated_preset_passes_its_own_link_checker(preset):
    """Generate the preset, then run the generated project's own
    `scripts/check_doc_links.py` inside it.

    Much stronger than the `@docs/`-only graph check above: this validates every
    relative `[text](path)` link *and* every `#anchor` across `docs/` and
    `.claude/`. It has caught a skill pointing at a reference file whose name
    differed only by British/American spelling, an ADR inventory row for an ADR
    that was never written, a "full documentation" link to a doc only the
    upstream reference project had, and ~20 `#anchor` refs whose explicit
    `<a id="...">` targets were stripped when a style guide was adapted.

    Checking the *generated* tree rather than `templates/<preset>/` is deliberate
    and load-bearing: a link like `../../../python/docs/dev/foo.md` resolves fine
    inside `templates/` (where the other preset is a sibling) while being broken
    in every real generated project. Only running the checker post-generation
    catches that class.
    """
    checker_in_template = REAL_REPO_ROOT / "templates" / preset / "scripts" / "check_doc_links.py"
    if not checker_in_template.is_file():
        pytest.skip(f"{preset} ships no scripts/check_doc_links.py")

    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "proj"
        result = runner.invoke(
            app,
            ["generate", str(proj), "--preset", preset, "--name", "Link Check", "--package", "link_check"],
        )
        assert result.exit_code == 0, result.stdout
        # `cwd=proj` is required, not cosmetic: the checker's default path list is
        # ["."], so running it from anywhere else silently scans that other tree
        # and reports a cheerful zero.
        proc = subprocess.run(
            [sys.executable, str(proj / "scripts" / "check_doc_links.py"), "docs", ".claude"],
            cwd=str(proj),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert proc.returncode == 0, (
            f"generated {preset} project has broken doc links/anchors:\n{proc.stdout}\n{proc.stderr}"
        )
        # Guard the guard: if the scan ever silently covers nothing, fail loudly.
        assert "0 file(s) scanned" not in proc.stdout, f"checker scanned nothing:\n{proc.stdout}"


@pytest.mark.parametrize("preset", ["python", "java", "frontend", "macos"])
def test_preset_never_links_outside_its_own_tree(preset):
    """A preset must be self-contained: no relative link may escape its own root.

    `templates/java/docs/dev/java_android_coding_standard.md` once pointed at
    `../../../python/docs/dev/python_coding_standard.md` - valid within
    `templates/`, meaningless once generated, since a real project has no sibling
    preset. Catching it by path shape reports the actual mistake ("escapes the
    preset") instead of a confusing "file not found" against a temp directory.
    """
    preset_root = (REAL_REPO_ROOT / "templates" / preset).resolve()
    link_re = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    escapes: list[str] = []
    for md in preset_root.rglob("*.md"):
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1):
            for target in link_re.findall(line):
                target = target.split()[0].split("#")[0]
                if not target or target.startswith(("http://", "https://", "mailto:", "/")):
                    continue
                resolved = (md.parent / target).resolve()
                if preset_root not in resolved.parents and resolved != preset_root:
                    escapes.append(f"{md.relative_to(preset_root)}:{lineno} -> {target}")
    assert escapes == [], f"links escaping templates/{preset}/ (they break once generated):\n" + "\n".join(escapes)


def test_example_config_generates_with_no_unresolved_markdown_placeholders(tmp_path):
    # awesome-templates.example.toml is the documented --config-file example (see
    # README.md's "Config file" section) - it must actually work end to end,
    # and every deterministic {{PLACEHOLDER}} token it fills in must leave no
    # trace in the generated Markdown. docs/adr/template.md's own `{{ seq }}`
    # / `{{ title }}` placeholders belong to the shipped ADR skeleton and are
    # intentionally left for authors to fill. PLACEHOLDER_RE correctly ignores
    # them because they aren't the all-caps `{{WORD}}` shape it matches.
    config_path = REAL_REPO_ROOT / "awesome-templates.example.toml"
    proj = tmp_path / "proj"
    result = runner.invoke(app, ["generate", ".", "--config-file", str(config_path), "--output-dir", str(proj)])
    assert result.exit_code == 0, result.stdout
    assert "Warnings:" not in result.stdout

    md_files = list(proj.rglob("*.md"))
    assert md_files  # sanity: didn't just generate an empty tree

    leftover = [f for f in md_files if PLACEHOLDER_RE.search(f.read_text(encoding="utf-8"))]
    assert leftover == []


def test_real_preset_agents_doc_lists_every_real_agent_file(tmp_path):
    proj = tmp_path / "proj"
    result = runner.invoke(
        app,
        ["generate", str(proj), "--preset", "python", "--name", "Big", "--package", "big"],
    )
    assert result.exit_code == 0, result.stdout

    # A generated project's agents are merged from both templates/common/ (shared
    # across every preset, see presets.COMMON_PRESET_NAME) and templates/python/
    # (preset-specific) - see this file's own "every real agent file" claim.
    agent_stems = {p.stem for p in (REAL_REPO_ROOT / "templates" / "python" / ".claude" / "agents").glob("*.md")}
    agent_stems |= {p.stem for p in (REAL_REPO_ROOT / "templates" / "common" / ".claude" / "agents").glob("*.md")}
    assert len(agent_stems) == 12  # guard the guard: pin the real preset's current agent count
    agents_doc = (proj / "docs" / "agent" / "agents.md").read_text()
    for stem in agent_stems:
        assert stem in agents_doc, f"{stem} missing from generated docs/agent/agents.md"


@pytest.mark.parametrize("preset", ["python", "java", "frontend", "macos"])
def test_dry_run_reports_marker_count_without_calling_api(preset, tmp_path):
    # --resolve-markers --dry-run must report the real TEMPLATE-INIT count from
    # the source preset and make no API call (proven by staying offline here).
    real_templates = REAL_REPO_ROOT / "templates"
    expected = len(scan_tree(real_templates / preset))
    assert expected > 0  # sanity: the real presets do carry markers

    proj = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(proj),
            "--preset",
            preset,
            "--name",
            "X",
            "--resolve-markers",
            "--harness",
            "claude",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["markers_to_resolve"] == expected
    assert not proj.exists()  # dry-run writes nothing


# --- specialization layer ----------------------------------------------------

_REAL_TEMPLATES = Workspace(root=REAL_REPO_ROOT / "templates")
_PRESET_SPECIALIZATION_PAIRS = [
    (preset, specialization)
    for preset in list_presets(_REAL_TEMPLATES)
    for specialization in list_specializations(_REAL_TEMPLATES, preset)
]


def test_real_repo_actually_ships_specializations():
    # Guard the guard: if this list is ever empty (e.g. a future refactor moves
    # specializations/ elsewhere without updating list_specializations), the
    # parametrized test below would silently collect zero cases and report a
    # cheerful "0 passed" instead of catching the regression.
    assert _PRESET_SPECIALIZATION_PAIRS, "expected at least one real (preset, specialization) pair"


@pytest.mark.parametrize("preset,specialization", _PRESET_SPECIALIZATION_PAIRS)
def test_real_preset_specialization_has_no_placeholder_leftovers(preset, specialization, tmp_path):
    proj = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "generate",
            str(proj),
            "--preset",
            preset,
            "--name",
            "Big",
            "--package",
            "big",
            "--specialization",
            specialization,
        ],
    )
    assert result.exit_code == 0, result.stdout

    md_files = list(proj.rglob("*.md"))
    leftover = [f for f in md_files if PLACEHOLDER_RE.search(f.read_text(encoding="utf-8"))]
    assert leftover == []


def test_real_specializations_ship_only_agents_and_skills():
    # Structural enforcement of the "no hooks/loops/settings.json in a
    # specialization" rule (see specializations.py's module docstring for why):
    # a hook needs settings.json wiring only the core preset owns.
    offenders = {
        f"{preset}/{specialization}": found
        for preset, specialization in _PRESET_SPECIALIZATION_PAIRS
        if (found := disallowed_kinds_present(_REAL_TEMPLATES, preset, specialization))
    }
    assert offenders == {}


def test_real_repo_ships_an_active_model_policy():
    # The check is only worth anything while model-policy.toml actually turns it on: a deleted file
    # would silently read as `off`. `current` must also stay non-empty (load_policy enforces it).
    policy = _real_policy()
    assert policy.mode is not PolicyMode.off
    assert policy.current


@pytest.mark.parametrize("preset", ["cpp", "frontend", "java", "macos", "python"])
def test_real_preset_and_common_agents_pin_only_current_models(preset):
    # Pins the model migration: a plain `generate --preset <p>` copies common/ + the preset, and none
    # of those agents may pin a model outside the template's `recommended` lists. Specializations are
    # deliberately not covered here - they are the known-stale set `check-models` reports.
    policy = _real_policy()
    findings = scan_generation(_REAL_TEMPLATES, preset, [], policy)
    assert [model_policy.format_finding(f, REAL_REPO_ROOT) for f in findings] == []


def test_real_check_models_command_runs_against_the_real_tree():
    # Smoke test of the whole-tree sweep: it must run and emit well-formed JSON whatever the mode.
    result = runner.invoke(app, ["check-models", "--json"])
    assert result.exit_code in (0, 1), result.stdout
    payload = json.loads(result.stdout)
    assert set(payload) == {"mode", "current", "findings", "live"}
    assert payload["live"]["checked"] is False  # no --live, so no network


def test_real_recommended_lists_are_well_formed():
    policy = _real_policy()
    for vendor, ids in policy.recommended.items():
        assert all(m == m.strip() and m for m in ids), vendor
        assert model_policy.vendor_of(next(iter(ids)), policy) == vendor if ids else True
    assert policy.current == frozenset(m for ids in policy.recommended.values() for m in ids)
    # A key env var is only meaningful for a vendor the live check can query.
    assert set(policy.key_envs) <= set(FETCHERS)


def test_real_upgrade_rules_send_every_old_claude_tier_to_a_recommended_model():
    policy = _real_policy()
    rule = policy.upgrade["anthropic"]
    for old in ("claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-3-5", "claude-opus-99-9"):
        assert rule.target_for(old) in policy.recommended["anthropic"], old
    assert policy.upgrade["copilot"].target_for("anything") in policy.recommended["copilot"]


def test_every_shipped_agent_role_has_an_upgrade_tier():
    # "Every existing agent role has an update protocol": a role missing from [roles] would silently
    # fall through to the coarse family/default fallback; a role listed but no longer shipped is a
    # stale row in the matrix. Both directions are failures.
    policy = _real_policy()
    shipped = model_policy.discover_roles(Workspace(REAL_REPO_ROOT / "templates"))
    assert sorted(shipped - set(policy.role_tiers)) == [], "add these roles to `roles` in models.template.json"
    assert sorted(set(policy.role_tiers) - shipped) == [], "these [roles] entries match no shipped agent"


def test_real_role_upgrade_targets_are_recommended_for_every_role_and_vendor():
    policy = _real_policy()
    for vendor, rule in policy.upgrade.items():
        if not rule.tiers and not rule.roles:
            continue
        for role in policy.role_tiers:
            assert policy.upgrade_target(vendor, "old", role) in policy.recommended[vendor], (vendor, role)


def test_model_upgrade_matrix_doc_matches_the_data_template():
    policy = _real_policy()
    doc = (REAL_REPO_ROOT / "docs" / "model-upgrade-matrix.md").read_text(encoding="utf-8")
    assert model_policy.splice_matrix(doc, policy) == doc, "run: uv run awesome-templates model-matrix --write"


def test_real_model_matrix_check_command_passes():
    result = runner.invoke(app, ["model-matrix", "--check"])
    assert result.exit_code == 0, result.stdout
