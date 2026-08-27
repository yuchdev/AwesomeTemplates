# Java Coding Standard

Practical Java coding standard for this template. It is based primarily on the
Google Java Style Guide, but rewritten here as a concise, navigable reference
for project use rather than a verbatim upstream copy.

## Table of contents

- [1. Scope and principles](#1-scope-and-principles)
- [2. Source files](#2-source-files)
- [3. File structure](#3-file-structure)
- [4. Formatting](#4-formatting)
- [5. Language usage](#5-language-usage)
- [6. Naming](#6-naming)
- [7. Programming practices](#7-programming-practices)
- [8. Documentation and comments](#8-documentation-and-comments)
- [9. Imports and packages](#9-imports-and-packages)
- [10. Review checklist](#10-review-checklist)

## 1. Scope and principles

### 1.1 Goals

- Optimize for readability and maintainability.
- Prefer consistency with nearby code when several acceptable forms exist.
- Treat this guide as the default for all `.java` sources unless a submodule or
  generated code has stricter local rules.

### 1.2 Reference hierarchy

When this document is silent on a detail, follow the Google Java Style Guide.
If local code already uses a stable house style, match the surrounding file so
long as that does not reduce clarity.

## 2. Source files

### 2.1 File names

- Use the exact top-level type name plus `.java`.
- Keep one public top-level class, interface, enum, record, or annotation per
  file.

### 2.2 Encoding and whitespace

- Use `UTF-8`.
- Use spaces, never tabs, for indentation.
- Use Unix line endings when possible.
- Keep trailing whitespace out of commits.

### 2.3 Characters and literals

- Prefer readable source text over escaped Unicode when the character is clear.
- Use standard escape sequences such as `\n`, `\t`, and `\\` instead of octal
  or obscure Unicode escapes.
- Escape non-printable characters and add a short clarifying comment when the
  meaning is not obvious.

## 3. File structure

Arrange source files in this order:

1. License or copyright header, if required.
2. Package declaration.
3. Imports.
4. One top-level type.

Within a type, use this order unless a local convention is already established:

1. Constants.
2. Static fields.
3. Instance fields.
4. Constructors.
5. Public methods.
6. Protected methods.
7. Package-private methods.
8. Private methods.
9. Nested types.

Keep overloads adjacent.

## 4. Formatting

### 4.1 Braces

- Always use braces for `if`, `else`, `for`, `do`, and `while` bodies.
- Put the opening brace at the end of the controlling line.
- Put `else`, `catch`, and `finally` on the same line as the preceding closing
  brace.

```java
if (isReady) {
    run();
} else {
    recover();
}
```

### 4.2 Indentation and line wrapping

- Indent blocks with `4` spaces.
- Continuation lines should make the wrapped structure obvious; prefer breaking
  before operators only when it materially improves readability.
- Keep line length around `100` columns unless the surrounding code or tooling
  uses a different enforced limit.

### 4.3 Spacing

- Use one space after keywords like `if`, `for`, `catch`, and `switch`.
- Use one space around binary and ternary operators.
- Do not add spaces just inside parentheses, brackets, or braces.
- Put one space after commas and semicolons in `for` headers.

### 4.4 Vertical structure

- Use a single blank line between logical sections.
- Avoid excessive empty lines that visually fragment a method.
- Prefer short methods and short blocks over deep nesting.

## 5. Language usage

### 5.1 Prefer clarity over cleverness

- Write straightforward control flow.
- Avoid surprising side effects inside expressions.
- Use early returns to reduce nesting when they improve readability.

### 5.2 Exceptions

- Never swallow exceptions silently.
- Catch the most specific exception you can handle meaningfully.
- Preserve the original cause when wrapping exceptions.
- Do not use exceptions for normal control flow.

### 5.3 Nullability and optionality

- Make null-handling explicit in APIs.
- Prefer annotations or types already used by the project for null contracts.
- Use `Optional` sparingly and primarily for return values, not fields or
  parameters, unless the local framework clearly expects it.

### 5.4 Collections and streams

- Prefer interfaces (`List`, `Map`, `Set`) in APIs unless a concrete type is
  required.
- Use immutable collections when mutation is not needed.
- Keep stream pipelines readable; switch to loops when side effects, branching,
  or debugging become awkward.

## 6. Naming

### 6.1 Type names

- Classes, interfaces, records, enums, and annotations use `UpperCamelCase`.
- Use nouns or noun phrases for types.

### 6.2 Method names

- Methods use `lowerCamelCase`.
- Use verbs or verb phrases.
- Boolean-returning methods should read like predicates, such as `isReady()` or
  `hasChildren()`.

### 6.3 Variables and fields

- Local variables and parameters use `lowerCamelCase`.
- Constants use `UPPER_SNAKE_CASE`.
- Prefer descriptive names over abbreviations, except for well-known short names
  like `id`, `url`, or loop indices in tiny scopes.

### 6.4 Packages

- Use all lowercase package names.
- Keep package structure aligned with domain boundaries, not implementation
  accidents.

## 7. Programming practices

### 7.1 Class design

- Keep classes focused on one responsibility.
- Favor composition over inheritance unless inheritance clearly models the
  domain.
- Minimize mutable shared state.

### 7.2 Methods

- Keep methods small enough to read in one pass.
- Prefer a small number of clearly named helper methods over one large method.
- Avoid long parameter lists; introduce parameter objects when the grouping is
  real and stable.

### 7.3 Visibility

- Use the narrowest visibility that works.
- Do not widen visibility only for tests when package-private structure or test
  seams can solve the problem more cleanly.

### 7.4 Logging

- Log actionable information.
- Do not log and rethrow the same exception unless the extra context is useful
  and non-duplicative.
- Never log secrets, tokens, credentials, or personal data.

## 8. Documentation and comments

### 8.1 Javadoc

Add Javadoc for:

- Public types.
- Public and protected methods when behavior is not obvious from the signature.
- Public constants whose meaning is not self-evident.

Javadoc should explain intent, contracts, side effects, and constraints. It
should not restate the method name in sentence form.

### 8.2 Implementation comments

- Comment the why, not the obvious what.
- Keep comments updated with code changes.
- Delete stale TODOs and misleading commentary.

### 8.3 TODO format

Use TODOs only for specific follow-up work.

```text
TODO(username): Replace this temporary parser when schema v2 lands.
```

## 9. Imports and packages

### 9.1 Imports

- Do not use wildcard imports.
- Remove unused imports.
- Group imports consistently; if no project-specific formatter is enforced, use:
  1. static imports
  2. `java.*` / `javax.*`
  3. third-party imports
  4. project imports

Separate groups with a single blank line.

### 9.2 Static imports

- Use static imports sparingly.
- Prefer them only when they materially improve readability, such as in tests.

## 10. Review checklist

Before merging Java changes, confirm that:

- the file and type names match;
- formatting is consistent with this guide and the surrounding code;
- exceptions are handled explicitly and meaningfully;
- visibility is as narrow as practical;
- imports are minimal and ordered;
- comments and Javadoc still match behavior;
- logs are useful and do not leak sensitive data.

## Sources

- Google Java Style Guide: the primary upstream basis for this document.
- Local project conventions: use them when a module already enforces stricter or
  more specific formatting and architectural rules.
