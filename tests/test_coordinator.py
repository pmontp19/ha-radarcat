"""Tests for RadarcatCoordinator (docs/04-architecture.md §6).

No network: every metadata/tile request goes through ``aioresponses`` on top
of the HA-injected client session (docs/04-architecture.md §5's
``inject_websession`` rule). Generic tile mocks use a regex pattern so any
(x, y)/timestamp combination succeeds without registering dozens of exact
URLs; the base-tile-threshold test needs precise per-tile control instead, so
it registers exact URLs one at a time (see ``_register_base_tiles``).
"""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from aiohttp import ClientError
from aioresponses import aioresponses
from custom_components.radarcat import api
from custom_components.radarcat.const import (
    BASE_X_RANGE,
    BASE_Y_RANGE,
    DOMAIN,
    FONS_TILES_BASE,
    FRAME_COUNT,
    FRAME_INTERVAL_MIN,
    METADATA_URL,
    MIN_GOOD_BASE_TILES,
    RADAR_TILES_BASE,
    RADAR_X_RANGE,
    RADAR_Y_RANGE,
)
from custom_components.radarcat.coordinator import RadarcatCoordinator, _frame_set
from homeassistant.core import HomeAssistant
from PIL import Image
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.conftest import FakeClock, load_fixture

T0 = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
T1 = T0 + timedelta(minutes=FRAME_INTERVAL_MIN)


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Build and register a radarcat MockConfigEntry."""
    entry = MockConfigEntry(domain=DOMAIN, title="RadarCat", data={})
    entry.add_to_hass(hass)
    return entry


def _metadata_payload(latest: datetime) -> dict[str, str]:
    """A metadata JSON body carrying ``latest`` as ``dataUltimaImatge``.

    Format matches api._METADATA_DATE_FORMAT ("MM/dd/yyyy HH:mm'Z'",
    docs/01-data-sources.md §2) - the trailing Z is a literal character.
    """
    system = latest + timedelta(minutes=7)
    return {
        "dataUltimaImatge": latest.strftime("%m/%d/%Y %H:%MZ"),
        "dataSistema": system.strftime("%m/%d/%Y %H:%MZ"),
    }


def _mock_generic_tiles(mock_http: aioresponses) -> None:
    """Catch-all mocks: any base/radar tile URL succeeds, unlimited calls.

    aioresponses still records the real requested URL (not the pattern) in
    ``mock_http.requests``, so per-endpoint call counting below stays exact
    even though these mocks match every (x, y)/timestamp combination.
    """
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


def _register_base_tiles(mock_http: aioresponses, good_count: int) -> None:
    """Queue one more response per BaseGrid tile: the first ``good_count`` succeed.

    Calling this twice for the same grid queues two responses per URL
    (aioresponses serves same-URL registrations in FIFO order), letting one
    test drive two different coordinator cycles against the same tile set.
    """
    body = load_fixture("base_tile_z8_x128_y160.png")
    coords = [(x, y) for y in BASE_Y_RANGE for x in BASE_X_RANGE]
    for i, (x, y) in enumerate(coords):
        url = api.base_tile_url(x, y)
        if i < good_count:
            mock_http.get(url, body=body, content_type="image/png")
        else:
            mock_http.get(url, status=404)


def _tile_call_count(mock_http: aioresponses, base_url: str) -> int:
    """How many GETs actually landed on tiles under ``base_url``."""
    return sum(
        len(calls)
        for (method, url), calls in mock_http.requests.items()
        if method == "GET" and str(url).startswith(base_url)
    )


# ---------------------------------------------------------------------------
# _frame_set: pure helper, no HA/network involved
# ---------------------------------------------------------------------------


def test_frame_set_is_ascending_ending_at_latest() -> None:
    """10 timestamps, 6 min apart, oldest first, newest == latest."""
    frames = _frame_set(T0, FRAME_COUNT)

    assert len(frames) == FRAME_COUNT
    assert frames == sorted(frames)
    assert frames[-1] == T0
    assert frames[0] == T0 - timedelta(minutes=FRAME_INTERVAL_MIN * (FRAME_COUNT - 1))


# ---------------------------------------------------------------------------
# First cycle: build the whole FRAME_COUNT window
# ---------------------------------------------------------------------------


async def test_first_cycle_builds_all_frames(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A cold start composes FRAME_COUNT frames and encodes one animated WEBP."""
    mock_http.get(METADATA_URL, payload=_metadata_payload(T0))
    _mock_generic_tiles(mock_http)
    coord = RadarcatCoordinator(hass, _make_entry(hass))

    await coord.async_refresh()

    assert coord.data.frame_count == FRAME_COUNT
    assert coord.data.latest_timestamp == T0
    assert len(coord._frames) == FRAME_COUNT
    assert coord._frames[-1][0] == T0
    assert coord._frames[0][0] == T0 - timedelta(
        minutes=FRAME_INTERVAL_MIN * (FRAME_COUNT - 1)
    )

    # n_frames is not asserted here: every mocked tile is byte-identical
    # across all 10 timestamps, and libwebp's lossless encoder (minimize_size
    # in encode_animation) is free to collapse truly-identical consecutive
    # frames - a real cycle never has identical frames since the radar echo
    # changes, and encode_animation's own frame-count fidelity is already
    # covered by test_compositor.py with genuinely distinct frames.
    animation = Image.open(io.BytesIO(coord.data.content))
    assert animation.format == "WEBP"

    # static_content (docs/04-architecture.md §4.4/§6) is a plain PNG of the
    # same newest frame already held in _frames, not a separate animation.
    static = Image.open(io.BytesIO(coord.data.static_content))
    assert static.format == "PNG"
    assert static.convert("RGB").tobytes() == coord._frames[-1][1].tobytes()


