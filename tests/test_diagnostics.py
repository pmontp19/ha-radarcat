"""Tests for the radarcat diagnostics export.

``coordinator.py`` (T3) is being built in parallel and may not exist yet, so
this exercises ``async_get_config_entry_diagnostics`` against a minimal fake
coordinator/entry matching the public surface the BINDING CONTRACT
(``docs/04-architecture.md`` §6/§8) promises: ``.data``
(``RadarcatData | None``), ``.available``, ``.last_update_success`` (standard
``DataUpdateCoordinator``), ``.consecutive_failures``/``.last_error`` (the
resilience bookkeeping §8 explicitly calls out), and ``entry.runtime_data``
pointing at it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from custom_components.radarcat.diagnostics import async_get_config_entry_diagnostics
from homeassistant.core import HomeAssistant


@dataclass
class _FakeRadarcatData:
    """Shape-compatible stand-in for coordinator.RadarcatData."""

    content: bytes
    latest_timestamp: datetime
    frame_count: int


class _FakeCoordinator:
    """Minimal double exposing only what diagnostics.py reads."""

    def __init__(
        self,
        data: _FakeRadarcatData | None,
        *,
        last_update_success: bool,
        available: bool,
        consecutive_failures: int = 0,
        last_error: str | None = None,
    ) -> None:
        self.data = data
        self.last_update_success = last_update_success
        self.available = available
        self.consecutive_failures = consecutive_failures
        self.last_error = last_error


class _FakeEntry:
    """Stand-in for the typed RadarcatConfigEntry - only runtime_data matters."""

    def __init__(self, runtime_data: _FakeCoordinator) -> None:
        self.runtime_data = runtime_data


async def test_diagnostics_reflects_healthy_coordinator(hass: HomeAssistant) -> None:
    """With data present, the export surfaces the frame set and its timestamp."""
    data = _FakeRadarcatData(
        content=b"webp-bytes",
        latest_timestamp=datetime(2026, 8, 17, 11, 54, tzinfo=UTC),
        frame_count=10,
    )
    entry = _FakeEntry(_FakeCoordinator(data, last_update_success=True, available=True))

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics == {
        "frame_count": 10,
        "latest_timestamp": "2026-08-17T11:54:00+00:00",
        "last_update_success": True,
        "available": True,
        "consecutive_failures": 0,
        "last_error": None,
    }


async def test_diagnostics_before_first_successful_refresh(
    hass: HomeAssistant,
) -> None:
    """``coordinator.data`` is None only before the first successful refresh."""
    entry = _FakeEntry(
        _FakeCoordinator(None, last_update_success=False, available=False)
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics == {
        "frame_count": None,
        "latest_timestamp": None,
        "last_update_success": False,
        "available": False,
        "consecutive_failures": 0,
        "last_error": None,
    }


async def test_diagnostics_surfaces_consecutive_failures(hass: HomeAssistant) -> None:
    """A run of failed polls surfaces its count (docs/04-architecture.md §8)."""
    entry = _FakeEntry(
        _FakeCoordinator(
            None,
            last_update_success=False,
            available=False,
            consecutive_failures=3,
            last_error="Could not reach the Meteocat metadata endpoint",
        )
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["consecutive_failures"] == 3
    assert diagnostics["last_error"] == "Could not reach the Meteocat metadata endpoint"


async def test_diagnostics_last_error_survives_a_later_success(
    hass: HomeAssistant,
) -> None:
    """``last_error`` is history, not state (coordinator.py's own docstring):

    it must still show up in diagnostics even once the coordinator has
    recovered and ``consecutive_failures`` has been reset to 0.
    """
    data = _FakeRadarcatData(
        content=b"webp-bytes",
        latest_timestamp=datetime(2026, 8, 17, 11, 54, tzinfo=UTC),
        frame_count=10,
    )
    entry = _FakeEntry(
        _FakeCoordinator(
            data,
            last_update_success=True,
            available=True,
            consecutive_failures=0,
            last_error="Could not reach the Meteocat metadata endpoint",
        )
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["last_update_success"] is True
    assert diagnostics["consecutive_failures"] == 0
    assert diagnostics["last_error"] == "Could not reach the Meteocat metadata endpoint"


async def test_diagnostics_never_triggers_a_fetch(hass: HomeAssistant) -> None:
    """The export reads only what the coordinator already holds in memory.

    A coordinator double with no fetch method at all still produces a
    diagnostic - proof that nothing in this path calls back into the network.
    """
    data = _FakeRadarcatData(
        content=b"webp-bytes",
        latest_timestamp=datetime(2026, 8, 17, 11, 54, tzinfo=UTC),
        frame_count=1,
    )
    entry = _FakeEntry(_FakeCoordinator(data, last_update_success=True, available=True))

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["frame_count"] == 1
