"""The RadarCat integration.

Exposes the Meteocat radar animation over Catalonia as a single ``image``
entity (docs/03-feature-spec.md §2). Each config entry owns one
``RadarcatCoordinator`` that lives on ``entry.runtime_data``
(docs/04-architecture.md §1/§6): no ``hass.data`` dict, because this is a
single-config-entry service integration and ``runtime_data`` is the typed
handle every platform reads.

No options-update listener: v0.1.0 has no options flow, unlike
``../ha-cecat``'s scan-interval option (docs/03-feature-spec.md §7).
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import RadarcatCoordinator

# v0.1.0 has exactly one entity: image (docs/03-feature-spec.md §2).
PLATFORMS: tuple[Platform, ...] = (Platform.IMAGE,)

# The coordinator a config entry carries on its `runtime_data`. Typing the
# entry this way gives every platform `entry.runtime_data` already typed as
# the coordinator, with no cast and no `hass.data` lookup.
RadarcatConfigEntry = ConfigEntry[RadarcatCoordinator]

__all__ = [
    "PLATFORMS",
    "RadarcatConfigEntry",
    "async_setup_entry",
    "async_unload_entry",
]


async def async_setup_entry(hass: HomeAssistant, entry: RadarcatConfigEntry) -> bool:
    """Set up radarcat from a config entry.

    Arms the coordinator with a first refresh before forwarding to
    ``PLATFORMS``, so the image entity's first state already has real data
    instead of loading empty and waiting for the next poll.
    """
    coord = RadarcatCoordinator(hass, entry)
    entry.runtime_data = coord
    await coord.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RadarcatConfigEntry) -> bool:
    """Unload a radarcat config entry and stop its coordinator."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.async_shutdown()
    return unload_ok
