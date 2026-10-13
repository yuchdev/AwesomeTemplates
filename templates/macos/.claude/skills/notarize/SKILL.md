---
name: notarize
description: User-invoked as /notarize [path-to-app-or-dmg]. Walks a built macOS artefact through the Developer ID release gate - verifies nested code is signed with Hardened Runtime and a secure timestamp, prepares the notarytool submission, diagnoses an Invalid result from the notary log, and checks stapling and Gatekeeper acceptance. Use before publishing any release candidate or when notarization is rejected.
allowed-tools: Read, Grep, Glob, Bash, Agent
invocation: /notarize [path]
---

# Notarize

Gate a built artefact (`.app`, `.dmg`, `.pkg`, or `.zip`) at `$ARGUMENTS` against the
Developer ID notarization requirements. This is the mechanical checklist companion to
`release-engineer`; hand any fix to that agent (or to `swift-expert` / `cpp-expert` when
the defect is in how a binary is built).

This skill **verifies and prepares**. It does not run `notarytool submit` unless the
user explicitly asks in this session - a submission uploads the build to Apple.

## Steps

1. **Locate the artefact.** Resolve `$ARGUMENTS`; if empty, look for `*.app`, `*.dmg`,
   `*.pkg` under `build/`, `dist/`, and `.build/release`. Stop and ask if none or
   several plausible ones exist.
2. **Enumerate every Mach-O in the bundle**: `find <app> -type f \( -perm +111 -o -name
   "*.dylib" -o -name "*.so" \)` and, for each, `file` to keep real Mach-O binaries only.
   Nested helpers, XPC services, login items, frameworks, plug-ins, and bundled C++
   dylibs are all in scope.
3. **For each Mach-O, check**:
   - **Signed** - `codesign --verify --strict <path>` succeeds.
   - **Hardened Runtime** - `codesign -dv <path>` shows `flags=...(runtime)`.
   - **Secure timestamp** - `codesign -dvv <path>` shows a `Timestamp=` line (not
     `Signature=adhoc`).
   - **Developer ID Application** authority, with a consistent `TeamIdentifier` across
     the whole bundle.
   - **Install names** - `otool -L <path>` shows no absolute `/opt/homebrew`,
     `/usr/local`, or build-directory paths; dependencies resolve via `@rpath` /
     `@executable_path` / `@loader_path` to something inside the bundle.
4. **Check the bundle as a whole**: `codesign --verify --deep --strict --verbose=2
   <app>`; confirm no `get-task-allow` entitlement (a debug entitlement that fails
   notarization) via `codesign -d --entitlements :- <app>`.
5. **Prepare the submission** (show, don't run):
   ```bash
   ditto -c -k --keepParent MyApp.app MyApp.zip
   xcrun notarytool submit MyApp.zip --keychain-profile "<profile>" --wait
   xcrun stapler staple MyApp.app
   xcrun stapler validate MyApp.app
   spctl --assess --type execute --verbose=4 MyApp.app
   ```
   Name the keychain profile only - never ask for or echo an Apple ID, app-specific
   password, or API key.
6. **If a submission came back `Invalid`**, fetch the log with `xcrun notarytool log
   <id> --keychain-profile "<profile>"` and map each issue to its fix:

   | Notary message                                   | Fix                                                        |
   |--------------------------------------------------|------------------------------------------------------------|
   | "The binary is not signed with a valid Developer ID certificate" | Re-sign that component with the Developer ID Application identity |
   | "The signature does not include a secure timestamp" | Add `--timestamp` when signing                          |
   | "The executable does not have the hardened runtime enabled" | Add `--options runtime`                          |
   | "The binary uses an SDK older than the 10.9 SDK" | Rebuild with a current SDK / raise the deployment target    |
   | "The signature of the binary is invalid"         | A file changed after signing - re-sign inside-out, last     |
   | `get-task-allow` present                         | Strip the debug entitlement from the release entitlements   |

## Output

```
## Notarize - <artefact>
Mach-O binaries checked: N
Defects: M
### <path> - <check failed>
- Why: <one sentence>
- Fix: <one sentence>
Gatekeeper (spctl): accepted | rejected | not yet notarized
Verdict: READY TO SUBMIT | <M> defect(s) to fix first
```

## Completion checklist

- [ ] Every Mach-O in the bundle was checked, including nested helpers and bundled dylibs
- [ ] Signing, Hardened Runtime, timestamp, and authority were each verified, not assumed from the outer app
- [ ] `get-task-allow` and absolute install names were checked
- [ ] No credential, key, or password was read, printed, or requested
- [ ] No submission was made to Apple without the user's explicit instruction
- [ ] Fixes were handed to `release-engineer`, not edited by this skill
