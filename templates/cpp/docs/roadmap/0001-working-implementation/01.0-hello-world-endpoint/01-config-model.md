# 01 - Config model

**Parent story:** [README.md](README.md)
**Status:** ⬜ Not started

## Objective

This task is a stub to rename and implement a real one.
All subsequent paragraphs also should be rewritten into a real task.

## Files

- `include/{{PROJECT_PACKAGE}}/config/health_config.h` - new `HealthConfig` struct.
- `src/config/health_config.cpp` - default value + loading logic.
- `tests/unit/config/health_config_test.cpp` - default value + override test.

## Functions and Classes

- `HealthConfig` struct with a `std::string service_name` field, defaulting to `"{{PROJECT_PACKAGE}}"`.

## Constraints

- None

## Success criteria

- [ ] Implement `HealthConfig` struct with a `std::string service_name` field, defaulting to `"{{PROJECT_PACKAGE}}"`.
- [ ] Implement loading logic for `HealthConfig` struct.
- [ ] Implement the default value for `HealthConfig` struct.
- [ ] Implement unit tests for `HealthConfig` struct.
