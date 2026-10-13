/**
 * Reference specimen for /document-tests - the JSDoc-comment format, one per
 * classification.
 *
 * This is a *teaching example*, not a collected test. It lives under
 * `.claude/`, and its filename has no `.test.`/`.spec.` segment, so neither
 * `scripts/document_tests.py` nor a test runner's default include glob (Vitest,
 * Jest, and Playwright all match `*.{test,spec}.*`) ever picks it up. Each test
 * case below shows two things at once:
 *
 *   1. the structural signal `scripts/document_tests.py` keys on to classify
 *      it, and
 *   2. the exact JSDoc comment the codemod emits, as described in
 *      `../references/classification-guide.md`.
 *
 * JSDoc-comment contract (enforced by the codemod's title regex
 * `^\[(Unit|Mock|Integration|E2E)\] .+: verifies .+\.$`):
 *
 *   [<Class>] <describe > chain>: verifies "<test title>".
 *
 *   Scenario: ...
 *   Boundaries: ...
 *   On failure, first check: ...
 *
 * The module below, `widgetkit`, is a deliberately fictional library so
 * nothing here looks like it should resolve against your own code. Read the
 * *shape* - a real test importing the module under test and asserting on real
 * behavior - and copy the JSDoc comments, not the names.
 *
 * Note on classification: in a real project each of these four cases would
 * live in its own conventional place - a co-located `streak.test.js` or
 * `tests/unit/`, `tests/integration/`, and `tests/e2e/` (a Playwright
 * `*.spec.js`) - and the directory or filename signal alone would settle the
 * Integration and E2E tags. The E2E case also uses Playwright's `test`, not
 * Vitest's; it is shown here only to keep all four specimens side by side.
 */

import { describe, expect, it, vi } from 'vitest';

import { loadProfile } from './widgetkit/profile.js';
import { mountSearch } from './widgetkit/search.js';
import { nextStreak } from './widgetkit/streak.js';

// ----------------------------------------------------------------------- //
// [Unit] - pure logic, no fakes, no I/O. Signal: no mock/browser markers.
// ----------------------------------------------------------------------- //
describe('streak', () => {
  /**
   * [Unit] streak: verifies "a missed day resets the streak to zero".
   *
   * Scenario:
   *   - Given a current streak of 5 and a 2-day gap since the last check-in
   *   - When nextStreak(5, 2) executes
   *   - Then the result is confirmed to be 0
   *
   * Boundaries:
   *   - Focus: the gap > 1 branch of nextStreak
   *   - Fixtures/params: none
   *   - Scope: pure function, no DOM or network
   *
   * On failure, first check:
   *   - The day-gap comparison in nextStreak
   */
  it('a missed day resets the streak to zero', () => {
    expect(nextStreak(5, 2)).toBe(0);
  });
});

// ----------------------------------------------------------------------- //
// [Mock] - one module, an external boundary faked. Signal: vi.fn( / vi.mock(.
// ----------------------------------------------------------------------- //
describe('profile loader', () => {
  /**
   * [Mock] profile loader: verifies "a failed request shows the retry message".
   *
   * Scenario:
   *   - Given a stubbed fetch that resolves with a 503 response
   *   - When loadProfile(fetchStub) executes
   *   - Then the result is confirmed to be { state: 'error', retry: true }
   *
   * Boundaries:
   *   - Focus: the !response.ok branch of loadProfile
   *   - Fixtures/params: fetchStub (vi.fn)
   *   - Scope: loader module only, network faked
   *
   * On failure, first check:
   *   - The response.ok check and error mapping in loadProfile
   *   - Whether the stub's resolved shape still matches the real fetch Response
   */
  it('a failed request shows the retry message', async () => {
    const fetchStub = vi.fn().mockResolvedValue({ ok: false, status: 503 });
    await expect(loadProfile(fetchStub)).resolves.toEqual({ state: 'error', retry: true });
    expect(fetchStub).toHaveBeenCalledOnce();
  });
});

// ----------------------------------------------------------------------- //
// [Integration] - real modules wired against a DOM. Signal (in a real
// project): the tests/integration/ directory.
// ----------------------------------------------------------------------- //
describe('search', () => {
  /**
   * [Integration] search: verifies "typing a query renders matching results".
   *
   * Scenario:
   *   - Given the real search box, results list, and URL-state modules mounted
   *     into a jsdom container with an in-memory index
   *   - When the user types "tea" into the search box
   *   - Then the results list is confirmed to show exactly the two matching items
   *
   * Boundaries:
   *   - Focus: input event -> query -> rendered list
   *   - Fixtures/params: in-memory index of three items
   *   - Scope: three real modules, no network
   *
   * On failure, first check:
   *   - The input-event debounce in mountSearch
   *   - The index's case-insensitive matching
   */
  it('typing a query renders matching results', async () => {
    const container = document.createElement('div');
    mountSearch(container, { index: ['Green tea', 'Black tea', 'Coffee'] });
    const input = container.querySelector('input[type="search"]');
    input.value = 'tea';
    input.dispatchEvent(new Event('input'));
    await vi.waitFor(() => expect(container.querySelectorAll('li')).toHaveLength(2));
  });
});

// ----------------------------------------------------------------------- //
// [E2E] - a real browser page. Signal: the ({ page }) fixture / page.goto(.
// In a real project this lives in tests/e2e/home.spec.js with
// `import { test, expect } from '@playwright/test'`.
// ----------------------------------------------------------------------- //
/**
 * [E2E] home: verifies "the nav link opens the about page".
 *
 * Scenario:
 *   - Given the site served locally and a fresh browser page
 *   - When the user clicks the "About" link in the main navigation
 *   - Then the URL is confirmed to end in /about and the page heading reads "About"
 *
 * Boundaries:
 *   - Focus: navigation from the home page
 *   - Fixtures/params: Playwright page fixture
 *   - Scope: full page load in a real browser
 *
 * On failure, first check:
 *   - The href on the About link in the site header
 *   - Whether the local server started before the test ran
 */
it('the nav link opens the about page', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'About' }).click();
  await expect(page).toHaveURL(/\/about$/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('About');
});
