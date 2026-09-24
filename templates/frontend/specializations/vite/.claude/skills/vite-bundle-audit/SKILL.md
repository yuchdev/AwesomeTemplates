---
name: vite-bundle-audit
description: User-invoked as /vite-bundle-audit. Builds the project with Vite and audits what actually ships - secrets leaked through VITE_-prefixed environment variables, oversized chunks and their causes, published source maps, and dev-only code left in production output. Use before a release, and after any change to environment variables, dependencies, or code splitting.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /vite-bundle-audit
---

# Vite Bundle Audit

Audit the production build, not the source. Vite inlines every `VITE_`-prefixed variable
into the output as plain text, so the built `dist/` is the only place to confirm what a
visitor can actually download. Every file there is public.

## Steps

1. **Build**: `npm run build` (or `npx --no-install vite build`). Record the chunk-size
   summary it prints. If the build fails, stop and hand the failure to `vite-expert`.
2. **Env-variable exposure**:
   - List the variable **names** in `.env`, `.env.production`, and `.env.*.local` that
     carry the client prefix (`VITE_` or the configured `envPrefix`). Never print values.
   - Flag any name that suggests a secret (`SECRET`, `PRIVATE`, `PASSWORD`, `TOKEN`,
     `KEY` other than a publishable/public key, `DATABASE_URL`, `SERVICE_ROLE`) as HIGH -
     it is inlined into the bundle.
   - Run `python .claude/hooks/secret_scan.py` over the files in `dist/` to catch
     credential-shaped strings that reached the output by any route.
   - Confirm `envPrefix` is not `''` and `define` does not inject non-prefixed env values.
3. **Chunk sizes**: list every JS/CSS chunk over ~250 kB (minified, before gzip) or over
   the configured `chunkSizeWarningLimit`. For each, identify the largest contributors
   (`npx vite-bundle-visualizer` or `rollup-plugin-visualizer` if available; otherwise
   `grep` the chunk for package names). Common causes: a whole library imported for one
   function, a locale/icon set bundled in full, a route that should be lazy-loaded.
4. **Source maps**: `find dist -name "*.map"`. Public `.map` files, or a
   `//# sourceMappingURL=` comment in shipped JS, publish the original source - MEDIUM
   unless the project deliberately serves them.
5. **Dev leftovers**: grep `dist/` for `localhost`, `127.0.0.1`, staging hostnames, and
   debug flags that should have been compiled out.
6. **Report** each finding with the file (in `dist/` and its source) and a one-line fix.
   Hand fixes to `vite-expert`, and any exposed secret to `security-auditor` immediately -
   a secret that ever shipped must be rotated, not just removed. This skill reports; it
   does not edit.

## Output

```
## Vite Bundle Audit - <date>
Build: pass | fail
Total JS: <kB> · Total CSS: <kB> · Chunks over limit: N
### [HIGH|MEDIUM|LOW] <finding>
- Where: <dist file> (from <source file or .env name>)
- Fix: <one sentence>
Verdict: CLEAN | <N> finding(s) - <any HIGH blocks release>
```

## Completion checklist

- [ ] Audited a fresh production build, not a stale `dist/`
- [ ] Env files checked by variable name only - no secret value printed in the report
- [ ] `secret_scan.py` run over the built output
- [ ] Every chunk over the limit explained by its largest contributors
- [ ] Source maps and dev-only hostnames checked in `dist/`
- [ ] Any exposed secret escalated to `security-auditor` with a rotation note
