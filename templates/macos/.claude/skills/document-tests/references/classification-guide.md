# Test classification & doc-comment guide

Backs `/document-tests`. The `scripts/document_tests.py` codemod classifies
**mechanically** from structural signals; this guide gives the **semantic**
definitions you use to hand-resolve the `Ambiguous classification` cases it
flags, plus the comment format the script emits (Doxygen for C++, DocC `///` for Swift).

## How the script classifies (match its logic when overriding)

Directory and filename first, then body markers:

1. Path contains an `e2e` directory, or the filename ends `_e2e_test.cpp`/
   `_e2e_test.cc` → **E2E**, regardless of body content.
2. Path contains an `integration` directory, or the filename ends
   `_integration_test.cpp`/`_integration_test.cc`/`IT.cpp`/`IT.cc` → **E2E**
   if the body uses an end-to-end marker, else **Integration**.
3. Path contains a `unit`/`test`/`tests` directory (or an unrecognised
   layout) → **E2E** if the body uses an end-to-end marker; else **Mock** if
   the body uses a GoogleMock marker; else **Unit**.
4. Unrecognised directory → same body-based guess as step 3, **flagged `ambiguous`**.

Body markers the script looks for (case-insensitive substring match):

- **End-to-end:** `std::system(`, ` system(`, `popen(`, `fork(`, `execve(`,
  `boost::process`, `subprocess::`, `curl_easy_`, `httplib::client`,
  `grpc::CreateChannel`, `::socket(`.
- **GoogleMock:** `MOCK_METHOD`, `EXPECT_CALL(`, `NiceMock<`, `StrictMock<`,
  `ON_CALL(`, `::testing::Mock`, `ReturnRef(`, `WillOnce(`, `WillRepeatedly(`.

`ambiguous` means "no directory convention matched" — the script guessed from
the body only. Those are the cases you must read and confirm.

### Swift specifics

For `.swift` files the same precedence applies, with these Swift/Xcode conventions:

1. A path containing an `e2e` directory or any `*UITests` directory, or a filename
   ending `E2ETests.swift`/`UITests.swift` → **E2E**.
2. A path containing an `integration` or `*IntegrationTests` directory, or a filename
   ending `IntegrationTests.swift`/`IT.swift` → **E2E** if the body has an end-to-end
   marker, else **Integration**.
