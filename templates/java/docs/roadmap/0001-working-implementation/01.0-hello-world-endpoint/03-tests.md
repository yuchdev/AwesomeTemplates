# 03 - Tests

**Parent task:** [README.md](README.md)
**Status:** ⬜ Not started
**Depends on:** [02-health-endpoint.md](02-health-endpoint.md)

## Requirements

- Integration test: `GET /health` returns `200` and the expected JSON body.
- Unit test: `HealthConfig` default and override, from subtask 01.
- Both tests pass under this project's standard test command.

## Files

- `tests/integration/test_health_endpoint.py` - new integration test.
