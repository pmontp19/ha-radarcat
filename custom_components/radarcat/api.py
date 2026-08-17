"""HTTP client for the Meteocat radar widget (fetch only, no compositing).

Endpoints and formats per docs/01-data-sources.md §2/§14: the metadata dates
use "MM/dd/yyyy HH:mm'Z'" (a literal trailing "Z", not ISO 8601) and every
{zz}/{xxx}/{yyy} path component is UTC and zero-padded. The session is always
injected (Platinum inject_websession, docs/04-architecture.md §5) - this
module never creates one; real callers (the coordinator, T3) pass
async_get_clientsession(hass).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import BASE_Z, FONS_TILES_BASE, METADATA_URL, RADAR_TILES_BASE, RADAR_Z

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "RadarcatConnectionError",
    "RadarcatFormatError",
    "base_tile_url",
    "fetch_metadata",
    "fetch_tile",
    "radar_tile_url",
]

_REQUEST_TIMEOUT_SECONDS = 12
# "MM/dd/yyyy HH:mm'Z'" (docs/01-data-sources.md §2): the trailing Z in the
# format string is a literal character match, not the %Z timezone directive.
_METADATA_DATE_FORMAT = "%m/%d/%Y %H:%MZ"


class RadarcatConnectionError(Exception):
    """Network/timeout/non-200 reaching a Meteocat widget endpoint."""


class RadarcatFormatError(Exception):
    """The metadata response is not the expected JSON shape or date format."""


async def fetch_metadata(session: ClientSession) -> tuple[datetime, datetime]:
    """Fetch (latest_image_utc, system_utc) from METADATA_URL.

    Both returned datetimes are timezone-aware UTC. Raises
    RadarcatConnectionError on network/timeout/non-200, RadarcatFormatError on
    unparseable JSON or dates.
    """
    try:
        async with session.get(
            METADATA_URL, timeout=ClientTimeout(total=_REQUEST_TIMEOUT_SECONDS)
        ) as response:
            response.raise_for_status()
            body = await response.json(content_type=None)
    except (ClientError, TimeoutError) as err:
        raise RadarcatConnectionError(
            f"Could not reach the Meteocat metadata endpoint: {err}"
        ) from err
    except ValueError as err:
        raise RadarcatFormatError(
            f"Metadata response was not valid JSON: {err}"
        ) from err

    try:
        latest_raw = body["dataUltimaImatge"]
        system_raw = body["dataSistema"]
    except (KeyError, TypeError) as err:
        raise RadarcatFormatError(
            f"Metadata response is missing an expected field: {err}"
        ) from err

    return _parse_meteocat_date(latest_raw), _parse_meteocat_date(system_raw)


def _parse_meteocat_date(raw: object) -> datetime:
    """Parse "MM/dd/yyyy HH:mm'Z'" into a timezone-aware UTC datetime."""
    if not isinstance(raw, str):
        raise RadarcatFormatError(f"Expected a date string, got {raw!r}")
    try:
        naive = datetime.strptime(raw, _METADATA_DATE_FORMAT)
    except ValueError as err:
        raise RadarcatFormatError(f"Unparseable Meteocat date {raw!r}: {err}") from err
    return naive.replace(tzinfo=UTC)


async def fetch_tile(session: ClientSession, url: str) -> bytes | None:
    """Fetch one tile PNG, or None (no exception) on a 404 or empty body.

    A missing tile is normal (docs/01-data-sources.md §14.2 - the RadarGrid/
    BaseGrid ranges carry margin indices that legitimately 404). Raises
    RadarcatConnectionError only on a real connection failure.
    """
    try:
        async with session.get(
            url, timeout=ClientTimeout(total=_REQUEST_TIMEOUT_SECONDS)
        ) as response:
            if response.status == 404:
                _LOGGER.debug("Tile not found (expected margin 404): %s", url)
                return None
            response.raise_for_status()
            body = await response.read()
    except (ClientError, TimeoutError) as err:
        raise RadarcatConnectionError(f"Could not fetch tile {url}: {err}") from err

    return body or None


def radar_tile_url(timestamp: datetime, x: int, y: int) -> str:
    """Build a RadarGrid tile URL for a UTC timestamp and (x, y).

    Path is {base}/{YYYY}/{MM}/{DD}/{HH}/{mm}/{zz}/000/000/{xxx}/000/000/{yyy}.png
    (docs/01-data-sources.md §2). timestamp must be timezone-aware (as
    returned by fetch_metadata); it is converted to UTC before formatting.
    """
    path = timestamp.astimezone(UTC).strftime("%Y/%m/%d/%H/%M")
    return (
        f"{RADAR_TILES_BASE}/{path}/{RADAR_Z:02d}/000/000/{x:03d}/000/000/{y:03d}.png"
    )


def base_tile_url(x: int, y: int) -> str:
    """Build a BaseGrid tile URL for (x, y). No timestamp: the base map is static."""
    return f"{FONS_TILES_BASE}/{BASE_Z:02d}/000/000/{x:03d}/000/000/{y:03d}.png"
