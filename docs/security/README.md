# Security

Threat models, security review outputs, and posture documentation for Awesome Templates.

The `security-auditor` agent owns this directory. Every change touching auth,
secrets, external integrations, or untrusted-input ingestion triggers a security
review whose output is stored here.

## Naming convention

`threat-model-<scope>.md` for threat models, `review-<scope>-<YYYY-MM-DD>.md`
for point-in-time reviews.

## What a threat model must contain

1. **Scope** - which components and trust boundaries are in scope.
2. **Assets** - what secrets, PII, and data are handled.
3. **Threat actors** - attacker profiles considered.
4. **STRIDE analysis** - Spoofing, Tampering, Repudiation, Info Disclosure, DoS, Elevation.
5. **Mitigations** - existing controls and open gaps.
6. **Verdict** - CRITICAL (merge blocked) / HIGH / MEDIUM / LOW / INFO.

## Security rules (non-negotiable)

- Never log secrets; rely on this project's log-redaction mechanism (if any)
  and verify it covers new sinks.
- Never hard-code credentials. Read from settings/env.
- Treat all untrusted external input as sensitive - no unredacted raw input
  in logs, exceptions, stored reports, or API error bodies.
- Untrusted input must never reach a shell, SQL string, `eval`, or an AI
  prompt without sanitization/parameterization.

> **SME REVIEW NEEDED (AI-drafted - verify before relying on this):**
> 
> ## threat-model-resolve-markers.md (draft)
> 
> ### 1. Scope
> 
> The `generate --resolve-markers` / `--update-guidelines` path, which is the only part of
> this project that leaves the local machine or executes another program. Four trust
> boundaries: (a) `templates/**` content and the marker instructions extracted from it into
> a model prompt; (b) the *researched target project's* files, read by
> `resolver.gather_context` or by the headless session, flowing into a model prompt; (c)
> model output flowing back onto the filesystem via `resolver.render`,
> `markers.apply_replacements`, and `resolver.render_milestone`; (d) the `claude` CLI
> subprocess spawned by `headless.resolve_tree_headless`. Out of scope: the plain offline
> `generate`, which is a filesystem copy with regex substitution and no network.
> 
> ### 2. Assets
> 
> - `ANTHROPIC_API_KEY` - read by `resolver.load_api_key` from the environment or a `.env`
>   in the cwd, seeded into `os.environ` by `ai.client.build_client`, and forwarded into
>   the subprocess env in `headless.resolve_tree_headless`.
> - The researched project's source code and internal design docs - `gather_context`
>   inlines its `README.md`, `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, dependency
>   manifest, source-tree listing, and `docs/adr/*.md` heads into an outbound request.
> - The user's working tree - the session runs with `cwd=project_root` and holds `Edit`
>   (plus `Write` under `--update-guidelines`).
> - Generated `.claude/settings.json`, which encodes permission allow/deny lists and hook
>   wiring for the target project.
> 
> ### 3. Threat actors
> 
> An author of a hostile or compromised repository that `awesome-templates` is pointed at;
> a contributor of a malicious template or specialization; a manipulated or simply wrong
> model response; a local attacker able to prepend to `PATH`.
> 
> ### 4. STRIDE
> 
> - **Spoofing** - `headless.find_claude` resolves the binary with `shutil.which("claude")`
>   and nothing pins it, so a `PATH` entry under attacker control receives the API key in
>   its environment and the full prompt on stdin.
> - **Tampering** - `render_milestone` interpolates model-supplied `plan["task_slug"]` and
>   `subtask["slug"]` directly into filesystem paths, unvalidated, and
>   `seed_first_milestone` calls `shutil.rmtree(milestone_dir)` before writing them: a
>   traversal-shaped slug writes outside the milestone directory. Separately,
>   `dependencies.write_inline_dependencies` mutates `templates/**` in place under
>   `--inline`/`--remove`.
> - **Repudiation** - `build_command` passes `--no-session-persistence`, so no transcript
>   survives; only `proc.stdout[-2000:]` reaches the `info` log. Reconciliation is a
>   before/after `markers.scan_tree` diff rather than the model's self-report, which is the
>   right call and should stay that way.
> - **Information disclosure** - a third party's proprietary code is uploaded on every run
>   with no per-run consent step. On a non-zero exit, `proc.stderr[-500:]` is appended to
>   `warnings` and printed, which can surface credential-bearing error text.
> - **Denial of service** - `_TIMEOUT_SECONDS = 3600` combined with
>   `capture_output=True` buffers an hour of output in memory; the fallback
>   `resolver.resolve_tree` issues one billed API call per marker with no cap.
> - **Elevation of privilege** - the session runs with `--permission-mode
>   bypassPermissions` (documented as necessary because Claude Code blocks `Edit` under
>   `.claude/**` otherwise), so the "closed set of files you may edit" is enforced by prompt
>   text alone. Content in a hostile researched repo is therefore a prompt-injection path
>   into a session with write access to the user's tree.
> 
> ### 5. Mitigations
> 
> Existing controls: the hard tool allowlist in `headless._BASE_TOOLS` (Read, Grep, Glob,
> Edit, TodoWrite - no Bash, no network tools; `Write` added only under
> `--update-guidelines`); `--setting-sources user`, which stops the generated kit's own
> hooks from firing on the session's edits; the prompt passed over stdin rather than argv,
> with no shell involved; reconciliation by scan diff; `SME REVIEW NEEDED` output never
> silently resolved away (`resolver.render`); `markers._is_quoted`, which refuses to
> resolve marker syntax quoted inside code spans or fences; and non-destructive defaults
> (`--force` required to overwrite, per-increment idempotency sentinels).
> 
> Open gaps, roughly in priority order: no validation of model-supplied path components in
> `render_milestone`; no enforced path jail behind the prompt-level file allowlist; no
> integrity pin or explicit-path option for the `claude` binary; no redaction filter on the
> stderr tail appended to `warnings`; no gate on model output before it is spliced to disk
> (a detector for this is designed but deferred - see
> `../roadmap/0003-api-based-marker-research/plan.md`, "Quality gate on the output").
> 
> ### 6. Verdict
> 
> Draft assessment, not a completed review: no CRITICAL identified. The unvalidated
> model-supplied path components and the prompt-only file-scope boundary under
> `bypassPermissions` both read as HIGH and should be confirmed or downgraded by a human
> reviewer before this file is treated as authoritative.
