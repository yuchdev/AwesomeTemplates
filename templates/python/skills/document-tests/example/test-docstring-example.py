"""Reference specimen for /document-tests — the docstring format, one per class.

This is a *teaching example*, not a collected test (it lives under `.claude/`,
outside `tests/`, so pytest never runs it). Each function below shows two things
at once:

1. the structural signal `scripts/document_tests.py` keys on to classify it, and
2. the exact docstring the codemod emits and that
   [../references/classification-guide.md](../references/classification-guide.md)
   describes.

Docstring contract (enforced by the codemod's title regex
``^\\[(Unit|Mock|Integration|E2E)\\] .+: verifies .+\\.$``):

    [<Class>] <short name>: verifies <one sentence ending in a period>.

    Scenario: <what is set up and exercised>
    Boundaries: <what is real vs mocked; scope of the test>
    On-failure-first-check: <where to look first when this fails>

Note on classification: the codemod decides by **directory first, then body
markers**. This file is in an unrecognised directory, so the codemod would tag
each case `ambiguous` and fall back to the body signal — exactly the situation
where a human uses the semantic definitions in the classification guide. The
body of each function is written so the *intended* class is unambiguous.
"""

from __future__ import annotations

from unittest import mock

import pytest

from {{PROJECT_PACKAGE}}.orders.pricing import DiscountTier, resolve_carrier


# --------------------------------------------------------------------------- #
# [Unit] — pure logic, no mocks, no I/O. Signal: no mock/runner markers.
# --------------------------------------------------------------------------- #
def test_discount_tier_below_threshold_is_none() -> None:
    """[Unit] discount tier low: verifies a subtotal under 50.00 maps to NONE.

    Scenario: Call DiscountTier.from_subtotal(49.99) with a plain float, no mocks or I/O.
    Boundaries: Pure function; exercises only the <50.00 branch of the tier ladder.
    On-failure-first-check: If this fails, inspect the 50.00 / 100.00 cutoffs in
        DiscountTier.from_subtotal.
    """
    assert DiscountTier.from_subtotal(49.99) is DiscountTier.NONE


# --------------------------------------------------------------------------- #
# [Mock] — unit-scoped, but a collaborator is patched. Signal: mock./monkeypatch.
# --------------------------------------------------------------------------- #
def test_carrier_resolution_uses_lookup_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """[Mock] carrier resolution: verifies resolve_carrier delegates to its lookup table.

    Scenario: monkeypatch the module's _CARRIER_MAP to a controlled entry, then resolve a zone.
    Boundaries: Only the one function under test runs for real; the table it reads is a mock.
    On-failure-first-check: If this fails, check that resolve_carrier reads _CARRIER_MAP
        rather than hard-coding the mapping.
    """
    monkeypatch.setattr(
        "{{PROJECT_PACKAGE}}.orders.pricing._CARRIER_MAP",
        {"EU-WEST": "eu-express"},
    )
    assert resolve_carrier("EU-WEST") == "eu-express"
    # An unmapped zone still falls back to "standard" through the patched table.
    assert resolve_carrier("ZZ-UNKNOWN") == "standard"


# --------------------------------------------------------------------------- #
# [Integration] — two+ real components wired together, external edge mocked.
# Signal: no e2e runner, real collaborators. (Body is an illustrative sketch.)
# --------------------------------------------------------------------------- #
@pytest.mark.skip(reason="illustrative sketch — shows the [Integration] shape, not a live test")
def test_order_store_round_trip(tmp_path) -> None:
    """[Integration] store round-trip: verifies a saved order reloads by order_id.

    Scenario: Persist an order to a real filesystem store rooted at tmp_path,
        then load it back through the store's find_by_id.
    Boundaries: Real store + real serialisation wired together; only the on-disk
        location is a test fixture (tmp_path). No payment backend, no network.
    On-failure-first-check: If this fails, compare the serialised order_id written
        to disk against the value find_by_id queries with.
    """
    # from {{PROJECT_PACKAGE}}.orders.store.filesystem import FilesystemOrderStore
    # store = FilesystemOrderStore(root=tmp_path)
    # order = make_order(order_id="abc123")
    # await store.save_order(order)
    # assert (await store.find_by_id("abc123")).order_id == "abc123"
    ...


# --------------------------------------------------------------------------- #
# [E2E] — a full user entry point driven end to end. Signal: CliRunner/TestClient.
# (Body is an illustrative sketch of the runner shape.)
# --------------------------------------------------------------------------- #
@pytest.mark.skip(reason="illustrative sketch — shows the [E2E] shape, not a live test")
def test_process_order_cli_reports_status() -> None:
    """[E2E] process-order CLI: verifies `orders process` prints the resolved order status.

    Scenario: Invoke the Typer app through CliRunner with a fixture order and mocked
        payment backend, then assert on the rendered CLI output.
    Boundaries: The whole CLI entry point runs (parsing → processing → view); only
        the external payment backend is mocked at the process edge.
    On-failure-first-check: If this fails, run the same command manually and compare
        the order_status line in the output to the fixture's expected status.
    """
    # from typer.testing import CliRunner
    # from {{PROJECT_PACKAGE}}.cli.commands import app
    # with mock.patch("{{PROJECT_PACKAGE}}.backends.payment.factory.build_payment_backend", return_value=FakePayment()):
    #     result = CliRunner().invoke(app, ["process", "--order", "fixtures/order.json"])
    # assert result.exit_code == 0
    # assert "confirmed" in result.stdout
    _ = mock  # referenced so the [E2E]/[Mock] body markers are visible to the codemod
