# 01 - Config model

**Parent story:** [README.md](README.md)
**Owner:** `swift-expert`
**Status:** ⬜ Not started

## Objective

This task is a stub to rename and implement a real one.
All subsequent paragraphs also should be rewritten into a real task.

## Files

- `Sources/{{PROJECT_PACKAGE}}/Config/AppConfig.swift` - new `AppConfig` struct.
- `Tests/{{PROJECT_PACKAGE}}Tests/AppConfigTests.swift` - default value + override test.

## Types and Functions

- `AppConfig` struct (`Sendable`, `Equatable`) with a `let greeting: String` property,
  defaulting to `"Hello from {{PROJECT_NAME}}"`, and a failable/throwing loader.

## Constraints

- None

## Success criteria

- [ ] Implement `AppConfig` as an immutable value type with a `greeting` property, defaulting to `"Hello from {{PROJECT_NAME}}"`.
- [ ] Implement loading logic for `AppConfig` (e.g. from `UserDefaults` or a bundled plist).
- [ ] Implement the default value for `AppConfig`.
- [ ] Implement unit tests for `AppConfig`.
