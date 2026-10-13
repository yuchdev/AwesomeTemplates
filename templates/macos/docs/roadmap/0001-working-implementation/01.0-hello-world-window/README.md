# Story 01.0 - Hello World Window

**Parent milestone:** [plan.md](../plan.md)
**Status:** ⬜ Not started

## Scope

This story is a stub to rename and implement a real one.
All subsequent paragraphs also should be rewritten into a real story.

## Tasks

| #  | Document                                   | Owner          | Status         | Blocks |
|----|--------------------------------------------|----------------|----------------|--------|
| 01 | [Config model](01-config-model.md)         | `swift-expert` | ⬜ Not started | 02     |
| 02 | [Hello window](02-hello-window.md)         | `swift-expert` | ⬜ Not started | 03     |
| 03 | [Tests](03-tests.md)                       | `testing-expert` | ⬜ Not started | -      |

## Key constraints

- No new third-party dependencies.
- Follows this project's existing config-loading convention (see
  `@docs/dev/swift_coding_standard.md`).
- Minimum deployment target and sandbox entitlements are unchanged.

## Files or directories created or modified by this story

- `Sources/{{PROJECT_PACKAGE}}/Config/AppConfig.swift` - new `AppConfig` struct.
- `Tests/{{PROJECT_PACKAGE}}Tests/AppConfigTests.swift` - default value + override test.
- `Sources/{{PROJECT_PACKAGE}}/UI/HelloView.swift` - new SwiftUI view.
- `Sources/{{PROJECT_PACKAGE}}/UI/HelloViewModel.swift` - new `@MainActor` view model.
- Wire the view into the app's existing `Scene` / `WindowGroup`.
- `Tests/{{PROJECT_PACKAGE}}Tests/HelloViewModelTests.swift` - new unit test.
