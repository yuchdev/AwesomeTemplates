# Test classification & JSDoc-comment guide

Backs `/document-tests`. The `scripts/document_tests.py` codemod classifies
**mechanically** from structural signals; this guide gives the **semantic**
definitions you use to hand-resolve the `Ambiguous classification` cases it
flags, plus the JSDoc-comment format the script emits.

## How the script classifies (match its logic when overriding)

Directory and filename first, then body markers:

1. Path contains an `e2e` or `cypress` directory, or the filename has an `.e2e.`
   segment (`checkout.e2e.spec.ts`) → **E2E**, regardless of body content.
2. Path contains an `integration` directory, or the filename has an
   `.integration.`/`.int.` segment → **E2E** if the test drives a real browser,
   else **Integration**.
3. Path contains a `unit`/`test`/`tests`/`__tests__`/`spec` directory, or the
   file is a `*.test.*` file anywhere (the co-located convention) → **E2E** if
   the test drives a real browser; else **Mock** if the test or its module uses
   a mocking marker; else **Unit**.
4. A `*.spec.*` file outside any test directory → same body-based guess as
   step 3, **flagged `ambiguous`**. The `.spec` suffix means "Playwright browser
   test" in some projects and "Vitest/Jasmine unit test" in others.

Markers the script looks for (case-insensitive substring match):

- **Browser (E2E):** a Playwright `({ page })` fixture, `page.goto(`,
  `page.locator(`, `page.getByRole(`, `page.click(`, `page.fill(`, `cy.visit(`,
  `cy.get(`, `browser.url(`, `browser.newPage(`, `puppeteer.launch(` - in the
  test call itself.
- **Mocking, in the test call:** `vi.fn(`, `vi.spyOn(`, `vi.useFakeTimers(`,
  `vi.stubGlobal(`, `jest.fn(`, `jest.spyOn(`, `jest.useFakeTimers(`,
  `mock.fn(`, `mock.method(`, `mock.timers`, `sinon.`, `server.use(`, `nock(`,
  `fetchMock`, `mockResolvedValue`, `mockReturnValue`, `mockImplementation`.
- **Mocking, anywhere in the file:** `vi.mock(`, `vi.doMock(`, `jest.mock(`,
  `jest.unstable_mockModule(`, `setupServer(`, `setupWorker(`. Vitest and Jest
  hoist module mocks above the imports, so they apply to every test in the file
  even though none of them appears inside a test body.

`ambiguous` means "no directory convention matched" — the script guessed from
the body only. Those are the cases you must read and confirm.

## Semantic definitions (the ground truth for resolving ambiguity)

| Class           | Real meaning                                                                                                                                                  | {{PROJECT_NAME}} examples                                                                 |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| **Unit**        | Pure logic, no mocking, no network/storage/timer I/O. Isolated by construction, not by mocking. Rendering into an in-process DOM (jsdom/happy-dom) with no fakes still counts. | A price formatter, a form validator, a function that builds a list element from data.     |
| **Mock**        | Unit-scoped but a collaborator is replaced with a fake. Tests behaviour *around* an external boundary without hitting it.                                     | A profile loader with `fetch` stubbed; a theme toggle with `localStorage` faked.           |
| **Integration** | Two or more real modules wired together against a DOM, externals faked at the network/storage edge. Not a pure unit; not a full browser journey.              | A search box + results list + URL-state module mounted together with an MSW server.        |
| **E2E**         | A full user-facing journey in a real browser — Playwright, Cypress, WebdriverIO, Puppeteer — even if some network routes are stubbed.                          | Opening the home page, following the nav link, and submitting the contact form.            |

Resolution rule of thumb when the script flags ambiguous:

- Fakes present but only one module under test → **Mock**, not Integration.
- Real modules wired together, network/storage edge faked → **Integration**.
- A real browser page anywhere in the test → **E2E**, regardless of stubbed routes.
- No fakes, no browser, pure inputs/outputs → **Unit**.

The precedence when signals conflict is **E2E > Integration > Mock > Unit** — the
outer boundary being exercised is what a future reader cares about most. This
matches the classification model already published in `test-documenter`
(`.claude/agents/test-documenter.md`); keep the two in sync if either changes.

## JSDoc-comment format the script emits

Title line must match:
`^\[(Unit|Mock|Integration|E2E)\] <context>: verifies "<test title>".$`
where `<context>` is the enclosing `describe` titles joined with ` > ` (or the
file's base name when there is no `describe`), followed by **Scenario**,
**Boundaries**, and **On failure, first check** stanzas.

A full worked specimen — one correctly-documented test per classification,
each also exhibiting the body signal the codemod keys on — is in
[../example/documented-test-example.js](../example/documented-test-example.js).

### Good

```js
describe('price format', () => {
  /**
   * [Unit] price format: verifies "renders cents with two decimals".
   *
   * Scenario:
   *   - Given an amount of 1999 cents with no fakes or I/O
   *   - When formatPrice(1999, 'USD') executes
   *   - Then the result is confirmed to be "$19.99"
   *
   * Boundaries:
   *   - Focus: the cents-to-decimal conversion
   *   - Fixtures/params: none
   *   - Scope: pure function, no DOM or network
   *
   * On failure, first check:
   *   - The Intl.NumberFormat options in formatPrice
   */
  it('renders cents with two decimals', () => { ... });
});
```

### Bad (why)

```js
// no [Class] tag, no 'verifies', no stanzas
/** Tests the price thing. */
it('works', () => { ... });
```

The bad one fails the title regex, carries no classification, and gives an
on-call reader nothing to act on when it breaks.

## Boundaries of this skill

JSDoc comments only. Never change test logic, fixtures, assertions, titles, or
imports. Leave any test that already has a custom (non-generated) doc comment
untouched unless the user explicitly asked to `--force` that specific file.
