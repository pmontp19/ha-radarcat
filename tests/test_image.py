"""Tests for RadarcatEntity (entity.py) and both image.py entities.

``coordinator.py`` (T3) is being built in parallel and may not exist yet, so
these use a minimal fake coordinator matching the public surface the
BINDING CONTRACT (``docs/04-architecture.md`` §6) promises: ``.hass``,
``.config_entry``, ``.data`` (``RadarcatData | None``), ``.available``.
Entity-base coverage (unique_id, DeviceInfo, availability delegation) is
folded in here rather than a separate ``test_entity.py`` - there is nothing
left for a standalone file to isolate.

Two platform entities exist since v0.1.1 (docs/04-architecture.md §7):
``RadarcatImage`` (the 10-frame animation) and ``RadarcatStaticImage`` (only
the newest frame, always present alongside it). Both subclass the shared
``_RadarcatImageBase``, so the ``image_last_updated`` seed/bump tests below
are parametrized over both rather than only covering one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from custom_components.radarcat.const import (
    ATTRIBUTION,
    DOMAIN,
    IMAGE_CONTENT_TYPE,
    STATIC_IMAGE_CONTENT_TYPE,
)
from custom_components.radarcat.image import RadarcatImage, RadarcatStaticImage
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import EntityDescription
from pytest_homeassistant_custom_component.common import MockConfigEntry

_DESCRIPTION = EntityDescription(key="radar")
_STATIC_DESCRIPTION = EntityDescription(key="radar_actual")

# (entity class, its EntityDescription) - the two always-present image
# entities (docs/03-feature-spec.md §2), used to parametrize the behavior
# _RadarcatImageBase is responsible for so neither is tested only once.
_IMAGE_ENTITY_PARAMS = [
    pytest.param(RadarcatImage, _DESCRIPTION, id="radar"),
    pytest.param(RadarcatStaticImage, _STATIC_DESCRIPTION, id="radar_actual"),
]


@dataclass
class _FakeRadarcatData:
    """Shape-compatible stand-in for coordinator.RadarcatData."""

    content: bytes
    static_content: bytes
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


def _make_static_entity(
    hass: HomeAssistant,
) -> tuple[RadarcatStaticImage, _FakeCoordinator]:
    entry = MockConfigEntry(domain=DOMAIN, data={})
    coordinator = _FakeCoordinator(hass, entry)
    return RadarcatStaticImage(coordinator, _STATIC_DESCRIPTION), coordinator


# ---------------------------------------------------------------------------
# RadarcatEntity: device, attribution, unique_id, availability
# ---------------------------------------------------------------------------


def test_unique_id_is_entry_id_prefixed_by_key(hass: HomeAssistant) -> None:
    """unique_id = f"{entry_id}_{description.key}" (docs/04-architecture.md §7)."""
    entity, coordinator = _make_entity(hass)
    assert entity.unique_id == f"{coordinator.config_entry.entry_id}_radar"


def test_entity_id_is_pinned_regardless_of_translated_name(hass: HomeAssistant) -> None:
    """entity_id is exactly image.radarcat_radar, not derived from the
    translated name "Radar" - which today only coincidentally slugifies to
    the same result (see _RadarcatImageBase.__init__: "RadarCat" + "Radar"
    -> radarcat_radar). Same pin, same shape of test as
    test_static_entity_id_is_pinned_regardless_of_translated_name below.
    """
    entity, _ = _make_entity(hass)
    assert entity.entity_id == "image.radarcat_radar"


def test_entity_id_survives_a_translated_name_change(hass: HomeAssistant) -> None:
    """The pin holds even if the entity's translated name were to change.

    A subclass whose translation_key would slugify to something completely
    different still gets the SAME pinned entity_id, because
    _RadarcatImageBase.__init__ derives it from entity_description.key, never
    from the (translation-dependent) name property - proving this is a real
    pin, not just today's translation happening to agree with it.
    """

    class _DriftingNameImage(RadarcatImage):
        _attr_translation_key = "this_translation_key_does_not_exist_at_all"

    entry = MockConfigEntry(domain=DOMAIN, data={})
    coordinator = _FakeCoordinator(hass, entry)

    entity = _DriftingNameImage(coordinator, _DESCRIPTION)

    assert entity.entity_id == "image.radarcat_radar"


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


def test_both_image_entities_share_the_same_device(hass: HomeAssistant) -> None:
    """RadarcatImage and RadarcatStaticImage attach to the identical DeviceInfo.

    Both are "always present" on the same single service device
    (docs/03-feature-spec.md §2), never two separate devices.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={})
    coordinator = _FakeCoordinator(hass, entry)
    radar = RadarcatImage(coordinator, _DESCRIPTION)
    radar_actual = RadarcatStaticImage(coordinator, _STATIC_DESCRIPTION)

    assert radar.device_info == radar_actual.device_info


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
        static_content=b"png-bytes",
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
# RadarcatStaticImage: the v0.1.1 always-present latest-frame-only entity
# ---------------------------------------------------------------------------


