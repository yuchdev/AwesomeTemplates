"""Live check: every model ID this repo recommends or pins is actually served by its vendor.

Opt-in (`uv run pytest --live-models`), because it needs network and API keys and must never run as
part of the offline default suite. Complements the offline allowlist test in
`test_integration_real_repo.py`: that one proves pins are *recommended*; this one proves the
recommendations (and pins) *exist* - the "typo or retired ID" fault mode. A vendor with no key is
skipped, or failed under `--live-models-strict` (use that as a release gate).
"""

from __future__ import annotations

import os

import pytest

from awesome_templates import model_catalog, model_policy
from awesome_templates.model_policy import ModelPolicy, PolicyMode, scan_all
from awesome_templates.workspace import Workspace
from tests.conftest import REAL_REPO_ROOT, REAL_TEMPLATES_ROOT

pytestmark = pytest.mark.live_models

VENDORS = sorted(model_catalog.FETCHERS)


@pytest.mark.parametrize("vendor", VENDORS)
def test_vendor_serves_every_recommended_and_pinned_model(vendor: str, request: pytest.FixtureRequest):
    policy = model_policy.load_policy(REAL_REPO_ROOT / "pyproject.toml")
    pins = sorted({f.model for f in scan_all(Workspace(REAL_TEMPLATES_ROOT), ModelPolicy(PolicyMode.warn, frozenset()))})
    to_check = model_catalog.ids_to_verify(policy, pins).get(vendor, set())
    if not to_check:
        pytest.skip(f"nothing recommended or pinned for {vendor}")

    env_name = policy.key_envs.get(vendor, "")
    if not os.environ.get(env_name):
        message = f"{vendor}: env var {env_name or '(none configured)'} is not set"
        if request.config.getoption("--live-models-strict"):
            pytest.fail(message)
        pytest.skip(message)

    served = model_catalog.fetch_supported(vendor, os.environ[env_name])
    missing = sorted(to_check - served)
    assert not missing, (
        f"{vendor} does not serve {missing}; fix pyproject.toml's model_policy.recommended or the agent pin. "
        f"Sample of served IDs: {sorted(served)[:10]}"
    )
