# Coverage Requirements Checklist

## Coverage Quick Start

This project targets **85% test coverage** on the JavaScript it ships. Enforce
that threshold in the test runner configuration your project actually uses.
Coverage measures JavaScript only - HTML and CSS are covered by browser tests,
validators, and accessibility checks, not by a line-coverage number.

### Running Tests with Coverage

Use whichever runner the project already has:

```bash
# Node.js built-in runner (no dependencies - suits a plain static site)
node --test --experimental-test-coverage

# Vitest (needs @vitest/coverage-v8)
npx vitest run --coverage

# Jest
npx jest --coverage

# Open: coverage/index.html (Vitest/Jest HTML reporter)
```

### What This Means

- ✅ Coverage is measured from an instrumented test run, not inferred
- ✅ A configured threshold can fail the coverage run when it drops below 85%
- ✅ Coverage reports are available when the chosen runner is configured to emit them

### If Coverage Check Fails

1. **Identify uncovered code**: open `coverage/index.html`
    - Red lines = not covered by tests
    - Yellow lines = partially covered (branch not fully exercised)
    - Green lines = fully covered

2. **Add tests** for the uncovered code, or

3. **Mark intentional exclusions** with an ignore hint the coverage provider
   understands (V8 and Istanbul both accept these):
   ```js
   /* c8 ignore start */
   function unreachableDefensiveBranch() {
     // verified unreachable; guarded for defense-in-depth only
   }
   /* c8 ignore stop */
   ```
   (Istanbul-only projects use `/* istanbul ignore next */`.)

4. **Re-run** the coverage command above.

### Threshold Details

- **Why 85%?** Balances quality with pragmatism
- **Not 100%**: Some code (defensive branches, browser-specific fallbacks) is
  hard/expensive to test
- **Not below 85%**: Ensures critical code paths are tested

### Configuration

The threshold lives in the runner's config - `coverage.thresholds` in
`vitest.config.js`, `coverageThreshold` in Jest's config, or
`--test-coverage-lines=85` for `node --test`.

### Tips

- Run a single test file: `node --test path/to/file.test.js`,
  `npx vitest run path/to/file.test.js`, or `npx jest path/to/file.test.js`
- Filter by test name: `--test-name-pattern` (node), `-t` (Vitest/Jest)
- Faster local iteration: run without coverage, then re-run with coverage before merging
- Update the threshold: change the runner's configured minimum (don't lower
  it casually)

## Checklist Before Submitting a Pull Request

### ✅ Local Testing

- [ ] Ran the full test suite with coverage (command above)
- [ ] Ran browser/E2E tests for any user-visible change
  ```bash
  npx playwright test
  ```
- [ ] Coverage is ≥ 85%
  - [ ] The runner's coverage summary shows ≥ 85% line coverage
  - [ ] No failing test in the run

### ✅ Code Review

- [ ] Reviewed uncovered code in `coverage/index.html`
  - [ ] Red lines (uncovered) are intentional or excluded with an ignore hint
  - [ ] If uncovered, added an ignore hint with a one-line reason
  - [ ] New code has test coverage ≥ 85%

- [ ] If coverage decreased:
  - [ ] Added new tests for new code paths
  - [ ] Documented why exclusions are needed
  - [ ] Consulted with team if the threshold is concerning

### ✅ Commit & Push

- [ ] Commit message references coverage status
  ```
  feat: add new feature with 87% coverage
  - Added 5 new test cases
  - Coverage improved from 82% to 87%
  ```

- [ ] Push to feature branch
  - [ ] CI pipeline runs successfully
  - [ ] All coverage checks pass
  - [ ] Coverage report available in CI artifacts

### ✅ Pull Request

- [ ] PR description includes:
  - [ ] Coverage before/after numbers
  - [ ] Any code intentionally excluded from coverage
  - [ ] Testing approach for new code (unit, DOM, browser)

## Adding New Code

### For New Modules

1. **Create test file** first (TDD approach):
   ```
   src/js/feature/module.js
   src/js/feature/module.test.js   <- create this first (or tests/unit/feature/module.test.js)
   ```