def test_static_unique_id_is_entry_id_prefixed_by_key(hass: HomeAssistant) -> None:
    """unique_id follows the same {entry_id}_{key} pattern, key='radar_actual'."""
    entity, coordinator = _make_static_entity(hass)
    assert entity.unique_id == f"{coordinator.config_entry.entry_id}_radar_actual"


def test_static_entity_id_is_pinned_regardless_of_translated_name(
    hass: HomeAssistant,
) -> None:
    """entity_id is exactly image.radarcat_radar_actual (docs/03-feature-
    spec.md §2), not derived from the (English) translated name "Current
    radar" - which would otherwise slugify to "current_radar" on an
    English-language HA instance. See RadarcatStaticImage.__init__.
    """
    entity, _ = _make_static_entity(hass)
    assert entity.entity_id == "image.radarcat_radar_actual"


def test_static_content_type_is_png(hass: HomeAssistant) -> None:
    """_attr_content_type is STATIC_IMAGE_CONTENT_TYPE ('image/png', §4.4)."""
    entity, _ = _make_static_entity(hass)
    assert entity.content_type == STATIC_IMAGE_CONTENT_TYPE == "image/png"


def test_static_translation_key_matches_the_landed_strings_json(
    hass: HomeAssistant,
) -> None:
    """_attr_translation_key = 'radar_actual' matches entity.image.radar_actual."""
    entity, _ = _make_static_entity(hass)
    assert entity.translation_key == "radar_actual"


async def test_static_async_image_returns_static_content_when_data_present(
    hass: HomeAssistant,
) -> None:
    """async_image returns coordinator.data.static_content, never .content."""
    entity, coordinator = _make_static_entity(hass)
    coordinator.data = _FakeRadarcatData(
        content=b"webp-bytes",
        static_content=b"png-bytes",
        latest_timestamp=datetime(2026, 8, 17, 11, 42, tzinfo=UTC),
        frame_count=10,
    )

    assert await entity.async_image() == b"png-bytes"


async def test_static_async_image_returns_none_before_first_refresh(
    hass: HomeAssistant,
) -> None:
    """async_image returns None while coordinator.data is still None."""
    entity, _ = _make_static_entity(hass)

    assert await entity.async_image() is None


# ---------------------------------------------------------------------------
# image_last_updated: bumped only from the coordinator listener, only when
# the frame set actually advanced (docs/04-architecture.md §3 - never inside
# async_image() itself).
# ---------------------------------------------------------------------------


def _frame(content: bytes, timestamp: datetime) -> _FakeRadarcatData:
    return _FakeRadarcatData(
        content=content,
        static_content=b"static-" + content,
        latest_timestamp=timestamp,
        frame_count=10,
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


# ---------------------------------------------------------------------------
# _RadarcatImageBase: the shared seed/bump logic above was found missing for
# RadarcatImage by an earlier adversarial review (AGENTS.md "State of the
# repository") and then moved into the shared base specifically so
# RadarcatStaticImage could not silently lose it - these two tests exercise
# BOTH entity classes explicitly (docs/04-architecture.md §7's "shared" is
# a claim, not just a refactor), not only the one covered above.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entity_cls, description", _IMAGE_ENTITY_PARAMS)
def test_init_seeds_image_last_updated_for_both_image_entities(
    hass: HomeAssistant,
    entity_cls: type[RadarcatImage | RadarcatStaticImage],
    description: EntityDescription,
) -> None:
    """Cold start: BOTH image entities seed image_last_updated immediately
    when coordinator.data is already populated at construction time - the
    exact fix (AGENTS.md) that moving this logic into _RadarcatImageBase
    must not lose for the new RadarcatStaticImage entity.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={})
    coordinator = _FakeCoordinator(hass, entry)
    coordinator.data = _frame(b"a", datetime(2026, 8, 17, 11, 42, tzinfo=UTC))

    entity = entity_cls(coordinator, description)

    assert entity.image_last_updated is not None


@pytest.mark.parametrize("entity_cls, description", _IMAGE_ENTITY_PARAMS)
def test_handle_coordinator_update_bumps_for_both_image_entities(
    hass: HomeAssistant,
    entity_cls: type[RadarcatImage | RadarcatStaticImage],
    description: EntityDescription,
) -> None:
    """Steady state: BOTH image entities bump image_last_updated on the same
    coordinator update that publishes a genuinely new frame.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={})
    coordinator = _FakeCoordinator(hass, entry)
    entity = entity_cls(coordinator, description)
    assert entity.image_last_updated is None

    coordinator.data = _frame(b"a", datetime(2026, 8, 17, 11, 42, tzinfo=UTC))
    with patch.object(entity, "async_write_ha_state") as write_state:
        entity._handle_coordinator_update()

    assert entity.image_last_updated is not None
    write_state.assert_called_once()
