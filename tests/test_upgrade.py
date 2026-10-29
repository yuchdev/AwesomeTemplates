from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from awesome_templates import upgrade
from awesome_templates.model_policy import (
    ModelPolicy,
    ModelPolicyError,
    PolicyMode,
    UpgradeRule,
    load_policy,
)

NEW_OPUS, NEW_SONNET = "claude-opus-5-5", "claude-sonnet-5-5"


def _policy() -> ModelPolicy:
    families = tuple((n, re.compile(f"^claude-{n}-")) for n in ("opus", "sonnet", "haiku"))
    anthropic = UpgradeRule(families, {"opus": NEW_OPUS, "sonnet": NEW_SONNET}, default=NEW_OPUS)
    recommended = {
        "anthropic": frozenset({NEW_OPUS, NEW_SONNET}),
        "copilot": frozenset({"Sol 6.1"}),
        "junie": frozenset({"junie-new"}),
        "codex": frozenset({"codex-new"}),
    }
    rules = {"anthropic": anthropic, "copilot": UpgradeRule(default="Sol 6.1")}
    return ModelPolicy(PolicyMode.warn, frozenset().union(*recommended.values()), recommended, {}, rules)


def _agent(root: Path, rel: str, model: str, *, newline: str = "\n", tail: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    body = newline.join(["---", "name: x", f"model: {model}{tail}", "tools: Read", "---", "", "model: not-a-pin"])
    path.write_bytes((body + newline).encode())
    return path


# --- matcher ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("old", "expected"),
    [
        ("claude-opus-4-8", NEW_OPUS),
        ("claude-sonnet-4-6", NEW_SONNET),
        ("claude-opus-9-9", NEW_OPUS),  # a release that did not exist when the table was written
        ("claude-haiku-3", NEW_OPUS),  # family with no target -> default
        ("claude-mystery", NEW_OPUS),  # no family at all -> default
    ],
)
def test_target_follows_family_not_version(old: str, expected: str):
    assert _policy().upgrade["anthropic"].target_for(old) == expected


def test_rule_without_a_default_has_no_target_for_unknown_models():
    rule = UpgradeRule((("opus", re.compile("^o")),), {"opus": "x"})
    assert rule.target_for("zzz") is None


def test_every_old_copilot_model_collapses_to_the_default():
    rule = _policy().upgrade["copilot"]
    assert {rule.target_for(m) for m in ("GPT-4.1", "o1", "anything")} == {"Sol 6.1"}


# --- plan ------------------------------------------------------------------------------------


def test_plan_upgrades_stale_pins_and_leaves_current_aliases_and_missing_alone(tmp_path: Path):
    _agent(tmp_path, ".claude/agents/a.md", "claude-opus-4-8")
    _agent(tmp_path, ".claude/agents/b.md", NEW_SONNET)
    _agent(tmp_path, ".claude/agents/c.md", "opus")
    (tmp_path / ".claude/agents/d.md").write_text("---\nname: d\n---\nbody\n")
    plan = upgrade.plan_upgrade(tmp_path, _policy())
    assert [(c.site.path.name, c.site.line, c.new_model) for c in plan.changes] == [("a.md", 3, NEW_OPUS)]
    assert plan.current == 2 and plan.unresolved == []


def test_plan_ignores_model_lines_outside_the_frontmatter(tmp_path: Path):
    _agent(tmp_path, ".claude/agents/a.md", NEW_OPUS)
    assert upgrade.plan_upgrade(tmp_path, _policy()).changes == []  # body has "model: not-a-pin"


def test_unverified_harness_is_skipped_unless_named(tmp_path: Path):
    _agent(tmp_path, ".github/agents/a.md", "GPT-4.1")
    auto = upgrade.plan_upgrade(tmp_path, _policy())
    assert auto.changes == [] and auto.skipped[0][0] == "copilot" and "not verified" in auto.skipped[0][1]
    named = upgrade.plan_upgrade(tmp_path, _policy(), ["copilot"])
    assert [(c.site.model, c.new_model) for c in named.changes] == [("GPT-4.1", "Sol 6.1")]


