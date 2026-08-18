"""The radar image entities: the animated WEBP and the latest-frame PNG.

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
``_RadarcatImageBase(RadarcatEntity, ImageEntity)`` nothing reaches
``ImageEntity.__init__`` automatically. It is called explicitly below, using
``coordinator.hass`` (set by ``DataUpdateCoordinator.__init__``), or
``self.access_tokens`` would not exist and the image proxy view would raise.

Two entities share the ``image_last_updated`` sync logic and the pinned-
entity_id fix (docs/04-architecture.md §7): ``RadarcatImage`` (the 10-frame
animation) and ``RadarcatStaticImage`` (only the newest frame, v0.1.1). Both
are always present (docs/03-feature-spec.md §2, no config field chooses one
over the other), so both fixes live once in ``_RadarcatImageBase`` rather
than being duplicated - or, worse, applied to only one of the two - per
entity.
"""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, IMAGE_CONTENT_TYPE, STATIC_IMAGE_CONTENT_TYPE
from .coordinator import RadarcatCoordinator
from .entity import RadarcatEntity

__all__ = ["RadarcatImage", "RadarcatStaticImage"]

_DESCRIPTION = EntityDescription(key="radar")
_STATIC_DESCRIPTION = EntityDescription(key="radar_actual")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up both radar image entities for this config entry.

    The coordinator lives on ``entry.runtime_data`` (the typed
    ``RadarcatConfigEntry`` that ``__init__.py``, T3, sets up) - read via the
    generic ``ConfigEntry`` here rather than importing that type, so this
    module has no import-time dependency on a sibling unit built in parallel.
    Both entities are added in the same call (docs/04-architecture.md §7):
    neither is optional, there is no config field selecting one over the
    other (docs/03-feature-spec.md §2).
    """
    coordinator: RadarcatCoordinator = entry.runtime_data
    async_add_entities(
        [
            RadarcatImage(coordinator, _DESCRIPTION),
            RadarcatStaticImage(coordinator, _STATIC_DESCRIPTION),
        ]
    )


class _RadarcatImageBase(RadarcatEntity, ImageEntity):
    """Shared ``image_last_updated`` seeding/sync for both image entities.

    Both ``RadarcatImage`` and ``RadarcatStaticImage`` publish a new
    ``latest_timestamp`` on the exact same coordinator cycle, so the cold
    start seed and the steady-state bump are identical for both - only what
    ``async_image()`` returns differs per subclass.
    """

    def __init__(
        self, coordinator: RadarcatCoordinator, description: EntityDescription
    ) -> None:
        """Wire up both parent branches, then pin a deterministic entity_id.

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

        ``self.entity_id`` is pinned explicitly for both subclasses here,
        not left to derive from the translated name: with
        ``has_entity_name`` set, HA slugifies "<device name> <translated
        entity name>" into the object id (read live:
        ``homeassistant/helpers/entity_platform.py``,
        ``_async_derive_object_ids``/``suggested_object_id`` - confirmed by
        running an unpinned entity through a real
        ``hass.config_entries.async_setup()``). For ``RadarcatImage`` this
        currently resolves to the right id only by coincidence, because
        ``entity.image.radar.name`` happens to be "Radar" in all three
        shipped languages ("RadarCat" + "Radar" -> ``radarcat_radar``); for
        ``RadarcatStaticImage`` the more natural English name ("Current
        radar") would resolve to ``image.radarcat_current_radar`` instead
        of the ``image.radarcat_radar_actual`` docs/03-feature-spec.md §2
        requires. Pinning both here (rather than only the one that would
        otherwise break) removes that same latent fragility from
        ``RadarcatImage`` too: a future translation edit must never be able
        to silently change either entity_id. ``_async_derive_object_ids``
        prefers ``entity.entity_id`` - set here, before this entity is ever
        added to a platform - over the translation-derived
        ``suggested_object_id``; setting ``entity_id`` explicitly is the
        documented way for an integration to pin it.
        """
        super().__init__(coordinator, description)
        ImageEntity.__init__(self, coordinator.hass)
        self.entity_id = f"image.{DOMAIN}_{description.key}"
        self._last_frame_timestamp: datetime | None = None
        self._sync_image_last_updated()

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


class RadarcatImage(_RadarcatImageBase):
    """The last-10-frames radar animation as a single animated WEBP."""

    _attr_content_type = IMAGE_CONTENT_TYPE
    _attr_translation_key = "radar"

    async def async_image(self) -> bytes | None:
        """Return the current animated WEBP bytes, or None before the first refresh.

        Per the ADR (docs/04-architecture.md §3): this method must never bump
        ``image_last_updated`` itself - only ``_sync_image_last_updated``
        does that, driven by the coordinator's own update cycle (or the cold
        start seeded from ``__init__``).
        """
        data = self.coordinator.data
        return data.content if data is not None else None


class RadarcatStaticImage(_RadarcatImageBase):
    """Only the most recent composited frame, as a static PNG (v0.1.1).

    Always present alongside ``RadarcatImage`` (docs/03-feature-spec.md §2):
    some uses (automations, low-bandwidth dashboards, cards that do not want
    motion) want only "how it looks right now", the same pattern AEMET's
    integration uses. Reuses the same frame the coordinator already composed
    (``RadarcatData.static_content``) - no separate fetch or compose.
    """

    _attr_content_type = STATIC_IMAGE_CONTENT_TYPE
    _attr_translation_key = "radar_actual"

    async def async_image(self) -> bytes | None:
        """Return the current static PNG bytes, or None before the first refresh.

        Same never-bump-here rule as ``RadarcatImage.async_image`` (docs/04-
        architecture.md §3): ``_sync_image_last_updated`` is the only place
        that touches ``image_last_updated``.
        """
        data = self.coordinator.data
        return data.static_content if data is not None else None
