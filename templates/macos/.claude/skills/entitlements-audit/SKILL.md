---
name: entitlements-audit
description: User-invoked as /entitlements-audit [path]. Finds every .entitlements file and Info.plist privacy/usage key under the given path (default the whole repo), compares them against a fixed least-privilege checklist and against the entitlements actually embedded in a built binary, and reports unjustified, over-broad, or Hardened-Runtime-weakening entries. Use before a release and on any change to an entitlements file, signing setting, or sandbox configuration.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /entitlements-audit [path]
---

# Entitlements Audit

Review every entitlement under `$ARGUMENTS` (default the whole repo) against a
least-privilege checklist. It is a narrower, mechanical companion to
`security-auditor`: an entitlement is a capability grant, and the cheapest defect to
prevent is one that was added "to make it work" and never removed.

## Steps

1. **Find the files**: `Glob **/*.entitlements`, `**/Info.plist`, and
   `grep -rn "CODE_SIGN_ENTITLEMENTS\|ENABLE_HARDENED_RUNTIME\|ENABLE_APP_SANDBOX"
   --include=*.pbxproj --include=*.xcconfig $ARGUMENTS`.
2. **Per component**: map each `.entitlements` file to the target it signs (app, helper,
   XPC service, extension). A helper has its **own** file; do not credit it with the
   app's entitlements.
3. **For each entitlement key, check**:
   - **Justified** - is there a one-line reason in an ADR, the release runbook, or a
     comment? An entitlement with no stated reason is a finding.
   - **Used** - does code actually exercise the capability (a `URLSession` call for
     `network.client`, an `NSOpenPanel` for `files.user-selected.*`)? An unused
     entitlement is a finding.
   - **Narrowest form** - `network.client` rather than `.server` unless the app
     listens; a user-selected file entitlement rather than a home-folder one; no
     `temporary-exception.*` without a tracked removal date.
4. **Flag outright, always** (needs `security-auditor` sign-off and an ADR):
   - `com.apple.security.app-sandbox` = `false` or absent on an App Store target
   - `com.apple.security.cs.disable-library-validation`
   - `com.apple.security.cs.allow-unsigned-executable-memory`
   - `com.apple.security.cs.allow-jit` (only legitimate for a real JIT)
   - `com.apple.security.cs.allow-dyld-environment-variables`
   - `com.apple.security.cs.disable-executable-page-protection`
   - `com.apple.security.get-task-allow` = `true` in a **release** entitlements file
   - any `com.apple.security.temporary-exception.*`
   - `NSAllowsArbitraryLoads` = `true` in `NSAppTransportSecurity`
5. **Privacy usage strings**: every protected-resource capability the code touches
   (camera, microphone, contacts, calendar, location, Apple Events, screen recording,
   files in Desktop/Documents/Downloads) needs the matching `NS*UsageDescription` key
   with a real, user-readable sentence - and a usage string with no matching code path
   is a finding too.
6. **Compare against reality**, if a built binary exists:
   `codesign -d --entitlements :- <app>` and diff the embedded set against the source
   `.entitlements`. Xcode and build settings can add or alter entries; the embedded set
   is what Apple's runtime enforces.
7. **Report every finding** with `file:line`, the key, the rule violated, and a
   one-line fix. Do not report a key as "unused" without actually searching for the
   capability it grants.
8. If findings exist, hand them to `release-engineer` (signing/packaging) or
   `security-auditor` (a weakening entitlement) - this skill reviews, it does not edit.

## Output

```
## Entitlements Audit - <path>
Entitlement files: N   Keys reviewed: K
Findings: M
### <file:line> - <key> - <rule violated>
- Why: <one sentence>
- Fix: <one sentence>
Verdict: CLEAN | <M> finding(s) to address
```

## Completion checklist

- [ ] Every `.entitlements` file was mapped to the target it signs
- [ ] Each key was checked for justification, actual use, and narrowest form
- [ ] The always-flag list was checked explicitly
- [ ] Usage-description keys were cross-checked against code that uses the capability
- [ ] The embedded entitlements of a built binary were compared, or the absence of a build was stated
- [ ] Findings were handed to `release-engineer` / `security-auditor`, not edited here