2. **Write tests** for all exported functions
   ```js
   // src/js/feature/module.test.js
   import { describe, it } from 'node:test';
   import assert from 'node:assert/strict';
   import { feature } from './module.js';

   describe('module', () => {
     it('handles the basic case', () => {
       assert.equal(feature(inputData), expectedOutput);
     });

     it('handles the edge case', () => {
       // ...
     });
   });
   ```

3. **Implement the module** to pass tests
4. **Run coverage check** and verify new code is exercised

### For New Functions in Existing Modules

1. **Add a test case** to the relevant `*.test.js` file
2. **Verify the test fails** (red), filtering to just that test by name
3. **Implement the function** to pass the test
4. **Verify the test passes** (green)
5. **Check coverage** includes the new code

### Code Patterns to Test

Make sure you test:

- ✅ **Happy path**: normal, expected usage
  ```js
  it('formats a valid price', () => {
    assert.equal(formatPrice(1999, 'USD'), '$19.99');
  });
  ```

- ✅ **Edge cases**: boundary conditions
  ```js
  it('renders an empty list message', () => {
    assert.equal(renderList([]).textContent, 'No items yet');
  });
  ```

- ✅ **Error handling**: invalid inputs
  ```js
  it('rejects a non-numeric amount', () => {
    assert.throws(() => formatPrice('abc', 'USD'), TypeError);
  });
  ```

- ✅ **Untrusted content**: markup-shaped input renders as text
  ```js
  it('does not interpret HTML in a user name', () => {
    const el = renderGreeting('<img src=x onerror=alert(1)>');
    assert.equal(el.querySelector('img'), null);
  });
  ```

## When Coverage Drops

### Step 1: Identify Coverage Gaps

Run the coverage command, then open `coverage/index.html` and look for red
lines (uncovered code).

### Step 2: Three Options

**Option A: Add Tests** (Preferred)
```js
it('covers the missing branch', () => {
  // Test the uncovered line/branch
});
```

**Option B: Exclude with an ignore hint** (Justified Cases)
```js
/* c8 ignore next 3 */
if (!('IntersectionObserver' in window)) {
  loadAllImagesEagerly(); // legacy-browser fallback; verified manually
}
```

**Option C: Discuss with Team** (If Threshold Too High)
- Consensus needed to lower the threshold below 85%
- Document the rationale
- Update the runner's configured minimum

### Step 3: Re-verify

Re-run the coverage command - it should show ≥ 85% and PASS.

## Troubleshooting

### "Coverage failed: 83% < 85%"

1. Check what's uncovered in the runner's summary, then open the HTML report.
2. Add tests or ignore hints.
3. Re-run until ≥ 85%.

### "Some files show 0% coverage"

1. Confirm a test actually imports the module - a script loaded only by an
   HTML page and never imported by a test shows 0%. Move its logic into an
   importable ES module.
2. Check the runner's coverage `include`/`exclude` globs didn't filter it out.
3. Code exercised only by Playwright runs in the browser, not in the unit
   runner, so it is not counted unless browser coverage collection is set up.

### "HTML report not generated"

1. Vitest needs the coverage provider installed (`@vitest/coverage-v8`).
2. `node --test` prints a text summary only; use `c8` or `--test-reporter=lcov`
   to produce a file you can render.
3. Check the reporter list in the runner config includes `html`.

## Summary

| Action               | Command                                         | Expected Result              |
|----------------------|-------------------------------------------------|------------------------------|
| Run all tests        | `npm test`                                      | All pass                     |
| Run with coverage    | `npx vitest run --coverage` (or equivalent)     | Pass + coverage summary      |
| View coverage        | Open `coverage/index.html`                      | Colored per-file view        |
| Run one test file    | `npx vitest run path/to/file.test.js`           | Test passes                  |
| Run browser tests    | `npx playwright test`                           | All journeys pass            |
| Find uncovered lines | Look for **red** in HTML                        | Know what to test next       |

---

**Remember**: Coverage ≥ 85% is required. Every PR must pass this check.
