"""The radar animation image entity.

Platform ``image`` (``ImageEntity``), not ``camera`` - see the ADR at
docs/04-architecture.md §3 for why: ``ImageView.handle`` writes
``async_image()``'s bytes straight to the HTTP response body with no
re-encoding, and the frontend paints a plain ``<img>`` that animates the WEBP
itself, no polling loop involved.

``ImageEntity.__init__`` (``homeassistant/components/image/__init__.py``)
takes ``hass`` directly and sets up ``self.access_tokens`` (read by
``entity_picture``/the ``/api/image_proxy`` view) and an httpx client for the
``image_url``/``image()`` fallback paths this entity never uses. Read live:
``CoordinatorEntity``'s own ``__init__`` chain
(``CoordinatorEntity -> BaseCoordinatorEntity``) does **not** call
``super().__init__()`` - ``BaseCoordinatorEntity.__init__`` just assigns
``self.coordinator``/``self.coordinator_context`` directly - so in the MRO of
``RadarcatImage(RadarcatEntity, ImageEntity)`` nothing reaches
``ImageEntity.__init__`` automatically. It is called explicitly below, using
``coordinator.hass`` (set by ``DataUpdateCoordinator.__init__``), or
``self.access_tokens`` would not exist and the image proxy view would raise.
"""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import IMAGE_CONTENT_TYPE
from .coordinator import RadarcatCoordinator
from .entity import RadarcatEntity

__all__ = ["RadarcatImage"]

_DESCRIPTION = EntityDescription(key="radar")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the radar image entity for this config entry.

    The coordinator lives on ``entry.runtime_data`` (the typed
    ``RadarcatConfigEntry`` that ``__init__.py``, T3, sets up) - read via the
    generic ``ConfigEntry`` here rather than importing that type, so this
    module has no import-time dependency on a sibling unit built in parallel.
    """
    coordinator: RadarcatCoordinator = entry.runtime_data
    async_add_entities([RadarcatImage(coordinator, _DESCRIPTION)])


class RadarcatImage(RadarcatEntity, ImageEntity):
    """The last-10-frames radar animation as a single animated WEBP."""

    _attr_content_type = IMAGE_CONTENT_TYPE
    _attr_translation_key = "radar"

    def __init__(
        self, coordinator: RadarcatCoordinator, description: EntityDescription
    ) -> None:
        """Wire up both parent branches (see module docstring for why).

        ``__init__.py`` (T3) runs ``async_config_entry_first_refresh()``
        before forwarding to platforms, so ``coordinator.data`` can already
        be a real, fully-composed ``RadarcatData`` by the time this runs.
        ``BaseCoordinatorEntity.async_added_to_hass`` only registers the
        listener (read live: ``homeassistant/helpers/update_coordinator.py``,
        it never calls ``_handle_coordinator_update()`` to sync initial
        state) - without seeding here, ``image_last_updated`` would stay
        unset and the entity would read "unknown" until the *next* poll,
        contradicting the ADR's "after every successful reconstruction"
        (docs/04-architecture.md §3).
        """
        super().__init__(coordinator, description)
        ImageEntity.__init__(self, coordinator.hass)
        self._last_frame_timestamp: datetime | None = None
        self._sync_image_last_updated()

    async def async_image(self) -> bytes | None:
        """Return the current animated WEBP bytes, or None before the first refresh.

        Per the ADR (docs/04-architecture.md §3): this method must never bump
        ``image_last_updated`` itself - only ``_sync_image_last_updated``
        does that, driven by the coordinator's own update cycle (or the cold
        start seeded from ``__init__``).
        """
        data = self.coordinator.data
        return data.content if data is not None else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Bump ``image_last_updated`` only when the frame set actually advanced.

        ``BaseCoordinatorEntity``'s default override just calls
        ``async_write_ha_state()``. This adds the cache-busting bump the
        frontend relies on (``computeImageUrl`` appends
        ``&state=<image_last_updated>``).
        """
        self._sync_image_last_updated()
        super()._handle_coordinator_update()

    def _sync_image_last_updated(self) -> None:
        """Seed/bump ``image_last_updated`` whenever ``latest_timestamp`` advanced.

        Shared by ``__init__`` (cold start) and ``_handle_coordinator_update``
        (steady state) - gated on ``latest_timestamp`` so a coordinator poll
        that found no new frame (docs/03-feature-spec.md §4, "dataUltimaImatge
        NO canvia") does not force every card to refetch identical bytes.
        """
        data = self.coordinator.data
        if data is not None and data.latest_timestamp != self._last_frame_timestamp:
            self._last_frame_timestamp = data.latest_timestamp
            self._attr_image_last_updated = dt_util.utcnow()