def test_named_harness_missing_from_the_project_is_reported(tmp_path: Path):
    plan = upgrade.plan_upgrade(tmp_path, _policy(), ["junie"])
    assert plan.skipped == [("junie", "not found in this project")]


def test_outdated_pin_without_a_target_is_unresolved(tmp_path: Path):
    _agent(tmp_path, ".junie/agents/a.md", "old-junie")
    plan = upgrade.plan_upgrade(tmp_path, _policy(), ["junie"])
    assert plan.changes == [] and [p.model for p in plan.unresolved] == ["old-junie"]


def test_vendor_without_recommendations_warns_instead_of_guessing(tmp_path: Path):
    _agent(tmp_path, ".claude/agents/a.md", "claude-opus-4-8")
    bare = ModelPolicy(PolicyMode.warn, frozenset({"x"}), {})
    warnings: list[str] = []
    plan = upgrade.plan_upgrade(tmp_path, bare, warnings=warnings)
    assert plan.changes == [] and "cannot judge" in warnings[0]


def test_codex_toml_pins_are_found(tmp_path: Path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex/config.toml").write_text('model = "old-codex"  # c\n[profiles.x]\nmodel = \'old-codex\'\nname = "n"\n')
    policy = ModelPolicy(
        PolicyMode.warn, frozenset({"codex-new"}), {"codex": frozenset({"codex-new"})}, {},
        {"codex": UpgradeRule(default="codex-new")},
    )
    plan = upgrade.plan_upgrade(tmp_path, policy, ["codex"])
    assert [c.site.line for c in plan.changes] == [1, 3]


# --- apply -----------------------------------------------------------------------------------


def test_apply_changes_only_the_model_line_and_preserves_quotes_comments_and_crlf(tmp_path: Path):
    path = _agent(tmp_path, ".claude/agents/a.md", '"claude-opus-4-8"', newline="\r\n", tail="  # keep me")
    before = path.read_bytes()
    plan = upgrade.plan_upgrade(tmp_path, _policy())
    assert upgrade.apply_changes(plan.changes) == 1
    assert path.read_bytes() == before.replace(b"claude-opus-4-8", NEW_OPUS.encode())


def test_apply_is_idempotent(tmp_path: Path):
    _agent(tmp_path, ".claude/agents/a.md", "claude-sonnet-4-6")
    upgrade.apply_changes(upgrade.plan_upgrade(tmp_path, _policy()).changes)
    again = upgrade.plan_upgrade(tmp_path, _policy())
    assert again.changes == [] and again.current == 1


def test_apply_leaves_a_line_that_changed_since_planning(tmp_path: Path):
    path = _agent(tmp_path, ".claude/agents/a.md", "claude-opus-4-8")
    plan = upgrade.plan_upgrade(tmp_path, _policy())
    path.write_text(path.read_text().replace("claude-opus-4-8", "claude-sonnet-4-6"))
    warnings: list[str] = []
    assert upgrade.apply_changes(plan.changes, warnings=warnings) == 0
    assert "changed since planning" in warnings[0] and "claude-sonnet-4-6" in path.read_text()


def test_unquoted_value_with_a_space_round_trips(tmp_path: Path):
    path = _agent(tmp_path, ".github/agents/a.md", "GPT 4.1")
    plan = upgrade.plan_upgrade(tmp_path, _policy(), ["copilot"])
    upgrade.apply_changes(plan.changes)
    assert "model: Sol 6.1\n" in path.read_text()


# --- git guard -------------------------------------------------------------------------------


class _Run:
    def __init__(self, stdout: bytes = b"", returncode: int = 0, raises: bool = False):
        self.result = subprocess.CompletedProcess([], returncode, stdout, "")
        self.raises, self.calls = raises, []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if self.raises:
            raise FileNotFoundError("git")
        return self.result


def test_dirty_files_reports_only_modified_targets(tmp_path: Path):
    a, b = tmp_path / ".claude/agents/a.md", tmp_path / ".claude/agents/b.md"
    run = _Run(b" M .claude/agents/a.md\0")
    assert upgrade.dirty_files(tmp_path, [a, b], run=run) == [a]


def test_dirty_files_uses_paths_relative_to_relative_git_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    root = Path("project")
    a, b = root / ".claude/agents/a.md", root / ".claude/agents/b.md"
    run = _Run(b" M .claude/agents/a.md\0")
    assert upgrade.dirty_files(root, [a, b], run=run) == [a]
    assert run.calls[0][-2:] == [".claude/agents/a.md", ".claude/agents/b.md"]


def test_dirty_files_requires_exact_status_path_match(tmp_path: Path):
    target = tmp_path / "nested/agents/a.md"
    run = _Run(b" M agents/a.md\0")
    assert upgrade.dirty_files(tmp_path, [target], run=run) == []


@pytest.mark.parametrize("status", [b"R ", b"C "])
def test_dirty_files_consumes_both_rename_or_copy_paths(tmp_path: Path, status: bytes):
    old, new = tmp_path / "before.md", tmp_path / "after.md"
    run = _Run(status + b" after.md\0before.md\0")
    assert upgrade.dirty_files(tmp_path, [old, new], run=run) == [old, new]


def test_dirty_files_preserves_unusual_filename_bytes(tmp_path: Path):
    relative = os.fsdecode(b".claude/agents/\xff.md")
    target = tmp_path / relative
    run = _Run(b" M .claude/agents/\xff.md\0")
    assert upgrade.dirty_files(tmp_path, [target], run=run) == [target]


@pytest.mark.parametrize("run", [_Run(returncode=128), _Run(raises=True)])
def test_dirty_files_cannot_refuse_outside_a_repo_or_without_git(tmp_path: Path, run: _Run):
    assert upgrade.dirty_files(tmp_path, [tmp_path / "a.md"], run=run) == []


def test_dirty_files_with_no_paths_does_not_call_git(tmp_path: Path):
    run = _Run()
    assert upgrade.dirty_files(tmp_path, [], run=run) == [] and run.calls == []


# --- config + hygiene ------------------------------------------------------------------------

BASE = (
    '[tool.awesome_templates.model_policy]\nmode = "warn"\n'
    '[tool.awesome_templates.model_policy.recommended]\nanthropic = ["claude-opus-5-5"]\n'
)


def test_load_policy_parses_upgrade_rules(tmp_path: Path):
    f = tmp_path / "p.toml"
    f.write_text(
        BASE + '[tool.awesome_templates.model_policy.upgrade.anthropic]\n'
        'families = { opus = "^claude-opus-" }\ntargets = { opus = "claude-opus-5-5" }\n'
    )
    assert load_policy(f).upgrade["anthropic"].target_for("claude-opus-1") == "claude-opus-5-5"


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ('default = "claude-opus-9"', "must be listed"),  # target not recommended
        ('families = { a = "(" }', "valid regex"),
        ('targets = { ghost = "claude-opus-5-5" }', "unknown families"),
    ],
)
def test_load_policy_rejects_bad_upgrade_rules(tmp_path: Path, body: str, match: str):
    f = tmp_path / "p.toml"
    f.write_text(BASE + f"[tool.awesome_templates.model_policy.upgrade.anthropic]\n{body}\n")
    with pytest.raises(ModelPolicyError, match=match):
        load_policy(f)


def test_validate_harness_names():
    upgrade.validate_harness_names(["claude", "codex"])
    with pytest.raises(ValueError, match="nope"):
        upgrade.validate_harness_names(["nope"])


def test_upgrade_import_does_not_pull_anthropic():
    code = "import sys; import awesome_templates.upgrade; sys.exit('anthropic' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0