# ---------------------------------------------------------------------------
# Unchanged timestamp: reuse self.data, no new fetch
# ---------------------------------------------------------------------------


async def test_unchanged_timestamp_reuses_data_without_refetch(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A second cycle with the same dataUltimaImatge fetches no tile at all."""
    mock_http.get(METADATA_URL, payload=_metadata_payload(T0), repeat=True)
    _mock_generic_tiles(mock_http)
    coord = RadarcatCoordinator(hass, _make_entry(hass))
    await coord.async_refresh()
    before = coord.data
    base_calls = _tile_call_count(mock_http, FONS_TILES_BASE)
    radar_calls = _tile_call_count(mock_http, RADAR_TILES_BASE)

    await coord.async_refresh()

    assert coord.data is before  # the exact same object, not a recompute
    assert _tile_call_count(mock_http, FONS_TILES_BASE) == base_calls
    assert _tile_call_count(mock_http, RADAR_TILES_BASE) == radar_calls


# ---------------------------------------------------------------------------
# New timestamp: delta-only fetch, window stays FRAME_COUNT, oldest dropped
# ---------------------------------------------------------------------------


async def test_new_timestamp_fetches_only_the_delta_frame(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A new dataUltimaImatge composes exactly one frame and drops the oldest."""
    mock_http.get(METADATA_URL, payload=_metadata_payload(T0))
    mock_http.get(METADATA_URL, payload=_metadata_payload(T1))
    _mock_generic_tiles(mock_http)
    coord = RadarcatCoordinator(hass, _make_entry(hass))
    await coord.async_refresh()
    base_calls_after_first = _tile_call_count(mock_http, FONS_TILES_BASE)
    radar_calls_after_first = _tile_call_count(mock_http, RADAR_TILES_BASE)

    await coord.async_refresh()

    assert coord.data.frame_count == FRAME_COUNT
    assert coord.data.latest_timestamp == T1
    assert len(coord._frames) == FRAME_COUNT
    assert coord._frames[-1][0] == T1
    assert coord._frames[0][0] == T1 - timedelta(
        minutes=FRAME_INTERVAL_MIN * (FRAME_COUNT - 1)
    )

    radar_tiles_per_frame = len(RADAR_X_RANGE) * len(RADAR_Y_RANGE)
    assert (
        _tile_call_count(mock_http, RADAR_TILES_BASE) - radar_calls_after_first
        == radar_tiles_per_frame
    )
    # Base tiles are already cached from the first cycle: zero new base calls.
    assert _tile_call_count(mock_http, FONS_TILES_BASE) == base_calls_after_first

    # static_content tracks the new newest frame too, still with no extra
    # fetch (the delta-only tile-call assertions above already prove that -
    # encode_static only ever reads self._frames[-1], see coordinator.py).
    static = Image.open(io.BytesIO(coord.data.static_content))
    assert static.convert("RGB").tobytes() == coord._frames[-1][1].tobytes()


async def test_gap_larger_than_one_interval_rebuilds_a_contiguous_window(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A jump of more than one interval (a recovered multi-cycle outage)
    rebuilds the whole window instead of leaving a gap in the middle.

    Without the fix, the delta-only path would append just this one new
    timestamp and drop just the single oldest frame, leaving every
    consecutive pair FRAME_INTERVAL_MIN apart except the one spot where the
    outage happened - a hole that would only close gradually over the
    following cycles instead of being fixed immediately.
    """
    gapped = T0 + timedelta(minutes=FRAME_INTERVAL_MIN * 3)
    mock_http.get(METADATA_URL, payload=_metadata_payload(T0))
    mock_http.get(METADATA_URL, payload=_metadata_payload(gapped))
    _mock_generic_tiles(mock_http)
    coord = RadarcatCoordinator(hass, _make_entry(hass))
    await coord.async_refresh()  # cycle 1: cold start, window ends at T0

    await coord.async_refresh()  # cycle 2: latest jumped 3 intervals ahead

    assert coord.data.frame_count == FRAME_COUNT
    assert coord.data.latest_timestamp == gapped
    assert len(coord._frames) == FRAME_COUNT
    timestamps = [ts for ts, _ in coord._frames]
    assert timestamps[-1] == gapped
    gaps = {b - a for a, b in pairwise(timestamps)}
    assert gaps == {timedelta(minutes=FRAME_INTERVAL_MIN)}  # fully contiguous


# ---------------------------------------------------------------------------
# Base-tile caching threshold (RadarCompositor.ensureBase port)
# ---------------------------------------------------------------------------


async def test_below_threshold_base_fetch_is_used_but_not_cached(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A load below MIN_GOOD_BASE_TILES is used once, never cached, and retried."""
    total_base_tiles = len(BASE_X_RANGE) * len(BASE_Y_RANGE)
    assert total_base_tiles > MIN_GOOD_BASE_TILES  # sanity: full grid clears the bar

    mock_http.get(METADATA_URL, payload=_metadata_payload(T0))
    mock_http.get(METADATA_URL, payload=_metadata_payload(T1))
    _register_base_tiles(mock_http, good_count=MIN_GOOD_BASE_TILES - 1)  # cycle 1
    _register_base_tiles(mock_http, good_count=total_base_tiles)  # cycle 2
    mock_http.get(
        re.compile(rf"^{re.escape(RADAR_TILES_BASE)}/.*"),
        body=load_fixture("radar_tile_z7_x65_y80_no_echo.png"),
        content_type="image/png",
        repeat=True,
    )
    coord = RadarcatCoordinator(hass, _make_entry(hass))

    await coord.async_refresh()  # cycle 1: below-threshold base load

    assert coord.data is not None  # still composed something, better than nothing
    assert coord._base_tiles is None  # not cached: below MIN_GOOD_BASE_TILES

    await coord.async_refresh()  # cycle 2: must retry the full base fetch

    assert coord._base_tiles is not None
    assert len(coord._base_tiles) == total_base_tiles
    assert _tile_call_count(mock_http, FONS_TILES_BASE) == total_base_tiles * 2


# ---------------------------------------------------------------------------
# Metadata failure: UpdateFailed, self.data preserved
# ---------------------------------------------------------------------------


async def test_metadata_failure_preserves_data_and_records_the_error(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A failed metadata fetch keeps self.data and counts the failure.

    ``async_refresh`` itself never raises (HA's coordinator catches
    ``UpdateFailed`` internally); the failure surfaces as
    ``last_update_success is False`` and a bumped failure counter instead.
    """
    mock_http.get(METADATA_URL, payload=_metadata_payload(T0))
    _mock_generic_tiles(mock_http)
    mock_http.get(METADATA_URL, status=500)
    coord = RadarcatCoordinator(hass, _make_entry(hass))
    await coord.async_refresh()
    good_data = coord.data

    await coord.async_refresh()

    assert coord.data is good_data
    assert coord.last_update_success is False
    assert coord.last_error is not None
    assert coord.consecutive_failures == 1


async def test_metadata_format_error_also_preserves_data(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A malformed metadata body (RadarcatFormatError) is handled the same way."""
    mock_http.get(METADATA_URL, payload=_metadata_payload(T0))
    _mock_generic_tiles(mock_http)
    mock_http.get(METADATA_URL, payload={"unexpected": "shape"})
    coord = RadarcatCoordinator(hass, _make_entry(hass))
    await coord.async_refresh()
    good_data = coord.data

    await coord.async_refresh()

    assert coord.data is good_data
    assert coord.last_update_success is False


# ---------------------------------------------------------------------------
# Availability (docs/04-architecture.md §6)
# ---------------------------------------------------------------------------


async def test_available_true_right_after_a_good_cycle(
    hass: HomeAssistant, mock_http: aioresponses, clock: FakeClock, monkeypatch
) -> None:
    """Right after a successful cycle, available is True."""
    monkeypatch.setattr("custom_components.radarcat.coordinator.utcnow", clock)
    mock_http.get(METADATA_URL, payload=_metadata_payload(T0))
    _mock_generic_tiles(mock_http)
    coord = RadarcatCoordinator(hass, _make_entry(hass))
    await coord.async_refresh()
    coord.last_update_success_time = clock.now  # align to the fake clock

    assert coord.available is True


async def test_available_false_once_past_the_stale_window(
    hass: HomeAssistant, mock_http: aioresponses, clock: FakeClock, monkeypatch
) -> None:
    """Data older than max(6 x interval, 1h) flips available to False."""
    monkeypatch.setattr("custom_components.radarcat.coordinator.utcnow", clock)
    mock_http.get(METADATA_URL, payload=_metadata_payload(T0))
    _mock_generic_tiles(mock_http)
    coord = RadarcatCoordinator(hass, _make_entry(hass))
    await coord.async_refresh()
    coord.last_update_success_time = clock.now

    clock.advance(minutes=30)  # 6 min interval -> floor is 1h
    assert coord.available is True
    clock.advance(hours=1)  # total 1h30, past the 1h floor
    assert coord.available is False


def test_available_false_before_any_successful_fetch(hass: HomeAssistant) -> None:
    """With no successful fetch yet, there is nothing fresh to present."""
    coord = RadarcatCoordinator(hass, _make_entry(hass))
    assert coord.available is False


# ---------------------------------------------------------------------------
# A single flaky tile must not abort the whole cycle
# ---------------------------------------------------------------------------


async def test_a_tile_connection_error_is_treated_as_a_missing_tile(
    hass: HomeAssistant, mock_http: aioresponses
) -> None:
    """A real connection failure on one tile is folded into "missing", not raised.

    Matches ``RadarCompositor.fetch`` in ``../radarcat``: any per-tile
    failure becomes a gap in the frame, never an aborted cycle.
    """
    mock_http.get(METADATA_URL, payload=_metadata_payload(T0))
    flaky_url = api.radar_tile_url(
        T0, next(iter(RADAR_X_RANGE)), next(iter(RADAR_Y_RANGE))
    )
    mock_http.get(flaky_url, exception=ClientError("boom"))
    _mock_generic_tiles(mock_http)
    coord = RadarcatCoordinator(hass, _make_entry(hass))

    await coord.async_refresh()

    assert coord.data is not None
    assert coord.data.frame_count == FRAME_COUNT
    assert coord.last_update_success is True
