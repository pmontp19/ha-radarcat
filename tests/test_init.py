"""Tests for radarcat's integration setup and unload (docs/04-architecture.md §1).

The coordinator's own cycle is exercised in ``test_coordinator.py``; this
module covers only the wiring ``async_setup_entry``/``async_unload_entry``
add on top: the coordinator lands on ``entry.runtime_data`` (never
``hass.data``), ``PLATFORMS`` forwards to ``(Platform.IMAGE,)``, and the
entry sets up and unloads cleanly end to end.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from aioresponses import aioresponses
from custom_components.radarcat import PLATFORMS, async_setup_entry, async_unload_entry
from custom_components.radarcat.const import (
    DOMAIN,
    FONS_TILES_BASE,
    METADATA_URL,
    RADAR_TILES_BASE,
)
from custom_components.radarcat.coordinator import RadarcatCoordinator
from homeassistant.config_entries import ConfigEntryState, Platform
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import load_fixture

T0 = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    """Build and register a radarcat MockConfigEntry."""
    entry = MockConfigEntry(domain=DOMAIN, title="RadarCat", data={})
    entry.add_to_hass(hass)
    return entry


def _mock_first_refresh(mock_http: aioresponses) -> None:
    """Everything one async_config_entry_first_refresh cycle needs."""
    mock_http.get(
        METADATA_URL,
        payload={
            "dataUltimaImatge": T0.strftime("%m/%d/%Y %H:%MZ"),
            "dataSistema": T0.strftime("%m/%d/%Y %H:%MZ"),
        },
    )
    mock_http.get(
        re.compile(rf"^{re.escape(FONS_TILES_BASE)}/.*"),
        body=load_fixture("base_tile_z8_x128_y160.png"),
        content_type="image/png",
        repeat=True,
    )
    mock_http.get(
        re.compile(rf"^{re.escape(RADAR_TILES_BASE)}/.*"),
        body=load_fixture("radar_tile_z7_x65_y80_no_echo.png"),
        content_type="image/png",
        repeat=True,
    )


def test_platforms_is_exactly_image() -> None:
    """v0.1.0 has exactly one entity, image (docs/03-feature-spec.md §2)."""
    assert PLATFORMS == (Platform.IMAGE,)


async def test_setup_entry_arms_coordinator_and_forwards_to_image(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """Setup does the first refresh, stores runtime_data, forwards to IMAGE.

    Runs under the entry's ``setup_lock``, the guarantee
    ``hass.config_entries.async_setup`` gives in production, because
    forwarding to a platform demands the lock (same pattern as
    ``../ha-cecat/tests/test_init.py``).
    """
    _mock_first_refresh(mock_http)
    entry = _entry(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    async with entry.setup_lock:
        assert await async_setup_entry(hass, entry) is True

    assert isinstance(entry.runtime_data, RadarcatCoordinator)
    assert entry.runtime_data.data is not None  # the first refresh really ran
    assert DOMAIN not in hass.data  # nothing on hass.data, only runtime_data
    assert len(hass.states.async_entity_ids("image")) == 1


async def test_unload_entry_unloads_platforms_and_shuts_down_coordinator(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A loaded entry unloads cleanly and returns True.

    Only the boolean result is asserted here (same as
    ``../ha-cecat/tests/test_init.py``'s analogous test): this direct-call
    path never runs the entry through HA's real state machine, so poking
    ``hass.states`` afterward would be asserting against this test's own
    shortcut rather than against ``async_unload_entry``.
    """
    _mock_first_refresh(mock_http)
    entry = _entry(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    async with entry.setup_lock:
        await async_setup_entry(hass, entry)
    # Direct-call path: pretend HA finished the state transition so the
    # unload really reaches async_unload_entry.
    entry.mock_state(hass, ConfigEntryState.LOADED)

    assert await async_unload_entry(hass, entry) is True
