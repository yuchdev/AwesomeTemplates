# Test classification & Javadoc guide

Backs `/document-tests`. The `scripts/document_tests.py` codemod classifies
**mechanically** from structural signals; this guide gives the **semantic**
definitions you use to hand-resolve the `Ambiguous classification` cases it flags,
plus the Javadoc format the script emits.

## How the script classifies (match its logic when overriding)

Directory and filename first, then body markers:

1. Path contains an `androidTest` source-set directory → **E2E** (instrumentation
   source set is device/UI by convention, regardless of body content).
2. Path contains an `integrationTest`/`integration` directory, or the filename
   ends `IT.java` (Maven Failsafe convention) → **E2E** if the body uses an
   instrumentation/UI marker, else **Integration**.
3. Path contains a `test` source-set directory (or an unrecognised layout) →
   **E2E** if the body uses an instrumentation/UI marker (a Robolectric+Espresso
   hybrid can still live in the unit source set); else **Mock** if the body uses
   a mocking marker; else **Unit**.
4. Unrecognised directory → same body-based guess as step 3, **flagged `ambiguous`**.

Body markers the script looks for (case-insensitive substring match):

- **E2E/instrumentation:** `Espresso`, `onView(`, `ActivityScenario`,
  `Instrumentation`, `UiAutomator`, `ComposeTestRule`,
  `createAndroidComposeRule`, `intending(`, `Intents.`.
- **Mocking:** `Mockito`, `@Mock`, `mock(`, `when(`, `verify(`, `Robolectric`,
  `PowerMock`, `doReturn(`, `doAnswer(`.

`ambiguous` means "no source-set convention matched" — the script guessed from the
body only. Those are the cases you must read and confirm.

## Semantic definitions (the ground truth for resolving ambiguity)

| Class           | Real meaning                                                                                                                  | {{PROJECT_NAME}} examples                                                              |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| **Unit**        | Pure logic, no mocking, no Android/device I/O. Isolated by construction, not by mocking.                                     | Pricing math, a mapper, a pure domain validator.                                        |
| **Mock**        | Unit-scoped but a collaborator is replaced with Mockito/a fake/Robolectric shadow. Tests behaviour *around* an external boundary without hitting it. | A repository test with the DAO mocked; a service test with the clock/notification scheduler mocked. |
| **Integration** | Two or more real components wired together, externals mocked or sandboxed at the process edge. Not a pure unit; not a full user flow. | Service + an in-memory Room database; a real parser over a fixture file.                 |
| **E2E**         | A full user-facing journey driven end to end — instrumentation/UI (Espresso, `ActivityScenario`, Compose test rule) or an end-to-end CLI/API action — even if some internals are mocked. | A navigation flow through Espresso; a camera-permission grant/deny instrumentation test. |

Resolution rule of thumb when the script flags ambiguous:

- Mocks present but only one unit under test → **Mock**, not Integration.
- Real collaborators wired together, external edge mocked/sandboxed → **Integration**.
- An instrumentation/UI runner anywhere in the body → **E2E**, regardless of mocks.
- No mocks, no runners, pure inputs/outputs → **Unit**.

The precedence when signals conflict is **E2E > Integration > Mock > Unit** — the
outer boundary being exercised is what a future reader cares about most. This
matches the classification model already published in `test-documenter`
(`.claude/agents/test-documenter.md`); keep the two in sync if either changes.

## Javadoc format the script emits

Title line must match:
`^\[(Unit|Mock|Integration|E2E)\] <context>: verifies <one sentence>.$`
followed by **Scenario**, **Boundaries**, and **On failure, first check** stanzas.

A full worked specimen — one correctly-documented test per class, each also
exhibiting the body signal the codemod keys on — is in
[../example/DocumentedTestExample.java](../example/DocumentedTestExample.java).

### Good

```java
/**
 * [Unit] discount tier: verifies subtotal below threshold maps to NONE.
 *
 * <p>Scenario:
 * <ul>
 *   <li>Given a subtotal of 49.99 with no mocks or I/O
 *   <li>When DiscountTier.fromSubtotal(49.99) executes
 *   <li>Then the result is confirmed to be DiscountTier.NONE
 * </ul>
 *
 * <p>Boundaries:
 * <ul>
 *   <li>Focus: the <50.00 branch of the discount ladder
 *   <li>Fixtures/params: none
 *   <li>Scope: pure function, no I/O
 * </ul>
 *
 * <p>On failure, first check:
 * <ul>
 *   <li>The 50.00 / 100.00 cutoffs in DiscountTier.fromSubtotal
 * </ul>
 */
@Test
public void testDiscountTierBelowThresholdIsNone() { ... }
```

### Bad (why)

```java
// no [Class] tag, no 'verifies', no stanzas
/** Tests the discount thing. */
@Test
public void testStuff() { ... }
```

The bad one fails the title regex, carries no classification, and gives an
on-call reader nothing to act on when it breaks.

## Boundaries of this skill

Javadoc comments only. Never change test logic, fixtures, assertions,
annotations, or imports. Leave any test that already has a custom
(non-generated) Javadoc untouched unless the user explicitly asked to `--force`
that specific file.
