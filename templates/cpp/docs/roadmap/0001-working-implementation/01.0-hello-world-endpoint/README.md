# Story 01.0 - Hello World Endpoint

**Parent milestone:** [plan.md](../plan.md)
**Status:** ⬜ Not started

## Scope

This story is a stub to rename and implement a real one.
All subsequent paragraphs also should be rewritten into a real story.


## Tasks

| #  | Document                                 | Status         | Blocks |
|----|------------------------------------------|----------------|--------|
| 01 | [Config model](01-config-model.md)       | ⬜ Not started | 02     |
| 02 | [Health endpoint](02-health-endpoint.md) | ⬜ Not started | 03     |
| 03 | [Tests](03-tests.md)                     | ⬜ Not started | -      |

## Key constraints

- No new third-party dependencies.
- Follows this project's existing config-loading convention (see
  `@docs/dev/cpp_coding_standard.md`).

## Files or directories created or modified by this story

- `include/{{PROJECT_PACKAGE}}/config/health_config.h` - new `HealthConfig` struct.
- `src/config/health_config.cpp` - default value + loading logic.
- `tests/unit/config/health_config_test.cpp` - default value + override test.
- `src/api/health_handler.cpp` / `include/{{PROJECT_PACKAGE}}/api/health_handler.h` - new route handler.
- Wire the route into the app's existing router setup.
- `tests/integration/health_endpoint_test.cpp` - new integration test.