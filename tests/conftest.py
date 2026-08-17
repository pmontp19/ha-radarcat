"""Shared pytest fixtures and helpers for radarcat tests."""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from aioresponses import aioresponses
from custom_components.radarcat.const import DOMAIN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytest_plugins = "pytest_homeassistant_custom_component"


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> bytes:
    """Load a raw fixture from ``tests/fixtures`` as bytes.

    ``name`` is the file name including its extension (``.png``/``.json``).
    Real fixtures are literal copies of ``docs/captures/`` (observed
    evidence); synthetic ones carry the ``_SYNTHETIC`` suffix and a
    ``_comment`` key declaring so (``AGENTS.md`` evidence discipline).
    """
    return (FIXTURES_DIR / name).read_bytes()


def load_json_fixture(name: str) -> dict:
    """Load a JSON fixture from ``tests/fixtures`` as a parsed dict."""
    if not name.endswith(".json"):
        name = f"{name}.json"
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


class FakeClock:
    """A controllable stand-in for ``homeassistant.util.dt.utcnow``.

    No business logic in this integration depends on wall-clock time yet
    (unlike ``cecat``'s stale-data windows), but the coordinator (T2/T3) will
    need one for its "same timestamp, skip rebuild" cadence, so the fixture
    is kept available here rather than added ad hoc later.

    Patch it over the ``utcnow`` reference of the module under test, e.g.::

        monkeypatch.setattr("custom_components.radarcat.coordinator.utcnow", clock)
    """

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    """A ``FakeClock`` starting at a fixed, memorable instant.

    2026-08-17 11:42 UTC is the capture instant of
    ``radar_tile_z7_x65_y80_no_echo.png`` (see ``tests/fixtures/README.md``),
    so a test using that fixture starts in the same moment the evidence was
    observed.
    """
    return FakeClock(datetime(2026, 8, 17, 11, 42, tzinfo=UTC))


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let the HA flow manager load the radarcat custom component."""


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a radarcat MockConfigEntry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="RadarCat",
        data={},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_http() -> Generator[aioresponses]:
    """An ``aioresponses`` context covering every request made in a test."""
    with aioresponses() as mocked:
        yield mocked
