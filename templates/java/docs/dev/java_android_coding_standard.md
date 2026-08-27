# Java/Android Coding Standard

Android-oriented Java coding standard derived from the Android Open Source
Project document `AOSP_Java_code_style_for_contributors.html`. Use this guide
for platform-style Java and Android code; when a topic is not covered here,
fall back to the project Java standard.

## Table of contents

- [1. Scope](#1-scope)
- [2. Core rule: be consistent](#2-core-rule-be-consistent)
- [3. Java language rules](#3-java-language-rules)
- [4. Java library rules](#4-java-library-rules)
- [5. Java style rules](#5-java-style-rules)
- [6. Android structure and architecture](#6-android-structure-and-architecture)
- [7. Logging rules](#7-logging-rules)
- [8. Javatests style rules](#8-javatests-style-rules)
- [9. Project-specific overrides](#9-project-specific-overrides)

## 1. Scope

- These rules are intended for Android and Android-platform-style Java code.
- For general Java formatting not restated here, use `java_coding_standard.md`.
- If an existing file has a stable local convention, match it unless doing so
  would make the code less readable.

## 2. Core rule: be consistent

Consistency is the first rule. When editing an existing file:

- match the surrounding brace style, spacing, and comment style;
- keep naming aligned with nearby code;
- preserve local patterns unless they conflict with an explicit rule in this
  guide.

The goal is to keep the reader focused on behavior, not on style changes.

## 3. Java language rules

### 3.1 Do not ignore exceptions

- Never leave an empty `catch` block without a deliberate, documented reason.
- Prefer one of these responses, in order:
  1. propagate the exception;
  2. wrap it in a more appropriate abstraction-level exception;
  3. recover gracefully with a safe fallback;
  4. crash intentionally only when failure is truly unrecoverable.
- If a catch is intentionally empty, explain why in a short comment.

### 3.2 Do not catch generic exceptions

- Catch `Exception`, `Throwable`, or other overly broad types only when the
  framework boundary or cleanup logic genuinely requires it.
- Prefer the narrowest exception type that corresponds to the recovery path.
- Do not hide programmer errors such as `NullPointerException` or
  `IllegalStateException` under generic recovery code.

### 3.3 Do not use finalizers

- Do not rely on finalizers for cleanup.
- Prefer explicit resource management, `try`-with-resources, lifecycle-aware
  cleanup, or platform-specific ownership APIs.

### 3.4 Fully qualify imports only when needed for clarity

- Prefer normal imports for readability.
- Use fully qualified names only to resolve naming conflicts or to make an
  ambiguous API reference explicit.

## 4. Java library rules

- Prefer well-understood standard library facilities before introducing custom
  utilities.
- Use library APIs consistently across a module; do not mix competing idioms
  without a clear reason.
- Be cautious with heavyweight abstractions in framework-sensitive paths such as
  startup, binder boundaries, or UI-critical code.

## 5. Java style rules

### 5.1 Use standard Javadoc comments

- Document public classes, interfaces, enums, records, and annotations.
- Document public and protected methods when behavior, threading, side effects,
  or nullability are not obvious from the signature.
- Write doc comments as complete sentences.
- Prefer describing contracts and constraints over restating the method name.

### 5.2 Write short methods

- Keep methods easy to scan and reason about.
- Split long methods when they mix responsibilities or require heavy scrolling.
- Prefer descriptive helpers over comments that only apologize for method size.

### 5.3 Define fields in standard places

Use a stable field order inside a class:

1. `public static final` constants
2. `private static` fields
3. instance fields
4. constructors
5. public methods
6. non-public helpers

Keep related fields together and keep lifecycle-sensitive fields easy to find.

### 5.4 Limit variable scope

- Declare variables in the narrowest scope possible.
- Initialize variables as close as possible to first use.
- Avoid reusing one local variable for unrelated meanings.

### 5.5 Order import statements

- Do not use wildcard imports.
- Remove unused imports.
- Keep import ordering stable and formatter-friendly.
- If the module has no stricter rule, order imports as:
  1. static imports
  2. `java.*` / `javax.*`
  3. Android / `androidx.*`
  4. third-party imports
  5. project imports

Separate groups with one blank line.

### 5.6 Use spaces for indentation

- Use spaces, not tabs.
- Use `4` spaces for block indentation.
- Wrap continuation lines so the structure is obvious.

### 5.7 Follow standard field naming conventions

- Constants use `UPPER_SNAKE_CASE`.
- Other fields use `lowerCamelCase`.
- Prefixes like `m` or `s` should only be used when they are already the local
  module convention.
- Boolean names should read clearly as state or predicates.

### 5.8 Use standard brace style

- Put the opening brace at the end of the current line.
- Always use braces for conditional and loop bodies.
- Put `else`, `catch`, and `finally` on the same line as the preceding closing
  brace.

### 5.9 Limit line length

- Prefer keeping lines at or below `100` columns unless tooling or surrounding
  code uses a different enforced limit.
- Break long expressions at logical boundaries.

### 5.10 Use standard Java annotations

- Use `@Override` whenever overriding a superclass or interface method.
- Use nullability annotations consistently with the project stack.
- Keep annotations in the conventional position and order used by the module.

### 5.11 Treat acronyms as words

- Use `XmlHttpRequest`, not `XMLHTTPRequest`.
- Use `parseUrl()`, not `parseURL()`.
- Preserve established platform class names when they already exist.

### 5.12 Use TODO comments deliberately

Format TODO comments so ownership or intent is clear:

```text
TODO(username): Remove this workaround after API 35 migration.
```

Do not leave vague TODOs that have no action, owner, or trigger.

## 6. Android structure and architecture

### 6.1 Keep components thin

- Activities, fragments, services, receivers, and views should mainly bind,
  delegate, and manage lifecycle boundaries.
- Put business logic in ViewModels, controllers, use cases, repositories, or
  similarly focused collaborators.

### 6.2 Respect lifecycle and threading

- Make lifecycle ownership explicit.
- Avoid leaking contexts, views, cursors, or callbacks.
- State which thread a method must run on when it is not obvious.

### 6.3 Prefer explicit dependencies

- Constructor injection is preferred where practical.
- Avoid hidden global state and hard-wired singletons in code that needs to be
  tested or reused.

## 7. Logging rules

### 7.1 Log sparingly

- Logging should help diagnose real problems, not narrate every branch.
- Avoid duplicate logs for the same failure across multiple layers.
- Do not log secrets, tokens, personally identifiable information, or noisy
  high-frequency events without a strong operational reason.

### 7.2 Choose log level deliberately

- `ERROR`: something failed and user-visible or system-visible behavior is
  affected.
- `WARN`: something unexpected happened, but recovery is still possible.
- `INFO`: notable state transitions or operational signals worth keeping in
  release builds.
- `DEBUG` / `VERBOSE`: development diagnostics that should be gated or compiled
  out according to module practice.

### 7.3 Avoid log spam

- Log an event once at the layer that has the best context.
- Prefer structured, concise messages over repeated stack traces.

## 8. Javatests style rules

- Test names should describe behavior, not implementation details.
- Keep test setup focused; extract helpers only when they improve readability.
- Prefer deterministic tests with no hidden shared state.
- Separate unit, integration, instrumented, and UI tests according to the
  project’s build and reporting model.
- Assertions should make the failure reason obvious.

## 9. Project-specific overrides

Add local mandatory rules here when a project enforces stricter conventions.
Each override should name its enforcement source, such as:

- a Gradle task;
- Android Lint;
- Detekt, Checkstyle, or Spotless equivalent tooling;
- a CI gate;
- a review checklist.

Keep this section concrete and auditable. Avoid aspirational advice that cannot
be verified in review or automation.

## Sources

- `AOSP_Java_code_style_for_contributors.html`
- `java_coding_standard.md` for baseline Java conventions not repeated here
