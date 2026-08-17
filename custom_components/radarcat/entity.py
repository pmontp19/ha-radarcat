"""Shared entity base for every radarcat platform entity.

One place for the three things all entities share (docs/04-architecture.md
§7): the single service ``DeviceInfo``, the licence-mandated ``ATTRIBUTION``
(docs/03-feature-spec.md §6) and the stale-data availability window the
coordinator (T3) already computes. There is only one platform entity in
v0.1.0 (``RadarcatImage``), but the split mirrors the sibling repos'
``entity.py`` pattern (docs/05-implementation-plan.md T4) so a v0.2.0 sensor
can subclass this without duplicating any of it.

``available`` delegates to ``RadarcatCoordinator.available`` on purpose, the
same reasoning as ``CecatEntity``
(``../ha-cecat/custom_components/cecat/entity.py``): ``CoordinatorEntity``'s
own default only tracks ``last_update_success``, which can never distinguish
a frozen-but-stale source from a healthy one that just had a transient
glitch. Only data older than the coordinator's own staleness window
(docs/04-architecture.md §6) takes the entity to ``unavailable``.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import RadarcatCoordinator

__all__ = ["RadarcatEntity"]


class RadarcatEntity(CoordinatorEntity[RadarcatCoordinator]):
    """Base class for radarcat entities: device, attribution, availability."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self, coordinator: RadarcatCoordinator, description: EntityDescription
    ) -> None:
        """Attach the coordinator, the description key and the shared device.

        The ``entry_id`` prefix on ``unique_id`` costs nothing and survives a
        future change of scope even though the integration is
        ``single_config_entry`` (only one entry will ever exist in v0.1.0).
        """
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            name="RadarCat",
            manufacturer=ATTRIBUTION,
        )

    @property
    def available(self) -> bool:
        """Whether the coordinator's data is fresh enough to present.

        Delegates to the coordinator's own staleness check
        (docs/04-architecture.md §6) rather than ``CoordinatorEntity``'s
        default ``last_update_success`` - a transient network glitch keeps the
        last animation visible, and only a genuinely stale source takes the
        entity down.
        """
        return self.coordinator.available
