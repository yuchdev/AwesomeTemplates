# {{PROJECT_NAME}} Frontend Style Guide

Referenced by `frontend-expert` and `testing-expert` (`.claude/agents/`). This is a
starting skeleton, not a finished standard - fill in the project-specific
rules below before relying on it.

## Contents

- **HTML** - semantic-element expectations, the required document head
  (`<!doctype html>`, `lang`, `charset`, viewport), and the validator the project
  uses (e.g. `html-validate` or the W3C Nu checker).
- **CSS** - naming scheme (BEM, utility-first, or scoped), the design-token custom
  properties, the breakpoint scale, and the linter (e.g. `stylelint`).
- **JavaScript** - ECMAScript target, module format (native ES modules vs. a
  bundler), JSDoc expectations for exported functions, and the linter/formatter
  (e.g. `eslint` + `prettier`).
- **Accessibility** - the conformance target (e.g. WCAG 2.2 AA), keyboard-navigation
  and focus-visibility rules, colour-contrast minimums, and the automated checker
  (e.g. axe-core via Playwright).
- **Browser support** - the supported browser matrix (a Browserslist query or an
  explicit list) and the policy for features outside it (progressive enhancement
  vs. polyfill).
- **Performance budgets** - page-weight, image, and Core Web Vitals targets
  (LCP, CLS, INP) and what measures them (Lighthouse CI or similar).
- **Testing** - the test classification scheme `testing-expert` uses when it
  reports coverage/risk deltas (unit vs. mock vs. integration vs. e2e), and which
  runners the project uses (e.g. `node --test` or Vitest for logic, Playwright for
  browser flows).

## Project-specific overrides

Add this project's mandatory rules here: concrete, enforced-by-a-hook-or-CI-gate
rules, not general advice. Each entry should name what enforces it (an npm script,
a lint rule, a CI gate, a review checklist item) so the rule is auditable rather
than aspirational.
