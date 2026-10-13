# 02 - Site header

**Parent story:** [README.md](README.md)
**Status:** ⬜ Not started
**Depends on:** [01-page-skeleton.md](01-page-skeleton.md)

## Objective

This task is a stub to rename and implement a real one.
All subsequent paragraphs also should be rewritten into a real task.

## Files

- `index.html` - add a `<nav>` inside the `<header>` with a menu toggle `<button>`.
- `js/site-header.js` - ES module wiring the toggle.

## Elements and Functions

- `toggleMenu(expanded)` - pure function returning the next `aria-expanded` state.
- `initSiteHeader(root)` - attaches the click handler to the toggle button.

## Constraints

- The navigation links remain reachable without JavaScript.

## Success criteria

- [ ] The toggle is a real `<button>` whose `aria-expanded` reflects the menu state.
- [ ] The menu opens and closes with keyboard (Enter/Space) as well as pointer input.
- [ ] Focus is visible on every navigation link and on the toggle.
