"""Diagnostics export for the radarcat integration.

No user location or other PII exists anywhere in v0.1.0
(docs/04-architecture.md §8): the radar covers the whole of Catalonia and
the config flow takes zero fields, so unlike the sibling repos' `TO_REDACT`
set there is nothing to redact here - documented explicitly, the same way
they document an `exempt` quality-scale rule.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import RadarcatCoordinator

__all__ = ["async_get_config_entry_diagnostics"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return the diagnostic snapshot for one config entry.

    Reads only what the coordinator already holds in memory (docs/04-
    architecture.md §8) - downloading a diagnostic never triggers a fetch.
    """
    coordinator: RadarcatCoordinator = entry.runtime_data
    data = coordinator.data

    return {
        "frame_count": data.frame_count if data is not None else None,
        "latest_timestamp": (
            data.latest_timestamp.isoformat() if data is not None else None
        ),
        "last_update_success": coordinator.last_update_success,
        "available": coordinator.available,
        "consecutive_failures": coordinator.consecutive_failures,
        "last_error": coordinator.last_error,
    }
