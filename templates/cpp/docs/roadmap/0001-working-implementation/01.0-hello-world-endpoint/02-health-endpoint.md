# 02 - Health endpoint

**Parent story:** [README.md](README.md)
**Status:** ⬜ Not started
**Depends on:** [01-config-model.md](01-config-model.md)

## Objective

This task is a stub to rename and implement a real one.
All subsequent paragraphs also should be rewritten into a real task.

## Files

- `src/api/health_handler.cpp` / `include/{{PROJECT_PACKAGE}}/api/health_handler.h` - new route handler.
- Wire the route into the app's existing router setup.

## Functions and Classes

- `HealthConfig` struct with a `std::string service_name` field, defaulting to `"{{PROJECT_PACKAGE}}"`.

## Constraints

- None

## Success criteria

- [ ] Implement the `GET /health` route that returns `{"status": "ok", "service": <service_name>}` with a `200` status code.
- [ ] `service_name` comes from `HealthConfig` (task 01) - no hardcoded string.
