"""Tests for RadarcatEntity (entity.py) and RadarcatImage (image.py).

``coordinator.py`` (T3) is being built in parallel and may not exist yet, so
these use a minimal fake coordinator matching the public surface the
BINDING CONTRACT (``docs/04-architecture.md`` §6) promises: ``.hass``,
``.config_entry``, ``.data`` (``RadarcatData | None``), ``.available``.
Entity-base coverage (unique_id, DeviceInfo, availability delegation) is
folded in here rather than a separate ``test_entity.py`` - ``RadarcatImage``
is the only platform entity in v0.1.0, so there is nothing left for a
standalone file to isolate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from custom_components.radarcat.const import ATTRIBUTION, DOMAIN, IMAGE_CONTENT_TYPE
from custom_components.radarcat.image import RadarcatImage
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import EntityDescription
from pytest_homeassistant_custom_component.common import MockConfigEntry

_DESCRIPTION = EntityDescription(key="radar")


@dataclass
class _FakeRadarcatData:
    """Shape-compatible stand-in for coordinator.RadarcatData."""

    content: bytes
    latest_timestamp: datetime
    frame_count: int


class _FakeCoordinator:
    """Minimal double exposing only what entity.py/image.py read."""

    def __init__(self, hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.data: _FakeRadarcatData | None = None
        self.available = True


def _make_entity(hass: HomeAssistant) -> tuple[RadarcatImage, _FakeCoordinator]:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    coordinator = _FakeCoordinator(hass, entry)
    return RadarcatImage(coordinator, _DESCRIPTION), coordinator


# ---------------------------------------------------------------------------
# RadarcatEntity: device, attribution, unique_id, availability
# ---------------------------------------------------------------------------


def test_unique_id_is_entry_id_prefixed_by_key(hass: HomeAssistant) -> None:
    """unique_id = f"{entry_id}_{description.key}" (docs/04-architecture.md §7)."""
    entity, coordinator = _make_entity(hass)
    assert entity.unique_id == f"{coordinator.config_entry.entry_id}_radar"


def test_device_info_is_a_single_service_device(hass: HomeAssistant) -> None:
    """DeviceInfo names the shared 'RadarCat' service device (docs §7)."""
    entity, coordinator = _make_entity(hass)
    info = entity.device_info
    assert info["identifiers"] == {(DOMAIN, coordinator.config_entry.entry_id)}
    assert info["entry_type"] is DeviceEntryType.SERVICE
    assert info["name"] == "RadarCat"
    assert info["manufacturer"] == ATTRIBUTION


def test_attribution_is_the_const_value(hass: HomeAssistant) -> None:
    """_attr_attribution reuses const.ATTRIBUTION verbatim."""
    entity, _ = _make_entity(hass)
    assert entity.attribution == ATTRIBUTION


def test_available_delegates_to_coordinator(hass: HomeAssistant) -> None:
    """available reflects coordinator.available, not last_update_success."""
    entity, coordinator = _make_entity(hass)

    coordinator.available = True
    assert entity.available is True

    coordinator.available = False
    assert entity.available is False


# ---------------------------------------------------------------------------
# RadarcatImage.async_image
# ---------------------------------------------------------------------------


async def test_async_image_returns_content_when_data_present(
    hass: HomeAssistant,
) -> None:
    """async_image returns coordinator.data.content when data exists."""
    entity, coordinator = _make_entity(hass)
    coordinator.data = _FakeRadarcatData(
        content=b"webp-bytes",
        latest_timestamp=datetime(2026, 8, 17, 11, 42, tzinfo=UTC),
        frame_count=10,
    )

    assert await entity.async_image() == b"webp-bytes"


async def test_async_image_returns_none_before_first_refresh(
    hass: HomeAssistant,
) -> None:
    """async_image returns None while coordinator.data is still None."""
    entity, _ = _make_entity(hass)

    assert await entity.async_image() is None


def test_content_type_is_webp(hass: HomeAssistant) -> None:
    """_attr_content_type is IMAGE_CONTENT_TYPE ('image/webp'), never GIF (ADR §3)."""
    entity, _ = _make_entity(hass)
    assert entity.content_type == IMAGE_CONTENT_TYPE == "image/webp"


def test_translation_key_matches_the_landed_strings_json(hass: HomeAssistant) -> None:
    """_attr_translation_key = 'radar' matches entity.image.radar in strings.json."""
    entity, _ = _make_entity(hass)
    assert entity.translation_key == "radar"


# ---------------------------------------------------------------------------
# image_last_updated: bumped only from the coordinator listener, only when
# the frame set actually advanced (docs/04-architecture.md §3 - never inside
# async_image() itself).
# ---------------------------------------------------------------------------


def _frame(content: bytes, timestamp: datetime) -> _FakeRadarcatData:
    return _FakeRadarcatData(
        content=content, latest_timestamp=timestamp, frame_count=10
    )


def test_init_seeds_image_last_updated_when_data_already_populated(
    hass: HomeAssistant,
) -> None:
    """Cold start: seed image_last_updated immediately if data already exists.

    ``__init__.py`` (T3) runs ``async_config_entry_first_refresh()`` before
    forwarding to platforms, so ``coordinator.data`` can already be a real
    ``RadarcatData`` by the time ``RadarcatImage.__init__`` runs.
    ``BaseCoordinatorEntity.async_added_to_hass`` only registers the
    listener - it never calls ``_handle_coordinator_update()`` to sync
    initial state (read live: ``homeassistant/helpers/update_coordinator.py``)
    - so without this seeding the entity would read "unknown" until the
    *next* poll, even though ``async_image()`` already serves a real WEBP.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={})
    coordinator = _FakeCoordinator(hass, entry)
    coordinator.data = _frame(b"a", datetime(2026, 8, 17, 11, 42, tzinfo=UTC))

    entity = RadarcatImage(coordinator, _DESCRIPTION)

    assert entity.image_last_updated is not None


