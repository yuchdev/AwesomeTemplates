"""Per-backend adapters for headless sessions - marker research (headless.py)
and cross-harness porting (port.py): binary discovery and argv construction for
each supported CLI. Those callers stay responsible for *what* a session needs to
do (the manifest, the prompt, reconciliation); this module is only responsible
for *how* to ask a given CLI to do it, so a wrong guess about one backend's flag
names is a one-function fix here, not a rewrite of a caller. See
docs/roadmap/0001-alternative-harness-support/plan.md's "Proposed architecture"
section for the design this module implements.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Callable, Optional

HARNESS_NAMES = ("claude", "copilot", "junie")


@dataclass(frozen=True)
class Harness:
    """One headless-CLI backend's identity and argv-construction recipe.

    :ivar name: the `--harness` value this registration answers to.
    :ivar binary_names: candidate executable names tried in order via
        `shutil.which` - more than one entry lets a harness accept an
        alternate binary name without a second registry entry.
    :ivar default_model: the model alias passed when the caller doesn't
        override it, or `None` when the backend has no CLI model flag.
    :ivar prompt_via: `"stdin"` when the session prompt is piped to the
        subprocess's stdin (claude's mechanism today), `"arg"` when the
        backend instead expects the prompt as a command-line argument -
        `build_command` is responsible for placing it correctly in that case,
        and the caller must not also pipe it over stdin.
    :ivar forwards_anthropic_key: whether `ANTHROPIC_API_KEY` should be
        forwarded into this harness's subprocess environment - true only for
        `claude`; copilot/junie authenticate through their own mechanisms.
    :ivar build_command: `(binary, *, tools, model, prompt) -> argv`. `prompt`
        is unused (and should not be embedded in argv) when `prompt_via` is
        `"stdin"`; it is required and must appear in the returned argv when
        `prompt_via` is `"arg"`.
    :ivar porting_target_hint: free-text hint, consumed by `port.py`'s prompt
        builder, naming where this harness conventionally expects its own
        agent/skill-equivalent files to live. `None` until tasks 07.0/08.0
        confirm it for copilot/junie; `claude` never needs one since it is
        never a `--port-to` target.
    """

    name: str
    binary_names: tuple[str, ...]
    default_model: Optional[str]
    prompt_via: str
    forwards_anthropic_key: bool
    build_command: Callable[..., list[str]]
    porting_target_hint: Optional[str] = None


def find_harness(harness: Harness) -> Optional[str]:
    """Absolute path of the first installed candidate binary, or None -
    the same contract `headless.find_claude()` had before it was folded in
    here, generalized across harnesses.

    :param harness: the :class:`Harness` whose `binary_names` to search.
    :return: absolute path to the first match on `PATH`, or `None` if none
        of `harness.binary_names` is installed.
    """
    for candidate in harness.binary_names:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def get(name: str) -> Harness:
    """Look up a harness by its `--harness`/`--port-to` value.

    :param name: one of `HARNESS_NAMES`.
    :return: the registered :class:`Harness`.
    :raises KeyError: if `name` is not registered - `cli.py` turns this into
        the same `_fail(...)` shape `_resolve_preset` already uses for an
        unknown preset (see task 04.0).
    """
    return _REGISTRY[name]


def _build_claude_command(
    claude_bin: str,
    *,
    tools: tuple[str, ...],
    model: str,
    prompt: Optional[str] = None,
) -> list[str]:
    """The headless argv for `claude`. `prompt` is accepted for signature
    parity with `Harness.build_command` but unused - claude's prompt travels
    over stdin (`prompt_via="stdin"`), not argv. See `_CLAUDE.prompt_via`.

    `--setting-sources user` keeps the user's own settings (and their normal
    login - OAuth or ANTHROPIC_API_KEY) while skipping project/local settings:
    with the documented `generate .` usage the generated kit's own
    settings.json sits at the session cwd and its wired hooks would otherwise
    fire on - and could block - every edit the session makes. `--tools` is a
    variadic flag, so it goes last, where the argv ends before anything could
    be swallowed into its value list.

    `--permission-mode bypassPermissions` is required, not a convenience:
    Claude Code's permission layer treats `.claude/**` files as sensitive and
    blocks Edit on them even under acceptEdits and even with an explicit
    `--allowedTools "Edit(<kit>/**)"` rule (verified empirically) - and the
    kit's agent/loop files, the very thing the marker-research session exists
    to edit, all live under `.claude/`. The security boundary is therefore the
    tool allowlist (no Bash, no network tools) plus the caller's closed file
    set named in the prompt, not per-path permission checks.

    :param claude_bin: absolute path to the `claude` executable.
    :param tools: the exact tool allowlist for the session, in argv order.
    :param model: the `--model` alias handed to the CLI.
    :param prompt: ignored; present only for `Harness.build_command` parity.
    :return: the argv list ready to hand to `subprocess.run`.
    """
    return [
        claude_bin,
        "-p",
        "--output-format",
        "text",
        "--setting-sources",
        "user",
        "--permission-mode",
        "bypassPermissions",
        "--no-session-persistence",
        "--model",
        model,
        "--tools",
        *tools,
    ]


_CLAUDE = Harness(
    name="claude",
    binary_names=("claude",),
    default_model="opus",
    prompt_via="stdin",
    forwards_anthropic_key=True,
    build_command=_build_claude_command,
)

_REGISTRY: dict[str, Harness] = {"claude": _CLAUDE}


def _build_copilot_command(
    copilot_bin: str,
    *,
    tools: tuple[str, ...],
    model: Optional[str],
    prompt: Optional[str] = None,
) -> list[str]:
    """The headless argv for `copilot`, per subtask 01's confirmed contract.

    Unlike `claude`, copilot's `-p`/`--prompt` is *both* the non-interactive
    switch and the prompt-delivery mechanism at once: it takes the prompt text
    as its argument value (`prompt_via="arg"`), so the prompt travels in argv
    here rather than over stdin. `--output-format text` is passed explicitly to
    mirror claude's explicit choice rather than relying on the documented
    default.

    The `tools` parameter is accepted for `Harness.build_command` signature
    parity but is deliberately *not* iterated into flags: copilot's
    `--allow-tool`/`--deny-tool` take one `kind(argument)` permission pattern
    per occurrence, not a variadic list of tool names, and there is no copilot
    equivalent for claude's `Read`/`Grep`/`Glob`/`TodoWrite` (read-only
    exploration is governed by path permissions, not tool permissions, and the
    session's cwd is already the kit root). So the posture is `--allow-all-tools`
    (copilot's own `--help` states this is "required for non-interactive mode",
    so it is the actual `--permission-mode bypassPermissions` analogue, not a
    convenience) plus two denials that claw the grant back down to claude's own
    posture: `--deny-tool=shell` (no shell access, matching claude's no-Bash
    allowlist) and `--deny-tool=url` (no network access - claude's own
    `_BASE_TOOLS` allowlist has no web-fetch/network tool at all, so
    `--allow-all-tools` alone would newly grant copilot's `url()` network tool
    kind that claude's session never has; a marker-research prompt processes
    untrusted repo content, so an ungated network tool would be a
    prompt-injection-driven exfiltration path). `--allow-all-tools` - rather
    than a narrower `--allow-tool=write` allowlist - is used because that is
    the only combination the spike actually confirmed works non-interactively;
    the narrower substitution was an untested recommendation that a live run
    never validated (see
    docs/roadmap/0001-alternative-harness-support/02.0-copilot-adapter/01-spike-copilot-contract.md's
    "Correction (2026-08-30, post-`/pr-review`)" note under Q3). Both denials
    take precedence over `--allow-all-tools` per copilot's own documented
    permission model ("Denial rules always take precedence over allow rules,
    even `--allow-all-tools`"). This posture cannot be derived 1:1 from
    `tools`.

    `--secret-env-vars=ANTHROPIC_API_KEY` is copilot's own flag to strip and
    redact that variable from its shell-tool/MCP subprocess environments -
    defense-in-depth alongside (not instead of) `headless.py`'s own
    env-stripping, since `forwards_anthropic_key=False`.

    `--model` is omitted entirely when `model is None` (subtask 01 confirmed no
    opus-comparable alias, so `_COPILOT.default_model=None`); it is appended
    only when a caller explicitly overrides the model - passing a `None`
    positionally into an argv list is a bug, not a no-op.

    :param copilot_bin: absolute path to the `copilot` executable.
    :param tools: accepted for signature parity; not mapped 1:1 onto flags (see
        above).
    :param model: the `--model` value to select, or `None` to let copilot's own
        default routing choose (the flag is then omitted).
    :param prompt: the prompt text, embedded as the `-p` value since
        `prompt_via` is `"arg"`.
    :raises ValueError: if `prompt` is `None` - copilot's `-p` is both the
        non-interactive switch and the prompt-delivery slot, so a missing prompt
        would leave `-p`'s value slot to be filled by the next flag (broken
        argv), not degrade gracefully.
    :return: the argv list ready to hand to `subprocess.run`.
    """
    if prompt is None:
        raise ValueError("prompt is required for copilot (prompt_via='arg')")
    # copilot's `-p` takes the prompt as its adjacent value, so it must follow
    # immediately (unlike claude's bare print-mode `-p` + stdin prompt).
    cmd = [copilot_bin, "-p", prompt]
    cmd += [
        "--output-format",
        "text",
        "--allow-all-tools",
        "--deny-tool=shell",
        "--deny-tool=url",
        "--secret-env-vars=ANTHROPIC_API_KEY",
    ]
    if model is not None:
        cmd += ["--model", model]
    return cmd


_COPILOT = Harness(
    name="copilot",
    binary_names=("copilot",),
    default_model=None,
    prompt_via="arg",
    forwards_anthropic_key=False,
    build_command=_build_copilot_command,
    # Confirmed against the installed copilot CLI's own --help text (task
    # 07.0 subtask 01's spike) - see
    # docs/roadmap/0001-alternative-harness-support/07.0-copilot-porting-session/01-spike-copilot-porting-target.md#findings-2026-08-30
    porting_target_hint=(
        "Copilot has its own conventions for repository-level configuration: put "
        "custom agents in `.github/agents/` (confirmed via the CLI's own --add-dir "
        "help text; auto-discovery from the session's own cwd without --add-dir was "
        "not independently verified, so mention the directory but don't assume a "
        "flag is unnecessary); put reusable skills as `SKILL.md` files under "
        "`.github/skills/` or `.agents/skills/` (Copilot already auto-discovers "
        "`.claude/skills/` too, so this is about idiom, not discoverability); put "
        "anything else that doesn't map onto an agent or skill into "
        "`.github/copilot-instructions.md` or `AGENTS.md`. Copilot has no "
        "project-level convention for hooks or loops - if a Claude-authored hook "
        "or loop has no equivalent concept for you, say so explicitly per the "
        "porting rules above rather than inventing a location for it."
    ),
)

_REGISTRY["copilot"] = _COPILOT


def _build_junie_command(
    junie_bin: str,
    *,
    tools: tuple[str, ...],
    model: Optional[str],
    prompt: Optional[str] = None,
) -> list[str]:
    """The headless argv for `junie`, per subtask 01's confirmed contract.

    Junie selects non-interactive mode simply by being *given a task string* -
    there is no separate `-p`/`--prompt` switch the way claude and copilot each
    have one. So the prompt travels in argv (`prompt_via="arg"`) as the final
    *bare positional* element, matching the CLI's own documented example
    (`junie "Fix the bug in the login function"`) rather than a `--task=` flag,
    which avoids any ambiguity about that flag's value-joining syntax.

    `--output-format json` is passed explicitly (unlike claude/copilot's
    `text`): subtask 01 confirmed `text` emits raw ANSI escape codes, whereas
    `json` yields clean structured `sessionId`/`taskName`/`result`/`changes`/
    `llmUsage` fields - cleaner for command-result logging and free of ANSI
    bytes. `--skip-update-check` is documented as "Useful for CI or automation"
    and is appropriate for every headless invocation, avoiding a network update
    check on a marker-research session. No `--project` flag is passed:
    `headless.resolve_tree_headless` already sets the subprocess `cwd` to the
    project root and junie's own `--project` defaults to the current directory
    (same reasoning as claude/copilot needing no explicit cwd flag).

    IMPORTANT - action-scope caveat: unlike claude (hard `--tools` allowlist)
    and copilot (`--allow-tool`/`--deny-tool` pair), **Junie exposes no
    tool/permission-restriction flag of any kind** in its CLI surface (subtask
    01 confirmed this against the full `--help` option listing). The `tools`
    parameter is therefore accepted only for `Harness.build_command` signature
    parity and cannot be translated into any flag - not even a fixed pair like
    copilot's. A headless Junie session's action scope is consequently **not
    restricted by any CLI flag**; it runs with whatever autonomy its agent mode
    grants, bounded only by the session cwd. Callers choosing this harness must
    understand the blast radius differs from claude/copilot. This is a
    documented capability gap from the spike, deferred per plan.md's Non-goals,
    not something to paper over by inventing a flag that does not exist.

    `--model` is omitted entirely when `model is None` (subtask 01 confirmed no
    opus-comparable default alias, so `_JUNIE.default_model=None`); it is
    appended only when a caller explicitly overrides the model, same pattern as
    `_build_copilot_command` - passing a `None` positionally into argv is a bug,
    not a no-op.

    :param junie_bin: absolute path to the `junie` executable.
    :param tools: accepted for signature parity only; Junie has no CLI mechanism
        to restrict tool use, so this is never mapped onto any flag (see above).
    :param model: the `--model` value to select, or `None` to let junie's own
        default routing choose (the flag is then omitted).
    :param prompt: the prompt text, appended as the final bare positional argv
        element since `prompt_via` is `"arg"`.
    :raises ValueError: if `prompt` is `None` - the bare positional task string
        is junie's *only* non-interactive trigger (no `-p`-style switch), so
        omitting it would silently drop the invocation into interactive mode
        rather than failing cleanly.
    :return: the argv list ready to hand to `subprocess.run`.
    """
    if prompt is None:
        raise ValueError("prompt is required for junie (prompt_via='arg')")
    cmd = [
        junie_bin,
        "--output-format",
        "json",
        "--skip-update-check",
    ]
    if model is not None:
        cmd += ["--model", model]
    # Junie's non-interactive trigger is the bare positional task string itself
    # (no `-p`-style switch); it goes last so nothing else can be mistaken for
    # it, mirroring the CLI's own documented `junie "<task>"` example.
    cmd.append(prompt)
    return cmd


_JUNIE = Harness(
    name="junie",
    binary_names=("junie",),
    default_model=None,
    prompt_via="arg",
    forwards_anthropic_key=False,
    build_command=_build_junie_command,
    # Confirmed both via the installed junie CLI's own --help text and by
    # direct filesystem inspection of real, populated `.junie/` directories on
    # this machine (task 08.0 subtask 01's spike) - see
    # docs/roadmap/0001-alternative-harness-support/08.0-junie-porting-session/01-spike-junie-porting-target.md#findings-2026-08-30
    porting_target_hint=(
        "Junie has its own conventions for repository-level configuration, "
        "directly observed on disk in real projects: put custom agents as flat "
        "`.md` files under `.junie/agents/<name>.md`; put reusable skills as "
        "`SKILL.md` files under `.junie/skills/<name>/SKILL.md`. `.junie/commands/` "
        "is also a real, populated directory in some projects and may be a fit for "
        "anything loop-like, though its own internal file shape wasn't confirmed - "
        "use your judgment there. Put anything else that doesn't map onto an agent "
        "or skill into `.junie/guidelines.md`. No fixed convention was found for "
        "hooks - if a Claude-authored hook has no equivalent concept for you, say "
        "so explicitly per the porting rules above rather than inventing a "
        "location for it."
    ),
)

_REGISTRY["junie"] = _JUNIE
