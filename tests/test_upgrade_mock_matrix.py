"""Mock-project tests for `upgrade` across vendors: valid pins of every vendor, and malformed ones.

Every test builds a throwaway project under `tmp_path` and judges it with the REAL repo policy (the
TOML plus the packaged template), so a change to the shipped roles/tiers/targets that breaks an upgrade
shows up here. Nothing touches the network or the user's models.json.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from awesome_templates import model_state, upgrade
from awesome_templates.model_policy import ModelPolicy, PolicyMode, load_policy

REPO = Path(__file__).resolve().parents[1]
POLICY = load_policy(REPO / "model-policy.toml", fallback=model_state.load_template())
OPUS, SONNET, HAIKU = "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"
SOL, LUNA = "GPT-6.1 Sol", "GPT-6 Luna"


def _write(root: Path, rel: str, text: str, *, binary: bool = False) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text if binary else text.encode())
    return path


def _agent(root: Path, rel: str, model: str) -> Path:
    return _write(root, rel, f"---\nname: x\nmodel: {model}\n---\n\nbody\n")


def _plan(root: Path, harness: list[str] | None = None, policy: ModelPolicy = POLICY):
    warnings: list[str] = []
    return upgrade.plan_upgrade(root, policy, harness, warnings=warnings), warnings


def _targets(plan) -> dict[str, str]:
    return {c.site.path.stem: c.new_model for c in plan.changes}


# --- Claude: every old model of every tier, by role ---------------------------------------------

CLAUDE_OLD = ["claude-opus-4-8", "claude-opus-4-1", "claude-opus-3", "claude-sonnet-4-6", "claude-sonnet-3-7",
              "claude-haiku-3-5", "claude-opus-99-9", "claude-sonnet-99-9"]
DEEP_ROLES = ["cpp-expert", "security-auditor", "python-expert", "django-expert", "swiftui-expert", "agent-orchestrator"]
STANDARD_ROLES = ["docs-updater", "docs-writer", "feature-reviewer", "task-verifier", "test-documenter"]


@pytest.mark.parametrize("old", CLAUDE_OLD)
@pytest.mark.parametrize("role", DEEP_ROLES)
def test_claude_deep_roles_always_land_on_the_flagship_whatever_the_old_model(tmp_path: Path, role: str, old: str):
    _agent(tmp_path, f".claude/agents/{role}.md", old)
    assert _targets(_plan(tmp_path)[0]) == {role: OPUS}


@pytest.mark.parametrize("old", CLAUDE_OLD)
@pytest.mark.parametrize("role", STANDARD_ROLES)
def test_claude_standard_roles_land_on_sonnet_even_from_an_opus_pin(tmp_path: Path, role: str, old: str):
    _agent(tmp_path, f".claude/agents/{role}.md", old)
    assert _targets(_plan(tmp_path)[0]) == {role: SONNET}


@pytest.mark.parametrize(
    ("old", "expected"),
    [
        ("claude-opus-4-8", OPUS),
        ("claude-sonnet-4-6", SONNET),
        ("claude-haiku-3-5", HAIKU),
        ("claude-opus-99-9", OPUS),  # a release that did not exist when the table was written
        ("claude-mystery-1", OPUS),  # no family -> vendor default
    ],
)
def test_claude_agent_not_in_the_role_table_keeps_the_old_models_family(tmp_path: Path, old: str, expected: str):
    _agent(tmp_path, ".claude/agents/my-own-agent.md", old)
    assert _targets(_plan(tmp_path)[0]) == {"my-own-agent": expected}


@pytest.mark.parametrize("current", [OPUS, SONNET, HAIKU, "claude-fable-5-1", "opus", "sonnet", "haiku", "inherit"])
def test_claude_current_models_and_aliases_are_never_rewritten(tmp_path: Path, current: str):
    _agent(tmp_path, ".claude/agents/cpp-expert.md", current)
    plan, _ = _plan(tmp_path)
    assert plan.changes == [] and plan.current == 1


# --- Copilot: role decides between the two GPT-6 models ----------------------------------------

COPILOT_OLD = ["GPT-4.1", "GPT-5.2", "GPT-5.6 Sol", "GPT-6 Sol", "Sol 6.1", "Luna 6.1", "gpt-5", "o3"]


@pytest.mark.parametrize("old", COPILOT_OLD)
def test_copilot_cpp_expert_gets_sol_and_docs_updater_gets_luna(tmp_path: Path, old: str):
    _agent(tmp_path, ".github/agents/cpp-expert.md", old)
    _agent(tmp_path, ".github/agents/docs-updater.md", old)
    assert _targets(_plan(tmp_path, ["copilot"])[0]) == {"cpp-expert": SOL, "docs-updater": LUNA}


@pytest.mark.parametrize("old", COPILOT_OLD)
def test_copilot_unknown_agent_gets_the_cheap_default_never_the_flagship(tmp_path: Path, old: str):
    _agent(tmp_path, ".github/agents/custom-thing.md", old)
    assert _targets(_plan(tmp_path, ["copilot"])[0]) == {"custom-thing": LUNA}


@pytest.mark.parametrize("current", [SOL, LUNA])
def test_copilot_current_models_stay(tmp_path: Path, current: str):
    _agent(tmp_path, ".github/agents/cpp-expert.md", current)
    assert _plan(tmp_path, ["copilot"])[0].changes == []


def test_the_misnamed_copilot_models_from_before_the_docs_lookup_are_treated_as_outdated(tmp_path: Path):
    _agent(tmp_path, ".github/agents/cpp-expert.md", "Sol 6.1")
    assert _targets(_plan(tmp_path, ["copilot"])[0]) == {"cpp-expert": SOL}


# --- vendors without upgrade rules (Junie, Codex): never guess ------------------------------------


def test_junie_pins_are_unresolved_and_warned_because_no_models_are_configured(tmp_path: Path):
    _agent(tmp_path, ".junie/agents/cpp-expert.md", "whatever-9")
    plan, warnings = _plan(tmp_path, ["junie"])
    assert plan.changes == [] and plan.unresolved == [] and any("no recommended models" in w for w in warnings)


def test_codex_toml_pin_is_found_but_not_rewritten_without_a_rule(tmp_path: Path):
    _write(tmp_path, ".codex/config.toml", 'model = "gpt-5-codex"\n')
    plan, warnings = _plan(tmp_path, ["codex"])
    assert plan.changes == [] and any("codex" in w for w in warnings)


def test_a_vendor_with_recommended_models_but_no_target_is_reported_unresolved(tmp_path: Path):
    policy = ModelPolicy(
        PolicyMode.warn, frozenset({"j-new"}), {"junie": frozenset({"j-new"})}, {}, {}, {}
    )
    _agent(tmp_path, ".junie/agents/a.md", "j-old")
    plan, _ = _plan(tmp_path, ["junie"], policy)
    assert [p.model for p in plan.unresolved] == ["j-old"] and plan.changes == []


# --- mixed project, idempotency, round trip ----------------------------------------------------


def test_one_project_with_two_harnesses_upgrades_each_against_its_own_vendor(tmp_path: Path):
    _agent(tmp_path, ".claude/agents/cpp-expert.md", "claude-opus-4-8")
    _agent(tmp_path, ".github/agents/cpp-expert.md", "GPT-4.1")
    plan, _ = _plan(tmp_path, ["claude", "copilot"])
    assert {(c.site.harness, c.new_model) for c in plan.changes} == {("claude", OPUS), ("copilot", SOL)}


def test_apply_then_replan_is_clean_and_changes_only_the_model_line(tmp_path: Path):
    path = _agent(tmp_path, ".claude/agents/docs-updater.md", "claude-opus-4-8")
    before = path.read_text()
    plan, _ = _plan(tmp_path)
    assert upgrade.apply_changes(plan.changes) == 1
    after = path.read_text()
    assert after == before.replace("claude-opus-4-8", SONNET)
    again, _ = _plan(tmp_path)
    assert again.changes == [] and again.current == 1


# --- faulty files: none may crash the run or corrupt another file ------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",  # empty file
        "no frontmatter at all\nmodel: claude-opus-4-8\n",  # `model:` only in the body
        "---\nname: x\n",  # frontmatter never closed, no model
        "---\nname: x\n---\nmodel: claude-opus-4-8\n",  # model after the frontmatter ended
        "---\nmodel:\n---\n",  # empty value
        "---\nmodel:    \n---\n",  # whitespace-only value
        "---\nmodel: ''\n---\n",  # empty quoted value
        "\n---\nmodel: claude-opus-4-8\n---\n",  # frontmatter not on line 1
    ],
)
def test_files_without_a_usable_frontmatter_model_are_ignored(tmp_path: Path, text: str):
    _write(tmp_path, ".claude/agents/cpp-expert.md", text)
    plan, _ = _plan(tmp_path)
    assert plan.changes == [] and plan.unresolved == [] and plan.current == 0


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("model: 'claude-opus-4-8'", "model: 'claude-opus-5-5'"),
        ('model: "claude-opus-4-8"', 'model: "claude-opus-5-5"'),
        ("model: claude-opus-4-8   # was the flagship", "model: claude-opus-5-5   # was the flagship"),
        ("model:claude-opus-4-8", "model:claude-opus-5-5"),
        ("  model:  claude-opus-4-8", "  model:  claude-opus-5-5"),
    ],
)
def test_rewrite_preserves_quotes_comments_and_spacing(tmp_path: Path, line: str, expected: str):
    path = _write(tmp_path, ".claude/agents/cpp-expert.md", f"---\nname: x\n{line}\n---\nbody\n")
    plan, _ = _plan(tmp_path)
    assert upgrade.apply_changes(plan.changes) == 1
    assert path.read_text() == f"---\nname: x\n{expected}\n---\nbody\n"


def test_crlf_files_keep_their_line_endings(tmp_path: Path):
    path = _write(tmp_path, ".claude/agents/cpp-expert.md", "---\r\nmodel: claude-opus-4-8\r\n---\r\nbody\r\n")
    plan, _ = _plan(tmp_path)
    upgrade.apply_changes(plan.changes)
    assert path.read_bytes() == b"---\r\nmodel: claude-opus-5-5\r\n---\r\nbody\r\n"


def test_a_second_model_key_in_the_body_is_not_a_pin(tmp_path: Path):
    path = _write(tmp_path, ".claude/agents/cpp-expert.md", "---\nmodel: claude-opus-4-8\n---\nmodel: claude-sonnet-4-6\n")
    plan, _ = _plan(tmp_path)
    upgrade.apply_changes(plan.changes)
    assert path.read_text() == "---\nmodel: claude-opus-5-5\n---\nmodel: claude-sonnet-4-6\n"


def test_a_project_with_no_agents_dir_or_an_empty_one_is_simply_clean(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    plan, warnings = _plan(tmp_path)
    assert plan.changes == [] and warnings == []


def test_non_markdown_files_in_the_agents_dir_are_ignored(tmp_path: Path):
    _write(tmp_path, ".claude/agents/notes.txt", "model: claude-opus-4-8\n")
    _write(tmp_path, ".claude/agents/sub/deep.md", "---\nmodel: claude-opus-4-8\n---\n")
    assert _plan(tmp_path)[0].changes == []


def test_a_file_that_is_not_valid_utf8_does_not_crash_the_whole_run(tmp_path: Path):
    _write(tmp_path, ".claude/agents/broken.md", b"---\nmodel: claude-opus-4-8\n\xff\xfe\n---\n", binary=True)
    good = _agent(tmp_path, ".claude/agents/cpp-expert.md", "claude-opus-4-8")
    plan, warnings = _plan(tmp_path)
    assert _targets(plan) == {"cpp-expert": OPUS} and any("broken.md" in w for w in warnings)
    assert good.is_file()


def test_a_file_edited_between_plan_and_apply_is_left_alone_and_reported(tmp_path: Path):
    path = _agent(tmp_path, ".claude/agents/cpp-expert.md", "claude-opus-4-8")
    plan, _ = _plan(tmp_path)
    path.write_text("---\nname: x\nmodel: claude-sonnet-4-6\n---\n")  # someone changed it meanwhile
    warnings: list[str] = []
    assert upgrade.apply_changes(plan.changes, warnings=warnings) == 0
    assert "claude-sonnet-4-6" in path.read_text() and any("changed since planning" in w for w in warnings)


def test_a_file_that_vanished_between_plan_and_apply_does_not_crash(tmp_path: Path):
    path = _agent(tmp_path, ".claude/agents/cpp-expert.md", "claude-opus-4-8")
    plan, _ = _plan(tmp_path)
    path.unlink()
    warnings: list[str] = []
    assert upgrade.apply_changes(plan.changes, warnings=warnings) == 0 and warnings


def test_a_name_that_looks_like_a_regex_does_not_break_role_lookup(tmp_path: Path):
    _agent(tmp_path, ".claude/agents/a+b(c.md", "claude-opus-4-8")
    assert _targets(_plan(tmp_path)[0]) == {"a+b(c": OPUS}  # unknown role -> family fallback


@pytest.mark.parametrize("name", ["unknown-harness", "", "CLAUDE"])
def test_unknown_harness_names_are_rejected(name: str):
    with pytest.raises(ValueError, match="unknown harness"):
        upgrade.validate_harness_names([name])


def test_naming_a_harness_that_is_absent_is_reported_as_skipped(tmp_path: Path):
    plan, _ = _plan(tmp_path, ["copilot"])
    assert plan.skipped == [("copilot", "not found in this project")]


def test_unverified_harnesses_are_skipped_on_autodetect(tmp_path: Path):
    _agent(tmp_path, ".github/agents/cpp-expert.md", "GPT-4.1")
    plan, _ = _plan(tmp_path)
    assert plan.changes == [] and plan.skipped and plan.skipped[0][0] == "copilot"


def test_policy_mode_off_leaves_no_recommended_list_so_nothing_can_be_judged(tmp_path: Path):
    _agent(tmp_path, ".claude/agents/cpp-expert.md", "claude-opus-4-8")
    plan, warnings = _plan(tmp_path, policy=ModelPolicy(PolicyMode.off, frozenset()))
    assert plan.changes == [] and any("no recommended models" in w for w in warnings)


def test_every_target_of_every_shipped_role_is_a_recommended_model_for_that_vendor():
    for vendor in ("anthropic", "copilot"):
        for role in POLICY.role_tiers:
            assert POLICY.upgrade_target(vendor, "ancient-model", role) in POLICY.recommended[vendor], (vendor, role)