3. A path containing `unit`/`test`/`tests` or any directory ending in `Tests` (SwiftPM's
   `Tests/FooTests/`, Xcode's `FooTests/`) → **E2E** on an end-to-end marker; else
   **Mock** on a test-double marker; else **Unit**.
4. Otherwise the same body guess, **flagged `ambiguous`**.

Swift body markers (case-insensitive substring match):

- **End-to-end:** `Process()`, `NSTask`, `XCUIApplication`, `URLSession.shared`,
  `URLSession(configuration`, `posix_spawn`, `NWConnection`, `NWListener`,
  `executableURL`.
- **Test double:** `mock`, `fake`, `stub`, `spy` - a naming-convention heuristic,
  because Swift has no mocking framework in the toolchain. A type named `MockClock`
  or `FakeKeychain` is what flips a test to **Mock**; a double named `ClockDouble`
  is invisible to the script, which is exactly the kind of miss you correct by hand.
  Substring matching also means an unrelated identifier containing `spy`/`fake` can
  false-positive - read the body before accepting a **Mock** on a flagged file.

What the script discovers: XCTest methods matching `func test…()` with no parameters,
and any `func` carrying an `@Test` attribute (including multi-line
`@Test(arguments: …)` and stacked attributes such as `@MainActor`). The comment is
inserted above the topmost attribute. Helper methods like `func testHelper(arg:)` are
deliberately not matched.

## Semantic definitions (the ground truth for resolving ambiguity)

| Class           | Real meaning                                                                                                                  | {{PROJECT_NAME}} examples                                                              |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| **Unit**        | Pure logic, no mocking, no filesystem/network/device I/O. Isolated by construction, not by mocking.                          | A parsing routine, a mapper, a pure math/domain function.                               |
| **Mock**        | Unit-scoped but a collaborator is replaced with a GoogleMock fake (C++) or a hand-written protocol-based test double (Swift). Tests behaviour *around* an external boundary without hitting it. | A repository test with the storage backend mocked; a service test with the clock/network client mocked. |
| **Integration** | Two or more real components wired together, externals mocked or sandboxed at the process edge. Not a pure unit; not a full user flow. | A service + an in-memory store; a real parser over a fixture file.                       |
| **E2E**         | A full user-facing journey driven end to end — a spawned subprocess, a real network/RPC call, a launched app driven through `XCUIApplication`, or an end-to-end CLI/service action — even if some internals are mocked. | A CLI invocation via `boost::process`; a service test that opens a real socket; an `XCUIApplication` launch test. |

Resolution rule of thumb when the script flags ambiguous:

- Mocks present but only one unit under test → **Mock**, not Integration.
- Real collaborators wired together, external edge mocked/sandboxed → **Integration**.
- A subprocess/socket/RPC marker anywhere in the body → **E2E**, regardless of mocks.
- No mocks, no subprocess/socket markers, pure inputs/outputs → **Unit**.

The precedence when signals conflict is **E2E > Integration > Mock > Unit** — the
outer boundary being exercised is what a future reader cares about most. This
matches the classification model already published in `test-documenter`
(`.claude/agents/test-documenter.md`); keep the two in sync if either changes.

## Comment format the script emits (Doxygen for C++, DocC `///` for Swift)

Title line must match:
`^\[(Unit|Mock|Integration|E2E)\] <context>: verifies <one sentence>.$`
followed by **Scenario**, **Boundaries**, and **On failure, first check** stanzas.

Full worked specimens — one correctly-documented test per classification, each also
exhibiting the body signal the codemod keys on — are in
[../example/DocumentedTestExample.cpp](../example/DocumentedTestExample.cpp) (C++) and
[../example/DocumentedTestExample.swift](../example/DocumentedTestExample.swift) (Swift).

### Good

```cpp
/**
 * [Unit] discount tier: verifies subtotal below threshold maps to NONE.
 *
 * Scenario:
 *   - Given a subtotal of 49.99 with no mocks or I/O
 *   - When DiscountTier::fromSubtotal(49.99) executes
 *   - Then the result is confirmed to be DiscountTier::kNone
 *
 * Boundaries:
 *   - Focus: the <50.00 branch of the discount ladder
 *   - Fixtures/params: none
 *   - Scope: pure function, no I/O
 *
 * On failure, first check:
 *   - The 50.00 / 100.00 cutoffs in DiscountTier::fromSubtotal
 */
TEST(DiscountTierTest, BelowThresholdIsNone) { ... }
```

### Bad (why)

```cpp
// no [Class] tag, no 'verifies', no stanzas
/** Tests the discount thing. */
TEST(DiscountTierTest, Stuff) { ... }
```

The same shape in Swift, using `///`:

```swift
/// [Unit] discount tier: verifies subtotal below threshold maps to none.
///
/// Scenario:
///   - Given a subtotal of 49.99 with no test doubles or I/O
///   - When DiscountTier.from(subtotal: 49.99) executes
///   - Then the result is confirmed to be .none
///
/// Boundaries:
///   - Focus: the <50.00 branch of the discount ladder
///   - Fixtures/params: none
///   - Scope: pure function, no I/O
///
/// On failure, first check:
///   - The 50.00 / 100.00 cutoffs in DiscountTier.from(subtotal:)
@Test func belowThresholdIsNone() { ... }
```

The bad one fails the title regex, carries no classification, and gives an
on-call reader nothing to act on when it breaks.

## Boundaries of this skill

Doc comments only. Never change test logic, fixtures, assertions, macro
arguments, attributes, or includes/imports. Leave any test that already has a custom
(non-generated) doc comment untouched unless the user explicitly asked to
`--force` that specific file.