def test_init_leaves_image_last_updated_unset_before_first_refresh(
    hass: HomeAssistant,
) -> None:
    """No coordinator.data yet at construction -> image_last_updated stays None."""
    entity, _ = _make_entity(hass)
    assert entity.image_last_updated is None


def test_handle_coordinator_update_bumps_on_first_data(hass: HomeAssistant) -> None:
    """The first successful refresh bumps image_last_updated and writes state."""
    entity, coordinator = _make_entity(hass)
    assert entity.image_last_updated is None

    coordinator.data = _frame(b"a", datetime(2026, 8, 17, 11, 42, tzinfo=UTC))
    with patch.object(entity, "async_write_ha_state") as write_state:
        entity._handle_coordinator_update()

    assert entity.image_last_updated is not None
    write_state.assert_called_once()


def test_handle_coordinator_update_skips_bump_when_timestamp_unchanged(
    hass: HomeAssistant,
) -> None:
    """A coordinator poll with no new frame (§4 of 03-feature-spec.md) still
    calls async_write_ha_state (the CoordinatorEntity default), but must not
    move image_last_updated - the frontend would needlessly refetch identical
    bytes otherwise."""
    entity, coordinator = _make_entity(hass)
    same_timestamp = datetime(2026, 8, 17, 11, 42, tzinfo=UTC)
    coordinator.data = _frame(b"a", same_timestamp)
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()
    first_bump = entity.image_last_updated

    coordinator.data = _frame(b"a", same_timestamp)  # unchanged latest_timestamp
    with patch.object(entity, "async_write_ha_state") as write_state:
        entity._handle_coordinator_update()

    assert entity.image_last_updated == first_bump
    write_state.assert_called_once()


def test_handle_coordinator_update_bumps_again_on_new_timestamp(
    hass: HomeAssistant,
) -> None:
    """A genuinely new frame moves image_last_updated forward."""
    entity, coordinator = _make_entity(hass)
    ts1 = datetime(2026, 8, 17, 11, 42, tzinfo=UTC)
    coordinator.data = _frame(b"a", ts1)
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()
    first_bump = entity.image_last_updated

    ts2 = ts1 + timedelta(minutes=6)
    coordinator.data = _frame(b"b", ts2)
    with patch.object(entity, "async_write_ha_state") as write_state:
        entity._handle_coordinator_update()

    assert entity.image_last_updated is not None
    assert entity.image_last_updated >= first_bump
    write_state.assert_called_once()


async def test_async_image_never_touches_image_last_updated(
    hass: HomeAssistant,
) -> None:
    """The official warning cited by the ADR (§3): async_image() must never
    bump image_last_updated itself."""
    entity, coordinator = _make_entity(hass)
    coordinator.data = _frame(b"a", datetime(2026, 8, 17, 11, 42, tzinfo=UTC))

    await entity.async_image()

    assert entity.image_last_updated is None
