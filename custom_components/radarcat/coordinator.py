"""The data coordinator for the radarcat integration.

One ``RadarcatCoordinator`` per config entry owns the rolling window of
composited frames (docs/04-architecture.md §6) and re-encodes it into a
single animated WEBP after every cycle that actually changed something. It
depends on ``api.py``/``compositor.py``'s contract (docs/04-architecture.md
§4/§5), not on their implementation.

Cycle (``_async_update_data``, docs/03-feature-spec.md §4):
1. ``api.fetch_metadata``. A connection/format error never drops the last
   good animation: it is recorded and re-raised as ``UpdateFailed`` so HA
   keeps ``self.data`` untouched (same pattern as ``../ha-cecat``'s
   ``CecatCoordinator``).
2. If ``latest_image_utc`` did not change since the last successful cycle,
   return ``self.data`` unchanged - no tile fetch, no recompute (the
   "isNew" check, mirrors ``RadarStore.refresh()`` in ``../radarcat``).
3. First successful cycle ever (``_frames`` empty), OR the gap between
   ``latest`` and the newest frame already held is anything other than
   exactly one ``FRAME_INTERVAL_MIN`` (a metadata outage spanning more than
   one cycle recovered - see step 1): build the whole ``FRAME_COUNT``-
   timestamp window and compose all of it, discarding whatever stale
   window existed. A partial delta here would otherwise leave a hole in
   the middle of an otherwise 6-min-spaced window.
4. Otherwise (the common case: exactly one interval elapsed): compose only
   the one new frame, append it, and drop the oldest once the window
   exceeds ``FRAME_COUNT``.
5. Base tiles are fetched once and cached, but only once the fetch reaches
   ``MIN_GOOD_BASE_TILES`` - a below-threshold load is used for this call
   (better to show something) but never cached, so the next cycle retries
   the full fetch instead of being stuck with a bad partial set forever
   (port of ``RadarCompositor.ensureBase`` in ``../radarcat``).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.dt import utcnow
from PIL import Image

from . import api
from .compositor import compose_frame, encode_animation
from .const import (
    BASE_X_RANGE,
    BASE_Y_RANGE,
    DOMAIN,
    FRAME_COUNT,
    FRAME_INTERVAL_MIN,
    MIN_GOOD_BASE_TILES,
    RADAR_X_RANGE,
    RADAR_Y_RANGE,
    SCAN_INTERVAL_MIN,
)

_LOGGER = logging.getLogger(__name__)

# Same stale-data floor as ../ha-cecat (docs/04-architecture.md §6): a
# transient error keeps the last good animation visible; only a source that
# has really stopped (older than max(6 x interval, 1h)) goes unavailable.
_STALE_FLOOR = timedelta(hours=1)


@dataclass
class RadarcatData:
    """The published state of the integration: one ready-to-serve animation.

    ``content`` is already-encoded WEBP bytes (docs/04-architecture.md §6) -
    ``image.py`` (T4) serves it as-is, no re-encoding on the read path.
    """

    content: bytes
    latest_timestamp: datetime
    frame_count: int


class RadarcatCoordinator(TimestampDataUpdateCoordinator[RadarcatData]):
    """Fetches, composites and caches the rolling window of radar frames.

    ``always_update=False``: when a cycle finds no new ``dataUltimaImatge``
    it returns the exact same ``RadarcatData`` object, and the dataclass's
    default value equality makes HA skip notifying listeners for that
    no-op cycle - the reactive ``image_last_updated`` bump the ADR
    (docs/04-architecture.md §3) hands to ``image.py`` must only fire when a
    frame genuinely changed, never every ``SCAN_INTERVAL_MIN`` regardless.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Arm the coordinator with the fixed radarcat poll interval."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=SCAN_INTERVAL_MIN),
            config_entry=entry,
            always_update=False,
        )
        # Cached only once >= MIN_GOOD_BASE_TILES tiles were fetched; see
        # _ensure_base_tiles.
        self._base_tiles: dict[tuple[int, int], bytes] | None = None
        # Rolling window, chronological order, at most FRAME_COUNT entries.
        self._frames: list[tuple[datetime, Image.Image]] = []
        self._consecutive_failures = 0
        # Surface of the last failure for diagnostics; unlike the failure
        # counter this is never reset on success (it is history, not state).
        self.last_error: str | None = None

    # ------------------------------------------------------------------
    # Cycle (docs/03-feature-spec.md §4, docs/04-architecture.md §6)
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> RadarcatData:
        """Fetch one cycle and fold it into the rolling frame window."""
        session = async_get_clientsession(self.hass)
        try:
            latest, _system = await api.fetch_metadata(session)
        except (api.RadarcatConnectionError, api.RadarcatFormatError) as err:
            self._record_failure(err)
            raise UpdateFailed(str(err)) from err

        # A successful metadata fetch ends any standing failure streak,
        # whether or not the timestamp actually changed below.
        self._consecutive_failures = 0

        if self.data is not None and latest == self.data.latest_timestamp:
            # "isNew" check (docs/03-feature-spec.md §4): nothing changed at
            # the source, so nothing is re-fetched or recomputed.
            return self.data

        step = timedelta(minutes=FRAME_INTERVAL_MIN)
        if self._frames and latest - self._frames[-1][0] != step:
            # Anything other than exactly one interval since the newest
            # frame already held - most likely a metadata outage that
            # spanned more than one SCAN_INTERVAL_MIN cycle (the exact case
            # the UpdateFailed handling above exists to survive). A
            # delta-only append here would leave a gap in the middle of an
            # otherwise 6-min-spaced window that only closes gradually over
            # the next ~54 min. Simplicity over cleverness: discard the
            # stale window and treat this like a second cold start rather
            # than trying to splice it.
            self._frames = []

        # Cold start (_frames empty, whether from a real first run or the
        # reset above) builds the whole hour-long window in one go, same as
        # RadarAnimator.build() on launch in ../radarcat. Steady state: the
        # other FRAME_COUNT - 1 frames are already in _frames from previous
        # cycles, only the new one is missing.
        timestamps = _frame_set(latest, FRAME_COUNT) if not self._frames else [latest]

        base_tiles = await self._ensure_base_tiles(session)

        for timestamp in timestamps:
            radar_tiles = await self._fetch_radar_tiles(session, timestamp)
            frame = compose_frame(base_tiles, radar_tiles)
            self._frames.append((timestamp, frame))

        while len(self._frames) > FRAME_COUNT:
            self._frames.pop(0)

        content = encode_animation([frame for _, frame in self._frames])
        return RadarcatData(
            content=content,
            latest_timestamp=self._frames[-1][0],
            frame_count=len(self._frames),
        )

    # ------------------------------------------------------------------
    # Tile fetching
    # ------------------------------------------------------------------

    async def _ensure_base_tiles(
        self, session: ClientSession
    ) -> dict[tuple[int, int], bytes]:
        """Return the cached base tiles, or fetch and maybe cache them.

        Port of ``RadarCompositor.ensureBase`` in ``../radarcat``: a fetch
        that reaches ``MIN_GOOD_BASE_TILES`` becomes the cache for every
        later cycle (the base map is static, no point re-fetching it every
        6 min); a fetch that falls short is still returned for THIS call
        (better to render something) but is deliberately not cached, so a
        transient network blip does not freeze the integration on a
        half-blank base map forever - the next cycle tries the full fetch
        again instead of being stuck with the bad partial result.
        """
        if self._base_tiles is not None:
            return self._base_tiles
        tiles = await self._fetch_tile_grid(
            session, BASE_X_RANGE, BASE_Y_RANGE, api.base_tile_url
        )
        if len(tiles) >= MIN_GOOD_BASE_TILES:
            self._base_tiles = tiles
        return tiles

    async def _fetch_radar_tiles(
        self, session: ClientSession, timestamp: datetime
    ) -> dict[tuple[int, int], bytes]:
        """Fetch every RadarGrid tile for one frame's timestamp."""
        return await self._fetch_tile_grid(
            session,
            RADAR_X_RANGE,
            RADAR_Y_RANGE,
            lambda x, y: api.radar_tile_url(timestamp, x, y),
        )

    async def _fetch_tile_grid(
        self,
        session: ClientSession,
        x_range: range,
        y_range: range,
        url_for: Callable[[int, int], str],
    ) -> dict[tuple[int, int], bytes]:
        """Fetch every (x, y) in the grid concurrently, dropping the misses.

        No ordering dependency exists between tiles (docs/05-implementation-
        plan.md T3), so a plain ``asyncio.gather`` is enough - Meteocat's
        widget itself fires the same fan-out per refresh.
        """
        coords = [(x, y) for y in y_range for x in x_range]
        results = await asyncio.gather(
            *(self._fetch_one_tile(session, url_for(x, y)) for x, y in coords)
        )
        return {
            coord: data
            for coord, data in zip(coords, results, strict=True)
            if data is not None
        }

    async def _fetch_one_tile(self, session: ClientSession, url: str) -> bytes | None:
        """Fetch one tile, treating a real connection failure as a miss too.

        ``api.fetch_tile`` already turns a 404/empty body into ``None``
        (docs/01-data-sources.md §14.2); a genuine connection error
        (timeout, DNS, 5xx) is caught here and folded into the same "missing
        tile" outcome rather than aborting the whole cycle, matching
        ``RadarCompositor.fetch`` in ``../radarcat`` (any failure there
        becomes ``nil``, not a thrown error) - one flaky tile must not cost
        the other ~35-41 tiles of the same frame/base load.
        """
        try:
            return await api.fetch_tile(session, url)
        except api.RadarcatConnectionError as err:
            _LOGGER.debug("Tile fetch failed, treating as missing: %s", err)
            return None

    # ------------------------------------------------------------------
    # Availability (docs/04-architecture.md §6, same pattern as CecatCoordinator)
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Whether the last good animation is fresh enough to present.

        A transient error keeps the last known animation visible; only a
        source that stopped publishing for real (older than
        ``max(6 x interval, 1h)``) goes ``unavailable``.
        """
        if self.last_update_success_time is None:
            return False
        return utcnow() - self.last_update_success_time <= self._stale_after

    @property
    def _stale_after(self) -> timedelta:
        """``max(6 x interval, 1h)``: how long the last good data stays trusted."""
        interval = self.update_interval or timedelta(minutes=SCAN_INTERVAL_MIN)
        return max(interval * 6, _STALE_FLOOR)

    # ------------------------------------------------------------------
    # Resilience bookkeeping (read by diagnostics.py, T4)
    # ------------------------------------------------------------------

    def _record_failure(self, err: Exception) -> None:
        """Count the failure and stamp ``last_error`` for diagnostics."""
        self.last_error = str(err) or type(err).__name__
        self._consecutive_failures += 1

    @property
    def consecutive_failures(self) -> int:
        """How many fetches in a row have failed."""
        return self._consecutive_failures


def _frame_set(latest: datetime, count: int) -> list[datetime]:
    """Build ``count`` timestamps ending at ``latest``, ascending order.

    Port of ``RadarAnimator.frameSet`` (../radarcat/Sources/RadarCat/
    RadarAnimator.swift:243-245): ``latest``, ``latest - 6min``, ...,
    ``latest - (count-1)*6min``, then reversed into chronological order.
    """
    step = timedelta(minutes=FRAME_INTERVAL_MIN)
    return [latest - step * i for i in reversed(range(count))]
