# 01 - Config model

**Parent task:** [README.md](README.md)
**Status:** ⬜ Not started

## Requirements

- Add a `HealthConfig` struct with a `std::string service_name` field,
  defaulting to `"{{PROJECT_PACKAGE}}"`.
- Load it the same way other config sections are loaded in this project.

## Files

- `include/{{PROJECT_PACKAGE}}/config/health_config.h` - new `HealthConfig` struct.
- `src/config/health_config.cpp` - default value + loading logic.
- `tests/unit/config/health_config_test.cpp` - default value + override test.
